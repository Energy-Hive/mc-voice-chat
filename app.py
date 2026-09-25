import os
import json
import struct
import hashlib
from aiohttp import web, WSMsgType

PORT = int(os.environ.get("PORT", 10000))

# room_id -> {"name": str, "password": hash, "owner": str, "members": set(names)}
rooms = {}
# player_name -> room_id
player_room = {}
# player_name -> aiohttp WebSocketResponse
players = {}
# player_name -> {"muted": bool, "deafened": bool}
player_info = {}

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>MC Voice Chat</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0a0a1a;color:#e0e0e0;min-height:100vh}
.c{max-width:420px;margin:0 auto;padding:12px}
h1{text-align:center;font-size:22px;padding:16px 0 4px;color:#e94560}
.sub{text-align:center;color:#666;font-size:12px;margin-bottom:16px}
.card{background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:14px;padding:16px;margin-bottom:12px}
.card h2{font-size:14px;color:#e94560;margin-bottom:12px}
.row{display:flex;gap:8px;margin-bottom:8px}
input[type=text],input[type=password]{flex:1;padding:12px;background:rgba(255,255,255,0.07);border:1px solid rgba(255,255,255,0.12);border-radius:10px;color:#fff;font-size:15px;outline:none}
input:focus{border-color:#e94560}
input::placeholder{color:#555}
.btn{padding:12px;border:none;border-radius:10px;font-size:14px;font-weight:600;cursor:pointer;flex:1;text-align:center}
.btn:active{transform:scale(0.96)}
.btn-go{background:linear-gradient(135deg,#e94560,#c23152);color:#fff}
.btn-blue{background:linear-gradient(135deg,#2979ff,#1565c0);color:#fff}
.btn-off{background:rgba(255,255,255,0.08);color:#aaa;border:1px solid rgba(255,255,255,0.1)}
.btn-mic{background:#00c853;color:#fff;font-size:18px;padding:16px}
.btn-mic.muted{background:#ff1744}
.btn-deaf{background:rgba(255,255,255,0.08);color:#aaa;border:1px solid rgba(255,255,255,0.1)}
.btn-deaf.active{background:#ff6d00;color:#fff}
.btn-sm{padding:8px;font-size:12px;border-radius:8px}
.dot{width:10px;height:10px;border-radius:50%;background:#ff1744;display:inline-block}
.dot.on{background:#00e676;box-shadow:0 0 8px #00e67680}
.dot.speak{animation:p .4s infinite}
@keyframes p{50%{transform:scale(1.4)}}
.viz{height:32px;display:flex;align-items:center;justify-content:center;gap:2px;margin:8px 0}
.vb{width:3px;background:#e94560;border-radius:2px;min-height:3px}
.sr{display:flex;align-items:center;gap:8px;margin:8px 0}
.sr label{font-size:12px;color:#888;min-width:60px}
.sr span{font-size:12px;color:#e94560;min-width:35px;text-align:right}
input[type=range]{flex:1;-webkit-appearance:none;height:4px;background:rgba(255,255,255,0.1);border-radius:2px}
input[type=range]::-webkit-slider-thumb{-webkit-appearance:none;width:18px;height:18px;border-radius:50%;background:#e94560}
.pi{display:flex;align-items:center;gap:8px;padding:8px;background:rgba(255,255,255,0.03);border-radius:8px;margin-bottom:4px}
.pi .pn{flex:1;font-size:14px}
.pd{width:8px;height:8px;border-radius:50%;background:#555}
.pd.on{background:#00e676}.pd.speak{background:#00e676;animation:p .4s infinite}
.hidden{display:none!important}
.log{max-height:80px;overflow-y:auto;font-size:11px;color:#555;font-family:monospace;padding:8px;background:rgba(0,0,0,0.3);border-radius:8px}
.ctrl{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin:8px 0}
.room-badge{background:rgba(233,69,96,0.15);border:1px solid #e94560;border-radius:8px;padding:8px 12px;margin-bottom:8px;font-size:13px;color:#ff8a80}
.room-badge span{color:#fff;font-weight:600}
.pw-display{background:rgba(0,200,83,0.1);border:1px solid #00c853;border-radius:8px;padding:10px;margin:8px 0;text-align:center;font-size:18px;font-weight:700;color:#00e676;letter-spacing:3px;cursor:pointer}
.pw-display small{display:block;font-size:11px;color:#888;font-weight:400;letter-spacing:0;margin-top:4px}
</style>
</head>
<body>
<div class="c">
<h1>🎤 MC Voice Chat</h1>
<p class="sub">Password-Protected Voice Rooms</p>

<!-- STEP 1 -->
<div class="card" id="cC">
<h2>🔌 Step 1: Connect</h2>
<p style="margin-bottom:8px"><span class="dot" id="sD"></span> <span id="sT">Disconnected</span></p>
<div class="row"><input type="text" id="iN" placeholder="Minecraft username" maxlength="16"></div>
<button class="btn btn-go" id="bC" onclick="go()">Connect & Enable Mic</button>
</div>

<!-- STEP 2 -->
<div class="card hidden" id="cR">
<h2>🏠 Step 2: Choose Room</h2>
<p style="color:#888;font-size:12px;margin-bottom:12px">Only players with your room name and password can hear you.</p>

<h3 style="font-size:13px;color:#aaa;margin-bottom:8px">Create Room</h3>
<div class="row"><input type="text" id="iRN" placeholder="Room name (e.g. Squad1)" maxlength="24"></div>
<div class="row"><input type="password" id="iRP" placeholder="Set a password"></div>
<button class="btn btn-go" onclick="createRoom()" style="margin-bottom:16px">🔒 Create Room</button>

<h3 style="font-size:13px;color:#aaa;margin-bottom:8px">Join Room</h3>
<div class="row"><input type="text" id="iJN" placeholder="Room name"></div>
<div class="row"><input type="password" id="iJP" placeholder="Enter room password"></div>
<button class="btn btn-blue" onclick="joinRoom()">🔑 Join Room</button>
</div>

<!-- IN ROOM -->
<div class="card hidden" id="cV">
<h2>🎙️ Active Voice Room</h2>
<div class="room-badge">🔒 Room: <span id="roomName">-</span></div>
<div class="pw-display" id="pwShow" onclick="copyPw()">
<span id="pwText">----</span>
<small>Tap to copy password</small>
</div>
<div class="viz" id="viz"></div>
<div class="ctrl">
<button class="btn btn-mic" id="bM" onclick="tM()">🎤</button>
<button class="btn btn-deaf" id="bD" onclick="tD()">🔊</button>
<button class="btn btn-off btn-sm" onclick="leaveRoom()">Leave</button>
</div>
<div class="sr"><label>Volume</label><input type="range" min="0" max="100" value="100" oninput="mV=this.value/100;document.getElementById('lV').textContent=this.value+'%'"><span id="lV">100%</span></div>
<div class="sr"><label>Mic Gain</label><input type="range" min="0" max="200" value="100" oninput="mG=this.value/100;document.getElementById('lG').textContent=this.value+'%'"><span id="lG">100%</span></div>
</div>

<!-- PLAYERS -->
<div class="card hidden" id="cP">
<h2>👥 Players in Room</h2>
<ul id="pL" style="list-style:none"><li class="pi" style="justify-content:center;color:#555">Alone in room</li></ul>
</div>

<!-- LOG -->
<div class="card"><h2>📋 Log</h2><div class="log" id="log"></div></div>
</div>

<script>
let ws, ctx, mic, an, pr, nm='', mu=false, de=false, mV=1, mG=1, myRoom='', myPw='', ll=[];
let pS = {};

async function go(){
  nm = document.getElementById('iN').value.trim();
  if(!nm){ lg('Enter your Minecraft username!','e'); return; }
  lg('Connecting to server...','i');

  try {
    mic = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true }
    });
    ctx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 24000 });
    if(ctx.state === 'suspended') await ctx.resume();

    an = ctx.createAnalyser(); an.fftSize = 32;
    const s = ctx.createMediaStreamSource(mic);
    s.connect(an);

    pr = ctx.createScriptProcessor(2048, 1, 1);
    s.connect(pr);
    pr.connect(ctx.destination);
    pr.onaudioprocess = e => {
      if(mu || !ws || ws.readyState !== 1 || !myRoom) return;
      const d = e.inputBuffer.getChannelData(0), p = new Int16Array(d.length);
      for(let i=0; i<d.length; i++){
        const v = Math.max(-1, Math.min(1, d[i] * mG));
        p[i] = v < 0 ? v * 0x8000 : v * 0x7FFF;
      }
      let r = 0;
      for(let i=0; i<d.length; i++) r += d[i] * d[i];
      if(Math.sqrt(r / d.length) < 0.01) return;
      ws.send(p.buffer);
    };

    startViz();

    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = proto + '//' + location.host + '/ws';
    ws = new WebSocket(wsUrl);
    ws.binaryType = 'arraybuffer';

    ws.onopen = () => {
      ws.send(JSON.stringify({ t: 'join', name: nm }));
      document.getElementById('sD').classList.add('on');
      document.getElementById('sT').textContent = 'Connected as ' + nm;
      document.getElementById('bC').textContent = 'Connected ✓';
      document.getElementById('cC').classList.add('hidden');
      document.getElementById('cR').classList.remove('hidden');
      lg('Connected! Create or join a room below.','o');
    };

    ws.onmessage = e => {
      if(e.data instanceof ArrayBuffer) playAudio(e.data);
      else handleMsg(JSON.parse(e.data));
    };

    ws.onclose = () => { lg('Disconnected from server','e'); fullCleanup(); };
    ws.onerror = () => lg('Connection error','e');
  } catch(e) {
    lg('Microphone error: ' + e.message,'e');
  }
}

function fullCleanup(){
  if(ws) ws.close();
  if(mic){ mic.getTracks().forEach(t => t.stop()); mic = null; }
  if(ctx){ ctx.close().catch(()=>{}); ctx = null; }
  ws = null; mu = de = false; myRoom = ''; myPw = '';
  document.getElementById('sD').classList.remove('on');
  document.getElementById('sT').textContent = 'Disconnected';
  document.getElementById('bC').textContent = 'Connect & Enable Mic';
  document.getElementById('cC').classList.remove('hidden');
  ['cR','cV','cP'].forEach(id => document.getElementById(id).classList.add('hidden'));
}

function createRoom(){
  const name = document.getElementById('iRN').value.trim();
  const pw = document.getElementById('iRP').value;
  if(!name){ lg('Enter a room name!','e'); return; }
  if(!pw){ lg('Enter a room password!','e'); return; }
  if(ws) ws.send(JSON.stringify({ t: 'create_room', name: name, password: pw }));
}

function joinRoom(){
  const name = document.getElementById('iJN').value.trim();
  const pw = document.getElementById('iJP').value;
  if(!name || !pw){ lg('Enter room name and password!','e'); return; }
  if(ws) ws.send(JSON.stringify({ t: 'join_room', name: name, password: pw }));
}

function leaveRoom(){
  if(ws) ws.send(JSON.stringify({ t: 'leave_room' }));
  myRoom = ''; myPw = '';
  document.getElementById('cV').classList.add('hidden');
  document.getElementById('cP').classList.add('hidden');
  document.getElementById('cR').classList.remove('hidden');
  lg('Left room','i');
}

function playAudio(b){
  if(de || !ctx || b.byteLength < 8) return;
  const v = new DataView(b), nl = v.getUint8(0), vol = v.getFloat32(1, true);
  if(nl < 1 || nl > 20) return;
  let n = '';
  for(let i=0; i<nl; i++) n += String.fromCharCode(v.getUint8(5 + i));
  const ps = 5 + nl;
  if(ps >= b.byteLength) return;
  const p = new Int16Array(b.slice(ps)), f = new Float32Array(p.length);
  const ev = vol * mV;
  for(let i=0; i<p.length; i++) f[i] = (p[i] / (p[i] < 0 ? 0x8000 : 0x7FFF)) * ev;
  const a = ctx.createBuffer(1, f.length, ctx.sampleRate);
  a.getChannelData(0).set(f);
  const s = ctx.createBufferSource();
  s.buffer = a; s.connect(ctx.destination); s.start();
  pS[n] = Date.now();
}

function handleMsg(m){
  switch(m.t){
    case 'welcome': lg(m.msg,'i'); break;
    case 'room_created':
      myRoom = m.name; myPw = m.password;
      document.getElementById('cR').classList.add('hidden');
      document.getElementById('cV').classList.remove('hidden');
      document.getElementById('cP').classList.remove('hidden');
      document.getElementById('roomName').textContent = m.name;
      document.getElementById('pwText').textContent = m.password;
      lg('Room "' + m.name + '" created! Share your password.','o');
      break;
    case 'room_joined':
      myRoom = m.name; myPw = m.password || '';
      document.getElementById('cR').classList.add('hidden');
      document.getElementById('cV').classList.remove('hidden');
      document.getElementById('cP').classList.remove('hidden');
      document.getElementById('roomName').textContent = m.name;
      document.getElementById('pwText').textContent = m.password || '(hidden)';
      lg('Joined room "' + m.name + '"!','o');
      break;
    case 'room_left':
      myRoom = ''; myPw = '';
      document.getElementById('cV').classList.add('hidden');
      document.getElementById('cP').classList.add('hidden');
      document.getElementById('cR').classList.remove('hidden');
      break;
    case 'room_players':
      ll = m.players || []; updatePlayers(); break;
    case 'error': lg(m.msg,'e'); break;
    case 'info': lg(m.msg,'i'); break;
  }
}

function tM(){
  mu = !mu;
  const b = document.getElementById('bM');
  b.textContent = mu ? '🔇' : '🎤';
  b.classList.toggle('muted', mu);
  if(ws) ws.send(JSON.stringify({ t: 'mute', muted: mu }));
}

function tD(){
  de = !de;
  const b = document.getElementById('bD');
  b.textContent = de ? '🔇' : '🔊';
  b.classList.toggle('active', de);
  if(de && !mu) tM();
  if(ws) ws.send(JSON.stringify({ t: 'deaf', deafened: de }));
}

function copyPw(){
  if(!myPw) return;
  navigator.clipboard.writeText(myPw).then(() => lg('Password copied!','o')).catch(() => {
    const ta = document.createElement('textarea');
    ta.value = myPw; document.body.appendChild(ta);
    ta.select(); document.execCommand('copy');
    document.body.removeChild(ta);
    lg('Password copied!','o');
  });
}

function updatePlayers(){
  const u = document.getElementById('pL'), now = Date.now(), o = ll.filter(n => n !== nm);
  u.innerHTML = o.length ? o.map(n => {
    const s = (now - (pS[n] || 0)) < 500;
    return `<li class="pi"><div class="pd ${s?'speak':'on'}"></div><span class="pn">${n}</span></li>`;
  }).join('') : '<li class="pi" style="justify-content:center;color:#555">Alone in room</li>';
}

function startViz(){
  const v = document.getElementById('viz'); v.innerHTML = '';
  for(let i=0; i<20; i++){
    const b = document.createElement('div');
    b.className = 'vb'; b.style.height = '3px';
    v.appendChild(b);
  }
  (function draw(){
    if(!an) return;
    const a = new Uint8Array(an.frequencyBinCount);
    an.getByteFrequencyData(a);
    for(let i=0; i<v.children.length; i++){
      const val = a[i] || 0;
      v.children[i].style.height = Math.max(3, (val / 255) * 32) + 'px';
      v.children[i].style.background = mu ? '#333' : val > 180 ? '#ff1744' : val > 80 ? '#00e676' : '#e94560';
    }
    requestAnimationFrame(draw);
  })();
}

function lg(m, t){
  const b = document.getElementById('log'), d = document.createElement('div');
  d.style.color = t === 'e' ? '#ff5252' : t === 'o' ? '#00e676' : '#448aff';
  d.textContent = '[' + new Date().toLocaleTimeString() + '] ' + m;
  b.appendChild(d); b.scrollTop = b.scrollHeight;
  while(b.children.length > 30) b.removeChild(b.firstChild);
}

setInterval(() => { if(ws && ws.readyState === 1) ws.send(JSON.stringify({ t: 'ping' })); }, 3000);
setInterval(updatePlayers, 1000);
lg('Ready! Enter your Minecraft name to start.','i');
</script>
</body>
</html>"""

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

async def send_room_players(room_id):
    if room_id not in rooms: return
    members = list(rooms[room_id]["members"])
    for name in members:
        ws = players.get(name)
        if ws and not ws.closed:
            try:
                await ws.send_str(json.dumps({"t": "room_players", "players": members}))
            except: pass

async def route_audio(sender, audio):
    room = player_room.get(sender)
    if not room or room not in rooms: return
    if player_info.get(sender, {}).get("muted"): return

    nb = sender.encode("utf-8")[:20]
    pkt = struct.pack("<Bf", len(nb), 1.0) + nb + audio

    for member in rooms[room]["members"]:
        if member == sender: continue
        if player_info.get(member, {}).get("deafened"): continue
        ws = players.get(member)
        if not ws or ws.closed: continue
        try:
            await ws.send_bytes(pkt)
        except: pass

async def handle_http(request):
    return web.Response(text=HTML, content_type="text/html")

async def handle_ws(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    pn = None

    try:
        async for msg in ws:
            if msg.type == WSMsgType.BINARY:
                if pn:
                    await route_audio(pn, msg.data)
            elif msg.type == WSMsgType.TEXT:
                m = json.loads(msg.data)
                c = m.get("t", "")

                if c == "join":
                    n = m.get("name", "").strip()[:16]
                    if not n: continue
                    if n in players and not players[n].closed:
                        try: await players[n].close()
                        except: pass
                    pn = n
                    players[n] = ws
                    player_info[n] = {"muted": False, "deafened": False}
                    print(f"[+] {n} connected ({len(players)} online)")
                    await ws.send_str(json.dumps({"t": "welcome", "msg": f"Welcome {n}!"}))

                elif c == "create_room" and pn:
                    rname = m.get("name", "").strip()[:24]
                    rpw = m.get("password", "").strip()
                    if not rname or not rpw:
                        await ws.send_str(json.dumps({"t": "error", "msg": "Room name and password required"}))
                        continue

                    old = player_room.get(pn)
                    if old and old in rooms:
                        rooms[old]["members"].discard(pn)
                        if not rooms[old]["members"]: del rooms[old]
                        else: await send_room_players(old)

                    rid = rname.lower()
                    if rid in rooms:
                        await ws.send_str(json.dumps({"t": "error", "msg": "Room already exists. Pick another name."}))
                        continue

                    rooms[rid] = {
                        "name": rname,
                        "password": hash_pw(rpw),
                        "owner": pn,
                        "members": {pn}
                    }
                    player_room[pn] = rid
                    print(f"[ROOM] {pn} created '{rname}'")
                    await ws.send_str(json.dumps({"t": "room_created", "name": rname, "password": rpw}))
                    await send_room_players(rid)

                elif c == "join_room" and pn:
                    rname = m.get("name", "").strip()
                    rpw = m.get("password", "").strip()
                    rid = rname.lower()

                    if rid not in rooms:
                        await ws.send_str(json.dumps({"t": "error", "msg": "Room not found"}))
                        continue
                    if rooms[rid]["password"] != hash_pw(rpw):
                        await ws.send_str(json.dumps({"t": "error", "msg": "Wrong password"}))
                        continue

                    old = player_room.get(pn)
                    if old and old in rooms:
                        rooms[old]["members"].discard(pn)
                        if not rooms[old]["members"]: del rooms[old]
                        else: await send_room_players(old)

                    rooms[rid]["members"].add(pn)
                    player_room[pn] = rid
                    print(f"[ROOM] {pn} joined '{rooms[rid]['name']}'")
                    await ws.send_str(json.dumps({"t": "room_joined", "name": rooms[rid]["name"], "password": rpw}))
                    await send_room_players(rid)

                elif c == "leave_room" and pn:
                    old = player_room.pop(pn, None)
                    if old and old in rooms:
                        rooms[old]["members"].discard(pn)
                        if not rooms[old]["members"]: del rooms[old]
                        else: await send_room_players(old)
                    await ws.send_str(json.dumps({"t": "room_left"}))

                elif c == "mute" and pn:
                    player_info[pn]["muted"] = m.get("muted", False)
                elif c == "deaf" and pn:
                    player_info[pn]["deafened"] = m.get("deafened", False)

    except Exception as e:
        print(f"[!] WS Error: {e}")
    finally:
        if pn:
            players.pop(pn, None)
            player_info.pop(pn, None)
            old = player_room.pop(pn, None)
            if old and old in rooms:
                rooms[old]["members"].discard(pn)
                if not rooms[old]["members"]: del rooms[old]
                else: await send_room_players(old)
            print(f"[-] {pn} disconnected ({len(players)} online)")

    return ws

app = web.Application()
app.router.add_get('/', handle_http)
app.router.add_get('/ws', handle_ws)

if __name__ == '__main__':
    print(f"🎤 MC Voice Chat starting on port {PORT}...")
    web.run_app(app, host='0.0.0.0', port=PORT)
