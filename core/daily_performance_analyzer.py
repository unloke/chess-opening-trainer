import datetime
from typing import List, Dict, Optional
import chess
import chess.pgn
from sqlalchemy.orm import Session
import logging

# 假設依賴的服務與模型已正確導入
from ..services.lichess_api import LichessAPI
from .opening_manager import OpeningManager, Opening
from ..database.models import Mistake

logger = logging.getLogger(__name__)

class DailyPerformanceAnalyzer:
    """
    DailyPerformanceAnalyzer 服務類：
    1. 取得 Lichess 對局，與開局庫比對，找出偏差（Mistake）並寫入資料庫。
    2. 支援批次分析與單局分析。
    """
    def __init__(self, lichess_username: str, user_id: int, db_session: Session, opening_manager: OpeningManager):
        self.lichess_username = lichess_username
        self.user_id = user_id
        self.db_session = db_session
        self.opening_manager = opening_manager
        self.analysis_batch_time = None

    def analyze_performance(self, time_range: str = "最近7天") -> Dict:
        """
        主流程：分析指定時間範圍內的所有對局，找出偏差。
        """
        try:
            self.analysis_batch_time = datetime.datetime.utcnow()
            start_time = self._parse_time_range(time_range)
            
            lichess_api = LichessAPI(self.lichess_username)
            games = lichess_api.get_last_games(since=start_time)
            
            if not games:
                logger.info(f"未找到 {time_range} 的對局記錄。")
                return {
                    'total_games': 0,
                    'total_deviations': 0,
                    'mistakes': [],
                    'deviation_details': []  # 新增：偏差詳情列表
                }
                
            total_games = 0
            total_deviations = 0
            all_deviation_details = []  # 新增：收集所有偏差詳情
            
            for game in games:
                try:
                    res = self.analyze_performance_for_game(game)
                    if res:
                        total_games += 1
                        total_deviations += res['deviation_count']
                        # 新增：收集此對局的偏差詳情
                        if 'deviation_details' in res and res['deviation_details']:
                            all_deviation_details.extend(res['deviation_details'])
                except Exception as e:
                    logger.error(f"分析對局時發生錯誤: {e}")
                    
            mistake_objs = self._get_last_analysis_mistakes(self.analysis_batch_time)
            unique_mistakes = self._deduplicate_mistakes(mistake_objs)
            
            # 新增：按開局名稱對偏差詳情進行分組
            deviation_by_opening = {}
            for detail in all_deviation_details:
                opening_name = detail['opening_name']
                if opening_name not in deviation_by_opening:
                    deviation_by_opening[opening_name] = []
                deviation_by_opening[opening_name].append(detail)
            
            logger.info(f"分析完成: {total_games} 盤對局，{total_deviations} 個偏差，{len(unique_mistakes)} 個獨特錯題。")
            
            return {
                'total_games': total_games,
                'total_deviations': total_deviations,
                'mistakes': unique_mistakes,
                'deviation_details': all_deviation_details,  # 新增：所有偏差詳情
                'deviation_by_opening': deviation_by_opening  # 新增：按開局分組的偏差
            }
        except Exception as e:
            logger.error(f"執行表現分析時發生錯誤: {e}")
            return {
                'total_games': 0,
                'total_deviations': 0,
                'mistakes': [],
                'deviation_details': [],  # 新增：空的偏差詳情列表
                'error': str(e)
            }

    def analyze_performance_for_game(self, game: chess.pgn.Game) -> Optional[Dict]:
        """
        分析單一對局，找出所有偏差。
        """
        headers = game.headers
        user_color = None
        if headers.get("White") == self.lichess_username:
            user_color = chess.WHITE  # 0
        elif headers.get("Black") == self.lichess_username:
            user_color = chess.BLACK  # 1
        if user_color is None:
            logger.warning(f"用戶 {self.lichess_username} 未參與此局，跳過。headers={headers}")
            return None
            
        # 確保 user_color 為 int（0=白, 1=黑），與 Opening.side 一致
        user_color = int(user_color)
        
        # 獲取與用戶顏色相符的開局庫
        openings = self.opening_manager.get_openings_by_side(user_color)
        if not openings:
            logger.warning(f"找不到 user_color={user_color} 的開局庫，無法比對。現有開局庫: {[f'{op.name}({op.side})' for op in self.opening_manager.openings]}")
            return {'deviation_count': 0, 'deviation_details': []}
            
        moves = list(game.mainline_moves())
        deviation_count = 0
        deviation_details = []  # 新增：收集此對局的偏差詳情
        
        # 獲取對局基本信息
        game_info = {
            'event': headers.get('Event', '未知賽事'),
            'white': headers.get('White', '未知白方'),
            'black': headers.get('Black', '未知黑方'),
            'date': headers.get('Date', '未知日期'),
            'result': headers.get('Result', '*'),
            'user_color': '白方' if user_color == chess.WHITE else '黑方',
            'url': headers.get('Site', '')
        }
        
        for op in openings:
            logger.info(f"開始比對對局 {headers.get('Event', '')} vs 開局庫 {op.name}({op.side})")
            op_root = op.root_node
            if not op_root:
                logger.warning(f"開局庫 {op.name} 的根節點為空，跳過。")
                continue
                
            op_start_fen = op_root.headers.get("FEN", chess.STARTING_FEN)
            
            # 對齊局面
            board = chess.Board(op_start_fen)
            start_index = self._find_alignment_index(chess.Board(), moves, op_start_fen)
            if start_index is None:
                logger.info(f"開局庫 {op.name}({op.side}) 找不到對齊點，跳過。")
                continue
                
            current_node = op_root
            
            # 從對齊點開始比對
            for idx, move in enumerate(moves[start_index:], start=start_index):
                # 檢查當前是否輪到用戶走棋
                if board.turn == user_color:
                    # 檢查用戶的走法是否符合開局庫
                    child_node = self._find_child_node(current_node, move)
                    if child_node:
                        # 走法正確，更新節點
                        current_node = child_node
                    else:
                        # 找出正確的走法
                        correct_moves = []
                        for child in current_node.variations:
                            if board.is_legal(child.move):
                                correct_moves.append(child.move.uci())
                        
                        if correct_moves:  # 只有在有正確走法時才記錄偏差
                            logger.info(f"發現偏差: fen={board.fen()}，開局庫={op.name}，move={move.uci()}, 正確走法={correct_moves}")
                            
                            # 收集偏差詳情
                            deviation_detail = {
                                'game': game_info,
                                'opening_name': op.name,
                                'opening_side': op.side,
                                'fen': board.fen(),
                                'user_move': move.uci(),
                                'correct_moves': correct_moves,
                                'move_number': board.fullmove_number,
                                'position': self._get_position_description(board)
                            }
                            deviation_details.append(deviation_detail)
                            
                            try:
                                self._save_mistake_from_board(board, current_node, op)
                                deviation_count += 1
                            except Exception as e:
                                logger.error(f"保存偏差時發生錯誤: {e}")
                            
                            # 一盤棋一個開局只記錄一次偏差
                            break
                else:
                    # 對手走棋，檢查是否在開局庫中有對應走法
                    child_node = self._find_child_node(current_node, move)
                    if child_node:
                        # 對手走法在開局庫中，更新節點
                        current_node = child_node
                    else:
                        # 對手脫譜，不算用戶偏差，但記錄日誌
                        logger.info(f"對手在第{board.fullmove_number}回合脫譜: {move.uci()}")
                        break  # 對手脫譜後不再比對
                
                # 更新棋盤
                board.push(move)
                
        return {'deviation_count': deviation_count, 'deviation_details': deviation_details}
        
    def _get_position_description(self, board: chess.Board) -> str:
        """
        根據FEN生成簡短的局面描述。
        """
        try:
            # 獲取當前走子方
            turn = "白方" if board.turn == chess.WHITE else "黑方"
            
            # 獲取棋子數量
            piece_count = {
                'P': len(board.pieces(chess.PAWN, chess.WHITE)),
                'N': len(board.pieces(chess.KNIGHT, chess.WHITE)),
                'B': len(board.pieces(chess.BISHOP, chess.WHITE)),
                'R': len(board.pieces(chess.ROOK, chess.WHITE)),
                'Q': len(board.pieces(chess.QUEEN, chess.WHITE)),
                'K': len(board.pieces(chess.KING, chess.WHITE)),
                'p': len(board.pieces(chess.PAWN, chess.BLACK)),
                'n': len(board.pieces(chess.KNIGHT, chess.BLACK)),
                'b': len(board.pieces(chess.BISHOP, chess.BLACK)),
                'r': len(board.pieces(chess.ROOK, chess.BLACK)),
                'q': len(board.pieces(chess.QUEEN, chess.BLACK)),
                'k': len(board.pieces(chess.KING, chess.BLACK))
            }
            
            # 檢查是否為開局階段
            is_opening = board.fullmove_number <= 15
            phase = "開局階段" if is_opening else "中局/殘局"
            
            return f"{turn}走，{phase}，第{board.fullmove_number}回合"
        except Exception as e:
            logger.error(f"生成局面描述時發生錯誤: {e}")
            return "未知局面"

    def _find_alignment_index(self, board: chess.Board, moves: List[chess.Move], target_fen: str) -> Optional[int]:
        """
        在 moves 中尋找與 target_fen 對齊的起始索引。
        """
        for i in range(len(moves) + 1):
            if board.fen().split(' ')[0] == target_fen.split(' ')[0]:  # 只比較棋子位置，忽略其他狀態
                return i
            if i < len(moves):
                board.push(moves[i])
        return None

    def _find_child_node(self, node: chess.pgn.GameNode, move: chess.Move) -> Optional[chess.pgn.GameNode]:
        """
        在 node 的 variations 中尋找與 move 匹配的子節點。
        """
        for child in node.variations:
            if child.move == move:
                return child
        return None

    def _save_mistake_from_board(self, board: chess.Board, current_node: chess.pgn.GameNode, opening: Opening):
        """
        將偏差寫入資料庫，實現 UPSERT。
        """
        fen = board.fen()
        correct_move_uci = None
        correct_moves = []
        
        # 找出所有正確的走法
        for child in current_node.variations:
            if board.is_legal(child.move):
                correct_moves.append(child.move.uci())
                if not correct_move_uci:  # 保存第一個作為主要正確走法
                    correct_move_uci = child.move.uci()
        
        if not correct_move_uci:
            logger.warning(f"找不到正確走法，跳過保存錯題: {fen}")
            return
            
        logger.info(f"保存錯題: FEN={fen}, 正確走法={correct_move_uci}, 開局={opening.name}")
        
        try:
            # 確保使用 opening.db_model.id 而非 opening.id
            opening_id = opening.db_model.id
            
            mistake = self.db_session.query(Mistake).filter_by(
                fen=fen,
                user_id=self.user_id,
                opening_id=opening_id
            ).first()
            if mistake:
                mistake.miss_count += 1
                mistake.last_missed_at = self.analysis_batch_time
                logger.info(f"更新現有錯題: ID={mistake.id}, 錯誤次數={mistake.miss_count}")
            else:
                mistake = Mistake(
                    fen=fen,
                    correct_move_uci=correct_move_uci,
                    user_id=self.user_id,
                    opening_id=opening_id,
                    miss_count=1,
                    last_missed_at=self.analysis_batch_time
                )
                self.db_session.add(mistake)
                logger.info(f"新增錯題: FEN={fen}, 用戶ID={self.user_id}, 開局ID={opening_id}")
            self.db_session.commit()
        except Exception as e:
            self.db_session.rollback()
            logger.error(f"保存錯題時發生錯誤: {e}")
            raise

    def _get_last_analysis_mistakes(self, batch_time: datetime.datetime) -> List[Mistake]:
        """
        取得本次分析批次產生的所有 Mistake。
        """
        return self.db_session.query(Mistake).filter(
            Mistake.last_missed_at == batch_time,
            Mistake.user_id == self.user_id
        ).all()

    def _deduplicate_mistakes(self, mistakes: List[Mistake]) -> List[Mistake]:
        """
        以 (fen, opening_id) 為 key 去重。
        """
        seen = set()
        unique = []
        for m in mistakes:
            key = (m.fen, m.opening_id)
            if key not in seen:
                seen.add(key)
                unique.append(m)
        return unique

    def _parse_time_range(self, time_range: str) -> datetime.datetime:
        """
        將時間範圍字串轉為 UTC 起始時間。
        """
        now = datetime.datetime.utcnow()
        if time_range == "今天":
            return now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif time_range == "最近7天":
            return now - datetime.timedelta(days=7)
        elif time_range == "最近30天":
            return now - datetime.timedelta(days=30)
        else:
            return now - datetime.timedelta(days=7)

    def close(self):
        self.db_session.close()

    def get_today_mistakes(self) -> List[Mistake]:
        """
        取得今天的錯題，供複習使用。
        """
        try:
            today_start = datetime.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            return self.db_session.query(Mistake).filter(
                Mistake.last_missed_at >= today_start,
                Mistake.user_id == self.user_id
            ).all()
        except Exception as e:
            logger.error(f"獲取今日錯題時發生錯誤: {e}")
            return []
