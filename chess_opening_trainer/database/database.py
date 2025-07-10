# -*- coding: utf-8 -*-
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from ..config import SQLALCHEMY_DATABASE_URL

# 建立資料庫引擎
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

# 建立 SessionLocal 類別，每個實例都是一個資料庫會話
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 建立 Base 類別，我們的 ORM 模型將繼承它
Base = declarative_base()

def init_db():
    """初始化資料庫，建立所有表格。"""
    from . import models  # 確保模型被註冊
    Base.metadata.create_all(bind=engine)