# -*- coding: utf-8 -*-
"""Ընդհանուր ուղիներ, գույներ և կարգավորումներ (web հավելված)."""
import os
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent   # նախագծի արմատը (app/-ից մեկ մակարդակ վեր)
ROOT = Path(os.getenv("DATA_DIR") or BASE)   # DATA_DIR՝ մշտական սկավառակ (cloud), հակառակ դեպքում՝ նախագծի թղթապանակը
DATA = ROOT / "data"
OUT = ROOT / "output"
UPL = ROOT / "uploads"
VAULT = ROOT / "vault"
WEB = BASE / "web"
TPL = BASE / "templates"
ASSETS = BASE / "assets"
LAW_LIB = DATA / "law_originals"
WH_PHOTOS = VAULT / "_warehouse"
QDIR = DATA / "quarterly"

for _d in (DATA, OUT, UPL, VAULT, LAW_LIB, WH_PHOTOS, QDIR):
    _d.mkdir(parents=True, exist_ok=True)

_seed = BASE / "data" / "networks.json"   # նոր սկավառակի վրա առաջին գործարկման սկզբնական ցանկ
if DATA != BASE / "data" and _seed.exists() and not (DATA / "networks.json").exists():
    (DATA / "networks.json").write_bytes(_seed.read_bytes())

# Mix Media ֆիրմային գույները (նույնն է, ինչ PDF-երում՝ kp.py / mediaplan.py)
BRAND = dict(navy="#1D1B5E", violet="#6A3DE8", blue="#2E8CF0", ink="#12152E", muted="#6B7090",
             soft="#F5F3FF", tint="#EDE8FE", line="#DDE0EE")

COMPANY = dict(name="«Միքս Մեդիա» ՍՊԸ", address="ՀՀ, ք. Երևան, Լևոնյան 48",
               phone="+374 44 702 703", email="info@mix-media.am", site="mix-media.am")

APP_PASSWORD = os.getenv("APP_PASSWORD", "").strip()   # դատարկ՝ առանց մուտքի գաղտնաբառի
HOST = os.getenv("APP_HOST") or "0.0.0.0"     # լռելյայն՝ բաց է ցանցի համար (ուրիշները մտնում են http://192.168…:8000)
PORT = int(os.getenv("APP_PORT") or os.getenv("PORT") or 8000)
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "300") or 300)
MAX_UPLOAD = MAX_UPLOAD_MB * 1024 * 1024

DOC_EXT = (".docx", ".pdf", ".xlsx", ".xlsm", ".csv", ".txt", ".doc", ".pptx")
IMG_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp")
AUDIO_EXT = (".mp3", ".ogg", ".oga", ".opus", ".wav", ".m4a", ".aac", ".flac")
