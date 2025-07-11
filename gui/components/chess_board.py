# chess_opening_trainer/gui/components/chess_board.py
# -*- coding: utf-8 -*-
import chess
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt
from typing import Optional, Dict, Tuple, List
from ...config import RESOURCES_DIR
import logging

logger = logging.getLogger(__name__)

class ChessBoardWidget(QtWidgets.QGraphicsView):
    moveMade = QtCore.pyqtSignal(chess.Move)
    
    COLORS = {
        "light_square": QtGui.QColor("#F0D9B5"),
        "dark_square": QtGui.QColor("#B58863"),
        "last_move": QtGui.QColor(255, 255, 0, 100),
        "selected": QtGui.QColor(30, 144, 255, 150),
        "hint_from": QtGui.QColor(144, 238, 144, 100),
        "hint_to": QtGui.QColor(144, 238, 144, 200),
        "deviation_from": QtGui.QColor(255, 99, 71, 100),
        "deviation_to": QtGui.QColor(255, 99, 71, 200),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.board = chess.Board()
        self.square_size = 75.0 # 保持為 float 以進行精確計算
        self.flipped = False
        self.allow_user_input = False
        self.selected_square: Optional[int] = None
        self.highlights: Dict[int, QtGui.QColor] = {}
        
        # 初始載入一次
        self.piece_images = self._load_piece_images()
        
        self.setScene(QtWidgets.QGraphicsScene(self))
        self.setRenderHint(QtGui.QPainter.Antialiasing)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.draw_board()

    def _load_piece_images(self) -> Dict[str, QtGui.QPixmap]:
        images = {}
        img_path = RESOURCES_DIR / "images"
        
        # --- 關鍵修正 ---
        # 確保用於縮放的尺寸是整數
        scaled_size = int(self.square_size)
        if scaled_size <= 0: return {} # 避免無效尺寸

        for color in ['w', 'b']:
            for piece in ['p', 'n', 'b', 'r', 'q', 'k']:
                key = f"{color}{piece.upper()}"
                filename = str(img_path / f"{color}{piece.upper()}.png")
                if QtGui.QImageReader.imageFormat(filename):
                    pixmap = QtGui.QPixmap(filename)
                    # 使用轉換後的整數尺寸
                    images[key] = pixmap.scaled(scaled_size, scaled_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        return images

    def set_board(self, board: chess.Board):
        self.board = board
        self.draw_board()

    def set_flipped(self, flipped: bool):
        if self.flipped != flipped:
            self.flipped = flipped
            self.selected_square = None
            self.draw_board()
    
    def clear_highlights(self):
        self.highlights.clear()
        self.draw_board() # 清除後立即重繪

    def highlight_squares(self, squares_and_colors: List[Tuple[int, QtGui.QColor]]):
        for square, color in squares_and_colors:
            self.highlights[square] = color
        self.draw_board()

    def highlight_move(self, move: chess.Move, from_color: QtGui.QColor, to_color: QtGui.QColor):
        self.highlights.clear() # 先清除舊的高亮
        if self.board.move_stack: # 如果有上一步，也高亮上一步
             last_move = self.board.peek()
             self.highlights[last_move.from_square] = self.COLORS["last_move"]
             self.highlights[last_move.to_square] = self.COLORS["last_move"]
        self.highlights[move.from_square] = from_color
        self.highlights[move.to_square] = to_color
        self.draw_board()

    def draw_board(self):
        self.scene().clear()
        for square in chess.SQUARES:
            file, rank = chess.square_file(square), chess.square_rank(square)
            is_light = (file + rank) % 2 != 0
            base_color = self.COLORS["light_square"] if is_light else self.COLORS["dark_square"]

            x, y = self._get_draw_coords(square)
            rect = QtCore.QRectF(x, y, self.square_size, self.square_size)
            
            brush_color = self.highlights.get(square, base_color)
            self.scene().addRect(rect, QtGui.QPen(Qt.NoPen), QtGui.QBrush(brush_color))

            piece = self.board.piece_at(square)
            if piece:
                key = f"{'w' if piece.color else 'b'}{piece.symbol().upper()}"
                if key in self.piece_images:
                    pixmap_item = self.scene().addPixmap(self.piece_images[key])
                    # 確保圖片和格子對齊
                    pixmap_item.setPos(x, y)
    
    def resizeEvent(self, event: QtGui.QResizeEvent):
        super().resizeEvent(event)
        self.scene().setSceneRect(0, 0, self.width(), self.height())
        new_square_size = min(self.width(), self.height()) / 8.0
        
        # 只有在尺寸變化顯著時才重新加載圖片，以提高性能
        if abs(new_square_size - self.square_size) > 0.1:
            self.square_size = new_square_size
            self.piece_images = self._load_piece_images()
        
        self.draw_board()
    
    def heightForWidth(self, width: int) -> int:
        return width
    
    def _get_draw_coords(self, square: int) -> Tuple[float, float]:
        file, rank = chess.square_file(square), chess.square_rank(square)
        draw_file = 7 - file if self.flipped else file
        draw_rank = rank if self.flipped else 7 - rank
        return draw_file * self.square_size, draw_rank * self.square_size

    def mousePressEvent(self, event: QtGui.QMouseEvent):
        if not self.allow_user_input or event.button() != Qt.LeftButton:
            return

        pos = self.mapToScene(event.pos())
        # 避免除以零的錯誤
        if self.square_size == 0: return
        
        file, rank = int(pos.x() // self.square_size), int(pos.y() // self.square_size)
        
        if not (0 <= file < 8 and 0 <= rank < 8): return

        clicked_file, clicked_rank = (7 - file, rank) if self.flipped else (file, 7 - rank)
        clicked_square = chess.square(clicked_file, clicked_rank)

        piece = self.board.piece_at(clicked_square)

        if self.selected_square is None:
            if piece and piece.color == self.board.turn:
                self.selected_square = clicked_square
                self.clear_highlights()
                if self.board.move_stack:
                    last_move = self.board.peek()
                    self.highlights[last_move.from_square] = self.COLORS["last_move"]
                    self.highlights[last_move.to_square] = self.COLORS["last_move"]
                self.highlights[clicked_square] = self.COLORS["selected"]
                self.draw_board()
        else:
            from_sq, to_sq = self.selected_square, clicked_square
            
            move = chess.Move(from_sq, to_sq)
            if self.board.piece_type_at(from_sq) == chess.PAWN and chess.square_rank(to_sq) in [0, 7]:
                move.promotion = chess.QUEEN

            if move in self.board.legal_moves:
                self.moveMade.emit(move)
            
            self.selected_square = None
            self.clear_highlights()