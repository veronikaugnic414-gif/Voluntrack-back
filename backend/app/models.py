from sqlalchemy import Column, Integer, String, Float, Boolean, Text, ForeignKey, DateTime, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
from datetime import datetime

# 1. Таблиця Користувачів
# 1. Таблиця Користувачів
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    role = Column(String, nullable=False) # 'volunteer', 'organization', 'user'
    
    # Загальні поля для всіх ролей
    name = Column(String, nullable=True)     # Сюди пишемо назву організації або ім'я юзера
    about = Column(String, nullable=True)    # Сюди пишемо опис організації або спеціалізацію волонтера
    location = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)
    points = Column(Integer, default=0)      # Рейтинг для юзерів
    
    # Статус та безпека
    is_verified = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    
    verification_token = Column(String, nullable=True)
    
    # Зв'язки
    posts = relationship("Post", back_populates="owner")
    comments = relationship("Comment", back_populates="author")

# 2. Таблиця Постів (Збори та проєкти)
class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(Text)
    category = Column(String, nullable=True)
    location = Column(String, nullable=True)
    
    # Фінансові дані
    goal_amount = Column(Float, default=0.0)
    raised_amount = Column(Float, default=0.0) # Поле для суми зібраних коштів
    donors_count = Column(Integer, default=0)  # Для статистики в кабінеті
    
    # Статус та дати
    status = Column(String, default="active") # "active" або "closed"
    created_at = Column(DateTime, default=datetime.utcnow)
    deadline = Column(DateTime, nullable=True)
    
    # Медіа та звіти
    cover_image_url = Column(String, nullable=True)
    report_text = Column(Text, nullable=True)
    report_media_urls = Column(JSON, nullable=True)
    
    # Статистика
    likes_count = Column(Integer, default=0)
    comments_count = Column(Integer, default=0)

    # Зв'язки
    owner_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User", back_populates="posts")
    comments = relationship("Comment", back_populates="post")

# 3. Таблиця Коментарів
class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    post_id = Column(Integer, ForeignKey("posts.id"))
    author_id = Column(Integer, ForeignKey("users.id"))

    post = relationship("Post", back_populates="comments")
    author = relationship("User", back_populates="comments")

# 4. Таблиця Скарг
class Complaint(Base):
    __tablename__ = "complaints"

    id = Column(Integer, primary_key=True, index=True)
    text = Column(String, nullable=False)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_resolved = Column(Boolean, default=False)

# 5. Таблиця Сповіщень
class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    type = Column(String, nullable=False)
    message = Column(String, nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("users.id"))
    receiver_id = Column(Integer, ForeignKey("users.id"))
    text = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())