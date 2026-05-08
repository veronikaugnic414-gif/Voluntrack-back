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
    name: Optional[str] = None
    location: Optional[str] = None
    about: Optional[str] = None
    avatar_url: Optional[str] = None

class UserUpdate(BaseModel):
    name: Optional[str] = None
    bio: Optional[str] = None
    location: Optional[str] = None
    about: Optional[str] = None
    avatar_url: Optional[str] = None

class UserResponse(UserBase):
    id: int
    is_verified: bool

    class Config:
        from_attributes = True

# --- 2. Схеми для Постів (Стрічка і Збори) ---
class PostBase(BaseModel):
    title: str
    description: str
    goal_amount: Optional[float] = None
    
class PostCreate(BaseModel):
    title: str
    description: str
    goal_amount: float
    deadline: Optional[datetime] = None
    cover_image_url: Optional[str] = None
    category: Optional[str] = None
    location: Optional[str] = None

class PostResponse(PostBase):
    id: int
    current_raised: float
    created_at: datetime
    is_active: bool
    owner_id: int
    
    # Нові поля з Figma
    cover_image_url: Optional[str] = None
    deadline: Optional[datetime] = None
    status: str = "active"
    likes_count: int = 0
    comments_count: int = 0
    category: Optional[str] = None
    location: Optional[str] = None
    
    # НОВІ ПОЛЯ ДЛЯ ЗВІТНОСТІ
    report_text: Optional[str] = None
    report_media_urls: Optional[List[str]] = []

    class Config:
        from_attributes = True

# --- 3. Схема для закриття збору та додавання звіту ---
class PostClose(BaseModel):
    report_text: str
    report_media_urls: Optional[List[str]] = []

# --- 4. Схеми для Коментарів ---
class CommentCreate(BaseModel):
    text: str

class CommentResponse(BaseModel):
    id: int
    text: str
    created_at: datetime
    post_id: int
    author_id: int

    class Config:
        from_attributes = True