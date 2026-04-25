import uvicorn
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import get_db
from models import User
from security import hash_password, verify_password, create_access_token
from mail import send_verification_email, generate_verification_token

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterSchema(BaseModel):
    email: str
    password: str


class LoginSchema(BaseModel):
    email: str
    password: str


@router.post("/register")
async def register(data: RegisterSchema, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email вже зайнятий")

    token = generate_verification_token()
    user = User(
        email=data.email,
        password=hash_password(data.password),
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


@router.get("/verify/{token}")
def verify_email(token: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.verification_token == token).first()
    if not user:
        raise HTTPException(status_code=404, detail="Невірний токен")

    user.is_verified = True
    user.verification_token = None
    db.commit()
    return {"message": "Email підтверджено, можеш увійти"}