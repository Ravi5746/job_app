from sqlalchemy import Column, Integer, String, Text, DateTime, JSON
from sqlalchemy.sql import func
from app.db.session import Base

class QACache(Base):
    __tablename__ = "qa_cache"

    id = Column(Integer, primary_key=True, index=True)
    question_text = Column(Text, unique=True, index=True, nullable=False)
    question_embedding = Column(JSON, nullable=False) # list of floats (384 dimensions)
    answer_text = Column(Text, nullable=False)
    reasoning = Column(Text, nullable=True)
    used_count = Column(Integer, default=0)
    last_used = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
