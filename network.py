# network.py
import socket
import threading
import json
import time

class NetworkManager:
    def __init__(self, on_message, on_disconnect):
        self.on_message = on_message
        self.on_disconnect = on_disconnect

        self.sock = None
        self.conn = None
        self.client = None
        self.thread = None
        self.running = False
        self.is_server = False
        self.net_mode = False
        self.lock = threading.Lock()

    def start_server(self, port=8888):
        self.close()
        self.running = True
        self.is_server = True
        self.net_mode = True
        # 启动子线程来处理 accept，不阻塞主线程
        self.thread = threading.Thread(target=self._accept_loop, args=(port,), daemon=True)
        self.thread.start()
        return None, True  # 立即返回，不阻塞

    def _accept_loop(self, port):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind(('0.0.0.0', port))
            self.sock.listen(1)
            print("[Network] 服务端线程启动，等待连接...")
            self.conn, addr = self.sock.accept()
            print(f"[Network] 收到连接: {addr}")
            # 通知主程序连接成功
            self.on_message({"type": "connected"})
            # 启动接收线程
            recv_thread = threading.Thread(target=self._receive, daemon=True)
            recv_thread.start()
        except Exception as e:
            print(f"[Network] accept 线程异常: {e}")
            self.on_disconnect()

    def join_server(self, ip, port=8888):
        self.close()
        self.running = True
        self.is_server = False
        self.net_mode = True
        print(f"[Network] 正在连接 {ip}:{port}...")
        try:
            self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client.connect((ip, port))
            print("[Network] socket 连接成功")
            self.thread = threading.Thread(target=self._receive, daemon=True)
            self.thread.start()
            print("[Network] 接收线程已启动")
        except Exception as e:
            print(f"[Network] join_server 异常: {e}")
            self.close()
            raise  # 重新抛出，让上层捕获

    def send(self, data):
        if not self.net_mode:
            return False
        msg = json.dumps(data) + "\n"
        try:
            # 不加锁，因为 send 在子线程中调用，且 Python 的 GIL 保证 socket.send 是原子操作
            sock = self.conn if self.is_server else self.client
            if sock is None:
                return False
            sock.settimeout(3)
            sock.send(msg.encode())
            sock.settimeout(None)
            print(f"[Network] 发送成功: {data}")
            return True
        except socket.timeout:
            print("[Network] 发送超时")
            return False
        except Exception as e:
            print(f"[Network] 发送失败: {e}")
            return False

    def close(self):
        self.net_mode = False
        self.running = False
        with self.lock:
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
            if self.client:
                try:
                    self.client.close()
                except:
                    pass
                self.client = None

    def _receive(self):
        print("[Network] _receive 线程开始")
        sock = self.conn if self.is_server else self.client
        buffer = ""
        print("[Network] 接收线程启动")
        while self.running and self.net_mode:
            try:
                data = sock.recv(4096).decode()
                if not data:
                    print("[Network] 收到空数据，连接关闭")
                    break
                buffer += data
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    if line:
                        print(f"[Network] 收到消息: {line}")  # 调试打印
                        try:
                            msg = json.loads(line)
                            self.on_message(msg)
                        except Exception as e:
                            print(f"[Network] 消息解析失败: {e}")
            except socket.timeout:
                continue
            except Exception as e:
                print(f"[Network] 接收异常: {e}")
                break
        print("[Network] 接收线程结束")
        if self.net_mode:
            self.on_disconnect()