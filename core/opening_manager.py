# chess_opening_trainer/core/opening_manager.py
import chess
import chess.pgn
import logging
import os
from typing import List, Tuple, Optional
from ..database.models import Opening as OpeningModel
from ..database.database import SessionLocal

logger = logging.getLogger(__name__)

class Opening:
    def __init__(self, db_model: OpeningModel):
        self.db_model = db_model
        self.name = db_model.name
        self.pgn_path = db_model.pgn_path
        self.root_node: Optional[chess.pgn.GameNode] = None
        self.all_lines: List[List[chess.Move]] = []
        # 直接存 int（0/1），確保與 chess.WHITE/chess.BLACK 一致
        self.side = db_model.side if db_model.side in (0, 1) else int(bool(db_model.side))
        self.load_and_parse()

    def set_side(self, side: int):
        self.side = int(side)
        self.db_model.side = int(side)

    def load_and_parse(self):
        try:
            with open(self.pgn_path, 'r', encoding='utf-8') as pgn_file:
                game = chess.pgn.read_game(pgn_file)
                if not game:
                    logger.error(f"無法從 {self.pgn_path} 讀取遊戲。")
                    return
                self.root_node = game
                self._extract_all_lines()
                logger.info(f"成功從 '{self.name}' 載入 {len(self.all_lines)} 條路線。")
        except Exception as e:
            logger.error(f"解析 PGN 檔案 {self.pgn_path} 失敗: {e}")
            self.root_node = None
            self.all_lines = []
            
    def _extract_all_lines(self):
        if not self.root_node: return
        self.all_lines = []
        def recurse(node: chess.pgn.GameNode, current_path: List[chess.Move]):
            if node.is_end():
                if current_path: self.all_lines.append(list(current_path))
                return
            for variation in node.variations:
                current_path.append(variation.move)
                recurse(variation, current_path)
                current_path.pop()
        recurse(self.root_node, [])

class OpeningManager:
    # ... (init, load_openings_for_user, add_opening, get_opening_by_name, get_all_opening_names 保持不變)
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.db = SessionLocal()
        self.openings: List[Opening] = []
        self.load_openings_for_user()

    def load_openings_for_user(self):
        db_openings = self.db.query(OpeningModel).filter(OpeningModel.user_id == self.user_id).all()
        self.openings = [Opening(db_model) for db_model in db_openings]

    def get_opening_by_name_and_side(self, name: str, side: bool) -> Optional[Opening]:
        result = next((op for op in self.openings if op.name == name and op.side == side), None)
        logger.info(f"查找開局庫: {name} side={side}，找到: {result is not None}")
        return result

    def add_opening(self, name: str, pgn_path: str, side: bool) -> Optional['Opening']:
        logger.info(f"嘗試新增開局庫: {name} side={side}")
        if self.get_opening_by_name_and_side(name, side):
            logger.error(f"已存在同名且同色的開局庫: {name}（{'白方' if side else '黑方'}）")
            return None
        new_opening_db = OpeningModel(
            name=name,
            pgn_path=pgn_path,
            user_id=self.user_id,
            side=1 if side else 0  # 白方=1, 黑方=0
        )
        self.db.add(new_opening_db)
        try:
            self.db.commit()
            self.db.refresh(new_opening_db)
            new_opening = Opening(new_opening_db)
            new_opening.set_side(side)
            if not new_opening.all_lines:
                logger.error(f"PGN '{name}' 解析失敗，新增操作已取消。")
                self.db.delete(new_opening_db)
                self.db.commit()
                return None
            self.openings.append(new_opening)
            logger.info(f"已為用戶 {self.user_id} 新增開局庫: {name} ({'白方' if side else '黑方'})")
            return new_opening
        except Exception as e:
            self.db.rollback()
            logger.error(f"新增開局庫時發生資料庫錯誤: {e}")
            return None

    # --- 新增方法 ---
    def remove_opening(self, name: str, side: bool = None) -> bool:
        """從資料庫和記憶體中移除一個開局庫（可指定顏色）。"""
        if side is not None:
            opening_to_remove = self.get_opening_by_name_and_side(name, side)
        else:
            opening_to_remove = self.get_opening_by_name(name)
        if not opening_to_remove:
            logger.warning(f"試圖移除不存在的開局庫: {name}（{side}）")
            return False
        try:
            db_model = opening_to_remove.db_model
            self.db.delete(db_model)
            self.db.commit()
            self.openings.remove(opening_to_remove)
            logger.info(f"成功移除開局庫: {name}（{side}）")
            return True
        except Exception as e:
            self.db.rollback()
            logger.error(f"移除開局庫 '{name}'（{side}）時發生錯誤: {e}")
            return False

    def get_opening_by_name(self, name: str) -> Optional[Opening]:
        return next((op for op in self.openings if op.name == name), None)

    def get_all_opening_names(self) -> List[str]:
        # 回傳名稱（白）/（黑）格式
        result = []
        for op in self.openings:
            color_str = '白' if op.side else '黑'
            result.append(f"{op.name}（{color_str}）")
            logger.info(f"列舉開局庫: {op.name}（{color_str}）")
        return result

    def get_openings_by_side(self, side: bool) -> List[Opening]:
        """取得所有同色（白/黑）的開局庫"""
        return [op for op in self.openings if op.side == side]