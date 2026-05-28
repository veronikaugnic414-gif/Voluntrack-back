import os
import shutil
import secrets
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request, UploadFile, File, Form, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_, and_
from typing import List, Optional

from app.database import get_db
from app.models import Post, User, Comment, Complaint, Notification, Like, Subscription, SavedPost, PostCoauthor  
from app.schemas import PostResponse, CommentCreate, CommentResponse, ComplaintCreate, ComplaintResponse, PostUpdate
from app.auth import get_current_user 
from app.limiter import limiter 

router = APIRouter(prefix="/posts", tags=["Збори (Posts)"])

def send_email_notification(email: str, message: str):
    import time
    time.sleep(2) 
    print(f"📧 У ФОНІ: Відправлено лист на {email}. Текст: {message}")


# 1. СТВОРЕННЯ ДОПИСУ (З підтримкою типів: Збір, Волонтерство, Проєкт)
@router.post("/", response_model=PostResponse)
@limiter.limit("3/minute")
async def create_post(
    request: Request, 
    title: str = Form(...),
    description: str = Form(...),
    goal_amount: float = Form(0.0), 
    post_type: str = Form("donation"), 
    monobank_link: Optional[str] = Form(None), 
    deadline: Optional[datetime] = Form(None),
    category: Optional[str] = Form(None),
    location: Optional[str] = Form(None),
    file: UploadFile = File(...), 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    if current_user.role == "user":
        raise HTTPException(status_code=403, detail="Тільки волонтери та організації можуть створювати дописи")

    if post_type not in ["donation", "volunteering", "project"]:
        raise HTTPException(status_code=400, detail="Невірний тип допису")

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
        post_type=post_type, 
        monobank_link=monobank_link, 
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


# 2. ОТРИМАННЯ ДОПИСІВ З РОЗУМНОЮ ФІЛЬТРАЦІЄЮ ТА СУМІСНИМ СТАТУСОМ КООЛАБОРАЦІЇ В ПРОФІЛІ
@router.get("/", response_model=List[PostResponse])
def get_posts(
    db: Session = Depends(get_db),
    search: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    owner_id: Optional[int] = Query(None), 
    current_user: Optional[User] = Depends(get_current_user)
):
    # 💡 ВИПРАВЛЕНО: Додано joinedload(Post.coauthors) для автоматичного підтягування об'єктів User-співавторів у схему відповіді
    if (current_user and current_user.role in ["volunteer", "organization"]) or search:
        query = db.query(Post).options(joinedload(Post.owner), joinedload(Post.coauthors))
    else:
        query = db.query(Post).options(joinedload(Post.owner), joinedload(Post.coauthors)).filter(Post.status == "active")
    
    if owner_id:
        query = query.outerjoin(PostCoauthor, PostCoauthor.post_id == Post.id).filter(
            or_(
                Post.owner_id == owner_id,
                and_(PostCoauthor.user_id == owner_id, PostCoauthor.status == "accepted")
            )
        )
        
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
    
    # 💡 ВИПРАВЛЕНО: Додано joinedload(Post.coauthors) також і для збережених дописів
    posts = db.query(Post).options(joinedload(Post.owner), joinedload(Post.coauthors)).filter(Post.id.in_(post_ids)).all()
    
    for post in posts:
        post.is_saved = True
    return posts


# ТРИГЕР ЗБЕРЕЖЕННЯ / ВИДАЛЕННЯ ДОПИСУ В ЗАКЛАДКИ
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


# 3. ОТРИМАННЯ ОДНОГО ДОПИСУ ЗА ID
@router.get("/{post_id}", response_model=PostResponse)
def get_single_post(post_id: int, db: Session = Depends(get_db)):
    # 💡 ВИПРАВЛЕНО: Додано joinedload(Post.coauthors) для детальної сторінки одного поста
    post = db.query(Post).options(joinedload(Post.owner), joinedload(Post.coauthors)).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Допис не знайдено")
    return post


# 4. РЕДАГУВАННЯ ДОПИСУ
@router.patch("/{post_id}", response_model=PostResponse)
def edit_post(
    post_id: int,
    post_data: PostUpdate,  
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Допис не знайдено")
    if post.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Ви можете редагувати лише свій допис")

    if post_data.title is not None: post.title = post_data.title
    if post_data.description is not None: post.description = post_data.description
    if post_data.goal_amount is not None: post.goal_amount = post_data.goal_amount
    if post_data.raised_amount is not None: post.raised_amount = post_data.raised_amount 
    if post_data.location is not None: post.location = post_data.location
    if post_data.deadline is not None: post.deadline = post_data.deadline

    db.commit()
    db.refresh(post)
    return post


# 5. ЗАКРИТТЯ ДОПИСУ З НАДШИЛАННЯМ ФАЙЛІВ ТА СПОВІЩЕННЯМИ ПІДПИСНИКАМ
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
        raise HTTPException(status_code=404, detail="Допис не знайдено")
    if post.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Ви можете закрити тільки свій допис")
    if post.status == "closed":
        raise HTTPException(status_code=400, detail="Цей допис вже закрито")

    post.status = "closed"
    post.report_text = report_text
    
    if file:
        UPLOAD_DIR = "static/reports"
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        file_extension = file.filename.split(".")[-1]
        file_name = f"report_{post_id}_{secrets.token_hex(3)}.{file_extension}"
        file_path = f"{UPLOAD_DIR}/{file_name}"
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        post.report_media_urls = [f"http://127.0.0.1:8000/{file_path}"]

    subscribers = db.query(Subscription).filter(Subscription.followed_id == current_user.id).all()
    
    author_name = current_user.name if current_user.role == "organization" else f"{current_user.name} {current_user.surname or ''}".strip()
    notification_msg = f"Допис '{post.title}' від {author_name} успішно закрито! Опубліковано офіційний звіт. 📑"
    
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


# 6. ВИДАЛЕННЯ ДОПИСУ
@router.delete("/{post_id}")
def delete_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Допис не знайдено")
    if post.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Ви можете видалити лише свій допис")

    db.delete(post)
    db.commit()
    return {"message": "Допис успішно видалено"}


# 7. ДОДАВАННЯ КОМЕНТАРЯ АБО ВІДПОВІДІ
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
        raise HTTPException(status_code=404, detail="Допис не знайдено")

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


# 8. ОТРИМАННЯ КОМЕНТАРІВ ТА ВІДПОВІДЕЙ
@router.get("/{post_id}/comments", response_model=List[CommentResponse])
def get_comments(post_id: int, db: Session = Depends(get_db)):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Допис не знайдено")
    
    return db.query(Comment).options(joinedload(Comment.author)).filter(Comment.post_id == post_id).order_by(Comment.created_at.asc()).all()


# 9. ЛАЙК ДОПИСУ
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
        raise HTTPException(status_code=404, detail="Допис не знайдено")
        
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
        raise HTTPException(status_code=404, detail="Допис не знайдено")

    new_complaint = Complaint(
        text=complaint_data.text,
        post_id=post_id,
        author_id=current_user.id
    )
    db.add(new_complaint)
    
    warning_msg = f"Увага! На ваш допис (ID: {post.id}) надійшла скарга. Адміністрація проводить перевірку ⚠️"
    new_notif = Notification(user_id=post.owner_id, type="warning", message=warning_msg)
    db.add(new_notif)
    
    background_tasks.add_task(
        send_email_notification, 
        "user@example.com", 
        f"На ваш допис '{post.title}' надійшла скарга!"
    )

    db.commit()
    db.refresh(new_complaint)
    return new_complaint


# ─── 💡 КЕРУВАННЯ СПІЛЬНИМИ ЗБОРАМИ (КООЛАБОРАЦІЇ) ───

# ЗАПРОСИТИ ПАРТНЕРА СТАТИ СПІВАВТОРОМ ЗБОРУ
@router.post("/{post_id}/share-with/{partner_id}")
def invite_coauthor(post_id: int, partner_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Допис не знайдено")
    if post.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Тільки головний творець допису може запрошувати співавторів")
    if partner_id == current_user.id:
        raise HTTPException(status_code=400, detail="Ви не можете запросити самого себе")

    existing = db.query(PostCoauthor).filter_by(post_id=post_id, user_id=partner_id).first()
    if existing:
        return {"message": "Партнер уже запрошений або підтвердив участь у цьому зборі"}

    new_collaboration = PostCoauthor(post_id=post_id, user_id=partner_id, status="pending")
    db.add(new_collaboration)
    
    author_name = current_user.name if current_user.role == "organization" else f"{current_user.name} {current_user.surname or ''}".strip()
    db.add(Notification(
        user_id=partner_id,
        type="info",
        message=f"Користувач {author_name} запрошує вас об'єднати зусилля і стать співавтором публікації '{post.title}'! 🤝"
    ))
    
    db.commit()
    return {"message": "Запрошення до спільної колаборації успішно надіслано! 🤝"}


# ПІДТВЕРДИТИ УЧАСТЬ У СПІЛЬНОМУ ЗБОРІ
@router.post("/{post_id}/accept-collaboration")
def accept_collaboration(post_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    link = db.query(PostCoauthor).filter_by(post_id=post_id, user_id=current_user.id, status="pending").first()
    if not link:
        raise HTTPException(status_code=404, detail="Запрошення на коолаборацію не знайдено або вже підтверджено")

    link.status = "accepted"
    
    post = db.query(Post).filter(Post.id == post_id).first()
    partner_name = current_user.name if current_user.role == "organization" else f"{current_user.name} {current_user.surname or ''}".strip()
    db.add(Notification(
        user_id=post.owner_id,
        type="info",
        message=f"Партнер {partner_name} прийняв ваше запрошення! Тепер збір '{post.title}' є спільним 🎉"
    ))
    
    db.commit()
    return {"message": "Ви успішно приєдналися до спільного збору! Тепер він відображається у вашому профілі 🖤"}


# ОТРИМАТИ ВСІХ ПІДТВЕРДЖЕНИХ СПІВАВТОРІВ ДОПИСУ
@router.get("/{post_id}/coauthors")
def get_post_coauthors(post_id: int, db: Session = Depends(get_db)):
    coauthors = db.query(User).join(PostCoauthor, PostCoauthor.user_id == User.id).filter(
        PostCoauthor.post_id == post_id,
        PostCoauthor.status == "accepted"
    ).all()
    
    return [
        {
            "id": u.id,
            "name": u.name,
            "surname": u.surname,
            "role": u.role,
            "avatar_url": u.avatar_url,
            "is_trusted": u.is_trusted
        } for u in coauthors
    ]