# -*- coding: utf-8 -*-
"""Google Drive՝ ՄԻԱՅՆ հին մոնիտորինգի արխիվը մեկ անգամ ներմուծելու համար (techimport.py).
Հավելվածի ընթացիկ աշխատանքը (ԱԿՏ, մոնիտորինգ) Drive-ից այլևս կախված չէ."""
import html as _html
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

import drive_src


def _scrape(fid):
    url = f"https://drive.google.com/embeddedfolderview?id={fid}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "en"})
    try:
        html = urllib.request.urlopen(req, timeout=40).read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        if e.code in (401, 403, 404):
            raise PermissionError("Папка закрыта: Google Drive → «Поделиться» → «Все, у кого есть ссылка» → «Читатель»")
        raise
    out = []
    for m in re.finditer(r'id="entry-([\w-]+)"(.*?)flip-entry-title">([^<]*)<', html, re.S):
        chunk = m[2]
        kind = "sheet" if "spreadsheets" in chunk else ("folder" if "/folders/" in chunk else "file")
        out.append(dict(id=m[1], name=_html.unescape(m[3]).strip(), kind=kind))
    if not out:
        for sid in dict.fromkeys(re.findall(r"spreadsheets/d/([\w-]{25,})", html)):
            out.append(dict(id=sid, name="", kind="sheet"))
    if not out:
        raise PermissionError("В папке не найдено файлов (или она закрыта: «Все, у кого есть ссылка» → «Читатель»)")
    return out


def list_folder(link):
    """-> [{id, name, kind: sheet|file|folder}]"""
    kind, fid = drive_src.parse_link(link)
    if kind != "folder":
        raise ValueError("Это не ссылка на папку (нужна …/drive/folders/…)")
    svc = drive_src._service()
    if svc:
        files = svc.files().list(q=f"'{fid}' in parents and trashed=false", pageSize=500,
                                 fields="files(id,name,mimeType)").execute()["files"]
        return [dict(id=f["id"], name=f["name"], kind="sheet" if f["mimeType"] == drive_src.SHEET else
                     "folder" if f["mimeType"] == drive_src.FOLDER else "file") for f in files]
    key = os.getenv("GOOGLE_API_KEY")
    if key:
        q = urllib.parse.quote(f"'{fid}' in parents and trashed=false")
        try:
            data = json.loads(urllib.request.urlopen(
                f"https://www.googleapis.com/drive/v3/files?q={q}&pageSize=500&fields=files(id,name,mimeType)&key={key}",
                timeout=40).read())
            return [dict(id=f["id"], name=f["name"], kind="sheet" if f["mimeType"] == drive_src.SHEET else
                         "folder" if f["mimeType"] == drive_src.FOLDER else "file") for f in data.get("files", [])]
        except Exception:  # noqa — փորձում ենք հանրային եղանակը
            pass
    return _scrape(fid)


def download_sheet(file_id, dest):
    """Google Sheet -> .xlsx (նշումներով)."""
    svc = drive_src._service()
    if svc:
        return drive_src.fetch(f"https://docs.google.com/spreadsheets/d/{file_id}/edit")[0]
    try:
        return drive_src._http(f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=xlsx", dest)
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise PermissionError("файл закрыт («Все, у кого есть ссылка» → «Читатель»)")
        raise
