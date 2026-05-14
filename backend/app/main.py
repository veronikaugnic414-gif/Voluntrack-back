from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
# Додаємо імпорти твоїх файлів
from app.database import engine
from app.models import Base
from app import posts
from app import auth
from app import admin


app = FastAPI()

origins = [
    "http://localhost:3000"
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
Base.metadata.create_all(bind=engine)
app.include_router(auth.router)
app.include_router(posts.router)
app.include_router(admin.router)

@app.get("/")
def root():
    return {"status": "Voluntrack API is online", "database": "ready"}

