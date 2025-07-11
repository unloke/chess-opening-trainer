from PyQt5 import QtWidgets, QtCore, QtGui
import chess
from datetime import date

TOP_MARGIN = 20          # 內容區域距離 GroupBox 標題的高度
SIDE_MARGIN = 12         # 左右內邊距

class PerformanceTab(QtWidgets.QWidget):
    analyze_requested = QtCore.pyqtSignal()
    start_review_requested = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.setContentsMargins(15, 15, 15, 15)
        self.layout.setSpacing(12)                       # 調回較寬距離，避免群組緊貼
        
        # 頂部標籤：顯示日期
        self.date_label = QtWidgets.QLabel(f"日期: {date.today().strftime('%Y-%m-%d')}")
        self.date_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        self.layout.addWidget(self.date_label)
        
        # 分析設定
        settings_group = QtWidgets.QGroupBox("分析設定")
        settings_layout = QtWidgets.QVBoxLayout(settings_group)
        settings_layout.setContentsMargins(
            SIDE_MARGIN, TOP_MARGIN, SIDE_MARGIN, 12)    # 增加上邊距
        
        # 時間選擇器
        time_layout = QtWidgets.QHBoxLayout()
        time_layout.addWidget(QtWidgets.QLabel("分析時間範圍:"))
        
        self.time_combo = QtWidgets.QComboBox()
        self.time_combo.addItems(["今天", "最近3天", "最近7天", "最近30天"])
        time_layout.addWidget(self.time_combo)
        time_layout.addStretch()
        
        settings_layout.addLayout(time_layout)
        
        self.analyze_button = QtWidgets.QPushButton("分析實戰表現")
        self.analyze_button.setStyleSheet("QPushButton { padding: 8px; font-size: 12px; }")
        settings_layout.addWidget(self.analyze_button)
        
        self.layout.addWidget(settings_group)
        
        # 概覽區域：統計數據
        self.summary_group = QtWidgets.QGroupBox("分析概覽")
        summary_layout = QtWidgets.QVBoxLayout(self.summary_group)
        summary_layout.setContentsMargins(
            SIDE_MARGIN, TOP_MARGIN, SIDE_MARGIN, 12)    # 增加上邊距
        
        # 統計數據
        self.stats_widget = QtWidgets.QWidget()
        stats_layout = QtWidgets.QGridLayout(self.stats_widget)
        
        self.total_games_label = QtWidgets.QLabel("總對局數: 0")
        self.user_games_label = QtWidgets.QLabel("您的對局: 0")
        self.deviations_label = QtWidgets.QLabel("發現偏差: 0")
        self.mistakes_saved_label = QtWidgets.QLabel("保存錯題: 0")
        
        stats_layout.addWidget(self.total_games_label, 0, 0)
        stats_layout.addWidget(self.user_games_label, 0, 1)
        stats_layout.addWidget(self.deviations_label, 1, 0)
        stats_layout.addWidget(self.mistakes_saved_label, 1, 1)
        
        summary_layout.addWidget(self.stats_widget)
        
        # 複習按鈕
        self.review_button = QtWidgets.QPushButton("開始複習分析錯題")
        self.review_button.setEnabled(False)
        self.review_button.setStyleSheet("QPushButton { padding: 8px; font-size: 12px; background-color: #4CAF50; color: white; }")
        summary_layout.addWidget(self.review_button)
        
        self.layout.addWidget(self.summary_group)
        
        # 分析結果
        results_group = QtWidgets.QGroupBox("分析結果")
        results_layout = QtWidgets.QVBoxLayout(results_group)
        results_layout.setContentsMargins(
            SIDE_MARGIN, TOP_MARGIN, SIDE_MARGIN, 12)    # 增加上邊距
        
        self.results_text = QtWidgets.QTextEdit()
        self.results_text.setReadOnly(True)
        self.results_text.setPlaceholderText("點擊分析按鈕獲取結果...")
        self.results_text.setMaximumHeight(150)
        results_layout.addWidget(self.results_text)
        
        self.layout.addWidget(results_group)
        
        # 新增：偏差詳情區域
        deviations_group = QtWidgets.QGroupBox("偏差詳情")
        deviations_layout = QtWidgets.QVBoxLayout(deviations_group)
        deviations_layout.setContentsMargins(
            SIDE_MARGIN, TOP_MARGIN, SIDE_MARGIN, 12)
            
        # 開局選擇器
        opening_layout = QtWidgets.QHBoxLayout()
        opening_layout.addWidget(QtWidgets.QLabel("選擇開局:"))
        
        self.opening_combo = QtWidgets.QComboBox()
        self.opening_combo.addItem("所有開局")
        opening_layout.addWidget(self.opening_combo)
        opening_layout.addStretch()
        
        deviations_layout.addLayout(opening_layout)
        
        # 偏差詳情表格
        self.deviations_table = QtWidgets.QTableWidget()
        self.deviations_table.setColumnCount(5)
        self.deviations_table.setHorizontalHeaderLabels(["對局", "開局", "回合", "您的走法", "正確走法"])
        self.deviations_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.deviations_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.deviations_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.deviations_table.setAlternatingRowColors(True)
        deviations_layout.addWidget(self.deviations_table)
        
        # 詳細信息區域
        self.detail_text = QtWidgets.QTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setMaximumHeight(100)
        self.detail_text.setPlaceholderText("選擇一行查看詳細信息...")
        deviations_layout.addWidget(self.detail_text)
        
        self.layout.addWidget(deviations_group)

        # --- 本次分析錯題複習區塊 ---
        self.review_group = QtWidgets.QGroupBox("本次分析錯題複習")
        self.review_group.setVisible(False)
        review_layout = QtWidgets.QVBoxLayout(self.review_group)
        self.review_status_label = QtWidgets.QLabel("")
        self.review_info_label = QtWidgets.QLabel("")
        self.review_info_label.setWordWrap(True)
        review_layout.addWidget(self.review_status_label)
        review_layout.addWidget(self.review_info_label)
        self.layout.addWidget(self.review_group)

        self.analyze_button.clicked.connect(self.analyze_requested)
        self.review_button.clicked.connect(self.start_review_requested)
        self.opening_combo.currentIndexChanged.connect(self.filter_deviations_by_opening)
        self.deviations_table.itemSelectionChanged.connect(self.show_deviation_details)
        
        # 初始化狀態
        self.today_mistakes_count = 0
        self.deviation_details = []
        self.deviation_by_opening = {}
        
    def set_analysis_results(self, results: dict):
        """設置分析結果"""
        self.results_text.clear()
        
        # 更新統計數據
        total_games = results.get("total_games", 0)
        total_deviations = results.get("total_deviations", 0)
        mistakes = results.get("mistakes", [])
        mistakes_count = len(mistakes)
        
        # 保存偏差詳情
        self.deviation_details = results.get("deviation_details", [])
        self.deviation_by_opening = results.get("deviation_by_opening", {})
        
        # 確保偏差數量與錯題數量一致
        if mistakes_count > total_deviations:
            total_deviations = mistakes_count
        
        self.total_games_label.setText(f"總對局數: {total_games}")
        self.user_games_label.setText(f"您的對局: {total_games}")  # 所有都是用戶的對局
        self.deviations_label.setText(f"發現偏差: {total_deviations}")
        self.mistakes_saved_label.setText(f"保存錯題: {mistakes_count}")
        
        # 更新複習按鈕狀態
        self.today_mistakes_count = mistakes_count
        self.review_button.setEnabled(mistakes_count > 0)
        
        # 顯示結果訊息
        if total_games == 0:
            message = "未找到任何對局，請確認 Lichess 用戶名是否正確。"
        elif total_deviations == 0:
            message = f"分析了 {total_games} 盤對局，未發現偏差。"
        else:
            message = f"分析了 {total_games} 盤對局，發現 {total_deviations} 處偏差，保存了 {mistakes_count} 個錯題。"
        
        self.results_text.setText(message)
        
        # 更新開局選擇器
        self.opening_combo.clear()
        self.opening_combo.addItem("所有開局")
        for opening_name in self.deviation_by_opening.keys():
            self.opening_combo.addItem(opening_name)
            
        # 顯示所有偏差
        self.populate_deviations_table(self.deviation_details)
        
        # 根據結果設置按鈕樣式
        if mistakes_count > 0:
            self.review_button.setStyleSheet(
                "QPushButton { padding: 8px; font-size: 12px; background-color: #4CAF50; color: white; }"
            )
        else:
            self.review_button.setStyleSheet(
                "QPushButton { padding: 8px; font-size: 12px; background-color: #cccccc; color: #666666; }"
            )
            
    def populate_deviations_table(self, deviations):
        """填充偏差表格"""
        self.deviations_table.setRowCount(0)
        
        for i, deviation in enumerate(deviations):
            self.deviations_table.insertRow(i)
            
            # 對局信息
            game_info = deviation.get('game', {})
            event = game_info.get('event', '未知賽事')
            white = game_info.get('white', '未知白方')
            black = game_info.get('black', '未知黑方')
            game_text = f"{white} vs {black}"
            
            # 開局信息
            opening_name = deviation.get('opening_name', '未知開局')
            side = "白方" if deviation.get('opening_side', 0) == chess.WHITE else "黑方"
            opening_text = f"{opening_name}（{side}）"
            
            # 回合信息
            move_number = deviation.get('move_number', 0)
            position = deviation.get('position', '未知局面')
            move_text = f"{move_number}. {position}"
            
            # 走法信息
            user_move = deviation.get('user_move', '')
            correct_moves = deviation.get('correct_moves', [])
            correct_text = ", ".join(correct_moves) if correct_moves else "無"
            
            # 設置表格單元格
            self.deviations_table.setItem(i, 0, QtWidgets.QTableWidgetItem(game_text))
            self.deviations_table.setItem(i, 1, QtWidgets.QTableWidgetItem(opening_text))
            self.deviations_table.setItem(i, 2, QtWidgets.QTableWidgetItem(str(move_number)))
            self.deviations_table.setItem(i, 3, QtWidgets.QTableWidgetItem(user_move))
            self.deviations_table.setItem(i, 4, QtWidgets.QTableWidgetItem(correct_text))
            
            # 存儲詳細信息的索引
            self.deviations_table.setItem(i, 0, QtWidgets.QTableWidgetItem(game_text))
            self.deviations_table.item(i, 0).setData(QtCore.Qt.UserRole, i)
            
        self.deviations_table.resizeColumnsToContents()
        
    def filter_deviations_by_opening(self):
        """根據選擇的開局過濾偏差"""
        selected_opening = self.opening_combo.currentText()
        
        if selected_opening == "所有開局":
            self.populate_deviations_table(self.deviation_details)
        else:
            filtered_deviations = self.deviation_by_opening.get(selected_opening, [])
            self.populate_deviations_table(filtered_deviations)
            
    def show_deviation_details(self):
        """顯示選中偏差的詳細信息"""
        selected_items = self.deviations_table.selectedItems()
        if not selected_items:
            return
            
        row = selected_items[0].row()
        index = self.deviations_table.item(row, 0).data(QtCore.Qt.UserRole)
        
        if index < 0 or index >= len(self.deviation_details):
            return
            
        deviation = self.deviation_details[index]
        
        # 構建詳細信息文本
        game_info = deviation.get('game', {})
        event = game_info.get('event', '未知賽事')
        white = game_info.get('white', '未知白方')
        black = game_info.get('black', '未知黑方')
        date = game_info.get('date', '未知日期')
        result = game_info.get('result', '*')
        user_color = game_info.get('user_color', '未知方')
        url = game_info.get('url', '')
        
        opening_name = deviation.get('opening_name', '未知開局')
        side = "白方" if deviation.get('opening_side', 0) == chess.WHITE else "黑方"
        
        fen = deviation.get('fen', '')
        user_move = deviation.get('user_move', '')
        correct_moves = deviation.get('correct_moves', [])
        correct_text = ", ".join(correct_moves) if correct_moves else "無"
        
        detail_text = f"對局: {event} ({date})\n"
        detail_text += f"對陣: {white} vs {black} [{result}]\n"
        detail_text += f"您執: {user_color}\n"
        detail_text += f"開局: {opening_name}（{side}）\n"
        detail_text += f"您的走法: {user_move}\n"
        detail_text += f"正確走法: {correct_text}\n"
        
        if url:
            detail_text += f"對局連結: {url}\n"
            
        self.detail_text.setText(detail_text)

    def set_status(self, text: str):
        """設置狀態訊息"""
        self.results_text.setPlaceholderText(text)
        self.results_text.clear()
        
    def get_today_mistakes_count(self) -> int:
        """獲取今日錯題數量"""
        return self.today_mistakes_count

    def show_review_panel(self, show: bool = True):
        self.review_group.setVisible(show)
        if not show:
            self.review_status_label.setText("")
            self.review_info_label.setText("")

    def update_review_status(self, remaining, total):
        self.review_status_label.setText(f"剩餘錯題：{remaining} / {total}")

    def update_review_info(self, text):
        self.review_info_label.setText(text)

    def reset_review_feedback(self):
        self.review_info_label.setStyleSheet("")