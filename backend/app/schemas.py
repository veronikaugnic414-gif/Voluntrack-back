from pydantic import BaseModel
from typing import Optional, List
from enum import Enum
from datetime import datetime

# Наші ролі
class UserRole(str, Enum):
    user = "user"
    volunteer = "volunteer"
    organization = "organization"

# --- 1. Схеми для Користувачів (Профілі) ---
class UserBase(BaseModel):
    email: str
    role: UserRole = UserRole.user
    bio: Optional[str] = None
    points: int = 0

class UserResponse(UserBase):
    id: int
    is_verified: bool

    class Config:
        from_attributes = True # Це дозволяє FastAPI читати дані з бази

# --- 2. Схеми для Постів (Стрічка і Збори) ---
class PostBase(BaseModel):
    title: str
    description: str
    goal_amount: Optional[float] = None
    
class PostCreate(PostBase):
    pass # Для створення поста нам достатньо заголовка, опису і суми

class PostResponse(PostBase):
    id: int
    current_raised: float
    created_at: datetime
    is_active: bool
    owner_id: int

    class Config:
        from_attributes = True