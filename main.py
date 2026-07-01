import os, sys, time, json, ssl, socket, threading, asyncio, base64, binascii, re, jwt, pickle, random
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from threading import Thread
from flask import Flask, request, jsonify, render_template_string

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

# ==================== ফ্লাস্ক অ্যাপ ====================
app = Flask(__name__)

# ==================== গ্লোবাল ভেরিয়েবল ====================
connected_clients = {}
connected_clients_lock = threading.Lock()
active_power_targets = {}
active_power_lock = threading.Lock()
spam_threads = {}
spam_threads_lock = threading.Lock()
auto_uids = []      # auto_uid.txt - SMART MONITORED (স্ট্যাটাস দেখে অটো স্প্যাম)
invite_uids = []    # inv_uid.txt - ACTIVE TARGETS (সরাসরি স্প্যাম)
auto_spam_active = False
auto_spam_thread = None
refresh_timer = None
target_status_cache = {}
smart_target_statuses = {}
smart_monitor_threads = {}
smart_monitor_lock = threading.Lock()
target_group_leaders = {}
active_invite_targets = {}  # inv_uid.txt এর জন্য সক্রিয় টার্গেট
invite_spam_thread = None

C = "\033[96m"
G = "\033[92m"
Y = "\033[93m"
R = "\033[91m"
RS = "\033[0m"
BOLD = "\033[1m"

_ID = '4575104506'
_PW = 'TORIKUL_TORIKUL_E6H3H'

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
def load_invite_uids(filename="inv_uid.txt"):
    """Load UIDs from inv_uid.txt - এগুলো সরাসরি ACTIVE TARGETS হিসেবে স্প্যাম পাবে"""
    global invite_uids
    uids = []
    try:
        with open(filename, "r", encoding="utf-8") as file:
            for line in file:
                uid = line.strip()
                if uid and not uid.startswith("#") and uid.isdigit():
                    uids.append(uid)
        invite_uids = uids
        print(f"{G}📦 Loaded {len(invite_uids)} ACTIVE TARGETS from inv_uid.txt{RS}")
    except FileNotFoundError:
        print(f"{Y}⚠️ inv_uid.txt not found! Creating...{RS}")
        with open(filename, "w") as f:
            f.write("# ACTIVE TARGETS - These UIDs will be spammed directly\n")
            f.write("# Example:\n")
            f.write("# 1234567890\n")
            f.write("# 0987654321\n")
        invite_uids = []
    return invite_uids

def save_invite_uids(uids):
    """Save UIDs to inv_uid.txt"""
    try:
        with open("inv_uid.txt", "w", encoding="utf-8") as file:
            file.write("# ACTIVE TARGETS - These UIDs will be spammed directly\n")
            file.write("# Example:\n")
            for uid in uids:
                file.write(f"{uid}\n")
        global invite_uids
        invite_uids = uids
        # নতুন UIDs যোগ করলে স্প্যাম শুরু করুন
        if uids and not auto_spam_active:
            start_invite_targets_spam()
    except Exception as e:
        print(f"{R}❌ Failed to save inv_uid.txt: {e}{RS}")

def load_auto_uids(filename="auto_uid.txt"):
    """Load UIDs from auto_uid.txt - এগুলো SMART MONITORED (স্ট্যাটাস দেখে স্প্যাম)"""
    global auto_uids
    uids = []
    try:
        with open(filename, "r", encoding="utf-8") as file:
            for line in file:
                uid = line.strip()
                if uid and not uid.startswith("#") and uid.isdigit():
                    uids.append(uid)
        auto_uids = uids
        print(f"{G}📦 Loaded {len(auto_uids)} SMART MONITORED UIDs from auto_uid.txt{RS}")
    except FileNotFoundError:
        print(f"{Y}⚠️ auto_uid.txt not found! Creating...{RS}")
        with open(filename, "w") as f:
            f.write("# SMART MONITORED UIDs - Status based auto spam\n")
            f.write("# Example:\n")
            f.write("# 1234567890\n")
            f.write("# 0987654321\n")
        auto_uids = []
    return auto_uids

def save_auto_uids(uids):
    """Save UIDs to auto_uid.txt"""
    try:
        with open("auto_uid.txt", "w", encoding="utf-8") as file:
            file.write("# SMART MONITORED UIDs - Status based auto spam\n")
            file.write("# Example:\n")
            for uid in uids:
                file.write(f"{uid}\n")
    except Exception as e:
        print(f"{R}❌ Failed to save auto_uid.txt: {e}{RS}")

# ==================== INVITE TARGETS SPAM WORKER ====================
def invite_targets_spam_worker():
    """inv_uid.txt এর UID গুলোতে সরাসরি স্প্যাম পাঠানোর জন্য ওয়ার্কার"""
    global auto_spam_active
    
    print(f"\n{G}{'='*60}{RS}")
    print(f"{G}🎯 ACTIVE TARGETS SPAM STARTED ON {len(invite_uids)} TARGETS:{RS}")
    for tid in invite_uids:
        print(f"{G}   ➤ {tid} (ACTIVE TARGET){RS}")
    print(f"{C}{'='*60}{RS}\n")

    total_requests = 0
    round_number = 0

    def run_async(coro):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(coro)
        except:
            return None
        finally:
            loop.close()

    while auto_spam_active:
        with connected_clients_lock:
            clients_list = list(connected_clients.values())

        if not clients_list:
            time.sleep(2)
            continue

        round_number += 1

        for target_id in invite_uids:
            for client in clients_list:
                try:
                    if hasattr(client, 'CliEnts2') and client.key:
                        # === 1. রুম স্প্যাম ===
                        try:
                            open_pkt = openroom(client.key, client.iv)
                            if open_pkt:
                                client.CliEnts2.send(open_pkt)
                            
                            spam_pkt = spmroom(client.key, client.iv, target_id)
                            if spam_pkt:
                                client.CliEnts2.send(spam_pkt)
                                total_requests += 1
                        except:
                            pass

                        # === 2. গ্রুপ ইনভাইট (3/5/6 প্লেয়ার) ===
                        for players in [3, 5, 6]:
                            try:
                                async def send_invite():
                                    p1 = await OpEnSq(client.key, client.iv)
                                    client.CliEnts2.send(p1)
                                    await asyncio.sleep(0.05)
                                    p2 = await cHSq(players, target_id, client.key, client.iv)
                                    client.CliEnts2.send(p2)
                                    await asyncio.sleep(0.05)
                                    p3 = await SEnd_InV(players, target_id, client.key, client.iv)
                                    client.CliEnts2.send(p3)
                                    total_requests += 1
                                    await asyncio.sleep(0.05)
                                    p4 = await ExiT(client.key, client.iv)
                                    client.CliEnts2.send(p4)
                                run_async(send_invite())
                            except:
                                pass

                        # === 3. ব্যাজ জয়িন ===
                        for badge_name, badge_value in BADGES.items():
                            try:
                                badge_pkt = create_badge_join_packet(client.key, client.iv, target_id, badge_value)
                                if badge_pkt:
                                    client.CliEnts2.send(badge_pkt)
                                    total_requests += 1
                                    time.sleep(0.03)
                            except:
                                pass

                except Exception as e:
                    print(f"{R}❌ Error: {e}{RS}")

                time.sleep(0.05)

        if round_number % 5 == 0:
            print(f"{C}{'='*50}{RS}")
            print(f"{G}📊 ACTIVE TARGETS Round {round_number} Complete{RS}")
            print(f"{G}📊 Total Requests: {total_requests}{RS}")
            print(f"{G}🎯 Active Targets: {len(invite_uids)}{RS}")
            print(f"{G}🤖 Bots Online: {len(clients_list)}{RS}")
            print(f"{C}{'='*50}{RS}\n")
        
        time.sleep(0.5)

    print(f"\n{R}🛑 ACTIVE TARGETS SPAM STOPPED{RS}\n")

def start_invite_targets_spam():
    """inv_uid.txt এর UID গুলোতে স্প্যাম শুরু করুন"""
    global auto_spam_active, invite_spam_thread
    
    if not invite_uids:
        print(f"{Y}⚠️ No active targets in inv_uid.txt{RS}")
        return False, "No active targets in inv_uid.txt"
    
    if invite_spam_thread and invite_spam_thread.is_alive():
        return False, "Active targets spam already running"
    
    auto_spam_active = True
    invite_spam_thread = Thread(target=invite_targets_spam_worker, daemon=True)
    invite_spam_thread.start()
    
    return True, f"Started spam on {len(invite_uids)} active targets"

def stop_invite_targets_spam():
    """inv_uid.txt এর স্প্যাম বন্ধ করুন"""
    global auto_spam_active
    auto_spam_active = False
    return True, "Active targets spam stopped"

# ==================== STATUS CHECKER FUNCTIONS ====================
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
    """Create join request with badge using custom working avatars"""
    try:
        # xBunnEr list of working avatar IDs
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
                24: selected_avatar, # এখানে xBunnEr এর অবতার আইডি ব্যবহার করা হয়েছে
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

# ==================== SMART MONITOR FOR AUTO_UID ====================
def monitor_target_smart(target_uid):
    """Smart monitor that automatically starts/stops spam based on target status"""
    print(f"{C}🧠 SMART MONITOR started for target: {target_uid}{RS}")
    
    last_status = None
    is_currently_spamming = False
    leader_spam_started = set()
    
    while True:
        with smart_monitor_lock:
            if target_uid not in smart_monitor_threads:
                print(f"{Y}📌 Smart monitor stopped for: {target_uid}{RS}")
                break
        
        try:
            status_info = get_detailed_status(target_uid)
            current_status = status_info.get('status', 'OFFLINE')
            is_online = status_info.get('is_online', False)
            mode = status_info.get('mode', '')
            squad_owner = status_info.get('squad_owner')
            
            should_spam = False
            spam_reason = ""
            
            if not is_online or current_status == 'OFFLINE':
                spam_reason = "Target is OFFLINE"
                should_spam = False
            elif current_status == 'INGAME':
                spam_reason = f"Target is IN-GAME ({mode})"
                should_spam = False
            elif current_status == 'MATCHMAKING':
                spam_reason = "Target is MATCHMAKING"
                should_spam = False
            elif current_status in ['SOLO', 'SOCIAL_ISLAND', 'IN_ROOM']:
                spam_reason = f"Target is {current_status} - READY TO SPAM"
                should_spam = True
            elif current_status == 'INSQUAD':
                if squad_owner and str(squad_owner) != str(target_uid):
                    spam_reason = f"Target in squad, leader: {squad_owner}"
                    should_spam = True
                    if squad_owner not in leader_spam_started:
                        print(f"{G}🎯 Starting spam on group leader: {squad_owner}{RS}")
                        start_multi_spam([squad_owner])
                        leader_spam_started.add(squad_owner)
                        target_group_leaders[target_uid] = squad_owner
                else:
                    spam_reason = "Target is squad owner - READY TO SPAM"
                    should_spam = True
            else:
                spam_reason = f"Status: {current_status}"
                should_spam = is_online
            
            if should_spam and not is_currently_spamming:
                print(f"{G}▶️ SMART: Starting spam on {target_uid} - {spam_reason}{RS}")
                start_multi_spam([target_uid])
                is_currently_spamming = True
                
            elif not should_spam and is_currently_spamming:
                print(f"{R}⏸️ SMART: Stopping spam on {target_uid} - {spam_reason}{RS}")
                stop_spam(target_uid)
                is_currently_spamming = False
            
            if current_status != 'INSQUAD' and target_uid in target_group_leaders:
                old_leader = target_group_leaders[target_uid]
                print(f"{Y}👋 Target left squad, stopping leader spam: {old_leader}{RS}")
                stop_spam(old_leader)
                del target_group_leaders[target_uid]
                if old_leader in leader_spam_started:
                    leader_spam_started.discard(old_leader)
            
            if last_status != current_status:
                status_icon = "🟢 ONLINE" if is_online else "⚫ OFFLINE"
                print(f"\n{BOLD}🧠 SMART MONITOR - UID: {target_uid}")
                print(f"  Status:     {status_icon}")
                print(f"  Game Mode:  {current_status}")
                print(f"  Time:       {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{RS}")
                print(f"{C}Status changed: {last_status} → {current_status}{RS}\n")
                last_status = current_status
                
                with smart_monitor_lock:
                    smart_target_statuses[target_uid] = current_status
            
            if target_uid in target_group_leaders:
                leader_uid = target_group_leaders[target_uid]
                leader_status = get_detailed_status(leader_uid)
                if not leader_status.get('is_online', False):
                    print(f"{Y}⚠️ Leader {leader_uid} went offline, stopping{RS}")
                    stop_spam(leader_uid)
                    
        except Exception as e:
            print(f"{R}❌ Smart monitor error for {target_uid}: {e}{RS}")
        
        time.sleep(3)

def start_smart_monitor(target_uid):
    """Start smart monitoring for a target"""
    with smart_monitor_lock:
        if target_uid in smart_monitor_threads:
            return False, f"Already monitoring {target_uid}"
        
        thread = Thread(target=monitor_target_smart, args=(target_uid,), daemon=True)
        smart_monitor_threads[target_uid] = thread
        thread.start()
        return True, f"Smart monitoring started for {target_uid}"

def stop_smart_monitor(target_uid):
    """Stop smart monitoring for a target"""
    with smart_monitor_lock:
        if target_uid in smart_monitor_threads:
            del smart_monitor_threads[target_uid]
            stop_spam(target_uid)
            return True, f"Smart monitoring stopped for {target_uid}"
    return False, f"No monitor found for {target_uid}"

# ==================== STATUS CHECKER SESSION ====================
_TTL = 6 * 60 * 60

_Hr = {
    'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 9; G011A Build/PI)',
    'Connection': 'Keep-Alive',
    'Accept-Encoding': 'gzip',
    'Content-Type': 'application/x-www-form-urlencoded',
    'Expect': '100-continue',
    'X-Unity-Version': '2018.4.11f1',
    'X-GA': 'v1 1',
    'ReleaseVersion': 'OB54',
}

_cx = {}

def _rdVr(data, pos):
    n = 0
    sh = 0
    while True:
        b = data[pos]
        pos += 1
        n |= (b & 0x7F) << sh
        sh += 7
        if not b & 0x80:
            break
    return n, pos

def _pbF(data):
    out = {}
    pos = 0
    while pos < len(data):
        try:
            tag, pos = _rdVr(data, pos)
            fn = tag >> 3
            wt = tag & 0x7
            if wt == 0:
                v, pos = _rdVr(data, pos)
                out[fn] = v
            elif wt == 2:
                ln, pos = _rdVr(data, pos)
                out[fn] = data[pos:pos+ln]
                pos += ln
            elif wt == 1:
                out[fn] = data[pos:pos+8]
                pos += 8
            elif wt == 5:
                out[fn] = data[pos:pos+4]
                pos += 4
            else:
                break
        except:
            break
    return out

async def _vr(n):
    h = []
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            b |= 0x80
        h.append(b)
        if not n:
            break
    return bytes(h)

async def _enc(hx, k, v):
    return AES.new(k, AES.MODE_CBC, v).encrypt(pad(bytes.fromhex(hx), 16)).hex()

async def _hx(n):
    f = hex(n)[2:]
    return ('0' + f) if len(f) == 1 else f

async def _var(fn, val):
    return await _vr((fn << 3) | 0) + await _vr(val)

async def _len(fn, val):
    e = val.encode() if isinstance(val, str) else val
    return await _vr((fn << 3) | 2) + await _vr(len(e)) + e

async def _pb(flds):
    p = bytearray()
    for f, v in flds.items():
        if isinstance(v, dict):
            p.extend(await _len(f, await _pb(v)))
        elif isinstance(v, int):
            p.extend(await _var(f, v))
        elif isinstance(v, (str, bytes)):
            p.extend(await _len(f, v))
    return p

async def _pk(px, n, k, v):
    e = await _enc(px, k, v)
    _ = await _hx(len(e) // 2)
    m = {2: '000000', 3: '00000', 4: '0000', 5: '000'}
    return bytes.fromhex(n + m.get(len(_), '000000') + _ + e)

async def _fix(rs):
    d = {}
    for r in rs:
        fd = {'wire_type': r.wire_type}
        if r.wire_type in ('varint', 'string', 'bytes'):
            fd['data'] = r.data
        elif r.wire_type == 'length_delimited':
            fd['data'] = await _fix(r.data.results)
        d[r.field] = fd
    return d

async def _parse(hx):
    try:
        from protobuf_decoder.protobuf_decoder import Parser
        return json.dumps(await _fix(Parser().parse(hx)))
    except:
        return None

async def _uidEnc(uid):
    return (await _pb({1: int(uid)})).hex()[2:]

async def _stPkt(uid, k, v):
    ue = await _uidEnc(int(uid))
    return await _pk(f"080112090A05{ue}1005", '0F15', k, v)

async def _rmPkt(ruid, k, v):
    return await _pk((await _pb({1: 1, 2: {1: ruid, 3: {}, 4: 1, 6: 'en'}})).hex(), '0E15', k, v)

def _tdiff(ts):
    d = int((datetime.now() - datetime.fromtimestamp(ts)).total_seconds())
    return f"{(abs(d) % 3600) // 60:02}:{abs(d) % 60:02}"

def _pStatus(pkt):
    data = json.loads(pkt)
    if '5' not in data or 'data' not in data['5']:
        return {'status': 'OFFLINE'}
    jd = data['5']['data']
    if '1' not in jd or 'data' not in jd['1']:
        return {'status': 'OFFLINE'}
    d = jd['1']['data']
    if '3' not in d or 'data' not in d['3']:
        return {'status': 'OFFLINE'}
    st = d['3']['data']
    gc = d.get('9', {}).get('data', 0)
    cm = d.get('10', {}).get('data', 0) + 1 if '10' in d else 0
    go = d.get('8', {}).get('data', 0)
    tg = d.get('4', {}).get('data', 0)
    m5 = d.get('5', {}).get('data')
    m6 = d.get('6', {}).get('data')
    mn = sc = 0
    if tg:
        a, b = _tdiff(tg).split(':')
        mn = int(a)
        sc = int(b)
    
    if st == 4:
        return {
            'status': 'IN_ROOM',
            'room_uid': d.get('15', {}).get('data'),
            'players': f"{d.get('17',{}).get('data',0)}/{d.get('18',{}).get('data',0)}",
            'room_owner': d.get('1', {}).get('data')
        }
    
    base = {
        1: 'SOLO',
        2: 'INSQUAD',
        3: 'INGAME',
        5: 'INGAME',
        7: 'MATCHMAKING',
        6: 'SOCIAL_ISLAND'
    }.get(st, 'OFFLINE')
    
    mode = None
    f14 = d.get('14', {}).get('data')
    if f14 == 1:
        mode = 'TRAINING'
    elif f14 == 2:
        mode = 'SOCIAL_ISLAND'
    
    mm = {
        (2, 1): 'BR_RANK', (5, 23): 'TRAINING', (6, 15): 'CS_RANK',
        (1, 43): 'LONE_WOLF', (1, 1): 'BERMUDA', (1, 15): 'CLASH_SQUAD',
        (1, 29): 'CONVOY_CRUNCH', (1, 61): 'FREE_FOR_ALL'
    }
    if (m5, m6) in mm:
        mode = mm[(m5, m6)]
    
    res = {'status': base, 'mode': mode}
    if base == 'INSQUAD':
        res['squad_owner'] = go
        res['squad_size'] = f"{gc}/{cm}" if gc else None
    if base in ('INGAME', 'INSQUAD') and tg:
        res['time_playing'] = f"{mn}m {sc}s"
    return res

def _pRoom(pkt):
    data = json.loads(pkt)
    rd = data['5']['data']['1']['data']
    mm = {
        1: 'BERMUDA', 201: 'BATTLE_CAGE', 15: 'CLASH_SQUAD', 43: 'LONE_WOLF',
        3: 'RUSH_HOUR', 27: 'BOMB_SQUAD_5V5', 24: 'DEATH_MATCH'
    }
    return {
        'room_id': int(rd['1']['data']),
        'room_name': rd['2']['data'],
        'owner_uid': int(rd['37']['data']['1']['data']),
        'mode': mm.get(rd.get('4', {}).get('data'), 'UNKNOWN'),
        'players': f"{rd.get('6',{}).get('data',0)}/{rd.get('7',{}).get('data',0)}",
        'spectators': rd.get('9', {}).get('data', 0),
        'emulator': bool(rd.get('17', {}).get('data', 1)),
    }

async def _rAll(reader, timeout=5):
    buf = b''
    while True:
        try:
            chunk = await asyncio.wait_for(reader.read(65536), timeout=timeout)
        except asyncio.TimeoutError:
            break
        if not chunk:
            break
        buf += chunk
    return buf

async def _scan(buf, k, v):
    h = buf.hex()
    for mk, pt in [('0f00', '0f'), ('0e00', '0e')]:
        i = h.find(mk)
        if i != -1 and i % 2 == 0:
            return pt, h[i + 10:]
    if len(buf) > 5:
        pl = buf[5:]
        pl = pl[:len(pl) - (len(pl) % 16)]
        if len(pl) >= 16:
            try:
                dc = unpad(AES.new(k, AES.MODE_CBC, v).decrypt(pl), 16).hex()
                for mk, pt in [('0f00', '0f'), ('0e00', '0e')]:
                    i = dc.find(mk)
                    if i != -1 and i % 2 == 0:
                        return pt, dc[i + 10:]
            except:
                pass
    return None, None

async def _mkLogin(oid, atk):
    return await _pb({
        3: str(datetime.now())[:-7], 4: 'free fire', 5: 1, 7: '1.126.7',
        8: 'Android OS 9 / API-28 (PQ3B.190801.10101846/G9650ZHU2ARC6)',
        9: 'Handheld', 10: 'Verizon', 11: 'WIFI', 12: 1920, 13: 1080,
        14: '280', 15: 'ARM64 FP ASIMD AES VMH | 2865 | 4', 16: 3003,
        17: 'Adreno (TM) 640', 18: 'OpenGL ES 3.1 v1.46',
        19: 'Google|34a7dcdf-a7d5-4cb6-8d7e-3b0e448a0c57',
        20: '223.191.51.89', 21: 'en', 22: oid, 23: '4', 24: 'Handheld',
        25: {6: 55, 8: 81},
        29: atk, 30: 1, 73: 3, 78: 3, 79: 2, 81: '64',
        93: 'android', 97: 1, 98: 1, 99: '4', 100: '4',
    })


async def _auth(uid, tok, ts, k, v):
    uh = hex(uid)[2:]
    hd = {9: '0000000', 8: '00000000', 10: '000000', 7: '000000000'}.get(len(uh), '0000000')
    e = await _enc(tok.encode().hex(), k, v)
    el = await _hx(len(e) // 2)
    return f"0115{hd}{uh}{await _hx(ts)}00000{el}{e}"

async def _login():
    sx = ssl.create_default_context()
    sx.check_hostname = False
    sx.verify_mode = ssl.CERT_NONE

    async with aiohttp.ClientSession() as s:
        async with s.post('https://100067.connect.garena.com/oauth/guest/token/grant',
                         headers=_Hr,
                         data={
                             'uid': _ID,
                             'password': _PW,
                             'response_type': 'token',
                             'client_type': '2',
                             'client_secret': '2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3',
                             'client_id': '100067'
                         }, ssl=sx) as r:
            if r.status != 200:
                raise Exception(f"OAuth {r.status}")
            d = await r.json()
            oid = d['open_id']
            atk = d['access_token']

    raw = await _mkLogin(oid, atk)
    ep = AES.new(b'Yg&tc%DEuh6%Zc^8', AES.MODE_CBC, b'6oyZDr22E3ychjM%').encrypt(pad(raw, 16))

    async with aiohttp.ClientSession() as s:
        async with s.post('https://loginbp.ggpolarbear.com/MajorLogin', data=ep, headers=_Hr, ssl=sx) as r:
            if r.status != 200:
                raise Exception(f"MajorLogin {r.status}")
            mr = await r.read()

    mlr = _pbF(mr)
    tok = mlr[8].decode()
    tgt = mlr[1]
    k = mlr[22]
    v = mlr[23]
    ts = mlr[21]
    url = mlr[10].decode()

    h2 = {**_Hr, 'Authorization': f'Bearer {tok}'}
    async with aiohttp.ClientSession() as s:
        async with s.post(f"{url}/GetLoginData", data=ep, headers=h2, ssl=sx) as r:
            if r.status != 200:
                raise Exception(f"GetLoginData {r.status}")
            lr = await r.read()

    ld = _pbF(lr)
    ip, port = ld[14].decode().split(':')
    at = await _auth(int(tgt), tok, int(ts), k, v)
    return {
        'account_id': tgt,
        'token': tok,
        'key': k,
        'iv': v,
        'ip': ip,
        'port': int(port),
        'auth': at,
        'exp': time.time() + _TTL
    }

def _sess():
    global _cx
    if 's' in _cx and _cx['s'] and time.time() < _cx['s']['exp']:
        return _cx['s']
    _cx['s'] = asyncio.run(_login())
    return _cx['s']

async def _query(uid, sx):
    rd, wr = await asyncio.open_connection(sx['ip'], sx['port'])
    try:
        wr.write(bytes.fromhex(sx['auth']))
        await wr.drain()
        await _rAll(rd, timeout=3)
        pkt = await _stPkt(uid, sx['key'], sx['iv'])
        wr.write(pkt)
        await wr.drain()
        buf = await _rAll(rd, timeout=5)
        if not buf:
            return {'status': 'NO_RESPONSE'}
        pt, pl = await _scan(buf, sx['key'], sx['iv'])
        if pt == '0f':
            raw = await _parse(pl)
            if not raw:
                return {'status': 'PARSE_ERROR'}
            info = _pStatus(raw)
            if info.get('status') == 'IN_ROOM':
                wr.write(await _rmPkt(int(info['room_uid']), sx['key'], sx['iv']))
                await wr.drain()
                rb = await _rAll(rd, timeout=5)
                if rb:
                    rt, rp = await _scan(rb, sx['key'], sx['iv'])
                    if rt == '0e':
                        rr = await _parse(rp)
                        if rr:
                            info['room_info'] = _pRoom(rr)
            return info
        elif pt == '0e':
            raw = await _parse(pl)
            return _pRoom(raw) if raw else {'status': 'PARSE_ERROR'}
        return {'status': 'UNKNOWN', 'buf': buf.hex()[:120]}
    finally:
        wr.close()
        try:
            await wr.wait_closed()
        except:
            pass

def get_detailed_status(uid):
    """Get detailed status information"""
    try:
        session = _sess()
        result = asyncio.run(_query(int(uid), session))
        
        detailed = {
            'uid': str(uid),
            'timestamp': datetime.now().isoformat(),
            'is_online': result.get('status', 'OFFLINE') not in ['OFFLINE', 'ERROR', 'NO_RESPONSE'],
            'status': result.get('status', 'UNKNOWN'),
            'mode': result.get('mode', 'N/A'),
        }
        
        if result.get('status') == 'INSQUAD':
            detailed['squad_owner'] = result.get('squad_owner')
            detailed['squad_size'] = result.get('squad_size')
        elif result.get('status') == 'IN_ROOM':
            detailed['room_owner'] = result.get('room_owner')
            detailed['players'] = result.get('players')
            if result.get('room_info'):
                detailed['room_details'] = result['room_info']
        
        if result.get('time_playing'):
            detailed['time_playing'] = result['time_playing']
        
        return detailed
    except Exception as e:
        return {'status': 'ERROR', 'error': str(e), 'uid': str(uid)}

# ==================== ENHANCED SPAM WORKER (MULTI-TARGET) ====================
def spam_worker_multi(targets_list):
    """একাধিক টার্গেটে একসাথে স্প্যাম করার জন্য ওয়ার্কার"""
    print(f"\n{G}{'='*60}{RS}")
    print(f"{G}🎯 MULTI-TARGET SPAM STARTED ON {len(targets_list)} TARGETS:{RS}")
    for tid in targets_list:
        print(f"{G}   ➤ {tid}{RS}")
    print(f"{C}{'='*60}{RS}\n")

    total_requests = 0
    round_number = 0

    def run_async(coro):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(coro)
        except:
            return None
        finally:
            loop.close()

    while True:
        global auto_spam_active
        if not auto_spam_active:
            break

        with active_power_lock:
            current_targets = list(active_power_targets.keys())
            if not current_targets:
                break

        with connected_clients_lock:
            clients_list = list(connected_clients.values())

        if not clients_list:
            time.sleep(2)
            continue

        round_number += 1

        for target_id in current_targets:
            for client in clients_list:
                with active_power_lock:
                    if target_id not in active_power_targets:
                        break

                try:
                    if hasattr(client, 'CliEnts2') and client.key:
                        # === 1. রুম স্প্যাম ===
                        try:
                            open_pkt = openroom(client.key, client.iv)
                            if open_pkt:
                                client.CliEnts2.send(open_pkt)
                            
                            spam_pkt = spmroom(client.key, client.iv, target_id)
                            if spam_pkt:
                                client.CliEnts2.send(spam_pkt)
                                total_requests += 1
                        except:
                            pass

                        # === 2. গ্রুপ ইনভাইট (5 প্লেয়ার) ===
                        try:
                            async def send_invite_5():
                                p1 = await OpEnSq(client.key, client.iv)
                                client.CliEnts2.send(p1)
                                await asyncio.sleep(0.05)
                                p2 = await cHSq(5, target_id, client.key, client.iv)
                                client.CliEnts2.send(p2)
                                await asyncio.sleep(0.05)
                                p3 = await SEnd_InV(5, target_id, client.key, client.iv)
                                client.CliEnts2.send(p3)
                                total_requests += 1
                                await asyncio.sleep(0.05)
                                p4 = await ExiT(client.key, client.iv)
                                client.CliEnts2.send(p4)
                            run_async(send_invite_5())
                        except:
                            pass

                        # === 3. ব্যাজ জয়িন ===
                        for badge_name, badge_value in BADGES.items():
                            try:
                                badge_pkt = create_badge_join_packet(client.key, client.iv, target_id, badge_value)
                                if badge_pkt:
                                    client.CliEnts2.send(badge_pkt)
                                    total_requests += 1
                                    time.sleep(0.03)
                            except:
                                pass

                        # === 4. 3 প্লেয়ার গ্রুপ ইনভাইট ===
                        try:
                            group_pkt_3 = create_group_invite_packet(client.key, client.iv, target_id, 3)
                            if group_pkt_3:
                                client.CliEnts2.send(group_pkt_3)
                                total_requests += 1
                                time.sleep(0.03)
                        except:
                            pass

                        # === 5. 6 প্লেয়ার গ্রুপ ইনভাইট ===
                        try:
                            group_pkt_6 = create_group_invite_packet(client.key, client.iv, target_id, 6)
                            if group_pkt_6:
                                client.CliEnts2.send(group_pkt_6)
                                total_requests += 1
                                time.sleep(0.03)
                        except:
                            pass

                except Exception as e:
                    print(f"{R}❌ Error: {e}{RS}")

                time.sleep(0.05)

        if round_number % 5 == 0:
            print(f"{C}{'='*50}{RS}")
            print(f"{G}📊 Round {round_number} Complete{RS}")
            print(f"{G}📊 Total Requests: {total_requests}{RS}")
            print(f"{G}🎯 Active Targets: {len(current_targets)}{RS}")
            print(f"{G}🤖 Bots Online: {len(clients_list)}{RS}")
            print(f"{C}{'='*50}{RS}\n")
        
        time.sleep(0.5)

    with spam_threads_lock:
        for tid in targets_list:
            if tid in spam_threads:
                del spam_threads[tid]

    print(f"\n{R}🛑 MULTI-SPAM STOPPED ON {len(targets_list)} TARGETS{RS}\n")

def start_multi_spam(targets_list):
    """একাধিক টার্গেটে স্প্যাম শুরু করুন"""
    global auto_spam_active
    
    if isinstance(targets_list, str):
        targets_list = [targets_list]
    
    new_targets = []
    with active_power_lock:
        for target in targets_list:
            if target not in active_power_targets:
                active_power_targets[target] = {
                    'active': True,
                    'start_time': datetime.now()
                }
                new_targets.append(target)
    
    if new_targets:
        auto_spam_active = True
        thread = Thread(target=spam_worker_multi, args=(new_targets,), daemon=True)
        with spam_threads_lock:
            for tid in new_targets:
                spam_threads[tid] = thread
        thread.start()
        return True, f"Started spam on {len(new_targets)} targets: {', '.join(new_targets)}"
    return False, "No new targets to start"

def stop_spam(target_id):
    """একটি নির্দিষ্ট টার্গেটের স্প্যাম বন্ধ করুন"""
    with active_power_lock:
        if target_id in active_power_targets:
            del active_power_targets[target_id]
            return True, f"Spam stopped on: {target_id}"
        return False, f"No active spam on: {target_id}"

def stop_all_spam():
    """সব স্প্যাম বন্ধ করুন"""
    global auto_spam_active
    auto_spam_active = False
    with active_power_lock:
        targets = list(active_power_targets.keys())
        for target in targets:
            del active_power_targets[target]
    return True, f"Stopped all spam ({len(targets)} targets)"

def get_status():
    """বর্তমান স্প্যাম স্ট্যাটাস পাওয়া"""
    with active_power_lock:
        active_targets = list(active_power_targets.keys())
        targets_info = []
        for target in active_targets:
            info = active_power_targets[target]
            start_time = info.get('start_time')
            elapsed = (datetime.now() - start_time).total_seconds() if start_time else 0
            targets_info.append({
                'uid': target,
                'elapsed_minutes': int(elapsed / 60)
            })
    
    with connected_clients_lock:
        accounts_count = len(connected_clients)
        accounts_list = list(connected_clients.keys())
    
    with smart_monitor_lock:
        monitored_targets = [
            {'uid': uid, 'status': smart_target_statuses.get(uid, 'CHECKING...')} 
            for uid in smart_monitor_threads.keys()
        ]
    
    return {
        'active_targets': targets_info,
        'active_count': len(active_targets),
        'accounts_count': accounts_count,
        'accounts_list': accounts_list[:50],
        'auto_uids': auto_uids,
        'invite_uids': invite_uids,
        'auto_active': auto_spam_active,
        'smart_monitored': monitored_targets
    }

# ==================== AUTO REFRESH ====================
def auto_refresh_and_restart():
    """প্রতি ৭ মিনিটে রিফ্রেশ - কিন্তু ACTIVE TARGETS অফ হবে না"""
    global auto_spam_active, refresh_timer
    
    print(f"\n{Y}{'='*50}{RS}")
    print(f"{Y}🔄 AUTO REFRESH INITIATED (KEEPING ACTIVE TARGETS){RS}")
    print(f"{Y}{'='*50}{RS}\n")
    
    # আগে এখানে stop_all_spam() ছিল, যা এখন সরিয়ে দেওয়া হয়েছে।
    # এর ফলে বর্তমানে যা চলছে তা বন্ধ হবে না।

    # ফাইল থেকে নতুন UID গুলো লোড করা (যদি আপনি ফাইলে নতুন কিছু লিখে থাকেন)
    load_auto_uids()
    load_invite_uids()
    
    # SMART MONITORED (auto_uid.txt) - শুধুমাত্র নতুন UID গুলো যোগ করা হবে
    if auto_uids:
        print(f"{G}🧠 Checking for new SMART monitor targets...{RS}")
        for uid in auto_uids:
            with smart_monitor_lock:
                if uid not in smart_monitor_threads:
                    start_smart_monitor(uid)
    
    # ACTIVE TARGETS (inv_uid.txt) - যদি স্প্যাম থ্রেড বন্ধ থাকে তবেই চালু করবে
    if invite_uids:
        if not invite_spam_thread or not invite_spam_thread.is_alive():
            print(f"{G}🎯 Starting ACTIVE TARGETS worker...{RS}")
            start_invite_targets_spam()
        else:
            print(f"{G}✅ ACTIVE TARGETS worker is already running.{RS}")
    
    # টাইমার রিসেট করা
    if refresh_timer:
        refresh_timer.cancel()
    refresh_timer = threading.Timer(7 * 60, auto_refresh_and_restart)
    refresh_timer.daemon = True
    refresh_timer.start()
    
    print(f"{G}✅ Refresh Complete. Next check in 7 minutes.{RS}\n")

def start_auto_refresh():
    global refresh_timer
    if refresh_timer:
        refresh_timer.cancel()
    refresh_timer = threading.Timer(7 * 60, auto_refresh_and_restart)
    refresh_timer.daemon = True
    refresh_timer.start()
    print(f"{G}⏰ Auto-refresh timer started (every 7 minutes){RS}")

def start_auto_spam():
    """অটো স্প্যাম শুরু করুন (auto_uid.txt স্মার্ট মনিটর + inv_uid.txt সরাসরি স্প্যাম)"""
    global auto_spam_active
    
    if auto_spam_active:
        return False, "Auto spam already active"
    
    auto_spam_active = True
    
    # SMART MONITORED (auto_uid.txt)
    if auto_uids:
        for uid in auto_uids:
            start_smart_monitor(uid)
        print(f"{G}🧠 Started SMART monitors on {len(auto_uids)} UIDs{RS}")
    
    # ACTIVE TARGETS (inv_uid.txt)
    if invite_uids:
        start_invite_targets_spam()
        print(f"{G}🎯 Started ACTIVE TARGETS spam on {len(invite_uids)} UIDs{RS}")
    
    return True, f"Auto spam started (Smart: {len(auto_uids)}, Active: {len(invite_uids)})"

def stop_auto_spam():
    """অটো স্প্যাম বন্ধ করুন"""
    global auto_spam_active
    auto_spam_active = False
    
    # স্মার্ট মনিটর বন্ধ
    with smart_monitor_lock:
        monitors = list(smart_monitor_threads.keys())
        for uid in monitors:
            del smart_monitor_threads[uid]
    
    # একটিভ টার্গেট স্প্যাম বন্ধ
    stop_invite_targets_spam()
    stop_all_spam()
    
    return True, "Auto spam stopped"

# ==================== ACCOUNTS ====================
ACCOUNTS = []

def load_accounts_from_file(filename="accs.txt"):
    loaded_accounts = []
    try:
        if not os.path.exists(filename):
            with open(filename, "w") as f:
                f.write(f"# Format: UID:PASSWORD\n")
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
                        loaded_accounts.append({'id': uid, 'password': pwd})
        
        print(f"{G}📦 Loaded {len(loaded_accounts)} accounts from {filename}{RS}")
    except Exception as e:
        print(f"{R}❌ Error loading {filename}: {e}{RS}")
    
    return loaded_accounts

ACCOUNTS = load_accounts_from_file("accs.txt")

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
            # --- প্রোটোবাফ ডাটা তৈরি ---
            major_login = MajoRLoGinrEq_pb2.MajorLogin()
            major_login.event_time = str(datetime.now())[:-7]
            major_login.game_name = "free fire"
            major_login.platform_id = 2
            major_login.client_version = "1.126.7" # এখানে আপনার ভার্সনটি দিন
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
            major_login.game_disk_storage_available = random.randint(18000, 25000)
            major_login.external_sdcard_total_storage = 119234
            major_login.external_sdcard_avail_storage = random.randint(25000, 60000)
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

            # সিরিয়ালাইজ এবং এনক্রিপশন
            raw_data = major_login.SerializeToString()
            key = b'Yg&tc%DEuh6%Zc^8'
            iv = b'6oyZDr22E3ychjM%'
            cipher = AES.new(key, AES.MODE_CBC, iv)
            self.PaYload = cipher.encrypt(pad(raw_data, 16))

        except Exception as e:
            print(f"{R}❌ Protobuf building error: {e}{RS}")
            time.sleep(5)
            return self.ToKen_GeneRaTe(Access_ToKen, Access_Uid)

        # সার্ভারে রিকোয়েস্ট পাঠানো
        self.ResPonse = requests.post(self.UrL, headers=self.HeadErs, data=self.PaYload, verify=False)        
        
        if self.ResPonse.status_code == 200:
            try:
                # রেসপন্স ডিকোড করা
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

# ==================== FLASK ROUTES ====================
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

# ==================== NORMAL SPAM GET API ====================
@app.route('/api/normal', methods=['GET'])
def api_normal_get_control():
    """
    Get API for Normal Spam Control
    Usage:
    - ON:  /api/normal?action=on&uid=12345678,98765432
    - OFF: /api/normal?action=off&uid=12345678
    - OFF ALL: /api/normal?action=off
    """
    action = request.args.get('action', '').lower()
    target_input = request.args.get('uid', '').strip()

    if action == 'on':
        if not target_input:
            return jsonify({'success': False, 'message': 'Target UID(s) required!'}), 400
        
        # কমা বা স্পেস দিয়ে আলাদা করা UIDs হ্যান্ডেল করা
        targets = []
        if ',' in target_input:
            targets = [tid.strip() for tid in target_input.split(',') if tid.strip().isdigit()]
        else:
            targets = [tid.strip() for tid in target_input.split() if tid.strip().isdigit()]
            
        if not targets:
            # যদি সরাসরি একটি UID হয়
            if target_input.isdigit():
                targets = [target_input]
            else:
                return jsonify({'success': False, 'message': 'Invalid UID format!'}), 400

        success, message = start_multi_spam(targets)
        return jsonify({'success': success, 'message': message})

    elif action == 'off':
        if target_input:
            # নির্দিষ্ট একটি UID অফ করা
            success, message = stop_spam(target_input)
            stop_smart_monitor(target_input) # যদি স্মার্ট মনিটরে থাকে সেটাও অফ হবে
            return jsonify({'success': success, 'message': message})
        else:
            # সব স্প্যাম অফ করা
            stop_all_spam()
            stop_invite_targets_spam()
            return jsonify({'success': True, 'message': 'All normal spam stopped successfully!'})

    return jsonify({'success': False, 'message': 'Invalid action! Use action=on or action=off'}), 400

@app.route('/api/start', methods=['POST'])
def api_start():
    data = request.get_json()
    target_input = data.get('uid', '').strip()
    smart_mode = data.get('smart', False)
    
    if ',' in target_input:
        targets = [tid.strip() for tid in target_input.split(',') if tid.strip().isdigit()]
    elif ' ' in target_input:
        targets = [tid.strip() for tid in target_input.split() if tid.strip().isdigit()]
    else:
        targets = [target_input] if target_input.isdigit() else []
    
    if not targets:
        return jsonify({'success': False, 'message': 'Valid UID(s) required'})
    
    if smart_mode:
        success_count = 0
        for uid in targets:
            success, msg = start_smart_monitor(uid)
            if success:
                success_count += 1
        return jsonify({'success': success_count > 0, 'message': f'Smart monitoring started on {success_count}/{len(targets)} targets'})
    else:
        success, message = start_multi_spam(targets)
        return jsonify({'success': success, 'message': message})

@app.route('/api/stop', methods=['POST'])
def api_stop():
    data = request.get_json()
    target_id = data.get('uid', '').strip()
    
    if not target_id:
        return jsonify({'success': False, 'message': 'UID is required'})
    
    success, message = stop_spam(target_id)
    stop_smart_monitor(target_id)
    return jsonify({'success': success, 'message': message})

@app.route('/api/stop-all', methods=['POST'])
def api_stop_all():
    stop_auto_spam()
    return jsonify({'success': True, 'message': 'All spam stopped'})

@app.route('/api/status', methods=['GET'])
def api_status():
    status = get_status()
    return jsonify({'success': True, 'data': status})

@app.route('/api/accounts', methods=['GET'])
def api_accounts():
    with connected_clients_lock:
        return jsonify({
            'success': True,
            'count': len(connected_clients),
            'accounts': list(connected_clients.keys())
        })

@app.route('/api/auto-uids', methods=['GET'])
def api_get_auto_uids():
    return jsonify({'success': True, 'uids': auto_uids})

@app.route('/api/auto-uids', methods=['POST'])
def api_update_auto_uids():
    data = request.get_json()
    uids = data.get('uids', [])
    global auto_uids
    auto_uids = [uid.strip() for uid in uids if uid.strip().isdigit()]
    save_auto_uids(auto_uids)
    return jsonify({'success': True, 'message': f'Saved {len(auto_uids)} UIDs'})

@app.route('/api/invite-uids', methods=['GET'])
def api_get_invite_uids():
    return jsonify({'success': True, 'uids': invite_uids})

@app.route('/api/invite-uids', methods=['POST'])
def api_update_invite_uids():
    data = request.get_json()
    uids = data.get('uids', [])
    global invite_uids
    invite_uids = [uid.strip() for uid in uids if uid.strip().isdigit()]
    save_invite_uids(invite_uids)
    # নতুন UIDs যোগ করলে স্প্যাম শুরু করুন
    if invite_uids:
        start_invite_targets_spam()
    return jsonify({'success': True, 'message': f'Saved {len(invite_uids)} invite UIDs'})

@app.route('/api/start-auto', methods=['POST'])
def api_start_auto():
    success, message = start_auto_spam()
    return jsonify({'success': success, 'message': message})

@app.route('/api/stop-auto', methods=['POST'])
def api_stop_auto():
    success, message = stop_auto_spam()
    return jsonify({'success': success, 'message': message})

@app.route('/api/check-status', methods=['POST'])
def api_check_status():
    data = request.get_json()
    target_id = data.get('uid', '').strip()
    
    if not target_id:
        return jsonify({'success': False, 'message': 'UID is required'})
    
    status = get_detailed_status(target_id)
    return jsonify({'success': True, 'data': status})

@app.route('/api/smart-monitors', methods=['GET'])
def api_smart_monitors():
    with smart_monitor_lock:
        return jsonify({
            'success': True,
            'monitored': list(smart_monitor_threads.keys())
        })

# ==================== HTML TEMPLATE ====================
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=yes">
    <title>MAHIR SPAM - ULTIMATE MULTI-TARGET</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        :root {
            --bg-color: rgba(9, 14, 23, 0.85);
            --card-bg: rgba(17, 24, 38, 0.95);
            --text-main: #ffffff;
            --text-muted: #8b9bb4;
            --primary-red: #ff3366;
            --primary-blue: #00d4ff;
            --primary-purple: #9b59b6;
            --border-color: #233045;
            --success: #00cc66;
            --warning: #ffd700;
            --smart: #9b59b6;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Poppins', sans-serif; }
        body { background-color: #000; color: var(--text-main); display: flex; justify-content: center; align-items: center; min-height: 100vh; padding: 20px; overflow-x: hidden; }
        #matrix-canvas { position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; z-index: -1; }
        
        .app-container { width: 100%; max-width: 700px; padding: 30px 20px; display: flex; flex-direction: column; gap: 25px; background: var(--bg-color); backdrop-filter: blur(8px); border-radius: 20px; border: 1px solid rgba(255, 51, 102, 0.2); box-shadow: 0 0 40px rgba(0, 0, 0, 0.8); z-index: 1; }
        
        .header { text-align: center; margin-bottom: 15px; }
        .premium-badge { color: var(--warning); font-size: 0.85rem; font-weight: 600; letter-spacing: 2px; display: flex; justify-content: center; gap: 10px; margin-bottom: 10px; flex-wrap: wrap; }
        .main-title { font-size: 2.5rem; font-weight: 800; background: linear-gradient(90deg, var(--primary-red), var(--primary-purple)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin: 15px 0; }
        
        .card { background-color: var(--card-bg); border-radius: 20px; padding: 25px 20px; border: 1px solid var(--border-color); box-shadow: 0 10px 30px rgba(0,0,0,0.5); }
        .card-header { display: flex; align-items: center; gap: 15px; margin-bottom: 20px; }
        .icon-circle { width: 40px; height: 40px; border-radius: 50%; background: rgba(26,35,51,0.9); display: flex; justify-content: center; align-items: center; color: var(--primary-red); font-size: 1.2rem; }
        .card-title h3 { font-size: 1.2rem; font-weight: 600; }
        .card-title p { font-size: 0.75rem; color: var(--text-muted); }
        
        .input-group { margin-bottom: 15px; }
        .input-label { display: flex; align-items: center; gap: 8px; color: var(--text-muted); font-size: 0.85rem; margin-bottom: 8px; }
        input[type="text"].plain-input, textarea { width: 100%; background: rgba(9,14,23,0.7); border: 1px solid var(--border-color); color: white; padding: 15px; border-radius: 12px; font-size: 1rem; outline: none; }
        input[type="text"].plain-input:focus, textarea:focus { border-color: var(--primary-red); box-shadow: 0 0 10px rgba(255,51,102,0.3); }
        textarea { resize: vertical; font-family: monospace; }
        
        .btn { width: 100%; padding: 14px; border: none; border-radius: 12px; font-size: 1rem; font-weight: 600; cursor: pointer; display: flex; justify-content: center; align-items: center; gap: 10px; transition: 0.3s; margin-top: 12px; }
        .btn-primary { background: linear-gradient(90deg, var(--primary-red), var(--primary-purple)); color: white; }
        .btn-primary:hover { transform: translateY(-2px); box-shadow: 0 5px 20px rgba(255,51,102,0.3); }
        .btn-danger-outline { background: transparent; border: 1px solid var(--primary-red); color: var(--primary-red); }
        .btn-danger-outline:hover { background: rgba(255,51,102,0.1); transform: translateY(-2px); }
        .btn-warning { background: transparent; border: 1px solid var(--warning); color: var(--warning); }
        .btn-warning:hover { background: rgba(255,215,0,0.1); transform: translateY(-2px); }
        .btn-success { background: transparent; border: 1px solid var(--success); color: var(--success); }
        .btn-success:hover { background: rgba(0,204,102,0.1); transform: translateY(-2px); }
        .btn-smart { background: linear-gradient(90deg, #8e44ad, #9b59b6); color: white; }
        .btn-smart:hover { transform: translateY(-2px); box-shadow: 0 5px 20px rgba(155,89,182,0.3); }
        
        .console-box { background: #000; border: 1px solid var(--border-color); border-radius: 12px; height: 200px; padding: 15px; font-family: 'Courier New', monospace; font-size: 0.75rem; color: var(--primary-blue); overflow-y: auto; text-align: left; }
        .console-line { margin-bottom: 6px; }
        .console-line .time { color: var(--text-muted); margin-right: 10px; }
        .console-line .success { color: var(--success); }
        .console-line .error { color: var(--primary-red); }
        .console-line .info { color: var(--primary-blue); }
        .console-line .smart { color: #9b59b6; }
        
        .badge-info { background: rgba(155,89,182,0.1); color: var(--primary-purple); border: 1px solid var(--primary-purple); padding: 12px; border-radius: 12px; text-align: center; font-size: 0.8rem; font-weight: 600; margin-top: 15px; }
        .status-badge { background: rgba(0,204,102,0.1); color: var(--success); border: 1px solid var(--success); padding: 12px; border-radius: 12px; text-align: center; display: flex; justify-content: center; align-items: center; gap: 8px; margin-top: 10px; font-size: 0.8rem; font-weight: 600; }
        .status-dot { width: 8px; height: 8px; background: var(--success); border-radius: 50%; animation: pulse 1.5s infinite; }
        .smart-badge { background: rgba(155,89,182,0.1); color: #9b59b6; border: 1px solid #9b59b6; }
        
        @keyframes pulse { 0%,100% { transform: scale(1); opacity: 1; } 50% { transform: scale(1.3); opacity: 0.5; } }
        
        .active-list, .accounts-list { max-height: 200px; overflow-y: auto; margin-top: 10px; }
        .active-item { background: rgba(30,30,40,0.8); padding: 12px; margin: 8px 0; border-radius: 10px; display: flex; justify-content: space-between; align-items: center; border-left: 3px solid #ff3366; }
        .active-uid { font-family: monospace; font-weight: bold; color: #ff3366; font-size: 14px; }
        .smart-item { border-left-color: #9b59b6; }
        .stop-small { background: #eb3349; color: white; border: none; padding: 6px 18px; border-radius: 8px; cursor: pointer; font-size: 12px; font-weight: bold; transition: 0.2s; }
        .stop-small:hover { background: #c0392b; }
        .account-item { background: rgba(30,30,40,0.6); padding: 6px 12px; margin: 4px 0; border-radius: 8px; font-family: monospace; font-size: 11px; color: #4facfe; }
        
        .flex-buttons { display: flex; gap: 12px; margin-top: 12px; }
        .flex-buttons .btn { margin-top: 0; }
        
        .refresh-badge { background: rgba(255,215,0,0.15); color: var(--warning); border: 1px solid var(--warning); border-radius: 12px; padding: 8px; text-align: center; font-size: 0.7rem; margin-top: 10px; }
        
        .copyright { text-align: center; color: var(--text-muted); font-size: 0.7rem; margin-top: 20px; }
        
        ::-webkit-scrollbar { width: 5px; }
        ::-webkit-scrollbar-track { background: #1a1a2e; border-radius: 10px; }
        ::-webkit-scrollbar-thumb { background: #ff3366; border-radius: 10px; }
        
        .mode-toggle { display: flex; gap: 10px; margin-bottom: 15px; }
        .mode-btn { flex: 1; padding: 10px; background: rgba(30,30,40,0.6); border: 1px solid var(--border-color); border-radius: 10px; cursor: pointer; text-align: center; transition: 0.3s; }
        .mode-btn.active { background: linear-gradient(90deg, var(--primary-red), var(--primary-purple)); border-color: var(--primary-red); }
        .mode-btn.smart-mode.active { background: linear-gradient(90deg, #8e44ad, #9b59b6); }
        
        .feature-badge {
            display: inline-block;
            background: rgba(255,51,102,0.2);
            color: #ff3366;
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 10px;
            margin: 2px;
        }
        
        .multi-hint {
            background: rgba(0,212,255,0.1);
            border: 1px solid #00d4ff;
            border-radius: 8px;
            padding: 8px;
            font-size: 11px;
            color: #00d4ff;
            margin-top: 8px;
            text-align: center;
        }
    </style>
</head>
<body>
    <canvas id="matrix-canvas"></canvas>

    <div class="app-container">
        <div class="header">
            <div class="premium-badge"><i class="fa-solid fa-crown"></i> ULTIMATE MULTI-TARGET</div>
            <h1 class="main-title">MAHIR<br>SPAM</h1>
            <div class="premium-badge">
                <i class="fa-solid fa-users"></i> 3/5/6 INVITE | 
                <i class="fa-solid fa-medal"></i> V-BADGE | 
                <i class="fa-solid fa-brain"></i> SMART |
                <i class="fa-solid fa-layer-group"></i> MULTI-TARGET
            </div>
        </div>

        <!-- Auto UIDs Card -->
        <div class="card">
            <div class="card-header">
                <div class="icon-circle"><i class="fa-solid fa-file-alt"></i></div>
                <div class="card-title"><h3>AUTO UIDs (auto_uid.txt)</h3><p>সব UID তে একসাথে স্প্যাম করবে</p></div>
            </div>
            <textarea id="autoUidsText" rows="4" placeholder="এক লাইনে একটি UID দিয়ে সব টার্গেট লিখুন&#10;Example:&#10;1234567890&#10;0987654321&#10;1122334455"></textarea>
            <div class="flex-buttons">
                <button class="btn btn-success" onclick="saveAutoUids()"><i class="fa-solid fa-save"></i> SAVE</button>
                <button class="btn btn-smart" onclick="startAutoSpam()"><i class="fa-solid fa-brain"></i> START SMART</button>
                <button class="btn btn-danger-outline" onclick="stopAutoSpam()"><i class="fa-solid fa-stop"></i> STOP ALL</button>
            </div>
        </div>

        <!-- Invite UIDs Card -->
        <div class="card">
            <div class="card-header">
                <div class="icon-circle"><i class="fa-solid fa-user-plus"></i></div>
                <div class="card-title"><h3>INVITE UIDs (inv_uid.txt)</h3><p>এই UID গুলো ইনভাইট পাবে</p></div>
            </div>
            <textarea id="inviteUidsText" rows="3" placeholder="এক লাইনে একটি UID"></textarea>
            <div class="flex-buttons">
                <button class="btn btn-purple" onclick="saveInviteUids()"><i class="fa-solid fa-save"></i> SAVE INVITE UIDs</button>
            </div>
        </div>

        <!-- Single/Multi Target Card -->
        <div class="card">
            <div class="card-header">
                <div class="icon-circle"><i class="fa-solid fa-bullseye"></i></div>
                <div class="card-title"><h3>TARGET UIDs</h3><p>একাধিক UID কমা(,) বা স্পেস দিয়ে আলাদা করুন</p></div>
            </div>
            <div class="mode-toggle">
                <div id="normalModeBtn" class="mode-btn active" onclick="setMode('normal')"><i class="fa-solid fa-fire"></i> NORMAL</div>
                <div id="smartModeBtn" class="mode-btn smart-mode" onclick="setMode('smart')"><i class="fa-solid fa-brain"></i> SMART</div>
            </div>
            <div class="input-group">
                <div class="input-label"><i class="fa-solid fa-crosshairs"></i> TARGET UID(s)</div>
                <input type="text" id="startUid" class="plain-input" placeholder="এক বা একাধিক UID: 1234567890,0987654321,1122334455">
            </div>
            <div class="multi-hint">
                <i class="fa-solid fa-info-circle"></i> একাধিক UID: কমা(,) বা স্পেস দিয়ে আলাদা করুন যেমন: 1234567890,0987654321,1122334455
            </div>
            <div class="flex-buttons">
                <button class="btn btn-primary" onclick="startSpam()"><i class="fa-solid fa-play"></i> START SPAM</button>
                <button class="btn btn-smart" onclick="checkAndStartSmart()"><i class="fa-solid fa-search"></i> CHECK & START</button>
            </div>
        </div>

        <!-- Stop Card -->
        <div class="card">
            <div class="card-header">
                <div class="icon-circle"><i class="fa-solid fa-stop"></i></div>
                <div class="card-title"><h3>STOP SPAM</h3><p>একটি বা সব টার্গেট বন্ধ করুন</p></div>
            </div>
            <div class="input-group">
                <div class="input-label"><i class="fa-solid fa-crosshairs"></i> UID TO STOP</div>
                <input type="text" id="stopUid" class="plain-input" placeholder="Enter UID to Stop">
            </div>
            <div class="flex-buttons">
                <button class="btn btn-danger-outline" onclick="stopSpam()"><i class="fa-solid fa-power-off"></i> STOP</button>
                <button class="btn btn-warning" onclick="stopAllSpam()"><i class="fa-solid fa-stop-circle"></i> STOP ALL</button>
            </div>
        </div>

        <!-- Status Card -->
        <div class="card">
            <div class="card-header">
                <div class="icon-circle"><i class="fa-solid fa-terminal"></i></div>
                <div class="card-title"><h3>Console & Status</h3><p>Live Logs</p></div>
            </div>
            
            <div class="console-box" id="consoleBox">
                <div class="console-line"><span class="time">[System]</span> <span class="info">MAHIR SPAM ULTIMATE Ready</span></div>
                <div class="console-line"><span class="time">[System]</span> <span class="info">Multi-Target Support: একসাথে যত ইচ্ছে UID তে স্প্যাম</span></div>
                <div class="console-line"><span class="time">[System]</span> <span class="info">Auto-refresh every 7 minutes</span></div>
            </div>
            
            <div class="badge-info"><i class="fa-solid fa-medal"></i> V-BADGE + PRO_BADGE + CRAFTLAND + MODERATOR</div>
            <div class="status-badge">
                <div class="status-dot"></div>
                <span>STATUS: <span id="statusText">IDLE</span></span>
            </div>
            <div class="badge smart-badge">
                <i class="fa-solid fa-brain"></i> SMART MONITORING: <span id="smartCount">0</span> targets
            </div>
            <div class="refresh-badge">
                <i class="fa-solid fa-clock"></i> Auto-refresh every 7 minutes
            </div>
        </div>

        <!-- Features Card -->
        <div class="card">
            <div class="card-header">
                <div class="icon-circle"><i class="fa-solid fa-star"></i></div>
                <div class="card-title"><h3>SPAM FEATURES</h3><p>What's included</p></div>
            </div>
            <div style="display: flex; flex-wrap: wrap; gap: 8px;">
                <span class="feature-badge"><i class="fa-solid fa-door-open"></i> Room Join</span>
                <span class="feature-badge"><i class="fa-solid fa-user-group"></i> 3-Player Group</span>
                <span class="feature-badge"><i class="fa-solid fa-user-group"></i> 5-Player Group</span>
                <span class="feature-badge"><i class="fa-solid fa-user-group"></i> 6-Player Group</span>
                <span class="feature-badge"><i class="fa-solid fa-medal"></i> V-Badge Join</span>
                <span class="feature-badge"><i class="fa-solid fa-trophy"></i> PRO Badge Join</span>
                <span class="feature-badge"><i class="fa-solid fa-hammer"></i> CRAFTLAND Badge</span>
                <span class="feature-badge"><i class="fa-solid fa-shield"></i> MODERATOR Badge</span>
                <span class="feature-badge"><i class="fa-solid fa-brain"></i> Smart Monitor</span>
                <span class="feature-badge"><i class="fa-solid fa-chart-line"></i> Status Check</span>
                <span class="feature-badge"><i class="fa-solid fa-layer-group"></i> Multi-Target</span>
            </div>
        </div>

        <!-- Active Targets Card -->
        <div class="card">
            <div class="card-header">
                <div class="icon-circle"><i class="fa-solid fa-list"></i></div>
                <div class="card-title"><h3>ACTIVE TARGETS</h3><p>সক্রিয় টার্গেট গুলো</p></div>
            </div>
            <div id="activeSpamList" class="active-list">
                <div class="console-line">📭 No active targets</div>
            </div>
        </div>

        <!-- Smart Monitored Card -->
        <div class="card">
            <div class="card-header">
                <div class="icon-circle"><i class="fa-solid fa-brain"></i></div>
                <div class="card-title"><h3>SMART MONITORED</h3><p>স্মার্ট মনিটরে থাকা টার্গেট</p></div>
            </div>
            <div id="smartMonitoredList" class="active-list">
                <div class="console-line">📭 No smart monitored targets</div>
            </div>
        </div>

        <!-- Connected Accounts Card -->
        <div class="card">
            <div class="card-header">
                <div class="icon-circle"><i class="fa-solid fa-users"></i></div>
                <div class="card-title"><h3>CONNECTED ACCOUNTS</h3><p>অনলাইন অ্যাকাউন্ট</p></div>
            </div>
            <div id="accountsList" class="accounts-list">
                <div class="console-line">Loading...</div>
            </div>
        </div>

        <div class="copyright">
            MAHIR SPAM ULTIMATE <i class="fa-solid fa-heart" style="color: #ff3366;"></i> v7.0 | যত ইচ্ছে UID তে একসাথে স্প্যাম
        </div>
    </div>

    <script>
        let currentMode = 'normal';
        
        const canvas = document.getElementById('matrix-canvas');
        const ctx = canvas.getContext('2d');
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
        const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789@#$%&'.split('');
        const fontSize = 14;
        const columns = canvas.width / fontSize;
        const drops = Array(Math.floor(columns)).fill(1);

        function drawMatrix() {
            ctx.fillStyle = 'rgba(0, 0, 0, 0.05)';
            ctx.fillRect(0, 0, canvas.width, canvas.height);
            ctx.fillStyle = '#ff3366';
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

        function logToConsole(message, type = 'info') {
            const consoleBox = document.getElementById('consoleBox');
            const now = new Date();
            const timeStr = now.toLocaleTimeString();
            const line = document.createElement('div');
            line.className = 'console-line';
            line.innerHTML = `<span class="time">[${timeStr}]</span> <span class="${type}">${message}</span>`;
            consoleBox.appendChild(line);
            consoleBox.scrollTop = consoleBox.scrollHeight;
            if (consoleBox.children.length > 100) consoleBox.removeChild(consoleBox.children[0]);
        }

        function setMode(mode) {
            currentMode = mode;
            document.getElementById('normalModeBtn').classList.remove('active');
            document.getElementById('smartModeBtn').classList.remove('active');
            if (mode === 'normal') {
                document.getElementById('normalModeBtn').classList.add('active');
                logToConsole('🔄 NORMAL মোড সক্রিয় (সব টার্গেটে একসাথে স্প্যাম)', 'info');
            } else {
                document.getElementById('smartModeBtn').classList.add('active');
                logToConsole('🧠 SMART মোড সক্রিয় (স্ট্যাটাস দেখে অটো স্প্যাম)', 'smart');
            }
        }

        async function loadAutoUids() {
            try {
                const response = await fetch('/api/auto-uids');
                const data = await response.json();
                if (data.success && data.uids) {
                    document.getElementById('autoUidsText').value = data.uids.join('\\n');
                }
            } catch (error) { console.error('Error:', error); }
        }

        async function loadInviteUids() {
            try {
                const response = await fetch('/api/invite-uids');
                const data = await response.json();
                if (data.success && data.uids) {
                    document.getElementById('inviteUidsText').value = data.uids.join('\\n');
                }
            } catch (error) { console.error('Error:', error); }
        }

        async function saveAutoUids() {
            const text = document.getElementById('autoUidsText').value;
            const uids = text.split('\\n').filter(line => line.trim() && /^\\d+$/.test(line.trim())).map(l => l.trim());
            
            try {
                const response = await fetch('/api/auto-uids', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ uids: uids })
                });
                const data = await response.json();
                if (data.success) {
                    logToConsole(`✅ ${uids.length} টি UID auto_uid.txt এ সেভ হয়েছে`, 'success');
                }
            } catch (error) { logToConsole(`❌ Error: ${error.message}`, 'error'); }
        }

        async function saveInviteUids() {
            const text = document.getElementById('inviteUidsText').value;
            const uids = text.split('\\n').filter(line => line.trim() && /^\\d+$/.test(line.trim())).map(l => l.trim());
            
            try {
                const response = await fetch('/api/invite-uids', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ uids: uids })
                });
                const data = await response.json();
                if (data.success) {
                    logToConsole(`✅ ${uids.length} টি UID inv_uid.txt এ সেভ হয়েছে`, 'success');
                }
            } catch (error) { logToConsole(`❌ Error: ${error.message}`, 'error'); }
        }

        async function startAutoSpam() {
            try {
                const response = await fetch('/api/start-auto', { method: 'POST' });
                const data = await response.json();
                if (data.success) {
                    logToConsole(`🧠 ${data.message}`, 'smart');
                    refreshStatus();
                } else {
                    logToConsole(`❌ ${data.message}`, 'error');
                }
            } catch (error) { logToConsole(`❌ Error: ${error.message}`, 'error'); }
        }

        async function stopAutoSpam() {
            try {
                const response = await fetch('/api/stop-auto', { method: 'POST' });
                const data = await response.json();
                if (data.success) {
                    logToConsole(`✅ ${data.message}`, 'success');
                    refreshStatus();
                }
            } catch (error) { logToConsole(`❌ Error: ${error.message}`, 'error'); }
        }

        async function checkAndStartSmart() {
            const uidInput = document.getElementById('startUid').value.trim();
            if (!uidInput) { logToConsole('❌ টার্গেট UID দিন!', 'error'); return; }
            
            let uids = [];
            if (uidInput.includes(',')) {
                uids = uidInput.split(',').map(u => u.trim()).filter(u => /^\\d+$/.test(u));
            } else if (uidInput.includes(' ')) {
                uids = uidInput.split(' ').map(u => u.trim()).filter(u => /^\\d+$/.test(u));
            } else {
                uids = [uidInput];
            }
            
            if (uids.length === 0) {
                logToConsole('❌ সঠিক UID দিন!', 'error');
                return;
            }
            
            for (const uid of uids) {
                logToConsole(`🔍 ${uid} এর স্ট্যাটাস চেক করা হচ্ছে...`, 'info');
                
                try {
                    const response = await fetch('/api/check-status', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ uid: uid })
                    });
                    const data = await response.json();
                    if (data.success) {
                        const status = data.data;
                        logToConsole(`📊 ${uid}: ${status.status} | Online: ${status.is_online}`, 'smart');
                        
                        if (status.is_online && status.status !== 'INGAME' && status.status !== 'MATCHMAKING') {
                            await startSmartSpam(uid);
                        } else {
                            logToConsole(`⏸️ ${uid} এর স্ট্যাটাস ${status.status}, স্মার্ট মনিটর শুরু হচ্ছে...`, 'warning');
                            await startSmartSpam(uid);
                        }
                    }
                } catch (error) { logToConsole(`❌ Error: ${error.message}`, 'error'); }
            }
        }

        async function startSmartSpam(uid) {
            try {
                const response = await fetch('/api/start', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ uid: uid, smart: true })
                });
                const data = await response.json();
                if (data.success) {
                    logToConsole(`🧠 ${data.message}`, 'smart');
                    refreshStatus();
                } else {
                    logToConsole(`❌ ${data.message}`, 'error');
                }
            } catch (error) { logToConsole(`❌ Error: ${error.message}`, 'error'); }
        }

        async function startSpam() {
            const uidInput = document.getElementById('startUid').value.trim();
            if (!uidInput) { logToConsole('❌ টার্গেট UID দিন!', 'error'); return; }
            
            // একাধিক UID পার্সিং
            let uids = [];
            if (uidInput.includes(',')) {
                uids = uidInput.split(',').map(u => u.trim()).filter(u => /^\\d+$/.test(u));
            } else if (uidInput.includes(' ')) {
                uids = uidInput.split(' ').map(u => u.trim()).filter(u => /^\\d+$/.test(u));
            } else {
                uids = [uidInput];
            }
            
            if (uids.length === 0) {
                logToConsole('❌ সঠিক UID দিন!', 'error');
                return;
            }

            if (currentMode === 'smart') {
                for (const uid of uids) {
                    await startSmartSpam(uid);
                }
            } else {
                logToConsole(`🚀 ${uids.length} টি টার্গেটে স্প্যাম শুরু হচ্ছে: ${uids.join(', ')}`, 'info');
                try {
                    const response = await fetch('/api/start', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ uid: uidInput, smart: false })
                    });
                    const data = await response.json();
                    if (data.success) {
                        logToConsole(`✅ ${data.message}`, 'success');
                        document.getElementById('startUid').value = '';
                        refreshStatus();
                    } else {
                        logToConsole(`❌ ${data.message}`, 'error');
                    }
                } catch (error) { logToConsole(`❌ Connection error: ${error.message}`, 'error'); }
            }
        }

        async function stopSpam() {
            const uid = document.getElementById('stopUid').value.trim();
            if (!uid) { logToConsole('❌ বন্ধ করার জন্য UID দিন!', 'error'); return; }

            logToConsole(`🛑 ${uid} এর স্প্যাম বন্ধ করা হচ্ছে...`, 'info');

            try {
                const response = await fetch('/api/stop', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ uid: uid, smart: true })
                });
                const data = await response.json();
                if (data.success) {
                    logToConsole(`✅ ${data.message}`, 'success');
                    document.getElementById('stopUid').value = '';
                    refreshStatus();
                } else {
                    logToConsole(`❌ ${data.message}`, 'error');
                }
            } catch (error) { logToConsole(`❌ Connection error: ${error.message}`, 'error'); }
        }

        async function stopAllSpam() {
            if (!confirm('⚠️ সব স্প্যাম এবং মনিটর বন্ধ করবেন?')) return;

            logToConsole(`🛑 সব স্প্যাম বন্ধ করা হচ্ছে...`, 'info');

            try {
                const response = await fetch('/api/stop-all', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({})
                });
                const data = await response.json();
                if (data.success) {
                    logToConsole(`✅ ${data.message}`, 'success');
                    refreshStatus();
                } else {
                    logToConsole(`❌ ${data.message}`, 'error');
                }
            } catch (error) { logToConsole(`❌ Connection error: ${error.message}`, 'error'); }
        }

        async function refreshStatus() {
            try {
                const response = await fetch('/api/status');
                const data = await response.json();
                if (data.success && data.data) {
                    const status = data.data;
                    
                    const activeList = document.getElementById('activeSpamList');
                    if (status.active_targets && status.active_targets.length > 0) {
                        document.getElementById('statusText').innerHTML = `<i class="fa-solid fa-bolt"></i> স্প্যামিং: ${status.active_targets.length} টি টার্গেট`;
                        activeList.innerHTML = status.active_targets.map(target => `
                            <div class="active-item">
                                <div><span class="active-uid">🎯 ${target.uid}</span>
                                <div style="font-size:10px; color:#888;">♾️ UNLIMITED | ${target.elapsed_minutes} মিনিট</div></div>
                                <button class="stop-small" onclick="stopFromList('${target.uid}')">STOP</button>
                            </div>
                        `).join('');
                    } else {
                        document.getElementById('statusText').innerHTML = `<i class="fa-solid fa-check"></i> নিস্ক্রিয়`;
                        activeList.innerHTML = '<div class="console-line">📭 কোনো সক্রিয় টার্গেট নেই</div>';
                    }
                    
                    const smartList = document.getElementById('smartMonitoredList');
                    if (status.smart_monitored && status.smart_monitored.length > 0) {
                        document.getElementById('smartCount').innerHTML = status.smart_monitored.length;
                        smartList.innerHTML = status.smart_monitored.map(item => `
                            <div class="active-item smart-item">
                                <div><span class="active-uid">🧠 ${item.uid}</span>
                                <div style="font-size:10px; color:#9b59b6; font-weight: bold;">স্ট্যাটাস: ${item.status || 'চেক করা হচ্ছে...'}</div></div>
                                <button class="stop-small" onclick="stopFromList('${item.uid}')">STOP</button>
                            </div>
                        `).join('');
                    } else {
                        document.getElementById('smartCount').innerHTML = '0';
                        smartList.innerHTML = '<div class="console-line">📭 কোনো স্মার্ট মনিটর টার্গেট নেই</div>';
                    }
                    
                    const accountsList = document.getElementById('accountsList');
                    if (status.accounts_list && status.accounts_list.length > 0) {
                        accountsList.innerHTML = status.accounts_list.map(acc => `<div class="account-item"><i class="fa-solid fa-user-check"></i> ${acc}</div>`).join('');
                        if (status.accounts_count > 50) {
                            accountsList.innerHTML += `<div class="account-item">... এবং আরও ${status.accounts_count - 50}টি</div>`;
                        }
                    } else {
                        accountsList.innerHTML = '<div class="console-line">⚠️ কোনো অ্যাকাউন্ট সংযুক্ত নেই</div>';
                    }
                    
                    if (status.auto_active) {
                        logToConsole(`🧠 অটো স্প্যাম সক্রিয়: ${status.auto_uids.length} টি টার্গেট`, 'smart');
                    }
                }
            } catch (error) { console.error('Status error:', error); }
        }

        async function stopFromList(uid) {
            document.getElementById('stopUid').value = uid;
            await stopSpam();
        }

        loadAutoUids();
        loadInviteUids();
        setInterval(refreshStatus, 3000);
        refreshStatus();

        document.getElementById('startUid').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') startSpam();
        });
        document.getElementById('stopUid').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') stopSpam();
        });
    </script>
</body>
</html>
'''

# ==================== MAIN ====================
def main():
    print(f"""
    {C}{BOLD}
    ╔══════════════════════════════════════════════════════════════════════╗
    ║              🎯 MAHIR SPAM ULTIMATE MULTI-TARGET 🎯                  ║
    ║                                                                      ║
    ║     📁 auto_uid.txt  → SMART MONITORED (স্ট্যাটাস দেখে স্প্যাম)      ║
    ║     📁 inv_uid.txt   → ACTIVE TARGETS (সরাসরি স্প্যাম)               ║
    ║                                                                      ║
    ║     ✅ 3/5/6 প্লেয়ার গ্রুপ ইনভাইট                                  ║
    ║     ✅ V-BADGE + PRO_BADGE + CRAFTLAND + MODERATOR জয়িন             ║
    ║     ✅ স্মার্ট মনিটরিং - স্ট্যাটাস দেখে অটো স্প্যাম                  ║
    ║     ✅ প্রতি ৭ মিনিটে অটো রিফ্রেশ                                    ║
    ║                                                                      ║
    ║     🌐 ওয়েব প্যানেল: http://127.0.0.1:5000                         ║
    ║     👑 ডেভেলপার: MAHIR                                             ║
    ╚══════════════════════════════════════════════════════════════════════╝
    {RS}
    """)
    
    # Load files
    load_auto_uids()
    load_invite_uids()
    
    # Start accounts
    Thread(target=run_accounts, daemon=True).start()
    
    # Start auto refresh timer
    start_auto_refresh()
    
    # Start auto spam
    start_auto_spam()
    
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)

if __name__ == "__main__":
    try:
        import aiohttp
    except ImportError:
        os.system("pip install aiohttp")
    
    main()