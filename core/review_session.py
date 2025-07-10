# chess_opening_trainer/core/review_session.py
import chess
import random
from PyQt5.QtCore import QObject, pyqtSignal, QTimer
from typing import List, Tuple
from ..database.models import Mistake
from ..database.database import SessionLocal

class ReviewSession(QObject):
    """管理一個錯題複習會話。"""
    state_changed = pyqtSignal(object, int, int) # board, remaining_count, total_count
    review_finished = pyqtSignal(str) # "completed" or "no_mistakes"
    feedback_provided = pyqtSignal(bool, str) # is_correct, correct_move_san

    def __init__(self, user_id: int):
        super().__init__()
        self.user_id = user_id
        self.db = SessionLocal()
        self.board = chess.Board()
        
        self.mistakes_queue: List[Mistake] = []
        self.failed_mistakes: List[Mistake] = []
        self.total_count = 0

    def start(self):
        """開始複習會話。"""
        self.mistakes_queue = self.db.query(Mistake).filter_by(user_id=self.user_id).order_by(Mistake.miss_count.desc()).all()
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
        correct_move_san = self.board.san(correct_move)
        
        self.feedback_provided.emit(is_correct, correct_move_san)
        
        if is_correct:
            # 答對了，從佇列中移除
            self.mistakes_queue.pop(0)
        else:
            # 答錯了，移到失敗列表，稍後再複習
            self.failed_mistakes.append(self.mistakes_queue.pop(0))
        
        # 延遲後呈現下一題
        QTimer.singleShot(1500, self.present_next_mistake)