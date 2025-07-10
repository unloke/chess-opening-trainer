# chess_opening_trainer/gui/tabs/management_tab.py
from PyQt5 import QtWidgets, QtCore

class ManagementTab(QtWidgets.QWidget):
    add_opening_requested = QtCore.pyqtSignal()
    remove_opening_requested = QtCore.pyqtSignal(str) # opening_name

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.setContentsMargins(15, 15, 15, 15)
        self.layout.setSpacing(10) # <-- 新增間距

        self.layout.addWidget(QtWidgets.QLabel("我的開局庫:"))
        
        self.list_widget = QtWidgets.QListWidget()
        self.layout.addWidget(self.list_widget, 1) # <-- 讓列表可擴展
        
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.setSpacing(10) # <-- 新增按鈕間距
        self.add_button = QtWidgets.QPushButton("新增開局庫...")
        self.remove_button = QtWidgets.QPushButton("移除選定項")
        button_layout.addWidget(self.add_button)
        button_layout.addWidget(self.remove_button)
        self.layout.addLayout(button_layout)

        # Connect signals
        self.add_button.clicked.connect(self.add_opening_requested)
        self.remove_button.clicked.connect(self._on_remove_opening)

    def _on_remove_opening(self):
        selected_item = self.list_widget.currentItem()
        if selected_item:
            name = selected_item.text()
            # --- 新增確認對話框 ---
            reply = QtWidgets.QMessageBox.question(
                self,
                '確認移除',
                f"您確定要移除 '{name}' 嗎？\n這將同時刪除所有相關的錯題記錄。",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No
            )
            
            if reply == QtWidgets.QMessageBox.Yes:
                self.remove_opening_requested.emit(name)

    def update_opening_list(self, names):
        self.list_widget.clear()
        self.list_widget.addItems(names)