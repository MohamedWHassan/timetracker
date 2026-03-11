# Website Time Tracker

Tracks time spent on YouTube, Facebook, and Instagram. Automatically closes tabs when you hit the 30-minute daily limit per site.

---

## Requirements

- Linux with GNOME on Wayland
- Python 3.10+
- Firefox
- `xdotool` and `rich` (installed during setup)

---

## Installation

### 1. Install dependencies

```bash
pip3 install rich
sudo dnf install xdotool   # Fedora
# or
sudo apt install xdotool   # Ubuntu/Debian
```

### 2. Enable the systemd service (runs on boot)

```bash
systemctl --user daemon-reload
systemctl --user enable --now timetracker
```

Verify it's running:

```bash
systemctl --user status timetracker
```

### 3. Load the browser extension (Firefox)

1. Open Firefox and go to `about:debugging#/runtime/this-firefox`
2. Click **Load Temporary Add-on**
3. Select `/home/qhmoso/work/timetracker/extension/manifest.json`

> **Note:** Temporary add-ons are removed when Firefox restarts. To make it permanent, the extension would need to be signed by Mozilla or installed via an enterprise policy.

---

## Usage

### View the live dashboard

```bash
python3 /home/qhmoso/work/timetracker/tracker_tui.py
```

Press `Ctrl+C` to close the dashboard (the daemon keeps running in the background).

### Dashboard layout

```
  YouTube      ████████░░░░░░░░░░░░░░░░    14m 23s
  Facebook     ███████████████████░░░░░    28m 01s
  Instagram    ████████████████████████    30m 00s  ⚠  LIMIT — tabs closed
```

- Progress bars fill relative to the most-used site today
- Sites that hit the limit turn **red** and all their tabs are closed automatically

---

## Configuration

### Change the time limit

Edit the `LIMIT_SECONDS` line in both files:

**`trackerd.py`** (line 18):
```python
LIMIT_SECONDS = 30 * 60  # change 30 to any number of minutes
```

**`tracker_tui.py`** (line 14):
```python
LIMIT_SECONDS = 30 * 60
```

Then restart the daemon:

```bash
systemctl --user restart timetracker
```

### Add or remove tracked sites

Edit the `TRACKED_SITES` and `SITES` entries in both `trackerd.py` and `extension/background.js`.

---

## File Structure

```
timetracker/
├── trackerd.py          # Background daemon (HTTP server + database writes)
├── tracker_tui.py       # Terminal dashboard (read-only, open on demand)
├── extension/
│   ├── manifest.json    # Firefox extension manifest
│   └── background.js    # Tracks active tab time, closes blocked tabs
└── README.md
```

Data is stored in `~/.timetracker.db` (SQLite). Logs are written to `~/.timetracker.log`.

---

## Service Management

```bash
systemctl --user status timetracker    # check status
systemctl --user stop timetracker      # stop the daemon
systemctl --user start timetracker     # start the daemon
systemctl --user restart timetracker   # restart after config changes
journalctl --user -u timetracker -f    # follow live logs
```

---

## How It Works

1. The **browser extension** watches which tab is active every 5 seconds
2. It sends the site name and elapsed time to the **daemon** via `POST /heartbeat`
3. The daemon stores the data in SQLite and exposes `GET /status` with blocked sites
4. The extension checks `/status` and **closes any tabs** for sites over the limit
5. The **TUI dashboard** reads the same SQLite database and displays live stats
