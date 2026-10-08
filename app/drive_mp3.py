# -*- coding: utf-8 -*-
"""Google Drive թղթապանակի MP3 ֆայլերի ցուցակ (մեդիա պլանում հոլովակ ընտրելու համար).

Թղթապանակը պետք է բացված լինի «Anyone with the link — Viewer»:
Ցուցակը կարդացվում է այս հերթականությամբ (առաջինը, որ աշխատում է).
  1) GOOGLE_API_KEY  (Google Cloud-ի API key, Drive API միացված) — ամենահուսալին
  2) GOOGLE_SA_JSON  (service account, թղթապանակը share արած այդ email-ին)
  3) Առանց բանալու՝ հանրային թղթապանակի էջից (embeddedfolderview)
Ոչինչ չի փոխվում Drive-ում, միայն կարդացվում է."""
import html
import json
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent   # նախագծի արմատը (app/-ից մեկ մակարդակ վեր)
from config import DATA  # noqa: E402
CFG = DATA / "mp3_folder.json"
AUDIO_EXT = (".mp3",)
DEFAULT_FOLDER = "https://drive.google.com/drive/folders/1ecwboUNN3H9QR1EvqTt5lF5yVfGI--LA"  # Mix Media MP3


# ------------------------------------------------------------------ թղթապանակի հղումը
def folder_id(link):
    link = (link or "").strip()
    m = re.search(r"/folders/([\w\-]+)", link) or re.search(r"[?&]id=([\w\-]+)", link)
    if m:
        return m[1]
    if re.fullmatch(r"[\w\-]{20,}", link):
        return link
    return None


def get_folder():
    """-> թղթապանակի հղում (բոտում պահված կամ MP3_FOLDER run.bat-ում) կամ None."""
    try:
        v = json.load(open(CFG, encoding="utf-8")).get("link")
        if v:
            return v
    except Exception:
        pass
    return os.getenv("MP3_FOLDER") or DEFAULT_FOLDER


def set_folder(link):
    fid = folder_id(link)
    if not fid:
        raise ValueError("Սա Google Drive թղթապանակի հղում չէ (…/drive/folders/…)")
    CFG.parent.mkdir(exist_ok=True)
    url = f"https://drive.google.com/drive/folders/{fid}"
    json.dump({"link": url}, open(CFG, "w", encoding="utf-8"), ensure_ascii=False)
    return url


def file_link(file_id):
    """Սեղմելիս բացվում է Drive-ի նվագարկիչը."""
    return f"https://drive.google.com/file/d/{file_id}/view"


# ------------------------------------------------------------------ ցուցակ
def _is_audio(name, mime=""):
    return name.lower().endswith(AUDIO_EXT) or mime.startswith("audio/")


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "en"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def _by_api_key(fid, key):
    out, token = [], None
    while True:
        q = urllib.parse.urlencode(dict(q=f"'{fid}' in parents and trashed=false", key=key, pageSize=1000,
                                        fields="nextPageToken,files(id,name,mimeType)", orderBy="name",
                                        **({"pageToken": token} if token else {})))
        data = json.loads(_get(f"https://www.googleapis.com/drive/v3/files?{q}"))
        out += [(f["id"], f["name"]) for f in data.get("files", []) if _is_audio(f["name"], f.get("mimeType", ""))]
        token = data.get("nextPageToken")
        if not token:
            return out


def _by_service_account(fid):
    key = os.getenv("GOOGLE_SA_JSON")
    if not key or not Path(key).exists():
        return None
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    creds = service_account.Credentials.from_service_account_file(
        key, scopes=["https://www.googleapis.com/auth/drive.readonly"])
    svc = build("drive", "v3", credentials=creds, cache_discovery=False)
    files = svc.files().list(q=f"'{fid}' in parents and trashed=false", pageSize=1000, orderBy="name",
                             fields="files(id,name,mimeType)").execute().get("files", [])
    return [(f["id"], f["name"]) for f in files if _is_audio(f["name"], f.get("mimeType", ""))]


def parse_embedded(page):
    """Հանրային թղթապանակի էջից՝ [(id, name)]."""
    out = []
    for m in re.finditer(r'id="entry-([\w\-]+)".*?class="flip-entry-title">(.*?)</div>', page, re.S):
        name = html.unescape(re.sub(r"<[^>]+>", "", m[2])).strip()
        if _is_audio(name):
            out.append((m[1], name))
    return out


def _by_public_page(fid):
    page = _get(f"https://drive.google.com/embeddedfolderview?id={fid}#list")
    if "accounts.google.com" in page[:5000] and "flip-entry" not in page:
        raise PermissionError("Թղթապանակը փակ է: Բացեք «Anyone with the link — Viewer»")
    return parse_embedded(page)


def list_mp3(link):
    """-> [(file_id, name)] ըստ անվան: Սխալի դեպքում՝ հասկանալի հաղորդագրությամբ բացառություն."""
    fid = folder_id(link)
    if not fid:
        raise ValueError("Թղթապանակի հղումը սխալ է")
    errors = []
    key = os.getenv("GOOGLE_API_KEY")
    if key:
        try:
            return sorted(_by_api_key(fid, key), key=lambda x: x[1].lower())
        except Exception as e:  # noqa
            errors.append(f"API key՝ {e}")
    try:
        r = _by_service_account(fid)
        if r is not None:
            return sorted(r, key=lambda x: x[1].lower())
    except Exception as e:  # noqa
        errors.append(f"service account՝ {e}")
    try:
        return sorted(_by_public_page(fid), key=lambda x: x[1].lower())
    except Exception as e:  # noqa
        errors.append(str(e))
    raise RuntimeError("Չհաջողվեց կարդալ թղթապանակը. " + " | ".join(errors))


# ------------------------------------------------------------------ լսելու համար (նախադիտում բոտում)
MAX_PREVIEW = 45 * 1024 * 1024  # Telegram-ը թույլ է տալիս մինչև 50 ՄԲ


def download(file_id):
    """MP3-ը ներբեռնում է հանրային հղումով (կամ API key-ով) -> bytes. Շատ մեծ ֆայլի դեպքում՝ ValueError."""
    key = os.getenv("GOOGLE_API_KEY")
    urls = []
    if key:
        urls.append(f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media&key={key}")
    urls += [f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t",
             f"https://drive.google.com/uc?export=download&id={file_id}&confirm=t"]
    last = None
    for u in urls:
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                size = int(r.headers.get("Content-Length") or 0)
                if size > MAX_PREVIEW:
                    raise ValueError("Ֆայլը շատ մեծ է բոտում լսելու համար (50 ՄԲ-ից ավել)")
                data = r.read(MAX_PREVIEW + 1)
            if len(data) > MAX_PREVIEW:
                raise ValueError("Ֆայլը շատ մեծ է բոտում լսելու համար (50 ՄԲ-ից ավել)")
            head = data[:300].lstrip().lower()
            if head.startswith((b"<!doctype html", b"<html")):
                last = PermissionError("Ֆայլը փակ է կամ Drive-ը չտվեց ներբեռնել")
                continue
            return data
        except ValueError:
            raise
        except Exception as e:  # noqa
            last = e
    raise last or RuntimeError("Չհաջողվեց ներբեռնել")
