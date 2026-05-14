from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict
import json
from app.database import get_db
from app.models import Message, User
from app.schemas import MessageResponse
from app.auth import get_current_user

router = APIRouter(tags=["Чат (WebSockets та Історія)"])

# 1. Ендпоінт для отримання історії листування з конкретним юзером
@router.get("/chat/history/{other_user_id}", response_model=List[MessageResponse])
def get_chat_history(
    other_user_id: int, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    # Шукаємо всі повідомлення між поточним юзером і other_user_id
    messages = db.query(Message).filter(
        ((Message.sender_id == current_user.id) & (Message.receiver_id == other_user_id)) |
        ((Message.sender_id == other_user_id) & (Message.receiver_id == current_user.id))
    ).order_by(Message.created_at.asc()).all()
    
    return messages

# --- МАГІЯ WEBSOCKETS ---

# Менеджер з'єднань (тримає інформацію про те, хто зараз онлайн)
class ConnectionManager:
    def __init__(self):
        # Словник: {user_id: WebSocket}
        self.active_connections: Dict[int, WebSocket] = {}

    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        self.active_connections[user_id] = websocket

    def disconnect(self, user_id: int):
        if user_id in self.active_connections:
            del self.active_connections[user_id]

    async def send_personal_message(self, message_data: dict, receiver_id: int):
        # Відправляємо повідомлення, ТІЛЬКИ якщо людина зараз онлайн
        if receiver_id in self.active_connections:
            websocket = self.active_connections[receiver_id]
            await websocket.send_json(message_data)

manager = ConnectionManager()

# Сам маршрут труби (з'єднання)
@router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: int, db: Session = Depends(get_db)):
    # 1. Користувач підключається
    await manager.connect(websocket, user_id)
    try:
        while True:
            # 2. Чекаємо, поки користувач щось напише
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            receiver_id = message_data.get("receiver_id")
            text = message_data.get("text")
            
            # 3. Зберігаємо повідомлення в базу даних
            new_message = Message(sender_id=user_id, receiver_id=receiver_id, text=text)
            db.add(new_message)
            db.commit()
            db.refresh(new_message)
            
            # 4. Формуємо відповідь і миттєво відправляємо отримувачу
            response_data = {
                "id": new_message.id,
                "sender_id": user_id,
                "receiver_id": receiver_id,
                "text": text,
                "created_at": str(new_message.created_at)
            }
            await manager.send_personal_message(response_data, receiver_id)
            
    except WebSocketDisconnect:
        # Якщо користувач закрив додаток — відключаємо його
        manager.disconnect(user_id)