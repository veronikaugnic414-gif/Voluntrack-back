from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from dotenv import load_dotenv
import os
import uuid

load_dotenv()

conf = ConnectionConfig(
    MAIL_USERNAME=os.getenv("MAIL_USERNAME"),
    MAIL_PASSWORD=os.getenv("MAIL_PASSWORD"),
    MAIL_FROM=os.getenv("MAIL_FROM"),
    MAIL_PORT=int(os.getenv("MAIL_PORT")),
    MAIL_SERVER=os.getenv("MAIL_SERVER"),
    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True,
)


async def send_verification_email(email: str, token: str):
    link = f"http://localhost:8000/auth/verify/{token}"

    message = MessageSchema(
        subject="Підтвердження email",
        recipients=[email],
        body=f"Привіт! Перейди за посиланням щоб підтвердити акаунт:\n\n{link}",
        subtype="plain"
    )

    fm = FastMail(conf)
    await fm.send_message(message)


def generate_verification_token() -> str:
    return str(uuid.uuid4())  # випадковий унікальний рядок