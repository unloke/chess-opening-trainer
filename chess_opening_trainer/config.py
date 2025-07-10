# -*- coding: utf-8 -*-
import os
from pathlib import Path

# --- 基本路徑設定 ---
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
RESOURCES_DIR = BASE_DIR / "resources"

# 確保資料目錄存在
DATA_DIR.mkdir(exist_ok=True)
(DATA_DIR / "openings").mkdir(exist_ok=True)

# --- 資料庫設定 ---
DB_NAME = "trainer_data.db"
DB_PATH = DATA_DIR / DB_NAME
# SQLAlchemy 連線字串
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH.as_posix()}"

# --- 訓練設定 ---
REVIEW_CORRECT_DELAY = 1000   # ms
REVIEW_CYCLE_DELAY = 1500     # ms

# --- API 設定 (Lichess 為範例) ---
LICHESS_API_BASE_URL = "https://lichess.org/api"
# 使用者代理，API 請求時建議提供
USER_AGENT = "ChessOpeningTrainer/1.0 (your-contact-email@example.com)"

# --- 日誌設定 ---
LOG_LEVEL = "INFO"
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'