from PyQt5 import QtWidgets, QtCore
import chess

class OpeningImportDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("匯入新開局")
        self.layout = QtWidgets.QVBoxLayout(self)

        # 開局名稱
        self.name_layout = QtWidgets.QHBoxLayout()
        self.name_label = QtWidgets.QLabel("開局名稱:")
        self.name_input = QtWidgets.QLineEdit()
        self.name_layout.addWidget(self.name_label)
        self.name_layout.addWidget(self.name_input)
        self.layout.addLayout(self.name_layout)

        # 執棋方選擇
        self.side_layout = QtWidgets.QHBoxLayout()
        self.side_label = QtWidgets.QLabel("執棋方:")
        self.side_combo = QtWidgets.QComboBox()
        self.side_combo.addItems(["持白方", "持黑方"])
        self.side_layout.addWidget(self.side_label)
        self.side_layout.addWidget(self.side_combo)
        self.layout.addLayout(self.side_layout)

        # PGN 檔案路徑
        self.path_layout = QtWidgets.QHBoxLayout()
        self.path_label = QtWidgets.QLabel("PGN 檔案:")
        self.path_input = QtWidgets.QLineEdit()
        self.path_input.setReadOnly(True)
        self.browse_button = QtWidgets.QPushButton("瀏覽...")
        self.path_layout.addWidget(self.path_label)
        self.path_layout.addWidget(self.path_input)
        self.path_layout.addWidget(self.browse_button)
        self.layout.addLayout(self.path_layout)
        
        # 按鈕
        self.button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        self.layout.addWidget(self.button_box)

        # 連接信號
        self.browse_button.clicked.connect(self.browse_file)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

    def browse_file(self):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "選擇 PGN 檔案", "", "PGN Files (*.pgn)"
        )
        if file_path:
            self.path_input.setText(file_path)

    def get_data(self):
        """返回開局名稱、選擇的顏色和檔案路徑"""
        return (
            self.name_input.text(),
            chess.WHITE if self.side_combo.currentIndex() == 0 else chess.BLACK,
            self.path_input.text()
        )