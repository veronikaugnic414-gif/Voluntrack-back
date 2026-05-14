from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models import User, Complaint, Post , Notification
from app.schemas import UserResponse, ComplaintResponse
from app.auth import get_current_user

router = APIRouter(prefix="/admin", tags=["Адмін-панель (Admin)"])

# Функція-перевірка: чи є юзер адміном?
def check_admin(user: User):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Доступ заборонено: ви не адміністратор")

# 1. Отримати всі скарги
@router.get("/complaints", response_model=List[ComplaintResponse])
def get_all_complaints(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    check_admin(current_user)
    return db.query(Complaint).filter(Complaint.is_resolved == False).all()

# 2. Видати/забрати галочку довіри волонтеру
@router.patch("/users/{user_id}/trust", response_model=UserResponse)
def toggle_trust(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    check_admin(current_user)
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="Користувача не знайдено")
    
    target_user.is_trusted = not target_user.is_trusted
    
    #Генерація сповіщення
    if target_user.is_trusted:
        msg = "Вітаємо! Ваш профіль успішно верифіковано адміністратором ✅"
    else:
        msg = "Ваш статус верифікації було знято ❌"
        
    new_notif = Notification(user_id=target_user.id, type="admin", message=msg)
    db.add(new_notif)
    # ----------------------------------

    db.commit()
    db.refresh(target_user)
    return target_user

# 3. Блокування/розблокування користувача
@router.patch("/users/{user_id}/block", response_model=UserResponse)
def toggle_block(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    check_admin(current_user)
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="Користувача не знайдено")
    
    target_user.is_active = not target_user.is_active
    
    # 🌸 НОВИЙ КОД: Генерація сповіщення
    if target_user.is_active:
        msg = "Ваш акаунт розблоковано. З поверненням на Voluntrack! 🟢"
    else:
        msg = "Увага! Ваш акаунт було тимчасово заблоковано через порушення правил 🛑"
        
    new_notif = Notification(user_id=target_user.id, type="system", message=msg)
    db.add(new_notif)
    # ----------------------------------

    db.commit()
    db.refresh(target_user)
    return target_user