import customtkinter as ctk
import socket, threading, random

sock = None
my_name = ""
my_turn = False
current_tid = None
is_rolled = False
is_game_running = False
in_post_game = False

# เพิ่มตัวแปรสำหรับนับจำนวนครั้งที่กด Claim ในแต่ละเทิร์น
claim_count = 0 

def create_connection():
    global sock, my_name
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((ip_entry.get().strip(), 5000))
        
        raw_name = name_entry.get().strip() or f"User{random.randint(10,99)}"
        my_name = raw_name.replace("|", "").replace(";", "").replace(",", "")[:15]
        
        send_msg(f"JOIN|{my_name}")
        threading.Thread(target=listen_server, daemon=True).start()
        login_frame.place_forget() 
        game_frame.pack(fill="both", expand=True) 
    except:
        info_label.configure(text="Connection Failed! Check IP and Server.", text_color="#FF4C4C")

def send_msg(msg):
    if sock:
        try: sock.sendall((msg + "\n").encode())
        except: pass

def listen_server():
    global my_turn, current_tid, is_rolled, my_name, is_game_running, in_post_game, claim_count
    buf = ""
    while True:
        try:
            data = sock.recv(1024).decode()
            if not data: break
            buf += data
            while "\n" in buf:
                line, buf = buf.split("\n", 1)
                if not line: continue
                parts = line.split("|")
                cmd = parts[0]

                if cmd == "YOURNAME" and len(parts) >= 2:
                    my_name = parts[1]
                    root.title(f"Bluff Dice - Client [{my_name}]")

                elif cmd == "LOBBY" and len(parts) >= 2:
                    update_lobby_ui(parts[1])
                
                elif cmd == "START":
                    is_game_running = True
                    in_post_game = False
                    start_btn.pack_forget()
                    ready_btn.pack_forget()
                    status_label.configure(text="Game Started! Waiting for turn...", text_color="#FFFFFF", font=("Arial", 24, "bold"))
                
                elif cmd == "TURN" and len(parts) >= 3:
                    current_tid = parts[2]
                    my_turn = (parts[1] == my_name)
                    is_rolled = False
                    claim_count = 0 # รีเซ็ตจำนวนครั้งการ Claim เมื่อเริ่มเทิร์นใหม่
                    
                    if my_turn:
                        status_label.configure(text="⭐ YOUR TURN ⭐", text_color="#F9A826", font=("Arial", 28, "bold"))
                    else:
                        status_label.configure(text=f"Waiting for {parts[1]}...", text_color="#A9A9A9", font=("Arial", 22))
                        
                    # รีเซ็ตสถานะปุ่ม Roll และ Claim ทุกครั้งเมื่อเริ่มเทิร์นใหม่
                    roll_btn.configure(state="normal" if my_turn else "disabled")
                    claim_btn.configure(state="normal" if my_turn else "disabled", text="Send Claim", fg_color="#E67E22")
                    claim_entry.configure(state="normal" if my_turn else "disabled")
                
                elif cmd == "ROLLRESULT" and len(parts) >= 2:
                    dice_display.configure(text=parts[1])
                    is_rolled = True
                
                elif cmd == "GUESS" and len(parts) >= 4:
                    current_tid = parts[3]
                    status_label.configure(text=f"⚠️ {parts[1]} claims: {parts[2]}", text_color="#FF6B6B", font=("Arial", 26, "bold"))
                    guess_frame.pack(pady=15)
                
                elif cmd == "RESULT" and len(parts) >= 5:
                    guess_frame.pack_forget()
                    status_label.configure(text=f"Actual: {parts[2]} | {parts[4]} lost HP!", text_color="#FFFFFF", font=("Arial", 22))

                elif cmd == "RESETDICE":
                    dice_display.configure(text="🎲")
                    guess_frame.pack_forget()

                elif cmd == "WIN" and len(parts) >= 2:
                    is_game_running = False
                    in_post_game = True
                    status_label.configure(text=f"🏆 {parts[1]} WINS! 🏆", text_color="#FFD700", font=("Arial", 32, "bold"))
                    action_f.pack_forget()
                    guess_frame.pack_forget()
                    start_btn.pack_forget()
                    ready_btn.pack_forget()
                    end_game_frame.pack(pady=20)

                elif cmd == "CHAT" and len(parts) >= 3:
                    chat_view.configure(state="normal")
                    chat_view.insert("end", f"{parts[1]}: {parts[2]}\n")
                    chat_view.see("end")
                    chat_view.configure(state="disabled")
        except: break

def update_lobby_ui(data):
    p_list_box.configure(state="normal")
    p_list_box.delete("0.0", "end")
    
    players_data = [p for p in data.split(";") if p]
    total_players = len(players_data)
    all_ready = True
    
    my_is_host = False
    my_is_ready = False
    
    for p_info in players_data:
        try:
            n, hp, h, r = p_info.split(",")
            hp_str = "💀" if int(hp) <= 0 else "❤️" * int(hp)
            tag = "[HOST]" if h == "1" else ("[READY]" if r == "1" else "")
            p_list_box.insert("end", f"{n}\nHP: {hp_str} {tag}\n\n")
            
            if h == "0" and r == "0":
                all_ready = False
                
            if n == my_name:
                my_is_host = (h == "1")
                my_is_ready = (r == "1")
        except ValueError: continue
        
    p_list_box.configure(state="disabled")

    if not is_game_running and not in_post_game:
        if my_is_host:
            start_btn.pack(side="left", padx=5)
            ready_btn.pack_forget()
            if total_players >= 2 and all_ready:
                start_btn.configure(state="normal", fg_color="#28A745", text="START GAME")
            else:
                start_btn.configure(state="disabled", fg_color="#555555", text="WAITING FOR PLAYERS...")
        else:
            ready_btn.pack(side="left", padx=5)
            start_btn.pack_forget()
            if my_is_ready:
                ready_btn.configure(text="CANCEL READY", fg_color="#E67E22", hover_color="#D35400")
            else:
                ready_btn.configure(text="READY", fg_color="#007BFF", hover_color="#0056B3")
    else:
        start_btn.pack_forget()
        ready_btn.pack_forget()

def on_roll(): send_msg("ROLL")
    
def on_claim():
    global claim_count
    if my_turn and is_rolled and claim_count < 2:
        val = claim_entry.get().strip()

        if val.isdigit() and 1 <= int(val) <= 6:
            claim_count += 1
            roll_btn.configure(state="disabled") # 1. ล็อกปุ่มลูกเต๋าทันทีที่กด
            
            if claim_count == 1:
                # ครั้งที่ 1: แจ้งเตือนตัวเองให้ตรวจทาน "ยังไม่ส่งให้เพื่อน"
                claim_btn.configure(text="Confirm Claim (Final)", fg_color="#17A2B8")
                
                # แอบส่งข้อความระบบกระซิบในแชทตัวเอง เพื่อให้รู้ว่ากำลังจะส่งเลขอะไร
                chat_view.configure(state="normal")
                chat_view.insert("end", f"[System]: You are claiming {val}. Edit number or click 'Confirm' to send.\n")
                chat_view.see("end")
                chat_view.configure(state="disabled")
            else:
                # ครั้งที่ 2: คอนเฟิร์มเลขสุดท้าย ส่งไปที่เซิร์ฟเวอร์จริงๆ
                send_msg(f"CLAIM|{val}")
                claim_btn.configure(state="disabled", text="Claim Locked!", fg_color="#555555")
                claim_entry.configure(state="disabled")
                claim_entry.delete(0, 'end')
        else:
            claim_entry.delete(0, 'end')
            claim_entry.configure(placeholder_text="1-6 Only!")
            root.after(1500, lambda: claim_entry.configure(placeholder_text="Claim (1-6)"))

def on_guess(choice):
    send_msg(f"GUESS|{choice}|{current_tid}")
    guess_frame.pack_forget()

def on_chat(event=None):
    msg = chat_input.get().strip()
    if msg:
        send_msg(f"CHAT|{msg.replace('|', '')}")
        chat_input.delete(0, 'end')

def back_to_lobby():
    global in_post_game
    in_post_game = False
    status_label.configure(text="Welcome to the Lobby", text_color="#FFFFFF", font=("Arial", 24, "bold"))
    dice_display.configure(text="🎲")

    roll_btn.configure(state="normal")
    claim_btn.configure(text="Send Claim", fg_color="#E67E22", state="normal")
    claim_entry.configure(state="normal")
    claim_entry.delete(0, 'end')

    end_game_frame.pack_forget()
    action_f.pack(pady=10)
    send_msg("REFRESH") 

# ================= CLIENT UI =================
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")
root = ctk.CTk()
root.geometry("850x600")
root.title("Bluff Dice - Client")

# --- Login Screen ---
login_frame = ctk.CTkFrame(root, width=350, corner_radius=15, fg_color="#2B2B2B")
login_frame.place(relx=0.5, rely=0.5, anchor="center")

ctk.CTkLabel(login_frame, text="BLUFF DICE", font=("Arial", 28, "bold"), text_color="#4CA1AF").pack(pady=(20, 10))
name_entry = ctk.CTkEntry(login_frame, placeholder_text="Enter your name", width=250, height=40, font=("Arial", 14))
name_entry.pack(pady=10)
ip_entry = ctk.CTkEntry(login_frame, placeholder_text="Server IP", width=250, height=40, font=("Arial", 14))
ip_entry.insert(0, "127.0.0.1")
ip_entry.pack(pady=10)
ctk.CTkButton(login_frame, text="Connect to Game", width=250, height=40, font=("Arial", 14, "bold"), command=create_connection).pack(pady=(15, 5))
info_label = ctk.CTkLabel(login_frame, text="", font=("Arial", 12))
info_label.pack(pady=(0, 15))

# --- Main Game Screen ---
game_frame = ctk.CTkFrame(root, fg_color="transparent")

sidebar = ctk.CTkFrame(game_frame, width=250, corner_radius=0, fg_color="#1E1E1E")
sidebar.pack(side="left", fill="y", padx=(0, 10))

ctk.CTkLabel(sidebar, text="Players", font=("Arial", 16, "bold")).pack(pady=(10, 0), padx=10, anchor="w")
p_list_box = ctk.CTkTextbox(sidebar, height=200, font=("Arial", 14), fg_color="#2B2B2B", state="disabled")
p_list_box.pack(fill="x", padx=10, pady=5)

ctk.CTkLabel(sidebar, text="Chat", font=("Arial", 16, "bold")).pack(pady=(10, 0), padx=10, anchor="w")
chat_view = ctk.CTkTextbox(sidebar, font=("Arial", 13), fg_color="#2B2B2B", state="disabled")
chat_view.pack(fill="both", expand=True, padx=10, pady=5)
chat_input = ctk.CTkEntry(sidebar, placeholder_text="Type a message...")
chat_input.pack(fill="x", padx=10, pady=(0, 10))
chat_input.bind("<Return>", on_chat)

main_board = ctk.CTkFrame(game_frame, fg_color="transparent")
main_board.pack(side="right", fill="both", expand=True)

top_bar = ctk.CTkFrame(main_board, height=50, fg_color="transparent")
top_bar.pack(fill="x", pady=10)
start_btn = ctk.CTkButton(top_bar, text="START GAME", fg_color="#28A745", font=("Arial", 14, "bold"), command=lambda: send_msg("START"))
ready_btn = ctk.CTkButton(top_bar, text="READY", fg_color="#007BFF", font=("Arial", 14, "bold"), command=lambda: send_msg("READY"))
ctk.CTkButton(top_bar, text="Quit", width=60, fg_color="#DC3545", hover_color="#C82333", command=root.destroy).pack(side="right", padx=10)

board_center = ctk.CTkFrame(main_board, fg_color="#2B2B2B", corner_radius=15)
board_center.pack(expand=True, fill="both", padx=20, pady=(0, 20))

status_label = ctk.CTkLabel(board_center, text="Welcome to the Lobby", font=("Arial", 24, "bold"))
status_label.pack(pady=(40, 20))

dice_display = ctk.CTkLabel(board_center, text="🎲", font=("Arial", 120))
dice_display.pack(pady=20)

action_f = ctk.CTkFrame(board_center, fg_color="transparent")
action_f.pack(pady=10)
roll_btn = ctk.CTkButton(action_f, text="Roll Dice", width=120, height=40, font=("Arial", 14, "bold"), command=on_roll)
roll_btn.pack(side="left", padx=5)
claim_entry = ctk.CTkEntry(action_f, placeholder_text="Claim (1-6)", width=100, height=40, font=("Arial", 14), justify="center")
claim_entry.pack(side="left", padx=5)

# ประกาศตัวแปร claim_btn เพื่อใช้ในการเรียกเปลี่ยนข้อความ/สี ภายหลัง
claim_btn = ctk.CTkButton(action_f, text="Send Claim", width=140, height=40, fg_color="#E67E22", hover_color="#D35400", font=("Arial", 14, "bold"), command=on_claim)
claim_btn.pack(side="left", padx=5)

guess_frame = ctk.CTkFrame(board_center, fg_color="transparent")
ctk.CTkButton(guess_frame, text="Believe (True)", width=140, height=45, fg_color="#28A745", hover_color="#218838", font=("Arial", 15, "bold"), command=lambda: on_guess("believe")).pack(side="left", padx=10)
ctk.CTkButton(guess_frame, text="Call Bluff (Lie!)", width=140, height=45, fg_color="#DC3545", hover_color="#C82333", font=("Arial", 15, "bold"), command=lambda: on_guess("lie")).pack(side="left", padx=10)

end_game_frame = ctk.CTkFrame(board_center, fg_color="transparent")
ctk.CTkButton(end_game_frame, text="Play Again", width=140, height=40, fg_color="#007BFF", command=back_to_lobby).pack(side="left", padx=10)

root.mainloop()