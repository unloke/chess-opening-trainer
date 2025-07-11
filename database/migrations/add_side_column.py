"""
資料庫遷移腳本：為 openings 表添加 side 字段
"""
import logging
from sqlalchemy import text
from ..database import engine

logger = logging.getLogger(__name__)

def migrate():
    """執行遷移"""
    try:
        with engine.connect() as conn:
            # SQLite 專用的檢查方法
            result = conn.execute(text("PRAGMA table_info(openings)"))
            columns = [row[1] for row in result.fetchall()]
            
            if 'side' not in columns:
                # 添加 side 字段
                conn.execute(text("ALTER TABLE openings ADD COLUMN side INTEGER DEFAULT 0"))
                conn.commit()
                logger.info("已成功添加 side 字段到 openings 表")
                print("已成功添加 side 字段到 openings 表")
            else:
                logger.info("side 字段已存在，跳過遷移")
                print("side 字段已存在，跳過遷移")
    except Exception as e:
        logger.error(f"執行遷移時發生錯誤: {e}")
        print(f"執行遷移時發生錯誤: {e}")
        raise

if __name__ == "__main__":
    migrate() 