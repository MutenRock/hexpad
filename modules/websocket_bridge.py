"""
WebSocket bridge — envoie chaque message MIDI en JSON vers un serveur WS.
Compatible avec n'importe quel jeu web JS via ws.onmessage.
Requiert : pip install websockets
"""
import asyncio, json, threading

try:
    import websockets
    WS_OK = True
except ImportError:
    WS_OK = False
    print("[WS] websockets manquant — pip install websockets")

class WebSocketBridge:
    def __init__(self, url):
        self.url = url
        self.loop = self.queue = None
        if WS_OK:
            self.loop  = asyncio.new_event_loop()
            self.queue = asyncio.Queue()
            threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._connect())

    async def _connect(self):
        print(f"[WS] Connexion \u00e0 {self.url} \u2026")
        try:
            async with websockets.connect(self.url) as ws:
                print("[WS] Connect\u00e9 !")
                while True:
                    payload = await self.queue.get()
                    await ws.send(json.dumps(payload))
        except Exception as e:
            print(f"[WS] Erreur : {e}")

    def handle(self, msg):
        if not WS_OK or not self.loop:
            return
        event = {
            "type":    msg.type,
            "note":    getattr(msg, "note",     None),
            "control": getattr(msg, "control",  None),
            "value":   getattr(msg, "value",    getattr(msg, "velocity", 0)),
            "channel": msg.channel,
        }
        asyncio.run_coroutine_threadsafe(self.queue.put(event), self.loop)
        print(f"[WS] -> {event}")
