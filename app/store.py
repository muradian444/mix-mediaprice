# -*- coding: utf-8 -*-
"""JSON պահոց՝ հաճախորդներ, ցանցեր/հասցեներ, կարգավորումներ (ատոմային գրառում, պահուստ .bak)."""
import json
import os
import re
import shutil
import tempfile
import threading
import time
import unicodedata
from pathlib import Path

from config import DATA

_LOCK = threading.RLock()

CLIENTS = DATA / "clients.json"
NETS = DATA / "networks.json"
SETTINGS = DATA / "app_settings.json"

DEFAULT_SETTINGS = dict(lang="hy", theme="light", planned_per_day=0, drive_link="",
                        mp3_folder="", act_times="9:20-23:50/30", monitor_folder="")


# ------------------------------------------------------------------ հիմք
def read_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except Exception:  # վնասված ֆայլ՝ չենք ընկնում, վերցնում ենք լռելյայնը
        bad = Path(path).with_suffix(".broken.json")
        try:
            shutil.copy(path, bad)
        except Exception:
            pass
        return default


def write_json(path, data):
    """Ատոմային գրառում՝ ֆայլը երբեք կես չի մնում. Առաջին անգամ՝ .bak պատճեն."""
    path = Path(path)
    with _LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        bak = path.with_suffix(path.suffix + ".bak")
        if path.exists() and not bak.exists():
            try:
                shutil.copy(path, bak)
            except Exception:
                pass
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, path)
        finally:
            Path(tmp).unlink(missing_ok=True)
    return data


def new_id(prefix=""):
    return f"{prefix}{int(time.time() * 1000):x}{os.urandom(2).hex()}"


def safe_name(s, limit=60, default="file"):
    """Ֆայլի անվան համար՝ առանց վտանգավոր նշանների (հայերենը պահպանվում է)."""
    s = unicodedata.normalize("NFC", str(s or "")).strip()
    s = s.replace("/", "-").replace("\\", "-")
    s = re.sub(r'[\x00-\x1f<>:"|?*]+', "", s)
    s = re.sub(r"\s+", " ", s).strip(" .")
    s = s[:limit].strip(" .")
    return s or default


# ------------------------------------------------------------------ կարգավորումներ
def settings():
    return {**DEFAULT_SETTINGS, **read_json(SETTINGS, {})}


def save_settings(patch):
    s = settings()
    s.update({k: v for k, v in (patch or {}).items() if k in DEFAULT_SETTINGS})
    write_json(SETTINGS, s)
    return s


# ------------------------------------------------------------------ հաճախորդներ
def clients():
    raw = read_json(CLIENTS, [])
    out = []
    for c in raw if isinstance(raw, list) else []:
        name = (c if isinstance(c, str) else c.get("name", "")).strip()
        if name and name not in out:
            out.append(name)
    return out


def add_client(name):
    name = (name or "").strip()
    if not name:
        return clients()
    cl = [c for c in clients() if c.casefold() != name.casefold()]
    cl.insert(0, name)
    write_json(CLIENTS, cl[:60])
    return cl[:60]


def delete_client(name):
    cl = [c for c in clients() if c != name]
    write_json(CLIENTS, cl)
    return cl


# ------------------------------------------------------------------ ցանցեր և հասցեներ
def networks():
    raw = read_json(NETS, [])
    out = []
    for n in raw if isinstance(raw, list) else []:
        if not isinstance(n, dict):
            continue
        out.append(dict(name=str(n.get("name", "")).strip() or "Ցանց",
                        addresses=[str(a).strip() for a in (n.get("addresses") or []) if str(a).strip()]))
    return out


def save_networks(nets):
    write_json(NETS, nets)
    return nets


def add_network(name):
    nets = networks()
    name = (name or "").strip()
    if not name:
        raise ValueError("Ցանցի անունը դատարկ է")
    if any(n["name"].casefold() == name.casefold() for n in nets):
        raise ValueError("Այդ անունով ցանց արդեն կա")
    nets.append(dict(name=name, addresses=[]))
    save_networks(nets)
    return nets


def add_addresses(net_index, lines):
    """Ավելացնում է հասցեներ՝ կրկնվողները բաց թողնելով. -> (ցանցեր, ավելացվածների ինդեքսները)."""
    nets = networks()
    if not 0 <= net_index < len(nets):
        raise ValueError("Ցանցը չգտնվեց")
    have = {a.casefold() for a in nets[net_index]["addresses"]}
    added = []
    for raw in lines:
        a = re.sub(r"\s+", " ", str(raw or "")).strip()
        if a and a.casefold() not in have:
            have.add(a.casefold())
            nets[net_index]["addresses"].append(a)
            added.append(len(nets[net_index]["addresses"]) - 1)
    save_networks(nets)
    return nets, added


def delete_address(net_index, addr_index):
    nets = networks()
    if not 0 <= net_index < len(nets):
        raise ValueError("Ցանցը չգտնվեց")
    addrs = nets[net_index]["addresses"]
    if not 0 <= addr_index < len(addrs):
        raise ValueError("Հասցեն չգտնվեց")
    addrs.pop(addr_index)
    save_networks(nets)
    return nets


def _fold(s):
    """Որոնման նորմալացում՝ ռեգիստր, հայկական/լատինական կետադրություն, կրկնակի բացատ."""
    s = unicodedata.normalize("NFKC", str(s or "")).casefold()
    s = re.sub(r"[․.,:;«»\"'()\-–—/]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


TRANSLIT = {"ու": "u", "և": "ev", "ա": "a", "բ": "b", "գ": "g", "դ": "d", "ե": "e", "զ": "z", "է": "e",
            "ը": "y", "թ": "t", "ժ": "zh", "ի": "i", "լ": "l", "խ": "kh", "ծ": "ts", "կ": "k", "հ": "h",
            "ձ": "dz", "ղ": "gh", "ճ": "ch", "մ": "m", "յ": "y", "ն": "n", "շ": "sh", "ո": "o", "չ": "ch",
            "պ": "p", "ջ": "j", "ռ": "r", "ս": "s", "վ": "v", "տ": "t", "ր": "r", "ց": "ts", "փ": "p",
            "ք": "k", "օ": "o", "ֆ": "f"}


def latin(s):
    """Հայերենը՝ լատինատառ (որ «komitas»-ով էլ գտնվի «Կոմիտաս»)."""
    s = _fold(s).replace("ու", "u")
    return "".join(TRANSLIT.get(ch, ch) for ch in s)


def search_addresses(query, net_indexes=None, limit=400):
    """Հասցեների որոնում բոլոր ցանցերում՝ ըստ բառերի (ցանցի անունով և լատինատառ էլ է գտնում)."""
    nets = networks()
    words = [w for w in _fold(query).split() if w]
    if not words:
        return []
    lat_words = [w for w in latin(query).split() if w]
    out = []
    for ni, n in enumerate(nets):
        if net_indexes and ni not in net_indexes:
            continue
        nname = _fold(n["name"])
        for ai, a in enumerate(n["addresses"]):
            hay = _fold(a) + " " + nname
            if all(w in hay for w in words) or all(w in latin(hay) for w in lat_words):
                out.append(dict(net=ni, addr=ai, net_name=n["name"], address=a))
                if len(out) >= limit:
                    return out
    return out
