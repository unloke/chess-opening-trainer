## core/progress_tracker.py
from dataclasses import dataclass, asdict
import json
import os
import random
from typing import List

@dataclass
class ProgressData:
    opening_id: str
    line_order: List[int]
    current_line_ptr: int
    ply_index: int
    mistakes: List[dict]  # 每個錯誤儲存 {"line_ptr": int, "ply": int, "move": str}

class ProgressTracker:
    """
    保存並讀取練習進度。
    檔案位置: data/user_data/progress.json
    """
    SAVE_PATH = os.path.join(
        os.path.dirname(__file__), os.pardir, 'data', 'user_data', 'progress.json'
    )

    def __init__(self):
        self._ensure_file()
        self.load()

    def _ensure_file(self):
        folder = os.path.dirname(self.SAVE_PATH)
        os.makedirs(folder, exist_ok=True)
        if not os.path.exists(self.SAVE_PATH):
            # 初始空白資料
            initial = ProgressData('', [], 0, 0, [])
            with open(self.SAVE_PATH, 'w', encoding='utf-8') as f:
                json.dump(asdict(initial), f, ensure_ascii=False, indent=2)

    def load(self) -> ProgressData:
        with open(self.SAVE_PATH, 'r', encoding='utf-8') as f:
            raw = json.load(f)
        self.data = ProgressData(**raw)
        return self.data

    def save(self):
        with open(self.SAVE_PATH, 'w', encoding='utf-8') as f:
            json.dump(asdict(self.data), f, ensure_ascii=False, indent=2)

    def init_opening(self, opening_id: str, num_lines: int):
        """
        新開局時，隨機排列所有路線並重設進度與錯題。
        """
        order = list(range(num_lines))
        random.shuffle(order)
        self.data = ProgressData(
            opening_id=opening_id,
            line_order=order,
            current_line_ptr=0,
            ply_index=0,
            mistakes=[]
        )
        self.save()

    def ensure_opening(self, opening_id: str, num_lines: int):
        """
        若進度檔非對應開局，初始化新開局。
        """
        if self.data.opening_id != opening_id:
            self.init_opening(opening_id, num_lines)

    def record_mistake(self, line_ptr: int, ply: int, move: str):
        """
        記錄一次新的錯誤，避免重複。
        """
        if not any(
            e['line_ptr'] == line_ptr and e['ply'] == ply
            for e in self.data.mistakes
        ):
            self.data.mistakes.append({
                'line_ptr': line_ptr,
                'ply': ply,
                'move': move
            })
            self.save()

    def advance_ply(self):
        """
        當答對當前步，前進一個 ply。
        """
        self.data.ply_index += 1
        self.save()

    def advance_line(self):
        """
        完成一條線後，切換到下一條，重設 ply。
        """
        self.data.current_line_ptr += 1
        self.data.ply_index = 0
        self.save()