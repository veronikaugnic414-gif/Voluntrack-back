from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from dotenv import load_dotenv
import os
import uuid

load_dotenv()

# Read mail config with safe defaults so the app doesn't crash on import
# when env vars are missing (e.g. on first deploy before secrets are configured)
MAIL_USERNAME = os.getenv("MAIL_USERNAME")
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
MAIL_FROM = os.getenv("MAIL_FROM")
MAIL_PORT_RAW = os.getenv("MAIL_PORT")
MAIL_SERVER = os.getenv("MAIL_SERVER")

# Mail is enabled only when all required env vars are present
MAIL_ENABLED = bool(MAIL_USERNAME and MAIL_PASSWORD and MAIL_FROM and MAIL_PORT_RAW and MAIL_SERVER)

# Backend URL for verification/reset links - falls back to localhost for dev
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

conf = None
if MAIL_ENABLED:
    conf = ConnectionConfig(
        MAIL_USERNAME=MAIL_USERNAME,
        MAIL_PASSWORD=MAIL_PASSWORD,
        MAIL_FROM=MAIL_FROM,
        MAIL_PORT=int(MAIL_PORT_RAW),
        MAIL_SERVER=MAIL_SERVER,
        MAIL_STARTTLS=True,
        MAIL_SSL_TLS=False,
        USE_CREDENTIALS=True,
        VALIDATE_CERTS=False,
    )
else:
    print("[MAIL] Email sending is DISABLED — env vars not configured")

async def send_verification_email(email: str, token: str):
    # Змінна має називатися саме так, як у HTML нижче
    verify_url = f"http://localhost:8000/auth/verify/{token}"
    
    # Створюємо красивий HTML-дизайн листа
    html_content = f"""
    <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 600px; margin: 0 auto; padding: 30px; background-color: #f9f9f9; border-radius: 12px; border: 1px solid #eaeaea;">
        <div style="text-align: center; margin-bottom: 20px;">
            <h1 style="color: #2c3e50; margin: 0;">Voluntrack</h1>
            <p style="color: #7f8c8d; font-size: 16px; margin-top: 5px;">Платформа добрих справ</p>
        </div>
        
        <div style="background-color: white; padding: 25px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
            <h2 style="color: #2c3e50; font-size: 20px;">Вітаємо у команді! 🎉</h2>
            <p style="color: #555; font-size: 16px; line-height: 1.5;">
                Дякуємо за реєстрацію. Щоб завершити створення профілю та отримати доступ до всіх можливостей соціальної мережі, будь ласка, підтвердіть свою електронну пошту.
            </p>
            
            <div style="text-align: center; margin: 35px 0;">
                <a href="{verify_url}" style="background-color: #4CAF50; color: white; padding: 14px 30px; text-decoration: none; border-radius: 6px; font-weight: bold; font-size: 16px; display: inline-block; transition: background-color 0.3s;">
                    Підтвердити Email
                </a>
            </div>
            
            <p style="color: #999; font-size: 13px; text-align: center; margin-top: 30px; border-top: 1px solid #eee; padding-top: 15px;">
                Якщо ви не реєструвалися на Voluntrack, просто проігноруйте цей лист.
            </p>
        </div>
    </div>
    """

    message = MessageSchema(
        subject="Підтвердження реєстрації у Voluntrack",
        recipients=[email],
        body=html_content,
        subtype="html" 
    )

    fm = FastMail(conf)
    await fm.send_message(message)


def generate_verification_token() -> str:
    return str(uuid.uuid4())  # випадковий унікальний рядок


async def send_reset_email(email: str, token: str):
    link = f"http://localhost:8000/auth/reset-password?token={token}"

    # Створюємо красивий HTML-дизайн для відновлення пароля
    html_content = f"""
    <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 600px; margin: 0 auto; padding: 30px; background-color: #f9f9f9; border-radius: 12px; border: 1px solid #eaeaea;">
        <div style="text-align: center; margin-bottom: 20px;">
            <h1 style="color: #2c3e50; margin: 0;">Voluntrack</h1>
        </div>
        
        <div style="background-color: white; padding: 25px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
            <h2 style="color: #2c3e50; font-size: 20px;">Скидання пароля 🔐</h2>
            <p style="color: #555; font-size: 16px; line-height: 1.5;">
                Ми отримали запит на скидання пароля для вашого акаунту. Натисніть кнопку нижче, щоб створити новий:
            </p>
            
            <div style="text-align: center; margin: 35px 0;">
                <a href="{link}" style="background-color: #e74c3c; color: white; padding: 14px 30px; text-decoration: none; border-radius: 6px; font-weight: bold; font-size: 16px; display: inline-block; transition: background-color 0.3s;">
                    Скинути пароль
                </a>
            </div>
            
            <p style="color: #999; font-size: 13px; text-align: center; margin-top: 30px; border-top: 1px solid #eee; padding-top: 15px;">
                Якщо ви не робили цей запит, просто проігноруйте цей лист. Ваш пароль залишиться без змін.
            </p>
        </div>
    </div>
    """

    message = MessageSchema(
        subject="Скидання пароля - Voluntrack",
        recipients=[email],
        body=html_content,
        subtype="html" 
    )

    fm = FastMail(conf)
    await fm.send_message(message)
