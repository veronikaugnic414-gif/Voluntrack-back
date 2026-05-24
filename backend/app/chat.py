from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from typing import List, Dict, Optional
import json
from contextlib import contextmanager

from app.database import get_db, SessionLocal
from app.models import Message, User
from app.schemas import MessageResponse
from app.auth import get_current_user
from app.security import decode_access_token

router = APIRouter(tags=["Чат (WebSockets та Історія)"])


# 1. ENDPOINT: СПИСОК АКТИВНИХ ДІАЛОГІВ ДЛЯ СТОРІНКИ CHAT.JS
@router.get("/chat/conversations")
def get_conversations(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # 💡 ВИПРАВЛЕНО: Чистий Python-алгоритм групування розмов для 100% сумісності з SQLite
    # Витягуємо всі повідомлення, пов'язані з поточним користувачем
    all_messages = db.query(Message).filter(
        or_(Message.sender_id == current_user.id, Message.receiver_id == current_user.id)
    ).order_by(Message.created_at.desc()).all()

    # Словник для збереження лише найсвіжішого повідомлення для кожного співрозмовника
    latest_messages_dict = {}
    for msg in all_messages:
        partner_id = msg.receiver_id if msg.sender_id == current_user.id else msg.sender_id
        
        if partner_id not in latest_messages_dict:
            latest_messages_dict[partner_id] = msg

    conversations = []
    for partner_id, msg in latest_messages_dict.items():
        partner = db.query(User).filter(User.id == partner_id).first()
        
        if partner:
            partner_name = partner.name if partner.role == "organization" else f"{partner.name} {partner.surname or ''}".strip()
            conversations.append({
                "partner_id": partner.id,
                "partner_name": partner_name or "Користувач Voluntrack",
                "last_message": msg.text,
                "last_message_time": msg.created_at.isoformat(),
                "unread_count": 0  
            })

    return conversations


# 2. ENDPOINT: ОТРИМАННЯ ІСТОРІЇ ЛИСТУВАННЯ
@router.get("/chat/history/{other_user_id}", response_model=List[MessageResponse])
def get_chat_history(
    other_user_id: int, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    messages = db.query(Message).filter(
        ((Message.sender_id == current_user.id) & (Message.receiver_id == other_user_id)) |
        ((Message.sender_id == other_user_id) & (Message.receiver_id == current_user.id))
    ).order_by(Message.created_at.asc()).all()
    
    return messages


# --- МАГІЯ WEBSOCKETS ---

class ConnectionManager:
    def __init__(self):
        # Хранилище активних з'єднань: {user_id: WebSocket}
        self.active_connections: Dict[int, WebSocket] = {}

    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        self.active_connections[user_id] = websocket
        await self.broadcast_online_status()

    # 💡 ВИПРАВЛЕНО: Метод зроблено асинхронним, оскільки всередині викликається await
    async def disconnect(self, user_id: int):
        if user_id in self.active_connections:
            del self.active_connections[user_id]
        await self.broadcast_online_status()

    async def broadcast_online_status(self):
        online_users = list(self.active_connections.keys())
        for connection in self.active_connections.values():
            try:
                await connection.send_json({
                    "type": "online_status",
                    "users": online_users
                })
            except Exception:
                pass

    async def send_personal_message(self, message_data: dict, receiver_id: int):
        if receiver_id in self.active_connections:
            websocket = self.active_connections[receiver_id]
            try:
                await websocket.send_json({
                    "type": "message",
                    "data": message_data
                })
            except Exception:
                await self.disconnect(receiver_id)

manager = ConnectionManager()


@contextmanager
def get_websocket_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Маршрут WebSocket-труби
@router.websocket("/chat/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(...)):
    email = decode_access_token(token)
    if not email:
        await websocket.close(code=4008)
        return

    with get_websocket_db() as db:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            await websocket.close(code=4008)
            return
        user_id = user.id

    await manager.connect(websocket, user_id)
    
    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            receiver_id = int(message_data.get("receiver_id"))
            text = message_data.get("text")
            
            if not text or not receiver_id:
                continue

            with get_websocket_db() as db:
                new_message = Message(sender_id=user_id, receiver_id=receiver_id, text=text)
                db.add(new_message)
                db.commit()
                db.refresh(new_message)
                
                response_data = {
                    "id": new_message.id,
                    "sender_id": user_id,
                    "receiver_id": receiver_id,
                    "text": text,
                    "created_at": new_message.created_at.isoformat()
                }

            await manager.send_personal_message(response_data, receiver_id)
            await manager.send_personal_message(response_data, user_id)
            
    except WebSocketDisconnect:
        await manager.disconnect(user_id)