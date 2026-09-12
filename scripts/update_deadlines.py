#!/usr/bin/env python3
"""
Conservative official-page deadline updater.

What it does:
- Reads data/venues.json.
- Fetches each configured official page.
- Searches only near configured deadline labels.
- Updates exact ISO deadlines only when a date AND time are found.
- If a date is found without a time, stores YYYY-MM-DD in *DeadlineDateOnly.
- Never replaces a known future exact deadline with a weaker date-only guess.
- Continues safely when a page blocks scraping or its format changes.
"""

from __future__ import annotations
import json, re, sys, html as html_lib
from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "venues.json"

MONTH = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
DATE_PATTERNS = [
    re.compile(rf"\b{MONTH}\s+\d{{1,2}}(?:st|nd|rd|th)?[,]?\s+20\d{{2}}\b", re.I),
    re.compile(rf"\b\d{{1,2}}(?:st|nd|rd|th)?\s+{MONTH}[,]?\s+20\d{{2}}\b", re.I),
    re.compile(r"\b20\d{2}[-/]\d{1,2}[-/]\d{1,2}\b"),
]
TIME_RE = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s*(a\.?m\.?|p\.?m\.?)\b|\b([01]?\d|2[0-3]):([0-5]\d)\b", re.I)
TZ_RE = re.compile(r"\b(AoE|Anywhere on Earth|UTC(?:\s*[+\-−]\s*\d{1,2}(?::?\d{2})?)?|GMT(?:\s*[+\-−]\s*\d{1,2}(?::?\d{2})?)?|EDT|EST|PDT|PST|CET|CEST|SAST)\b", re.I)

TZ_FIXED = {
    "AOE": "-12:00", "ANYWHERE ON EARTH": "-12:00",
    "UTC": "+00:00", "GMT": "+00:00",
    "EDT": "-04:00", "EST": "-05:00", "PDT": "-07:00", "PST": "-08:00",
    "CET": "+01:00", "CEST": "+02:00", "SAST": "+02:00",
}

HEADERS = {
    "User-Agent": "Machine-Learning-Venues deadline checker (+https://github.com/ritaadhikari/Machine-Learning-Venues)"
}

def clean_text(raw_html: str) -> str:
    soup = BeautifulSoup(raw_html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(" ", strip=True)
    text = html_lib.unescape(text)
    text = text.replace("−", "-").replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", text)

def fetch(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=25, allow_redirects=True)
    r.raise_for_status()
    return clean_text(r.text)

def year_of(date_text: str) -> int | None:
    m = re.search(r"\b(20\d{2})\b", date_text)
    return int(m.group(1)) if m else None

def context_ok(window: str, terms: list[str]) -> bool:
    if not terms:
        return True
    low = window.lower()
    return any(term.lower() in low for term in terms)

def candidate_after_label(text: str, labels: list[str], allowed_years: list[int], context_terms: list[str]):
    candidates = []
    low = text.lower()
    for label in labels:
        start = 0
        ll = label.lower()
        while True:
            idx = low.find(ll, start)
            if idx < 0:
                break
            # Prefer content after the label; keep a little preceding context for cycle/track terms.
            window = text[max(0, idx-120): min(len(text), idx+420)]
            start = idx + len(ll)
            if not context_ok(window, context_terms):
                continue
            label_pos = window.lower().find(ll)
            after = window[label_pos + len(ll):]
            for pat in DATE_PATTERNS:
                dm = pat.search(after)
                if not dm:
                    continue
                dtxt = dm.group(0)
                y = year_of(dtxt)
                if y not in allowed_years:
                    continue
                # Time/timezone are searched close to the found date.
                tail = after[dm.start(): min(len(after), dm.end()+150)]
                tm = TIME_RE.search(tail)
                tzm = TZ_RE.search(tail)
                candidates.append((dtxt, tm.group(0) if tm else None, tzm.group(0) if tzm else None, window))
                break
    return candidates

def parse_date(date_text: str):
    cleaned = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", date_text, flags=re.I)
    return date_parser.parse(cleaned, fuzzy=False)

def parse_time(time_text: str | None):
    if not time_text:
        return None
    s = time_text.lower().replace(".", "")
    m = re.match(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)$", s)
    if m:
        h = int(m.group(1)); minute = int(m.group(2) or 0)
        if m.group(3) == "pm" and h != 12: h += 12
        if m.group(3) == "am" and h == 12: h = 0
        return h, minute
    m = re.match(r"([01]?\d|2[0-3]):([0-5]\d)$", s)
    return (int(m.group(1)), int(m.group(2))) if m else None

def offset_from_token(token: str | None):
    if not token:
        return None
    key = token.upper().strip()
    if key in TZ_FIXED:
        return TZ_FIXED[key]
    key = key.replace("−", "-").replace(" ", "")
    m = re.match(r"(?:UTC|GMT)([+\-])(\d{1,2})(?::?(\d{2}))?$", key)
    if m:
        sign = m.group(1); h = int(m.group(2)); minute = int(m.group(3) or 0)
        return f"{sign}{h:02d}:{minute:02d}"
    return None

def offset_for_iana(zone_name: str, date_obj, hour: int, minute: int):
    try:
        z = ZoneInfo(zone_name)
        dt = datetime(date_obj.year, date_obj.month, date_obj.day, hour, minute, tzinfo=z)
        off = dt.utcoffset()
        total = int(off.total_seconds() // 60)
        sign = "+" if total >= 0 else "-"
        total = abs(total)
        return f"{sign}{total//60:02d}:{total%60:02d}"
    except Exception:
        return None

def make_iso(date_text: str, time_text: str | None, tz_token: str | None, fallback_zone: str | None):
    d = parse_date(date_text)
    time_parts = parse_time(time_text)
    if not time_parts:
        return None, d.strftime("%Y-%m-%d")
    hour, minute = time_parts
    offset = offset_from_token(tz_token)
    if not offset and fallback_zone:
        offset = offset_for_iana(fallback_zone, d, hour, minute)
    if not offset:
        return None, d.strftime("%Y-%m-%d")
    return f"{d.year:04d}-{d.month:02d}-{d.day:02d}T{hour:02d}:{minute:02d}:00{offset}", None

def is_future_iso(value: str | None) -> bool:
    if not value:
        return False
    try:
        return datetime.fromisoformat(value).astimezone(timezone.utc) > datetime.now(timezone.utc)
    except Exception:
        return False

def update_deadline(v: dict, kind: str, text: str):
    cfg = v["autoUpdate"]
    labels = cfg.get("paperLabels" if kind == "paper" else "abstractLabels", [])
    if not labels:
        return False
    candidates = candidate_after_label(
        text, labels, cfg.get("allowedYears", []), cfg.get("contextTerms", [])
    )
    if not candidates:
        return False

    # Choose the first high-confidence labeled candidate.
    date_text, time_text, tz_token, _ = candidates[0]
    iso, date_only = make_iso(date_text, time_text, tz_token, cfg.get("fallbackTimeZone"))

    iso_key = "paperDeadline" if kind == "paper" else "abstractDeadline"
    date_key = "paperDeadlineDateOnly" if kind == "paper" else "abstractDeadlineDateOnly"

    changed = False
    if iso:
        if v.get(iso_key) != iso:
            print(f"  {kind}: {v.get(iso_key)} -> {iso}")
            v[iso_key] = iso
            changed = True
        if v.get(date_key):
            v[date_key] = None
            changed = True
    elif date_only:
        # Do not downgrade a known future exact deadline to date-only.
        if not is_future_iso(v.get(iso_key)) and v.get(date_key) != date_only:
            print(f"  {kind} date-only: {v.get(date_key)} -> {date_only}")
            v[date_key] = date_only
            changed = True
    return changed

def main():
    payload = json.loads(DATA.read_text(encoding="utf-8"))
    changed_deadline = False
    checked = 0

    for v in payload["venues"]:
        cfg = v.get("autoUpdate", {})
        if not cfg.get("enabled") or not cfg.get("page"):
            continue
        print(f"Checking {v['name']}: {cfg['page']}")
        try:
            text = fetch(cfg["page"])
            checked += 1
            changed_deadline |= update_deadline(v, "abstract", text)
            changed_deadline |= update_deadline(v, "paper", text)
        except Exception as e:
            print(f"  skipped: {type(e).__name__}: {e}")

    today = datetime.now(timezone.utc).date().isoformat()
    meta_changed = payload.setdefault("meta", {}).get("lastChecked") != today
    payload["meta"]["lastChecked"] = today
    payload["meta"]["lastRunSummary"] = f"Checked {checked} official pages; conservative parser."

    DATA.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Done. deadline_changed={changed_deadline}, checked={checked}, date={today}")

if __name__ == "__main__":
    main()
