# token_server.py
# Run this on your machine: python token_server.py
# It serves fresh tokens at: http://localhost:8080/get-token

import json
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from livekit import api  # pip install livekit

# ── CONFIG — paste your LiveKit credentials here ──────────────────────
LIVEKIT_URL="wss://busbooking-p52t2etx.livekit.cloud"
LIVEKIT_API_KEY="API9gbSvNpQjiLm"
LIVEKIT_API_SECRET="TsqhZbIbeA7dvVJKTeYzL9hk9hjQy1NBAsPtIksBW6j"
ROOM_NAME          = "bus-booking-room"
PORT               = 8080
# ─────────────────────────────────────────────────────────────────────

def generate_token():
    token = (
        api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
        .with_grants(api.VideoGrants(
            room_join=True,
            room=ROOM_NAME,
            can_publish=True,
            can_subscribe=True,
            can_publish_data=True,
        ))
        .with_identity(f"user-{int(time.time())}")
        .with_name("User")
        .with_ttl(8 * 3600)  # 8 hours
        .to_jwt()
    )
    return token


class TokenHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path == "/get-token":
            try:
                token = generate_token()
                body = json.dumps({"token": token, "url": LIVEKIT_URL}).encode()
                self.send_response(200)
                self._cors()
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                print(f"✅ Token issued to {self.client_address[0]}")
            except Exception as e:
                self.send_response(500)
                self._cors()
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def _cors(self):
        # Allow requests from your Vercel site
        self.send_header("Access-Control-Allow-Origin", "https://busbookingsahayak.vercel.app")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def log_message(self, format, *args):
        pass  # suppress default logs


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), TokenHandler)
    print(f"🚀 Token server running at http://localhost:{PORT}/get-token")
    print(f"🔑 API Key: {LIVEKIT_API_KEY}")
    print(f"🏠 Room: {ROOM_NAME}")
    print("─" * 50)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Token server stopped.")