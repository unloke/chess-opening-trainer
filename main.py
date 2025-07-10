# chess_opening_trainer/main.py

# -*- coding: utf-8 -*-
import sys
import logging
from PyQt5 import QtWidgets

# 使用絕對導入，從專案根目錄開始
from chess_opening_trainer.config import LOG_LEVEL, LOG_FORMAT
from chess_opening_trainer.database.database import init_db
from chess_opening_trainer.gui.main_window import ChessMainWindow

def setup_logging():
    """設定全域日誌記錄器。"""
    logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)
    # 可以為特定模組設定不同的日誌級別
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

def main():
    # 1. 初始化日誌
    setup_logging()
    
    # 2. 初始化資料庫 (如果不存在，則建立)
    logging.info("正在初始化資料庫...")
    init_db()
    logging.info("資料庫初始化完成。")

    # 3. 啟動 Qt 應用程式
    app = QtWidgets.QApplication(sys.argv)
    
    # 4. 創建並顯示主視窗
    window = ChessMainWindow()
    window.show()
    
    # 5. 進入事件循環
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()