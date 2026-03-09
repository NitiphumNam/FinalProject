import customtkinter as ctk
import socket, threading, random

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception: return "127.0.0.1"

HOST = "0.0.0.0"
PORT = 5000
players = {}; order = []; turn = 0; turn_id = 0; current_action = None
start_hp = 3; game_started = False

def create_server_socket():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    return s

def safe_send(c, msg):
    try: c.sendall((msg + "\n").encode())
    except: pass 

def broadcast(msg):
    for c in list(players.keys()): safe_send(c, msg)

def log(t):
    console.configure(state="normal")
    console.insert("end", f"[*] {t}\n")
    console.see("end")
    console.configure(state="disabled")

def update_ui_list():
    plist.configure(state="normal")
    plist.delete("0.0", "end")
    for p in players.values():
        status_txt = "OUT" if p["hp"] <= 0 else f"HP: {p['hp']}"
        tag = "[HOST]" if p["host"] else ("[READY]" if p["ready"] else "")
        plist.insert("end", f"👤 {p['name']} | {status_txt} {tag}\n")
    plist.configure(state="disabled")

def broadcast_lobby_status():
    p_list = [f"{p['name']},{p['hp']},{int(p['host'])},{int(p['ready'])}" for p in players.values()]
    broadcast(f"LOBBY|{';'.join(p_list)}")
    update_ui_list()

def remove_player(c):
    global turn, game_started, current_action
    if c not in players: return
    name = players[c]["name"]; was_host = players[c]["host"]

    was_active_turn = (order and len(order) > 0 and order[turn] == c)
    was_in_action = (current_action and current_action[0] == c)

    was_guesser = False
    if current_action and len(order) > 1:
        target_idx = get_next_alive_player(turn)
        if order[target_idx] == c:
            was_guesser = True

    del players[c]
    if c in order:
        idx = order.index(c)
        order.remove(c)
        if turn >= len(order): turn = 0
        elif idx < turn: turn -= 1

    if was_host and len(order) > 0:
        players[order[0]]["host"] = True
        log(f"Host rights transferred to {players[order[0]]['name']}")

    broadcast_lobby_status(); log(f"{name} disconnected.")

    if game_started and len(order) >= 2:
        if was_in_action or was_active_turn:
            current_action = None
            broadcast(f"CHAT|System|{name} disconnected! Moving to next turn.")
            start_new_turn()

    elif game_started and len(order) < 2:
        game_started = False
        broadcast("CHAT|System|Not enough players. Game aborted.")
        broadcast("WIN|No one") # แจ้ง Client ให้รีเซ็ต UI เป็นหน้าจบเกม
        for p in players.values(): p["hp"] = start_hp; p["ready"] = False
        broadcast_lobby_status()
    try: c.close()
    except: pass

def get_next_alive_player(current_idx):
    if not order: return 0
    idx = (current_idx + 1) % len(order)
    for _ in range(len(order)):
        if players[order[idx]]["hp"] > 0: return idx
        idx = (idx + 1) % len(order)
    return idx

def check_for_winner():
    global game_started
    alive = [p for p in players.values() if p["hp"] > 0]
    if len(alive) <= 1 and game_started:
        winner_name = alive[0]['name'] if alive else "No one"
        # ส่ง WIN ให้ Client ทราบก่อน เพื่อปรับสถานะ UI ให้ถูกต้อง
        broadcast(f"WIN|{winner_name}") 
        game_started = False
        for p in players.values(): p["hp"] = start_hp; p["ready"] = False
        broadcast_lobby_status()
        return True
    return False

def start_new_turn():
    global turn_id, current_action
    if check_for_winner(): return
    turn_id += 1; current_action = None
    for p in players.values(): p["rolls_done"] = 0; p["last_roll"] = 0
    broadcast("RESETDICE")
    if order and len(order) > turn:
        active_player_name = players[order[turn]]["name"]
        broadcast(f"TURN|{active_player_name}|{turn_id}")

def handle_client(c):
    global turn, game_started, current_action
    buf = ""
    while True:
        try:
            data = c.recv(1024).decode()
            if not data: break
            buf += data
            while "\n" in buf:
                line, buf = buf.split("\n", 1)
                if not line: continue
                parts = line.split("|")
                cmd = parts[0]

                if cmd == "JOIN" and len(parts) >= 2:
                    p_name = parts[1].replace(";", "").replace(",", "")[:15]
                    if any(p["name"] == p_name for p in players.values()): p_name += f"_{random.randint(10,99)}"
                    safe_send(c, f"YOURNAME|{p_name}")
                    assigned_hp = start_hp if not game_started else 0 
                    players[c] = {"name": p_name, "hp": assigned_hp, "host": (len(players)==0), "ready": False, "rolls_done": 0, "last_roll": 0}
                    order.append(c)
                    log(f"{p_name} joined."); broadcast_lobby_status()
                    
                    if game_started: 
                        # ผู้เล่นที่เข้ามาใหม่ จะถูกบังคับให้ซ่อนปุ่ม Start/Ready ทันที
                        safe_send(c, "START") 
                        safe_send(c, "CHAT|System|Game is running. You are a spectator.")

                elif cmd == "READY":
                    players[c]["ready"] = not players[c]["ready"]; broadcast_lobby_status()

                elif cmd == "START":
                    if players[c]["host"]:
                        if len(players) >= 2:
                            if all(p["ready"] or p["host"] for p in players.values()):
                                game_started = True; broadcast("START"); start_new_turn()
                            else: safe_send(c, "CHAT|System|Cannot start! All players must be READY.")
                        else: safe_send(c, "CHAT|System|Need at least 2 players to start!")
                        
                elif cmd == "REFRESH":
                    broadcast_lobby_status()

                elif cmd == "ROLL":
                    if not game_started: continue
                    if c == order[turn] and current_action is None:
                        players[c]["rolls_done"] += 1
                        val = random.randint(1, 6); players[c]["last_roll"] = val
                        safe_send(c, f"ROLLRESULT|{val}")

                elif cmd == "CLAIM" and len(parts) >= 2:
                    if not game_started: continue
                    if c == order[turn] and players[c]["last_roll"] > 0:
                        try:
                            claim_val = int(parts[1])
                            current_action = (c, players[c]["last_roll"], claim_val, turn_id)
                            target_idx = get_next_alive_player(turn)
                            safe_send(order[target_idx], f"GUESS|{players[c]['name']}|{claim_val}|{turn_id}")
                        except ValueError: pass

                elif cmd == "GUESS" and len(parts) >= 3:
                    if not game_started: continue
                    if not current_action: continue
                    roller_sock, actual, claimed, tid = current_action
                    if parts[2] != str(tid): continue
                    is_truth = (actual == claimed)
                    correct_guess = is_truth if parts[1] == "believe" else not is_truth
                    loser_sock = roller_sock if correct_guess else c
                    players[loser_sock]["hp"] -= 1
                    broadcast(f"RESULT|{players[roller_sock]['name']}|{actual}|{claimed}|{players[loser_sock]['name']}")
                    turn = get_next_alive_player(turn); broadcast_lobby_status(); start_new_turn()

                elif cmd == "CHAT" and len(parts) >= 2:
                    if parts[1].strip(): broadcast(f"CHAT|{players[c]['name']}|{parts[1]}")
        except: break
    remove_player(c)

def server_main():
    s = create_server_socket()
    s.bind((HOST, PORT)); s.listen()
    log(f"Server online on port {PORT}")
    while True:
        try: conn, _ = s.accept(); threading.Thread(target=handle_client, args=(conn,), daemon=True).start()
        except: continue

# ================= SERVER UI =================
ctk.set_appearance_mode("dark")
app = ctk.CTk(); app.geometry("550x650"); app.title("Bluff Dice - Server")

header = ctk.CTkLabel(app, text="⚙️ SERVER CONTROL PANEL", font=("Arial", 22, "bold"), text_color="#4CA1AF")
header.pack(pady=(15, 10))

top = ctk.CTkFrame(app, corner_radius=10, fg_color="#2B2B2B")
top.pack(fill="x", padx=15, pady=5)
ctk.CTkLabel(top, text="Start HP:", font=("Arial", 14)).pack(side="left", padx=10, pady=10)
hp_ent = ctk.CTkEntry(top, width=60, justify="center"); hp_ent.insert(0, "3"); hp_ent.pack(side="left")

def apply_hp(): 
    global start_hp
    try:
        new_hp = int(hp_ent.get())
        if new_hp > 0: start_hp = new_hp; log(f"HP configured to {start_hp}")
    except ValueError: hp_ent.delete(0, 'end'); hp_ent.insert(0, str(start_hp))

ctk.CTkButton(top, text="Set HP", width=70, font=("Arial", 12, "bold"), command=apply_hp).pack(side="left", padx=10)

my_ip = get_local_ip()
def copy_ip():
    app.clipboard_clear(); app.clipboard_append(my_ip); app.update()
    copy_btn.configure(text="Copied!", fg_color="#28A745")
    app.after(2000, lambda: copy_btn.configure(text="Copy IP", fg_color="#007BFF"))

ctk.CTkLabel(top, text=f"IP: {my_ip}", font=("Arial", 14, "bold"), text_color="#00FF00").pack(side="right", padx=10)
copy_btn = ctk.CTkButton(top, text="Copy IP", width=70, fg_color="#007BFF", command=copy_ip)
copy_btn.pack(side="right", padx=5)

content = ctk.CTkFrame(app, fg_color="transparent")
content.pack(fill="both", expand=True, padx=15, pady=10)

ctk.CTkLabel(content, text="Connected Players", font=("Arial", 14, "bold")).pack(anchor="w")
plist = ctk.CTkTextbox(content, height=120, font=("Arial", 13), fg_color="#1E1E1E", state="disabled")
plist.pack(fill="x", pady=(0, 15))

ctk.CTkLabel(content, text="Server Logs", font=("Arial", 14, "bold")).pack(anchor="w")
console = ctk.CTkTextbox(content, font=("Consolas", 12), fg_color="#1E1E1E", text_color="#A9A9A9", state="disabled")
console.pack(fill="both", expand=True)

threading.Thread(target=server_main, daemon=True).start()
app.mainloop()