from PyQt5 import QtWidgets, QtCore
import chess

class ManagementTab(QtWidgets.QWidget):
    add_opening_requested = QtCore.pyqtSignal(str, str, object)  # name, file_path, color
    remove_opening_requested = QtCore.pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.setContentsMargins(15, 15, 15, 15)
        self.layout.setSpacing(10)

        self.layout.addWidget(QtWidgets.QLabel("我的開局庫:"))
        self.list_widget = QtWidgets.QListWidget()
        self.layout.addWidget(self.list_widget, 1)
        
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.setSpacing(10)
        self.add_button = QtWidgets.QPushButton("新增開局庫...")
        self.remove_button = QtWidgets.QPushButton("移除選定項")
        button_layout.addWidget(self.add_button)
        button_layout.addWidget(self.remove_button)
        self.layout.addLayout(button_layout)

        self.add_button.clicked.connect(self._show_add_dialog)
        self.remove_button.clicked.connect(self._on_remove_opening)

    def _show_add_dialog(self):
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("新增開局庫")
        layout = QtWidgets.QFormLayout(dialog)

        name_input = QtWidgets.QLineEdit()
        layout.addRow("開局名稱:", name_input)

        side_combo = QtWidgets.QComboBox()
        side_combo.addItems(["持白方", "持黑方"])
        side_combo.setCurrentIndex(0)  # 預設選白方
        layout.addRow("執棋方:", side_combo)

        file_button = QtWidgets.QPushButton("選擇 PGN 文件...")
        file_path = [""]  # 使用列表存儲路徑以便在內部函數中修改

        def choose_file():
            path, _ = QtWidgets.QFileDialog.getOpenFileName(
                dialog, "選擇 PGN 文件", "", "PGN 文件 (*.pgn)"
            )
            if path:
                file_path[0] = path
                file_button.setText(path.split("/")[-1])

        file_button.clicked.connect(choose_file)
        layout.addRow("PGN 文件:", file_button)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        layout.addRow(buttons)

        def on_accept():
            if not name_input.text().strip():
                QtWidgets.QMessageBox.warning(dialog, "錯誤", "請輸入開局名稱")
                return
            if not file_path[0]:
                QtWidgets.QMessageBox.warning(dialog, "錯誤", "請選擇 PGN 文件")
                return
            color = chess.WHITE if side_combo.currentIndex() == 0 else chess.BLACK
            print(f"用戶選擇顏色: {'白方' if color == chess.WHITE else '黑方'}")
            self.add_opening_requested.emit(name_input.text(), file_path[0], color)
            dialog.accept()

        buttons.accepted.connect(on_accept)
        buttons.rejected.connect(dialog.reject)
        dialog.exec_()

    def _on_remove_opening(self):
        selected_item = self.list_widget.currentItem()
        if selected_item:
            display_name = selected_item.text()
            reply = QtWidgets.QMessageBox.question(
                self,
                '確認移除',
                f"您確定要移除 '{display_name}' 嗎？\n這將同時刪除所有相關的錯題記錄。",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No
            )
            if reply == QtWidgets.QMessageBox.Yes:
                self.remove_opening_requested.emit(display_name)

    def update_opening_list(self, openings):
        self.list_widget.clear()
        # openings 應為 List[Opening]，顯示名稱+顏色
        for op in openings:
            color_str = '白' if op.side == chess.WHITE else '黑' if op.side == chess.BLACK else '未知'
            self.list_widget.addItem(f"{op.name}（{color_str}）")