# D:/services/lichess_api.py 

import logging
import requests
import chess.pgn
from io import StringIO
from datetime import datetime

logger = logging.getLogger(__name__)

class LichessAPI:
    """
    與 Lichess REST API 互動，擷取並解析「標準」西洋棋對局。
    2025-07-09 修正：
        • 改用 application/x-chess-pgn 直接拿純 PGN。
        • 以 chess.pgn.read_game 依序解析，完全排除「棋局黏合」問題。
    """
    BASE_URL = "https://lichess.org/api"

    def __init__(self, username: str, token: str | None = None):
        self.username = username
        # 直接要求純 PGN；避免 NDJSON 造成額外拆解
        self.headers = {"Accept": "application/x-chess-pgn"}
        if token:
            self.headers["Authorization"] = f"Bearer {token}"
        logger.info(f"LichessAPI for user '{username}' initialized.")

    def get_last_games(
        self,
        max_games: int = 50,
        since: datetime | None = None,
        perf_types: list[str] | None = None
    ) -> list[chess.pgn.Game]:
        """
        回傳最近的標準對局清單 (list[chess.pgn.Game]).
        解析流程：
            1. 向 /games/user 取得純 PGN
            2. 用 chess.pgn.read_game 逐局讀取
            3. 僅保留 Variant == "Standard" 的棋局
        """
        params = {
            "max": max_games,
            "pgnInJson": False,
            "clocks": True,
            "moves": True,
        }
        if perf_types:
            params["perfType"] = ",".join(perf_types)
        if since:
            params["since"] = int(since.timestamp() * 1000)

        logger.info(f"Fetching games for '{self.username}' with params: {params}")
        try:
            resp = requests.get(
                f"{self.BASE_URL}/games/user/{self.username}",
                params=params,
                headers=self.headers,
                timeout=30,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Error fetching games from Lichess: {e}")
            return []

        pgn_io = StringIO(resp.text)
        games: list[chess.pgn.Game] = []
        total_parsed = 0

        while True:
            try:
                game = chess.pgn.read_game(pgn_io)
            except Exception as e:
                logger.warning(f"Parsing error, skipping one game: {e}")
                continue  # 嘗試繼續解析下一局

            if game is None:  # EOF
                break

            total_parsed += 1
            variant = game.headers.get("Variant", "Standard").lower()
            if variant != "standard":
                logger.debug(f"skip non-standard ({variant})")
                continue
            games.append(game)

            if len(games) >= max_games:  # 多抓回來也只留需求量
                break

        logger.info(f"Total PGN blocks read: {total_parsed}; Standard games parsed: {len(games)}")
        return games
