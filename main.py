import os, sys, time, json, socket, threading, asyncio, re, jwt, random
from datetime import datetime, timedelta
from threading import Thread
from flask import Flask, request, jsonify, render_template_string, session, redirect, url_for, send_from_directory, Response
from functools import wraps
import requests
import urllib3
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from google.protobuf.timestamp_pb2 import Timestamp

# ========== আপনার কাস্টম মডিউল ==========
from Pb2 import MajoRLoGinrEq_pb2
from byte import *
from byte import xSEndMsg, Auth_Chat
from xHeaders import *
from black9 import openroom, spmroom
import xKEys

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==================== LOGIN REQUIRED DECORATOR ====================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function

# ==================== কনফিগ ====================
ADMIN_PASSWORD = "MAHIRJOD"
SECRET_KEY = "mahir_system_secret_key_2024"
AUTO_RESET_INTERVAL = 2 * 60 * 60  # 2 ঘণ্টা
SSE_INTERVAL = 2  # সেকেন্ড

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024

# ==================== গ্লোবাল ভেরিয়েবল ====================
connected_clients = {}
connected_clients_lock = threading.Lock()
active_spam_targets = {}
active_spam_lock = threading.Lock()
spam_threads = {}
spam_threads_lock = threading.Lock()
accounts_initialized = False
accounts_initializing = False
auto_reset_timer = None

ACCOUNTS_FILE = "accs.txt"
GROUP_ACCOUNTS_FILE = "group.txt"

C = "\033[96m"; G = "\033[92m"; Y = "\033[93m"; R = "\033[91m"; RS = "\033[0m"; BOLD = "\033[1m"

# ==================== ব্যাজ ও গ্রুপ কনফিগ ====================
BADGES = {"V_BADGE": 32768, "PRO_BADGE": 262144, "CRAFTLAND": 1048576, "MODERATOR": 2048, "SMALL_V": 64}
GROUP_CONFIGS = {3: {"type": 1, "players": 3}, 5: {"type": 2, "players": 5}, 6: {"type": 3, "players": 6}}

# ==================== অ্যাকাউন্ট লোডার ====================
def load_accounts_from_text(content):
    accounts = []
    for line in content.split('\n'):
        line = line.strip()
        if line and not line.startswith("#"):
            if ":" in line:
                uid, pwd = line.split(":", 1)
            else:
                uid, pwd = line, ""
            if uid.isdigit():
                accounts.append({'id': uid.strip(), 'password': pwd.strip()})
    return accounts

def load_accounts(filename="accs.txt"):
    if not os.path.exists(filename):
        with open(filename, "w") as f:
            f.write("# UID:PASSWORD\n")
        return []
    with open(filename, "r", encoding="utf-8") as f:
        return load_accounts_from_text(f.read())

def load_group_accounts(filename="group.txt"):
    if not os.path.exists(filename):
        with open(filename, "w") as f:
            f.write("# UID:PASSWORD\n")
        return []
    with open(filename, "r", encoding="utf-8") as f:
        return load_accounts_from_text(f.read())

ACCOUNTS = load_accounts(ACCOUNTS_FILE)
GROUP_ACCOUNTS = load_group_accounts(GROUP_ACCOUNTS_FILE)

# ==================== প্যাকেট ক্রিয়েটর (শুধু ব্যাজ ও গ্রুপ ইনভাইট) ====================
def create_group_invite_packet(key, iv, target_uid, players=5, region="BD"):
    try:
        group_type = GROUP_CONFIGS[players]["type"]
        proto_fields = {
            1: 33,
            2: {
                1: int(target_uid), 2: region.upper(), 3: 1, 4: 1,
                5: bytes([1,7,9,10,11,18,25,26,32]),
                6: "[C][B][FF0000] INVITE",
                7: 330, 8: 1000, 10: region.upper(),
                11: bytes.fromhex("61"*32),
                12: 1, 13: int(target_uid),
                14: {1: random.randint(1000000000,9999999999), 2: group_type,
                     3: "\u0010\u0015\b\n\u000b\u0013\f\u000f\u0011\u0004\u0007\u0002\u0003\r\u000e\u0012\u0001\u0005\u0006"},
                16: 1, 17: 1, 18: 312, 19: 46,
                23: bytes([16,1,24,1]),
                24: random.randint(902000000,902050099),
                26: "", 28: ""
            },
            10: "en",
            13: {2:1, 3:1}
        }
        packet = CrEaTe_ProTo(proto_fields).hex()
        ptype = "0519" if region.lower()=="bd" else "0515"
        encrypted = EnC_PacKeT(packet, key, iv)
        length = len(encrypted)//2
        len_hex = DecodE_HeX(length)
        padding = {2:"000000",3:"00000",4:"0000",5:"000"}.get(len(len_hex), "000")
        return bytes.fromhex(ptype + padding + len_hex + encrypted)
    except:
        return None

def create_badge_join_packet(key, iv, target_uid, badge_value, region="BD"):
    try:
        avatar = random.choice([902000011,902000013,902047016,902049015,902000154,902000127,902000207,902000305,902037031,902042011,902053016,902053018])
        proto_fields = {
            1: 33,
            2: {
                1: int(target_uid), 2: region.upper(), 3:1, 4:1,
                5: bytes([1,7,9,10,11,18,25,26,32]),
                6: "[C][B][FF0000] MAHIR BADGE",
                7:330, 8:1000, 10: region.upper(),
                11: bytes.fromhex("61"*32), 12:1, 13:int(target_uid),
                14: {1: random.randint(1000000000,9999999999), 2:8,
                     3: "\u0010\u0015\b\n\u000b\u0013\f\u000f\u0011\u0004\u0007\u0002\u0003\r\u000e\u0012\u0001\u0005\u0006"},
                16:1,17:1,18:312,19:46,
                23: bytes([16,1,24,1]),
                24: avatar, 26:"", 28:"",
                31:{1:1,2:badge_value}, 32:badge_value,
                34:{1:int(target_uid),2:8,3:bytes([15,6,21,8,10,11,19,12,17,4,14,20,7,2,1,5,16,3,13,18])}
            },
            10:"en",
            13:{2:1,3:1}
        }
        packet = CrEaTe_ProTo(proto_fields).hex()
        ptype = "0519" if region.lower()=="bd" else "0515"
        encrypted = EnC_PacKeT(packet, key, iv)
        length = len(encrypted)//2
        len_hex = DecodE_HeX(length)
        padding = {2:"000000",3:"00000",4:"0000",5:"000"}.get(len(len_hex), "000")
        return bytes.fromhex(ptype + padding + len_hex + encrypted)
    except:
        return None

# ==================== স্প্যাম ওয়ার্কার (অপটিমাইজড) ====================
# একক ইভেন্ট লুপ শেয়ার করার জন্য
_loop = asyncio.new_event_loop()

def run_async(coro):
    return _loop.run_until_complete(coro)

def send_full_spam(client, target_uid):
    total = 0
    try:
        if not hasattr(client, 'CliEnts2') or not client.key:
            return 0
        # রুম স্প্যাম
        try:
            open_pkt = openroom(client.key, client.iv)
            if open_pkt:
                client.CliEnts2.send(open_pkt)
            spam_pkt = spmroom(client.key, client.iv, target_uid)
            if spam_pkt:
                client.CliEnts2.send(spam_pkt)
                total += 1
        except:
            pass
        # স্কোয়াড ইনভাইট
        try:
            p1 = OpEnSq(client.key, client.iv, "BD")
            client.CliEnts2.send(p1)
            time.sleep(0.03)
            p2 = cHSq(5, target_uid, client.key, client.iv, "BD")
            client.CliEnts2.send(p2)
            time.sleep(0.03)
            p3 = SEnd_InV(5, target_uid, client.key, client.iv, "BD")
            client.CliEnts2.send(p3)
            time.sleep(0.03)
            p4 = ExiT(client.key, client.iv)
            client.CliEnts2.send(p4)
            total += 1
        except:
            pass
        # ব্যাজ জয়েন
        for badge_value in BADGES.values():
            try:
                pkt = create_badge_join_packet(client.key, client.iv, target_uid, badge_value)
                if pkt:
                    client.CliEnts2.send(pkt)
                    total += 1
                    time.sleep(0.02)
            except:
                pass
        # গ্রুপ ইনভাইট
        for players in [3,5,6]:
            try:
                pkt = create_group_invite_packet(client.key, client.iv, target_uid, players)
                if pkt:
                    client.CliEnts2.send(pkt)
                    total += 1
                    time.sleep(0.02)
            except:
                pass
    except:
        pass
    return total

def send_squad_spam(client, target_uid):
    total = 0
    try:
        if not hasattr(client, 'CliEnts2') or not client.key:
            return 0
        try:
            p1 = OpEnSq(client.key, client.iv, "BD")
            client.CliEnts2.send(p1)
            time.sleep(0.03)
            p2 = cHSq(5, target_uid, client.key, client.iv, "BD")
            client.CliEnts2.send(p2)
            time.sleep(0.03)
            p3 = SEnd_InV(5, target_uid, client.key, client.iv, "BD")
            client.CliEnts2.send(p3)
            time.sleep(0.03)
            p4 = ExiT(client.key, client.iv)
            client.CliEnts2.send(p4)
            total += 1
        except:
            pass
        for players in [3,6]:
            try:
                pkt = create_group_invite_packet(client.key, client.iv, target_uid, players)
                if pkt:
                    client.CliEnts2.send(pkt)
                    total += 1
                    time.sleep(0.02)
            except:
                pass
    except:
        pass
    return total

def spam_worker(target_uid, spam_type='full'):
    print(f"\n{G}🎯 SPAM STARTED ON {target_uid} (Type: {spam_type}){RS}")
    total_requests = 0
    round_num = 0
    while True:
        with active_spam_lock:
            if target_uid not in active_spam_targets:
                break

        # একত্রে সব ক্লায়েন্ট নেওয়া
        with connected_clients_lock:
            all_clients = list(connected_clients.values())
        # গ্রুপ অ্যাকাউন্টগুলোও যোগ করা
        for acc in GROUP_ACCOUNTS:
            if acc['id'] in connected_clients:
                all_clients.append(connected_clients[acc['id']])

        if not all_clients:
            time.sleep(1)
            continue

        round_num += 1
        for client in all_clients:
            with active_spam_lock:
                if target_uid not in active_spam_targets:
                    break
            try:
                if spam_type == 'full':
                    total_requests += send_full_spam(client, target_uid)
                else:
                    total_requests += send_squad_spam(client, target_uid)
            except:
                pass
            time.sleep(0.04)  # কমিয়ে দেওয়া

        if round_num % 20 == 0:
            print(f"{C}{'='*40}{RS}\n{G}📊 Round {round_num} | Requests: {total_requests} | Bots: {len(all_clients)}{RS}")
        time.sleep(0.3)  # প্রতিটি রাউন্ডের মাঝে কম বিরতি

    with spam_threads_lock:
        if target_uid in spam_threads:
            del spam_threads[target_uid]
    print(f"\n{R}🛑 SPAM STOPPED ON {target_uid}{RS}\n")

def start_spam(target_uid, spam_type='full'):
    with active_spam_lock:
        if target_uid in active_spam_targets:
            return False, f"Already spamming {target_uid}"
        active_spam_targets[target_uid] = {'type': spam_type, 'start_time': datetime.now()}
    thread = Thread(target=spam_worker, args=(target_uid, spam_type), daemon=True)
    with spam_threads_lock:
        spam_threads[target_uid] = thread
    thread.start()
    return True, f"Started {spam_type} spam on {target_uid}"

def stop_spam(target_uid):
    with active_spam_lock:
        if target_uid in active_spam_targets:
            del active_spam_targets[target_uid]
            return True, f"Stopped spam on {target_uid}"
    return False, f"No spam found for {target_uid}"

def stop_all_spam():
    with active_spam_lock:
        targets = list(active_spam_targets.keys())
        for t in targets:
            del active_spam_targets[t]
    return True, f"Stopped all spam ({len(targets)} targets)"

def get_spam_status():
    with active_spam_lock:
        active = []
        for uid, info in active_spam_targets.items():
            elapsed = (datetime.now() - info['start_time']).total_seconds() if info.get('start_time') else 0
            active.append({
                'uid': uid,
                'type': info.get('type','full'),
                'elapsed_minutes': int(elapsed/60),
                'banner_url': f"https://mahir-banner-api.vercel.app/profile?uid={uid}"
            })
    with connected_clients_lock:
        count = len(connected_clients)
        accounts_list = list(connected_clients.keys())[:50]
    return {'active_targets': active, 'active_count': len(active), 'accounts_count': count, 'accounts_list': accounts_list}

# ==================== অটো রিসেট ====================
def auto_reset_spam():
    global auto_reset_timer, accounts_initialized, ACCOUNTS, GROUP_ACCOUNTS
    print(f"\n{Y}🔄 AUTO RESET INITIATED{RS}")
    stop_all_spam()
    with connected_clients_lock:
        connected_clients.clear()
    ACCOUNTS = load_accounts(ACCOUNTS_FILE)
    GROUP_ACCOUNTS = load_group_accounts(GROUP_ACCOUNTS_FILE)
    accounts_initialized = False
    Thread(target=run_accounts, daemon=True).start()
    Thread(target=run_group_accounts, daemon=True).start()
    if auto_reset_timer:
        auto_reset_timer.cancel()
    auto_reset_timer = threading.Timer(AUTO_RESET_INTERVAL, auto_reset_spam)
    auto_reset_timer.daemon = True
    auto_reset_timer.start()
    print(f"{G}✅ Auto reset complete.{RS}")

def start_auto_reset():
    global auto_reset_timer
    if auto_reset_timer:
        auto_reset_timer.cancel()
    auto_reset_timer = threading.Timer(AUTO_RESET_INTERVAL, auto_reset_spam)
    auto_reset_timer.daemon = True
    auto_reset_timer.start()

def trigger_manual_reset():
    auto_reset_spam()
    return True, "Manual reset triggered"

# ==================== FF_CLIENT ====================
class FF_CLient():
    def __init__(self, uid, password):
        self.id = uid
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
                    self.packet = json.loads(DeCode_PackEt(f'08{self.DaTa2.hex().split("08",1)[1]}'))
                    self.AutH = self.packet['5']['data']['7']['data']
            except:
                pass

    def Connect_SerVer(self, Token, tok, host, port, key, iv, host2, port2):
        self.AutH_ToKen_0115 = tok
        self.CliEnts = socket.create_connection((host, int(port)))
        self.CliEnts.send(bytes.fromhex(self.AutH_ToKen_0115))
        self.DaTa = self.CliEnts.recv(1024)
        threading.Thread(target=self.Connect_SerVer_OnLine, args=(Token, tok, host, port, key, iv, host2, port2), daemon=True).start()
        try:
            self.Exemple = xMsGFixinG('12345678')
        except:
            pass
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
                        if hasattr(self, 'CliEnts2'):
                            self.CliEnts2.close()
                        self.Connect_SerVer(Token, tok, host, port, key, iv, host2, port2)
                    except:
                        self.CliEnts.close()
                        if hasattr(self, 'CliEnts2'):
                            self.CliEnts2.close()
                        self.Connect_SerVer(Token, tok, host, port, key, iv, host2, port2)
            except Exception as e:
                print(f"{R}❌ Connection error {self.id}: {e}{RS}")
                with connected_clients_lock:
                    if self.id in connected_clients:
                        del connected_clients[self.id]
                self.Connect_SerVer(Token, tok, host, port, key, iv, host2, port2)

    def GeT_Key_Iv(self, serialized_data):
        my_message = xKEys.MyMessage()
        my_message.ParseFromString(serialized_data)
        timestamp, key, iv = my_message.field21, my_message.field22, my_message.field23
        timestamp_obj = Timestamp()
        timestamp_obj.FromNanoseconds(timestamp)
        combined = timestamp_obj.seconds * 1_000_000_000 + timestamp_obj.nanos
        return combined, key, iv

    def Guest_GeneRaTe(self, uid, password):
        url = "https://100067.connect.garena.com/oauth/guest/token/grant"
        headers = {
            "Host": "100067.connect.garena.com",
            "User-Agent": "GarenaMSDK/4.0.19P4(G011A ;Android 9;en;US;)",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "close",
        }
        data = {
            "uid": uid,
            "password": password,
            "response_type": "token",
            "client_type": "2",
            "client_secret": "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3",
            "client_id": "100067",
        }
        try:
            resp = requests.post(url, headers=headers, data=data).json()
            access_token, open_id = resp['access_token'], resp['open_id']
            time.sleep(0.2)
            print(f'{C}🔐 Login: {self.id}{RS}')
            return self.ToKen_GeneRaTe(access_token, open_id)
        except:
            time.sleep(10)
            return self.Guest_GeneRaTe(uid, password)

    def GeT_LoGin_PorTs(self, jwt_token, payload, dynamic_url="https://clientbp.ggpolarbear.com"):
        url = f'{dynamic_url}/GetLoginData'
        headers = {
            'Expect': '100-continue',
            'Authorization': f'Bearer {jwt_token}',
            'X-Unity-Version': '2022.3.47f1',
            'X-GA': 'v1 1',
            'ReleaseVersion': 'OB54',
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'UnityPlayer/2022.3.47f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)',
            'Connection': 'close',
            'Accept-Encoding': 'deflate, gzip',
        }
        try:
            resp = requests.post(url, headers=headers, data=payload, verify=False)
            data = json.loads(DeCode_PackEt(resp.content.hex()))
            addr1, addr2 = data['32']['data'], data['14']['data']
            ip, ip2 = addr1[:-6], addr2[:-6]
            port, port2 = addr1[-5:], addr2[-5:]
            return ip, port, ip2, port2
        except:
            return None, None, None, None

    def ToKen_GeneRaTe(self, access_token, open_id):
        url = "https://loginbp.ggpolarbear.com/MajorLogin"
        headers = {
            'X-Unity-Version': '2022.3.47f1',
            'ReleaseVersion': 'OB54',
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-GA': 'v1 1',
            'User-Agent': 'UnityPlayer/2022.3.47f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)',
            'Host': 'loginbp.ggpolarbear.com',
            'Connection': 'Keep-Alive',
            'Accept-Encoding': 'gzip'
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
            major_login.open_id = open_id
            major_login.open_id_type = "4"
            major_login.login_open_id_type = 4
            major_login.access_token = access_token
            major_login.login_by = 3
            major_login.platform_sdk_id = 2
            major_login.origin_platform_type = "4"
            major_login.primary_platform_type = "4"
            memory_available = major_login.memory_available
            memory_available.version = 55
            memory_available.hidden_value = 81
            major_login.external_storage_total = 128512
            major_login.external_storage_available = random.randint(38000,52000)
            major_login.internal_storage_total = 110731
            major_login.internal_storage_available = random.randint(18000,32000)
            major_login.game_disk_storage_total = 26628
            major_login.game_disk_storage_available = random.randint(18000,28080)
            major_login.external_sdcard_total_storage = 119234
            major_login.external_sdcard_avail_storage = random.randint(28080,60000)
            major_login.library_path = "/data/app/~~random/base.apk"
            major_login.library_token = "hash|base.apk"
            major_login.client_using_version = "7428b253defc164018c604a1ebbfebdf"
            major_login.supported_astc_bitset = 16383
            major_login.analytics_detail = b"FwQVTgUPX1UaUllDDwcWCRBpWAUOUgsvA1snWlBaO1kFYg=="
            major_login.loading_time = random.randint(9000,18000)
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
            payload = cipher.encrypt(pad(raw_data, 16))
        except:
            time.sleep(5)
            return self.ToKen_GeneRaTe(access_token, open_id)

        resp = requests.post(url, headers=headers, data=payload, verify=False)
        if resp.status_code == 200:
            try:
                data = json.loads(DeCode_PackEt(resp.content.hex()))
                jwt_token = data['8']['data']
                combined, key, iv = self.GeT_Key_Iv(resp.content)
                ip, port, ip2, port2 = self.GeT_LoGin_PorTs(jwt_token, payload)
                return jwt_token, key, iv, combined, ip, port, ip2, port2
            except:
                time.sleep(5)
                return self.ToKen_GeneRaTe(access_token, open_id)
        else:
            time.sleep(5)
            return self.ToKen_GeneRaTe(access_token, open_id)

    def Get_FiNal_ToKen_0115(self):
        try:
            result = self.Guest_GeneRaTe(self.id, self.password)
            if not result:
                time.sleep(5)
                return self.Get_FiNal_ToKen_0115()
            token, key, iv, ts, ip, port, ip2, port2 = result
            if not all([ip, port, ip2, port2]):
                time.sleep(5)
                return self.Get_FiNal_ToKen_0115()
            self.JwT_ToKen = token
            try:
                decoded = jwt.decode(token, options={"verify_signature": False})
                account_id = decoded.get('account_id')
                enc_acc = hex(account_id)[2:]
                hex_ts = DecodE_HeX(ts)
                self.JwT_ToKen_ = token.encode().hex()
                print(f'{C}🆔 Account UID: {account_id}{RS}')
            except:
                time.sleep(5)
                return self.Get_FiNal_ToKen_0115()
            try:
                enc_len = len(EnC_PacKeT(self.JwT_ToKen_, key, iv)) // 2
                header = hex(enc_len)[2:]
                length = len(enc_acc)
                pad = '00000000'
                if length == 9:
                    pad = '0000000'
                elif length == 8:
                    pad = '00000000'
                elif length == 10:
                    pad = '000000'
                elif length == 7:
                    pad = '000000000'
                self.Header = f'0115{pad}{enc_acc}{hex_ts}00000{header}'
                self.FiNal_ToKen_0115 = self.Header + EnC_PacKeT(self.JwT_ToKen_, key, iv)
            except:
                time.sleep(5)
                return self.Get_FiNal_ToKen_0115()
            self.AutH_ToKen = self.FiNal_ToKen_0115
            self.Connect_SerVer(self.JwT_ToKen, self.AutH_ToKen, ip, port, key, iv, ip2, port2)
            return self.AutH_ToKen, key, iv
        except:
            time.sleep(5)
            return self.Get_FiNal_ToKen_0115()

def start_account(account):
    try:
        print(f"{G}🚀 Logging in: {account['id']}{RS}")
        FF_CLient(account['id'], account['password'])
    except:
        time.sleep(1)
        start_account(account)

def run_accounts_from_list(accounts):
    for acc in accounts:
        Thread(target=start_account, args=(acc,), daemon=True).start()
        time.sleep(0.15)  # একটু কমিয়ে দেওয়া

def run_accounts():
    global accounts_initialized, accounts_initializing
    if accounts_initializing:
        return
    accounts_initializing = True
    try:
        run_accounts_from_list(ACCOUNTS)
        accounts_initialized = True
    finally:
        accounts_initializing = False

def run_group_accounts():
    run_accounts_from_list(GROUP_ACCOUNTS)

# ==================== SSE STREAM ====================
@app.route('/stream')
def stream():
    def event_stream():
        last_data = None
        while True:
            time.sleep(SSE_INTERVAL)
            current_data = get_spam_status()
            with connected_clients_lock:
                current_data['accounts_count'] = len(connected_clients)
                current_data['accounts_list'] = list(connected_clients.keys())[:50]
            if current_data != last_data:
                last_data = current_data
                yield f"data: {json.dumps(current_data)}\n\n"
    return Response(event_stream(), mimetype="text/event-stream")

# ==================== ওয়েব রাউট ====================
@app.route('/login', methods=['GET','POST'])
def login_page():
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
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

# ==================== ফাইল আপলোড এপিআই ====================
@app.route('/api/upload/accs', methods=['POST'])
@login_required
def upload_accs():
    global ACCOUNTS
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected'}), 400
    try:
        content = file.read().decode('utf-8')
        accs = load_accounts_from_text(content)
        if not accs:
            return jsonify({'success': False, 'message': 'No valid accounts'}), 400
        with open(ACCOUNTS_FILE, 'w', encoding='utf-8') as f:
            for a in accs:
                f.write(f"{a['id']}:{a['password']}\n")
        ACCOUNTS = accs
        with connected_clients_lock:
            connected_clients.clear()
        Thread(target=run_accounts, daemon=True).start()
        return jsonify({'success': True, 'message': f'Uploaded {len(accs)} accounts', 'count': len(accs)})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/upload/group', methods=['POST'])
@login_required
def upload_group():
    global GROUP_ACCOUNTS
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected'}), 400
    try:
        content = file.read().decode('utf-8')
        accs = load_accounts_from_text(content)
        if not accs:
            return jsonify({'success': False, 'message': 'No valid accounts'}), 400
        with open(GROUP_ACCOUNTS_FILE, 'w', encoding='utf-8') as f:
            for a in accs:
                f.write(f"{a['id']}:{a['password']}\n")
        GROUP_ACCOUNTS = accs
        with connected_clients_lock:
            for gid in [a['id'] for a in accs]:
                if gid in connected_clients:
                    del connected_clients[gid]
        Thread(target=run_group_accounts, daemon=True).start()
        return jsonify({'success': True, 'message': f'Uploaded {len(accs)} group accounts', 'count': len(accs)})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/get/accs', methods=['GET'])
@login_required
def download_accs():
    return send_from_directory('.', ACCOUNTS_FILE, as_attachment=True)

@app.route('/api/get/group', methods=['GET'])
@login_required
def download_group():
    return send_from_directory('.', GROUP_ACCOUNTS_FILE, as_attachment=True)

@app.route('/api/accounts/count', methods=['GET'])
@login_required
def accounts_count():
    with connected_clients_lock:
        return jsonify({
            'success': True,
            'data': {
                'total_accounts': len(ACCOUNTS),
                'total_group_accounts': len(GROUP_ACCOUNTS),
                'connected_accounts': len(connected_clients),
                'active_targets': len(active_spam_targets),
                'initialized': accounts_initialized
            }
        })

# ==================== স্প্যাম এপিআই ====================
@app.route('/api/spam/all', methods=['POST'])
@login_required
def api_start_full_spam():
    data = request.get_json()
    uid = data.get('uid', '').strip()
    if not uid or not uid.isdigit():
        return jsonify({'success': False, 'message': 'Valid UID required'}), 400
    uids = [u.strip() for u in re.split(r'[,\s]+', uid) if u.strip().isdigit()]
    results = []
    for target in uids:
        success, msg = start_spam(target, 'full')
        results.append({'uid': target, 'success': success, 'message': msg})
    return jsonify({'success': True, 'results': results})

@app.route('/api/spam/squad', methods=['POST'])
@login_required
def api_start_squad_spam():
    data = request.get_json()
    uid = data.get('uid', '').strip()
    if not uid or not uid.isdigit():
        return jsonify({'success': False, 'message': 'Valid UID required'}), 400
    uids = [u.strip() for u in re.split(r'[,\s]+', uid) if u.strip().isdigit()]
    results = []
    for target in uids:
        success, msg = start_spam(target, 'squad')
        results.append({'uid': target, 'success': success, 'message': msg})
    return jsonify({'success': True, 'results': results})

@app.route('/api/stop/<uid>', methods=['GET'])
@login_required
def api_stop_spam(uid):
    if not uid.isdigit():
        return jsonify({'success': False, 'message': 'Invalid UID'}), 400
    success, msg = stop_spam(uid)
    return jsonify({'success': success, 'message': msg})

@app.route('/api/stop-all', methods=['GET','POST'])
@login_required
def api_stop_all():
    success, msg = stop_all_spam()
    return jsonify({'success': success, 'message': msg})

@app.route('/api/reset', methods=['GET','POST'])
@login_required
def api_reset():
    success, msg = trigger_manual_reset()
    return jsonify({'success': success, 'message': msg})

@app.route('/api/status', methods=['GET'])
def api_status():
    password = request.args.get('pass')
    if password == ADMIN_PASSWORD or session.get('logged_in'):
        return jsonify({'success': True, 'data': get_spam_status()})
    return jsonify({'success': False, 'message': 'Unauthorized'}), 401

@app.route('/api/accounts', methods=['GET'])
def api_accounts():
    password = request.args.get('pass')
    if password == ADMIN_PASSWORD or session.get('logged_in'):
        with connected_clients_lock:
            return jsonify({'success': True, 'accounts': list(connected_clients.keys())})
    return jsonify({'success': False, 'message': 'Unauthorized'}), 401

@app.route('/api/targets', methods=['GET'])
def api_targets():
    password = request.args.get('pass')
    if password != ADMIN_PASSWORD and not session.get('logged_in'):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    with active_spam_lock:
        targets = []
        for uid, info in active_spam_targets.items():
            elapsed = (datetime.now() - info['start_time']).total_seconds() if info.get('start_time') else 0
            targets.append({
                'uid': uid,
                'type': info.get('type', 'full'),
                'elapsed_minutes': int(elapsed/60),
                'banner_url': f"https://mahir-banner-api.vercel.app/profile?uid={uid}"
            })
    return jsonify({'success': True, 'targets': targets})

# ==================== টেমপ্লেট (আপডেটেড) ====================
LOGIN_TEMPLATE = '''
<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>MAHIR SYSTEM</title>
<style>body{background:#05050a;color:#fff;font-family:sans-serif;display:flex;justify-content:center;align-items:center;min-height:100vh;margin:0}.login-box{background:rgba(10,10,25,0.8);border:1px solid rgba(255,0,127,0.3);border-radius:16px;padding:40px 30px;width:100%;max-width:400px;text-align:center}.login-box h1{background:linear-gradient(135deg,#ff007f,#7f00ff);-webkit-background-clip:text;-webkit-text-fill-color:transparent}.input-group{margin:20px 0}.input-group input{width:100%;padding:12px;border-radius:8px;border:1px solid #333;background:#111;color:#fff;font-size:1rem}.btn-login{width:100%;padding:14px;background:linear-gradient(135deg,#ff007f,#7f00ff);border:none;border-radius:8px;color:#fff;font-weight:bold;cursor:pointer}.error{color:#ff4444;margin-top:10px}</style></head>
<body><div class="login-box"><h1>MAHIR SYSTEM</h1><p style="color:#00ffcc;">Access Control Panel</p><form method="POST"><div class="input-group"><input type="password" name="password" placeholder="Enter Password" required></div><button class="btn-login">UNLOCK</button>{% if error %}<div class="error">{{ error }}</div>{% endif %}</form></div></body></html>
'''

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MAHIR SPAM ENGINE</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Inter',sans-serif;background:linear-gradient(135deg,#060417,#0e0b30);min-height:100vh;color:#fff;padding:20px}
.container{max-width:1400px;margin:0 auto}
.header{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:15px;padding-bottom:20px;border-bottom:1px solid rgba(255,255,255,0.05)}
.logo{font-size:2.2rem;font-weight:800;background:linear-gradient(135deg,#ff007f,#7f00ff);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.stats-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:15px;margin:20px 0}
.stat-card{background:rgba(255,255,255,0.03);backdrop-filter:blur(10px);border-radius:12px;padding:15px;text-align:center;border:1px solid rgba(255,255,255,0.05);transition:0.3s}
.stat-card:hover{transform:translateY(-4px);border-color:rgba(255,0,127,0.3)}
.stat-card .value{font-size:1.8rem;font-weight:700}
.controls-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:20px;margin:20px 0}
.control-card{background:rgba(255,255,255,0.02);backdrop-filter:blur(10px);border-radius:12px;padding:20px;border:1px solid rgba(255,255,255,0.05);transition:0.3s}
.control-card:hover{border-color:rgba(255,0,127,0.2)}
.input-group{display:flex;gap:10px;flex-wrap:wrap;margin:10px 0}
.input-group input{flex:1;padding:10px 14px;border:1px solid rgba(255,255,255,0.08);border-radius:8px;background:rgba(0,0,0,0.4);color:#fff;font-family:monospace;min-width:120px;transition:0.3s}
.input-group input:focus{border-color:#ff007f;box-shadow:0 0 15px rgba(255,0,127,0.1);outline:none}
.btn{padding:10px 18px;border:none;border-radius:8px;font-weight:600;cursor:pointer;display:inline-flex;align-items:center;gap:6px;transition:0.3s}
.btn:hover{transform:translateY(-2px);box-shadow:0 6px 20px rgba(0,0,0,0.3)}
.btn-primary{background:linear-gradient(135deg,#ff007f,#7f00ff);color:#fff}
.btn-success{background:linear-gradient(135deg,#00b09b,#96c93d);color:#fff}
.btn-danger{background:linear-gradient(135deg,#ff0844,#ffb199);color:#fff}
.btn-warning{background:linear-gradient(135deg,#ffaa00,#ff6600);color:#000}
.btn-purple{background:linear-gradient(135deg,#8e44ad,#9b59b6);color:#fff}
.btn-outline{background:transparent;border:1px solid rgba(255,255,255,0.15);color:#fff}
.btn-outline:hover{background:rgba(255,255,255,0.05)}
.btn-sm{padding:6px 12px;font-size:0.8rem}
.btn-cyan{background:linear-gradient(135deg,#00d2ff,#3a7bd5);color:#fff}
.btn-cyan:hover{transform:translateY(-2px);box-shadow:0 5px 20px rgba(0,210,255,0.3)}
.upload-area{border:2px dashed rgba(255,255,255,0.1);border-radius:10px;padding:20px;text-align:center;cursor:pointer;transition:0.3s}
.upload-area:hover{border-color:rgba(255,0,127,0.3);background:rgba(255,0,127,0.03)}
.upload-area.dragover{border-color:#ff007f;background:rgba(255,0,127,0.05)}
.upload-area i{font-size:1.8rem;color:rgba(255,255,255,0.2)}
.target-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:20px;margin-top:15px}
.target-card{background:rgba(20,20,40,0.6);border-radius:16px;overflow:hidden;border:1px solid rgba(255,255,255,0.06);transition:all 0.4s cubic-bezier(0.175,0.885,0.32,1.275);backdrop-filter:blur(8px);opacity:0;transform:translateY(20px)}
.target-card.visible{opacity:1;transform:translateY(0)}
.target-card:hover{transform:translateY(-6px) scale(1.01);border-color:rgba(255,0,127,0.4);box-shadow:0 12px 40px rgba(255,0,127,0.15)}
.target-card img{width:100%;height:auto;display:block;border-bottom:1px solid rgba(255,255,255,0.05)}
.target-card .info{padding:12px 16px;display:flex;justify-content:space-between;align-items:center;background:rgba(0,0,0,0.3)}
.target-card .info .uid{font-family:monospace;font-weight:bold;color:#ff007f;font-size:1rem}
.target-card .info .type{font-size:0.7rem;background:rgba(255,255,255,0.08);padding:2px 10px;border-radius:12px;color:rgba(255,255,255,0.6)}
.target-card .info .time{font-size:0.7rem;color:rgba(255,255,255,0.3)}
.console-box{background:rgba(0,0,0,0.5);border-radius:10px;height:150px;padding:12px;font-family:monospace;font-size:0.75rem;color:#00ffcc;overflow-y:auto}
.console-box .line{opacity:0;animation:fadeInLine 0.3s forwards}
@keyframes fadeInLine{to{opacity:1}}
.toast{position:fixed;bottom:20px;right:20px;background:rgba(0,0,0,0.9);padding:12px 20px;border-radius:8px;z-index:999;color:#fff;display:flex;align-items:center;gap:10px;border:1px solid rgba(255,255,255,0.1);animation:slideIn 0.3s cubic-bezier(0.175,0.885,0.32,1.275)}
.toast.success{border-color:#00b09b}
.toast.error{border-color:#ff0844}
@keyframes slideIn{from{transform:translateX(100%);opacity:0}to{transform:translateX(0);opacity:1}}
.status-dot{width:10px;height:10px;border-radius:50%;display:inline-block;margin-right:6px}
.status-dot.online{background:#00ffcc;animation:blink 1.5s infinite}
.status-dot.offline{background:#ff4444}
@keyframes blink{0%,100%{opacity:1}50%{opacity:0.3}}
.footer{text-align:center;color:rgba(255,255,255,0.15);font-size:0.7rem;margin-top:30px;padding-top:15px;border-top:1px solid rgba(255,255,255,0.03)}
.stop-small{background:#eb3349;border:none;color:#fff;padding:4px 12px;border-radius:6px;cursor:pointer;font-size:0.7rem;transition:0.3s}
.stop-small:hover{background:#c0392b;transform:scale(1.05)}
.empty-state{color:rgba(255,255,255,0.3);text-align:center;padding:20px;width:100%}

/* Modal Styles */
.modal{display:none;position:fixed;z-index:999;left:0;top:0;width:100%;height:100%;overflow:auto;background:rgba(0,0,0,0.8);backdrop-filter:blur(10px)}
.modal-content{background:rgba(20,20,40,0.95);margin:2% auto;padding:20px;border:1px solid rgba(255,0,127,0.3);border-radius:16px;width:95%;max-width:1400px;max-height:90vh;overflow-y:auto;position:relative}
.modal-close{position:absolute;right:20px;top:15px;font-size:2rem;font-weight:bold;color:#fff;cursor:pointer;transition:0.3s}
.modal-close:hover{color:#ff007f}
.modal-title{font-size:1.8rem;margin-bottom:20px;background:linear-gradient(135deg,#ff007f,#7f00ff);-webkit-background-clip:text;-webkit-text-fill-color:transparent;display:inline-block}
.modal-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:20px}

@media(max-width:600px){.controls-grid{grid-template-columns:1fr}.input-group{flex-direction:column}.btn{width:100%;justify-content:center}.modal-grid{grid-template-columns:1fr}}
</style>
</head>
<body>
<div class="container">
<div class="header">
<div class="logo"><i class="fas fa-bolt"></i> MAHIR SYSTEM <span style="font-size:1rem;color:rgba(255,255,255,0.3);">v3.0</span></div>
<div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;">
    <span class="status-dot online" id="statusDot"></span>
    <span id="statusText" style="color:rgba(255,255,255,0.5);font-size:0.85rem;">Connecting...</span>
    <button class="btn btn-cyan btn-sm" onclick="showAllTargets()"><i class="fas fa-images"></i> Show All Targets</button>
    <a href="/logout" class="btn btn-outline btn-sm"><i class="fas fa-sign-out-alt"></i> LOGOUT</a>
</div>
</div>
<div class="stats-grid">
<div class="stat-card"><i class="fas fa-bullseye" style="color:#ff007f;"></i><h3>ACTIVE</h3><div class="value" id="activeCount">0</div></div>
<div class="stat-card"><i class="fas fa-robot" style="color:#4facfe;"></i><h3>BOTS</h3><div class="value" id="botCount">0</div></div>
<div class="stat-card"><i class="fas fa-users" style="color:#ffaa00;"></i><h3>GROUP</h3><div class="value" id="groupCount">0</div></div>
<div class="stat-card"><i class="fas fa-clock" style="color:#00ffcc;"></i><h3>AUTO RESET</h3><div class="value" style="font-size:1.2rem;">2 HOURS</div></div>
</div>
<div class="controls-grid">
<div class="control-card"><h3><i class="fas fa-upload" style="color:#ff007f;"></i> UPLOAD ACCOUNTS</h3><div class="upload-area" id="accsUpload"><i class="fas fa-file-alt"></i><p>Drop <strong>accs.txt</strong> or click</p><input type="file" id="accsFileInput" accept=".txt" style="display:none;"><div id="accsStatus" style="font-size:0.75rem;color:rgba(255,255,255,0.3);margin-top:6px;">No file</div></div></div>
<div class="control-card"><h3><i class="fas fa-upload" style="color:#ffaa00;"></i> UPLOAD GROUP</h3><div class="upload-area" id="groupUpload"><i class="fas fa-users"></i><p>Drop <strong>group.txt</strong> or click</p><input type="file" id="groupFileInput" accept=".txt" style="display:none;"><div id="groupStatus" style="font-size:0.75rem;color:rgba(255,255,255,0.3);margin-top:6px;">No file</div></div></div>
</div>
<div class="controls-grid">
<div class="control-card"><h3><i class="fas fa-fire" style="color:#ff007f;"></i> FULL SPAM</h3><div class="input-group"><input id="fullUid" placeholder="Target UID(s) (comma separated)"><button class="btn btn-primary" onclick="startFull()"><i class="fas fa-play"></i> START</button></div></div>
<div class="control-card"><h3><i class="fas fa-users" style="color:#00b09b;"></i> SQUAD SPAM</h3><div class="input-group"><input id="squadUid" placeholder="Target UID(s) (comma separated)"><button class="btn btn-success" onclick="startSquad()"><i class="fas fa-play"></i> START</button></div></div>
</div>
<div class="controls-grid">
<div class="control-card"><h3><i class="fas fa-stop" style="color:#ff0844;"></i> STOP</h3><div class="input-group"><input id="stopUid" placeholder="Target UID"><button class="btn btn-danger" onclick="stopSingle()"><i class="fas fa-power-off"></i> STOP</button></div><div style="display:flex;gap:8px;margin-top:10px;flex-wrap:wrap;"><button class="btn btn-warning" onclick="stopAll()"><i class="fas fa-stop-circle"></i> STOP ALL</button><button class="btn btn-purple" onclick="resetNow()"><i class="fas fa-sync"></i> RESET</button></div></div>
<div class="control-card"><h3><i class="fas fa-file" style="color:#4facfe;"></i> FILES</h3><div style="background:rgba(0,0,0,0.3);padding:10px;border-radius:8px;font-size:0.85rem;"><div>📁 accs.txt <span id="accCount" style="color:rgba(255,255,255,0.4);">0 accounts</span></div><div>📁 group.txt <span id="groupFileCount" style="color:rgba(255,255,255,0.4);">0 accounts</span></div><div style="display:flex;gap:8px;margin-top:8px;"><button class="btn btn-outline btn-sm" onclick="downloadAccs()"><i class="fas fa-download"></i> accs.txt</button><button class="btn btn-outline btn-sm" onclick="downloadGroup()"><i class="fas fa-download"></i> group.txt</button></div></div></div>
</div>
<div class="control-card"><h3><i class="fas fa-images" style="color:#ff007f;"></i> TARGETS <span style="font-size:0.8rem;color:rgba(255,255,255,0.3);">(with Banner)</span></h3>
<div style="display:flex;gap:10px;margin-bottom:10px;flex-wrap:wrap;">
    <button class="btn btn-cyan btn-sm" onclick="showAllTargets()"><i class="fas fa-expand"></i> View All</button>
    <button class="btn btn-outline btn-sm" onclick="refreshTargets()"><i class="fas fa-sync"></i> Refresh</button>
</div>
<div id="targetGrid" class="target-grid"><div class="empty-state">🎯 No active targets</div></div>
</div>
<div class="control-card"><h3><i class="fas fa-terminal" style="color:#00ffcc;"></i> CONSOLE</h3><div class="console-box" id="consoleBox"><div class="line">[System] MAHIR SPAM ENGINE v3.0</div><div class="line">[System] Real-time SSE enabled</div></div></div>
<div class="control-card"><h3><i class="fas fa-robot" style="color:#4facfe;"></i> CONNECTED ACCOUNTS</h3><div id="accountsContainer"><span style="color:rgba(255,255,255,0.3);">Loading...</span></div></div>
<div class="footer">MAHIR SYSTEM v3.0 | Auto Reset 2 Hours | <i class="fas fa-bolt" style="color:#ff007f;"></i> Real-time SSE</div>
</div>

<!-- Modal for All Targets -->
<div id="targetModal" class="modal">
    <div class="modal-content">
        <span class="modal-close" onclick="closeModal()">&times;</span>
        <div class="modal-title"><i class="fas fa-images"></i> All Targets with Banners</div>
        <div id="modalGrid" class="modal-grid"><div class="empty-state">Loading...</div></div>
    </div>
</div>

<script>
// ========== SSE Real-time Stream ==========
const evtSource = new EventSource('/stream');
evtSource.onopen = function() {
    document.getElementById('statusText').textContent = 'Live';
    document.getElementById('statusDot').className = 'status-dot online';
};
evtSource.onerror = function() {
    document.getElementById('statusText').textContent = 'Reconnecting...';
    document.getElementById('statusDot').className = 'status-dot offline';
};
evtSource.onmessage = function(event) {
    try {
        const data = JSON.parse(event.data);
        updateUI(data);
    } catch(e) {}
};

function updateUI(data) {
    document.getElementById('activeCount').textContent = data.active_count || 0;
    document.getElementById('botCount').textContent = data.accounts_count || 0;
    document.getElementById('groupCount').textContent = data.active_targets ? data.active_targets.length : 0;
    renderTargets(data.active_targets, 'targetGrid');
    updateAccounts(data.accounts_list);
}

function renderTargets(targets, containerId = 'targetGrid') {
    const grid = document.getElementById(containerId);
    if (!targets || targets.length === 0) {
        grid.innerHTML = '<div class="empty-state">🎯 No active targets</div>';
        return;
    }
    grid.innerHTML = targets.map((t, index) => `
        <div class="target-card visible" style="animation-delay: ${index * 0.05}s">
            <img src="${t.banner_url}" alt="Banner for ${t.uid}" 
                 loading="lazy" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex'">
            <div style="display:none;align-items:center;justify-content:center;height:150px;background:rgba(0,0,0,0.4);color:#ff007f;font-weight:bold;font-size:1.2rem;font-family:monospace;">
                ${t.uid}
            </div>
            <div class="info">
                <span class="uid">🎯 ${t.uid}</span>
                <span class="type">${t.type.toUpperCase()}</span>
                <span class="time">${t.elapsed_minutes}m</span>
            </div>
        </div>
    `).join('');
}

function updateAccounts(accounts) {
    const container = document.getElementById('accountsContainer');
    if (!accounts || accounts.length === 0) {
        container.innerHTML = '<span style="color:rgba(255,255,255,0.3);">No accounts connected</span>';
        return;
    }
    container.innerHTML = accounts.map(a => 
        `<span style="background:rgba(30,30,40,0.4);padding:2px 10px;border-radius:6px;font-family:monospace;font-size:11px;color:#4facfe;display:inline-block;margin:3px 4px;">${a}</span>`
    ).join('');
}

// ========== Show All Targets Modal ==========
function showAllTargets() {
    const modal = document.getElementById('targetModal');
    modal.style.display = 'block';
    document.getElementById('modalGrid').innerHTML = '<div class="empty-state">Loading targets...</div>';
    
    fetch('/api/targets?pass=MAHIRJOD')
        .then(res => res.json())
        .then(data => {
            if (data.success && data.targets && data.targets.length > 0) {
                renderTargets(data.targets, 'modalGrid');
            } else {
                document.getElementById('modalGrid').innerHTML = '<div class="empty-state">No targets found</div>';
            }
        })
        .catch(() => {
            document.getElementById('modalGrid').innerHTML = '<div class="empty-state">Error loading targets</div>';
        });
}

function closeModal() {
    document.getElementById('targetModal').style.display = 'none';
}

// Close modal on outside click
window.onclick = function(event) {
    const modal = document.getElementById('targetModal');
    if (event.target == modal) {
        modal.style.display = 'none';
    }
};

function refreshTargets() {
    fetch('/api/targets?pass=MAHIRJOD')
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                renderTargets(data.targets, 'targetGrid');
                showToast('Targets refreshed', 'success');
            }
        })
        .catch(() => showToast('Refresh failed', 'error'));
}

// ========== Toast, Log, Upload, Spam Functions ==========
function showToast(msg,type='info'){var t=document.createElement('div');t.className='toast '+type;t.innerHTML='<i class="fas '+(type==='success'?'fa-check-circle':type==='error'?'fa-exclamation-circle':'fa-info-circle')+'"></i> '+msg;document.body.appendChild(t);setTimeout(()=>t.remove(),4000);}
function log(msg,type='info'){var box=document.getElementById('consoleBox'),now=new Date(),line=document.createElement('div');line.className='line';line.innerHTML='<span style="color:rgba(255,255,255,0.3);">['+now.toLocaleTimeString()+']</span> <span style="color:'+(type==='success'?'#00ffcc':type==='error'?'#ff3366':'#4facfe')+';">'+msg+'</span>';box.appendChild(line);box.scrollTop=box.scrollHeight;if(box.children.length>80)box.removeChild(box.children[0]);}

function uploadAccs(file){var fd=new FormData();fd.append('file',file);fetch('/api/upload/accs',{method:'POST',body:fd}).then(r=>r.json()).then(d=>{if(d.success){document.getElementById('accsStatus').innerHTML='✅ '+d.count+' accounts';showToast(d.message,'success');log('Uploaded accs.txt: '+d.count+' accounts','success');}else{showToast(d.message,'error');}}).catch(()=>showToast('Upload failed','error'));}
function uploadGroup(file){var fd=new FormData();fd.append('file',file);fetch('/api/upload/group',{method:'POST',body:fd}).then(r=>r.json()).then(d=>{if(d.success){document.getElementById('groupStatus').innerHTML='✅ '+d.count+' accounts';showToast(d.message,'success');log('Uploaded group.txt: '+d.count+' accounts','success');}else{showToast(d.message,'error');}}).catch(()=>showToast('Upload failed','error'));}
document.getElementById('accsUpload').addEventListener('click',()=>document.getElementById('accsFileInput').click());
document.getElementById('accsFileInput').addEventListener('change',function(e){if(this.files.length)uploadAccs(this.files[0]);});
document.getElementById('groupUpload').addEventListener('click',()=>document.getElementById('groupFileInput').click());
document.getElementById('groupFileInput').addEventListener('change',function(e){if(this.files.length)uploadGroup(this.files[0]);});

// Drag & Drop
['accsUpload','groupUpload'].forEach(id=>{
    const el=document.getElementById(id);
    el.addEventListener('dragover',e=>{e.preventDefault();el.classList.add('dragover');});
    el.addEventListener('dragleave',()=>el.classList.remove('dragover'));
    el.addEventListener('drop',e=>{e.preventDefault();el.classList.remove('dragover');const files=e.dataTransfer.files;if(files.length){id==='accsUpload'?uploadAccs(files[0]):uploadGroup(files[0]);}});
});

function startFull(){var u=document.getElementById('fullUid').value.trim();if(!u){showToast('Enter UID','error');return}var uids=u.split(',').filter(x=>/^\\d+$/.test(x.trim()));if(!uids.length){showToast('Invalid UID','error');return}log('Starting FULL spam on '+uids.join(','),'info');fetch('/api/spam/all',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({uid:u})}).then(r=>r.json()).then(d=>{if(d.success){showToast('Started full spam','success')}else showToast(d.message||'Failed','error')}).catch(()=>showToast('Error','error'));}
function startSquad(){var u=document.getElementById('squadUid').value.trim();if(!u){showToast('Enter UID','error');return}var uids=u.split(',').filter(x=>/^\\d+$/.test(x.trim()));if(!uids.length){showToast('Invalid UID','error');return}log('Starting SQUAD spam on '+uids.join(','),'info');fetch('/api/spam/squad',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({uid:u})}).then(r=>r.json()).then(d=>{if(d.success){showToast('Started squad spam','success')}else showToast(d.message||'Failed','error')}).catch(()=>showToast('Error','error'));}
function stopSingle(){var u=document.getElementById('stopUid').value.trim();if(!u){showToast('Enter UID','error');return}if(!/^\\d+$/.test(u)){showToast('Invalid UID','error');return}log('Stopping spam on '+u,'info');fetch('/api/stop/'+u).then(r=>r.json()).then(d=>{if(d.success){showToast(d.message,'success');document.getElementById('stopUid').value='';}else showToast(d.message,'error')}).catch(()=>showToast('Error','error'));}
function stopAll(){if(!confirm('Stop all spam?'))return;log('Stopping ALL spam','info');fetch('/api/stop-all').then(r=>r.json()).then(d=>{if(d.success){showToast(d.message,'success');}}).catch(()=>showToast('Error','error'));}
function resetNow(){if(!confirm('Manual reset? This will reload accounts.'))return;log('Manual reset triggered','info');fetch('/api/reset').then(r=>r.json()).then(d=>{if(d.success){showToast(d.message,'success');}}).catch(()=>showToast('Error','error'));}
function downloadAccs(){window.location.href='/api/get/accs';}
function downloadGroup(){window.location.href='/api/get/group';}

// Enter key support
document.getElementById('fullUid').addEventListener('keypress',e=>{if(e.key==='Enter')startFull()});
document.getElementById('squadUid').addEventListener('keypress',e=>{if(e.key==='Enter')startSquad()});
document.getElementById('stopUid').addEventListener('keypress',e=>{if(e.key==='Enter')stopSingle()});

log('System ready - Real-time SSE enabled','info');
</script>
</body>
</html>
'''

# ==================== মেইন ====================
def main():
    print(f"""
    {C}{BOLD}
    ╔═══════════════════════════════════════════════════════════════════╗
    ║            🎯 MAHIR SPAM SYSTEM v3.0 (Light) 🎯                  ║
    ║    ✅ Real-time SSE updates                                     ║
    ║    ✅ Persistent accounts                                      ║
    ║    ✅ Animated UI                                              ║
    ║    ✅ Auto reset every 2 hours                                 ║
    ║    🌐 http://127.0.0.1:8080                                    ║
    ║    🔑 Password: MAHIRJOD                                       ║
    ╚═══════════════════════════════════════════════════════════════════╝
    {RS}
    """)
    Thread(target=run_accounts, daemon=True).start()
    Thread(target=run_group_accounts, daemon=True).start()
    start_auto_reset()
    port = int(os.environ.get("PORT", 8081))
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)

if __name__ == "__main__":
    try:
        import aiohttp
    except ImportError:
        os.system("pip install aiohttp")
    main()