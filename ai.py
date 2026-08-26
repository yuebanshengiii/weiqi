# ai.py
import random
from config import BOARD_SIZE

def evaluate_point(board, row, col, player):
    """评估在 (row, col) 下子对 player 的得分"""
    if board[row][col] != 0:
        return 0
    total_score = 0
    directions = [(1, 0), (0, 1), (1, 1), (1, -1)]
    size = BOARD_SIZE
    for dr, dc in directions:
        count = 1
        open_left = 0
        open_right = 0
        r, c = row + dr, col + dc
        while 0 <= r < size and 0 <= c < size and board[r][c] == player:
            count += 1
            r += dr
            c += dc
        if 0 <= r < size and 0 <= c < size and board[r][c] == 0:
            open_right = 1
        r, c = row - dr, col - dc
        while 0 <= r < size and 0 <= c < size and board[r][c] == player:
            count += 1
            r -= dr
            c -= dc
        if 0 <= r < size and 0 <= c < size and board[r][c] == 0:
            open_left = 1

        if count >= 5:
            score = 100000
        elif count == 4:
            if open_left and open_right:
                score = 50000
            elif open_left or open_right:
                score = 5000
            else:
                score = 0
        elif count == 3:
            if open_left and open_right:
                score = 3000
            elif open_left or open_right:
                score = 300
            else:
                score = 0
        elif count == 2:
            if open_left and open_right:
                score = 200
            elif open_left or open_right:
                score = 20
            else:
                score = 0
        elif count == 1:
            score = 10 if (open_left or open_right) else 1
        else:
            score = 0
        total_score += score
    return total_score

def get_ai_move(board, current_player):
    """返回最佳落子位置 (row, col)"""
    size = BOARD_SIZE
    empty = [(r, c) for r in range(size) for c in range(size) if board[r][c] == 0]
    if not empty:
        return None
    opponent = 1 if current_player == 2 else 2
    center = size // 2
    best_score = -1
    best_move = None

    # 直接获胜
    for r, c in empty:
        if evaluate_point(board, r, c, current_player) >= 100000:
            return (r, c)
    # 防守对手必胜
    for r, c in empty:
        if evaluate_point(board, r, c, opponent) >= 100000:
            return (r, c)

    # 综合评分
    for r, c in empty:
        attack = evaluate_point(board, r, c, current_player)
        defense = evaluate_point(board, r, c, opponent)
        if defense >= 5000:
            defense *= 2.0
        if defense >= 3000:
            defense *= 1.5
        score = attack * 3.0 + defense * 2.0
        dist = abs(r - center) + abs(c - center)
        score += (size - dist) * 0.2
        if attack >= 3000 and defense >= 3000:
            score += 2000
        score += random.uniform(-0.5, 0.5)
        if score > best_score:
            best_score = score
            best_move = (r, c)
    return best_move