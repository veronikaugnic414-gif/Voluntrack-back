import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional
from app.database import get_db
from app.models import User
from app.security import hash_password, verify_password, create_access_token
from app.mail import send_verification_email, send_reset_email, generate_verification_token

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterSchema(BaseModel):
    email: EmailStr
    password: str
    role: str  # volunteer / organization / user
    name: Optional[str] = None
    location: Optional[str] = None
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
    # Перевірка ролі
    if data.role not in ["volunteer", "organization", "user"]:
        raise HTTPException(status_code=400, detail="Невірна роль")

    # Перевірка пароля
    if len(data.password) < 8:
        raise HTTPException(status_code=400, detail="Пароль має бути мінімум 8 символів")

    # Перевірка email
    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email вже зайнятий")

    token = generate_verification_token()
    user = User(
        email=data.email,
        password=hash_password(data.password),
        role=data.role,
        name=data.name,
        location=data.location,
        about=data.about,
        verification_token=token
    )
    db.add(user)
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

@router.get("/verify/{token}")
def verify_email(token: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.verification_token == token).first()
    if not user:
        raise HTTPException(status_code=404, detail="Невірний токен")

    user.is_verified = True
    user.verification_token = None
    db.commit()
    return {"message": "Email підтверджено, можеш увійти"}