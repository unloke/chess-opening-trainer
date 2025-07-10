import chess
import logging
import random
from PyQt5.QtCore import QObject, pyqtSignal, QTimer
from typing import List, Optional

from .opening_manager import Opening
from .progress_tracker import ProgressTracker

logger = logging.getLogger(__name__)


class TrainingSession(QObject):
    """單一路線「學習 ➜ 複習」一體化流程（V4：加入進度訊號）。

    ### 主要差異
    1. 新增 `progress_changed` Signal → `(line_idx, line_total, step_idx, step_total)`。
    2. 任何棋盤推進、模式切換都會 `_emit_progress()`。
    3. GUI 可直接把此訊號綁到一個 `ProgressPanel`（下面完整程式碼範例）來顯示 *4/593 條線 · 1/22 步* 等字樣。
    """

    # ---------- Qt Signals ---------- #
    state_changed = pyqtSignal(str, object)           # (event_type, board)
    info_updated = pyqtSignal(str)                    # 文字提示
    mistake_made = pyqtSignal(object, object)         # (user_move, expected_move)
    line_completed = pyqtSignal(int)                  # 成功掌握一整條路線
    session_completed = pyqtSignal()                  # 全部路線完成
    progress_changed = pyqtSignal(int, int, int, int) # 新增：(line_idx, line_total, step_idx, step_total)

    # ---------- ctor ---------- #
    def __init__(
        self,
        opening: Opening,
        player_color: chess.Color,
        computer_move_delay: int = 500,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self.opening = opening
        self.player_color = player_color
        self.computer_move_delay = computer_move_delay

        # 狀態
        self.board = chess.Board()
        self.current_line: List[chess.Move] = []
        self.mode: str = "learn"  # "learn" | "review"
        self.current_move_index: int = 0  # learn 模式用
        self.review_queue: List[int] = []  # review 模式用，存 ply index
        self.next_round_mistakes: List[int] = []  # review 下一輪
        self.mistakes_in_line: List[int] = []  # 全部錯誤 (去重)

        # 進度
        self.progress = ProgressTracker()
        self.progress.ensure_opening(str(opening.db_model.id), len(opening.all_lines))

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------
    def start_new_line(self) -> None:
        self._load_progress_line()
        self._enter_learn_mode()
        QTimer.singleShot(0, self._process_next_position)

    def get_hint(self) -> Optional[chess.Move]:
        if self.mode == "learn" and self.current_move_index < len(self.current_line):
            return self.current_line[self.current_move_index]
        if self.mode == "review" and self.review_queue:
            idx = self.review_queue[0]
            return self.current_line[idx]
        return None

    def handle_user_move(self, move: chess.Move) -> None:
        if self.mode == "learn":
            self._handle_user_move_learn(move)
        else:
            self._handle_user_move_review(move)

    # ---------------------------------------------------------------------
    # Internal – Learn mode
    # ---------------------------------------------------------------------
    def _handle_user_move_learn(self, move: chess.Move) -> None:
        if self.current_move_index >= len(self.current_line):
            return

        expected = self.current_line[self.current_move_index]
        if move == expected:
            # 正確 — 推進
            self.board.push(move)
            self.current_move_index += 1
            self.progress.advance_ply()
            self.state_changed.emit("board_updated", self.board.copy())
            self.info_updated.emit(f"答對！({move.uci()})")
            self._emit_progress()
            QTimer.singleShot(0, self._process_next_position)
        else:
            # 錯誤 — 不推進，收錄錯題
            if self.current_move_index not in self.mistakes_in_line:
                self.mistakes_in_line.append(self.current_move_index)
            self.info_updated.emit(f"錯誤！正確走法: {expected.uci()}")
            self.mistake_made.emit(move, expected)

    def _process_next_position(self) -> None:
        if self.mode != "learn":
            return

        # 線結束？
        if self.current_move_index >= len(self.current_line):
            if self.mistakes_in_line:
                self._enter_review_mode()
            else:
                self._complete_current_line()
            return

        # 電腦回合？
        if self.board.turn != self.player_color:
            move = self.current_line[self.current_move_index]
            self.board.push(move)
            self.current_move_index += 1
            self.state_changed.emit("board_updated", self.board.copy())
            self.info_updated.emit("電腦走棋中…")
            self._emit_progress()
            QTimer.singleShot(self.computer_move_delay, self._process_next_position)
            return

        # 玩家回合
        self.state_changed.emit("board_updated", self.board.copy())
        self.info_updated.emit("輪到你了。")
        self._emit_progress()

    # ---------------------------------------------------------------------
    # Internal – Review mode
    # ---------------------------------------------------------------------
    def _enter_review_mode(self) -> None:
        self.mode = "review"
        self.review_queue = self.mistakes_in_line.copy()
        random.shuffle(self.review_queue)
        self.next_round_mistakes = []
        self.info_updated.emit("進入複習階段！")
        QTimer.singleShot(0, self._prepare_next_review_item)

    def _prepare_next_review_item(self) -> None:
        if not self.review_queue:
            if not self.next_round_mistakes:
                self._complete_current_line()
                return
            self.review_queue = self.next_round_mistakes
            random.shuffle(self.review_queue)
            self.next_round_mistakes = []
            self.info_updated.emit("新的複習輪開始！")

        idx = self.review_queue[0]
        self._setup_board_to_ply(idx)
        self.state_changed.emit("board_updated", self.board.copy())
        self.info_updated.emit("複習：請走正確一步。")
        self._emit_progress(step_override=idx + 1)

    def _handle_user_move_review(self, move: chess.Move) -> None:
        if not self.review_queue:
            return
        idx = self.review_queue[0]
        expected = self.current_line[idx]
        if move == expected and move in self.board.legal_moves:
            self.board.push(move)
            self.state_changed.emit("board_updated", self.board.copy())
            self.info_updated.emit("答對！")
            self.review_queue.pop(0)
            self._emit_progress(step_override=idx + 1)
            QTimer.singleShot(0, self._prepare_next_review_item)
        else:
            if idx not in self.next_round_mistakes:
                self.next_round_mistakes.append(idx)
            self.info_updated.emit(f"錯誤！正確走法: {expected.uci()}")
            self.mistake_made.emit(move, expected)

    # ---------------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------------
    def _setup_board_to_ply(self, ply: int) -> None:
        self.board.reset()
        fen = chess.STARTING_FEN
        if self.opening.root_node:
            fen = self.opening.root_node.headers.get("FEN", chess.STARTING_FEN)
        try:
            self.board.set_fen(fen)
        except ValueError:
            pass
        for mv in self.current_line[:ply]:
            if mv in self.board.legal_moves:
                self.board.push(mv)
            else:
                break

    def _complete_current_line(self) -> None:
        data = self.progress.data
        line_ptr = data.line_order[data.current_line_ptr]
        self.line_completed.emit(line_ptr)
        self.progress.advance_line()
        self.progress.save()
        if self.progress.data.current_line_ptr >= len(data.line_order):
            self.info_updated.emit("恭喜！所有路線已完成訓練。")
            self.session_completed.emit()
            return
        self._load_progress_line()
        self._enter_learn_mode()
        QTimer.singleShot(0, self._process_next_position)

    def _load_progress_line(self) -> None:
        data = self.progress.data
        line_ptr = data.line_order[data.current_line_ptr]
        self.current_line = self.opening.all_lines[line_ptr]
        self.current_move_index = data.ply_index
        self.mistakes_in_line = []
        self.review_queue = []
        self.next_round_mistakes = []

    def _enter_learn_mode(self) -> None:
        self.mode = "learn"
        self._setup_board_to_ply(self.current_move_index)
        self.state_changed.emit("board_updated", self.board.copy())
        self.info_updated.emit("開始學習新路線！")
        self._emit_progress()

    def _emit_progress(self, *, step_override: Optional[int] = None) -> None:
        """對 GUI 發射目前位置進度。"""
        data = self.progress.data
        line_idx = data.current_line_ptr + 1  # +1 for human-readable
        line_total = len(data.line_order)
        if self.mode == "learn":
            step_idx = self.current_move_index + 1  # +1 -> human-readable
        else:  # review
            step_idx = step_override or 1
        step_total = len(self.current_line)
        self.progress_changed.emit(line_idx, line_total, step_idx, step_total)
