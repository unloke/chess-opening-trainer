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
    def find_deviation(self, moves: list[chess.Move], user_color=None):
        """檢查實際走法與開局庫的差異，考慮玩家執棋顏色"""
        # 如果未提供 user_color，則使用開局設定的棋色
        side = user_color if user_color is not None else self.opening.side
        
        if not self.opening.root_node or side is None:
            return None

        board = chess.Board()
        current = self.opening.root_node

        for ply, move in enumerate(moves):
            if board.turn == side:  # 使用玩家棋色
                next_node = self._match_child(current, move)
                if not next_node:                 
                    # 確保返回的節點和移動是有效的
                    if current and current.board().is_valid() and board.is_legal(move):
                        return current, move, ply
                    else:
                        # 如果局面或移動無效，跳過這個偏差
                        continue
                current = next_node
            else:  # 對手走
                opp_node = self._match_child(current, move)
                current = opp_node or current     

            board.push(move)

        return None
