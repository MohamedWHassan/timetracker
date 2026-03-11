#!/usr/bin/env python3
"""
Time Tracker Daemon
Runs the HTTP server in the background (no UI).
Started automatically on boot via systemd.
Run 'python3 tracker_tui.py' to view the dashboard.
"""

import json
import logging
import signal
import sqlite3
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import date
from pathlib import Path

DB_PATH = Path.home() / ".timetracker.db"
PORT = 27182

# None means no limit
SITE_LIMITS = {
    "YouTube":   30 * 60,
    "Facebook":  30 * 60,
    "Instagram": 30 * 60,
    "VSCode":    None,
}

TRACKED_SITES = list(SITE_LIMITS.keys())

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(Path.home() / ".timetracker.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


def init_db(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            site TEXT NOT NULL,
            date TEXT NOT NULL,
            seconds INTEGER NOT NULL DEFAULT 0,
            UNIQUE(site, date)
        )
    """)
    conn.commit()


def add_seconds(conn, site: str, seconds: int):
    today = str(date.today())
    conn.execute("""
        INSERT INTO sessions (site, date, seconds) VALUES (?, ?, ?)
        ON CONFLICT(site, date) DO UPDATE SET seconds = seconds + ?
    """, (site, today, seconds, seconds))
    conn.commit()


def get_today_stats(conn) -> dict:
    today = str(date.today())
    rows = conn.execute(
        "SELECT site, seconds FROM sessions WHERE date = ?", (today,)
    ).fetchall()
    return {row[0]: row[1] for row in rows}


conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
init_db(conn)


class Handler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")

    def do_GET(self):
        if self.path != "/status":
            self.send_response(404)
            self.end_headers()
            return
        stats = get_today_stats(conn)
        blocked = [
            site for site, secs in stats.items()
            if SITE_LIMITS.get(site) is not None and secs >= SITE_LIMITS[site]
        ]
        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"blocked": blocked}).encode())

    def do_POST(self):
        if self.path != "/heartbeat":
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            data = json.loads(body)
            site = data.get("site", "")
            seconds = int(data.get("seconds", 0))
            if site in TRACKED_SITES and seconds > 0:
                add_seconds(conn, site, seconds)
                log.info(f"+{seconds}s on {site}")
        except Exception as e:
            log.warning(f"Bad request: {e}")
        self.send_response(200)
        self._cors()
        self.end_headers()
        self.wfile.write(b"ok")

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, *args):
        pass


def main():
    server = HTTPServer(("127.0.0.1", PORT), Handler)

    def shutdown(sig, frame):
        log.info("Shutting down...")
        server.shutdown()
        conn.close()
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    log.info(f"Time Tracker daemon started on port {PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
