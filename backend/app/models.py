from sqlalchemy import Column, Integer, String, Float, Boolean, Text, ForeignKey, DateTime, JSON, UniqueConstraint, and_
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
from datetime import datetime

class Education(Base):
    __tablename__ = "educations"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    institution = Column(String)
    institution_type = Column(String)  
    specialty = Column(String, nullable=True)
    start_year = Column(Integer, nullable=True)
    end_year = Column(Integer, nullable=True)
    is_current = Column(Boolean, default=False) 
    
    user = relationship("User", back_populates="educations")

class Document(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    file_url = Column(String, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))

    user = relationship("User", back_populates="documents")

class Like(Base):
    __tablename__ = "likes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)

    user = relationship("User", back_populates="likes")
    post = relationship("Post", back_populates="likes_relationship")

    __table_args__ = (UniqueConstraint("user_id", "post_id", name="unique_user_post_like"),)

# Таблиця збережених дописів (Закладки)
class SavedPost(Base):
    __tablename__ = "saved_posts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="saved_posts")
    post = relationship("Post", back_populates="saved_by_users")

    __table_args__ = (UniqueConstraint("user_id", "post_id", name="unique_user_saved_post"),)

# Таблиця підписок (Followers)
class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    follower_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    followed_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    __table_args__ = (UniqueConstraint("follower_id", "followed_id", name="unique_follower_followed"),)

# Зв'язок у профілях між Організаціями та Волонтерами
class VolunteerAffiliation(Base):
    __tablename__ = "volunteer_affiliations"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    volunteer_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    status = Column(String, default="pending") 
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("organization_id", "volunteer_id", name="unique_org_volunteer_link"),)


# Таблиця-лінк: Проміжна модель співавторства Many-to-Many
class PostCoauthor(Base):
    __tablename__ = "post_coauthors"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("post_id", "user_id", name="unique_post_coauthor_link"),)


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
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    posts = relationship("Post", back_populates="owner", cascade="all, delete-orphan")
    comments = relationship("Comment", back_populates="author", cascade="all, delete-orphan")
    educations = relationship("Education", back_populates="user", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="user", cascade="all, delete-orphan")
    likes = relationship("Like", back_populates="user", cascade="all, delete-orphan")
    
    saved_posts = relationship("SavedPost", back_populates="user", cascade="all, delete-orphan")
    
    followers = relationship("Subscription", foreign_keys=[Subscription.followed_id], cascade="all, delete-orphan")
    following = relationship("Subscription", foreign_keys=[Subscription.follower_id], cascade="all, delete-orphan")


class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(Text)
    category = Column(String, nullable=True)
    location = Column(String, nullable=True)
    
    post_type = Column(String, default="donation")  
    monobank_link = Column(String, nullable=True)   
    
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
    
    comments = relationship("Comment", back_populates="post", cascade="all, delete-orphan")
    complaints = relationship("Complaint", back_populates="post", cascade="all, delete-orphan")
    likes_relationship = relationship("Like", back_populates="post", cascade="all, delete-orphan")
    
    saved_by_users = relationship("SavedPost", back_populates="post", cascade="all, delete-orphan")
    
    # 💡 ВИПРАВЛЕНО (Пункт 12): Прибираємо жорстку фільтрацію за 'accepted' для відображення картки.
    # Це гарантує, що колаборація з'явиться в стрічці МИТТЄВО відразу після створення допису (і в pending, і в accepted).
    coauthors = relationship(
        "User",
        secondary="post_coauthors",
        primaryjoin="Post.id == PostCoauthor.post_id",
        secondaryjoin="User.id == PostCoauthor.user_id",
        viewonly=True
    )


class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"))
    author_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    
    parent_id = Column(Integer, ForeignKey("comments.id", ondelete="CASCADE"), nullable=True)

    post = relationship("Post", back_populates="comments")
    author = relationship("User", back_populates="comments")
    
    replies = relationship(
        "Comment", 
        back_populates="parent", 
        cascade="all, delete-orphan"
    )
    
    parent = relationship(
        "Comment", 
        back_populates="replies", 
        remote_side=[id]
    )


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