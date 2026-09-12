#!/usr/bin/env python3
from __future__ import annotations
import json,re,urllib.parse
from pathlib import Path
from datetime import datetime,timezone
import requests
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
SOURCES=ROOT/"data"/"discovery-sources.json"
KNOWN=ROOT/"data"/"funding-programs.json"
OUT=ROOT/"data"/"discovered-funding.json"
HEADERS={"User-Agent":"Machine-Learning-Venues funding discovery (+https://github.com/ritaadhikari/Machine-Learning-Venues)"}
KW=re.compile(r"(grant|scholar|financial.?assistance|travel.?support|travel.?award|funding|subsid|mobility|student.?support|fellowship)",re.I)

def norm(url):
    u=urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((u.scheme,u.netloc,u.path.rstrip("/"),u.query,""))

def main():
    sources=json.loads(SOURCES.read_text())["sources"]
    known=json.loads(KNOWN.read_text())["programs"]
    known_urls={norm(p["official"]) for p in known}
    existing={}
    if OUT.exists():
        try:
            for c in json.loads(OUT.read_text()).get("candidates",[]):existing[norm(c["url"])]=c
        except:pass

    for src in sources:
        try:
            r=requests.get(src["url"],headers=HEADERS,timeout=25,allow_redirects=True);r.raise_for_status()
            soup=BeautifulSoup(r.text,"html.parser")
            for a in soup.find_all("a",href=True):
                label=" ".join(a.stripped_strings).strip()
                href=urllib.parse.urljoin(r.url,a["href"])
                if not href.startswith("http"):continue
                if not (KW.search(label) or KW.search(href)):continue
                n=norm(href)
                if n in known_urls:continue
                item=existing.get(n,{"title":label or href,"url":href,"foundFrom":src["name"],"firstSeen":datetime.now(timezone.utc).date().isoformat(),"status":"needs-review"})
                item["lastSeen"]=datetime.now(timezone.utc).date().isoformat()
                existing[n]=item
        except Exception as e:
            print("skip",src["name"],type(e).__name__,e)

    candidates=sorted(existing.values(),key=lambda x:(x.get("status",""),x.get("title","").lower()))
    OUT.write_text(json.dumps({"meta":{"lastRun":datetime.now(timezone.utc).isoformat(),"count":len(candidates)},"candidates":candidates},indent=2,ensure_ascii=False)+"\n")
    print("discovered candidates:",len(candidates))

if __name__=="__main__":main()
