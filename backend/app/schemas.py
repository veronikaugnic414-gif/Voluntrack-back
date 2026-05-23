from pydantic import BaseModel, EmailStr
from typing import Optional, List
from enum import Enum
from datetime import datetime

class UserRole(str, Enum):
    user = "user"
    volunteer = "volunteer"
    organization = "organization"
    admin = "admin"

class InstitutionType(str, Enum):
    school = "Школа"
    gymnasium = "Гімназія"
    collegium = "Колегіум"
    college = "Коледж"
    vocational = "Училище"
    technicum = "Технікум"
    lyceum = "Ліцей"
    university = "Університет"
    institute = "Інститут"
    academy = "Академія"

class EducationBase(BaseModel):
    institution: str
    institution_type: InstitutionType 
    specialty: Optional[str] = None
    start_year: Optional[int] = None
    end_year: Optional[int] = None
    is_current: bool = False 

class EducationResponse(EducationBase):
    id: int
    class Config:
        from_attributes = True

class DocumentBase(BaseModel):
    title: str

class DocumentResponse(DocumentBase):
    id: int
    file_url: str
    user_id: int

    class Config:
        from_attributes = True

class UserBase(BaseModel):
    email: EmailStr
    role: UserRole = UserRole.user
    points: int = 0
    name: Optional[str] = None
    surname: Optional[str] = None
    location: Optional[str] = None
    specialization: Optional[str] = None 
    about: Optional[str] = None
    avatar_url: Optional[str] = None
    age: Optional[int] = None

class UserUpdate(BaseModel):
    name: Optional[str] = None
    surname: Optional[str] = None
    location: Optional[str] = None
    specialization: Optional[str] = None
    about: Optional[str] = None
    avatar_url: Optional[str] = None
    age: Optional[int] = None

class UserResponse(UserBase):
    id: int
    is_verified: bool
    is_trusted: bool  
    is_active: bool 
    educations: List[EducationResponse] = []
    documents: List[DocumentResponse] = []

    class Config:
        from_attributes = True

# Схема для передачі автора всередині поста
class PostOwnerFields(BaseModel):
    id: int
    name: Optional[str] = None
    surname: Optional[str] = None
    role: str
    avatar_url: Optional[str] = None

    class Config:
        from_attributes = True

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

# 💡 НОВА СХЕМА: Спеціально для безпечного редагування постів через JSON
class PostUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    goal_amount: Optional[float] = None
    location: Optional[str] = None
    deadline: Optional[datetime] = None

class PostResponse(PostBase):
    id: int
    raised_amount: float
    created_at: datetime
    status: str = "active"
    owner_id: int
    cover_image_url: Optional[str] = None
    deadline: Optional[datetime] = None
    likes_count: int = 0
    comments_count: int = 0
    category: Optional[str] = None
    location: Optional[str] = None
    report_text: Optional[str] = None
    report_media_urls: Optional[List[str]] = []
    owner: Optional[PostOwnerFields] = None

    class Config:
        from_attributes = True

class PostClose(BaseModel):
    report_text: str
    report_media_urls: Optional[List[str]] = []

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

class ComplaintCreate(BaseModel):
    text: str

class ComplaintResponse(BaseModel):
    id: int
    text: str
    post_id: Optional[int]
    author_id: int
    is_resolved: bool
    created_at: datetime

    class Config:
        from_attributes = True

class MessageResponse(BaseModel):
    id: int
    sender_id: int
    receiver_id: int
    text: str
    created_at: datetime

    class Config:
        from_attributes = True

class NotificationResponse(BaseModel):
    id: int
    user_id: int
    type: str
    message: str
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True