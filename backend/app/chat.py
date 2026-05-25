from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from typing import List, Dict, Optional
import json
from contextlib import contextmanager

from app.database import get_db, SessionLocal
from app.models import Message, User, Complaint # 💡 Додали Complaint для маркування блокувань
from app.schemas import MessageResponse
from app.auth import get_current_user
from app.security import decode_access_token

router = APIRouter(tags=["Чат (WebSockets та Історія)"])


# 💡 НОВИЙ ЕНДПОІНТ: БЛОКУВАННЯ / РОЗБЛОКУВАННЯ КОРИСТУВАЧА (Без міграцій БД)
@router.post("/chat/block/{other_user_id}")
def toggle_block_user(other_user_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.id == other_user_id:
        raise HTTPException(status_code=400, detail="Ви не можете заблокувати самого себе")
        
    # Шукаємо, чи є вже активне блокування
    existing_block = db.query(Complaint).filter(
        Complaint.author_id == current_user.id,
        Complaint.post_id == None, # Маркер того, що це не скарга на пост, а бан юзера
        Complaint.text == f"[BLOCKED] user_id:{other_user_id}"
    ).first()

    if existing_block:
        db.delete(existing_block)
        db.commit()
        return {"status": "unblocked", "message": "Користувача успішно розблоковано! ✅"}
        
    # Якщо блокування немає — створюємо його
    new_block = Complaint(
        text=f"[BLOCKED] user_id:{other_user_id}",
        post_id=None,
        author_id=current_user.id,
        is_resolved=True # Помічаємо як технічний запис
    )
    db.add(new_block)
    db.commit()
    return {"status": "blocked", "message": "Користувача заблоковано. Листування призупинено. 🚫"}


# 1. ENDPOINT: СПИСОК АКТИВНИХ ДІАЛОГІВ ДЛЯ СТОРІНКИ CHAT.JS
@router.get("/chat/conversations")
def get_conversations(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    all_messages = db.query(Message).filter(
        or_(Message.sender_id == current_user.id, Message.receiver_id == current_user.id)
    ).order_by(Message.created_at.desc()).all()

    latest_messages_dict = {}
    for msg in all_messages:
        partner_id = msg.receiver_id if msg.sender_id == current_user.id else msg.sender_id
        if partner_id not in latest_messages_dict:
            latest_messages_dict[partner_id] = msg

    # Витягуємо список тих, кого заблокував поточний юзер, і тих, хто заблокував його
    blocked_by_me = {
        int(c.text.split(":")[-1]) for c in db.query(Complaint).filter(
            Complaint.author_id == current_user.id, 
            Complaint.text.like("[BLOCKED] user_id:%")
        ).all()
    }
    
    conversations = []
    for partner_id, msg in latest_messages_dict.items():
        partner = db.query(User).filter(User.id == partner_id).first()
        
        if partner:
            partner_name = partner.name if partner.role == "organization" else f"{partner.name} {partner.surname or ''}".strip()
            
            # Перевіряємо, чи заблокований цей діалог взагалі
            is_muted = partner_id in blocked_by_me
            
            conversations.append({
                "partner_id": partner.id,
                "partner_name": partner_name or "Користувач Voluntrack",
                "last_message": "🚫 Ви заблокували цього користувача" if is_muted else msg.text,
                "last_message_time": msg.created_at.isoformat(),
                "unread_count": 0,
                "is_blocked": is_muted # Передаємо прапорець на фронтенд для зміни кнопок
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
        self.active_connections: Dict[int, WebSocket] = {}

    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        self.active_connections[user_id] = websocket
        await self.broadcast_online_status()

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
                # 💡 НАДЗВЕЧАЙНО ВАЖЛИВО: Перевірка на двостороннє блокування перед записом та відправкою
                is_blocked = db.query(Complaint).filter(
                    or_(
                        (Complaint.author_id == user_id) & (Complaint.text == f"[BLOCKED] user_id:{receiver_id}"),
                        (Complaint.author_id == receiver_id) & (Complaint.text == f"[BLOCKED] user_id:{user_id}")
                    )
                ).first()

                if is_blocked:
                    # Повертаємо івент помилки клієнту в WebSocket трубу
                    if user_id in manager.active_connections:
                        await manager.active_connections[user_id].send_json({
                            "type": "blocked_error",
                            "message": "Неможливо надіслати повідомлення. Користувач знаходиться в чорному списку. 🚫"
                        })
                    continue # Пропускаємо збереження і розсилку

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