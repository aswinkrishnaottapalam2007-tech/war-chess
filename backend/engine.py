import asyncio
import os
import shutil
import chess.engine

ENGINE_PATH = os.environ.get('STOCKFISH_PATH') or shutil.which('stockfish') or '/usr/games/stockfish'
STRENGTH = {
    'easy': {'skill': 0, 'depth': 3, 'time': 0.08},
    'hard': {'skill': 9, 'depth': 11, 'time': 0.4},
    'extreme': {'skill': 17, 'depth': 18, 'time': 1.2},
    'regret': {'skill': 20, 'depth': 25, 'time': 3.0},
}
slots = asyncio.Semaphore(2)


def calculate(board, difficulty):
    level = STRENGTH[difficulty]
    with chess.engine.SimpleEngine.popen_uci(ENGINE_PATH, timeout=10) as engine:
        engine.configure({'Threads': 1, 'Hash': 64, 'Skill Level': level['skill']})
        result = engine.play(board, chess.engine.Limit(time=level['time'], depth=level['depth']))
        if result.move is None:
            raise RuntimeError('Engine returned no move.')
        return result.move


async def choose_move(board, difficulty):
    async with slots:
        return await asyncio.to_thread(calculate, board, difficulty)