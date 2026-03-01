from sqlalchemy import Column, Integer, String, Float, Boolean
# Змінюємо ".database" на "app.database" для стабільності
from app.database import Base

class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    description = Column(String)
    goal_amount = Column(Float)
    current_raised = Column(Float, default=0.0)
    is_active = Column(Boolean, default=True)