#!/usr/bin/env python3
"""
Time Tracker TUI
Connects to the running daemon and displays a live dashboard.
Run 'python3 tracker_tui.py' anytime to view your stats.
"""

import sqlite3
import time
from datetime import date
from pathlib import Path

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text
from rich import box

DB_PATH = Path.home() / ".timetracker.db"
LIMIT_SECONDS = 30 * 60

TRACKED_SITES = ["YouTube", "Facebook", "Instagram"]

SITE_COLORS = {
    "YouTube": "red",
    "Facebook": "blue",
    "Instagram": "magenta",
}

console = Console()


def get_today_stats(conn) -> dict:
    today = str(date.today())
    rows = conn.execute(
        "SELECT site, seconds FROM sessions WHERE date = ?", (today,)
    ).fetchall()
    return {row[0]: row[1] for row in rows}


def get_history(conn) -> list:
    return conn.execute(
        "SELECT date, site, seconds FROM sessions ORDER BY date DESC, site"
    ).fetchall()


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


def build_display(conn) -> Panel:
    today = str(date.today())
    stats = get_today_stats(conn)
    history = get_history(conn)
    max_secs = max(stats.values(), default=1)

    # Today section
    today_text = Text()
    for site in TRACKED_SITES:
        secs = stats.get(site, 0)
        over = secs >= LIMIT_SECONDS
        color = "red" if over else SITE_COLORS[site]
        bar = make_bar(secs, max_secs)
        time_str = fmt_time(secs)
        warn = "  ⚠  LIMIT — tabs closed" if over else ""
        today_text.append(f"  {site:<12}", style=f"bold {color}")
        today_text.append(f" {bar} ", style=color)
        today_text.append(f"{time_str:>12}", style=f"bold {color}")
        today_text.append(f"{warn}\n", style="bold red")

    # History table
    hist_table = Table(box=box.SIMPLE, show_header=True,
                       header_style="bold cyan", expand=True)
    hist_table.add_column("Date", style="dim", width=12)
    hist_table.add_column("Site", width=12)
    hist_table.add_column("Time Spent", justify="right")

    seen_dates: set = set()
    for d, site, secs in history[:30]:
        over = secs >= LIMIT_SECONDS
        color = "red" if over else SITE_COLORS.get(site, "white")
        date_cell = d if d not in seen_dates else ""
        seen_dates.add(d)
        hist_table.add_row(date_cell, f"[{color}]{site}[/]",
                           f"[{color}]{fmt_time(secs)}[/]")

    return Panel(
        Group(
            Text.from_markup(f"\n[bold]Today  ({today})[/]\n"),
            today_text,
            Rule(style="dim"),
            Text.from_markup("[bold]History[/]\n"),
            hist_table,
            Rule(style="dim"),
            Text.from_markup(
                f"[dim]Limit: {fmt_time(LIMIT_SECONDS)} per site  •  "
                f"Press Ctrl+C to quit[/]"
            ),
        ),
        title="[bold white]Website Time Tracker[/]",
        border_style="bright_blue",
        padding=(0, 1),
    )


def main():
    if not DB_PATH.exists():
        console.print("[yellow]No data yet. Is the tracker daemon running?[/]")
        console.print("  Start it with:  [bold]systemctl --user start timetracker[/]")
        return

    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    try:
        with Live(build_display(conn), console=console, refresh_per_second=1,
                  screen=True) as live:
            while True:
                time.sleep(1)
                live.update(build_display(conn))
    except KeyboardInterrupt:
        pass
    finally:
        conn.close()


if __name__ == "__main__":
    main()
