# chess_opening_trainer/core/game_analyzer.py   (2025-07-09 hot-fix-2)

import chess
from .opening_manager import Opening

class GameAnalyzer:
    """
    比對實際走法與開局庫，找出第一個偏離點。
    改動紀錄
    ----------
    2025-07-09 hot-fix-2
        * 改以 _match_child() 安全取得子節點，完全排除 KeyError。
    """

    def __init__(self, opening: Opening):
        self.opening = opening

    # ---------- 內部工具 ---------- #
    @staticmethod
    def _match_child(node, move):
        """
        回傳與 move 相符的 child node；若找不到則回傳 None。
        不會丟出 KeyError。
        """
        for child in node.variations:
            if child.move == move:
                return child
        return None

    # ---------- 主要流程 ---------- #
    def find_deviation(
        self,
        moves: list[chess.Move],
        user_color: chess.Color,
    ):
        if not self.opening.root_node:
            return None

        board = chess.Board()
        current = self.opening.root_node

        for ply, move in enumerate(moves):
            if board.turn == user_color:
                next_node = self._match_child(current, move)
                if not next_node:                 # ← 偏離點
                    return current, move, ply
                current = next_node
            else:  # 對手走
                opp_node = self._match_child(current, move)
                current = opp_node or current     # 沒找到就停在原節點

            board.push(move)

        return None
