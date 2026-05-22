from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks, Request
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app.models import Post, User, Comment, Complaint, Notification
from app.schemas import PostCreate, PostResponse, PostClose, CommentCreate, CommentResponse, ComplaintCreate, ComplaintResponse
from app.auth import get_current_user 
from app.limiter import limiter # 🛡️ Імпортуємо наш захист від спаму

router = APIRouter(prefix="/posts", tags=["Збори (Posts)"])

# --- ДОПОМІЖНА ФУНКЦІЯ ДЛЯ ФОНОВОЇ ВІДПРАВКИ EMAIL ---
def send_email_notification(email: str, message: str):
    import time
    time.sleep(2) # Імітація довгої відправки
    print(f"📧 У ФОНІ: Відправлено лист на {email}. Текст: {message}")


# 1. СТВОРЕННЯ ЗБОРУ (Додано ліміт: макс 3 збори на хвилину від одного юзера)
@router.post("/", response_model=PostResponse)
@limiter.limit("3/minute")
def create_post(
    request: Request, # ⬅️ Обов'язковий параметр для лімітера
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
        category=post.category,
        location=post.location,
        owner_id=current_user.id
    )
    db.add(new_post)
    db.commit()
    db.refresh(new_post)
    return new_post


# 2. ОТРИМАННЯ ЗБОРІВ З ПАГІНАЦІЄЮ ТА ФІЛЬТРАЦІЄЮ (Читання зазвичай не лімітують жорстко)
@router.get("/")
def get_posts(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1, description="Номер сторінки"),
    limit: int = Query(10, ge=1, le=50, description="Кількість записів на сторінку"),
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

    total_items = query.count()
    offset = (page - 1) * limit
    posts = query.order_by(Post.created_at.desc()).offset(offset).limit(limit).all()
    total_pages = (total_items + limit - 1) // limit if limit > 0 else 1

    return {
        "metadata": {
            "total_items": total_items,
            "current_page": page,
            "limit": limit,
            "total_pages": total_pages,
            "has_next_page": page < total_pages
        },
        "data": posts
    }


# 3. ЗАКРИТТЯ ЗБОРУ
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


# 4. ДОДАВАННЯ КОМЕНТАРЯ (Захист від флуду: макс 5 коментарів на хвилину)
@router.post("/{post_id}/comments", response_model=CommentResponse)
@limiter.limit("5/minute")
def add_comment(
    request: Request, # ⬅️ Передаємо запит лімітеру
    post_id: int, 
    comment: CommentCreate, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Збір не знайдено")

    new_comment = Comment(
        text=comment.text,
        post_id=post_id,
        author_id=current_user.id
    )
    db.add(new_comment)
    
    post.comments_count += 1
    current_user.points += 1
    
    db.commit()
    db.refresh(new_comment)
    return new_comment


# 5. ОТРИМАННЯ КОМЕНТАРІВ
@router.get("/{post_id}/comments", response_model=List[CommentResponse])
def get_comments(post_id: int, db: Session = Depends(get_db)):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Збір не знайдено")
    
    comments = db.query(Comment).filter(Comment.post_id == post_id).order_by(Comment.created_at.desc()).all()
    return comments


# 6. ЛАЙК ЗБОРУ (Захист від автоклікерів: макс 10 лайків на хвилину)
@router.post("/{post_id}/like", response_model=PostResponse)
@limiter.limit("10/minute")
def like_post(
    request: Request,
    post_id: int, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Збір не знайдено")
        
    post.likes_count += 1
    db.commit()
    db.refresh(post)
    return post


# 7. СКАРГА З ФОНОВОЮ ЗАДАЧЕЮ (Захист від масових скарг: макс 2 на хвилину)
@router.post("/{post_id}/complaints", response_model=ComplaintResponse)
@limiter.limit("2/minute")
def report_post(
    request: Request,
    post_id: int, 
    complaint_data: ComplaintCreate, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Збір не знайдено")

    new_complaint = Complaint(
        text=complaint_data.text,
        post_id=post_id,
        author_id=current_user.id
    )
    db.add(new_complaint)
    
    warning_msg = f"Увага! На ваш збір (ID: {post.id}) надійшла скарга. Адміністрація проводить перевірку ⚠️"
    new_notif = Notification(user_id=post.owner_id, type="warning", message=warning_msg)
    db.add(new_notif)
    
    background_tasks.add_task(
        send_email_notification, 
        "user@example.com", 
        f"На ваш збір '{post.title}' надійшла скарга!"
    )

    db.commit()
    db.refresh(new_complaint)
    return new_complaint