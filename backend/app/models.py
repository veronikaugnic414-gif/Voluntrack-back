from sqlalchemy import Column, Integer, String, Float, Boolean, Enum, Text, ForeignKey, DateTime
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
    verification_token = Column(String, nullable=True)
    reset_token = Column(String, nullable=True)
    name = Column(String, nullable=True)
    location = Column(String, nullable=True)
    about = Column(String, nullable=True)

    # Нові поля для соцмережі
    bio = Column(Text, nullable=True) # Опис профілю
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
    goal_amount = Column(Float, nullable=True) # Якщо це збір - тут сума. Якщо просто допис - тут пусто
    current_raised = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    # Хто створив цей пост
    owner_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User", back_populates="posts")
    
    # Коментарі під цим постом
    comments = relationship("Comment", back_populates="post")
    # Нові поля з дизайну Figma
    cover_image_url = Column(String, nullable=True) # Обкладинка збору
    deadline = Column(DateTime, nullable=True) # Дата завершення "15 травня"
    status = Column(String, default="active") # Активний чи закритий
    likes_count = Column(Integer, default=0)
    comments_count = Column(Integer, default=0)

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