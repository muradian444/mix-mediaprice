# -*- coding: utf-8 -*-
"""🧾 ԱԿՏ-ի տվյալների շերտ՝ ֆայլ/Drive/տեխ. մոնիտորինգ -> օրերի թվեր -> Word/PDF.

(Բոտի extras.py-ի տրամաբանությունը, ուղղված սխալներով և web-ի համար JSON տեսքով.)"""
import re
from collections import OrderedDict
from datetime import date, datetime
from pathlib import Path

import act
import monitor
import store
from config import OUT

SOURCES = ("file", "monitor")


def _pct(played, planned):
    return round(100 * played / planned, 1) if planned else None


def days_json(days):
    return [dict(date=d.isoformat(), label=f"{d:%d.%m.%Y}", planned=v["planned"], played=v["played"],
                 missed=max(v["planned"] - v["played"], v["missed"]), pct=_pct(v["played"], v["planned"]))
            for d, v in days.items()]


def days_from_json(rows):
    """Frontend-ից վերադարձած օրերը՝ նորից OrderedDict (ստուգումով)."""
    days = OrderedDict()
    for r in rows or []:
        try:
            d = datetime.fromisoformat(str(r["date"])).date() if "T" in str(r["date"]) else date.fromisoformat(str(r["date"]))
        except (KeyError, ValueError, TypeError):
            continue
        planned = max(0, int(r.get("planned") or 0))
        played = max(0, min(int(r.get("played") or 0), planned if planned else 10 ** 9))
        days[d] = dict(planned=planned, played=played, missed=max(0, planned - played))
    if not days:
        raise ValueError("Օրերի տվյալները դատարկ են")
    return days


def off_detail(off_list):
    """[{date: 'ՕՕ.ԱԱ.ՏՏՏՏ', hours: [10, 11], full}] -> '03.10.2026՝ 10:00–12:00; 05.10.2026՝ ամբողջ օրը (15 ժ)'."""
    parts = []
    for r in off_list or []:
        hrs = r.get("hours") or []
        txt = "ամբողջ օրը" if r.get("full") else monitor.hour_ranges(hrs)
        parts.append(f"{r.get('date', '')}՝ {txt} ({len(hrs)} ժ)")
    return "; ".join(parts)


def _off_info(rows):
    """[(date, missed, full, hours)] -> ամփոփ դաշտեր՝ ԱԿՏ-ի «անջատված ԺԱՄԵՐ» սյունակի համար."""
    rows = rows or []
    off_list = [dict(date=f"{r[0]:%d.%m.%Y}", hours=list(r[3]) if len(r) > 3 else [], full=bool(r[2]),
                     missed=r[1]) for r in rows]
    return dict(off_days=len(rows), full_days=sum(1 for r in rows if r[2]),
                off_hours=sum(len(x["hours"]) for x in off_list),
                off_dates=monitor.ranges([r[0] for r in rows]),
                full_dates=monitor.ranges([r[0] for r in rows if r[2]]),
                off_list=off_list, off_detail=off_detail(off_list))


def hours_json(hours):
    """{ժամ: [planned, missed_or_played]} -> [{hour, label, planned, played, missed, pct}]."""
    out = []
    for h, (planned, missed) in hours.items():
        played = max(planned - missed, 0)
        out.append(dict(hour=int(h), label=f"{int(h):02d}:00–{(int(h) + 1) % 24:02d}:00", planned=planned,
                        played=played, missed=missed, pct=_pct(played, planned)))
    return out


def hours_from_json(rows):
    out = []
    for r in rows or []:
        try:
            h = int(r.get("hour"))
            planned = max(0, int(r.get("planned") or 0))
            played = max(0, min(int(r.get("played") or 0), planned if planned else 10 ** 9))
        except (TypeError, ValueError, AttributeError):
            continue
        try:
            missed = max(0, int(r.get("missed")))
        except (TypeError, ValueError):
            missed = planned - played
        out.append(dict(hour=h % 24, label=f"{h % 24:02d}:00–{(h + 1) % 24:02d}:00", planned=planned,
                        played=played, missed=max(missed, planned - played)))
    return out


def summary(days, clips=None, by_addr=None, extra=None, outages=None, hours=None):
    planned, played, missed = act.totals(days)
    zero = [f"{d:%d.%m.%Y}" for d, v in days.items() if not v["played"] and not v["planned"]]
    outages = outages or {}
    rows = [dict(obj=k[0] if isinstance(k, tuple) else str(k), addr=k[1] if isinstance(k, tuple) else str(k),
                 planned=v[0], played=v[0] - v[1], missed=v[1], **_off_info(outages.get(k)))
            for k, v in (by_addr or {}).items()]
    return dict(planned=planned, played=played, missed=missed, pct=_pct(played, planned),
                days=days_json(days), empty_days=zero, hours=hours_json(hours or {}),
                off_hours=sum(r["off_hours"] for r in rows),
                clips=[dict(name=k, played=v) for k, v in (clips or {}).items()],
                by_addr=rows, **(extra or {}))


# ------------------------------------------------------------------ 1) ֆայլ / Drive
def from_files(paths, start, end, planned_per_day=0, hours_out=None):
    """Մի քանի ֆայլ՝ գումարվում են օրերով (և ժամերով, եթե ֆայլում ժամ կա). -> (days, clips, errors).
    hours_out՝ {ժամ: [planned, missed]}."""
    days_all, clips_all = None, {}
    errors = []
    raw_hours = {}
    for p in paths:
        try:
            rows = act.read_rows(p)
            days, clips = act.aggregate(rows, start, end, planned_per_day or None, hours_out=raw_hours)
        except Exception as e:  # noqa — մեկ ֆայլի սխալը չի կոտրում մնացածը
            errors.append(f"{Path(p).name}՝ {e}")
            continue
        if days_all is None:
            days_all = days
        else:
            for d, v in days.items():
                for k in v:
                    days_all[d][k] += v[k]
        for k, v in clips.items():
            clips_all[k] = clips_all.get(k, 0) + v
    if days_all is None:
        raise ValueError("Ոչ մի ֆայլ չհաջողվեց կարդալ: " + (" | ".join(errors) if errors else ""))
    if hours_out is not None:
        for h in sorted(raw_hours, key=monitor.hour_order):
            planned, played = raw_hours[h]
            hours_out[h] = [planned, max(planned - played, 0)]
    return days_all, clips_all, errors


# ------------------------------------------------------------------ 2) տեխ. մոնիտորինգ
def _iso_day(v):
    try:
        return date.fromisoformat(str(v or "").strip()[:10])
    except ValueError:
        return None


def clip_to_plan(start, end, plan_start=None, plan_end=None):
    """ԱԿՏ-ի ժամանակահատվածը՝ մեդիա պլանի ժամանակահատվածի մեջ (պլանից դուրս օրերին գովազդ նախատեսված չէ).
    -> (start, end)"""
    ps, pe = _iso_day(plan_start), _iso_day(plan_end)
    s = max(start, ps) if ps else start
    e = min(end, pe) if pe else end
    if e < s:
        raise ValueError(f"ԱԿՏ-ի ժամանակահատվածը ({start:%d.%m.%Y} – {end:%d.%m.%Y}) չի համընկնում մեդիա պլանի "
                         f"ժամանակահատվածի հետ ({ps:%d.%m.%Y} – {pe:%d.%m.%Y})" if ps and pe else
                         "ԱԿՏ-ի ժամանակահատվածը չի համընկնում մեդիա պլանի ժամանակահատվածի հետ")
    return s, e


def monitor_months(start, end):
    """-> {months: [{month, ready, name, days, events}]}՝ ներկառուցված տեխ. մոնիտորինգի տվյալներով."""
    rows, _ = monitor.months_status(start, end)
    return dict(months=rows)


def monitor_addresses(start, end):
    """Մոնիտորինգում հանդիպող օբյեկտները (ժամանակահատվածի բոլոր օրերից)."""
    data, missing, errors, _ = monitor.load_period(start, end)
    keys = list(dict.fromkeys((r["obj"], r["addr"]) for d, rows in data.items() if start <= d <= end for r in rows))
    if not keys:
        raise ValueError("Ընտրված ժամանակահատվածում տեխ. մոնիտորինգի տվյալներ չկան"
                         + (f". {' | '.join(errors)}" if errors else ""))
    return [dict(obj=k[0], addr=k[1]) for k in keys], missing, errors


def _flat_addr(s):
    return re.sub(r"[\s.,;:·․\-–—«»\"'()/\\]+", "", str(s or "").lower())


def act_targets(addr_mode="all", targets=None, net_indexes=None):
    """ԱԿՏ-ի հասցեները՝ [{net, addr}].
    all՝ բոլոր ցանցերի բոլոր հասցեները, net՝ ընտրված ցանցերը, txt/plan՝ ցուցակ (տող կամ {net, addr}).
    Եթե ցանցը նշված չէ՝ փնտրում ենք հասցեն Կարգավորումների ցանցերում (որ համընկնումը ճիշտ լինի)."""
    nets = store.networks()
    if addr_mode == "all":
        return [dict(net=n["name"], addr=a) for n in nets for a in n["addresses"]]
    if addr_mode == "net":
        out = [dict(net=nets[i]["name"], addr=a) for i in (net_indexes or [])
               if isinstance(i, int) and 0 <= i < len(nets) for a in nets[i]["addresses"]]
        if not out:
            raise ValueError("Ընտրեք ցանցը")
        return out
    where = {}
    for n in nets:
        for a in n["addresses"]:
            where.setdefault(_flat_addr(a), n["name"])
    out = []
    for t in targets or []:
        slots = []
        if isinstance(t, dict):
            addr, net = str(t.get("addr") or "").strip(), str(t.get("net") or "").strip()
            slots = [str(s).strip() for s in (t.get("slots") or []) if re.fullmatch(r"\d{1,2}:\d{2}", str(s).strip())
                     and int(str(s).split(":")[0]) < 24]
        else:
            addr, net = str(t or "").strip(), ""
        if not addr:
            continue
        if not net or not monitor.net_words(net):
            net = where.get(_flat_addr(addr), net)
        out.append(dict(net=net, addr=addr, **({"slots": slots} if slots else {})))
    if not out:
        raise ValueError("Հասցեների ցանկը դատարկ է")
    return out


def from_monitor(start, end, times, addr_mode="all", targets=None, net_indexes=None,
                 min_per_hour=monitor.MIN_PER_HOUR):
    """Ճիշտ հաշվարկ. նախատեսված = ԲՈԼՈՐ հասցեներ × օրեր × ժամեր, չհեռարձակված = միայն մոնիտորինգում նշված ժամերը
    (⚠ 📞 🟡 🔧 🚧): Օրվա թերթում չգրված հասցեն այդ օրը աշխատել է. Եթերի 1 ժամը՝ առնվազն min_per_hour սփոթ."""
    T = act_targets(addr_mode, targets, net_indexes)
    if not times and not all(t.get("slots") for t in T):
        raise ValueError("Ընտրեք եթերացանկը (ժամերը)")
    data, missing, errors, files = monitor.load_period(start, end)
    in_period = [d for d in data if start <= d <= end]
    if not in_period:
        raise ValueError("Ընտրված ժամանակահատվածի տեխ. մոնիտորինգի տվյալները չկան"
                         + (f". {' | '.join(errors)}" if errors else
                            ". Բացեք «Տեխ. մոնիտորինգ» մենյուն և ներմուծեք հին ֆայլերը կամ միացրեք նամակների ընթերցումը"))
    days, by_addr, outages, info = monitor.compute_targets(data, T, times, start, end, min_per_hour)
    matched = [m for m in info["matches"] if m["obj"]]
    today = date.today()
    extra = dict(addresses=len(by_addr), per_day=info.get("per_day", len(times)), min_per_hour=min_per_hour,
                 future=[f"{d:%d.%m.%Y}" for d in days if d > today],
                 nodata=[f"{d:%d.%m.%Y}" for d in info["nodata"]], missing_months=missing, warnings=errors,
                 files=files, match=dict(matched=len(matched), total=len(by_addr)),
                 unmatched=[m["addr"] for m in info["matches"] if not m["obj"]][:300],
                 matches=info["matches"],
                 statuses=[dict(code=k, name=monitor.STATUS_NAMES.get(k, k), spots=v)
                           for k, v in sorted(info["statuses"].items(), key=lambda x: -x[1])],
                 off_total_days=len({r[0] for rows in outages.values() for r in rows}),
                 off_addresses=sum(1 for rows in outages.values() if rows),
                 hours_per_day=info.get("hours_per_day", 0), schedules=info.get("schedules", 1))
    return days, by_addr, extra, outages, info.get("hours") or {}


# ------------------------------------------------------------------ խանութի լոգո (PDF-ի վերևում աջից)
def _flat(s):
    return re.sub(r"[\s.,;:·\-–—«»\"'()/\\]+", "", str(s or "").lower())


def logo_networks():
    """Ցանցերը, որոնց լոգոն կա՝ [{index, name, short, logo}] (ԱԿՏ-ի ընտրացանկի համար)."""
    import adspace
    return [dict(index=n["index"], name=n["name"], short=n["short"], logo=n["logo"])
            for n in adspace.overview(False)["networks"] if n["logo"]]


def guess_network(client="", addresses=(), net_indexes=()):
    """Ո՞ր ցանցի/խանութի համար է ԱԿՏ-ը. -> ցանցի ինդեքս կամ None.
    Կարգը՝ 1) միակ ընտրված ցանց  2) հասցեների համընկնում  3) պատվիրատուի անունը ցանցի անվան մեջ."""
    import adspace
    nets = store.networks()
    picked = [i for i in (net_indexes or []) if isinstance(i, int) and 0 <= i < len(nets)]
    if len(picked) == 1:
        return picked[0]
    flat_addr = [f for f in (_flat(a) for a in addresses or []) if f]
    best, best_hits = None, 0
    if flat_addr:
        for i, n in enumerate(nets):
            have = {_flat(a) for a in n["addresses"]}
            hits = sum(1 for f in flat_addr if f in have)
            if hits > best_hits:
                best, best_hits = i, hits
    if best is not None:
        return best
    c = _flat(client)
    if len(c) >= 3:
        for i, n in enumerate(nets):
            sh = _flat(adspace.short_name(n["name"]))
            if len(sh) >= 3 and (sh in c or c in sh):
                return i
    return None


def logo_path(net_index):
    """Ցանցի լոգոյի ֆայլը (Path) կամ None."""
    import adspace
    nets = store.networks()
    try:
        name = nets[int(net_index)]["name"]
    except (TypeError, ValueError, IndexError):
        return None
    f = adspace.logo_file(name)
    return adspace.LOGOS / f if f else None


# ------------------------------------------------------------------ 3) փաստաթուղթ
def _int(v):
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return 0


def _off_list(row):
    out = []
    for r in row.get("off_list") or []:
        if not isinstance(r, dict):
            continue
        hrs = []
        for h in r.get("hours") or []:
            try:
                hrs.append(int(h) % 24)
            except (TypeError, ValueError):
                continue
        out.append(dict(date=str(r.get("date") or ""), hours=hrs, full=bool(r.get("full")), missed=_int(r.get("missed"))))
    return out


def make(client, contract, start, end, days, clips=None, by_addr=None, logo_net=None, seal=True, hours=None):
    """-> (docx path, pdf path | None). logo_net՝ ցանցի ինդեքս (խանութի լոգո PDF-ում), seal՝ ստորագրություն+կնիք,
    hours՝ [{hour, planned, played}] (հաշվարկը ըստ ժամերի)."""
    if not str(client or "").strip():
        raise ValueError("Լրացրեք հաճախորդի անունը")
    by = []
    for row in by_addr or []:
        if not isinstance(row, dict):
            continue
        ol = _off_list(row)
        by.append(dict(obj=str(row.get("obj") or ""), addr=str(row.get("addr") or ""),
                       planned=_int(row.get("planned")), missed=_int(row.get("missed")),
                       off_days=_int(row.get("off_days")), full_days=_int(row.get("full_days")),
                       off_hours=sum(len(x["hours"]) for x in ol) if ol else _int(row.get("off_hours")),
                       off_list=ol, off_detail=off_detail(ol) if ol else str(row.get("off_detail") or ""),
                       off_dates=str(row.get("off_dates") or ""), full_dates=str(row.get("full_dates") or "")))
    client, contract = str(client).strip(), str(contract or "—").strip()
    clips = {c["name"]: c["played"] for c in (clips or []) if isinstance(c, dict) and "name" in c} \
        if isinstance(clips, list) else (clips or {})
    hrs = hours_from_json(hours)
    docx_path = act.make_act(client, contract, start, end, days, clips, OUT, by_addr=by, hours=hrs)
    import actpdf
    pdf = actpdf.make_pdf(client, contract, start, end, days, clips, by, docx_path.with_suffix(".pdf"),
                          logo=logo_path(logo_net) if logo_net not in (None, "") else None, seal=bool(seal),
                          hours=hrs)
    return docx_path, pdf
