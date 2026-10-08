# -*- coding: utf-8 -*-
"""Google Drive՝ ՄԻԱՅՆ ԿԱՐԴԱԼՈՒ համար (drive.readonly). Ոչինչ չի փոխվում, սկրիպտ Drive-ում չկա:
Եղանակ 1. Service account (GOOGLE_SA_JSON=path\\to\\key.json) + թղթապանակը/ֆայլը share արեք այդ email-ին (Viewer).
Եղանակ 2. Հանրային հղում («Anyone with the link»)՝ առանց բանալու (ֆայլեր և Google Sheets)."""
import os
import re
import tempfile
import urllib.request
from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
SHEET = "application/vnd.google-apps.spreadsheet"
FOLDER = "application/vnd.google-apps.folder"


def parse_link(link):
    link = link.strip()
    m = re.search(r"/folders/([\w\-]+)", link)
    if m:
        return "folder", m[1]
    m = re.search(r"/d/([\w\-]+)", link) or re.search(r"[?&]id=([\w\-]+)", link)
    if m:
        return ("sheet" if "spreadsheets" in link else "file"), m[1]
    if re.fullmatch(r"[\w\-]{20,}", link):
        return "file", link
    raise ValueError("Google Drive հղումը չճանաչվեց")


def _service():
    key = os.getenv("GOOGLE_SA_JSON")
    if not key or not Path(key).exists():
        return None
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    creds = service_account.Credentials.from_service_account_file(key, scopes=SCOPES)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def _http(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
        data = r.read()
        if data[:15].lower().startswith(b"<!doctype html") or b"accounts.google.com" in data[:3000]:
            raise PermissionError("Ֆայլը փակ է: Բացեք «Anyone with the link — Viewer» կամ օգտագործեք service account")
        f.write(data)
    return dest


def fetch(link):
    """Վերադարձնում է ներբեռնված ֆայլերի ցուցակը (.xlsx / .csv)."""
    kind, fid = parse_link(link)
    tmp = Path(tempfile.mkdtemp(prefix="drv_"))
    svc = _service()
    out = []
    if svc:
        from googleapiclient.http import MediaIoBaseDownload
        import io
        if kind == "folder":
            files = svc.files().list(q=f"'{fid}' in parents and trashed=false", pageSize=200,
                                     fields="files(id,name,mimeType)").execute()["files"]
        else:
            files = [svc.files().get(fileId=fid, fields="id,name,mimeType").execute()]
        for f in files:
            name, mt = f["name"], f["mimeType"]
            if mt == FOLDER:
                continue
            if mt == SHEET:
                req = svc.files().export_media(fileId=f["id"], mimeType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                name += ".xlsx"
            elif name.lower().endswith((".xlsx", ".csv", ".xlsm")):
                req = svc.files().get_media(fileId=f["id"])
            else:
                continue
            buf = io.BytesIO()
            dl = MediaIoBaseDownload(buf, req)
            done = False
            while not done:
                _, done = dl.next_chunk()
            p = tmp / re.sub(r"[^\w.\-]", "_", name)
            p.write_bytes(buf.getvalue())
            out.append(p)
    else:
        if kind == "folder":
            raise PermissionError("Թղթապանակի համար պետք է service account (GOOGLE_SA_JSON). Կամ ուղարկեք ֆայլի հղումը/ֆայլը")
        if kind == "sheet":
            out.append(_http(f"https://docs.google.com/spreadsheets/d/{fid}/export?format=xlsx", tmp / "sheet.xlsx"))
        else:
            out.append(_http(f"https://drive.google.com/uc?export=download&id={fid}", tmp / "file.bin"))
            head = out[-1].read_bytes()[:4]
            out[-1] = out[-1].rename(out[-1].with_suffix(".xlsx" if head == b"PK\x03\x04" else ".csv"))
    if not out:
        raise FileNotFoundError("Drive-ում .xlsx / .csv / Google Sheet չգտնվեց")
    return out
