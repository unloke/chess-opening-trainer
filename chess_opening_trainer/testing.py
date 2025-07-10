# chess_opening_trainer/gui/main_window.py
import logging
from datetime import date, datetime
from PyQt5 import QtCore, QtGui, QtWidgets
import chess
import chess.pgn

# Core and services
from ..config import BASE_DIR
from ..core.opening_manager import OpeningManager
from ..core.training_session import TrainingSession
from ..core.review_session import ReviewSession # <-- Import ReviewSession
from ..core.game_analyzer import GameAnalyzer
from ..database.database import SessionLocal
from ..database.models import User
from ..services.lichess_api import LichessAPI

# GUI Components
from .components.chess_board import ChessBoardWidget
from .dialogs.opening_import_dialog import OpeningImportDialog
from .tabs.training_tab import TrainingTab
from .tabs.management_tab import ManagementTab
from .tabs.settings_tab import SettingsTab
from .tabs.performance_tab import PerformanceTab
from .tabs.review_tab import ReviewTab # <-- Import ReviewTab

logger = logging.getLogger(__name__)

# --- 新的棋盤容器 ---
class ChessBoardContainer(QtWidgets.QWidget):
    def __init__(self, board_widget: QtWidgets.QWidget, parent=None):
        super().__init__(parent)
        self.board_widget = board_widget
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        v_layout = QtWidgets.QVBoxLayout()
        v_layout.addStretch(1)
        v_layout.addWidget(self.board_widget, 0, QtCore.Qt.AlignCenter)
        v_layout.addStretch(1)
        layout.addLayout(v_layout)

    def resizeEvent(self, event: QtGui.QResizeEvent):
        super().resizeEvent(event)
        # 强制棋盘为正方形
        new_size = min(self.width(), self.height())
        self.board_widget.setFixedSize(new_size, new_size)

class ChessMainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("西洋棋開局訓練器 Pro")
        self.setWindowIcon(QtGui.QIcon(str(BASE_DIR / "resources" / "icons" / "app_icon.png")))
        self.resize(1366, 768) # 使用常見的螢幕解析度

        self.db_session = SessionLocal()
        self.current_user = self._get_or_create_user()
        self.opening_manager = OpeningManager(user_id=self.current_user.id)
        
        # --- Session Management ---
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
            user = User(username="default_user", lichess_username="", chesscom_username="", training_delay_ms=500)
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
        main_widget = QtWidgets.QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QtWidgets.QHBoxLayout(main_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # --- Left Panel (Chessboard) ---
        self.chessboard = ChessBoardWidget()
        board_container = ChessBoardContainer(self.chessboard)
        main_layout.addWidget(board_container, 5) # 給予棋盤更大的拉伸因子

        # --- Right Panel (Tabs) ---
        self.tab_widget = QtWidgets.QTabWidget()
        self.training_tab = TrainingTab()
        self.performance_tab = PerformanceTab()
        self.review_tab = ReviewTab() # <-- 建立 ReviewTab 實例
        self.management_tab = ManagementTab()
        self.settings_tab = SettingsTab()

        self.tab_widget.addTab(self.training_tab, "開局練習")
        self.tab_widget.addTab(self.performance_tab, "當日表現")
        self.tab_widget.addTab(self.review_tab, "錯題複習") # <-- 加入 Tab
        self.tab_widget.addTab(self.management_tab, "開局庫管理")
        self.tab_widget.addTab(self.settings_tab, "設定")
        
        main_layout.addWidget(self.tab_widget, 4) # 調整拉伸因子

    def _connect_signals(self):
        self.chessboard.moveMade.connect(self.on_user_move)
        self.training_tab.start_training_requested.connect(self.start_new_line)
        self.training_tab.hint_button.clicked.connect(self.show_hint)
        self.management_tab.add_opening_requested.connect(self.add_new_opening)
        self.management_tab.remove_opening_requested.connect(self.remove_opening)
        self.settings_tab.settings_saved.connect(self.save_user_settings)
        self.performance_tab.analyze_requested.connect(self.analyze_daily_performance)
        self.review_tab.start_review_requested.connect(self.start_review_session)
        # 監聽分頁切換
        self.tab_widget.currentChanged.connect(self.on_tab_changed)
    
    def analyze_daily_performance(self, platform: str, _):
        opening_name = self.training_tab.opening_combo.currentText()
        if not opening_name:
            QtWidgets.QMessageBox.warning(self, "錯誤", "請先在'開局練習'分頁中選擇一個開局庫進行對比。")
            return

        opening = self.opening_manager.get_opening_by_name(opening_name)
        if not opening or not opening.root_node:
            QtWidgets.QMessageBox.critical(self, "錯誤", f"無法載入開局庫 '{opening_name}'。")
            return

        self.performance_tab.set_status(f"正在從 {platform} 獲取對局...")
        QtWidgets.QApplication.processEvents()

        games = []
        user_to_check = ""

        if platform == "Lichess":
            if not self.current_user.lichess_username:
                QtWidgets.QMessageBox.warning(self, "錯誤", "請先在'設定'中填寫 Lichess 用戶名。")
                return
            api = LichessAPI(self.current_user.lichess_username)
            today_start = datetime.combine(date.today(), datetime.min.time())
            games = api.get_last_games(max_games=50, since=today_start, perf_types=["blitz", "rapid", "classical"])
            user_to_check = self.current_user.lichess_username.lower()
        
        elif platform == "Chess.com":
            self.performance_tab.set_results(f"Chess.com API 功能待完整實現。")
            return

        if not games:
            self.performance_tab.set_results(f"今天在 {platform} 上沒有找到任何對局。")
            return

        analyzer = GameAnalyzer(opening)
        results = []
        for game in games:
            white_player = game.headers.get("White", "").lower()
            black_player = game.headers.get("Black", "").lower()

            if user_to_check == white_player:
                player_color = chess.WHITE
                opponent = game.headers.get("Black", "N/A")
            elif user_to_check == black_player:
                player_color = chess.BLACK
                opponent = game.headers.get("White", "N/A")
            else:
                continue # 不是該用戶的對局

            moves = list(game.mainline_moves())
            deviation = analyzer.find_deviation(moves)
            
            game_result_str = f"對局 vs {opponent} ({game.headers.get('Site', '')}):" # <-- 修正 2: 變數改名
            if deviation:
                board, move, ply = deviation
                ply_number = (ply // 2) + 1
                color_str = "白方" if board.turn == chess.WHITE else "黑方"
                
                try:
                    san_move = board.san(move)
                except chess.IllegalMoveError:
                    san_move = move.uci() # Fallback to UCI notation

                game_result_str += f"\n  在第 {ply_number} 手 ({color_str}) 偏離了 '{opening.name}' 開局庫。"
                game_result_str += f"\n  您走了: {san_move} (正確走法之一: {', '.join([v.san() for v in deviation[0].variations]) if deviation[0].variations else 'N/A'})"
            else:
                game_result_str += "\n  完美！您的走法完全在開局庫內。"
            results.append(game_result_str) # <-- 修正 2: 將結果加入列表

        if not results:
            self.performance_tab.set_results(f"今天在 {platform} 上找到了對局，但玩家名稱不匹配（檢查大小寫）。")
        else:
            self.performance_tab.set_results("\n\n---\n\n".join(results))

    def resizeEvent(self, event: QtGui.QResizeEvent):
        super().resizeEvent(event)
        w = self.chessboard.width()
        self.chessboard.setMinimumHeight(w)

    # --- 其他方法保持不變 ---
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
            user.chesscom_username = settings["chesscom_username"]
            user.training_delay_ms = settings["training_delay_ms"]
            self.db_session.commit()
            QtWidgets.QMessageBox.information(self, "成功", "設定已儲存。")
            logger.info(f"User {user.id} settings updated.")
        except Exception as e:
            self.db_session.rollback()
            QtWidgets.QMessageBox.critical(self, "錯誤", f"儲存設定失敗: {e}")
            logger.error(f"Failed to save user settings: {e}")

    def start_new_line(self, opening_name, player_color):
        opening = self.opening_manager.get_opening_by_name(opening_name)
        if not opening: return
        computer_move_delay = self.current_user.training_delay_ms
        self.training_session = TrainingSession(opening, player_color, computer_move_delay)
        self.training_session.state_changed.connect(self.on_board_update)
        self.training_session.info_updated.connect(self.training_tab.info_label.setText)
        self.training_session.mistake_made.connect(self.on_mistake_made)
        self.chessboard.set_flipped(player_color == chess.BLACK)
        self.chessboard.allow_user_input = True
        self.training_tab.hint_button.setEnabled(True)
        self.training_session.start_new_line()
        
    # --- 新增和修改的方法 ---
    def on_tab_changed(self, index):
        """當分頁切換時，確保棋盤和輸入狀態正確。"""
        current_tab = self.tab_widget.widget(index)
        is_interactive_tab = (current_tab == self.training_tab or current_tab == self.review_tab)
        self.chessboard.allow_user_input = is_interactive_tab
        
        # 如果切換到錯題複習分頁，可以考慮自動開始或顯示提示
        if current_tab == self.review_tab:
            self.review_tab.status_label.setText("點擊按鈕開始複習您之前犯錯的局面。")
            # 可以在這裡清空棋盤或顯示一個初始畫面
            # self.chessboard.set_board(chess.Board(None)) # 清空棋盤
    
    def on_user_move(self, move: chess.Move):
        current_tab = self.tab_widget.currentWidget()
        if self.training_session and current_tab == self.training_tab:
            self.training_session.handle_user_move(move)
        elif self.review_session and current_tab == self.review_tab:
            self.review_session.handle_user_move(move)

    # --- 錯題複習邏輯 ---
    def start_review_session(self):
        self.tab_widget.setCurrentWidget(self.review_tab) # 確保在正確的分頁
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
        self.chessboard.set_flipped(board.turn == chess.BLACK) # 翻轉棋盤以匹配當前局面

    def on_review_feedback(self, is_correct, correct_move_san):
        self.review_tab.show_feedback(is_correct, correct_move_san)
        if not is_correct:
            # 高亮正確答案
            correct_move = self.review_session.board.parse_san(correct_move_san)
            self.chessboard.highlight_move(
                correct_move, 
                self.chessboard.COLORS["hint_from"], 
                self.chessboard.COLORS["hint_to"]
            )

    def on_review_finished(self, status: str):
        if status == "completed":
            message = "恭喜！所有錯題都已複習完畢。"
        else: # "no_mistakes"
            message = "太棒了！資料庫中沒有錯題記錄。"
        self.review_tab.status_label.setText(message)
        self.review_tab.info_label.setText("")
        self.review_session = None # 結束會話