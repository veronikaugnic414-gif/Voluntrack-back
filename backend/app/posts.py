import os
import shutil
import secrets
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request, UploadFile, File, Form, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_
from typing import List, Optional

from app.database import get_db
from app.models import Post, User, Comment, Complaint, Notification, Like, Subscription, SavedPost  
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


# 2. ОТРИМАННЯ ЗБОРІВ З РОЗУМНОЮ ФІЛЬТРАЦІЄЮ ТА СТАТУСОМ ЗБЕРЕЖЕННЯ
@router.get("/", response_model=List[PostResponse])
def get_posts(
    db: Session = Depends(get_db),
    search: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    current_user: Optional[User] = Depends(get_current_user)
):
    # 💡 ВИПРАВЛЕНО: Якщо йде точковий пошук або запит робить волонтер, знімаємо обмеження active, 
    # щоб фронтенд міг розпарсити деталі закритих звітів
    if (current_user and current_user.role in ["volunteer", "organization"]) or search:
        query = db.query(Post).options(joinedload(Post.owner))
    else:
        query = db.query(Post).options(joinedload(Post.owner)).filter(Post.status == "active")
    
    if search:
        query = query.filter((Post.title.ilike(f"%{search}%")) | (Post.description.ilike(f"%{search}%")))
    if category and category != "Усі":
        query = query.filter(Post.category.ilike(f"%{category}%"))
    if location:
        query = query.filter(Post.location.ilike(f"%{location}%"))

    posts = query.order_by(Post.created_at.desc()).all()

    if current_user:
        followed_ids = {
            sub.followed_id for sub in db.query(Subscription).filter(Subscription.follower_id == current_user.id).all()
        }
        saved_post_ids = {
            sp.post_id for sp in db.query(SavedPost).filter(SavedPost.user_id == current_user.id).all()
        }
        for post in posts:
            post.is_following = post.owner_id in followed_ids
            post.is_saved = post.id in saved_post_ids

    return posts


# ОТРИМАННЯ ВСІХ ЗБЕРЕЖЕНИХ ЗАКЛАДОК ЮЗЕРА
@router.get("/saved/all", response_model=List[PostResponse])
def get_saved_posts(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    saved_relations = db.query(SavedPost).filter(SavedPost.user_id == current_user.id).all()
    post_ids = [sr.post_id for sr in saved_relations]
    
    posts = db.query(Post).options(joinedload(Post.owner)).filter(Post.id.in_(post_ids)).all()
    
    for post in posts:
        post.is_saved = True
    return posts


# ТРИГЕР ЗБЕРЕЖЕННЯ / ВИДАЛЕННЯ ЗБОРУ В ЗАКЛАДКИ
@router.post("/{post_id}/save")
def toggle_save_post(post_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    existing = db.query(SavedPost).filter(SavedPost.user_id == current_user.id, SavedPost.post_id == post_id).first()
    if existing:
        db.delete(existing)
        db.commit()
        return {"message": "Допис видалено із закладок. 📁"}
    
    new_save = SavedPost(user_id=current_user.id, post_id=post_id)
    db.add(new_save)
    db.commit()
    return {"message": "Допис успішно збережено в закладки! 💾"}


# 3. ОТРИМАННЯ ОДНОГО ЗБОРУ ЗА ID (Дозволено завантажувати closed збори для звітів)
@router.get("/{post_id}", response_model=PostResponse)
def get_single_post(post_id: int, db: Session = Depends(get_db)):
    post = db.query(Post).options(joinedload(Post.owner)).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Збір не знайдено")
    return post


# 4. РЕДАГУВАННЯ ЗБОРУ
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


# 5. ЗАКРИТТЯ ЗБОРУ З НАДШИЛАННЯМ ФАЙЛІВ ТА СПОВІЩЕННЯМИ ПІДПИСНИКАМ
@router.post("/{post_id}/close", response_model=PostResponse)
def close_post(
    post_id: int, 
    report_text: str = Form(...), 
    file: Optional[UploadFile] = File(None), 
    background_tasks: BackgroundTasks = None,
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
    
    # 💡 ВИПРАВЛЕНО: Записуємо файл у наявну JSON-колонку report_media_urls як масив
    if file:
        UPLOAD_DIR = "static/reports"
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        file_extension = file.filename.split(".")[-1]
        file_name = f"report_{post_id}_{secrets.token_hex(3)}.{file_extension}"
        file_path = f"{UPLOAD_DIR}/{file_name}"
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Записуємо згенероване посилання як єдиний елемент масиву
        post.report_media_urls = [f"http://127.0.0.1:8000/{file_path}"]

    subscribers = db.query(Subscription).filter(Subscription.followed_id == current_user.id).all()
    
    author_name = current_user.name if current_user.role == "organization" else f"{current_user.name} {current_user.surname or ''}".strip()
    notification_msg = f"Збір '{post.title}' від {author_name} успішно закрито! Опубліковано офіційний звіт. 📑"
    
    for sub in subscribers:
        new_notification = Notification(
            user_id=sub.follower_id,
            type="report",
            message=notification_msg
        )
        db.add(new_notification)
        
        if background_tasks:
            background_tasks.add_task(
                send_email_notification,
                "follower@example.com", 
                notification_msg
            )
    
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


# 7. ДОДАВАННЯ КОМЕНТАРЯ АБО ВІДПОВІДІ (З підтримкою parent_id)
@router.post("/{post_id}/comments", response_model=CommentResponse)
@limiter.limit("5/minute")
def add_comment(
    request: Request, 
    post_id: int, 
    comment: CommentCreate, 
    parent_id: Optional[int] = Query(None), 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Збір не знайдено")

    new_comment = Comment(
        text=comment.text,
        post_id=post_id,
        author_id=current_user.id,
        parent_id=parent_id 
    )
    db.add(new_comment)
    
    post.comments_count += 1
    current_user.points += 1
    
    db.commit()
    db.refresh(new_comment)
    return new_comment


# 8. ОТРИМАННЯ КОМЕНТАРІВ ТА ВІДПОВІДЕЙ (З підвантаженням об'єкта автора)
@router.get("/{post_id}/comments", response_model=List[CommentResponse])
def get_comments(post_id: int, db: Session = Depends(get_db)):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Збір не знайдено")
    
    return db.query(Comment).options(joinedload(Comment.author)).filter(Comment.post_id == post_id).order_by(Comment.created_at.asc()).all()


# 9. ЛАЙК ЗБОРУ (Антивірус проти накруток)
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
        
    existing_like = db.query(Like).filter(Like.user_id == current_user.id, Like.post_id == post_id).first()

    if existing_like:
        db.delete(existing_like)
        if post.likes_count > 0:
            post.likes_count -= 1
    else:
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
    
    # 💡 ВИПРАВЛЕНО: Виправили опечатку "проводи" ➔ "проводить"
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