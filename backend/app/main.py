from fastapi import FastAPI
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
# Додаємо імпорти твоїх файлів
from app.database import engine
from app.models import Base
from app import posts
from app import auth
from app import media
from app import admin
from app import chat
from app import notification
import os

# 1. Створюємо лімітер, який буде розрізняти юзерів за їхньою IP-адресою
limiter = Limiter(key_func=get_remote_address)

app = FastAPI()

# 2. Підключаємо лімітер до нашого FastAPI додатку
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# --- СТАТИКА (ДЛЯ КАРТИНОК) ---
UPLOAD_DIR = "static/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True) # Створить папку автоматично, якщо її ще немає
app.mount("/static", StaticFiles(directory="static"), name="static") # Роздає файли в інтернет

# --- CORS ---
origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)

# --- ПІДКЛЮЧЕННЯ ВСІХ РОУТЕРІВ ---
app.include_router(auth.router)
app.include_router(posts.router)
app.include_router(admin.router)
app.include_router(chat.router)
app.include_router(notification.router)
app.include_router(media.router)

@app.get("/")
def root():
    return {"status": "Voluntrack API is online", "database": "ready"}