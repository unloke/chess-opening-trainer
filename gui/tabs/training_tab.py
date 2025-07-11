# chess_opening_trainer/gui/tabs/training_tab.py
from PyQt5 import QtWidgets, QtCore
import chess
from chess_opening_trainer.gui.components.progress_panel import ProgressPanel

TOP_MARGIN = 20          # 內容區域距離 GroupBox 標題的高度
SIDE_MARGIN = 12         # 左右內邊距


class TrainingTab(QtWidgets.QWidget):
    # Signals
    start_training_requested = QtCore.pyqtSignal(str)
    hint_requested = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        # ---------- 整體版面 ----------
        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.setContentsMargins(15, 15, 15, 15)
        self.layout.setSpacing(12)                       # 調回較寬距離，避免群組緊貼

        # ---------- 開局選擇 ----------
        opening_group = QtWidgets.QGroupBox("開局選擇")
        opening_layout = QtWidgets.QVBoxLayout(opening_group)
        opening_layout.setContentsMargins(
            SIDE_MARGIN, TOP_MARGIN, SIDE_MARGIN, 6)     # 關鍵：增加上邊距
        self.opening_combo = QtWidgets.QComboBox()
        opening_layout.addWidget(self.opening_combo)
        self.layout.addWidget(opening_group)

        # ---------- 進度面板 ----------
        self.progress_panel = ProgressPanel()
        self.layout.addWidget(self.progress_panel)

        # ---------- 訓練控制 ----------
        training_group = QtWidgets.QGroupBox("訓練控制")
        training_layout = QtWidgets.QVBoxLayout(training_group)
        training_layout.setContentsMargins(
            SIDE_MARGIN, TOP_MARGIN, SIDE_MARGIN, 12)    # 同樣增加上邊距
        training_layout.setSpacing(8)

        self.start_training_button = QtWidgets.QPushButton("開始 / 下一條路線")
        self.hint_button = QtWidgets.QPushButton("提示")
        self.hint_button.setEnabled(False)

        training_layout.addWidget(self.start_training_button)
        training_layout.addWidget(self.hint_button)
        self.layout.addWidget(training_group)

        # ---------- 資訊區 ----------
        info_group = QtWidgets.QGroupBox("訓練狀態")
        info_layout = QtWidgets.QVBoxLayout(info_group)
        info_layout.setContentsMargins(
            SIDE_MARGIN, TOP_MARGIN, SIDE_MARGIN, 12)    # 增加上邊距
        
        self.info_label = QtWidgets.QLabel("請選擇一個開局庫並開始訓練。")
        self.info_label.setObjectName("infoLabel")
        self.info_label.setAlignment(QtCore.Qt.AlignCenter)
        self.info_label.setWordWrap(True)
        self.info_label.setMinimumHeight(80)
        self.info_label.setStyleSheet("""
            QLabel {
                background-color: #2a2a2a;
                border: 2px solid #4a4a4a;
                border-radius: 8px;
                padding: 12px;
                color: #ffffff;
                font-size: 13px;
                font-weight: 500;
            }
        """)
        info_layout.addWidget(self.info_label)
        self.layout.addWidget(info_group)

        self.layout.addStretch()

        # ---------- Signals ----------
        self.start_training_button.clicked.connect(self._on_start_training)
        self.hint_button.clicked.connect(lambda: self.hint_requested.emit())

    # ----- Slots & helpers ----- #
    def _on_start_training(self):
        opening_name = self.opening_combo.currentText()
        if opening_name:
            self.start_training_requested.emit(opening_name) # 固定使用白方
            self.hint_button.setEnabled(True)

    def update_opening_list(self, names):
        self.opening_combo.clear()
        if names:
            self.opening_combo.addItems(names)
            self.start_training_button.setEnabled(True)
        else:
            self.start_training_button.setEnabled(False)
            self.hint_button.setEnabled(False)
            self.info_label.setText("請先到 '開局庫管理' 分頁匯入一個 PGN。")

    @QtCore.pyqtSlot(int, int, int, int)
    def update_progress(self, line_idx, line_total, step_idx, step_total):
        self.progress_panel.update_progress(line_idx, line_total, step_idx, step_total)
