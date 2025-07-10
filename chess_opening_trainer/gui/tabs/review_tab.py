# chess_opening_trainer/gui/tabs/review_tab.py
from PyQt5 import QtWidgets, QtCore

class ReviewTab(QtWidgets.QWidget):
    start_review_requested = QtCore.pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.setContentsMargins(15, 15, 15, 15)
        self.layout.setSpacing(10)
        
        self.start_button = QtWidgets.QPushButton("開始錯題複習")
        self.start_button.setFixedHeight(50)
        
        self.status_label = QtWidgets.QLabel("點擊按鈕開始複習您之前犯錯的局面。")
        self.status_label.setAlignment(QtCore.Qt.AlignCenter)
        self.status_label.setWordWrap(True)
        
        self.info_label = QtWidgets.QLabel("")
        self.info_label.setObjectName("infoLabel")
        self.info_label.setAlignment(QtCore.Qt.AlignCenter)
        self.info_label.setWordWrap(True)
        self.info_label.setMinimumHeight(80)
        
        self.layout.addWidget(self.start_button)
        self.layout.addWidget(self.status_label)
        self.layout.addWidget(self.info_label)
        self.layout.addStretch()

        self.start_button.clicked.connect(self.start_review_requested)

    def update_status(self, remaining: int, total: int):
        self.status_label.setText(f"複習進度: {total - remaining + 1} / {total}")

    def show_feedback(self, is_correct: bool, correct_move: str):
        if is_correct:
            self.info_label.setText("正確！")
            self.info_label.setStyleSheet("background-color: #4A7A44;") # Green
        else:
            self.info_label.setText(f"錯誤。正確答案是: {correct_move}")
            self.info_label.setStyleSheet("background-color: #8B0000;") # Dark Red
            
    def reset_feedback_style(self):
        self.info_label.setText("輪到你了...")
        self.info_label.setStyleSheet("") # Reset to default stylesheet