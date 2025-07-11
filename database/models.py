# chess_opening_trainer/database/models.py
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    lichess_username = Column(String, unique=True, nullable=True)
    # chesscom_username = Column(String, unique=True, nullable=True) # <-- 移除
    training_delay_ms = Column(Integer, default=500)
    error_display_delay_ms = Column(Integer, default=1000)

    openings = relationship("Opening", back_populates="user", cascade="all, delete-orphan")
    mistakes = relationship("Mistake", back_populates="user", cascade="all, delete-orphan")

# ... Opening 和 Mistake 類別保持不變 ...
class Opening(Base):
    __tablename__ = "openings"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    pgn_path = Column(String, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"))
    side = Column(Integer, default=0)  # 0=白方, 1=黑方
    user = relationship("User", back_populates="openings")
    mistakes = relationship("Mistake", back_populates="opening", cascade="all, delete-orphan")
    last_trained_line_index = Column(Integer, default=0)
    mastered_lines = Column(Text, default="")

class Mistake(Base):
    __tablename__ = "mistakes"
    id = Column(Integer, primary_key=True, index=True)
    fen = Column(String, nullable=False, index=True)
    correct_move_uci = Column(String, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"))
    opening_id = Column(Integer, ForeignKey("openings.id"), nullable=True)
    miss_count = Column(Integer, default=1)
    last_missed_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    user = relationship("User", back_populates="mistakes")
    opening = relationship("Opening", back_populates="mistakes")