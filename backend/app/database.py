from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Шлях до бази
SQLALCHEMY_DATABASE_URL = "sqlite:///./voluntrack.db"

# Створюємо двигун
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

# Налаштовуємо сесію
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# СУЧАСНИЙ СПОСІБ (SQLAlchemy 2.0+)
Base = declarative_base()

if __name__ == "__main__":
    try:
        connection = engine.connect()
        print("✅ Успіх! База підключена (без застарілих попереджень).")
        connection.close()
    except Exception as e:
        print(f"❌ Помилка: {e}")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()