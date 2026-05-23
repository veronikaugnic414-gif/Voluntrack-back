import secrets
import shutil
import os
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional

from app.database import get_db
from app.models import User, Education, Document, Notification  # 💡 Імпортували модель сповіщень
from app.security import decode_access_token, hash_password, verify_password, create_access_token
from app.mail import send_verification_email, send_reset_email, generate_verification_token
from app.schemas import UserUpdate, UserResponse, EducationBase, EducationResponse, DocumentResponse

bearer_scheme = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme), db: Session = Depends(get_db)):
    token = credentials.credentials
    email = decode_access_token(token)
    
    if not email:
        raise HTTPException(status_code=401, detail="Недійсний або прострочений токен")
        
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=401, detail="Користувача не знайдено")
        
    return user

router = APIRouter(prefix="/auth", tags=["auth"])

class RegisterSchema(BaseModel):
    email: EmailStr
    password: str
    role: str 
    name: Optional[str] = None
    surname: Optional[str] = None
    location: Optional[str] = None
    specialization: Optional[str] = None
    about: Optional[str] = None

    def validate_role(self):
        if self.role not in ["volunteer", "organization", "user"]:
            raise ValueError("Невірна роль")

class LoginSchema(BaseModel):
    email: str
    password: str

class ForgotPasswordSchema(BaseModel):
    email: str

class ResetPasswordSchema(BaseModel):
    token: str
    new_password: str


@router.post("/register")
async def register(data: RegisterSchema, db: Session = Depends(get_db)):
    if data.role not in ["volunteer", "organization", "user"]:
        raise HTTPException(status_code=400, detail="Невірна роль")

    if len(data.password) < 8:
        raise HTTPException(status_code=400, detail="Пароль має бути мінімум 8 символів")

    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email вже зайнятий")

    token = secrets.token_urlsafe(32)
    user = User(
        email=data.email,
        password=hash_password(data.password),
        role=data.role,
        name=data.name,
        surname=data.surname if data.role != "organization" else None,
        location=data.location,
        specialization=data.specialization if data.role in ["volunteer", "organization"] else None,
        about=data.about,
        verification_token=token
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # 💡 АВТОМАТИЧНЕ СТВОРЕННЯ ВІТАЛЬНОГО СПОВІЩЕННЯ ПРИ РЕЄСТРАЦІЇ
    welcome_notification = Notification(
        user_id=user.id,
        type="info",
        message="Дякуємо, що приєдналися до нашої спільноти Voluntrack! Разом ми сила 🖤",
        is_read=False
    )
    db.add(welcome_notification)
    db.commit()

    await send_verification_email(data.email, token)
    return {"message": "Перевір пошту для підтвердження"}


@router.post("/login")
def login(data: LoginSchema, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not verify_password(data.password, user.password):
        raise HTTPException(status_code=401, detail="Невірні дані")
    if not user.is_verified:
        raise HTTPException(status_code=403, detail="Email не підтверджено")

    token = create_access_token({"sub": user.email})
    return {"access_token": token, "token_type": "bearer"}


@router.post("/logout")
def logout():
    return {"message": "Успішно вийшли"}


@router.post("/forgot-password")
async def forgot_password(data: ForgotPasswordSchema, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="Користувача не знайдено")

    token = generate_verification_token()
    user.reset_token = token
    db.commit()

    await send_reset_email(data.email, token)
    return {"message": "Перевір пошту для скидання пароля"}


@router.post("/reset-password")
def reset_password(data: ResetPasswordSchema, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.reset_token == data.token).first()
    if not user:
        raise HTTPException(status_code=404, detail="Невірний токен")

    user.password = hash_password(data.new_password)
    user.reset_token = None
    db.commit()
    return {"message": "Пароль змінено успішно"}


@router.get("/reset-password")
def reset_password_page(token: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.reset_token == token).first()
    if not user:
        raise HTTPException(status_code=404, detail="Невірний токен")
    return {"message": "Токен дійсний", "token": token}


@router.get("/verify/{token}", response_class=HTMLResponse)
def verify_email(token: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.verification_token == token).first()
    
    if not user:
        error_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Помилка - Voluntrack</title>
            <style>
                body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f9f9f9; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
                .card { background-color: white; padding: 40px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); text-align: center; max-width: 400px; border-top: 5px solid #e74c3c; }
                h1 { color: #e74c3c; margin-top: 0; }
                p { color: #555; line-height: 1.5; }
            </style>
        </head>
        <body>
            <div class="card">
                <h1>Ой, помилка 😔</h1>
                <p>Цей токен невірний або час його дії минув. Можливо, ви вже підтвердили свою пошту раніше.</p>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=error_html, status_code=400)

    user.is_verified = True
    user.verification_token = None
    db.commit()
    
    success_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Успіх! - Voluntrack</title>
        <style>
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f9f9f9; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
            .card { background-color: white; padding: 40px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); text-align: center; max-width: 400px; border-top: 5px solid #4CAF50; }
            h1 { color: #2ecc71; margin-top: 0; }
            p { color: #555; line-height: 1.5; margin-bottom: 25px; }
            .btn { background-color: #4CAF50; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; transition: background-color 0.3s; display: inline-block; }
            .btn:hover { background-color: #45a049; }
        </style>
    </head>
    <body>
        <div class="card">
            <h1>Email підтверджено! 🎉</h1>
            <p>Вітаємо у Voluntrack! Ваша пошта успішно підтверджена. Тепер ви можете закрити цю сторінку та увійти у свій акаунт.</p>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=success_html)


@router.get("/me", response_model=UserResponse)
def get_profile(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=UserResponse)
def update_profile(
    profile_data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    for key, value in profile_data.model_dump(exclude_unset=True).items():
        setattr(current_user, key, value)

    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/me/education", response_model=EducationResponse)
def add_education(
    edu_data: EducationBase,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    new_edu = Education(**edu_data.model_dump(), user_id=current_user.id)
    db.add(new_edu)
    db.commit()
    db.refresh(new_edu)
    return new_edu


@router.post("/me/avatar")
def upload_avatar(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    file_extension = file.filename.split(".")[-1]
    file_path = f"static/avatars/{current_user.id}_avatar.{file_extension}"
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    current_user.avatar_url = f"http://127.0.0.1:8000/{file_path}"
    db.commit()
    db.refresh(current_user)
    
    return {"avatar_url": current_user.avatar_url}


@router.delete("/me/education/{edu_id}")
def delete_education(edu_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    edu = db.query(Education).filter(Education.id == edu_id, Education.user_id == current_user.id).first()
    if not edu:
        raise HTTPException(status_code=404, detail="Освіту не знайдено")
    db.delete(edu)
    db.commit()
    return {"message": "Видалено"}


@router.post("/me/documents", response_model=DocumentResponse)
async def upload_document(
    title: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "organization":
        raise HTTPException(status_code=403, detail="Тільки організації можуть завантажувати документи")

    UPLOAD_DIR = "static/documents"
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    file_extension = file.filename.split(".")[-1]
    file_name = f"{current_user.id}_{secrets.token_hex(4)}.{file_extension}"
    file_path = f"{UPLOAD_DIR}/{file_name}"

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    new_doc = Document(
        title=title,
        file_url=f"http://127.0.0.1:8000/{file_path}",
        user_id=current_user.id
    )
    db.add(new_doc)
    db.commit()
    db.refresh(new_doc)
    return new_doc


@router.delete("/me/documents/{doc_id}")
def delete_document(doc_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    doc = db.query(Document).filter(Document.id == doc_id, Document.user_id == current_user.id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Документ не знайдено")
    db.delete(doc)
    db.commit()
    return {"message": "Документ видалено"}