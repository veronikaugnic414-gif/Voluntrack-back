from sqlalchemy import Column, Integer, String, Float, Boolean, Text, ForeignKey, DateTime, JSON, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
from datetime import datetime

class Education(Base):
    __tablename__ = "educations"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    institution = Column(String)
    institution_type = Column(String)  
    specialty = Column(String, nullable=True)
    start_year = Column(Integer, nullable=True)
    end_year = Column(Integer, nullable=True)
    is_current = Column(Boolean, default=False) 
    
    user = relationship("User", back_populates="educations")

# Модель для документів організацій
class Document(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    file_url = Column(String, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))

    user = relationship("User", back_populates="documents")

# 💡 НОВА МОДЕЛЬ: Захист від накрутки лайків
class Like(Base):
    __tablename__ = "likes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)

    user = relationship("User", back_populates="likes")
    post = relationship("Post", back_populates="likes_relationship")

    # Обмеження на рівні бази даних: один юзер — один лайк для конкретного поста
    __table_args__ = (UniqueConstraint("user_id", "post_id", name="unique_user_post_like"),)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    role = Column(String, nullable=False)
    
    name = Column(String, nullable=True)
    surname = Column(String, nullable=True)
    specialization = Column(String, nullable=True)
    about = Column(String, nullable=True)
    location = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)
    age = Column(Integer, nullable=True)
    points = Column(Integer, default=0)
    
    is_verified = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    is_trusted = Column(Boolean, default=False)
    
    verification_token = Column(String, nullable=True)
    reset_token = Column(String, nullable=True)
    
    posts = relationship("Post", back_populates="owner", cascade="all, delete-orphan")
    comments = relationship("Comment", back_populates="author", cascade="all, delete-orphan")
    educations = relationship("Education", back_populates="user", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="user", cascade="all, delete-orphan")
    likes = relationship("Like", back_populates="user", cascade="all, delete-orphan") # 💡 Додано зв'язок для лайків користувача

class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(Text)
    category = Column(String, nullable=True)
    location = Column(String, nullable=True)
    
    goal_amount = Column(Float, default=0.0)
    raised_amount = Column(Float, default=0.0)
    donors_count = Column(Integer, default=0)
    
    status = Column(String, default="active")
    created_at = Column(DateTime, default=datetime.utcnow)
    deadline = Column(DateTime, nullable=True)
    
    cover_image_url = Column(String, nullable=True)
    report_text = Column(Text, nullable=True)
    report_media_urls = Column(JSON, nullable=True)
    
    likes_count = Column(Integer, default=0)
    comments_count = Column(Integer, default=0)

    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    owner = relationship("User", back_populates="posts")
    
    # Контроль каскадів: якщо пост видалено — чистимо коменти, скарги та лайки під ним
    comments = relationship("Comment", back_populates="post", cascade="all, delete-orphan")
    complaints = relationship("Complaint", back_populates="post", cascade="all, delete-orphan")
    likes_relationship = relationship("Like", back_populates="post", cascade="all, delete-orphan")

class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"))
    author_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))

    post = relationship("Post", back_populates="comments")
    author = relationship("User", back_populates="comments")

class Complaint(Base):
    __tablename__ = "complaints"

    id = Column(Integer, primary_key=True, index=True)
    text = Column(String, nullable=False)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=True)
    author_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_resolved = Column(Boolean, default=False)

    post = relationship("Post", back_populates="complaints")

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type = Column(String, nullable=False)
    message = Column(String, nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    receiver_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    text = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())