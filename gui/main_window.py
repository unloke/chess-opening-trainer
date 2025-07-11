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
from ..core.daily_performance_analyzer import DailyPerformanceAnalyzer
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
        
        try:
            # 初始化資料庫連接
            self.db_session = SessionLocal()
            
            # 獲取用戶資料
            self.current_user = self._get_or_create_user()
            
            # 保存用戶名，避免後續直接訪問 self.current_user 屬性
            self.username = self.current_user.username
            self.user_id = self.current_user.id
            
            # 確保 current_user 有效
            if not self.user_id:
                raise ValueError("無法獲取有效的用戶資料")
                
            # 初始化其他管理器
            self.opening_manager = OpeningManager(user_id=self.user_id)
            self.game_analyzer = None
            self.training_session = None
            self.review_session = None
            self.daily_analyzer = None
            self.performance_review_session = None  # 新增：本次分析錯題複習session
            
            # 設置 UI
            self._setup_central_widget()
            self._connect_signals()
            self.load_stylesheet()
            self.update_all_lists()
            
            # 載入設定
            user_settings = {
                'username': self.username,
                'lichess_username': self.current_user.lichess_username,
                'training_delay_ms': self.current_user.training_delay_ms,
                'error_display_delay_ms': getattr(self.current_user, 'error_display_delay_ms', 1000)
            }
            self.settings_tab.load_settings(user_settings)
        except Exception as e:
            logger.error(f"初始化主視窗時發生錯誤: {e}")
            QtWidgets.QMessageBox.critical(self, "錯誤", f"初始化應用程式失敗: {str(e)}")

    def _get_or_create_user(self):
        user = self.db_session.query(User).first()
        if not user:
            user = User(username="default_user", lichess_username="", training_delay_ms=500)
            self.db_session.add(user)
            self.db_session.commit()
            self.db_session.refresh(user)
        return user
    
    def analyze_daily_performance(self):
        time_range = self.performance_tab.time_combo.currentText()
        try:
            # 重新從資料庫查詢 user 資料，避免 DetachedInstanceError
            user = self.db_session.query(User).filter_by(username=self.username).first()
            if not user:
                QtWidgets.QMessageBox.critical(self, "錯誤", "無法找到用戶資料，請重新啟動應用。")
                return
                
            lichess_username = user.lichess_username
            if not lichess_username:
                QtWidgets.QMessageBox.warning(self, "錯誤", "請先在'設定'中填寫 Lichess 用戶名。")
                return
                
            self.performance_tab.set_status(f"正在從 Lichess 獲取{time_range}對局並分析...")
            QtWidgets.QApplication.processEvents()
            
            # 使用重新查詢的 user.id 而非 self.current_user.id
            self.daily_analyzer = DailyPerformanceAnalyzer(lichess_username, user.id, self.db_session, self.opening_manager)
            
            # 直接呼叫核心分析主流程
            all_results = self.daily_analyzer.analyze_performance(
                time_range=time_range
            )
            
            # 獲取本次分析批次的所有錯題
            batch_time = self.daily_analyzer.analysis_batch_time
            if batch_time:
                self.last_analysis_mistakes = self.db_session.query(Mistake).filter(
                    Mistake.last_missed_at == batch_time,
                    Mistake.user_id == user.id
                ).all()
                
                # 更新結果中的錯題數量
                all_results['mistakes'] = self.last_analysis_mistakes
            else:
                self.last_analysis_mistakes = all_results.get("mistakes", [])
                
            # 記錄實際錯題數量
            logger.info(f"分析完成，找到 {len(self.last_analysis_mistakes)} 個錯題")
            
            self.performance_tab.set_analysis_results(all_results)
        except Exception as e:
            logger.error(f"分析{time_range}表現時發生錯誤: {e}")
            self.performance_tab.set_status(f"分析失敗: {str(e)}")
        finally:
            if hasattr(self, 'daily_analyzer') and self.daily_analyzer:
                try:
                    self.daily_analyzer.close()
                except Exception as e:
                    logger.error(f"關閉 daily_analyzer 時發生錯誤: {e}")

    def start_today_review(self):
        """開始複習今日錯題"""
        try:
            # 重新從資料庫查詢 user 資料，避免 DetachedInstanceError
            user = self.db_session.query(User).filter_by(username=self.username).first()
            if not user:
                QtWidgets.QMessageBox.critical(self, "錯誤", "無法找到用戶資料，請重新啟動應用。")
                return
                
            # 優先用本次分析的錯題
            if hasattr(self, 'last_analysis_mistakes') and self.last_analysis_mistakes:
                today_mistakes = self.last_analysis_mistakes
            else:
                if not hasattr(self, 'daily_analyzer') or not self.daily_analyzer:
                    lichess_username = user.lichess_username
                    if not lichess_username:
                        QtWidgets.QMessageBox.warning(self, "錯誤", "請先設置 Lichess 用戶名。")
                        return
                    # 使用重新查詢的 user.id
                    self.daily_analyzer = DailyPerformanceAnalyzer(lichess_username, user.id, self.db_session, self.opening_manager)
                today_mistakes = self.daily_analyzer.get_today_mistakes()
                
            if not today_mistakes:
                QtWidgets.QMessageBox.information(self, "提示", "今天沒有找到需要複習的錯題。")
                return
            
            self.tab_widget.setCurrentWidget(self.review_tab)
            # 將 today_mistakes 傳遞給 start_review_session
            self.start_review_session(today_mistakes)
        except Exception as e:
            logger.error(f"啟動今日複習時發生錯誤: {e}")
            QtWidgets.QMessageBox.critical(self, "錯誤", f"啟動複習失敗: {str(e)}")

    def start_review_session(self, mistakes=None):
        """開始複習會話"""
        self.training_session = None
        self.tab_widget.setCurrentWidget(self.review_tab)
        
        # 重新從資料庫查詢 user 物件，避免 DetachedInstanceError
        try:
            # 直接獲取 user_id，避免使用 self.current_user
            user = self.db_session.query(User).filter_by(username=self.username).first()
            if not user:
                QtWidgets.QMessageBox.critical(self, "錯誤", "無法找到用戶資料，請重新啟動應用。")
                return
                
            # 過濾掉 opening_id 找不到的錯題
            valid_opening_ids = set(op.db_model.id for op in self.opening_manager.openings)
            filtered_mistakes = None
            if mistakes:
                filtered_mistakes = [m for m in mistakes if getattr(m, 'opening_id', None) in valid_opening_ids]
            else:
                # 使用所有錯題，直接使用 user.id
                all_mistakes = self.db_session.query(Mistake).filter_by(user_id=user.id).order_by(Mistake.miss_count.desc()).all()
                filtered_mistakes = [m for m in all_mistakes if getattr(m, 'opening_id', None) in valid_opening_ids]
            if not filtered_mistakes:
                QtWidgets.QMessageBox.information(self, "提示", "沒有可複習的錯題，請確認開局庫未被刪除。")
                return
                
            # 直接使用 user.id
            self.review_session = ReviewSession(user.id, custom_mistakes=filtered_mistakes)
            self.review_session.state_changed.connect(self.on_review_state_changed)
            self.review_session.review_finished.connect(self.on_review_finished)
            self.review_session.feedback_provided.connect(self.on_review_feedback)
            self.review_session.start()
        except Exception as e:
            logger.error(f"啟動複習會話時發生錯誤: {e}")
            QtWidgets.QMessageBox.critical(self, "錯誤", f"啟動複習失敗: {str(e)}")

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
        self.tab_widget.addTab(self.performance_tab, "實戰表現")
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
        self.performance_tab.start_review_requested.connect(self.start_today_review)
        self.review_tab.start_review_requested.connect(self.start_review_session)
        self.performance_tab.review_button.clicked.disconnect()
        self.performance_tab.review_button.clicked.connect(self.start_performance_review)
        self.tab_widget.currentChanged.connect(self.on_tab_changed)

    def update_all_lists(self):
        names = self.opening_manager.get_all_opening_names()
        self.training_tab.update_opening_list(names)
        # 新增：傳遞 Opening 物件列表給 management_tab
        self.management_tab.update_opening_list(self.opening_manager.openings)
        
    def add_new_opening(self, name: str, file_path: str, color):
        if name and file_path:
            if self.opening_manager.add_opening(name, file_path, color):
                QtWidgets.QMessageBox.information(self, "成功", f"開局 '{name}' 已匯入。")
                self.update_all_lists()
            else:
                QtWidgets.QMessageBox.critical(self, "錯誤", f"無法匯入 PGN: {file_path}")
                
    def _parse_name_and_side(self, display_name):
        import re
        m = re.match(r"(.+?)（([白黑])）", display_name)
        if m:
            name, color_str = m.group(1), m.group(2)
            side = chess.WHITE if color_str == '白' else chess.BLACK
            return name, side
        return display_name, None

    def remove_opening(self, display_name: str):
        name, side = self._parse_name_and_side(display_name)
        if side is not None and self.opening_manager.get_opening_by_name_and_side(name, side):
            if self.opening_manager.remove_opening(name, side):
                QtWidgets.QMessageBox.information(self, "成功", f"開局 '{display_name}' 已被移除。")
                self.update_all_lists()
            else:
                QtWidgets.QMessageBox.critical(self, "錯誤", f"移除開局 '{display_name}' 失敗。")
        else:
            QtWidgets.QMessageBox.critical(self, "錯誤", f"找不到對應的開局庫。")
            
    def save_user_settings(self, settings: dict):
        try:
            # 重新從資料庫查詢 user 資料，避免 DetachedInstanceError
            user = self.db_session.query(User).filter_by(username=self.username).first()
            if not user:
                QtWidgets.QMessageBox.critical(self, "錯誤", "無法找到用戶資料，請重新啟動應用。")
                return
                
            user.lichess_username = settings["lichess_username"]
            user.training_delay_ms = settings["training_delay_ms"]
            user.error_display_delay_ms = settings["error_display_delay_ms"]
            self.db_session.commit()
            
            # 更新 self.current_user 引用和本地變數
            self.current_user = user
            self.username = user.username
            self.user_id = user.id
            
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
        elif hasattr(self, 'performance_review_session') and self.performance_review_session and current_tab == self.performance_tab:
            self.performance_review_session.handle_user_move(move)
            
    def start_new_line(self, display_name):
        try:
            # 重新從資料庫查詢 user 資料，避免 DetachedInstanceError
            user = self.db_session.query(User).filter_by(username=self.username).first()
            if not user:
                QtWidgets.QMessageBox.critical(self, "錯誤", "無法找到用戶資料，請重新啟動應用。")
                return
                
            name, side = self._parse_name_and_side(display_name)
            opening = self.opening_manager.get_opening_by_name_and_side(name, side)
            if not opening: 
                QtWidgets.QMessageBox.warning(self, "錯誤", "找不到對應的開局庫。")
                return
                
            self.review_session = None
            computer_move_delay = user.training_delay_ms
            error_display_delay = getattr(user, 'error_display_delay_ms', 1000)
            player_color = opening.side if opening.side is not None else chess.WHITE
            self.training_session = TrainingSession(opening, player_color, computer_move_delay, error_display_delay)
            self.training_session.state_changed.connect(self.on_board_update)
            self.training_session.info_updated.connect(self.training_tab.info_label.setText)
            self.training_session.mistake_made.connect(self.on_mistake_made)
            self.training_session.progress_changed.connect(self.training_tab.update_progress)
            self.chessboard.set_flipped(player_color == chess.BLACK)
            self.chessboard.allow_user_input = True
            self.training_tab.hint_button.setEnabled(True)
            self.training_session.start_new_line()
        except Exception as e:
            logger.error(f"開始新訓練時發生錯誤: {e}")
            QtWidgets.QMessageBox.critical(self, "錯誤", f"開始訓練失敗: {str(e)}")
        
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
        
        try:
            # 直接獲取 user_id，避免使用 self.current_user
            user = self.db_session.query(User).filter_by(username=self.username).first()
            if not user:
                logger.error("無法找到用戶資料，錯誤將不會被記錄。")
                return
                
            existing_mistake = self.db_session.query(Mistake).filter_by(fen=fen, user_id=user.id).first()
            if existing_mistake:
                existing_mistake.miss_count += 1
            else:
                new_mistake = Mistake(
                    fen=fen, 
                    correct_move_uci=expected_move.uci(), 
                    user_id=user.id, 
                    opening_id=self.training_session.opening.db_model.id
                )
                self.db_session.add(new_mistake)
            self.db_session.commit()
        except Exception as e:
            logger.error(f"記錄錯誤時發生問題: {e}")
            self.db_session.rollback()
        
    def show_hint(self):
        if self.training_session and self.tab_widget.currentWidget() == self.training_tab:
            hint_move = self.training_session.get_hint()
            if hint_move:
                self.training_tab.info_label.setText(f"提示: {hint_move.uci()}")
                self.chessboard.highlight_move(hint_move, self.chessboard.COLORS["hint_from"], self.chessboard.COLORS["hint_to"])

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
            try:
                # 嘗試解析正確的移動
                correct_move = self.review_session.board.parse_san(correct_move_san)
                self.chessboard.highlight_move(correct_move, self.chessboard.COLORS["hint_from"], self.chessboard.COLORS["hint_to"])
            except chess.IllegalMoveError as e:
                # 如果 SAN 解析失敗，嘗試使用 UCI 格式
                logger.warning(f"無法解析 SAN 記譜法 '{correct_move_san}': {e}")
                try:
                    # 從錯題記錄中獲取 UCI 格式的移動
                    current_mistake = self.review_session.mistakes_queue[0] if self.review_session.mistakes_queue else None
                    if current_mistake:
                        correct_move = chess.Move.from_uci(current_mistake.correct_move_uci)
                        self.chessboard.highlight_move(correct_move, self.chessboard.COLORS["hint_from"], self.chessboard.COLORS["hint_to"])
                except Exception as uci_error:
                    logger.error(f"無法解析 UCI 移動: {uci_error}")
                    # 如果都失敗了，至少顯示文字提示
                    self.review_tab.info_label.setText(f"正確移動: {correct_move_san}")
            except Exception as e:
                logger.error(f"處理複習反饋時發生錯誤: {e}")
                self.review_tab.info_label.setText(f"正確移動: {correct_move_san}")
            
    def on_review_finished(self, status: str):
        message = "恭喜！所有錯題都已複習完畢。" if status == "completed" else "太棒了！資料庫中沒有錯題記錄。"
        self.review_tab.status_label.setText(message)
        self.review_tab.info_label.setText("")
        self.review_session = None
        
    def start_performance_review(self):
        if not hasattr(self, 'last_analysis_mistakes') or not self.last_analysis_mistakes:
            QtWidgets.QMessageBox.information(self, "提示", "請先分析並確保有錯題。")
            return
        
        try:
            # 重新從資料庫查詢 user 資料，避免 DetachedInstanceError
            user = self.db_session.query(User).filter_by(username=self.username).first()
            if not user:
                QtWidgets.QMessageBox.critical(self, "錯誤", "無法找到用戶資料，請重新啟動應用。")
                return
            
            # 直接使用所有錯題，不再按開局過濾
            # 記錄實際錯題數量
            logger.info(f"開始複習，錯題數量: {len(self.last_analysis_mistakes)}")
            
            # 確保所有錯題都能被複習
            self.performance_review_session = ReviewSession(user.id, custom_mistakes=self.last_analysis_mistakes)
            self.performance_review_session.state_changed.connect(self.on_performance_review_state_changed)
            self.performance_review_session.review_finished.connect(self.on_performance_review_finished)
            self.performance_review_session.feedback_provided.connect(self.on_performance_review_feedback)
            
            # 顯示複習面板
            self.performance_tab.show_review_panel(True)
            self.performance_review_session.start()
            
            # 記錄日誌
            logger.info(f"複習會話已啟動，錯題數量: {len(self.performance_review_session.mistakes_queue)}")
        except Exception as e:
            logger.error(f"啟動表現複習時發生錯誤: {e}")
            QtWidgets.QMessageBox.critical(self, "錯誤", f"啟動複習失敗: {str(e)}")

    def on_performance_review_state_changed(self, board, remaining, total):
        self.chessboard.set_board(board)
        self.chessboard.clear_highlights()
        self.performance_tab.update_review_status(remaining, total)
        self.performance_tab.reset_review_feedback()
        self.chessboard.set_flipped(board.turn == chess.BLACK)
        self.chessboard.allow_user_input = True
        # 狀態標籤樣式與錯題分析一致
        self.performance_tab.review_status_label.setStyleSheet("")
        if remaining > 0:
            self.performance_tab.review_status_label.setText(f"剩餘錯題：{remaining} / {total}")
        else:
            self.performance_tab.review_status_label.setText("")

    def on_performance_review_feedback(self, is_correct, correct_move_san):
        self.chessboard.allow_user_input = False
        if not is_correct:
            try:
                correct_move = self.performance_review_session.board.parse_san(correct_move_san)
                self.chessboard.highlight_move(correct_move, self.chessboard.COLORS["hint_from"], self.chessboard.COLORS["hint_to"])
            except Exception:
                self.performance_tab.update_review_info(f"正確走法: {correct_move_san}")
        # 回饋樣式與錯題分析一致
        self.performance_tab.review_info_label.setStyleSheet("")
        self.performance_tab.update_review_info(f"{'答對！' if is_correct else '錯誤！正確走法: ' + correct_move_san}")

    def on_performance_review_finished(self, status: str):
        # 結束訊息樣式與錯題分析一致
        self.performance_tab.review_info_label.setStyleSheet("")
        if status == "completed":
            self.performance_tab.review_status_label.setText("恭喜！所有錯題都已複習完畢。")
        else:
            self.performance_tab.review_status_label.setText("太棒了！資料庫中沒有錯題記錄。")
        self.performance_tab.update_review_status(0, 0)
        self.performance_tab.update_review_info("")
        self.performance_review_session = None

    def closeEvent(self, event: QtGui.QCloseEvent):
        if self.daily_analyzer:
            self.daily_analyzer.close()
        self.db_session.close()
        super().closeEvent(event)