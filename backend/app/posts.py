from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models import Post
from app.schemas import PostCreate, PostResponse

# Створюємо "роутер" (розділ) для стрічки
router = APIRouter(prefix="/posts", tags=["Feed & Fundraisers"])

@router.post("/", response_model=PostResponse)
def create_post(post: PostCreate, db: Session = Depends(get_db)):
    # Створюємо новий пост/збір у базі
    new_post = Post(
        title=post.title,
        description=post.description,
        goal_amount=post.goal_amount,
        owner_id=1 # Тимчасово ставимо id=1, поки не зв'яжемо з логіном
    )
    db.add(new_post)
    db.commit()
    db.refresh(new_post)
    return new_post

@router.get("/", response_model=List[PostResponse])
def get_all_posts(db: Session = Depends(get_db)):
    # Дістаємо всі активні пости, сортуємо від найновіших
    posts = db.query(Post).filter(Post.is_active == True).order_by(Post.created_at.desc()).all()
    return posts