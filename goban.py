import tkinter as tk
from tkinter import messagebox, simpledialog
import pygame
import random
import threading
import json
import os

from config import BOARD_SIZE, CELL_SIZE, MARGIN, WINDOW_SIZE
from ai import evaluate_point, get_ai_move
from network import NetworkManager

IP_FILE = "last_ip.json"

def save_last_ip(ip):
    try:
        with open(IP_FILE, "w") as f:
            json.dump({"ip": ip}, f)
    except:
        pass

def load_last_ip():
    try:
        with open(IP_FILE, "r") as f:
            data = json.load(f)
            return data.get("ip", "")
    except:
        return ""

class Goban:
    def __init__(self):
        pygame.mixer.init()
        import sys
        import os

        def resource_path(relative_path):
            """获取资源的绝对路径，兼容开发环境和打包后的 exe"""
            try:
                # PyInstaller 会把资源解压到 _MEIPASS 临时文件夹
                base_path = sys._MEIPASS
            except AttributeError:
                # 开发环境，直接使用当前目录
                base_path = os.path.abspath(".")
            return os.path.join(base_path, relative_path)

        # 加载音效
        try:
            sound_path = resource_path("move.wav")
            self.move_sound = pygame.mixer.Sound(sound_path)
            print(f"音效文件加载成功: {sound_path}")
        except Exception as e:
            print(f"未找到 move.wav 音效文件，落子将无声，错误: {e}")
            self.move_sound = None

        self.root = tk.Tk()
        self.root.title("五子棋 - 双人对战模式")
        self.root.resizable(False, False)
        self.root.geometry("+0+0")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

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
            font=("Arial", 14, "bold"),
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
        self.black_is_server = True

        self.net = NetworkManager(
            on_message=self.on_net_message,
            on_disconnect=self.on_net_disconnect
        )

        self.draw_board()
        self.canvas.bind("<Button-1>", self.on_click)
        self.root.mainloop()

    # ========== 窗口关闭 ==========
    def on_closing(self):
        self.net.close()
        self.root.destroy()

    # ========== 辅助方法 ==========
    def _get_my_color(self):
        if self.is_server:
            return 1 if self.black_is_server else 2
        else:
            return 2 if self.black_is_server else 1

    def _get_opponent_color(self):
        return 3 - self._get_my_color()

    # ========== 绘制 ==========
    def draw_board(self):
        self.canvas.delete("all")
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

    # ========== 状态更新 ==========
    def _update_status_text(self):
        if self.game_over:
            return
        if not self.net_mode:
            self.status_label.config(text="", fg="blue")
            return

        my_color = self._get_my_color()
        color_name = "黑" if my_color == 1 else "白"
        base = f"你执{color_name}棋"

        if self.current_player == my_color:
            status = "轮到你了"
            color = "green"
        else:
            status = "等待对手落子"
            color = "blue"

        self.status_label.config(text=f"{base} - {status}", fg=color)

    # ========== 联机界面 ==========
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
        self.close_net()
        self.status_label.config(text="正在等待对手连接...", fg="orange")
        self.root.update()
        try:
            # 直接调用，不等待 accept 完成
            self.net.start_server()
            # 等待连接成功的回调
        except Exception as e:
            messagebox.showerror("错误", f"创建房间失败：{e}")
            self.close_net()

    def on_net_message(self, msg):
        print(f"[Goban] 收到网络消息: {msg}")
        self.root.after(0, lambda: self._process_net_message(msg))
    def join_client(self):
        self.close_net()
        last_ip = load_last_ip()
        default_val = last_ip if last_ip else "127.0.0.1:8888"
        addr = simpledialog.askstring("加入房间", "请输入服务端地址 (格式: host:port)", initialvalue=default_val)
        if not addr:
            return
        if ":" in addr:
            host, port_str = addr.rsplit(":", 1)
            try:
                port = int(port_str)
            except:
                port = 8888
        else:
            host = addr
            port = 8888
        save_last_ip(addr)
        print(f"[客户端] 尝试连接 {host}:{port}")
        try:
            self.net.join_server(host, port)
            self.is_server = False
            self.net_mode = True
            self.root.title("五子棋 - 联机对战")
            self.status_label.config(text="联机中 - 客户端", fg="blue")
            print("[客户端] 连接成功，等待 init")
        except Exception as e:
            print(f"[客户端] 连接失败: {e}")
            import traceback
            traceback.print_exc()
            messagebox.showerror("错误", f"连接失败：{e}")
            self.close_net()

    def close_net(self):
        self.net.close()
        self.net_mode = False
        self.is_server = False
        self.game_over = False
        self._update_status_text()
        self.root.title("五子棋 - 双人对战模式")
        self._init_board()

    # ========== 网络回调 ==========
    def on_net_message(self, msg):
        print(f"[Goban] 收到网络消息: {msg}")
        self.root.after(0, lambda: self._process_net_message(msg))

    def _process_net_message(self, msg):
        print(f"[Goban] 处理消息: {msg}")
        typ = msg.get("type")
        
        # ===== 新增：处理 connected 消息 =====
        if typ == "connected":
            # 连接成功，初始化服务端游戏
            self.is_server = True
            self.net_mode = True
            self.root.title("五子棋 - 联机对战")
            # 随机先手
            self.black_is_server = random.choice([True, False])
            # 发送 init 消息给客户端
            self.net.send({"type": "init", "black_is_server": self.black_is_server})
            if self.black_is_server:
                self.current_player = 1
            else:
                self.current_player = 2
            self._update_status_text()
            self._init_board()
            print("[Goban] 服务端初始化完成，等待落子")
            return
        
        elif typ == "init":
            self.black_is_server = msg["black_is_server"]
            if not self.is_server:
                if self.black_is_server:
                    self.current_player = 2
                else:
                    self.current_player = 1
                self._update_status_text()
                self._init_board()
                
        elif typ == "move":
            row, col = msg["row"], msg["col"]
            opponent_color = self._get_opponent_color()
            if self.board[row][col] != 0:
                return
            self.board[row][col] = opponent_color
            self.move_history.append((row, col, opponent_color))
            self.play_sound()
            self.draw_board()
            if msg.get("win", False):
                self.end_game(winner_is_me=False)
                return
            else:
                self.current_player = self._get_my_color()
                self._update_status_text()
                
        elif typ == "reset":
            self._init_board()
            if self.is_server:
                self.current_player = 1 if self.black_is_server else 2
            else:
                self.current_player = 2 if self.black_is_server else 1
            self.game_over = False
            self._update_status_text()
            self.draw_board()

    def on_net_disconnect(self):
        self.root.after(0, self._on_disconnect_gui)

    def _on_disconnect_gui(self):
        self.close_net()
        self.status_label.config(text="对手已断开", fg="red")

    # ========== 游戏逻辑 ==========
    def _init_board(self):
        self.board = [[0 for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
        self.game_over = False
        self.move_history.clear()
        self.predicted_move = None
        self.is_ai_thinking = False
        self.draw_board()

    def reset_game(self):
        if self.net_mode:
            self.net.send({"type": "reset"})
            self._init_board()
            if self.is_server:
                self.current_player = 1 if self.black_is_server else 2
            else:
                self.current_player = 2 if self.black_is_server else 1
            self.game_over = False
            self._update_status_text()
            self.draw_board()
            return
        self._init_board()
        self.current_player = 1
        self.game_over = False
        self._update_status_text()
        self.draw_board()

    # ========== 点击处理 ==========
    def on_click(self, event):
        if self.game_over:
            return
        if self.net_mode:
            my_color = self._get_my_color()
            if self.current_player != my_color:
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
            self.end_game(winner_is_me=True)
            # 发送胜利消息，附带 win 标志
            if self.net_mode:
                self.net.send({"type": "move", "row": row, "col": col, "win": True})
            return

        if self.net_mode:
            if not self.net.send({"type": "move", "row": row, "col": col}):
                self.board[row][col] = 0
                self.move_history.pop()
                self.draw_board()
                messagebox.showerror("错误", "发送走法失败，请检查网络连接")
                return
            self.current_player = self._get_opponent_color()
            self._update_status_text()
        else:
            self.current_player = 2 if self.current_player == 1 else 1
            if self.ai_mode and self.current_player == 2:
                self.is_ai_thinking = True
                self.root.after(400, self.ai_move)

    # ========== 游戏结束处理 ==========
    def end_game(self, winner_is_me):
        if self.game_over:
            return
        self.game_over = True
        self.draw_board()
        if winner_is_me:
            text = "🎉 你赢了！"
            color = "green"
        else:
            text = "😞 你输了"
            color = "red"
        self.status_label.config(text=text, fg=color)
        self.root.update()

    # ========== AI 相关 ==========
    def ai_predict(self):
        if self.net_mode:
            messagebox.showinfo("提示", "联机模式下无法使用AI预测")
            return
        if self.game_over:
            messagebox.showinfo("提示", "游戏已结束")
            return
        if len(self.move_history) == BOARD_SIZE * BOARD_SIZE:
            messagebox.showinfo("提示", "棋盘已满")
            return
        move = get_ai_move(self.board, self.current_player)
        if not move:
            messagebox.showinfo("提示", "无位置")
            return
        self.predicted_move = move
        self.draw_board()

    def ai_move(self):
        if self.game_over or not self.ai_mode:
            self.is_ai_thinking = False
            return
        if self.current_player != 2:
            self.is_ai_thinking = False
            return
        move = get_ai_move(self.board, self.current_player)
        if not move:
            self.is_ai_thinking = False
            self.status_label.config(text="平局！", fg="orange")
            self.game_over = True
            self.draw_board()
            return
        row, col = move
        self.board[row][col] = 2
        self.move_history.append((row, col, 2))
        self.play_sound()
        self.draw_board()
        if self.check_win(row, col, 2):
            self.end_game(winner_is_me=False)
            self.is_ai_thinking = False
            return
        self.current_player = 1
        self.is_ai_thinking = False
        self._update_status_text()

    # ========== 模式切换 ==========
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

    # ========== 胜负判定 ==========
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

if __name__ == "__main__":
    Goban()