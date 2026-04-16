# -*- coding: utf-8 -*-
"""
Google Calendar（秘密の iCal URL）を取得し、前回実行時と内容が変わっていたら LINE に通知する。
初回実行時はベースラインのみ保存し、LINE は送らない（セットアップ直後の誤爆を防ぐ）。
環境変数: ICAL_URL, LINE_CHANNEL_ACCESS_TOKEN, LINE_USER_ID
"""
from __future__ import annotations

import hashlib
import os
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests
from icalendar import Calendar

JST = ZoneInfo("Asia/Tokyo")
STATE_FILE = "data/last_ical_sha256.txt"


def repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_state(path: str) -> str | None:
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as f:
        return f.read().strip() or None


def save_state(path: str, digest: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(digest)


def fetch_ical(url: str) -> bytes:
    r = requests.get(url, timeout=90)
    r.raise_for_status()
    return r.content


def build_summary(ical_bytes: bytes, max_lines: int = 40) -> str:
    """直近の予定の要約（変更通知に添える本文）。"""
    cal = Calendar.from_ical(ical_bytes)
    now = datetime.now(JST)
    start_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    window_end = now + timedelta(days=14)
    rows: list[tuple[datetime, str]] = []

    for component in cal.walk():
        if component.name != "VEVENT":
            continue
        summary = component.get("summary")
        if summary is None:
            continue
        title = str(summary)
        dtstart = component.get("dtstart")
        if dtstart is None:
            continue
        dt = dtstart.dt
        if isinstance(dt, datetime):
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=JST)
            else:
                dt = dt.astimezone(JST)
        else:
            dt = datetime.combine(dt, datetime.min.time(), tzinfo=JST)
        if dt < start_today or dt > window_end:
            continue
        rows.append((dt, title))

    rows.sort(key=lambda x: x[0])
    lines = [f"【カレンダーに変更がありました】({now.strftime('%Y-%m-%d %H:%M')} 時点)"]
    lines.append("")
    lines.append("▼ 直近の予定（参考・最大14日先まで）")
    if not rows:
        lines.append("（表示できる予定がありません）")
    else:
        for dt, title in rows[:max_lines]:
            lines.append(f"・{dt.strftime('%m/%d %H:%M')} {title}")
        if len(rows) > max_lines:
            lines.append(f"… ほか {len(rows) - max_lines} 件")

    text = "\n".join(lines)
    if len(text) > 4800:
        text = text[:4790] + "\n…(省略)"
    return text


def push_line(token: str, user_id: str, text: str) -> None:
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "to": user_id,
        "messages": [{"type": "text", "text": text}],
    }
    r = requests.post(url, json=payload, headers=headers, timeout=30)
    if r.status_code >= 400:
        print(r.text, file=sys.stderr)
        r.raise_for_status()


def main() -> int:
    try:
        ical_url = os.environ["ICAL_URL"]
        token = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
        user_id = os.environ["LINE_USER_ID"]
    except KeyError as e:
        print(f"Missing env: {e}", file=sys.stderr)
        return 1

    root = repo_root()
    state_path = os.path.join(root, STATE_FILE)

    body = fetch_ical(ical_url)
    digest = hashlib.sha256(body).hexdigest()
    prev = load_state(state_path)

    if prev == digest:
        print("カレンダー（iCal）の内容に変化はありません。")
        return 0

    if prev is None:
        save_state(state_path, digest)
        print("初回実行: ベースラインを保存しました。次回から変更時に LINE 通知します。")
        return 0

    summary = build_summary(body)
    push_line(token, user_id, summary)
    save_state(state_path, digest)
    print("変更を検知し、LINE に通知しました。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
