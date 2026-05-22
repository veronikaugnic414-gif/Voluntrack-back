import os
import uuid
import shutil
from fastapi import APIRouter, UploadFile, File, HTTPException, status

# Створюємо роутер для медіа-файлів
router = APIRouter(prefix="/media", tags=["Media"])

# Вказуємо ту саму папку, що і в main.py
UPLOAD_DIR = "static/uploads"

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    # 1. Перевіряємо формат файлу (щоб нам не завантажили віруси)
    allowed_extensions = [".jpg", ".jpeg", ".png", ".webp", ".pdf"]
    file_extension = os.path.splitext(file.filename)[1].lower()
    
    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Недопустимий формат файлу. Дозволені: {', '.join(allowed_extensions)}"
        )
    
    # 2. Генеруємо унікальне ім'я за допомогою UUID 
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)
    
    # 3. Зберігаємо файл на диск
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Помилка під час збереження файлу"
        )
        
    # 4. Повертаємо готове посилання
    file_url = f"http://127.0.0.1:8000/{file_path}"
    
    return {"file_url": file_url}