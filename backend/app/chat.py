from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from typing import List, Dict, Optional
import json
from contextlib import contextmanager

from app.database import get_db, SessionLocal
from app.models import Message, User, Complaint 
from app.schemas import MessageResponse
from app.auth import get_current_user
from app.security import decode_access_token

router = APIRouter(tags=["Чат (WebSockets та Історія)"])


# БЛОКУВАННЯ / РОЗБЛОКУВАННЯ КОРИСТУВАЧА
@router.post("/chat/block/{other_user_id}")
def toggle_block_user(other_user_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.id == other_user_id:
        raise HTTPException(status_code=400, detail="Ви не можете заблокувати самого себе")
        
    existing_block = db.query(Complaint).filter(
        Complaint.author_id == current_user.id,
        Complaint.post_id == None, 
        Complaint.text == f"[BLOCKED] user_id:{other_user_id}"
    ).first()

    if existing_block:
        db.delete(existing_block)
        db.commit()
        return {"status": "unblocked", "message": "Користувача успішно розблоковано! ✅"}
        
    new_block = Complaint(
        text=f"[BLOCKED] user_id:{other_user_id}",
        post_id=None,
        author_id=current_user.id,
        is_resolved=True 
    )
    db.add(new_block)
    db.commit()
    return {"status": "blocked", "message": "Користувача заблоковано. Листування призупинено. 🚫"}


# 1. ENDPOINT: СПИСОК АКТИВНИХ ДІАЛОГІВ
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
            is_muted = partner_id in blocked_by_me
            
            conversations.append({
                "partner_id": partner.id,
                "partner_name": partner_name or "Користувач Voluntrack",
                "last_message": "🚫 Ви заблокували цього користувача" if is_muted else msg.text,
                "last_message_time": msg.created_at.isoformat(),
                "unread_count": 0,
                "is_blocked": is_muted, 
                "is_trusted": partner.is_trusted 
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


# --- WEBSOCKETS CONNECTION MANAGER ---

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
        db = SessionLocal()
        try:
            online_users = list(self.active_connections.keys())
            for conn_id, connection in self.active_connections.items():
                try:
                    await connection.send_json({
                        "type": "online_status",
                        "users": online_users
                    })
                except Exception:
                    pass
        finally:
            db.close()

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


@router.websocket("/chat/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(...)):
    email = decode_access_token(token)
    if not email:
        await websocket.close(code=4008)
        return

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            await websocket.close(code=4008)
            return
        user_id = user.id
    finally:
        db.close()

    await manager.connect(websocket, user_id)
    
    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            receiver_id = int(message_data.get("receiver_id"))
            text = message_data.get("text")
            
            if not text or not receiver_id:
                continue

            db = SessionLocal()
            try:
                is_blocked = db.query(Complaint).filter(
                    or_(
                        (Complaint.author_id == user_id) & (Complaint.text == f"[BLOCKED] user_id:{receiver_id}"),
                        (Complaint.author_id == receiver_id) & (Complaint.text == f"[BLOCKED] user_id:{user_id}")
                    )
                ).first()

                if is_blocked:
                    if user_id in manager.active_connections:
                        await manager.active_connections[user_id].send_json({
                            "type": "blocked_error",
                            "message": "Неможливо надіслати повідомлення. Користувач знаходиться в чорному списку. 🚫"
                        })
                    continue 

                new_message = Message(sender_id=user_id, receiver_id=receiver_id, text=text)
                db.add(new_message)
                db.commit()
                db.refresh(new_message)
                
                # 💡 ВИПРАВЛЕНО: Додаємо прапорець довіри партнера безпосередньо у WebSocket повідомлення, 
                # щоб фронтенд миттєво підтягував статус довіри у шапку та стейти
                partner_user = db.query(User).filter(User.id == receiver_id).first()
                
                response_data = {
                    "id": new_message.id,
                    "sender_id": user_id,
                    "receiver_id": receiver_id,
                    "text": text,
                    "created_at": new_message.created_at.isoformat(),
                    "is_trusted": partner_user.is_trusted if partner_user else False
                }
            finally:
                db.close()

            await manager.send_personal_message(response_data, receiver_id)
            await manager.send_personal_message(response_data, user_id)
            
    except WebSocketDisconnect:
        await manager.disconnect(user_id)