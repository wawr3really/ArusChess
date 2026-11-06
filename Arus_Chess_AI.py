import os
import time
import math
import threading
import tkinter as tk
from tkinter import messagebox
import chess
import chess.engine
from selenium import webdriver

# --- НАСТРОЙКИ ---
CHESSCOM_URL = "https://www.chess.com/play/computer"
START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR"

def find_stockfish():
    paths = ["stockfish.exe", "stockfish-windows-x86-64.exe", os.path.join(os.path.dirname(os.path.abspath(__file__)), "stockfish.exe")]
    for p in paths:
        if os.path.exists(p): return p
    return None

class ChessBot:
    def __init__(self, log_callback):
        self.log = log_callback
        self.driver = None
        self.engine = None
        self.running = False
        self.my_color = None
        self.last_pieces = ""
        self.internal_turn = "w"
        self.analyzed_pieces = ""
        self.think_time = 0.5
        self.engine_lock = threading.Lock()

    def init_engine(self):
        with self.engine_lock:
            try:
                if self.engine: 
                    try: self.engine.quit()
                    except: pass
                self.engine = chess.engine.SimpleEngine.popen_uci(find_stockfish())
                self.engine.configure({"Skill Level": 20, "Threads": 2, "Hash": 64}) 
                return True
            except Exception as e:
                self.engine = None
                return False

    def start_browser(self):
        self.log("[*] Запуск браузера...")
        try:
            options = webdriver.ChromeOptions()
            options.add_argument("--start-maximized")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-extensions")
            options.add_argument("--disable-gpu")
            options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
            options.add_experimental_option('useAutomationExtension', False)
            
            profile_dir = os.path.join(os.getcwd(), "chrome_profile")
            options.add_argument(f"user-data-dir={profile_dir}")
            
            self.driver = webdriver.Chrome(options=options)
            self.driver.get(CHESSCOM_URL)
            time.sleep(3)
            self._ensure_overlay()
            return True
        except Exception as e:
            self.log(f"[!] Ошибка браузера: {e}")
            return False

    def _ensure_overlay(self):
        js_script = """
        try {
            if (!document.getElementById('arus-overlay-div')) {
                var div = document.createElement('div');
                div.id = 'arus-overlay-div';
                div.style.position = 'fixed'; div.style.top = '0'; div.style.left = '0';
                div.style.width = '100vw'; div.style.height = '100vh';
                div.style.pointerEvents = 'none'; div.style.zIndex = '2147483645';
                document.body.appendChild(div);
            }
            if (!document.getElementById('arus-overlay-canvas')) {
                var canvas = document.createElement('canvas');
                canvas.id = 'arus-overlay-canvas';
                canvas.style.position = 'fixed'; canvas.style.top = '0'; canvas.style.left = '0';
                canvas.style.width = '100vw'; canvas.style.height = '100vh';
                canvas.style.pointerEvents = 'none'; canvas.style.zIndex = '2147483647';
                document.body.appendChild(canvas);
            }
        } catch(e) {}
        """
        try: self.driver.execute_script(js_script)
        except: pass

    def get_game_state(self):
        js_script = """
        try {
            var board = document.querySelector('chess-board') || document.querySelector('wc-chess-board') || document.querySelector('.board');
            if (!board) return null;
            
            var piecesMap = {'wp':'P','wn':'N','wb':'B','wr':'R','wq':'Q','wk':'K','bp':'p','bn':'n','bb':'b','br':'r','bq':'q','bk':'k'};
            var matrix = Array(8).fill(null).map(() => Array(8).fill(null));
            var pieces = board.querySelectorAll('.piece');
            if (pieces.length < 2) return null; 

            for (var i = 0; i < pieces.length; i++) {
                var p = pieces[i];
                var cls = p.className.split(' ');
                var pieceType = cls.find(c => piecesMap[c]);
                if (pieceType) {
                    var squareCls = cls.find(c => c.startsWith('square-'));
                    if (squareCls) {
                        var coords = squareCls.replace('square-', '');
                        var file = parseInt(coords[0]) - 1;
                        var rank = parseInt(coords[1]) - 1;
                        matrix[7 - rank][file] = piecesMap[pieceType];
                    }
                }
            }
            
            var fen = '';
            for (var r = 0; r < 8; r++) {
                var empty = 0;
                for (var f = 0; f < 8; f++) {
                    if (matrix[r][f]) { if (empty > 0) { fen += empty; empty = 0; } fen += matrix[r][f]; } 
                    else empty++;
                }
                if (empty > 0) fen += empty;
                if (r < 7) fen += '/';
            }
            
            var isFlipped = board.classList.contains('flipped');
            return { pieces: fen, is_flipped: isFlipped };
        } catch(e) { return null; }
        """
        try: return self.driver.execute_script(js_script)
        except: return None

    def draw_arrow_and_esp(self, from_sq, to_sq, win_prob):
        self._ensure_overlay()
        js_script = f"""
        try {{
            var board = document.querySelector('chess-board') || document.querySelector('wc-chess-board') || document.querySelector('.board');
            if (!board) return;
            var canvas = document.getElementById('arus-overlay-canvas');
            var divLayer = document.getElementById('arus-overlay-div');
            if (!canvas || !divLayer) return;

            canvas.width = window.innerWidth; canvas.height = window.innerHeight;
            var ctx = canvas.getContext('2d');
            ctx.clearRect(0, 0, canvas.width, canvas.height);

            var rect = board.getBoundingClientRect();
            var isFlipped = board.classList.contains('flipped');
            var sqSize = rect.width / 8;

            function getCoords(sq) {{
                var file = sq[0].charCodeAt(0) - 97;
                var rank = 8 - parseInt(sq[1]);
                if (isFlipped) {{ file = 7 - file; rank = 7 - rank; }}
                return {{ 
                    x: rect.left + (file * sqSize), y: rect.top + (rank * sqSize),
                    cx: rect.left + (file * sqSize) + (sqSize / 2), cy: rect.top + (rank * sqSize) + (sqSize / 2)
                }};
            }}

            var p1 = getCoords('{from_sq}'); var p2 = getCoords('{to_sq}');
            var headlen = sqSize * 0.4; var angle = Math.atan2(p2.cy - p1.cy, p2.cx - p1.cx);
            
            ctx.shadowColor = '#478df5'; ctx.shadowBlur = 15;
            ctx.beginPath(); ctx.moveTo(p1.cx, p1.cy); ctx.lineTo(p2.cx, p2.cy);
            ctx.strokeStyle = '#478df5'; ctx.lineWidth = sqSize * 0.12; ctx.lineCap = 'round'; ctx.stroke();
            
            ctx.beginPath(); ctx.moveTo(p2.cx, p2.cy);
            ctx.lineTo(p2.cx - headlen * Math.cos(angle - Math.PI / 6), p2.cy - headlen * Math.sin(angle - Math.PI / 6));
            ctx.lineTo(p2.cx - headlen * Math.cos(angle + Math.PI / 6), p2.cy - headlen * Math.sin(angle + Math.PI / 6));
            ctx.closePath(); ctx.fillStyle = '#478df5'; ctx.fill();
            ctx.shadowBlur = 0;
            
            ctx.beginPath(); ctx.arc(p1.cx, p1.cy, sqSize * 0.15, 0, Math.PI * 2); ctx.fillStyle = '#478df5'; ctx.fill();

            var bSize = sqSize * 0.3; 
            var bw = 4;               
            var col = '#478df5';      

            function drawCorners(coord) {{
                return `
                <div class="esp-square" style="position:absolute; left:${{coord.x}}px; top:${{coord.y}}px; width:${{sqSize}}px; height:${{sqSize}}px; box-sizing:border-box; pointer-events: none; background: rgba(71, 141, 245, 0.15); border-radius: 4px;">
                    <div style="position:absolute; top:0; left:0; width:${{bSize}}px; height:${{bSize}}px; border-top:${{bw}}px solid ${{col}}; border-left:${{bw}}px solid ${{col}}; border-radius: 4px 0 0 0;"></div>
                    <div style="position:absolute; top:0; right:0; width:${{bSize}}px; height:${{bSize}}px; border-top:${{bw}}px solid ${{col}}; border-right:${{bw}}px solid ${{col}}; border-radius: 0 4px 0 0;"></div>
                    <div style="position:absolute; bottom:0; left:0; width:${{bSize}}px; height:${{bSize}}px; border-bottom:${{bw}}px solid ${{col}}; border-left:${{bw}}px solid ${{col}}; border-radius: 0 0 0 4px;"></div>
                    <div style="position:absolute; bottom:0; right:0; width:${{bSize}}px; height:${{bSize}}px; border-bottom:${{bw}}px solid ${{col}}; border-right:${{bw}}px solid ${{col}}; border-radius: 0 0 4px 0;"></div>
                </div>`;
            }}

            var olds = divLayer.querySelectorAll('.esp-square, .prob-tag');
            for(var i=0; i<olds.length; i++) olds[i].remove();

            divLayer.insertAdjacentHTML('beforeend', drawCorners(p1) + drawCorners(p2));

            var probDiv = document.createElement('div');
            probDiv.className = 'prob-tag';
            probDiv.style.position = 'absolute'; probDiv.style.left = p2.cx + 'px'; probDiv.style.top = p2.y + 'px';
            probDiv.style.transform = 'translate(-50%, -100%)';
            probDiv.style.background = 'rgba(8, 12, 19, 0.95)'; probDiv.style.color = '#fff';
            probDiv.style.fontFamily = "'Segoe UI', sans-serif"; probDiv.style.fontWeight = 'bold'; probDiv.style.fontSize = '12px';
            probDiv.style.padding = '3px 8px'; probDiv.style.borderRadius = '4px'; probDiv.style.border = '1px solid #478df5';
            probDiv.style.boxShadow = '0 0 10px rgba(71, 141, 245, 0.8)'; probDiv.style.pointerEvents = 'none';
            probDiv.innerText = '{win_prob}%';
            divLayer.appendChild(probDiv);
        }} catch(e) {{}}
        """
        try: self.driver.execute_script(js_script)
        except: pass

    def clear_arrow(self):
        try:
            self.driver.execute_script("""
                try {
                    var canvas = document.getElementById('arus-overlay-canvas');
                    if (canvas) { var ctx = canvas.getContext('2d'); ctx.clearRect(0, 0, canvas.width, canvas.height); }
                    var olds = document.querySelectorAll('.esp-square, .prob-tag');
                    for(var i=0; i<olds.length; i++) olds[i].remove();
                } catch(e) {}
            """)
        except: pass

    def safe_analyze(self, board):
        for attempt in range(3):
            if not self.running: return None
            try:
                with self.engine_lock:
                    if not self.engine:
                        self.log("[*] Движок не найден. Попытка запуска...")
                        if not self.init_engine():
                            time.sleep(1)
                            continue
                    result = self.engine.play(board, chess.engine.Limit(time=self.think_time))
                    return result
            except (chess.engine.EngineTerminatedError, BrokenPipeError, Exception) as e:
                self.log(f"[!] Сбой движка. Авто-рестарт...")
                time.sleep(1)
                with self.engine_lock:
                    self.init_engine() 
        self.log("[!] Не удалось восстановить движок.")
        return None

    def run_bot(self, stockfish_path, think_time):
        self.running = True
        self.think_time = think_time
        
        if not self.start_browser():
            self.running = False
            return
        
        self.log("[*] Запуск Stockfish...")
        if not self.init_engine():
            self.log("[!] Ошибка первого запуска, ждем...")
            time.sleep(2)
        self.log("[+] Готов к игре.")
        self.log("[+] Система авто-восстановления активна.")

        last_board_time = time.time()
        
        while self.running:
            try:
                self._ensure_overlay() 
                state = self.get_game_state()
                
                if not state:
                    if time.time() - last_board_time > 10.0:
                        self.log("[!] Браузер завис. Авто-перезагрузка...")
                        try:
                            self.driver.refresh()
                            time.sleep(3)
                            self._ensure_overlay()
                            self.clear_arrow()
                            self.last_pieces = ""
                            self.analyzed_pieces = ""
                            self.my_color = None
                        except: pass
                        last_board_time = time.time()
                    time.sleep(0.5)
                    continue
                
                last_board_time = time.time()

                pieces = state['pieces']
                is_flipped = state['is_flipped']

                # --- ОЖИДАНИЕ НАЧАЛА ПАРТИИ ---
                if pieces == START_FEN:
                    if self.last_pieces != START_FEN:
                        self.log("[*] Ожидание начала партии...")
                    
                    # Пока партия не началась, мы не знаем цвет.
                    self.my_color = None 
                    self.last_pieces = pieces
                    self.analyzed_pieces = ""
                    self.internal_turn = "w"
                    self.clear_arrow()
                    time.sleep(0.5)
                    continue

                # --- ПЕРВЫЙ ХОД СДЕЛАН (ОПРЕДЕЛЯЕМ ЦВЕТ) ---
                if self.my_color is None:
                    self.my_color = 'b' if is_flipped else 'w'
                    self.log(f"[+] Партия началась! Играем за {'БЕЛЫХ' if self.my_color == 'w' else 'ЧЕРНЫХ'}")

                # Если доска изменилась (был ход)
                if pieces != self.last_pieces:
                    self.last_pieces = pieces
                    self.internal_turn = "b" if self.internal_turn == "w" else "w"
                    self.clear_arrow() 
                    self.analyzed_pieces = ""
                    time.sleep(0.6) 

                # Если ход противника (ждем)
                if self.internal_turn != self.my_color:
                    time.sleep(0.1)
                    continue

                # Наш ход (делаем 1 анализ)
                if pieces != self.analyzed_pieces:
                    self.analyzed_pieces = pieces
                    
                    self.log("[*] Анализ...")
                    try:
                        board = chess.Board(f"{pieces} {self.internal_turn} - - 0 1")
                        if not board.is_valid():
                            continue
                    except ValueError:
                        continue
                    
                    if board.is_game_over():
                        continue

                    result = self.safe_analyze(board)

                    if result and result.move:
                        best = result.move
                        win_prob = 50.0
                        if 'score' in result.info:
                            s = result.info['score'].white()
                            if s.is_mate(): win_prob = 100 if s.mate() > 0 else 0
                            elif s.score() is not None:
                                cp = s.score()
                                win_prob = round((1 / (1 + math.exp(-cp / 400))) * 100, 1)
                                
                        from_sq = chess.square_name(best.from_square)
                        to_sq = chess.square_name(best.to_square)
                        self.log(f"-> {from_sq.upper()}{to_sq.upper()} ({win_prob}%)")
                        self.draw_arrow_and_esp(from_sq, to_sq, win_prob)
                    else:
                        time.sleep(5)
                        self.analyzed_pieces = "" 

                time.sleep(0.1)
            except Exception as e:
                time.sleep(1)
        self.stop()

    def stop(self):
        self.running = False
        self.clear_arrow()
        with self.engine_lock:
            try:
                if self.engine: self.engine.quit()
            except: pass
        self.log("[!] Остановлен.")


class ModernGUI:
    BG_COLOR = "#080c13"
    CARD_COLOR = "#101925"
    LINE_COLOR = "#1c2b3d"
    ACCENT = "#478df5"
    ACCENT_HOVER = "#5fa2ff"
    TEXT_MAIN = "#e8effa"
    TEXT_DIM = "#8d9cb1"
    TEXT_MUTE = "#5e6d82"

    def __init__(self, root):
        self.root = root
        self.root.title("Arus Chess AI")
        self.root.geometry("600x720")
        self.root.configure(bg=self.BG_COLOR)
        self.root.attributes("-topmost", True)
        
        self.bot = None
        font_title = ("Segoe UI", 24, "bold")
        
        header_frame = tk.Frame(root, bg=self.BG_COLOR)
        header_frame.pack(pady=(30, 10), fill="x", padx=40)
        tk.Label(header_frame, text="⚡ ", bg=self.BG_COLOR, fg=self.ACCENT, font=("Segoe UI", 20)).pack(side="left")
        tk.Label(header_frame, text="ARUS", bg=self.BG_COLOR, fg=self.ACCENT, font=font_title).pack(side="left")
        tk.Label(header_frame, text=" CHESS AI", bg=self.BG_COLOR, fg=self.TEXT_MAIN, font=font_title).pack(side="left")
        
        tk.Label(root, text="PREMIUM BOARD ANALYSIS & ESP OVERLAY", bg=self.BG_COLOR, fg=self.TEXT_DIM, font=("Segoe UI", 9)).pack(pady=(0, 20))

        settings_card = tk.Frame(root, bg=self.CARD_COLOR, bd=0, highlightthickness=1, highlightbackground=self.LINE_COLOR)
        settings_card.pack(pady=10, padx=40, fill="x", ipady=10)

        tk.Label(settings_card, text="Режим интеллекта:", bg=self.CARD_COLOR, fg=self.TEXT_DIM, font=("Segoe UI", 10)).pack(anchor="w", padx=20, pady=(5, 0))
        self.btn_pro = tk.Button(settings_card, text="🔥 PRO (Максимальный)", bg=self.ACCENT, fg="#fff", font=("Segoe UI", 10, "bold"), relief="flat", bd=0, width=22, pady=8, state="disabled")
        self.btn_pro.pack(padx=20, pady=5, anchor="w")

        tk.Label(settings_card, text="Время на анализ:", bg=self.CARD_COLOR, fg=self.TEXT_DIM, font=("Segoe UI", 10)).pack(anchor="w", padx=20, pady=(15, 0))
        slider_frame = tk.Frame(settings_card, bg=self.CARD_COLOR)
        slider_frame.pack(fill="x", padx=20, pady=10)

        self.time_canvas = tk.Canvas(slider_frame, height=6, bg=self.BG_COLOR, highlightthickness=0)
        self.time_canvas.pack(side="left", fill="x", expand=True)

        self.lbl_time = tk.Label(slider_frame, text="0.5 с", bg=self.CARD_COLOR, fg=self.ACCENT, font=("Consolas", 10, "bold"), width=5)
        self.lbl_time.pack(side="right", padx=(10, 0))

        self.time_val = 0.5
        self.dragging = False

        def update_slider(event):
            w = self.time_canvas.winfo_width()
            if w <= 1: return
            x = max(0, min(event.x, w))
            self.time_val = round(0.1 + (x / w) * 1.9, 1) 
            self.lbl_time.config(text=f"{self.time_val:.1f} с")
            draw_slider()

        def draw_slider():
            w = self.time_canvas.winfo_width()
            self.time_canvas.delete("all")
            self.time_canvas.create_rectangle(0, 0, w, 6, fill=self.LINE_COLOR, outline="")
            fill_w = ((self.time_val - 0.1) / 1.9) * w
            self.time_canvas.create_rectangle(0, 0, fill_w, 6, fill=self.ACCENT, outline="")
            self.time_canvas.create_oval(fill_w-6, -3, fill_w+6, 9, fill="#fff", outline="")

        def on_press(e): self.dragging = True; update_slider(e)
        def on_drag(e): 
            if self.dragging: update_slider(e)
        def on_release(e): self.dragging = False

        self.time_canvas.bind("<Button-1>", on_press)
        self.time_canvas.bind("<B1-Motion>", on_drag)
        self.time_canvas.bind("<ButtonRelease-1>", on_release)
        self.time_canvas.bind("<Configure>", lambda e: draw_slider())
        
        tk.Frame(settings_card, bg=self.LINE_COLOR, height=1).pack(fill="x", padx=20, pady=10)
        self.btn_auto = tk.Button(settings_card, text="🔒 Автоход: СКОРО", bg=self.BG_COLOR, fg=self.TEXT_MUTE, font=("Segoe UI", 10, "bold"), relief="flat", bd=0, anchor="w", padx=15, pady=8, state="disabled")
        self.btn_auto.pack(fill="x", padx=20, pady=(0, 5))

        btn_frame = tk.Frame(root, bg=self.BG_COLOR)
        btn_frame.pack(pady=20)
        self.btn_start = tk.Button(btn_frame, text="🚀 СТАРТ", bg=self.ACCENT, fg="#ffffff", font=("Segoe UI", 11, "bold"), relief="flat", width=15, cursor="hand2", activebackground=self.ACCENT_HOVER, bd=0)
        self.btn_start.config(command=self.start_bot)
        self.btn_start.pack(side="left", padx=10, ipady=8)
        
        self.btn_stop = tk.Button(btn_frame, text="🛑 СТОП", bg=self.LINE_COLOR, fg="#ff5f6d", font=("Segoe UI", 11, "bold"), relief="flat", width=10, cursor="hand2", state="disabled", bd=0)
        self.btn_stop.config(command=self.stop_bot)
        self.btn_stop.pack(side="left", padx=10, ipady=8)

        log_card = tk.Frame(root, bg=self.CARD_COLOR, bd=0, highlightthickness=1, highlightbackground=self.LINE_COLOR)
        log_card.pack(padx=40, pady=(0, 20), fill="both", expand=True)
        
        log_head = tk.Frame(log_card, bg="#0a121c")
        log_head.pack(fill="x")
        tk.Label(log_head, text="CONSOLE OUTPUT", bg="#0a121c", fg=self.TEXT_DIM, font=("Courier New", 8, "bold"), anchor="w", padx=15, pady=8).pack(fill="x")
        tk.Frame(log_card, bg=self.LINE_COLOR, height=1).pack(fill="x")

        self.text_log = tk.Text(log_card, bg=self.BG_COLOR, fg="#2ee6a8", font=("Consolas", 10), relief="flat", wrap="word", padx=15, pady=15, state="disabled", insertbackground=self.ACCENT)
        self.text_log.pack(side="left", fill="both", expand=True)

    def log(self, message):
        self.text_log.config(state="normal")
        self.text_log.insert(tk.END, message + "\n")
        self.text_log.config(state="disabled")
        self.text_log.see(tk.END)

    def start_bot(self):
        path = find_stockfish()
        if not path:
            messagebox.showerror("Ошибка", "stockfish.exe не найден!")
            return
        self.btn_start.config(state="disabled", bg=self.LINE_COLOR, fg=self.TEXT_DIM)
        self.btn_stop.config(state="normal", bg=self.ACCENT, fg="#ffffff")
        self.text_log.config(state="normal"); self.text_log.delete(1.0, tk.END); self.text_log.config(state="disabled")
        
        self.bot = ChessBot(self.log)
        threading.Thread(target=self.bot.run_bot, args=(path, self.time_val), daemon=True).start()

    def stop_bot(self):
        if self.bot: self.bot.stop()
        self.btn_start.config(state="normal", bg=self.ACCENT, fg="#ffffff")
        self.btn_stop.config(state="disabled", bg=self.LINE_COLOR, fg="#ff5f6d")

if __name__ == "__main__":
    root = tk.Tk()
    app = ModernGUI(root)
    app.root.mainloop() if hasattr(app, 'root') else root.mainloop()