"""SQLite 存储：查询日志（真实使用证据）、盯梢订阅与历史。"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS queries (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts INTEGER NOT NULL,
  claim TEXT NOT NULL,
  intent TEXT,
  verdict TEXT,
  session TEXT,
  ms INTEGER
);
CREATE TABLE IF NOT EXISTS watches (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  claim TEXT NOT NULL,
  created INTEGER NOT NULL,
  last_check INTEGER DEFAULT 0,
  last_verdict TEXT,
  fingerprint TEXT,
  history TEXT DEFAULT '[]',
  active INTEGER DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_queries_ts ON queries(ts);
"""


def _conn() -> sqlite3.Connection:
    Path(config.DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(config.DB_PATH, timeout=10)
    c.row_factory = sqlite3.Row
    return c


def init() -> None:
    with _conn() as c:
        c.executescript(SCHEMA)


def log_query(claim: str, intent: str, verdict: str, session: str, ms: int) -> None:
    with _conn() as c:
        c.execute(
            "INSERT INTO queries(ts,claim,intent,verdict,session,ms) VALUES(?,?,?,?,?,?)",
            (int(time.time()), claim[:200], intent, verdict, (session or "")[:64], ms),
        )


def stats() -> dict:
    today = int(time.mktime(time.localtime()[:3] + (0, 0, 0, 0, 0, -1)))
    with _conn() as c:
        total = c.execute("SELECT COUNT(*) FROM queries").fetchone()[0]
        today_n = c.execute("SELECT COUNT(*) FROM queries WHERE ts>=?", (today,)).fetchone()[0]
        sessions = c.execute("SELECT COUNT(DISTINCT session) FROM queries").fetchone()[0]
        rows = c.execute(
            "SELECT verdict, COUNT(*) n FROM queries GROUP BY verdict ORDER BY n DESC"
        ).fetchall()
        watches = c.execute("SELECT COUNT(*) FROM watches WHERE active=1").fetchone()[0]
    return {
        "total": total, "today": today_n, "sessions": sessions, "watches": watches,
        "by_verdict": {r["verdict"] or "unknown": r["n"] for r in rows},
    }


def recent(limit: int = 12) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT claim,verdict,intent,ts FROM queries ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [
        {"claim": r["claim"], "verdict": r["verdict"], "intent": r["intent"],
         "time": time.strftime("%m-%d %H:%M", time.localtime(r["ts"]))}
        for r in rows
    ]


def add_watch(claim: str) -> int:
    with _conn() as c:
        cur = c.execute("INSERT INTO watches(claim,created) VALUES(?,?)",
                        (claim[:200], int(time.time())))
        return int(cur.lastrowid)


def list_watches() -> list[dict]:
    with _conn() as c:
        rows = c.execute("SELECT * FROM watches ORDER BY active DESC, id DESC").fetchall()
    out = []
    for r in rows:
        try:
            hist = json.loads(r["history"] or "[]")
        except Exception:
            hist = []
        out.append({
            "id": r["id"], "claim": r["claim"], "created": r["created"],
            "last_check": r["last_check"], "last_verdict": r["last_verdict"],
            "active": bool(r["active"]), "history": hist[-8:],
        })
    return out


def get_watch(wid: int) -> dict | None:
    with _conn() as c:
        r = c.execute("SELECT * FROM watches WHERE id=?", (wid,)).fetchone()
    if not r:
        return None
    try:
        hist = json.loads(r["history"] or "[]")
    except Exception:
        hist = []
    return {"id": r["id"], "claim": r["claim"], "last_verdict": r["last_verdict"],
            "fingerprint": r["fingerprint"] or "", "history": hist, "active": bool(r["active"])}


def update_watch(wid: int, verdict: str, fingerprint: str, snapshot: dict) -> None:
    w = get_watch(wid) or {"history": []}
    hist = (w.get("history") or [])[-9:] + [{
        "ts": int(time.time()), "verdict": verdict, "fingerprint": fingerprint,
        "top": snapshot.get("top", []), "one_line": snapshot.get("one_line", ""),
    }]
    with _conn() as c:
        c.execute(
            "UPDATE watches SET last_check=?, last_verdict=?, fingerprint=?, history=? WHERE id=?",
            (int(time.time()), verdict, fingerprint, json.dumps(hist, ensure_ascii=False), wid),
        )


def set_active(wid: int, active: bool) -> None:
    with _conn() as c:
        c.execute("UPDATE watches SET active=? WHERE id=?", (1 if active else 0, wid))


def delete_watch(wid: int) -> None:
    with _conn() as c:
        c.execute("DELETE FROM watches WHERE id=?", (wid,))
