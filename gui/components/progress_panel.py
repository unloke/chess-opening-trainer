from PyQt5.QtWidgets import QWidget, QLabel, QHBoxLayout, QFrame, QSizePolicy


class ProgressPanel(QWidget):
    """
    常駐顯示目前 [路線進度] 與 [步數進度]。
    """
    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.line_label = QLabel("路線: - / -")
        self.step_label = QLabel("步數: - / -")

        for lbl in (self.line_label, self.step_label):
            lbl.setStyleSheet("color:#DDD; font-size:13px;")
            lbl.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        bar = QFrame()
        bar.setFixedSize(1, 18)
        bar.setStyleSheet("background:#555;")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 2, 0, 2)
        lay.setSpacing(6)
        lay.addWidget(self.line_label)
        lay.addWidget(bar)
        lay.addWidget(self.step_label)
        lay.addStretch()

        # 確保高度固定，避免被其他元件覆蓋
        self.setFixedHeight(24)

    # ---------- 公開 slot ---------- #
    def update_progress(self, line_idx, line_total, step_idx, step_total):
        self.line_label.setText(f"路線: {line_idx} / {line_total}")
        self.step_label.setText(f"步數: {step_idx} / {step_total}")
