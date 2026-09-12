#!/usr/bin/env python3
from __future__ import annotations
import json,re,html as html_lib
from pathlib import Path
from datetime import datetime,timezone
import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"data"/"funding-programs.json"
HEADERS={"User-Agent":"Machine-Learning-Venues funding tracker (+https://github.com/ritaadhikari/Machine-Learning-Venues)"}
MONTH=r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
PATS=[
 re.compile(rf"\b{MONTH}\s+\d{{1,2}}(?:st|nd|rd|th)?[,]?\s+20\d{{2}}\b",re.I),
 re.compile(rf"\b\d{{1,2}}(?:st|nd|rd|th)?\s+{MONTH}[,]?\s+20\d{{2}}\b",re.I),
 re.compile(r"\b20\d{2}[-/]\d{1,2}[-/]\d{1,2}\b")
]
DEFAULT_LABELS=["application deadline","submission deadline","applications close","apply by","deadline"]

def page_text(url):
    r=requests.get(url,headers=HEADERS,timeout=25,allow_redirects=True);r.raise_for_status()
    s=BeautifulSoup(r.text,"html.parser")
    for t in s(["script","style","noscript"]):t.decompose()
    return re.sub(r"\s+"," ",html_lib.unescape(s.get_text(" ",strip=True))).replace("−","-")

def find_date(text,labels):
    low=text.lower()
    for lab in labels:
        start=0
        while True:
            i=low.find(lab.lower(),start)
            if i<0:break
            win=text[i:i+360];start=i+len(lab)
            for p in PATS:
                m=p.search(win)
                if m:
                    raw=re.sub(r"(\d)(st|nd|rd|th)\b",r"\1",m.group(0),flags=re.I)
                    try:return date_parser.parse(raw).date().isoformat()
                    except:pass
    return None

def main():
    payload=json.loads(DATA.read_text())
    changed=False;checked=0
    now=datetime.now(timezone.utc)
    for p in payload["programs"]:
        cfg=p.get("autoUpdate",{})
        if not cfg.get("enabled") or not cfg.get("page"):continue
        try:
            txt=page_text(cfg["page"]);checked+=1
            found=find_date(txt,cfg.get("deadlineLabels",DEFAULT_LABELS))
            # Conservative rule:
            # - never overwrite a curated exact deadline;
            # - only fill a missing date for watch/event-specific entries;
            # - recurring deadlines are computed by the frontend from recurrence rules.
            if found and not p.get("deadline") and not p.get("deadlineDateOnly") and p.get("deadlineType") not in ("rolling","recurring"):
                year=int(found[:4])
                if year>=now.year:
                    p["deadlineDateOnly"]=found
                    p["deadlineType"]="date-only"
                    changed=True
                    print("filled",p["name"],found)
        except Exception as e:
            print("skip",p["name"],type(e).__name__,e)
    today=now.date().isoformat()
    if payload["meta"].get("lastChecked")!=today:
        payload["meta"]["lastChecked"]=today;changed=True
    payload["meta"]["lastRunSummary"]=f"Checked {checked} official program pages."
    DATA.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+"\n")
    print("done",changed,checked)

if __name__=="__main__":main()
