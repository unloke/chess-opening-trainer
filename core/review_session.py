# chess_opening_trainer/core/review_session.py
import chess
import random
from PyQt5.QtCore import QObject, pyqtSignal, QTimer
from typing import List, Tuple, Optional
from ..database.models import Mistake
from ..database.database import SessionLocal
import logging

class ReviewSession(QObject):
    """管理一個錯題複習會話。"""
    state_changed = pyqtSignal(object, int, int) # board, remaining_count, total_count
    review_finished = pyqtSignal(str) # "completed" or "no_mistakes"
    feedback_provided = pyqtSignal(bool, str) # is_correct, correct_move_san

    def __init__(self, user_id: int, custom_mistakes: Optional[List[Mistake]] = None):
        super().__init__()
        self.user_id = user_id
        self.db = SessionLocal()
        self.board = chess.Board()
        
        self.mistakes_queue: List[Mistake] = []
        self.failed_mistakes: List[Mistake] = []
        self.total_count = 0
        self.custom_mistakes = custom_mistakes

    def start(self):
        """開始複習會話。"""
        if self.custom_mistakes:
            # 使用自定義錯題列表（如今日錯題）
            self.mistakes_queue = self.custom_mistakes.copy()
            logging.info(f"使用自定義錯題列表，錯題數量: {len(self.mistakes_queue)}")
        else:
            # 使用所有錯題
            self.mistakes_queue = self.db.query(Mistake).filter_by(user_id=self.user_id).order_by(Mistake.miss_count.desc()).all()
            logging.info(f"從資料庫載入所有錯題，錯題數量: {len(self.mistakes_queue)}")
        
        # 檢查錯題是否有效
        valid_mistakes = []
        for mistake in self.mistakes_queue:
            try:
                # 嘗試解析FEN，確保錯題有效
                board = chess.Board(mistake.fen)
                valid_mistakes.append(mistake)
            except Exception as e:
                logging.error(f"無效的錯題FEN: {mistake.fen}, 錯誤: {e}")
        
        self.mistakes_queue = valid_mistakes
        logging.info(f"有效錯題數量: {len(self.mistakes_queue)}")
        
        random.shuffle(self.mistakes_queue)
        
        if not self.mistakes_queue:
            self.review_finished.emit("no_mistakes")
            return
        
        self.total_count = len(self.mistakes_queue)
        self.failed_mistakes = []
        self.present_next_mistake()

    def present_next_mistake(self):
        """呈現下一個錯題。"""
        if not self.mistakes_queue:
            if self.failed_mistakes:
                # 如果有答錯的，再來一輪
                self.mistakes_queue = self.failed_mistakes
                self.failed_mistakes = []
                self.total_count = len(self.mistakes_queue)
                self.present_next_mistake()
            else:
                self.review_finished.emit("completed")
            return

        current_mistake = self.mistakes_queue[0]
        self.board.set_fen(current_mistake.fen)
        self.state_changed.emit(self.board.copy(), len(self.mistakes_queue), self.total_count)

    def handle_user_move(self, move: chess.Move):
        """處理用戶的回答。"""
        current_mistake = self.mistakes_queue[0]
        correct_move = chess.Move.from_uci(current_mistake.correct_move_uci)
        is_correct = (move == correct_move)
        # 嘗試生成 SAN 記譜法，如果失敗則使用 UCI
        if correct_move in self.board.legal_moves:
            try:
                correct_move_san = self.board.san(correct_move)
            except Exception:
                correct_move_san = correct_move.uci()
        else:
            # 不合法，直接用 UCI 並給提示
            correct_move_san = correct_move.uci() + "（此局面下不合法，請檢查保存/分析流程）"
        self.feedback_provided.emit(is_correct, correct_move_san)
        if is_correct:
            self.mistakes_queue.pop(0)
        else:
            self.failed_mistakes.append(self.mistakes_queue.pop(0))
        QTimer.singleShot(1500, self.present_next_mistake)