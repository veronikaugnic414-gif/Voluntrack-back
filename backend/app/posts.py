import os
import shutil
import secrets
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request, UploadFile, File, Form, Query
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional

from app.database import get_db
from app.models import Post, User, Comment, Complaint, Notification, Like  # 💡 Додано модель Like
from app.schemas import PostResponse, CommentCreate, CommentResponse, ComplaintCreate, ComplaintResponse, PostUpdate
from app.auth import get_current_user 
from app.limiter import limiter 

router = APIRouter(prefix="/posts", tags=["Збори (Posts)"])

def send_email_notification(email: str, message: str):
    import time
    time.sleep(2) 
    print(f"📧 У ФОНІ: Відправлено лист на {email}. Текст: {message}")


# 1. СТВОРЕННЯ ЗБОРУ (Обкладинка обов'язкова)
@router.post("/", response_model=PostResponse)
@limiter.limit("3/minute")
async def create_post(
    request: Request, 
    title: str = Form(...),
    description: str = Form(...),
    goal_amount: float = Form(...),
    deadline: Optional[datetime] = Form(None),
    category: Optional[str] = Form(None),
    location: Optional[str] = Form(None),
    file: UploadFile = File(...), 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    if current_user.role == "user":
        raise HTTPException(status_code=403, detail="Тільки волонтери та організації можуть створювати збори")

    UPLOAD_DIR = "static/posts"
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file_extension = file.filename.split(".")[-1]
    file_name = f"{current_user.id}_{secrets.token_hex(4)}.{file_extension}"
    file_path = f"{UPLOAD_DIR}/{file_name}"
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    cover_url = f"http://127.0.0.1:8000/{file_path}"

    new_post = Post(
        title=title,
        description=description,
        goal_amount=goal_amount,
        deadline=deadline,
        cover_image_url=cover_url,
        category=category,
        location=location,
        owner_id=current_user.id,
        status="active"
    )
    db.add(new_post)
    db.commit()
    db.refresh(new_post)
    return new_post


# 2. ОТРИМАННЯ ЗБОРІВ З ФІЛЬТРАЦІЄЮ ТА ПОШУКОМ
@router.get("/", response_model=List[PostResponse])
def get_posts(
    db: Session = Depends(get_db),
    search: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    location: Optional[str] = Query(None)
):
    query = db.query(Post).options(joinedload(Post.owner)).filter(Post.status == "active")
    
    if search:
        query = query.filter((Post.title.ilike(f"%{search}%")) | (Post.description.ilike(f"%{search}%")))
    if category:
        query = query.filter(Post.category.ilike(f"%{category}%"))
    if location:
        query = query.filter(Post.location.ilike(f"%{location}%"))

    return query.order_by(Post.created_at.desc()).all()


# 3. ОТРИМАННЯ ОДНОГО ЗБОРУ ЗА ID
@router.get("/{post_id}", response_model=PostResponse)
def get_single_post(post_id: int, db: Session = Depends(get_db)):
    post = db.query(Post).options(joinedload(Post.owner)).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Збір не знайдено")
    return post


# 4. РЕДАГУВАННЯ ЗБОРУ (Через чисту схему PostUpdate)
@router.patch("/{post_id}", response_model=PostResponse)
def edit_post(
    post_id: int,
    post_data: PostUpdate,  
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Збір не знайдено")
    if post.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Ви можете редагувати лише свій збір")

    if post_data.title is not None: post.title = post_data.title
    if post_data.description is not None: post.description = post_data.description
    if post_data.goal_amount is not None: post.goal_amount = post_data.goal_amount
    if post_data.location is not None: post.location = post_data.location
    if post_data.deadline is not None: post.deadline = post_data.deadline

    db.commit()
    db.refresh(post)
    return post


# 5. ЗАКРИТТЯ ЗБОРУ
@router.post("/{post_id}/close", response_model=PostResponse)
def close_post(
    post_id: int, 
    report_text: str = Form(...), 
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
    post.report_text = report_text
    
    db.commit()
    db.refresh(post)
    return post


# 6. ВИДАЛЕННЯ ЗБОРУ
@router.delete("/{post_id}")
def delete_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Збір не знайдено")
    if post.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Ви можете видалити лише свій збір")

    db.delete(post)
    db.commit()
    return {"message": "Збір успішно видалено"}


# 7. ДОДАВАННЯ КОМЕНТАРЯ
@router.post("/{post_id}/comments", response_model=CommentResponse)
@limiter.limit("5/minute")
def add_comment(
    request: Request, 
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


# 8. ОТРИМАННЯ КОМЕНТАРІВ
@router.get("/{post_id}/comments", response_model=List[CommentResponse])
def get_comments(post_id: int, db: Session = Depends(get_db)):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Збір не знайдено")
    
    return db.query(Comment).filter(Comment.post_id == post_id).order_by(Comment.created_at.desc()).all()


# 9. ЛАЙК ЗБОРУ (💡 Захищено від накрутки — працює як перемикач)
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
        
    # Шукаємо, чи є вже лайк від цього користувача під цим постом
    existing_like = db.query(Like).filter(Like.user_id == current_user.id, Like.post_id == post_id).first()

    if existing_like:
        # Якщо лайк вже є — видаляємо його (дизлайк)
        db.delete(existing_like)
        if post.likes_count > 0:
            post.likes_count -= 1
    else:
        # Якщо лайка немає — створюємо запис в базі
        new_like = Like(user_id=current_user.id, post_id=post_id)
        db.add(new_like)
        post.likes_count += 1

    db.commit()
    db.refresh(post)
    return post


# 10. СКАРГА З ФОНОВОЮ ЗАДАЧЕЮ
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