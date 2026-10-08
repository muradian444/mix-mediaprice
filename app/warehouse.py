# -*- coding: utf-8 -*-
"""🏷 Պահեստ (склад)՝ ավելացնում ենք՝ ինչ է դա + նկարագրություն/որտեղ է գտնվում (օր.՝ mini PC-ն).

Ամեն միավոր՝ անուն, տեսակ, որտեղ է, քանակ, վիճակ, սերիական համար, նշումներ, նկարներ, պատմություն.
Պահվում է data/warehouse.json-ում (ատոմային գրառում, .bak պատճեն)."""
import csv
import io
import re
import time
from datetime import datetime

from config import DATA
from store import new_id, read_json, write_json, _fold, latin

FILE = DATA / "warehouse.json"

CATEGORIES = ["Mini PC", "Աուդիո սարք", "Բարձրախոս", "Ուժեղացուցիչ", "Մալուխ", "Միկրոֆոն",
              "Ցանցային սարք", "Համակարգիչ", "Պահեստամաս", "Այլ"]
STATUSES = ["պահեստում", "տեղադրված", "վերանորոգման", "պահուստ", "դուրս գրված"]
UNITS = ["հատ", "մետր", "կգ", "լիցք", "կոմպլեկտ"]


def _all():
    data = read_json(FILE, [])
    return data if isinstance(data, list) else []


def _norm(it):
    """Դաշտերի անվտանգ նորմալացում (հին/թերի գրառումները չեն կոտրում էջը)."""
    return dict(
        id=str(it.get("id") or new_id("w")),
        name=str(it.get("name") or "").strip(),
        category=str(it.get("category") or "Այլ").strip(),
        description=str(it.get("description") or "").strip(),
        location=str(it.get("location") or "").strip(),
        qty=max(0, int(it.get("qty") or 0)),
        unit=str(it.get("unit") or "հատ").strip(),
        status=str(it.get("status") or "պահեստում").strip(),
        serial=str(it.get("serial") or "").strip(),
        responsible=str(it.get("responsible") or "").strip(),
        tags=[str(t).strip() for t in (it.get("tags") or []) if str(t).strip()],
        photos=[str(p) for p in (it.get("photos") or []) if str(p)],
        created=it.get("created") or datetime.now().isoformat(timespec="seconds"),
        updated=it.get("updated") or datetime.now().isoformat(timespec="seconds"),
        history=[h for h in (it.get("history") or []) if isinstance(h, dict)][-40:],
    )


def items(q="", category="", status="", location="", sort="updated"):
    """Որոնում՝ անունով, նկարագրությամբ, տեղով, սերիականով, պիտակներով."""
    out = [_norm(i) for i in _all()]
    words = [w for w in _fold(q).split() if w]
    if words:
        lat_words = [w for w in latin(q).split() if w]

        def hay(i):
            return _fold(" ".join([i["name"], i["description"], i["location"], i["serial"],
                                   i["category"], i["responsible"], " ".join(i["tags"])]))
        out = [i for i in out if all(w in hay(i) for w in words)
               or all(w in latin(hay(i)) for w in lat_words)]
    if category:
        out = [i for i in out if i["category"] == category]
    if status:
        out = [i for i in out if i["status"] == status]
    if location:
        lf = _fold(location)
        out = [i for i in out if lf in _fold(i["location"])]
    keys = dict(updated=lambda i: i["updated"], created=lambda i: i["created"],
                name=lambda i: _fold(i["name"]), qty=lambda i: i["qty"],
                location=lambda i: _fold(i["location"]))
    out.sort(key=keys.get(sort, keys["updated"]), reverse=sort in ("updated", "created", "qty"))
    return out


def get(item_id):
    for i in _all():
        if str(i.get("id")) == str(item_id):
            return _norm(i)
    return None


def add(data, user="web"):
    name = str(data.get("name") or "").strip()
    if len(name) < 2:
        raise ValueError("Գրեք՝ ինչ է դա (առնվազն 2 նշան)")
    it = _norm(dict(data, id=new_id("w")))
    it["history"] = [dict(at=it["created"], by=user, what="ավելացվեց")]
    rows = _all()
    rows.append(it)
    write_json(FILE, rows)
    return it


def update(item_id, data, user="web"):
    rows = _all()
    for idx, raw in enumerate(rows):
        if str(raw.get("id")) != str(item_id):
            continue
        old = _norm(raw)
        merged = _norm({**old, **{k: v for k, v in (data or {}).items() if k not in ("id", "created", "history")}})
        if len(merged["name"]) < 2:
            raise ValueError("Գրեք՝ ինչ է դա (առնվազն 2 նշան)")
        changed = [k for k in ("name", "category", "description", "location", "qty", "unit",
                               "status", "serial", "responsible") if old[k] != merged[k]]
        merged["created"], merged["id"] = old["created"], old["id"]
        merged["updated"] = datetime.now().isoformat(timespec="seconds")
        merged["history"] = old["history"] + ([dict(at=merged["updated"], by=user,
                                                    what="փոփոխվեց՝ " + ", ".join(changed))] if changed else [])
        rows[idx] = merged
        write_json(FILE, rows)
        return merged
    raise ValueError("Միավորը չգտնվեց")


def delete(item_id):
    rows = _all()
    keep = [r for r in rows if str(r.get("id")) != str(item_id)]
    if len(keep) == len(rows):
        raise ValueError("Միավորը չգտնվեց")
    write_json(FILE, keep)
    return True


def add_photo(item_id, rel_path):
    it = get(item_id)
    if not it:
        raise ValueError("Միավորը չգտնվեց")
    photos = it["photos"] + [rel_path]
    return update(item_id, dict(photos=photos[:12]))


def stats():
    rows = items()
    by_cat, by_status, by_loc = {}, {}, {}
    for i in rows:
        by_cat[i["category"]] = by_cat.get(i["category"], 0) + 1
        by_status[i["status"]] = by_status.get(i["status"], 0) + 1
        if i["location"]:
            by_loc[i["location"]] = by_loc.get(i["location"], 0) + 1
    return dict(total=len(rows), units=sum(i["qty"] for i in rows), by_category=by_cat,
                by_status=by_status, locations=sorted(by_loc, key=lambda k: -by_loc[k])[:30])


def to_csv():
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\r\n")
    w.writerow(["Անվանում", "Տեսակ", "Որտեղ է", "Քանակ", "Միավոր", "Վիճակ", "Սերիական",
                "Պատասխանատու", "Նկարագրություն", "Պիտակներ", "Թարմացվել է"])
    for i in items(sort="name"):
        w.writerow([i["name"], i["category"], i["location"], i["qty"], i["unit"], i["status"],
                    i["serial"], i["responsible"], i["description"], ", ".join(i["tags"]), i["updated"]])
    return "﻿" + buf.getvalue()   # BOM՝ Excel-ը հայերենը ճիշտ բացի
