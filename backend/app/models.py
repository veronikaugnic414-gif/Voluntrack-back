from sqlalchemy import Column, Integer, String, Float, Boolean, Enum, Text, ForeignKey, DateTime, JSON
from sqlalchemy.orm import relationship
from app.database import Base
from datetime import datetime

#Таблиця Користувачів (Профілі та Ачівочки)
class User(Base):
    __tablename__ = "users"

    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    role = Column(String, nullable=False)
    is_verified = Column(Boolean, default=False)
    is_trusted = Column(Boolean, default = False)
    is_active = Column(Boolean, default=True)
    verification_token = Column(String, nullable=True)
    reset_token = Column(String, nullable=True)
    name = Column(String, nullable=True)
    location = Column(String, nullable=True)
    about = Column(String, nullable=True)

    # Нові поля для соцмережі
    avatar_url = Column(String, nullable=True)
    points = Column(Integer, default=0) # Ачівочки та рейтинг!

    # Зв'язки з іншими таблицями (що цей юзер створив)
    posts = relationship("Post", back_populates="owner")
    comments = relationship("Comment", back_populates="author")

# 3. Таблиця Постів (Стрічка дописів та зборів)
class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(Text)
    goal_amount = Column(Float, nullable=True) 
    current_raised = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    category = Column(String, nullable=True) # Сфера: військова, медицина, освіта тощо
    location = Column(String, nullable=True) # Місто або область

    # Хто створив цей пост
    owner_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User", back_populates="posts")
    
    # Коментарі під цим постом
    comments = relationship("Comment", back_populates="post")

    # Поля з дизайну Figma
    cover_image_url = Column(String, nullable=True) 
    deadline = Column(DateTime, nullable=True) 
    status = Column(String, default="active") # active / closed
    likes_count = Column(Integer, default=0)
    comments_count = Column(Integer, default=0)

    # --- НОВІ ПОЛЯ ДЛЯ ЗВІТНОСТІ ---
    report_text = Column(Text, nullable=True)          # Текст звіту ("Ми все купили!")
    report_media_urls = Column(JSON, nullable=True)    # Список посилань [фото1, відео1, документ.pdf]

# 4. Таблиця Коментарів (під постами)
class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    post_id = Column(Integer, ForeignKey("posts.id"))
    author_id = Column(Integer, ForeignKey("users.id"))

    post = relationship("Post", back_populates="comments")
    author = relationship("User", back_populates="comments")

# 5. Таблиця Чату (Особисті повідомлення)
class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    sender_id = Column(Integer, ForeignKey("users.id"))
    receiver_id = Column(Integer, ForeignKey("users.id"))

# 6. Таблиця Скарг (Модерація)
class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    reason = Column(Text, nullable=False) # Наприклад: "Нецензурна лексика"
    created_at = Column(DateTime, default=datetime.utcnow)

    reporter_id = Column(Integer, ForeignKey("users.id")) # Хто скаржиться
    reported_user_id = Column(Integer, ForeignKey("users.id")) # На кого скаржаться

class Complaint(Base):
    __tablename__ = "complaints"

    id = Column(Integer, primary_key=True, index=True)
    text = Column(String, nullable=False) # Текст скарги (напр. "Це шахрай!")
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=True) # На який збір скаржаться
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False) # Хто поскаржився
    created_at = Column(DateTime, default=datetime.utcnow)
    is_resolved = Column(Boolean, default=False) # Чи розібрався адмін з цією скаргою