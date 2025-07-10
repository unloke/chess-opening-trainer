# chess_opening_trainer/gui/tabs/settings_tab.py
from PyQt5 import QtWidgets, QtCore

class SettingsTab(QtWidgets.QWidget):
    settings_saved = QtCore.pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.setContentsMargins(15, 15, 15, 15)
        self.layout.setSpacing(20)

        accounts_group = QtWidgets.QGroupBox("平台帳號")
        accounts_layout = QtWidgets.QFormLayout(accounts_group)
        accounts_layout.setSpacing(10)

        self.lichess_user_input = QtWidgets.QLineEdit()
        # self.chesscom_user_input = QtWidgets.QLineEdit() # <-- 移除
        
        accounts_layout.addRow("Lichess 用戶名:", self.lichess_user_input)
        # accounts_layout.addRow("Chess.com 用戶名:", self.chesscom_user_input) # <-- 移除
        
        self.layout.addWidget(accounts_group)

        training_group = QtWidgets.QGroupBox("訓練設定")
        training_layout = QtWidgets.QFormLayout(training_group)
        training_layout.setSpacing(10)

        self.delay_input = QtWidgets.QSpinBox()
        self.delay_input.setRange(0, 5000)
        self.delay_input.setSingleStep(100)
        self.delay_input.setSuffix(" ms")
        
        training_layout.addRow("電腦走棋延遲:", self.delay_input)
        self.layout.addWidget(training_group)
        
        self.layout.addStretch()

        self.save_button = QtWidgets.QPushButton("儲存設定")
        self.save_button.clicked.connect(self._on_save)
        
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.save_button)
        
        self.layout.addLayout(button_layout)

    def load_settings(self, user_data: dict):
        self.lichess_user_input.setText(user_data.get("lichess_username", ""))
        self.delay_input.setValue(user_data.get("training_delay_ms", 500))

    def _on_save(self):
        settings = {
            "lichess_username": self.lichess_user_input.text().strip(),
            "training_delay_ms": self.delay_input.value()
        }
        self.settings_saved.emit(settings)