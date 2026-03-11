#!/usr/bin/env python3
"""
Time Tracker TUI
Live dashboard with today stats, monthly graphs, and full history.
Run 'python3 tracker_tui.py' anytime to view your stats.
Controls: Tab / Shift+Tab to switch views, Ctrl+C to quit.
"""

import calendar
import sqlite3
import sys
import termios
import threading
import time
import tty
from datetime import date
from pathlib import Path

import plotext as plt
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text
from rich import box

DB_PATH = Path.home() / ".timetracker.db"

SITE_LIMITS = {
    "YouTube":   30 * 60,
    "Facebook":  30 * 60,
    "Instagram": 30 * 60,
    "VSCode":    None,
}

CATEGORIES = {
    "Work":   ["VSCode"],
    "Social": ["YouTube", "Facebook", "Instagram"],
}

SITE_COLORS = {
    "YouTube":   "red",
    "Facebook":  "blue",
    "Instagram": "magenta",
    "VSCode":    "green",
}

# plotext color names
PLT_COLORS = {
    "YouTube":   "red",
    "Facebook":  "blue",
    "Instagram": "magenta+",
    "VSCode":    "green",
}

VIEWS = ["Today", "Month", "History"]

console = Console()


# ── DB helpers ─────────────────────────────────────────────────────────────────

def get_today_stats(conn) -> dict:
    today = str(date.today())
    rows = conn.execute(
        "SELECT site, seconds FROM sessions WHERE date = ?", (today,)
    ).fetchall()
    return {row[0]: row[1] for row in rows}


def get_month_stats(conn) -> dict[str, dict[int, int]]:
    """Returns {site: {day: seconds}} for the current month."""
    today = date.today()
    prefix = today.strftime("%Y-%m-")
    rows = conn.execute(
        "SELECT site, date, seconds FROM sessions WHERE date LIKE ?",
        (prefix + "%",),
    ).fetchall()
    result: dict[str, dict[int, int]] = {}
    for site, d, secs in rows:
        day = int(d.split("-")[2])
        result.setdefault(site, {})[day] = secs
    return result


def get_history(conn) -> list:
    return conn.execute(
        "SELECT date, site, seconds FROM sessions ORDER BY date DESC, site"
    ).fetchall()


# ── Formatting ─────────────────────────────────────────────────────────────────

def fmt_time(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}h {m:02d}m {s:02d}s"
    elif m > 0:
        return f"{m}m {s:02d}s"
    return f"{s}s"


def make_bar(secs: int, max_secs: int, width: int = 24) -> str:
    filled = int((secs / max_secs) * width) if max_secs > 0 else 0
    return "█" * filled + "░" * (width - filled)


# ── Views ──────────────────────────────────────────────────────────────────────

def view_today(conn) -> Group:
    today = str(date.today())
    stats = get_today_stats(conn)
    max_secs = max(stats.values(), default=1)

    sections = [Text.from_markup(f"\n[bold]Today  ({today})[/]\n")]

    for label, sites in CATEGORIES.items():
        t = Text()
        t.append(f" {label}\n", style="bold dim")
        for site in sites:
            secs = stats.get(site, 0)
            limit = SITE_LIMITS.get(site)
            over = limit is not None and secs >= limit
            color = "red" if over else SITE_COLORS[site]
            bar = make_bar(secs, max_secs)
            time_str = fmt_time(secs)
            limit_str = f"/ {fmt_time(limit)}" if limit else "  no limit"
            warn = "  ⚠ LIMIT — tabs closed" if over else ""
            t.append(f"  {site:<12}", style=f"bold {color}")
            t.append(f" {bar} ", style=color)
            t.append(f"{time_str:>12} ", style=f"bold {color}")
            t.append(f"{limit_str}", style="dim")
            t.append(f"{warn}\n", style="bold red")
        sections.append(t)

    return Group(*sections)


def view_month(conn) -> Group:
    today = date.today()
    month_name = today.strftime("%B %Y")
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    days = list(range(1, days_in_month + 1))

    month_data = get_month_stats(conn)
    all_sites = list(SITE_LIMITS.keys())

    sections = [Text.from_markup(f"\n[bold]Monthly Overview — {month_name}[/]\n")]

    for site in all_sites:
        site_data = month_data.get(site, {})
        if not any(site_data.values()):
            continue

        minutes = [round(site_data.get(d, 0) / 60, 1) for d in days]

        plt.clf()
        plt.theme("dark")
        plt.plotsize(60, 12)
        plt.bar(days, minutes, color=PLT_COLORS.get(site, "white"))
        plt.title(site)
        plt.xlabel("Day of month")
        plt.ylabel("Minutes")
        plt.xlim(1, days_in_month)

        graph_str = plt.build()

        color = SITE_COLORS[site]
        graph_text = Text()
        graph_text.append(f"\n {site}\n", style=f"bold {color}")
        graph_text.append(graph_str, style=color)
        graph_text.append("\n")
        sections.append(graph_text)

    if len(sections) == 1:
        sections.append(Text("\n  No data for this month yet.\n", style="dim"))

    return Group(*sections)


def view_history(conn) -> Group:
    history = get_history(conn)

    hist_table = Table(box=box.SIMPLE, show_header=True,
                       header_style="bold cyan", expand=True)
    hist_table.add_column("Date", style="dim", width=12)
    hist_table.add_column("Site", width=12)
    hist_table.add_column("Time Spent", justify="right")
    hist_table.add_column("Limit", justify="right", style="dim")

    seen_dates: set = set()
    for d, site, secs in history:
        limit = SITE_LIMITS.get(site)
        over = limit is not None and secs >= limit
        color = "red" if over else SITE_COLORS.get(site, "white")
        date_cell = d if d not in seen_dates else ""
        seen_dates.add(d)
        limit_cell = fmt_time(limit) if limit else "no limit"
        hist_table.add_row(
            date_cell,
            f"[{color}]{site}[/]",
            f"[{color}]{fmt_time(secs)}[/]",
            limit_cell,
        )

    return Group(
        Text.from_markup("\n[bold]Full History[/]\n"),
        hist_table,
    )


# ── Main display ───────────────────────────────────────────────────────────────

def build_display(conn, current_view: int) -> Panel:
    tabs = Text()
    for i, name in enumerate(VIEWS):
        if i == current_view:
            tabs.append(f" [{name}] ", style="bold white on bright_blue")
        else:
            tabs.append(f"  {name}  ", style="dim")
        if i < len(VIEWS) - 1:
            tabs.append(" ")

    if current_view == 0:
        content = view_today(conn)
    elif current_view == 1:
        content = view_month(conn)
    else:
        content = view_history(conn)

    return Panel(
        Group(
            tabs,
            Rule(style="dim"),
            content,
            Rule(style="dim"),
            Text.from_markup("[dim]Tab: next view  •  Ctrl+C: quit[/]"),
        ),
        title="[bold white]Website Time Tracker[/]",
        border_style="bright_blue",
        padding=(0, 1),
    )


# ── Keyboard input ─────────────────────────────────────────────────────────────

def read_keys(current_view_ref: list, stop_event: threading.Event):
    """Reads keystrokes in a background thread. Tab cycles views."""
    import select, os
    if not sys.stdin.isatty():
        return
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        while not stop_event.is_set():
            ready, _, _ = select.select([fd], [], [], 0.2)
            if not ready:
                continue
            ch = os.read(fd, 4).decode("utf-8", errors="ignore")
            if "\t" in ch:
                current_view_ref[0] = (current_view_ref[0] + 1) % len(VIEWS)
            elif "\x03" in ch:  # Ctrl+C
                stop_event.set()
                break
    except Exception:
        pass
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    if not DB_PATH.exists():
        console.print("[yellow]No data yet. Is the tracker daemon running?[/]")
        console.print("  Start it with:  [bold]systemctl --user start timetracker[/]")
        return

    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    current_view = [0]  # mutable ref for thread
    stop_event = threading.Event()

    key_thread = threading.Thread(
        target=read_keys, args=(current_view, stop_event), daemon=True
    )
    key_thread.start()

    try:
        with Live(build_display(conn, current_view[0]), console=console,
                  refresh_per_second=1, screen=True) as live:
            while not stop_event.is_set():
                time.sleep(0.2)
                live.update(build_display(conn, current_view[0]))
    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()
        conn.close()


if __name__ == "__main__":
    main()
