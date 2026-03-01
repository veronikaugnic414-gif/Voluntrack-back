from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
# Додаємо імпорти твоїх файлів
from app.database import engine
from app import models

# Оцей рядок — це "магія", яка створює таблиці в базі при запуску сервера
models.Base.metadata.create_all(bind=engine)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"status": "Voluntrack API is online", "database": "ready"}