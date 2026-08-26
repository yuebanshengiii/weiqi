import tkinter as tk
from tkinter import messagebox, simpledialog
import pygame
import random
import socket
import threading
import json

# ===== 配置 =====
BOARD_SIZE = 15
CELL_SIZE = 50
MARGIN = 50
WINDOW_SIZE = MARGIN * 2 + BOARD_SIZE * CELL_SIZE

class Goban:
    def __init__(self):
        pygame.mixer.init()
        try:
            self.move_sound = pygame.mixer.Sound("move.wav")
        except:
            print("未找到 move.wav 音效文件，落子将无声")

        self.root = tk.Tk()
        self.root.title("五子棋 - 双人对战模式")
        self.root.resizable(False, False)

        self.canvas = tk.Canvas(
            self.root,
            width=WINDOW_SIZE,
            height=WINDOW_SIZE,
            bg="#DEB887"
        )
        self.canvas.pack()

        self.status_label = tk.Label(
            self.root,
            text="",
            font=("Arial", 14),
            fg="blue"
        )
        self.status_label.pack(pady=(5, 0))

        button_frame = tk.Frame(self.root)
        button_frame.pack(pady=12)

        btn_font = ("Arial", 14)

        self.reset_btn = tk.Button(
            button_frame,
            text="重新开始",
            command=self.reset_game,
            font=btn_font,
            bg="#f0f0f0"
        )
        self.reset_btn.pack(side=tk.LEFT, padx=8)

        self.undo_btn = tk.Button(
            button_frame,
            text="悔棋",
            command=self.undo_move,
            font=btn_font,
            bg="#f0f0f0"
        )
        self.undo_btn.pack(side=tk.LEFT, padx=8)

        self.predict_btn = tk.Button(
            button_frame,
            text="AI预测",
            command=self.ai_predict,
            font=btn_font,
            bg="#e0f0ff"
        )
        self.predict_btn.pack(side=tk.LEFT, padx=8)

        self.ai_mode_btn = tk.Button(
            button_frame,
            text="AI对战",
            command=self.toggle_ai_mode,
            font=btn_font,
            bg="#ffcc99"
        )
        self.ai_mode_btn.pack(side=tk.LEFT, padx=8)

        self.online_btn = tk.Button(
            button_frame,
            text="联机对战",
            command=self.show_online_menu,
            font=btn_font,
            bg="#99ccff"
        )
        self.online_btn.pack(side=tk.LEFT, padx=8)

        # 游戏状态
        self.board = [[0 for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
        self.current_player = 1
        self.game_over = False
        self.move_history = []
        self.predicted_move = None
        self.ai_mode = False
        self.is_ai_thinking = False

        # 联机状态
        self.net_mode = False
        self.is_server = False
        self.black_is_server = True      # 服务端是否执黑
        self.sock = None
        self.conn = None
        self.client_sock = None
        self.net_thread = None
        self.running = True              # 控制接收线程

        self.draw_board()
        self.canvas.bind("<Button-1>", self.on_click)
        self.root.mainloop()

    # ========== 绘制和音效 ==========
    def draw_board(self):
        self.canvas.delete("all")
        # 画网格、边框、星位
        for i in range(BOARD_SIZE):
            x = MARGIN + i * CELL_SIZE
            self.canvas.create_line(x, MARGIN, x, WINDOW_SIZE - MARGIN, fill="black", width=2)
            y = MARGIN + i * CELL_SIZE
            self.canvas.create_line(MARGIN, y, WINDOW_SIZE - MARGIN, y, fill="black", width=2)
        self.canvas.create_rectangle(MARGIN, MARGIN, WINDOW_SIZE-MARGIN, WINDOW_SIZE-MARGIN,
                                     outline="black", width=5)
        for pos in [(7,7),(3,3),(11,3),(3,11),(11,11)]:
            x = MARGIN + pos[0]*CELL_SIZE
            y = MARGIN + pos[1]*CELL_SIZE
            self.canvas.create_oval(x-7, y-7, x+7, y+7, fill="black")

        piece_r = CELL_SIZE//2 - 4
        for r in range(BOARD_SIZE):
            for c in range(BOARD_SIZE):
                if self.board[r][c] == 0:
                    continue
                x = MARGIN + c*CELL_SIZE
                y = MARGIN + r*CELL_SIZE
                color = "black" if self.board[r][c] == 1 else "white"
                self.canvas.create_oval(x-piece_r, y-piece_r, x+piece_r, y+piece_r,
                                        fill=color, outline="gray", width=1)

        # 预测棋子
        if self.predicted_move and not self.net_mode and not self.ai_mode:
            r, c = self.predicted_move
            x = MARGIN + c*CELL_SIZE
            y = MARGIN + r*CELL_SIZE
            fill = "#666" if self.current_player == 1 else "#DDD"
            outline = "#333" if self.current_player == 1 else "#AAA"
            self.canvas.create_oval(x-piece_r, y-piece_r, x+piece_r, y+piece_r,
                                    fill=fill, outline=outline, width=2)
            self.canvas.create_oval(x-6, y-6, x+6, y+6, fill="#888")

    def play_sound(self):
        try:
            self.move_sound.play()
        except:
            pass

    # ========== 联机核心功能（修复重连） ==========
    def show_online_menu(self):
        if self.net_mode:
            self.status_label.config(text="已在联机中", fg="red")
            return
        choice = messagebox.askquestion("联机对战",
                                        "创建房间（作为服务端）？\n点击'是'创建，'否'加入房间")
        if choice == "yes":
            self.start_server()
        else:
            self.join_client()

    def start_server(self):
        self.close_net()                 # 清理残留
        self.running = True              # 重置运行标志
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind(('0.0.0.0', 8888))
            self.sock.listen(1)
            self.sock.settimeout(30)
            self.root.title("五子棋 - 等待连接...")
            self.status_label.config(text="等待对手连接...", fg="red")
            self.root.update()

            self.conn, addr = self.sock.accept()
            self.is_server = True
            self.net_mode = True
            self.root.title("五子棋 - 联机对战")
            self.status_label.config(text=f"联机中 - 服务端 {addr}", fg="blue")

            # 随机先手
            self.black_is_server = random.choice([True, False])
            self.send_message({"type": "init", "black_is_server": self.black_is_server})

            if self.black_is_server:
                self.current_player = 1
                self.status_label.config(text=self.status_label.cget("text") + " (你先手)", fg="blue")
            else:
                self.current_player = 2
                self.status_label.config(text=self.status_label.cget("text") + " (对手先手)", fg="blue")

            self._init_board()           # 清空棋盘
            self.net_thread = threading.Thread(target=self.receive_messages, daemon=True)
            self.net_thread.start()
        except socket.timeout:
            messagebox.showerror("超时", "等待连接超时")
            self.close_net()
        except Exception as e:
            messagebox.showerror("错误", f"创建房间失败：{e}")
            self.close_net()

    def join_client(self):
        self.close_net()
        self.running = True
        ip = simpledialog.askstring("加入房间", "请输入服务端IP地址")
        if not ip:
            return
        try:
            self.client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_sock.connect((ip, 8888))
            self.is_server = False
            self.net_mode = True
            self.root.title("五子棋 - 联机对战")
            self.status_label.config(text="联机中 - 客户端", fg="blue")
            self.net_thread = threading.Thread(target=self.receive_messages, daemon=True)
            self.net_thread.start()
        except Exception as e:
            messagebox.showerror("错误", f"连接失败：{e}")
            self.close_net()

    def close_net(self):
        self.net_mode = False
        self.is_server = False
        self.running = False
        self.status_label.config(text="", fg="blue")
        if self.conn:
            try:
                self.conn.close()
            except:
                pass
            self.conn = None
        if self.sock:
            try:
                self.sock.close()
            except:
                pass
            self.sock = None
        if self.client_sock:
            try:
                self.client_sock.close()
            except:
                pass
            self.client_sock = None
        self.root.title("五子棋 - 双人对战模式")
        self._init_board()

    def _init_board(self):
        self.board = [[0 for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
        self.game_over = False
        self.move_history.clear()
        self.predicted_move = None
        self.is_ai_thinking = False
        self.draw_board()

    def send_message(self, msg_dict):
        data = json.dumps(msg_dict) + "\n"
        try:
            if self.is_server and self.conn:
                self.conn.send(data.encode())
            elif not self.is_server and self.client_sock:
                self.client_sock.send(data.encode())
            else:
                return False
            return True
        except Exception as e:
            print("发送消息错误：", e)
            return False

    def send_move(self, row, col):
        self.send_message({"type": "move", "row": row, "col": col})

    def send_reset(self):
        self.send_message({"type": "reset"})

    def receive_messages(self):
        sock = self.conn if self.is_server else self.client_sock
        buffer = ""
        while self.running and self.net_mode:
            try:
                data = sock.recv(1024).decode()
                if not data:
                    break
                buffer += data
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    if line:
                        self.process_net_message(line)
            except Exception as e:
                print("接收异常：", e)
                break
        # 连接断开
        if self.net_mode:
            self.root.after(0, self.close_net)

    def process_net_message(self, message):
        try:
            data = json.loads(message)
            typ = data.get("type")
            if typ == "init":
                self.black_is_server = data["black_is_server"]
                if not self.is_server:   # 客户端
                    if self.black_is_server:
                        self.current_player = 2
                        self.status_label.config(text="联机中 - 客户端 (对手先手)", fg="blue")
                    else:
                        self.current_player = 1
                        self.status_label.config(text="联机中 - 客户端 (你先手)", fg="blue")
                    self._init_board()
            elif typ == "move":
                row, col = data["row"], data["col"]
                player = 2 if self.is_server else 1
                if self.board[row][col] != 0:
                    return
                self.board[row][col] = player
                self.move_history.append((row, col, player))
                self.play_sound()
                self.current_player = 1 if self.is_server else 2
                self.root.after(0, self.draw_board)
                if self.check_win(row, col, player):
                    winner = "黑棋" if player == 1 else "白棋"
                    self.root.after(0, lambda: self.end_game(winner))
            elif typ == "reset":
                self.root.after(0, self._init_board)
                self.root.after(0, lambda: self.draw_board())
        except Exception as e:
            print("处理消息错误：", e)

    def end_game(self, winner):
        if self.game_over:
            return
        self.game_over = True
        messagebox.showinfo("游戏结束", f"{winner}获胜！")
        self.draw_board()

    # ========== 游戏操作 ==========
    def reset_game(self):
        if self.net_mode:
            self.send_reset()
            self._init_board()
            # 恢复先手
            if self.is_server:
                self.current_player = 1 if self.black_is_server else 2
            else:
                self.current_player = 2 if self.black_is_server else 1
            self.draw_board()
            return
        self._init_board()
        self.current_player = 1
        self.draw_board()

    def on_click(self, event):
        if self.game_over:
            return
        if self.net_mode:
            my_color = 1 if (self.is_server and self.black_is_server) or \
                           (not self.is_server and not self.black_is_server) else 2
            if self.current_player != my_color:
                self.status_label.config(text="请等待对手", fg="red")
                return
        if self.ai_mode and self.current_player != 1:
            return
        if self.is_ai_thinking:
            return

        col = round((event.x - MARGIN) / CELL_SIZE)
        row = round((event.y - MARGIN) / CELL_SIZE)
        if not (0 <= row < BOARD_SIZE and 0 <= col < BOARD_SIZE) or self.board[row][col] != 0:
            return

        self.board[row][col] = self.current_player
        self.move_history.append((row, col, self.current_player))
        self.predicted_move = None
        self.play_sound()
        self.draw_board()

        if self.check_win(row, col, self.current_player):
            winner = "黑棋" if self.current_player == 1 else "白棋"
            if self.ai_mode:
                winner += "（你）" if self.current_player == 1 else "（AI）"
            elif self.net_mode:
                my_color = 1 if (self.is_server and self.black_is_server) or \
                               (not self.is_server and not self.black_is_server) else 2
                winner += "（你）" if self.current_player == my_color else "（对手）"
            self.game_over = True
            messagebox.showinfo("游戏结束", f"{winner}获胜！")
            return

        if self.net_mode:
            self.send_move(row, col)
            self.current_player = 2 if self.current_player == 1 else 1
        else:
            self.current_player = 2 if self.current_player == 1 else 1
            if self.ai_mode and self.current_player == 2:
                self.is_ai_thinking = True
                self.root.after(400, self.ai_move)

    # ========== AI 相关（略，与原代码相同） ==========
    def toggle_ai_mode(self):
        if self.net_mode:
            self.status_label.config(text="联机中不能切换AI", fg="red")
            return
        self.ai_mode = not self.ai_mode
        self.ai_mode_btn.config(text="双人对战" if self.ai_mode else "AI对战",
                                bg="#ff9999" if self.ai_mode else "#ffcc99")
        self.root.title("五子棋 - AI对战模式" if self.ai_mode else "五子棋 - 双人对战模式")
        self.reset_game()

    def undo_move(self):
        if self.ai_mode or self.net_mode:
            self.status_label.config(text="当前模式禁止悔棋", fg="red")
            return
        if not self.move_history:
            self.status_label.config(text="没有可悔的棋", fg="red")
            return
        if self.game_over:
            self.game_over = False
        row, col, player = self.move_history.pop()
        self.board[row][col] = 0
        self.current_player = player
        self.predicted_move = None
        self.draw_board()
        self.status_label.config(text="", fg="blue")

    def check_win(self, row, col, player):
        for dr, dc in [(1,0),(0,1),(1,1),(1,-1)]:
            count = 1
            for sign in (1, -1):
                r, c = row + sign*dr, col + sign*dc
                while 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE and self.board[r][c] == player:
                    count += 1
                    r += sign*dr
                    c += sign*dc
            if count >= 5:
                return True
        return False

    # AI 评分、预测、走法（保持原样，略）
    def evaluate_point(self, row, col, player):
        if self.board[row][col] != 0:
            return 0

        total_score = 0
        directions = [(1, 0), (0, 1), (1, 1), (1, -1)]

        for dr, dc in directions:
            count = 1
            open_left = 0
            open_right = 0

            r, c = row + dr, col + dc
            while 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE and self.board[r][c] == player:
                count += 1
                r += dr
                c += dc
            if 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE and self.board[r][c] == 0:
                open_right = 1

            r, c = row - dr, col - dc
            while 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE and self.board[r][c] == player:
                count += 1
                r -= dr
                c -= dc
            if 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE and self.board[r][c] == 0:
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


    def get_ai_move(self):
        empty = [(r, c) for r in range(BOARD_SIZE) for c in range(BOARD_SIZE) if self.board[r][c] == 0]
        if not empty:
            return None

        opponent = 1 if self.current_player == 2 else 2
        center = BOARD_SIZE // 2

        best_score = -1
        best_move = None

        for r, c in empty:
            if self.evaluate_point(r, c, self.current_player) >= 100000:
                return (r, c)
        for r, c in empty:
            if self.evaluate_point(r, c, opponent) >= 100000:
                return (r, c)

        for r, c in empty:
            attack = self.evaluate_point(r, c, self.current_player)
            defense = self.evaluate_point(r, c, opponent)

            if defense >= 5000:
                defense *= 2.0
            if defense >= 3000:
                defense *= 1.5

            score = attack * 3.0 + defense * 2.0

            dist = abs(r - center) + abs(c - center)
            score += (BOARD_SIZE - dist) * 0.2

            if attack >= 3000 and defense >= 3000:
                score += 2000

            score += random.uniform(-0.5, 0.5)

            if score > best_score:
                best_score = score
                best_move = (r, c)

        return best_move

    def ai_predict(self):
        if self.net_mode:
            messagebox.showinfo("提示", "联机模式下无法使用AI预测")
            return
        if self.game_over:
            messagebox.showinfo("提示", "游戏已结束，请重新开始")
            return
        if len(self.move_history) == BOARD_SIZE * BOARD_SIZE:
            messagebox.showinfo("提示", "棋盘已满，无法预测")
            return

        move = self.get_ai_move()
        if move is None:
            messagebox.showinfo("提示", "没有可落子的位置")
            return

        self.predicted_move = move
        self.draw_board()

    def ai_move(self):
        if self.game_over or self.ai_mode == False:
            self.is_ai_thinking = False
            return
        if self.current_player != 2:
            self.is_ai_thinking = False
            return

        move = self.get_ai_move()
        if move is None:
            self.is_ai_thinking = False
            messagebox.showinfo("提示", "棋盘已满，平局！")
            self.game_over = True
            return

        row, col = move
        self.board[row][col] = 2
        self.move_history.append((row, col, 2))
        self.play_sound()
        self.draw_board()

        if self.check_win(row, col, 2):
            messagebox.showinfo("游戏结束", "白棋（AI）获胜！")
            self.game_over = True
            self.is_ai_thinking = False
            return

        self.current_player = 1
        self.is_ai_thinking = False

if __name__ == "__main__":
    Goban()