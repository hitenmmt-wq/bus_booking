# ─────────────────────────────────────────────────────────────────────
# token_server.py
# Terminal 1:  python token_server.py
# Terminal 2:  py agent.py connect --room bus-booking-room

import json
import time
from collections import defaultdict
from datetime import timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from livekit import api

# ── CONFIG ──────────────────────────────────────────────────────────────────
LIVEKIT_API_SECRET="TsqhZbIbeA7dvVJKTeYzL9hk9hjQy1NBAsPtIksBW6j"
LIVEKIT_API_KEY    = "API9gbSvNpQjiLm"
LIVEKIT_URL        = "wss://busbooking-p52t2etx.livekit.cloud"
ROOM_NAME          = "bus-booking-room"
PORT               = 8080

# Adjust paths if your JSON files are in a different folder
BUS_FILE     = Path(__file__).parent / "bus_data_complete.json"
BOOKING_FILE = Path(__file__).parent / "booking_data.json"
# ────────────────────────────────────────────────────────────────────────────


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def generate_token() -> str:
    return (
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
        .with_ttl(timedelta(hours=8))
        .to_jwt()
    )


def seats_to_layout(bus: dict, travel_date: str, bookings: list) -> dict:
    """
    Convert flat seats[] array → deck/row layout for the FE seat chart.

    FE expects:
    {
      "decks": [
        {
          "label": "નીચેનો ડેક",
          "rows": [
            {
              "rowNo": 1,
              "left":  [{"name":"1A","status":"available","type":"window","price":450}],
              "right": [{"name":"1B","status":"booked",   "type":"aisle", "price":450}]
            }
          ]
        }
      ]
    }
    """
    # Seats already confirmed on this date
    booked_on_date = {
        b["seat_no"]
        for b in bookings
        if b["bus_id"] == bus["bus_id"]
           and b["travel_date"] == travel_date
           and b.get("booking_status") == "CONFIRMED"
    }

    price = bus.get("price", 0)

    # deck_key → row_no → side → [seat, ...]
    deck_rows: dict = defaultdict(lambda: defaultdict(lambda: {"left": [], "right": []}))

    for seat in bus.get("seats", []):
        deck_key = seat.get("deck", "single")
        row      = seat.get("row", 0)
        side     = seat.get("side", "left")
        status   = "booked" if seat["seat_no"] in booked_on_date else seat["status"]

        deck_rows[deck_key][row][side].append({
            "name":   seat["seat_no"],
            "status": status,
            "type":   seat["type"],
            "price":  price,
        })

    DECK_ORDER  = ["lower", "single", "upper"]
    DECK_LABELS = {
        "lower":  "નીચેનો ડેક",
        "upper":  "ઉપરનો ડેક",
        "single": "મુખ્ય ડેક",
    }

    decks = []
    for dk in DECK_ORDER:
        if dk not in deck_rows:
            continue
        rows = []
        for row_no in sorted(deck_rows[dk].keys()):
            rows.append({
                "rowNo": row_no,
                "left":  sorted(deck_rows[dk][row_no]["left"],  key=lambda s: s["name"]),
                "right": sorted(deck_rows[dk][row_no]["right"], key=lambda s: s["name"]),
            })
        if rows:
            decks.append({"label": DECK_LABELS.get(dk, dk.title()), "rows": rows})

    return {"decks": decks}


def search_buses(from_city: str, to_city: str, travel_date: str) -> list:
    bus_data     = load_json(BUS_FILE)
    booking_data = load_json(BOOKING_FILE)
    bookings     = booking_data.get("bookings", [])

    results = []
    for bus in bus_data.get("buses", []):
        if (bus["from_city"].lower() == from_city.lower()
                and bus["to_city"].lower() == to_city.lower()):

            booked = sum(
                1 for b in bookings
                if b["bus_id"] == bus["bus_id"]
                   and b["travel_date"] == travel_date
                   and b.get("booking_status") == "CONFIRMED"
            )
            available = bus["total_seats"] - booked
            if available <= 0:
                continue

            results.append({
                "id":               bus["bus_id"],
                "name":             bus["operator"],
                "route":            f"{bus['from_city']} → {bus['to_city']}",
                "departure":        bus["departure_time"],
                "arrival":          bus["arrival_time"],
                "bus_type":         bus["bus_type"],
                "price":            bus["price"],
                "seats_available":  available,
                "total_seats":      bus["total_seats"],
                "amenities":        bus.get("amenities", []),
                "rating":           bus.get("rating", 0),
                "layout":           seats_to_layout(bus, travel_date, bookings),
            })

    return results


class Handler(BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        self.send_response(200); self._cors(); self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        # GET /get-token
        if parsed.path == "/get-token":
            try:
                self._json({"token": generate_token(), "url": LIVEKIT_URL})
                print(f"✅ Token issued")
            except Exception as e:
                self._error(str(e))

        # GET /buses?from=Ahmedabad&to=Surat&date=2026-03-25
        elif parsed.path == "/buses":
            fc = params.get("from", [""])[0]
            tc = params.get("to",   [""])[0]
            dt = params.get("date", [""])[0]
            if not fc or not tc or not dt:
                self._error("from, to, date params required", 400); return
            try:
                buses = search_buses(fc, tc, dt)
                self._json({"buses": buses})
                print(f"🔍 {fc}→{tc} on {dt}: {len(buses)} buses")
            except Exception as e:
                self._error(str(e))

        else:
            self.send_response(404); self.end_headers()

    def _json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status); self._cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers(); self.wfile.write(body)

    def _error(self, msg, status=500):
        self._json({"error": msg}, status); print(f"❌ {msg}")

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def log_message(self, *args): pass


if __name__ == "__main__":
    httpd = HTTPServer(("0.0.0.0", PORT), Handler)
    print("─" * 56)
    print(f"🚀  http://localhost:{PORT}")
    print(f"")
    print(f"📡  GET /get-token")
    print(f"    GET /buses?from=Ahmedabad&to=Surat&date=2026-03-25")
    print(f"")
    print(f"📂  Bus data : {BUS_FILE}")
    print(f"🏠  Room     : {ROOM_NAME}")
    print("─" * 56)
    print(f"    py agent.py connect --room {ROOM_NAME}")
    print("─" * 56)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Stopped.")