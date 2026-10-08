# -*- coding: utf-8 -*-
"""MP3 հոլովակ -> սեղմվող հղում (մեդիա պլանի «Ֆայլ» սյունակի համար).

Հերթականություն՝
  1) Օգտատերը ինքն է ուղարկել Google Drive-ի հղում  -> օգտագործվում է այն (…/view, բացվում է նվագարկիչով)
  2) Google Drive (OAuth, ձեր Google հաշիվը)     -> MP3-ը վերբեռնվում է «Mix Media MP3/<հաճախորդ>» թղթապանակ,
     բացվում է «Anyone with the link — Viewer», հղումը՝ https://drive.google.com/file/d/ID/view
     Կարգավորում՝ մեկ անգամ գործարկեք drive_login.py (տես README)
  3) Telegram ալիք (MP3_CHANNEL=@ալիք կամ -100…)  -> բոտը MP3-ը ուղարկում է ալիք, հղումը՝ https://t.me/…
  4) Ոչինչ կարգավորված չէ -> None (բոտը կզգուշացնի)"""
import asyncio
import logging
import os
import re
from pathlib import Path

log = logging.getLogger("mixbot.mp3link")
BASE = Path(__file__).resolve().parent.parent   # նախագծի արմատը (app/-ից մեկ մակարդակ վեր)
from config import DATA  # noqa: E402
TOKEN = DATA / "drive_token.json"
CLIENT = Path(os.getenv("GOOGLE_OAUTH_CLIENT") or (BASE / "credentials.json"))
SCOPES = ["https://www.googleapis.com/auth/drive.file"]
ROOT_FOLDER = "Mix Media MP3"
FOLDER = "application/vnd.google-apps.folder"


# ------------------------------------------------------------------ 1) օգտատիրոջ հղում
def drive_link_from_text(text):
    """Google Drive / այլ http հղում -> մաքուր հղում (Drive-ի դեպքում՝ …/view) կամ None."""
    t = (text or "").strip()
    if not re.match(r"https?://", t):
        return None
    m = re.search(r"/file/d/([\w\-]+)", t) or re.search(r"[?&]id=([\w\-]+)", t)
    if m and "google." in t:
        return f"https://drive.google.com/file/d/{m[1]}/view"
    return t.split()[0]


# ------------------------------------------------------------------ 2) Google Drive
def _service():
    if not TOKEN.exists():
        return None
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            TOKEN.write_text(creds.to_json(), encoding="utf-8")
        else:
            return None
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def _folder(svc, name, parent=None):
    safe = name.replace("'", "\\'")
    q = f"name='{safe}' and mimeType='{FOLDER}' and trashed=false" + (f" and '{parent}' in parents" if parent else "")
    found = svc.files().list(q=q, fields="files(id)", pageSize=1).execute().get("files", [])
    if found:
        return found[0]["id"]
    meta = dict(name=name, mimeType=FOLDER, **({"parents": [parent]} if parent else {}))
    return svc.files().create(body=meta, fields="id").execute()["id"]


def _drive_upload(path, name, client):
    svc = _service()
    if svc is None:
        return None
    from googleapiclient.http import MediaFileUpload
    root = _folder(svc, ROOT_FOLDER)
    parent = _folder(svc, client, root) if client else root
    f = svc.files().create(body=dict(name=name, parents=[parent]),
                           media_body=MediaFileUpload(str(path), mimetype="audio/mpeg"), fields="id").execute()
    svc.permissions().create(fileId=f["id"], body=dict(type="anyone", role="reader")).execute()
    return f"https://drive.google.com/file/d/{f['id']}/view"


# ------------------------------------------------------------------ 3) Telegram ալիք
def tg_message_link(chat, message_id):
    if getattr(chat, "username", None):
        return f"https://t.me/{chat.username}/{message_id}"
    cid = str(chat.id)
    return f"https://t.me/c/{cid[4:] if cid.startswith('-100') else cid.lstrip('-')}/{message_id}"


async def _tg_channel(bot, file_id, caption):
    ch = os.getenv("MP3_CHANNEL", "").strip()
    if not ch:
        return None
    msg = await bot.send_audio(chat_id=ch, audio=file_id, caption=caption[:1000])
    return tg_message_link(msg.chat, msg.message_id)


# ------------------------------------------------------------------ main
async def make_link(bot, path, file_name, file_id, client=""):
    """-> (link | None, աղբյուր՝ 'drive' / 'telegram' / None, սխալի տեքստ | None)"""
    errors = []
    try:
        name = file_name if file_name.lower().endswith(".mp3") else file_name + ".mp3"
        name = re.sub(r"(\.mp3)+$", ".mp3", name, flags=re.I)
        link = await asyncio.get_running_loop().run_in_executor(None, _drive_upload, path, name, client)
        if link:
            return link, "drive", None
    except Exception as e:  # noqa
        log.exception("drive upload failed")
        errors.append(f"Google Drive՝ {e}")
    try:
        link = await _tg_channel(bot, file_id, f"{client} · {file_name}".strip(" ·"))
        if link:
            return link, "telegram", None
    except Exception as e:  # noqa
        log.exception("telegram channel failed")
        errors.append(f"Telegram ալիք՝ {e}")
    return None, None, "; ".join(errors) or None
