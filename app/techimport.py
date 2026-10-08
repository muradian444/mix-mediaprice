# -*- coding: utf-8 -*-
"""📥 Հին մոնիտորինգի ֆայլերի ՄԵԿ անգամյա ներմուծում (Google Sheets «… Тех мониторинг» -> տեղական բազա).

Աղբյուրը՝ կամ վերբեռնված .xlsx ֆայլեր, կամ հանրային Google Drive թղթապանակ (միայն ներմուծման համար):
Ներմուծվածից հետո Drive-ի կարիք չկա: Տեղական արդեն դրված նշումները չեն վերագրվում (INSERT OR IGNORE)."""
import datetime as dt
import re
import tempfile
import threading
from pathlib import Path

import openpyxl

import techmon as tm
from techmon import AUTO_MARK, STATUS_LIST, clean, db, kv_set, log, norm_status

DAY_SHEET = re.compile(r"\s*(\d{2})\.(\d{2})\.(\d{4})\s*$")
_STATE = dict(running=False, done=0, total=0, current="", log=[], error="", finished=False)
_STATE_LOCK = threading.Lock()


def state():
    with _STATE_LOCK:
        return dict(_STATE, log=list(_STATE["log"]))


def _set(**kw):
    with _STATE_LOCK:
        _STATE.update(kw)


def _say(msg):
    with _STATE_LOCK:
        _STATE["log"].append(msg)
        del _STATE["log"][:-60]


def _hour(v):
    if isinstance(v, dt.datetime):
        v = v.time()
    if isinstance(v, dt.timedelta):
        return 24 if v.total_seconds() % 86400 == 0 else int(v.total_seconds() // 3600)
    if isinstance(v, dt.time):
        return 24 if (v.hour == 0 and v.minute == 0) else v.hour
    if isinstance(v, (int, float)) and 0 <= v < 1.0001:
        h = round(v * 24)
        return 24 if h == 0 else h
    m = re.match(r"^\s*(\d{1,2}):(\d{2})", str(v or ""))
    if m:
        h = int(m[1])
        return 24 if h == 0 else h
    return None


def _note_meta(note):
    user, ts = "", ""
    m = re.search(r"Пользователь:\s*(.+)", note or "")
    if m:
        user = m.group(1).strip()
    m = re.search(r"(?:Дата изменения|Дата обнаружения):\s*(\d{2})\.(\d{2})\.(\d{4})[ ,]+(\d{2}):(\d{2})", note or "")
    if m:
        ts = f"{m[3]}-{m[2]}-{m[1]}T{m[4]}:{m[5]}:00+04:00"
    return user, ts


def import_workbook(path, label=""):
    """Մեկ .xlsx -> բազա. -> dict(days, cells, new, sheets)."""
    wb = openpyxl.load_workbook(path, data_only=True)
    days, cells, new = set(), 0, 0
    with db() as con:
        for ws in wb.worksheets:
            m = DAY_SHEET.match(ws.title)
            if not m:
                continue
            day = dt.date(int(m[3]), int(m[2]), int(m[1]))
            hours = {c.column: _hour(c.value) for c in ws[1] if c.column >= 3 and _hour(c.value) is not None}
            if not hours:
                continue
            days.add(day)
            for r in ws.iter_rows(min_row=2):
                obj, addr = clean(r[0].value), clean(r[1].value if len(r) > 1 else "")
                if not obj or not addr:
                    continue
                for c in r:
                    h = hours.get(c.column)
                    st = norm_status(c.value) if h else ""
                    if not st:
                        continue
                    note = c.comment.text if c.comment else ""
                    user, ts = _note_meta(note)
                    before = con.total_changes
                    con.execute("INSERT OR IGNORE INTO cells(day,obj,addr,hour,status,auto,note,user,ts) "
                                "VALUES(?,?,?,?,?,?,?,?,?)",
                                (f"{day:%Y-%m-%d}", obj, addr, h, st, 1 if AUTO_MARK in note else 0, note, user, ts))
                    cells += 1
                    if con.total_changes > before:
                        new += 1
                        tm._touch_object(con, obj, addr, f"{day:%Y-%m-%d}")
        # «ծածկված» օրեր. առաջին թերթից մինչև ամսվա վերջը (թերթը ստեղծվում էր միայն խնդրի դեպքում, ուրեմն
        # միջանկյալ բացերը՝ «խնդիր չի եղել»); ընթացիկ ամսվա համար՝ մինչև վերջին թերթը
        today = tm.now().date()
        by_month = {}
        for d in days:
            by_month.setdefault((d.year, d.month), []).append(d)
        for (y, mo), ds in by_month.items():
            first = dt.date(y, mo, 1)
            last_of_month = (first.replace(day=28) + dt.timedelta(4)).replace(day=1) - dt.timedelta(1)
            end = last_of_month if last_of_month < today.replace(day=1) else max(ds)
            d = min(ds)
            while d <= min(end, today):
                tm.mark_covered(con, d, "import")
                d += dt.timedelta(1)
        log("INFO", f"📥 Import {label or Path(str(path)).name}: дней={len(days)}, ячеек={cells}, новых={new}", con)
    return dict(days=len(days), cells=cells, new=new)


def import_files(paths):
    total = dict(files=0, days=0, cells=0, new=0, errors=[])
    for p in paths:
        try:
            r = import_workbook(p, Path(str(p)).name)
            total["files"] += 1
            for k in ("days", "cells", "new"):
                total[k] += r[k]
        except Exception as e:  # noqa — վնասված ֆայլը չի կանգնեցնում մնացածը
            total["errors"].append(f"{Path(str(p)).name}: {type(e).__name__}: {e}")
    return total


# ------------------------------------------------------------------ հանրային Google Drive թղթապանակ (միայն ներմուծման համար)
def _run_drive(link):
    import monitor_drive
    try:
        _set(running=True, finished=False, error="", done=0, total=0, current="", log=[])
        files = [f for f in monitor_drive.list_folder(link)
                 if f["kind"] == "sheet" and "log" not in f["name"].lower()]
        _set(total=len(files))
        _say(f"Файлов в папке: {len(files)}")
        stats = dict(days=0, cells=0, new=0)
        tmp = Path(tempfile.mkdtemp(prefix="tmimp_"))
        for i, f in enumerate(files, 1):
            _set(current=f["name"] or f["id"])
            try:
                p = monitor_drive.download_sheet(f["id"], tmp / f"{f['id']}.xlsx")
                r = import_workbook(p, f["name"])
                for k in stats:
                    stats[k] += r[k]
                _say(f"✓ {f['name']}: дней {r['days']}, записей {r['new']}")
            except Exception as e:  # noqa
                _say(f"✗ {f['name']}: {type(e).__name__}: {e}")
            _set(done=i)
        _say(f"Готово: дней {stats['days']}, новых записей {stats['new']}")
        kv_set("drive_import_done", tm.now_text())
    except Exception as e:  # noqa
        _set(error=f"{type(e).__name__}: {e}")
        _say(f"✗ {e}")
    finally:
        _set(running=False, finished=True)


def start_drive_import(link):
    if state()["running"]:
        raise ValueError("Импорт уже идёт")
    threading.Thread(target=_run_drive, args=(link,), name="techmon-import", daemon=True).start()
