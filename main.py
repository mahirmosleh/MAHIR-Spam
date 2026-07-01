import os, sys, time, json, ssl, socket, threading, asyncio, base64, binascii, re, jwt, pickle, random
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from threading import Thread
from flask import Flask, request, jsonify, render_template_string, session, redirect, url_for
from functools import wraps

import requests
import urllib3
from Pb2 import MajoRLoGinrEq_pb2
import random
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from google.protobuf.timestamp_pb2 import Timestamp

# custom project modules
from byte import *
from byte import xSEndMsg, Auth_Chat
from xHeaders import *
from black9 import openroom, spmroom
import xKEys

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==================== LOGIN CONFIG ====================
ADMIN_PASSWORD = "MAHIRJOD"
SECRET_KEY = "mahir_system_secret_key_2024"

# ==================== ফ্লাস্ক অ্যাপ ====================
app = Flask(__name__)
app.secret_key = SECRET_KEY

# ==================== LOGIN REQUIRED DECORATOR ====================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function

# ==================== গ্লোবাল ভেরিয়েবল ====================
connected_clients = {}
connected_clients_lock = threading.Lock()
active_spam_targets = {}  # target_uid -> {'type': 'full' or 'squad', 'start_time': datetime}
active_spam_lock = threading.Lock()
spam_threads = {}
spam_threads_lock = threading.Lock()

# Auto reset timer
auto_reset_timer = None
AUTO_RESET_INTERVAL = 2 * 60 * 60  # 2 hours in seconds

# File paths
ACCOUNTS_FILE = "accs.txt"
GROUP_ACCOUNTS_FILE = "group.txt"

C = "\033[96m"
G = "\033[92m"
Y = "\033[93m"
R = "\033[91m"
RS = "\033[0m"
BOLD = "\033[1m"

# ==================== ব্যাজ ভ্যালু ====================
BADGES = {
    "V_BADGE": 32768,
    "PRO_BADGE": 262144,
    "CRAFTLAND": 1048576,
    "MODERATOR": 2048,
    "SMALL_V": 64,
}

# ==================== GROUP INVITE CONFIG ====================
GROUP_CONFIGS = {
    3: {"type": 1, "players": 3},
    5: {"type": 2, "players": 5},
    6: {"type": 3, "players": 6}
}

# ==================== FILE LOADERS ====================
def load_accounts(filename="accs.txt"):
    """Load accounts from file"""
    accounts = []
    try:
        if not os.path.exists(filename):
            with open(filename, "w") as f:
                f.write("# Format: UID:PASSWORD\n")
                f.write("# Example:\n")
                f.write("# 1234567890:password123\n")
            return []

        with open(filename, "r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                if line and not line.startswith("#"):
                    if ":" in line:
                        parts = line.split(":")
                        uid = parts[0].strip()
                        pwd = parts[1].strip()
                    else:
                        uid = line.strip()
                        pwd = ""
                    
                    if uid.isdigit():
                        accounts.append({'id': uid, 'password': pwd})
        
        print(f"{G}📦 Loaded {len(accounts)} accounts from {filename}{RS}")
    except Exception as e:
        print(f"{R}❌ Error loading {filename}: {e}{RS}")
    
    return accounts

def load_group_accounts(filename="group.txt"):
    """Load group accounts for squad creation"""
    accounts = []
    try:
        if not os.path.exists(filename):
            with open(filename, "w") as f:
                f.write("# Group accounts for squad creation\n")
                f.write("# Format: UID:PASSWORD\n")
            return []

        with open(filename, "r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                if line and not line.startswith("#"):
                    if ":" in line:
                        parts = line.split(":")
                        uid = parts[0].strip()
                        pwd = parts[1].strip()
                    else:
                        uid = line.strip()
                        pwd = ""
                    
                    if uid.isdigit():
                        accounts.append({'id': uid, 'password': pwd})
        
        print(f"{G}📦 Loaded {len(accounts)} group accounts from {filename}{RS}")
    except Exception as e:
        print(f"{R}❌ Error loading {filename}: {e}{RS}")
    
    return accounts

ACCOUNTS = load_accounts("accs.txt")
GROUP_ACCOUNTS = load_group_accounts("group.txt")

# ==================== PACKET CREATION FUNCTIONS ====================
def create_group_invite_packet(key, iv, target_uid, players=5, region="BD"):
    """Create group invite packet"""
    try:
        group_config = GROUP_CONFIGS.get(players, GROUP_CONFIGS[5])
        group_type = group_config["type"]
        
        proto_fields = {
            1: 33,
            2: {
                1: int(target_uid),
                2: region.upper(),
                3: 1,
                4: 1,
                5: bytes([1, 7, 9, 10, 11, 18, 25, 26, 32]),
                6: "[C][B][FF0000] INVITE",
                7: 330,
                8: 1000,
                10: region.upper(),
                11: bytes.fromhex("61" * 32),
                12: 1,
                13: int(target_uid),
                14: {
                    1: random.randint(1000000000, 9999999999),
                    2: group_type,
                    3: "\u0010\u0015\b\n\u000b\u0013\f\u000f\u0011\u0004\u0007\u0002\u0003\r\u000e\u0012\u0001\u0005\u0006"
                },
                16: 1,
                17: 1,
                18: 312,
                19: 46,
                23: bytes([16, 1, 24, 1]),
                24: random.randint(902000000, 902050099),
                26: "",
                28: ""
            },
            10: "en",
            13: {2: 1, 3: 1}
        }
        
        packet = create_proto_sync(proto_fields).hex()
        
        if region.lower() == "ind":
            packet_type = "0514"
        elif region.lower() == "bd":
            packet_type = "0519"
        else:
            packet_type = "0515"
        
        encrypted = EnC_PacKeT(packet, key, iv)
        length = len(encrypted) // 2
        len_hex = DecodE_HeX(length)
        padding_map = {2: "000000", 3: "00000", 4: "0000", 5: "000"}
        padding = padding_map.get(len(len_hex), "000")
        
        return bytes.fromhex(packet_type + padding + len_hex + encrypted)
    except Exception as e:
        print(f"{R}❌ Group invite packet error: {e}{RS}")
        return None

def create_badge_join_packet(key, iv, target_uid, badge_value, region="BD"):
    """Create join request with badge"""
    try:
        avatar_ids = [
            902000028, 902000011, 902000015, 902000013, 902000086,
            902000154, 902000127, 902000207, 902000246, 902000305,
            902000338, 902047016, 902049015, 902052006, 902000100,
            902000204, 902052006, 902037031, 902042011, 902053016, 902051013
        ]
        selected_avatar = random.choice(avatar_ids)

        proto_fields = {
            1: 33,
            2: {
                1: int(target_uid),
                2: region.upper(),
                3: 1,
                4: 1,
                5: bytes([1, 7, 9, 10, 11, 18, 25, 26, 32]),
                6: "[C][B][FF0000] MAHIR BADGE",
                7: 330,
                8: 1000,
                10: region.upper(),
                11: bytes.fromhex("61" * 32),
                12: 1,
                13: int(target_uid),
                14: {
                    1: random.randint(1000000000, 9999999999),
                    2: 8,
                    3: "\u0010\u0015\b\n\u000b\u0013\f\u000f\u0011\u0004\u0007\u0002\u0003\r\u000e\u0012\u0001\u0005\u0006"
                },
                16: 1,
                17: 1,
                18: 312,
                19: 46,
                23: bytes([16, 1, 24, 1]),
                24: selected_avatar,
                26: "",
                28: "",
                31: {1: 1, 2: badge_value},
                32: badge_value,
                34: {
                    1: int(target_uid),
                    2: 8,
                    3: bytes([15, 6, 21, 8, 10, 11, 19, 12, 17, 4, 14, 20, 7, 2, 1, 5, 16, 3, 13, 18])
                }
            },
            10: "en",
            13: {2: 1, 3: 1}
        }
        
        packet = create_proto_sync(proto_fields).hex()
        
        if region.lower() == "ind":
            packet_type = "0514"
        elif region.lower() == "bd":
            packet_type = "0519"
        else:
            packet_type = "0515"
        
        encrypted = EnC_PacKeT(packet, key, iv)
        length = len(encrypted) // 2
        len_hex = DecodE_HeX(length)
        padding_map = {2: "000000", 3: "00000", 4: "0000", 5: "000"}
        padding = padding_map.get(len(len_hex), "000")
        
        return bytes.fromhex(packet_type + padding + len_hex + encrypted)
    except Exception as e:
        print(f"{R}❌ Badge join packet error: {e}{RS}")
        return None

def encode_varint_sync(value: int) -> bytes:
    result = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            byte |= 0x80
        result.append(byte)
        if not value:
            break
    return bytes(result)

def create_proto_sync(fields):
    packet = bytearray()
    
    for field, value in fields.items():
        field_num = int(field)
        
        if isinstance(value, dict):
            nested = create_proto_sync(value)
            packet.extend(encode_varint_sync((field_num << 3) | 2))
            packet.extend(encode_varint_sync(len(nested)))
            packet.extend(nested)
        elif isinstance(value, int):
            packet.extend(encode_varint_sync((field_num << 3) | 0))
            packet.extend(encode_varint_sync(value))
        elif isinstance(value, str):
            data = value.encode('utf-8')
            packet.extend(encode_varint_sync((field_num << 3) | 2))
            packet.extend(encode_varint_sync(len(data)))
            packet.extend(data)
        elif isinstance(value, bytes):
            packet.extend(encode_varint_sync((field_num << 3) | 2))
            packet.extend(encode_varint_sync(len(value)))
            packet.extend(value)
            
    return bytes(packet)

async def OpEnSq(K, V, region):
    fields = {
        1: 1,
        2: {
            2: "\u0001",
            3: 1,
            4: 1,
            5: "en",
            9: 1,
            11: 1,
            13: 1,
            14: {
                2: 5756,
                6: 11,
                8: "1.122.1",
                9: 2,
                10: 4
            }
        }
    }
    packet = '0514' if region.lower() == "BD" else "0515"
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), packet, K, V)

async def cHSq(Nu, Uid, K, V, region):
    fields = {
        1: 17,
        2: {
            1: int(Uid),
            2: 1,
            3: int(Nu - 1),
            4: 62,
            5: "\u001a",
            8: 5,
            13: 329
        }
    }
    packet = '0514' if region.lower() == "BD" else "0515"
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), packet, K, V)

async def SEnd_InV(Nu, Uid, K, V, region):
    fields = {
        1: 2,
        2: {
            1: int(Uid),
            2: region,
            4: int(Nu)
        }
    }
    packet = '0514' if region.lower() == "BD" else "0515"
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), packet, K, V)

async def ExiT(K, V):
    fields = {1: 7, 2: {1: 0}}
    return await _pk((await _pb(fields)).hex(), '0515', K, V)

# ==================== SPAM WORKER FUNCTIONS ====================
def run_async(coro):
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    except:
        return None
    finally:
        loop.close()

def send_full_spam(client, target_uid):
    """Send full spam: room + squad + badge + group invites"""
    total_sent = 0
    
    try:
        if not hasattr(client, 'CliEnts2') or not client.key:
            return 0
        
        # === 1. Room Spam ===
        try:
            open_pkt = openroom(client.key, client.iv)
            if open_pkt:
                client.CliEnts2.send(open_pkt)
            
            spam_pkt = spmroom(client.key, client.iv, target_uid)
            if spam_pkt:
                client.CliEnts2.send(spam_pkt)
                total_sent += 1
        except:
            pass

        # === 2. Squad Invite (5 player) ===
        try:
            async def send_squad():
                p1 = await OpEnSq(client.key, client.iv, "BD")
                client.CliEnts2.send(p1)
                await asyncio.sleep(0.05)
                p2 = await cHSq(5, target_uid, client.key, client.iv, "BD")
                client.CliEnts2.send(p2)
                await asyncio.sleep(0.05)
                p3 = await SEnd_InV(5, target_uid, client.key, client.iv, "BD")
                client.CliEnts2.send(p3)
                await asyncio.sleep(0.05)
                p4 = await ExiT(client.key, client.iv)
                client.CliEnts2.send(p4)
            run_async(send_squad())
            total_sent += 1
        except:
            pass

        # === 3. Badge Join ===
        for badge_name, badge_value in BADGES.items():
            try:
                badge_pkt = create_badge_join_packet(client.key, client.iv, target_uid, badge_value)
                if badge_pkt:
                    client.CliEnts2.send(badge_pkt)
                    total_sent += 1
                    time.sleep(0.03)
            except:
                pass

        # === 4. Group Invites (3, 5, 6 player) ===
        for players in [3, 5, 6]:
            try:
                group_pkt = create_group_invite_packet(client.key, client.iv, target_uid, players)
                if group_pkt:
                    client.CliEnts2.send(group_pkt)
                    total_sent += 1
                    time.sleep(0.03)
            except:
                pass
                
    except Exception as e:
        print(f"{R}❌ Full spam error: {e}{RS}")
    
    return total_sent

def send_squad_spam(client, target_uid):
    """Send only squad spam (group invites)"""
    total_sent = 0
    
    try:
        if not hasattr(client, 'CliEnts2') or not client.key:
            return 0
        
        # === Squad Invite (5 player) ===
        try:
            async def send_squad():
                p1 = await OpEnSq(client.key, client.iv, "BD")
                client.CliEnts2.send(p1)
                await asyncio.sleep(0.05)
                p2 = await cHSq(5, target_uid, client.key, client.iv, "BD")
                client.CliEnts2.send(p2)
                await asyncio.sleep(0.05)
                p3 = await SEnd_InV(5, target_uid, client.key, client.iv, "BD")
                client.CliEnts2.send(p3)
                await asyncio.sleep(0.05)
                p4 = await ExiT(client.key, client.iv)
                client.CliEnts2.send(p4)
            run_async(send_squad())
            total_sent += 1
        except:
            pass

        # === Group Invites (3, 6 player) ===
        for players in [3, 6]:
            try:
                group_pkt = create_group_invite_packet(client.key, client.iv, target_uid, players)
                if group_pkt:
                    client.CliEnts2.send(group_pkt)
                    total_sent += 1
                    time.sleep(0.03)
            except:
                pass
                
    except Exception as e:
        print(f"{R}❌ Squad spam error: {e}{RS}")
    
    return total_sent

def spam_worker(target_uid, spam_type='full'):
    """Main spam worker for a target"""
    print(f"\n{G}{'='*60}{RS}")
    print(f"{G}🎯 SPAM STARTED ON {target_uid} (Type: {spam_type}){RS}")
    print(f"{C}{'='*60}{RS}\n")

    total_requests = 0
    round_number = 0

    while True:
        with active_spam_lock:
            if target_uid not in active_spam_targets:
                break

        with connected_clients_lock:
            clients_list = list(connected_clients.values())
            
        # Also use group accounts for squad spam
        group_clients = []
        for acc in GROUP_ACCOUNTS:
            if acc['id'] in connected_clients:
                group_clients.append(connected_clients[acc['id']])
        
        all_clients = clients_list + group_clients

        if not all_clients:
            time.sleep(2)
            continue

        round_number += 1

        for client in all_clients:
            with active_spam_lock:
                if target_uid not in active_spam_targets:
                    break

            try:
                if spam_type == 'full':
                    total_requests += send_full_spam(client, target_uid)
                else:
                    total_requests += send_squad_spam(client, target_uid)
            except Exception as e:
                print(f"{R}❌ Spam error: {e}{RS}")

            time.sleep(0.05)

        if round_number % 10 == 0:
            print(f"{C}{'='*50}{RS}")
            print(f"{G}📊 Round {round_number} Complete{RS}")
            print(f"{G}📊 Total Requests: {total_requests}{RS}")
            print(f"{G}🎯 Target: {target_uid}{RS}")
            print(f"{G}🤖 Bots: {len(all_clients)}{RS}")
            print(f"{C}{'='*50}{RS}\n")
        
        time.sleep(0.5)

    with spam_threads_lock:
        if target_uid in spam_threads:
            del spam_threads[target_uid]

    print(f"\n{R}🛑 SPAM STOPPED ON {target_uid}{RS}\n")

def start_spam(target_uid, spam_type='full'):
    """Start spam on a target"""
    with active_spam_lock:
        if target_uid in active_spam_targets:
            return False, f"Already spamming {target_uid}"
        
        active_spam_targets[target_uid] = {
            'type': spam_type,
            'start_time': datetime.now()
        }
    
    thread = Thread(target=spam_worker, args=(target_uid, spam_type), daemon=True)
    with spam_threads_lock:
        spam_threads[target_uid] = thread
    thread.start()
    
    return True, f"Started {spam_type} spam on {target_uid}"

def stop_spam(target_uid):
    """Stop spam on a target"""
    with active_spam_lock:
        if target_uid in active_spam_targets:
            del active_spam_targets[target_uid]
            return True, f"Stopped spam on {target_uid}"
    return False, f"No spam found for {target_uid}"

def stop_all_spam():
    """Stop all spam"""
    with active_spam_lock:
        targets = list(active_spam_targets.keys())
        for target in targets:
            del active_spam_targets[target]
    return True, f"Stopped all spam ({len(targets)} targets)"

def get_spam_status():
    """Get current spam status"""
    with active_spam_lock:
        active_targets = []
        for target, info in active_spam_targets.items():
            start_time = info.get('start_time')
            elapsed = (datetime.now() - start_time).total_seconds() if start_time else 0
            active_targets.append({
                'uid': target,
                'type': info.get('type', 'full'),
                'elapsed_minutes': int(elapsed / 60)
            })
    
    with connected_clients_lock:
        accounts_count = len(connected_clients)
        accounts_list = list(connected_clients.keys())
    
    return {
        'active_targets': active_targets,
        'active_count': len(active_targets),
        'accounts_count': accounts_count,
        'accounts_list': accounts_list[:50]
    }

# ==================== AUTO RESET ====================
def auto_reset_spam():
    """Auto reset all spam every 2 hours"""
    global auto_reset_timer
    
    print(f"\n{Y}{'='*50}{RS}")
    print(f"{Y}🔄 AUTO RESET INITIATED (Every 2 Hours){RS}")
    print(f"{Y}{'='*50}{RS}\n")
    
    # Stop all spam
    stop_all_spam()
    
    # Reload accounts
    global ACCOUNTS, GROUP_ACCOUNTS
    ACCOUNTS = load_accounts("accs.txt")
    GROUP_ACCOUNTS = load_group_accounts("group.txt")
    
    print(f"{G}✅ Auto reset complete. Accounts reloaded.{RS}\n")
    
    # Schedule next reset
    if auto_reset_timer:
        auto_reset_timer.cancel()
    auto_reset_timer = threading.Timer(AUTO_RESET_INTERVAL, auto_reset_spam)
    auto_reset_timer.daemon = True
    auto_reset_timer.start()

def start_auto_reset():
    global auto_reset_timer
    if auto_reset_timer:
        auto_reset_timer.cancel()
    auto_reset_timer = threading.Timer(AUTO_RESET_INTERVAL, auto_reset_spam)
    auto_reset_timer.daemon = True
    auto_reset_timer.start()
    print(f"{G}⏰ Auto-reset timer started (every {AUTO_RESET_INTERVAL//3600} hours){RS}")

def trigger_manual_reset():
    """Manually trigger auto reset via API"""
    auto_reset_spam()
    return True, "Manual reset triggered"

# ==================== FF CLIENT ====================
class FF_CLient():
    def __init__(self, id, password):
        self.id = id
        self.password = password
        self.key = None
        self.iv = None
        self.Get_FiNal_ToKen_0115()

    def Connect_SerVer_OnLine(self, Token, tok, host, port, key, iv, host2, port2):
        try:
            self.AutH_ToKen_0115 = tok    
            self.CliEnts2 = socket.create_connection((host2, int(port2)))
            self.CliEnts2.send(bytes.fromhex(self.AutH_ToKen_0115))
            with connected_clients_lock:
                if self.id not in connected_clients:
                    connected_clients[self.id] = self
                    print(f"{G}✅ Online: {self.id} (Total: {len(connected_clients)}){RS}")
        except Exception as e:
            print(f"{R}❌ Online error {self.id}: {e}{RS}")
            return
        while True:
            try:
                self.DaTa2 = self.CliEnts2.recv(99999)
                if '0500' in self.DaTa2.hex()[0:4] and len(self.DaTa2.hex()) > 30:
                    self.packet = json.loads(DeCode_PackEt(f'08{self.DaTa2.hex().split("08", 1)[1]}'))
                    self.AutH = self.packet['5']['data']['7']['data']
            except: pass
                                                            
    def Connect_SerVer(self, Token, tok, host, port, key, iv, host2, port2):
        self.AutH_ToKen_0115 = tok    
        self.CliEnts = socket.create_connection((host, int(port)))
        self.CliEnts.send(bytes.fromhex(self.AutH_ToKen_0115))  
        self.DaTa = self.CliEnts.recv(1024)          	        
        threading.Thread(target=self.Connect_SerVer_OnLine, args=(Token, tok, host, port, key, iv, host2, port2)).start()
        try: self.Exemple = xMsGFixinG('12345678')
        except: pass
        self.key = key
        self.iv = iv
        with connected_clients_lock:
            if self.id not in connected_clients:
                connected_clients[self.id] = self
                print(f"{G}✅ Registered: {self.id}{RS}")
        while True:      
            try:
                self.DaTa = self.CliEnts.recv(1024)   
                if len(self.DaTa) == 0 or (hasattr(self, 'DaTa2') and len(self.DaTa2) == 0):
                    try:
                        self.CliEnts.close()
                        if hasattr(self, 'CliEnts2'): self.CliEnts2.close()
                        self.Connect_SerVer(Token, tok, host, port, key, iv, host2, port2)                    		                    
                    except:
                        try:
                            self.CliEnts.close()
                            if hasattr(self, 'CliEnts2'): self.CliEnts2.close()
                            self.Connect_SerVer(Token, tok, host, port, key, iv, host2, port2)
                        except:
                            self.CliEnts.close()
                            if hasattr(self, 'CliEnts2'): self.CliEnts2.close()
                            ResTarT_BoT()	            
            except Exception as e:
                print(f"{R}❌ Connection error {self.id}: {e}{RS}")
                with connected_clients_lock:
                    if self.id in connected_clients: del connected_clients[self.id]
                self.Connect_SerVer(Token, tok, host, port, key, iv, host2, port2)
                                    
    def GeT_Key_Iv(self, serialized_data):
        my_message = xKEys.MyMessage()
        my_message.ParseFromString(serialized_data)
        timestamp, key, iv = my_message.field21, my_message.field22, my_message.field23
        timestamp_obj = Timestamp()
        timestamp_obj.FromNanoseconds(timestamp)
        timestamp_seconds = timestamp_obj.seconds
        timestamp_nanos = timestamp_obj.nanos
        combined_timestamp = timestamp_seconds * 1_000_000_000 + timestamp_nanos
        return combined_timestamp, key, iv    

    def Guest_GeneRaTe(self, uid, password):
        self.url = "https://100067.connect.garena.com/oauth/guest/token/grant"
        self.headers = {
            "Host": "100067.connect.garena.com",
            "User-Agent": "GarenaMSDK/4.0.19P4(G011A ;Android 9;en;US;)",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "close",
        }
        self.dataa = {
            "uid": f"{uid}",
            "password": f"{password}",
            "response_type": "token",
            "client_type": "2",
            "client_secret": "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3",
            "client_id": "100067",
        }
        try:
            self.response = requests.post(self.url, headers=self.headers, data=self.dataa).json()
            self.Access_ToKen, self.Access_Uid = self.response['access_token'], self.response['open_id']
            time.sleep(0.2)
            print(f'{C}🔐 Login: {self.id}{RS}')
            return self.ToKen_GeneRaTe(self.Access_ToKen, self.Access_Uid)
        except Exception as e: 
            print(f"{R}❌ Login error {self.id}: {e}{RS}")
            time.sleep(10)
            return self.Guest_GeneRaTe(uid, password)
                                        
    def GeT_LoGin_PorTs(self, JwT_ToKen, PayLoad, dynamic_url="https://clientbp.ggpolarbear.com"):
        self.UrL = f'{dynamic_url}/GetLoginData'
        self.HeadErs = {
            'Expect': '100-continue',
            'Authorization': f'Bearer {JwT_ToKen}',
            'X-Unity-Version': '2022.3.47f1',
            'X-GA': 'v1 1',
            'ReleaseVersion': 'OB54',
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'UnityPlayer/2022.3.47f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)',
            'Connection': 'close',
            'Accept-Encoding': 'deflate, gzip',
        }        
        try:
            self.Res = requests.post(self.UrL, headers=self.HeadErs, data=PayLoad, verify=False)
            self.BesTo_data = json.loads(DeCode_PackEt(self.Res.content.hex()))  
            address, address2 = self.BesTo_data['32']['data'], self.BesTo_data['14']['data'] 
            ip, ip2 = address[:len(address) - 6], address2[:len(address2) - 6]
            port, port2 = address[len(address) - 5:], address2[len(address2) - 5:]             
            return ip, port, ip2, port2          
        except Exception as e:
            print(f"{R}❌ Failed to get ports: {e}{RS}")
        return None, None, None, None
        
    def ToKen_GeneRaTe(self, Access_ToKen, Access_Uid):
        self.UrL = "https://loginbp.ggpolarbear.com/MajorLogin"
        self.HeadErs = {
            'X-Unity-Version': '2022.3.47f1',
            'ReleaseVersion': 'OB54',
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-GA': 'v1 1',
            'User-Agent': 'UnityPlayer/2022.3.47f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)',
            'Host': 'loginbp.ggpolarbear.com',
            'Connection': 'Keep-Alive',
            'Accept-Encoding': 'deflate, gzip'
        }

        try:
            major_login = MajoRLoGinrEq_pb2.MajorLogin()
            major_login.event_time = str(datetime.now())[:-7]
            major_login.game_name = "free fire"
            major_login.platform_id = 2
            major_login.client_version = "1.126.7"
            major_login.client_version_code = "2024010012"
            major_login.system_software = "Android OS 11 / API-30 (RQ3A.210805.001)"
            major_login.system_hardware = "Handheld"
            major_login.device_type = "Handheld"
            major_login.telecom_operator = "Verizon"
            major_login.network_operator_a = "Verizon"
            major_login.network_type = "WIFI"
            major_login.network_type_a = "WIFI"
            major_login.screen_width = 1080
            major_login.screen_height = 2400
            major_login.screen_dpi = "440"
            major_login.processor_details = "ARMv8"
            major_login.memory = 6144
            major_login.gpu_renderer = "Adreno (TM) 650"
            major_login.gpu_version = "OpenGL ES 3.2 V@1.50"
            major_login.graphics_api = "OpenGLES3"
            major_login.unique_device_id = "Google|34a7dcdf-a7d5-4cb6-8d7e-3b0e448a0c57"
            major_login.language = "en"
            major_login.open_id = Access_Uid
            major_login.open_id_type = "4"
            major_login.login_open_id_type = 4
            major_login.access_token = Access_ToKen
            major_login.login_by = 3
            major_login.platform_sdk_id = 2
            major_login.origin_platform_type = "4"
            major_login.primary_platform_type = "4"
            
            memory_available = major_login.memory_available
            memory_available.version = 55
            memory_available.hidden_value = 81
            
            major_login.external_storage_total = 128512
            major_login.external_storage_available = random.randint(38000, 52000)
            major_login.internal_storage_total = 110731
            major_login.internal_storage_available = random.randint(18000, 32000)
            major_login.game_disk_storage_total = 26628
            major_login.game_disk_storage_available = random.randint(18000, 28080)
            major_login.external_sdcard_total_storage = 119234
            major_login.external_sdcard_avail_storage = random.randint(28080, 60000)
            major_login.library_path = "/data/app/~~random/base.apk"
            major_login.library_token = "hash|base.apk"
            major_login.client_using_version = "7428b253defc164018c604a1ebbfebdf"
            major_login.supported_astc_bitset = 16383
            major_login.analytics_detail = b"FwQVTgUPX1UaUllDDwcWCRBpWAUOUgsvA1snWlBaO1kFYg=="
            major_login.loading_time = random.randint(9000, 18000)
            major_login.release_channel = "android"
            major_login.if_push = 1
            major_login.is_vpn = 0
            major_login.cpu_type = 2
            major_login.cpu_architecture = "64"
            major_login.android_engine_init_flag = 110009

            raw_data = major_login.SerializeToString()
            key = b'Yg&tc%DEuh6%Zc^8'
            iv = b'6oyZDr22E3ychjM%'
            cipher = AES.new(key, AES.MODE_CBC, iv)
            self.PaYload = cipher.encrypt(pad(raw_data, 16))

        except Exception as e:
            print(f"{R}❌ Protobuf building error: {e}{RS}")
            time.sleep(5)
            return self.ToKen_GeneRaTe(Access_ToKen, Access_Uid)

        self.ResPonse = requests.post(self.UrL, headers=self.HeadErs, data=self.PaYload, verify=False)        
        
        if self.ResPonse.status_code == 200:
            try:
                self.BesTo_data = json.loads(DeCode_PackEt(self.ResPonse.content.hex()))
                self.JwT_ToKen = self.BesTo_data['8']['data']           
                self.combined_timestamp, self.key, self.iv = self.GeT_Key_Iv(self.ResPonse.content)
                ip, port, ip2, port2 = self.GeT_LoGin_PorTs(self.JwT_ToKen, self.PaYload)            
                return self.JwT_ToKen, self.key, self.iv, self.combined_timestamp, ip, port, ip2, port2
            except Exception as e:
                print(f"{R}❌ Response parsing error: {e}{RS}")
                time.sleep(5)
                return self.ToKen_GeneRaTe(Access_ToKen, Access_Uid)
        else:
            print(f"{R}❌ Token generation error, status: {self.ResPonse.status_code}{RS}")
            time.sleep(5)
            return self.ToKen_GeneRaTe(Access_ToKen, Access_Uid)
      
    def Get_FiNal_ToKen_0115(self):
        try:
            result = self.Guest_GeneRaTe(self.id, self.password)
            if not result:
                print(f"{Y}⚠️ Failed to get token {self.id}, retrying...{RS}")
                time.sleep(5)
                return self.Get_FiNal_ToKen_0115()
                
            token, key, iv, Timestamp, ip, port, ip2, port2 = result
            
            if not all([ip, port, ip2, port2]):
                print(f"{Y}⚠️ Failed to get ports {self.id}, retrying...{RS}")
                time.sleep(5)
                return self.Get_FiNal_ToKen_0115()
                
            self.JwT_ToKen = token        
            try:
                self.AfTer_DeC_JwT = jwt.decode(token, options={"verify_signature": False})
                self.AccounT_Uid = self.AfTer_DeC_JwT.get('account_id')
                self.EncoDed_AccounT = hex(self.AccounT_Uid)[2:]
                self.HeX_VaLue = DecodE_HeX(Timestamp)
                self.TimE_HEx = self.HeX_VaLue
                self.JwT_ToKen_ = token.encode().hex()
                print(f'{C}🆔 Account UID: {self.AccounT_Uid}{RS}')
            except Exception as e:
                print(f"{R}❌ Token decode error {self.id}: {e}{RS}")
                time.sleep(5)
                return self.Get_FiNal_ToKen_0115()
                
            try:
                self.Header = hex(len(EnC_PacKeT(self.JwT_ToKen_, key, iv)) // 2)[2:]
                length = len(self.EncoDed_AccounT)
                self.__ = '00000000'
                if length == 9: self.__ = '0000000'
                elif length == 8: self.__ = '00000000'
                elif length == 10: self.__ = '000000'
                elif length == 7: self.__ = '000000000'
                self.Header = f'0115{self.__}{self.EncoDed_AccounT}{self.TimE_HEx}00000{self.Header}'
                self.FiNal_ToKen_0115 = self.Header + EnC_PacKeT(self.JwT_ToKen_, key, iv)
            except Exception as e:
                print(f"{R}❌ Final token error {self.id}: {e}{RS}")
                time.sleep(5)
                return self.Get_FiNal_ToKen_0115()
                
            self.AutH_ToKen = self.FiNal_ToKen_0115
            self.Connect_SerVer(self.JwT_ToKen, self.AutH_ToKen, ip, port, key, iv, ip2, port2)        
            return self.AutH_ToKen, key, iv
            
        except Exception as e:
            print(f"{R}❌ {self.id} connection failed: {e}{RS}")
            time.sleep(5)
            return self.Get_FiNal_ToKen_0115()

def start_account(account):
    try:
        print(f"{G}🚀 Logging in: {account['id']}{RS}")
        FF_CLient(account['id'], account['password'])
    except Exception as e:
        time.sleep(1)
        start_account(account)

def run_accounts():
    for acc in ACCOUNTS:
        Thread(target=start_account, args=(acc,), daemon=True).start()
        time.sleep(0.2)

def run_group_accounts():
    for acc in GROUP_ACCOUNTS:
        Thread(target=start_account, args=(acc,), daemon=True).start()
        time.sleep(0.2)

# ==================== FLASK ROUTES ====================
@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        password = request.form.get('password', '')
        if password == ADMIN_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('index'))
        return render_template_string(LOGIN_TEMPLATE, error='Invalid Password!')
    return render_template_string(LOGIN_TEMPLATE, error=None)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login_page'))

@app.route('/')
@login_required
def index():
    return render_template_string(HTML_TEMPLATE)

# ==================== API ROUTES (GET) ====================

# GET API - Full Spam
@app.route('/api/spam/all/<uid>', methods=['GET'])
@login_required
def api_get_full_spam(uid):
    """GET API: Start full spam on a target (room + squad + badge + group)"""
    if not uid or not uid.isdigit():
        return jsonify({'success': False, 'message': 'Invalid UID format!'}), 400
    
    success, message = start_spam(uid, 'full')
    return jsonify({'success': success, 'message': message})

# GET API - Squad Spam
@app.route('/api/spam/squad/<uid>', methods=['GET'])
@login_required
def api_get_squad_spam(uid):
    """GET API: Start squad spam on a target (group invites only)"""
    if not uid or not uid.isdigit():
        return jsonify({'success': False, 'message': 'Invalid UID format!'}), 400
    
    success, message = start_spam(uid, 'squad')
    return jsonify({'success': success, 'message': message})

# GET API - Stop Spam
@app.route('/api/stop/<uid>', methods=['GET'])
@login_required
def api_get_stop_spam(uid):
    """GET API: Stop spam on a target"""
    if not uid or not uid.isdigit():
        return jsonify({'success': False, 'message': 'Invalid UID format!'}), 400
    
    success, message = stop_spam(uid)
    return jsonify({'success': success, 'message': message})

# GET API - Stop All
@app.route('/api/stop-all', methods=['GET'])
@login_required
def api_get_stop_all():
    """GET API: Stop all spam"""
    success, message = stop_all_spam()
    return jsonify({'success': success, 'message': message})

# GET API - Status
@app.route('/api/status', methods=['GET'])
@login_required
def api_get_status():
    """GET API: Get spam status"""
    return jsonify({'success': True, 'data': get_spam_status()})

# GET API - Reset
@app.route('/api/reset', methods=['GET'])
@login_required
def api_get_reset():
    """GET API: Manually trigger auto reset"""
    success, message = trigger_manual_reset()
    return jsonify({'success': success, 'message': message})

# GET API - Accounts
@app.route('/api/accounts', methods=['GET'])
@login_required
def api_get_accounts():
    """GET API: Get connected accounts"""
    with connected_clients_lock:
        accounts = list(connected_clients.keys())
    return jsonify({'success': True, 'accounts': accounts})

# ==================== API ROUTES (POST) ====================

# POST API - Full Spam
@app.route('/api/spam/all', methods=['POST'])
@login_required
def api_post_full_spam():
    """POST API: Start full spam on target(s)"""
    data = request.get_json()
    uid = data.get('uid', '').strip()
    
    if not uid or not uid.isdigit():
        return jsonify({'success': False, 'message': 'Valid UID required!'}), 400
    
    if ',' in uid:
        uids = [u.strip() for u in uid.split(',') if u.strip().isdigit()]
    elif ' ' in uid:
        uids = [u.strip() for u in uid.split() if u.strip().isdigit()]
    else:
        uids = [uid]
    
    results = []
    for target in uids:
        success, message = start_spam(target, 'full')
        results.append({'uid': target, 'success': success, 'message': message})
    
    return jsonify({'success': True, 'results': results})

# POST API - Squad Spam
@app.route('/api/spam/squad', methods=['POST'])
@login_required
def api_post_squad_spam():
    """POST API: Start squad spam on target(s)"""
    data = request.get_json()
    uid = data.get('uid', '').strip()
    
    if not uid or not uid.isdigit():
        return jsonify({'success': False, 'message': 'Valid UID required!'}), 400
    
    if ',' in uid:
        uids = [u.strip() for u in uid.split(',') if u.strip().isdigit()]
    elif ' ' in uid:
        uids = [u.strip() for u in uid.split() if u.strip().isdigit()]
    else:
        uids = [uid]
    
    results = []
    for target in uids:
        success, message = start_spam(target, 'squad')
        results.append({'uid': target, 'success': success, 'message': message})
    
    return jsonify({'success': True, 'results': results})

# POST API - Stop Spam
@app.route('/api/stop', methods=['POST'])
@login_required
def api_post_stop_spam():
    """POST API: Stop spam on a target"""
    data = request.get_json()
    uid = data.get('uid', '').strip()
    
    if not uid or not uid.isdigit():
        return jsonify({'success': False, 'message': 'Valid UID required!'}), 400
    
    success, message = stop_spam(uid)
    return jsonify({'success': success, 'message': message})

# POST API - Stop All
@app.route('/api/stop-all', methods=['POST'])
@login_required
def api_post_stop_all():
    """POST API: Stop all spam"""
    success, message = stop_all_spam()
    return jsonify({'success': success, 'message': message})

# POST API - Reset
@app.route('/api/reset', methods=['POST'])
@login_required
def api_post_reset():
    """POST API: Manually trigger auto reset"""
    success, message = trigger_manual_reset()
    return jsonify({'success': success, 'message': message})

# ==================== LOGIN TEMPLATE ====================
LOGIN_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MAHIR SYSTEM | Secure Login</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Rajdhani:wght@500;700&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Rajdhani', sans-serif; }
        body {
            background: #05050a;
            color: #fff;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
            overflow: hidden;
        }
        #matrix-canvas { position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; z-index: 0; }
        .login-box {
            background: rgba(10, 10, 25, 0.8);
            border: 1px solid rgba(255, 0, 127, 0.3);
            border-radius: 16px;
            padding: 50px 35px;
            width: 100%;
            max-width: 420px;
            backdrop-filter: blur(15px);
            text-align: center;
            position: relative;
            z-index: 1;
            box-shadow: 0 0 60px rgba(255, 0, 127, 0.1);
        }
        .login-box h1 {
            font-family: 'Orbitron', sans-serif;
            font-size: 2.2rem;
            background: linear-gradient(135deg, #ff007f, #7f00ff);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 5px;
        }
        .login-box p.sub {
            color: #00ffcc;
            text-transform: uppercase;
            letter-spacing: 4px;
            margin-bottom: 35px;
            font-size: 0.85rem;
        }
        .input-group {
            position: relative;
            margin-bottom: 25px;
        }
        .input-group i {
            position: absolute;
            left: 15px;
            top: 50%;
            transform: translateY(-50%);
            color: rgba(255,255,255,0.3);
            font-size: 1.1rem;
        }
        .input-group input {
            width: 100%;
            padding: 15px 15px 15px 45px;
            background: rgba(0, 0, 0, 0.5);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 10px;
            color: #fff;
            font-size: 1.1rem;
            outline: none;
            transition: 0.3s;
        }
        .input-group input:focus {
            border-color: #ff007f;
            box-shadow: 0 0 20px rgba(255, 0, 127, 0.15);
        }
        .btn-login {
            width: 100%;
            padding: 16px;
            background: linear-gradient(135deg, #ff007f, #7f00ff);
            border: none;
            border-radius: 10px;
            color: #fff;
            font-size: 1.2rem;
            font-weight: 700;
            cursor: pointer;
            transition: 0.3s;
            letter-spacing: 2px;
        }
        .btn-login:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 30px rgba(255, 0, 127, 0.3);
        }
        .error { color: #ff4444; margin-top: 15px; font-weight: 600; }
        .footer-text { color: rgba(255,255,255,0.2); font-size: 0.7rem; margin-top: 20px; letter-spacing: 1px; }
    </style>
</head>
<body>
    <canvas id="matrix-canvas"></canvas>
    <div class="login-box">
        <h1>MAHIR SYSTEM</h1>
        <p class="sub">Access Control Panel</p>
        <form action="/login" method="POST">
            <div class="input-group">
                <i class="fas fa-key"></i>
                <input type="password" name="password" placeholder="Enter Security Password" required>
            </div>
            <button type="submit" class="btn-login"><i class="fas fa-unlock-alt"></i> UNLOCK</button>
            {% if error %}<div class="error"><i class="fas fa-exclamation-circle"></i> {{ error }}</div>{% endif %}
        </form>
        <div class="footer-text">MAHIR ENGINE v3.0</div>
    </div>
    <script>
        const canvas = document.getElementById('matrix-canvas');
        const ctx = canvas.getContext('2d');
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
        const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789@#$%&'.split('');
        const fontSize = 14;
        const columns = canvas.width / fontSize;
        const drops = Array(Math.floor(columns)).fill(1);

        function drawMatrix() {
            ctx.fillStyle = 'rgba(5, 5, 10, 0.05)';
            ctx.fillRect(0, 0, canvas.width, canvas.height);
            ctx.fillStyle = '#ff007f';
            ctx.font = fontSize + 'px monospace';
            drops.forEach((y, i) => {
                const text = chars[Math.floor(Math.random() * chars.length)];
                ctx.fillText(text, i * fontSize, y * fontSize);
                if (y * fontSize > canvas.height && Math.random() > 0.975) drops[i] = 0;
                drops[i]++;
            });
        }
        setInterval(drawMatrix, 35);
        window.addEventListener('resize', () => { canvas.width = window.innerWidth; canvas.height = window.innerHeight; });
    </script>
</body>
</html>
'''

# ==================== HTML TEMPLATE ====================
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🔥 MAHIR SYSTEM - SPAM CONTROL</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Inter', sans-serif;
            background: linear-gradient(135deg, #060417, #0e0b30, #130a24);
            min-height: 100vh;
            color: #fff;
            padding: 20px;
        }
        #matrix-canvas { position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; z-index: 0; opacity: 0.3; }
        .container { max-width: 1400px; margin: 0 auto; position: relative; z-index: 1; }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; border-bottom: 1px solid rgba(255,255,255,0.05); padding-bottom: 20px; flex-wrap: wrap; gap: 15px;}
        .logo { font-size: 2.5rem; font-weight: 800; background: linear-gradient(135deg, #ff007f, #7f00ff); -webkit-background-clip: text; -webkit-text-fill-color: transparent; text-shadow: 0 0 30px rgba(255,0,127,0.15); }
        .logo i { -webkit-text-fill-color: initial; color: #ff007f; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .stat-card { background: rgba(255,255,255,0.03); backdrop-filter: blur(15px); border-radius: 16px; padding: 20px; text-align: center; border: 1px solid rgba(255,255,255,0.06); box-shadow: 0 8px 32px rgba(0,0,0,0.3); transition: 0.3s; }
        .stat-card:hover { transform: translateY(-3px); border-color: rgba(255,0,127,0.2); }
        .stat-card i { font-size: 2rem; margin-bottom: 8px; color: #ff007f; }
        .stat-card h3 { font-size: 0.75rem; color: rgba(255,255,255,0.4); margin-bottom: 5px; text-transform: uppercase; letter-spacing: 1px; }
        .stat-card .value { font-size: 2rem; font-weight: 800; }
        .controls-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .control-card { background: rgba(255,255,255,0.02); backdrop-filter: blur(15px); border-radius: 16px; padding: 25px; border: 1px solid rgba(255,255,255,0.06); box-shadow: 0 8px 32px rgba(0,0,0,0.3); }
        .control-card h3 { font-size: 1rem; margin-bottom: 15px; display: flex; align-items: center; gap: 10px; }
        .control-card h3 i { color: #ff007f; }
        .input-group { display: flex; gap: 10px; flex-wrap: wrap; }
        .input-group input { flex: 1; padding: 12px 16px; border: 1px solid rgba(255,255,255,0.08); border-radius: 10px; background: rgba(0,0,0,0.4); color: #fff; font-size: 0.95rem; font-family: monospace; outline: none; transition: 0.3s; min-width: 150px; }
        .input-group input:focus { border-color: #ff007f; box-shadow: 0 0 15px rgba(255,0,127,0.1); }
        .btn { padding: 12px 24px; border: none; border-radius: 10px; font-weight: 600; cursor: pointer; transition: all 0.3s; font-size: 0.9rem; display: inline-flex; align-items: center; gap: 8px; }
        .btn-primary { background: linear-gradient(135deg, #ff007f, #7f00ff); color: #fff; }
        .btn-primary:hover { transform: translateY(-2px); box-shadow: 0 5px 20px rgba(255,0,127,0.3); }
        .btn-success { background: linear-gradient(135deg, #00b09b, #96c93d); color: #fff; }
        .btn-success:hover { transform: translateY(-2px); box-shadow: 0 5px 20px rgba(0,176,155,0.3); }
        .btn-danger { background: linear-gradient(135deg, #ff0844, #ffb199); color: #fff; }
        .btn-danger:hover { transform: translateY(-2px); box-shadow: 0 5px 20px rgba(255,8,68,0.3); }
        .btn-warning { background: linear-gradient(135deg, #ffaa00, #ff6600); color: #000; }
        .btn-warning:hover { transform: translateY(-2px); box-shadow: 0 5px 20px rgba(255,170,0,0.3); }
        .btn-purple { background: linear-gradient(135deg, #8e44ad, #9b59b6); color: #fff; }
        .btn-purple:hover { transform: translateY(-2px); box-shadow: 0 5px 20px rgba(155,89,182,0.3); }
        .btn-outline { background: transparent; border: 1px solid rgba(255,255,255,0.15); color: #fff; }
        .btn-outline:hover { background: rgba(255,255,255,0.05); }
        .btn-sm { padding: 8px 14px; font-size: 0.8rem; }
        .active-list { max-height: 400px; overflow-y: auto; margin-top: 10px; }
        .active-item { background: rgba(30,30,40,0.6); padding: 12px 16px; margin: 6px 0; border-radius: 10px; display: flex; justify-content: space-between; align-items: center; border-left: 3px solid #ff007f; }
        .active-uid { font-family: monospace; font-weight: bold; color: #ff007f; font-size: 14px; }
        .active-type { font-size: 11px; color: rgba(255,255,255,0.4); background: rgba(255,255,255,0.05); padding: 2px 10px; border-radius: 12px; }
        .stop-small { background: #eb3349; color: white; border: none; padding: 5px 14px; border-radius: 8px; cursor: pointer; font-size: 11px; font-weight: bold; transition: 0.2s; }
        .stop-small:hover { background: #c0392b; }
        .account-item { background: rgba(30,30,40,0.4); padding: 4px 12px; margin: 3px 0; border-radius: 6px; font-family: monospace; font-size: 11px; color: #4facfe; display: inline-block; margin-right: 5px; }
        .console-box { background: rgba(0,0,0,0.5); border: 1px solid rgba(255,255,255,0.05); border-radius: 12px; height: 180px; padding: 15px; font-family: 'Courier New', monospace; font-size: 0.75rem; color: #00ffcc; overflow-y: auto; text-align: left; }
        .console-line { margin-bottom: 4px; }
        .console-line .time { color: rgba(255,255,255,0.3); margin-right: 10px; }
        .console-line .success { color: #00ffcc; }
        .console-line .error { color: #ff3366; }
        .console-line .info { color: #4facfe; }
        .badge-info { background: rgba(155,89,182,0.08); color: #9b59b6; border: 1px solid rgba(155,89,182,0.15); padding: 10px; border-radius: 10px; text-align: center; font-size: 0.8rem; margin-top: 10px; }
        .status-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; margin-right: 5px; }
        .status-dot.active { background: #00ffcc; animation: pulse 1s infinite; }
        .status-dot.idle { background: #ff4444; }
        @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-track { background: rgba(255,255,255,0.02); border-radius: 10px; }
        ::-webkit-scrollbar-thumb { background: #ff007f; border-radius: 10px; }
        .footer { text-align: center; color: rgba(255,255,255,0.15); font-size: 0.7rem; margin-top: 30px; padding-top: 20px; border-top: 1px solid rgba(255,255,255,0.03); }
        .toast { position: fixed; bottom: 20px; right: 20px; background: rgba(0,0,0,0.9); padding: 15px 25px; border-radius: 10px; z-index: 999; animation: slideIn 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards; border: 1px solid rgba(255,255,255,0.1); box-shadow: 0 10px 30px rgba(0,0,0,0.5); color:#fff; display:flex; align-items:center; gap:10px; font-weight:500; backdrop-filter: blur(10px); }
        .toast.success { border-color: #00b09b; }
        .toast.error { border-color: #ff0844; }
        .toast.info { border-color: #4facfe; }
        @keyframes slideIn { from { transform: translateX(100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
        .spam-type-toggle { display: flex; gap: 10px; margin: 10px 0; }
        .spam-type-btn { flex: 1; padding: 8px; background: rgba(30,30,40,0.4); border: 1px solid rgba(255,255,255,0.06); border-radius: 8px; cursor: pointer; text-align: center; transition: 0.3s; font-size: 0.8rem; }
        .spam-type-btn.active { background: linear-gradient(135deg, #ff007f, #7f00ff); border-color: #ff007f; }
        .spam-type-btn:hover { border-color: rgba(255,0,127,0.3); }
        .api-hint { background: rgba(0,212,255,0.05); border: 1px dashed rgba(0,212,255,0.2); border-radius: 8px; padding: 8px 12px; font-size: 0.7rem; color: rgba(255,255,255,0.4); margin-top: 10px; font-family: monospace; overflow-x: auto; white-space: nowrap; }
        @media (max-width: 768px) { .controls-grid { grid-template-columns: 1fr; } .input-group { flex-direction: column; } .btn { width: 100%; justify-content: center; } .header { flex-direction: column; text-align: center; } }
    </style>
</head>
<body>
    <canvas id="matrix-canvas"></canvas>
    <div class="container">
        <div class="header">
            <div>
                <div class="logo"><i class="fas fa-bolt"></i> MAHIR SYSTEM</div>
                <div style="color: rgba(255,255,255,0.3); font-size:0.85rem;">SPAM CONTROL ENGINE v3.0</div>
            </div>
            <a href="/logout" class="btn btn-outline btn-sm"><i class="fas fa-sign-out-alt"></i> LOGOUT</a>
        </div>

        <div class="stats-grid">
            <div class="stat-card"><i class="fas fa-bullseye"></i><h3>ACTIVE TARGETS</h3><div class="value" id="activeCount">0</div></div>
            <div class="stat-card"><i class="fas fa-robot"></i><h3>BOT ACCOUNTS</h3><div class="value" id="botCount">0</div></div>
            <div class="stat-card"><i class="fas fa-users"></i><h3>GROUP ACCOUNTS</h3><div class="value" id="groupCount">0</div></div>
            <div class="stat-card"><i class="fas fa-clock"></i><h3>AUTO RESET</h3><div class="value" style="font-size:1.2rem;">2 HOURS</div></div>
        </div>

        <div class="controls-grid">
            <!-- Full Spam Control -->
            <div class="control-card">
                <h3><i class="fas fa-fire"></i> FULL SPAM</h3>
                <div style="font-size:0.75rem; color:rgba(255,255,255,0.4); margin-bottom:10px;">Room + Squad + Badge + Group Invites</div>
                <div class="input-group">
                    <input type="text" id="fullUid" placeholder="Target UID(s) (comma separated)">
                    <button class="btn btn-primary" onclick="startFullSpam()"><i class="fas fa-play"></i> START</button>
                </div>
                <div class="api-hint">GET: /api/spam/all/&lt;UID&gt; | POST: /api/spam/all</div>
            </div>

            <!-- Squad Spam Control -->
            <div class="control-card">
                <h3><i class="fas fa-users"></i> SQUAD SPAM</h3>
                <div style="font-size:0.75rem; color:rgba(255,255,255,0.4); margin-bottom:10px;">Group Invites Only (3, 5, 6 Player)</div>
                <div class="input-group">
                    <input type="text" id="squadUid" placeholder="Target UID(s) (comma separated)">
                    <button class="btn btn-success" onclick="startSquadSpam()"><i class="fas fa-play"></i> START</button>
                </div>
                <div class="api-hint">GET: /api/spam/squad/&lt;UID&gt; | POST: /api/spam/squad</div>
            </div>
        </div>

        <div class="controls-grid">
            <!-- Stop Controls -->
            <div class="control-card">
                <h3><i class="fas fa-stop"></i> STOP SPAM</h3>
                <div class="input-group">
                    <input type="text" id="stopUid" placeholder="Target UID to stop">
                    <button class="btn btn-danger" onclick="stopSingleSpam()"><i class="fas fa-power-off"></i> STOP</button>
                </div>
                <div style="display:flex; gap:10px; margin-top:12px; flex-wrap:wrap;">
                    <button class="btn btn-warning" onclick="stopAllSpam()" style="flex:1;"><i class="fas fa-stop-circle"></i> STOP ALL</button>
                    <button class="btn btn-purple" onclick="triggerReset()" style="flex:1;"><i class="fas fa-sync"></i> RESET NOW</button>
                </div>
                <div class="api-hint">GET: /api/stop/&lt;UID&gt; | GET: /api/stop-all | GET: /api/reset</div>
            </div>

            <!-- File Info -->
            <div class="control-card">
                <h3><i class="fas fa-file"></i> ACCOUNT FILES</h3>
                <div style="background:rgba(0,0,0,0.3); padding:12px; border-radius:8px; font-size:0.85rem;">
                    <div><span style="color:#00ffcc;">📁 accs.txt</span> <span id="accCount" style="color:rgba(255,255,255,0.4);">0 accounts</span> <span style="color:rgba(255,255,255,0.2);">→ Room Spam</span></div>
                    <div><span style="color:#ffaa00;">📁 group.txt</span> <span id="groupFileCount" style="color:rgba(255,255,255,0.4);">0 accounts</span> <span style="color:rgba(255,255,255,0.2);">→ Squad Spam</span></div>
                    <div style="font-size:0.7rem; color:rgba(255,255,255,0.2); margin-top:8px;">Place accounts in these files to enable spam</div>
                </div>
            </div>
        </div>

        <!-- Active Targets -->
        <div class="control-card" style="margin-bottom:30px;">
            <h3><i class="fas fa-list"></i> ACTIVE TARGETS</h3>
            <div id="activeList" class="active-list">
                <div style="color:rgba(255,255,255,0.3); text-align:center; padding:20px;">No active targets</div>
            </div>
        </div>

        <!-- Console -->
        <div class="control-card" style="margin-bottom:30px;">
            <h3><i class="fas fa-terminal"></i> CONSOLE</h3>
            <div class="console-box" id="consoleBox">
                <div class="console-line"><span class="time">[System]</span> <span class="info">MAHIR SPAM ENGINE Initialized</span></div>
                <div class="console-line"><span class="time">[System]</span> <span class="info">Auto-reset every 2 hours</span></div>
            </div>
        </div>

        <!-- Connected Accounts -->
        <div class="control-card">
            <h3><i class="fas fa-robot"></i> CONNECTED ACCOUNTS</h3>
            <div id="accountsContainer">
                <span style="color:rgba(255,255,255,0.3); font-size:0.85rem;">Loading...</span>
            </div>
        </div>

        <div class="footer">
            MAHIR SYSTEM v3.0 | <i class="fas fa-code"></i> Engine by MAHIR | Auto Reset: 2 Hours
        </div>
    </div>

    <script>
        // Matrix Background
        const canvas = document.getElementById('matrix-canvas');
        const ctx = canvas.getContext('2d');
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
        const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789@#$%&'.split('');
        const fontSize = 12;
        const columns = canvas.width / fontSize;
        const drops = Array(Math.floor(columns)).fill(1);

        function drawMatrix() {
            ctx.fillStyle = 'rgba(5, 5, 10, 0.05)';
            ctx.fillRect(0, 0, canvas.width, canvas.height);
            ctx.fillStyle = '#ff007f';
            ctx.font = fontSize + 'px monospace';
            drops.forEach((y, i) => {
                const text = chars[Math.floor(Math.random() * chars.length)];
                ctx.globalAlpha = 0.3 + Math.random() * 0.3;
                ctx.fillText(text, i * fontSize, y * fontSize);
                ctx.globalAlpha = 1;
                if (y * fontSize > canvas.height && Math.random() > 0.975) drops[i] = 0;
                drops[i]++;
            });
        }
        setInterval(drawMatrix, 50);

        // Toast notifications
        function showToast(msg, type = 'info') {
            const toast = document.createElement('div');
            toast.className = `toast ${type}`;
            const icons = { success: 'fa-check-circle', error: 'fa-exclamation-circle', info: 'fa-info-circle' };
            toast.innerHTML = `<i class="fas ${icons[type] || icons.info}"></i> ${msg}`;
            document.body.appendChild(toast);
            setTimeout(() => toast.remove(), 4000);
        }

        // Console log
        function logToConsole(msg, type = 'info') {
            const consoleBox = document.getElementById('consoleBox');
            const now = new Date();
            const timeStr = now.toLocaleTimeString();
            const line = document.createElement('div');
            line.className = 'console-line';
            line.innerHTML = `<span class="time">[${timeStr}]</span> <span class="${type}">${msg}</span>`;
            consoleBox.appendChild(line);
            consoleBox.scrollTop = consoleBox.scrollHeight;
            if (consoleBox.children.length > 100) consoleBox.removeChild(consoleBox.children[0]);
        }

        // Start Full Spam
        function startFullSpam() {
            const uid = document.getElementById('fullUid').value.trim();
            if (!uid) { showToast('Enter target UID(s)!', 'error'); return; }
            
            const uids = uid.split(',').map(u => u.trim()).filter(u => /^\\d+$/.test(u));
            if (uids.length === 0) { showToast('Invalid UID(s)!', 'error'); return; }

            logToConsole(`🚀 Starting FULL spam on ${uids.length} target(s): ${uids.join(', ')}`, 'info');
            
            fetch('/api/spam/all', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ uid: uid })
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    showToast(`Started full spam on ${uids.length} target(s)`, 'success');
                    refreshStatus();
                } else {
                    showToast(data.message || 'Failed to start spam', 'error');
                }
            })
            .catch(err => { showToast('Error: ' + err.message, 'error'); });
        }

        // Start Squad Spam
        function startSquadSpam() {
            const uid = document.getElementById('squadUid').value.trim();
            if (!uid) { showToast('Enter target UID(s)!', 'error'); return; }
            
            const uids = uid.split(',').map(u => u.trim()).filter(u => /^\\d+$/.test(u));
            if (uids.length === 0) { showToast('Invalid UID(s)!', 'error'); return; }

            logToConsole(`🚀 Starting SQUAD spam on ${uids.length} target(s): ${uids.join(', ')}`, 'info');
            
            fetch('/api/spam/squad', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ uid: uid })
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    showToast(`Started squad spam on ${uids.length} target(s)`, 'success');
                    refreshStatus();
                } else {
                    showToast(data.message || 'Failed to start spam', 'error');
                }
            })
            .catch(err => { showToast('Error: ' + err.message, 'error'); });
        }

        // Stop Single Spam
        function stopSingleSpam() {
            const uid = document.getElementById('stopUid').value.trim();
            if (!uid) { showToast('Enter target UID to stop!', 'error'); return; }
            if (!/^\\d+$/.test(uid)) { showToast('Invalid UID!', 'error'); return; }

            logToConsole(`🛑 Stopping spam on ${uid}`, 'info');
            
            fetch(`/api/stop/${uid}`)
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    showToast(data.message, 'success');
                    document.getElementById('stopUid').value = '';
                    refreshStatus();
                } else {
                    showToast(data.message, 'error');
                }
            })
            .catch(err => { showToast('Error: ' + err.message, 'error'); });
        }

        // Stop All Spam
        function stopAllSpam() {
            if (!confirm('⚠️ Stop all spam?')) return;
            
            logToConsole('🛑 Stopping ALL spam', 'info');
            
            fetch('/api/stop-all')
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    showToast(data.message, 'success');
                    refreshStatus();
                }
            })
            .catch(err => { showToast('Error: ' + err.message, 'error'); });
        }

        // Trigger Reset
        function triggerReset() {
            if (!confirm('🔄 Manually trigger auto reset? This will stop all spam and reload accounts.')) return;
            
            logToConsole('🔄 Triggering manual reset...', 'info');
            
            fetch('/api/reset')
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    showToast(data.message, 'success');
                    refreshStatus();
                }
            })
            .catch(err => { showToast('Error: ' + err.message, 'error'); });
        }

        // Refresh Status
        function refreshStatus() {
            fetch('/api/status')
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    const status = data.data;
                    document.getElementById('activeCount').textContent = status.active_count || 0;
                    document.getElementById('botCount').textContent = status.accounts_count || 0;
                    
                    const activeList = document.getElementById('activeList');
                    if (status.active_targets && status.active_targets.length > 0) {
                        activeList.innerHTML = status.active_targets.map(target => `
                            <div class="active-item">
                                <div>
                                    <span class="active-uid">🎯 ${target.uid}</span>
                                    <span class="active-type">${target.type.toUpperCase()}</span>
                                    <div style="font-size:10px; color:rgba(255,255,255,0.3);">${target.elapsed_minutes}m running</div>
                                </div>
                                <button class="stop-small" onclick="quickStop('${target.uid}')">STOP</button>
                            </div>
                        `).join('');
                    } else {
                        activeList.innerHTML = '<div style="color:rgba(255,255,255,0.3); text-align:center; padding:20px;">No active targets</div>';
                    }
                }
            })
            .catch(err => console.error('Status refresh error:', err));

            // Refresh accounts
            fetch('/api/accounts')
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    const container = document.getElementById('accountsContainer');
                    if (data.accounts && data.accounts.length > 0) {
                        container.innerHTML = data.accounts.map(acc => 
                            `<span class="account-item">${acc}</span>`
                        ).join('');
                    } else {
                        container.innerHTML = '<span style="color:rgba(255,255,255,0.3); font-size:0.85rem;">No accounts connected</span>';
                    }
                }
            })
            .catch(err => console.error('Accounts refresh error:', err));
        }

        function quickStop(uid) {
            document.getElementById('stopUid').value = uid;
            stopSingleSpam();
        }

        // Auto refresh every 5 seconds
        setInterval(refreshStatus, 5000);
        refreshStatus();

        // Enter key support
        document.getElementById('fullUid').addEventListener('keypress', (e) => { if (e.key === 'Enter') startFullSpam(); });
        document.getElementById('squadUid').addEventListener('keypress', (e) => { if (e.key === 'Enter') startSquadSpam(); });
        document.getElementById('stopUid').addEventListener('keypress', (e) => { if (e.key === 'Enter') stopSingleSpam(); });
    </script>
</body>
</html>
'''

# ==================== MAIN ====================
def main():
    print(f"""
    {C}{BOLD}
    ╔══════════════════════════════════════════════════════════════════════╗
    ║              🎯 MAHIR SPAM SYSTEM v3.0 🎯                           ║
    ║                                                                      ║
    ║     📁 accs.txt     → Room + Squad + Badge + Group Spam              ║
    ║     📁 group.txt    → Squad Creation + Group Invite                  ║
    ║                                                                      ║
    ║     ✅ Full Spam: Room + Squad + Badge + Group Invite               ║
    ║     ✅ Squad Spam: Group Invites Only (3, 5, 6 Player)              ║
    ║     ✅ Auto Reset: Every 2 Hours                                    ║
    ║     ✅ GET/POST API Support                                         ║
    ║                                                                      ║
    ║     🌐 Web Panel: http://127.0.0.1:8080                            ║
    ║     🔑 Password: torikul                                            ║
    ║     👑 Developer: MAHIR                                             ║
    ╚══════════════════════════════════════════════════════════════════════╝
    {RS}
    """)
    
    # Start accounts
    Thread(target=run_accounts, daemon=True).start()
    Thread(target=run_group_accounts, daemon=True).start()
    
    # Start auto reset
    start_auto_reset()
    
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)

if __name__ == "__main__":
    try:
        import aiohttp
    except ImportError:
        os.system("pip install aiohttp")
    
    main()