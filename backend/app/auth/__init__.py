from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.security import decode_access_token
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional
from app.database import get_db
from app.models import User
from app.security import hash_password, verify_password, create_access_token
from app.mail import send_verification_email, send_reset_email, generate_verification_token
from app.schemas import UserUpdate, UserResponse

bearer_scheme = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme), db: Session = Depends(get_db)):
    token = credentials.credentials
    email = decode_access_token(token) # Розшифровуємо токен
    
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

    token = secrets.token_urlsafe(32)
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

@router.get("/verify/{token}", response_class=HTMLResponse)
def verify_email(token: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.verification_token == token).first()
    
    # --- ДИЗАЙН ДЛЯ ПОМИЛКИ (якщо токен невірний) ---
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

    # --- ЛОГІКА: Оновлюємо статус юзера в базі ---
    user.is_verified = True
    user.verification_token = None
    db.commit()
    
    # --- ДИЗАЙН ДЛЯ УСПІХУ ---
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


@router.get("/me")
def get_profile(current_user: User = Depends(get_current_user)):
    # Завдяки Depends(get_current_user), сюди потрапить тільки той, хто дав правильний токен!
    return {
        "email": current_user.email,
        "name": current_user.name,
        "role": current_user.role,
        "location": current_user.location,
        "about": current_user.about,
        "is_trusted": current_user.is_trusted  # Віддаємо статус галочки на фронтенд
    }


@router.patch("/me", response_model=UserResponse)
def update_profile(
    profile_data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user) # 🔒 Оновлювати можна тільки СВІЙ профіль
):
    # Оновлюємо тільки ті поля, які юзер передав у запиті
    if profile_data.name is not None:
        current_user.name = profile_data.name
    if profile_data.location is not None:
        current_user.location = profile_data.location
    if profile_data.about is not None:
        current_user.about = profile_data.about
    if profile_data.avatar_url is not None:
        current_user.avatar_url = profile_data.avatar_url

    db.commit()
    db.refresh(current_user)
    return current_user
