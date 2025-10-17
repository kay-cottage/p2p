# server_ws.py
import os, secrets, json, asyncio
from aiohttp import web, WSMsgType

HARD_TOKEN = "CHANGE_ME_123"   # <<< 修改为你想要的 token
HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", "8000"))

hosts = {}            # tunnel -> host_ws
sessions = {}         # session -> peer_ws
peer_to_session = {}  # peer_ws -> session
host_to_sessions = {} # host_ws -> set(session)

def pack_session(session_id: str, payload: bytes) -> bytes:
    sid = session_id.encode()
    return len(sid).to_bytes(2, "big") + sid + payload

def unpack_session(data: bytes):
    if len(data) < 2: return None, b""
    n = int.from_bytes(data[:2], "big")
    if 2 + n > len(data): return None, b""
    sid = data[2:2+n].decode()
    return sid, data[2+n:]

async def safe_close(ws):
    try:
        await ws.close()
    except:
        pass

async def ws_handler(request):
    ws = web.WebSocketResponse(max_msg_size=0)
    await ws.prepare(request)

    # Expect initial join text
    msg = await ws.receive()
    if msg.type != WSMsgType.TEXT:
        await ws.close(); return ws
    try:
        hello = json.loads(msg.data)
    except:
        await ws.close(); return ws

    if hello.get("op") != "join": await ws.close(); return ws
    token = hello.get("token"); role = hello.get("role"); tunnel = hello.get("tunnel")
    if token != HARD_TOKEN or role not in ("host","peer") or not tunnel:
        await ws.send_str(json.dumps({"op":"err","reason":"auth_or_params"}))
        await ws.close(); return ws

    # HOST logic
    if role == "host":
        old = hosts.get(tunnel)
        if old is not None and not old.closed:
            await safe_close(old)
        hosts[tunnel] = ws
        host_to_sessions[ws] = set()
        await ws.send_str(json.dumps({"op":"ok","role":"host","tunnel":tunnel}))
        try:
            async for m in ws:
                if m.type == WSMsgType.TEXT:
                    # support signal forwarding from host to peer: {"op":"signal","session":sid,"data":...}
                    try:
                        d = json.loads(m.data)
                        if d.get("op") == "signal" and "session" in d:
                            sid = d["session"]
                            peer = sessions.get(sid)
                            if peer and not peer.closed:
                                await peer.send_str(json.dumps({"op":"signal","session":sid,"data": d.get("data")}))
                    except:
                        pass
                elif m.type == WSMsgType.BINARY:
                    # host -> peer (must include session prefix)
                    sid, payload = unpack_session(m.data)
                    if not sid: continue
                    peer = sessions.get(sid)
                    if peer and not peer.closed:
                        await peer.send_bytes(payload)
                    else:
                        await ws.send_str(json.dumps({"op":"peer_gone","session":sid}))
                elif m.type in (WSMsgType.CLOSE, WSMsgType.ERROR):
                    break
        finally:
            for sid in list(host_to_sessions.get(ws, set())):
                p = sessions.pop(sid, None)
                if p and not p.closed:
                    try:
                        await p.send_str(json.dumps({"op":"host_closed","session":sid}))
                        await p.close()
                    except: pass
                peer_to_session.pop(p, None)
            host_to_sessions.pop(ws, None)
            if hosts.get(tunnel) is ws:
                hosts.pop(tunnel, None)
        return ws

    # PEER logic
    host_ws = hosts.get(tunnel)
    if host_ws is None or host_ws.closed:
        await ws.send_str(json.dumps({"op":"err","reason":"no_host"})); await ws.close(); return ws
    session_id = secrets.token_hex(6)
    sessions[session_id] = ws
    peer_to_session[ws] = session_id
    host_to_sessions.setdefault(host_ws, set()).add(session_id)
    await ws.send_str(json.dumps({"op":"ok","role":"peer","tunnel":tunnel,"session":session_id}))
    try:
        await host_ws.send_str(json.dumps({"op":"pair","tunnel":tunnel,"session":session_id}))
    except:
        sessions.pop(session_id, None); peer_to_session.pop(ws, None)
        await ws.send_str(json.dumps({"op":"err","reason":"host_unreachable"})); await ws.close(); return ws

    try:
        async for m in ws:
            if m.type == WSMsgType.TEXT:
                # forward signaling (webrtc) to host: {"op":"signal","session":sid,"data":...}
                try:
                    d = json.loads(m.data)
                    if d.get("op") == "signal" and "session" in d:
                        sid = d["session"]
                        if hosts.get(tunnel) and not hosts[tunnel].closed:
                            await hosts[tunnel].send_str(json.dumps({"op":"signal","session":sid,"data": d.get("data")}))
                except:
                    pass
            elif m.type == WSMsgType.BINARY:
                # peer -> host (relay): pack with session prefix when sending to host
                if host_ws.closed:
                    await ws.send_str(json.dumps({"op":"err","reason":"host_closed"})); await ws.close(); break
                packed = pack_session(session_id, m.data)
                await host_ws.send_bytes(packed)
            elif m.type in (WSMsgType.CLOSE, WSMsgType.ERROR):
                break
    finally:
        sessions.pop(session_id, None)
        peer_to_session.pop(ws, None)
        if host_ws and not host_ws.closed:
            try:
                await host_ws.send_str(json.dumps({"op":"peer_closed","session":session_id}))
            except: pass
            try:
                host_to_sessions[host_ws].discard(session_id)
            except: pass
        await safe_close(ws)
    return ws

async def index(_):
    return web.Response(text="WS relay alive\n")

def create_app():
    app = web.Application()
    app.router.add_get("/", index)
    app.router.add_get("/ws", ws_handler)
    return app

if __name__ == "__main__":
    web.run_app(create_app(), host=HOST, port=PORT)
