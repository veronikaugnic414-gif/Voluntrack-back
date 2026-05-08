from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models import Post, User, Comment
from app.schemas import PostCreate, PostResponse, PostClose, CommentCreate, CommentResponse
from app.auth import get_current_user 

router = APIRouter(prefix="/posts", tags=["Збори (Posts)"])

@router.post("/", response_model=PostResponse)
def create_post(
    post: PostCreate, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    if current_user.role == "user":
        raise HTTPException(status_code=403, detail="Тільки волонтери та організації можуть створювати збори")

    new_post = Post(
        title=post.title,
        description=post.description,
        goal_amount=post.goal_amount,
        deadline=post.deadline,
        cover_image_url=post.cover_image_url,
        category=post.category, # Зберігаємо сферу
        location=post.location, # Зберігаємо локацію
        owner_id=current_user.id
    )
    db.add(new_post)
    db.commit()
    db.refresh(new_post)
    return new_post


@router.get("/", response_model=List[PostResponse])
def get_posts(
    db: Session = Depends(get_db),
    search: Optional[str] = Query(None, description="Пошук за назвою/описом"),
    status: Optional[str] = Query("active", description="Статус (active/closed)"),
    category: Optional[str] = Query(None, description="Сфера (військова, медицина тощо)"),
    location: Optional[str] = Query(None, description="Місто або регіон")
):
    query = db.query(Post)
    
    if search:
        query = query.filter((Post.title.ilike(f"%{search}%")) | (Post.description.ilike(f"%{search}%")))
    if status:
        query = query.filter(Post.status == status)
    if category:
        query = query.filter(Post.category.ilike(f"%{category}%"))
    if location:
        query = query.filter(Post.location.ilike(f"%{location}%"))

    return query.order_by(Post.created_at.desc()).all()


@router.patch("/{post_id}/close", response_model=PostResponse)
def close_post(
    post_id: int, 
    report_data: PostClose, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    post = db.query(Post).filter(Post.id == post_id).first()
    
    if not post:
        raise HTTPException(status_code=404, detail="Збір не знайдено")
    if post.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Ви можете закрити тільки свій збір")
    if post.status == "closed":
        raise HTTPException(status_code=400, detail="Цей збір вже закрито")

    post.status = "closed"
    post.report_text = report_data.report_text
    post.report_media_urls = report_data.report_media_urls
    
    db.commit()
    db.refresh(post)
    return post



@router.post("/{post_id}/comments", response_model=CommentResponse)
def add_comment(
    post_id: int, 
    comment: CommentCreate, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user) # 🔒 Токен обов'язковий!
):
    # 1. Перевіряємо, чи існує такий збір
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Збір не знайдено")

    # 2. Створюємо новий коментар
    new_comment = Comment(
        text=comment.text,
        post_id=post_id,
        author_id=current_user.id
    )
    db.add(new_comment)
    
    # 3. Гейміфікація! Збільшуємо лічильник коментарів у пості та даємо +1 бал юзеру
    post.comments_count += 1
    current_user.points += 1
    
    db.commit()
    db.refresh(new_comment)
    return new_comment


# 4. Отримання всіх коментарів під конкретним збором
@router.get("/{post_id}/comments", response_model=List[CommentResponse])
def get_comments(post_id: int, db: Session = Depends(get_db)):
    # Шукаємо збір
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Збір не знайдено")
    
    # Віддаємо всі коментарі до нього (від найновіших до найстаріших)
    comments = db.query(Comment).filter(Comment.post_id == post_id).order_by(Comment.created_at.desc()).all()
    return comments


# 5. Лайк збору (Підтримка)
@router.post("/{post_id}/like", response_model=PostResponse)
def like_post(
    post_id: int, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user) # 🔒 Ставити лайки можуть тільки авторизовані!
):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Збір не знайдено")
        
    # Збільшуємо лічильник лайків на 1
    post.likes_count += 1
    db.commit()
    db.refresh(post)
    return post