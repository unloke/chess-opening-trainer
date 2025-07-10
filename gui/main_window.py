# D:/gui/main_window.py (最終功能正常版)

import logging
from datetime import date, datetime
from PyQt5 import QtCore, QtGui, QtWidgets
import chess
import chess.pgn

from ..config import BASE_DIR
from ..core.opening_manager import OpeningManager
from ..core.training_session import TrainingSession
from ..core.review_session import ReviewSession
from ..core.game_analyzer import GameAnalyzer
from ..database.database import SessionLocal
from ..database.models import User, Mistake
from ..services.lichess_api import LichessAPI
from .components.chess_board import ChessBoardWidget
from .dialogs.opening_import_dialog import OpeningImportDialog
from .tabs.training_tab import TrainingTab
from .tabs.management_tab import ManagementTab
from .tabs.settings_tab import SettingsTab
from .tabs.performance_tab import PerformanceTab
from .tabs.review_tab import ReviewTab

logger = logging.getLogger(__name__)

class ChessMainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("西洋棋開局訓練器")
        self.setWindowIcon(QtGui.QIcon(str(BASE_DIR / "resources" / "icons" / "app_icon.png")))
        self.resize(1366, 768)
        self.db_session = SessionLocal()
        self.current_user = self._get_or_create_user()
        self.opening_manager = OpeningManager(user_id=self.current_user.id)
        self.game_analyzer = None
        self.training_session: TrainingSession | None = None
        self.review_session: ReviewSession | None = None
        self._setup_central_widget()
        self._connect_signals()
        self.load_stylesheet()
        self.update_all_lists()
        self.settings_tab.load_settings(self.current_user.__dict__)

    def _get_or_create_user(self):
        user = self.db_session.query(User).first()
        if not user:
            user = User(username="default_user", lichess_username="", training_delay_ms=500)
            self.db_session.add(user)
            self.db_session.commit()
            self.db_session.refresh(user)
        return user

    def load_stylesheet(self):
        stylesheet_path = BASE_DIR / "gui" / "styles" / "dark_theme.qss"
        try:
            with open(stylesheet_path, "r", encoding="utf-8") as f: self.setStyleSheet(f.read())
        except FileNotFoundError: logger.warning(f"樣式表 '{stylesheet_path}' 未找到。")

    def _setup_central_widget(self):
        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self.setCentralWidget(splitter)
        self.chessboard = ChessBoardWidget()
        splitter.addWidget(self.chessboard)
        self.tab_widget = QtWidgets.QTabWidget()
        self.tab_widget.setMinimumWidth(380)
        self.training_tab = TrainingTab()
        self.performance_tab = PerformanceTab()
        self.review_tab = ReviewTab()
        self.management_tab = ManagementTab()
        self.settings_tab = SettingsTab()
        self.tab_widget.addTab(self.training_tab, "開局練習")
        self.tab_widget.addTab(self.performance_tab, "當日表現")
        self.tab_widget.addTab(self.review_tab, "錯題複習")
        self.tab_widget.addTab(self.management_tab, "開局庫管理")
        self.tab_widget.addTab(self.settings_tab, "設定")
        splitter.addWidget(self.tab_widget)
        splitter.setSizes([int(self.width() * 0.65), int(self.width() * 0.35)])

    def _connect_signals(self):
        self.chessboard.moveMade.connect(self.on_user_move)
        self.training_tab.start_training_requested.connect(self.start_new_line)
        self.training_tab.hint_button.clicked.connect(self.show_hint)
        self.management_tab.add_opening_requested.connect(self.add_new_opening)
        self.management_tab.remove_opening_requested.connect(self.remove_opening)
        self.settings_tab.settings_saved.connect(self.save_user_settings)
        self.performance_tab.analyze_requested.connect(self.analyze_daily_performance)
        self.review_tab.start_review_requested.connect(self.start_review_session)
        self.tab_widget.currentChanged.connect(self.on_tab_changed)

    def analyze_daily_performance(self):
        opening_name = self.training_tab.opening_combo.currentText()
        if not opening_name:
            QtWidgets.QMessageBox.warning(self, "錯誤", "請先在'開局練習'分頁中選擇一個開局庫進行對比。")
            return
        opening = self.opening_manager.get_opening_by_name(opening_name)
        if not opening: return
        lichess_username = self.current_user.lichess_username
        if not lichess_username:
            QtWidgets.QMessageBox.warning(self, "錯誤", "請先在'設定'中填寫 Lichess 用戶名。")
            return
        self.performance_tab.set_status("正在從 Lichess 獲取對局...")
        QtWidgets.QApplication.processEvents()
        
        api = LichessAPI(lichess_username)
        today_start = datetime.combine(date.today(), datetime.min.time())
        games = api.get_last_games(max_games=50, since=today_start, perf_types=["blitz", "rapid", "classical"])
        
        if not games:
            self.performance_tab.set_results(f"今天在 Lichess 上沒有找到 '{lichess_username}' 的任何標準對局。")
            return

        self.game_analyzer = GameAnalyzer(opening)
        results = []
        user_to_check_lower = lichess_username.lower()
        found_user_games = 0

        for game in games:
            white_player = game.headers.get("White", "").lower()
            black_player = game.headers.get("Black", "").lower()

            user_color, opponent = None, None
            if user_to_check_lower == white_player:
                user_color, opponent, found_user_games = chess.WHITE, black_player, found_user_games + 1
            elif user_to_check_lower == black_player:
                user_color, opponent, found_user_games = chess.BLACK, white_player, found_user_games + 1
            else:
                continue

            moves = list(game.mainline_moves())
            if not moves: continue

            deviation = self.game_analyzer.find_deviation(moves, user_color)
            
            opponent_name = opponent.capitalize() if opponent else "Unknown"
            game_result_str = f"對局 vs {opponent_name} ({game.headers.get('Site', '')}):"

            if deviation:
                node, move, ply = deviation
                board = node.board()
                ply_number = (ply // 2) + 1
                color_str = "白方" if board.turn == chess.WHITE else "黑方"
                try: san_move = board.san(move)
                except: san_move = move.uci()
                correct_moves_san = ', '.join([v.san() for v in node.variations]) or "N/A"
                game_result_str += f"\n  在第 {ply_number} 手 ({color_str}) 偏離了 '{opening.name}'。"
                game_result_str += f"\n  您走了: {san_move} (應走: {correct_moves_san})"
            else:
                game_result_str += "\n  完美！您的走法完全在開局庫內。"
            results.append(game_result_str)

        if not found_user_games:
            self.performance_tab.set_results(f"在 Lichess 上找到的標準對局中，沒有找到玩家 '{lichess_username}' 的對局。請檢查用戶名設置。")
        else:
            summary = f"分析完成！找到並分析了 {found_user_games} 場您的對局。\n\n"
            self.performance_tab.set_results(summary + "\n\n---\n\n".join(results))

    def update_all_lists(self):
        names = self.opening_manager.get_all_opening_names()
        self.training_tab.update_opening_list(names)
        self.management_tab.update_opening_list(names)
    def add_new_opening(self):
        dialog = OpeningImportDialog(self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            name, path = dialog.get_data()
            if name and path:
                if self.opening_manager.add_opening(name, path):
                    QtWidgets.QMessageBox.information(self, "成功", f"開局 '{name}' 已匯入。")
                    self.update_all_lists()
                else:
                    QtWidgets.QMessageBox.critical(self, "錯誤", f"無法匯入 PGN: {path}")
    def remove_opening(self, name: str):
        if self.opening_manager.remove_opening(name):
            QtWidgets.QMessageBox.information(self, "成功", f"開局 '{name}' 已被移除。")
            self.update_all_lists()
        else:
            QtWidgets.QMessageBox.critical(self, "錯誤", f"移除開局 '{name}' 失敗。")
    def save_user_settings(self, settings: dict):
        try:
            user = self.current_user
            user.lichess_username = settings["lichess_username"]
            user.training_delay_ms = settings["training_delay_ms"]
            self.db_session.commit()
            QtWidgets.QMessageBox.information(self, "成功", "設定已儲存。")
        except Exception as e:
            self.db_session.rollback()
            QtWidgets.QMessageBox.critical(self, "錯誤", f"儲存設定失敗: {e}")
    def on_tab_changed(self, index):
        current_tab = self.tab_widget.widget(index)
        is_interactive_tab = (current_tab == self.training_tab or current_tab == self.review_tab)
        self.chessboard.allow_user_input = is_interactive_tab
        if current_tab != self.training_tab: self.training_session = None
        if current_tab != self.review_tab: self.review_session = None
        if current_tab == self.review_tab:
            self.review_tab.status_label.setText("點擊按鈕開始複習您之前犯錯的局面。")
    def on_user_move(self, move: chess.Move):
        current_tab = self.tab_widget.currentWidget()
        if self.training_session and current_tab == self.training_tab:
            self.training_session.handle_user_move(move)
        elif self.review_session and current_tab == self.review_tab:
            self.review_session.handle_user_move(move)
    def start_new_line(self, opening_name, player_color):
        opening = self.opening_manager.get_opening_by_name(opening_name)
        if not opening: return
        self.review_session = None
        computer_move_delay = self.current_user.training_delay_ms
        self.training_session = TrainingSession(opening, player_color, computer_move_delay)
        self.training_session.state_changed.connect(self.on_board_update)
        self.training_session.info_updated.connect(self.training_tab.info_label.setText)
        self.training_session.mistake_made.connect(self.on_mistake_made)
        self.training_session.progress_changed.connect(self.training_tab.update_progress)
        self.chessboard.set_flipped(player_color == chess.BLACK)
        self.chessboard.allow_user_input = True
        self.training_tab.hint_button.setEnabled(True)
        self.training_session.start_new_line()
    def on_board_update(self, event_type: str, board: chess.Board):
        if event_type == "board_updated":
            self.chessboard.set_board(board)
            self.chessboard.clear_highlights()
            if board.move_stack:
                last_move = board.peek()
                self.chessboard.highlight_move(last_move, self.chessboard.COLORS["last_move"], self.chessboard.COLORS["last_move"])
    def on_mistake_made(self, user_move: chess.Move, expected_move: chess.Move):
        board = self.training_session.board
        fen = board.fen()
        self.chessboard.clear_highlights()
        self.chessboard.highlight_move(user_move, self.chessboard.COLORS["deviation_from"], self.chessboard.COLORS["deviation_to"])
        self.chessboard.highlight_move(expected_move, self.chessboard.COLORS["hint_from"], self.chessboard.COLORS["hint_to"])
        existing_mistake = self.db_session.query(Mistake).filter_by(fen=fen, user_id=self.current_user.id).first()
        if existing_mistake:
            existing_mistake.miss_count += 1
        else:
            new_mistake = Mistake(fen=fen, correct_move_uci=expected_move.uci(), user_id=self.current_user.id, opening_id=self.training_session.opening.db_model.id)
            self.db_session.add(new_mistake)
        self.db_session.commit()
    def show_hint(self):
        if self.training_session and self.tab_widget.currentWidget() == self.training_tab:
            hint_move = self.training_session.get_hint()
            if hint_move:
                self.training_tab.info_label.setText(f"提示: {hint_move.uci()}")
                self.chessboard.highlight_move(hint_move, self.chessboard.COLORS["hint_from"], self.chessboard.COLORS["hint_to"])
    def start_review_session(self):
        self.training_session = None
        self.tab_widget.setCurrentWidget(self.review_tab)
        self.review_session = ReviewSession(self.current_user.id)
        self.review_session.state_changed.connect(self.on_review_state_changed)
        self.review_session.review_finished.connect(self.on_review_finished)
        self.review_session.feedback_provided.connect(self.on_review_feedback)
        self.review_session.start()
    def on_review_state_changed(self, board, remaining, total):
        self.chessboard.set_board(board)
        self.chessboard.clear_highlights()
        self.review_tab.update_status(remaining, total)
        self.review_tab.reset_feedback_style()
        self.chessboard.set_flipped(board.turn == chess.BLACK)
        self.chessboard.allow_user_input = True
    def on_review_feedback(self, is_correct, correct_move_san):
        self.chessboard.allow_user_input = False
        self.review_tab.show_feedback(is_correct, correct_move_san)
        if not is_correct:
            correct_move = self.review_session.board.parse_san(correct_move_san)
            self.chessboard.highlight_move(correct_move, self.chessboard.COLORS["hint_from"], self.chessboard.COLORS["hint_to"])
    def on_review_finished(self, status: str):
        message = "恭喜！所有錯題都已複習完畢。" if status == "completed" else "太棒了！資料庫中沒有錯題記錄。"
        self.review_tab.status_label.setText(message)
        self.review_tab.info_label.setText("")
        self.review_session = None
    def closeEvent(self, event: QtGui.QCloseEvent):
        self.db_session.close()
        super().closeEvent(event)