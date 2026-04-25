from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
# Додаємо імпорти твоїх файлів
from database import engine
from models import Base
import auth



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

@app.get("/")
def root():
    return {"status": "Voluntrack API is online", "database": "ready"}