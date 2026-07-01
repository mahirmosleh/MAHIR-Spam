# status_api.py
# টার্গেট ইউজারের স্ট্যাটাস চেক করার জন্য API

import asyncio, json, ssl, time, threading
import aiohttp, urllib3
from flask import Flask, request, jsonify
from datetime import datetime
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import base64

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==================== কনফিগারেশন ====================
_ID = '4575104506'  # এখানে আপনার একটি ওয়ার্কিং অ্যাকাউন্টের UID দিন
_PW = 'TORIKUL_TORIKUL_E6H3H'  # সেই অ্যাকাউন্টের পাসওয়ার্ড
_TTL = 6 * 60 * 60  # 6 ঘন্টা
_cx = {}
_lk = threading.Lock()

# ==================== হেডারস ====================
_Hr = {
    'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 9; G011A Build/PI)',
    'Connection': 'Keep-Alive',
    'Accept-Encoding': 'gzip',
    'Content-Type': 'application/x-www-form-urlencoded',
    'Expect': '100-continue',
    'X-Unity-Version': '2018.4.11f1',
    'X-GA': 'v1 1',
    'ReleaseVersion': 'OB53',
}

# ==================== প্রোটোবাফ হেলপার ফাংশন ====================
def _read_varint(data, pos):
    """Read varint from protobuf data"""
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

def _parse_protobuf(data):
    """Parse protobuf data to dictionary"""
    out = {}
    pos = 0
    while pos < len(data):
        try:
            tag, pos = _read_varint(data, pos)
            fn = tag >> 3
            wt = tag & 0x7
            
            if wt == 0:  # varint
                v, pos = _read_varint(data, pos)
                out[fn] = v
            elif wt == 2:  # length-delimited
                ln, pos = _read_varint(data, pos)
                out[fn] = data[pos:pos+ln]
                pos += ln
            elif wt == 1:  # 64-bit
                out[fn] = data[pos:pos+8]
                pos += 8
            elif wt == 5:  # 32-bit
                out[fn] = data[pos:pos+4]
                pos += 4
            else:
                break
        except:
            break
    return out

async def _write_varint(n):
    """Write varint to bytes"""
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

async def _write_field(fn, val):
    """Write protobuf field"""
    return await _write_varint((fn << 3) | 0) + await _write_varint(val)

async def _write_length_delimited(fn, val):
    """Write length-delimited protobuf field"""
    e = val.encode() if isinstance(val, str) else val
    return await _write_varint((fn << 3) | 2) + await _write_varint(len(e)) + e

async def _build_protobuf(fields):
    """Build protobuf from fields dictionary"""
    p = bytearray()
    for f, v in fields.items():
        if isinstance(v, dict):
            p.extend(await _write_length_delimited(f, await _build_protobuf(v)))
        elif isinstance(v, int):
            p.extend(await _write_field(f, v))
        elif isinstance(v, (str, bytes)):
            p.extend(await _write_length_delimited(f, v))
    return p

async def _encrypt(hex_data, key, iv):
    """AES CBC encryption"""
    cipher = AES.new(key, AES.MODE_CBC, iv)
    encrypted = cipher.encrypt(pad(bytes.fromhex(hex_data), 16))
    return encrypted.hex()

async def _to_hex(n):
    """Convert integer to hex string"""
    h = hex(n)[2:]
    return ('0' + h) if len(h) == 1 else h

async def _uid_to_hex(uid):
    """Convert UID to hex for protobuf"""
    return (await _build_protobuf({1: int(uid)})).hex()[2:]

async def _build_status_packet(uid, key, iv):
    """Build status check packet"""
    uid_hex = await _uid_to_hex(int(uid))
    packet_data = f"080112090A05{uid_hex}1005"
    
    # Encrypt
    encrypted = await _encrypt(packet_data, key, iv)
    length_hex = await _to_hex(len(encrypted) // 2)
    
    # Padding for length
    padding = {2: '000000', 3: '00000', 4: '0000', 5: '000'}.get(len(length_hex), '000000')
    
    return bytes.fromhex('0F15' + padding + length_hex + encrypted)

async def _build_room_packet(room_uid, key, iv):
    """Build room info packet"""
    room_data = (await _build_protobuf({
        1: 1,
        2: {1: room_uid, 3: {}, 4: 1, 6: 'en'}
    })).hex()
    
    encrypted = await _encrypt(room_data, key, iv)
    length_hex = await _to_hex(len(encrypted) // 2)
    padding = {2: '000000', 3: '00000', 4: '0000', 5: '000'}.get(len(length_hex), '000000')
    
    return bytes.fromhex('0E15' + padding + length_hex + encrypted)

def _calculate_time_diff(timestamp):
    """Calculate time difference from timestamp"""
    diff = int((datetime.now() - datetime.fromtimestamp(timestamp)).total_seconds())
    return f"{(abs(diff) % 3600) // 60:02}:{abs(diff) % 60:02}"

def _parse_status_response(pkt_json):
    """Parse status response from JSON"""
    try:
        data = json.loads(pkt_json)
        
        if '5' not in data or 'data' not in data['5']:
            return {'status': 'OFFLINE'}
        
        jd = data['5']['data']
        if '1' not in jd or 'data' not in jd['1']:
            return {'status': 'OFFLINE'}
        
        d = jd['1']['data']
        if '3' not in d or 'data' not in d['3']:
            return {'status': 'OFFLINE'}
        
        status_code = d['3']['data']
        group_count = d.get('9', {}).get('data', 0)
        group_members = d.get('10', {}).get('data', 0)
        group_owner = d.get('8', {}).get('data', 0)
        target_group = d.get('4', {}).get('data', 0)
        mode_id_5 = d.get('5', {}).get('data')
        mode_id_6 = d.get('6', {}).get('data')
        
        # Calculate time if in game
        minutes = seconds = 0
        if target_group:
            t = _calculate_time_diff(target_group).split(':')
            minutes = int(t[0])
            seconds = int(t[1])
        
        # Status mapping
        status_map = {
            1: 'SOLO',
            2: 'INSQUAD',
            3: 'INGAME',
            5: 'INGAME',
            7: 'MATCHMAKING',
            6: 'SOCIAL_ISLAND'
        }
        
        base_status = status_map.get(status_code, 'OFFLINE')
        
        # Mode mapping
        mode = None
        if d.get('14', {}).get('data') == 1:
            mode = 'TRAINING'
        elif d.get('14', {}).get('data') == 2:
            mode = 'SOCIAL_ISLAND'
        
        mode_map = {
            (2, 1): 'BR_RANK',
            (5, 23): 'TRAINING',
            (6, 15): 'CS_RANK',
            (1, 43): 'LONE_WOLF',
            (1, 1): 'BERMUDA',
            (1, 15): 'CLASH_SQUAD',
            (1, 29): 'CONVOY_CRUNCH',
            (1, 61): 'FREE_FOR_ALL'
        }
        
        if (mode_id_5, mode_id_6) in mode_map:
            mode = mode_map[(mode_id_5, mode_id_6)]
        
        result = {'status': base_status, 'mode': mode}
        
        if base_status == 'INSQUAD':
            result['squad_owner'] = group_owner
            result['squad_size'] = f"{group_count}/{group_members + 1}" if group_count else None
        
        if base_status in ('INGAME', 'INSQUAD') and target_group:
            result['time_playing'] = f"{minutes}m {seconds}s"
        
        # Room info
        if status_code == 4:
            result['status'] = 'IN_ROOM'
            result['room_uid'] = d.get('15', {}).get('data')
            result['players'] = f"{d.get('17',{}).get('data',0)}/{d.get('18',{}).get('data',0)}"
            result['room_owner'] = d.get('1', {}).get('data')
        
        return result
        
    except Exception as e:
        return {'status': 'PARSE_ERROR', 'error': str(e)}

def _parse_room_response(pkt_json):
    """Parse room info response"""
    try:
        data = json.loads(pkt_json)
        rd = data['5']['data']['1']['data']
        
        mode_map = {
            1: 'BERMUDA',
            201: 'BATTLE_CAGE',
            15: 'CLASH_SQUAD',
            43: 'LONE_WOLF',
            3: 'RUSH_HOUR',
            27: 'BOMB_SQUAD_5V5',
            24: 'DEATH_MATCH'
        }
        
        return {
            'room_id': int(rd['1']['data']),
            'room_name': rd['2']['data'],
            'owner_uid': int(rd['37']['data']['1']['data']),
            'mode': mode_map.get(rd.get('4', {}).get('data'), 'UNKNOWN'),
            'players': f"{rd.get('6',{}).get('data',0)}/{rd.get('7',{}).get('data',0)}",
            'spectators': rd.get('9', {}).get('data', 0),
            'emulator': bool(rd.get('17', {}).get('data', 1)),
        }
    except Exception as e:
        return {'error': str(e)}

async def _read_all(reader, timeout=5):
    """Read all data from reader"""
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

async def _scan_packet(buf, key, iv):
    """Scan packet for status/room data"""
    hex_data = buf.hex()
    
    # Check for status packet (0F)
    i = hex_data.find('0f00')
    if i != -1 and i % 2 == 0:
        return '0f', hex_data[i + 10:]
    
    # Check for room packet (0E)
    i = hex_data.find('0e00')
    if i != -1 and i % 2 == 0:
        return '0e', hex_data[i + 10:]
    
    # Try to decrypt and scan
    if len(buf) > 5:
        payload = buf[5:]
        payload = payload[:len(payload) - (len(payload) % 16)]
        if len(payload) >= 16:
            try:
                cipher = AES.new(key, AES.MODE_CBC, iv)
                decrypted = unpad(cipher.decrypt(payload), 16).hex()
                
                i = decrypted.find('0f00')
                if i != -1 and i % 2 == 0:
                    return '0f', decrypted[i + 10:]
                
                i = decrypted.find('0e00')
                if i != -1 and i % 2 == 0:
                    return '0e', decrypted[i + 10:]
            except:
                pass
    
    return None, None

async def _create_login_packet(open_id, access_token):
    """Create login packet"""
    return await _build_protobuf({
        3: str(datetime.now())[:-7],
        4: 'free fire',
        5: 1,
        7: '1.123.1',
        8: 'Android OS 9 / API-28 (PQ3B.190801.10101846/G9650ZHU2ARC6)',
        9: 'Handheld',
        10: 'Verizon',
        11: 'WIFI',
        12: 1920,
        13: 1080,
        14: '280',
        15: 'ARM64 FP ASIMD AES VMH | 2865 | 4',
        16: 3003,
        17: 'Adreno (TM) 640',
        18: 'OpenGL ES 3.1 v1.46',
        19: 'Google|34a7dcdf-a7d5-4cb6-8d7e-3b0e448a0c57',
        20: '223.191.51.89',
        21: 'en',
        22: open_id,
        23: '4',
        24: 'Handheld',
        25: {6: 55, 8: 81},
        29: access_token,
        30: 1,
        73: 3,
        78: 3,
        79: 2,
        81: '64',
        93: 'android',
        97: 1,
        98: 1,
        99: '4',
        100: '4',
    })

async def _create_auth_packet(uid, token, timestamp, key, iv):
    """Create authentication packet"""
    uid_hex = hex(uid)[2:]
    padding = {
        9: '0000000',
        8: '00000000',
        10: '000000',
        7: '000000000'
    }.get(len(uid_hex), '0000000')
    
    encrypted = await _encrypt(token.encode().hex(), key, iv)
    length_hex = await _to_hex(len(encrypted) // 2)
    
    return f"0115{padding}{uid_hex}{await _to_hex(timestamp)}00000{length_hex}{encrypted}"

async def _login():
    """Login to game and get session"""
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    async with aiohttp.ClientSession() as session:
        # Guest login
        async with session.post(
            'https://100067.connect.garena.com/oauth/guest/token/grant',
            headers=_Hr,
            data={
                'uid': _ID,
                'password': _PW,
                'response_type': 'token',
                'client_type': '2',
                'client_secret': '2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3',
                'client_id': '100067',
            },
            ssl=ssl_context
        ) as r:
            if r.status != 200:
                raise Exception(f"OAuth failed: {r.status}")
            data = await r.json()
            open_id = data['open_id']
            access_token = data['access_token']
        
        # Create login packet
        login_data = await _create_login_packet(open_id, access_token)
        
        # Encrypt with master key
        master_key = b'Yg&tc%DEuh6%Zc^8'
        master_iv = b'6oyZDr22E3ychjM%'
        cipher = AES.new(master_key, AES.MODE_CBC, master_iv)
        encrypted_login = cipher.encrypt(pad(login_data, 16))
        
        # Major login
        async with session.post(
            'https://loginbp.ggpolarbear.com/MajorLogin',
            data=encrypted_login,
            headers=_Hr,
            ssl=ssl_context
        ) as r:
            if r.status != 200:
                raise Exception(f"MajorLogin failed: {r.status}")
            major_response = await r.read()
        
        # Parse response
        parsed = _parse_protobuf(major_response)
        token = parsed[8].decode()
        target_uid = parsed[1]
        key = parsed[22]
        iv = parsed[23]
        timestamp = parsed[21]
        url = parsed[10].decode()
        
        # Get login data
        headers = {**_Hr, 'Authorization': f'Bearer {token}'}
        async with session.post(
            f"{url}/GetLoginData",
            data=encrypted_login,
            headers=headers,
            ssl=ssl_context
        ) as r:
            if r.status != 200:
                raise Exception(f"GetLoginData failed: {r.status}")
            login_response = await r.read()
        
        login_parsed = _parse_protobuf(login_response)
        ip_port = login_parsed[14].decode().split(':')
        ip = ip_port[0]
        port = int(ip_port[1])
        
        # Create auth packet
        auth_packet = await _create_auth_packet(target_uid, token, timestamp, key, iv)
        
        print(f"\n✅ Status Checker Connected!")
        print(f"   Account ID: {target_uid}")
        print(f"   Token: {token[:50]}...")
        print(f"   Server: {ip}:{port}\n")
        
        return {
            'account_id': target_uid,
            'token': token,
            'key': key,
            'iv': iv,
            'ip': ip,
            'port': port,
            'auth': auth_packet,
            'exp': time.time() + _TTL
        }

def get_session():
    """Get or refresh session"""
    with _lk:
        session = _cx.get('session')
        if session and time.time() < session['exp']:
            return session
    
    new_session = asyncio.run(_login())
    with _lk:
        _cx['session'] = new_session
    return new_session

async def _query_status(uid, session):
    """Query status of a UID"""
    try:
        # Connect to server
        reader, writer = await asyncio.open_connection(
            session['ip'], 
            session['port']
        )
        
        try:
            # Send auth packet
            writer.write(bytes.fromhex(session['auth']))
            await writer.drain()
            
            # Read initial response
            await _read_all(reader, timeout=3)
            
            # Send status packet
            status_packet = await _build_status_packet(uid, session['key'], session['iv'])
            writer.write(status_packet)
            await writer.drain()
            
            # Read response
            buf = await _read_all(reader, timeout=5)
            
            if not buf:
                return {'status': 'NO_RESPONSE'}
            
            # Scan packet
            pkt_type, payload = await _scan_packet(buf, session['key'], session['iv'])
            
            if pkt_type == '0f':
                # Parse status
                from google.protobuf.json_format import Parse
                parsed = _parse_protobuf(bytes.fromhex(payload))
                # Convert to JSON for parsing
                import json
                pkt_json = json.dumps({k: {'data': v.decode() if isinstance(v, bytes) else v} 
                                      for k, v in parsed.items()}, default=str)
                info = _parse_status_response(pkt_json)
                
                # If in room, get room info
                if info.get('status') == 'IN_ROOM' and info.get('room_uid'):
                    writer.write(await _build_room_packet(int(info['room_uid']), session['key'], session['iv']))
                    await writer.drain()
                    
                    room_buf = await _read_all(reader, timeout=5)
                    if room_buf:
                        rt, rp = await _scan_packet(room_buf, session['key'], session['iv'])
                        if rt == '0e':
                            room_json = json.dumps({k: {'data': v.decode() if isinstance(v, bytes) else v} 
                                                   for k, v in _parse_protobuf(bytes.fromhex(rp)).items()}, default=str)
                            info['room_info'] = _parse_room_response(room_json)
                
                return info
                
            elif pkt_type == '0e':
                room_json = json.dumps({k: {'data': v.decode() if isinstance(v, bytes) else v} 
                                       for k, v in _parse_protobuf(bytes.fromhex(payload)).items()}, default=str)
                return _parse_room_response(room_json)
            
            return {'status': 'UNKNOWN', 'buffer': buf.hex()[:120]}
            
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except:
                pass
                
    except Exception as e:
        return {'status': 'ERROR', 'error': str(e)}

# ==================== ফ্লাস্ক API ====================
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/status')
def status_endpoint():
    """Get status of a UID"""
    uid = request.args.get('uid', '').strip()
    if not uid or not uid.isdigit():
        return jsonify({'error': 'Valid UID is required'}), 400
    
    try:
        session = get_session()
        result = asyncio.run(_query_status(uid, session))
        return jsonify({'uid': uid, **result})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({'status': 'ok', 'timestamp': datetime.now().isoformat()})

def run_status_api(port=5000):
    """Run the status API server"""
    app.run(host='0.0.0.0', port=port, debug=False)

if __name__ == '__main__':
    run_status_api()