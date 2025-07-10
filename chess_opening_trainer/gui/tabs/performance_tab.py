# chess_opening_trainer/gui/tabs/performance_tab.py
from PyQt5 import QtWidgets, QtCore

class PerformanceTab(QtWidgets.QWidget):
    analyze_requested = QtCore.pyqtSignal() # 不再需要傳遞平台名稱

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.setContentsMargins(15, 15, 15, 15)
        self.layout.setSpacing(10)
        
        self.analyze_button = QtWidgets.QPushButton("分析 Lichess 當日對局")
        self.layout.addWidget(self.analyze_button)
        
        self.results_text = QtWidgets.QTextEdit()
        self.results_text.setReadOnly(True)
        self.results_text.setPlaceholderText("點擊按鈕獲取 Lichess 對局分析結果...")
        
        self.layout.addWidget(QtWidgets.QLabel("分析結果:"))
        self.layout.addWidget(self.results_text, 1)

        self.analyze_button.clicked.connect(self.analyze_requested)

    def set_results(self, text: str):
        self.results_text.setText(text)

    def set_status(self, text: str):
        self.results_text.setPlaceholderText(text)
        self.results_text.setText("")