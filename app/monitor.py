# -*- coding: utf-8 -*-
"""«Տեխ. մոնիտորինգ» -> ԱԿՏ. Տվյալները վերցվում են հավելվածի ներկառուցված մոնիտորինգից (techmon.py),
Google Drive / Sheets այլևս չեն օգտագործվում:

Օրվա տվյալներում գրված են ՄԻԱՅՆ այն հասցեները, որոնք այդ օրը խնդիր են ունեցել: Եթե հասցեն օրվա մեջ չկա՝
այդ օրը ամեն ինչ աշխատել է: Այդ պատճառով «նախատեսված»-ը հաշվում ենք ԲՈԼՈՐ ընտրված հասցեներով × օրեր × ժամեր,
իսկ «չհեռարձակված»-ը՝ միայն նշված ժամերից:

Նշանները. ⚠ ПРОБЛЕМА · 📞 ЗВОНОК · 🟡 ПОДТВЕРЖДЕНО · 🔧 ремонт · 🚧 ТЕХ. ПРИЧИНА У ОБЪЕКТА -> գովազդը ՉԻ հեռարձակվել
Ժամ HH:00 սյունակը վերաբերում է HH:00–HH:59 ժամին (օր.՝ 9:20 և 9:50 սփոթները)."""
import datetime as dt
import difflib
import re
from collections import Counter, OrderedDict

import techmon

STATUS_NAMES = {"problem": "⚠ խնդիր", "call": "📞 զանգ", "confirmed": "🟡 հաստատված", "repair": "🔧 վերանորոգում",
                "object": "🚧 տեխ. պատճառ օբյեկտում"}
GENERIC = {"երևան", "մարզ", "փողոց", "խճուղի", "թաղ", "շենք", "հարկ", "տարած", "հողամաս", "հասցե", "թիվ", "yerevan", "armenia",
           "փող", "պողոտա", "միկրոշրջան", "զորավար", "շին", "սուպերմարկետ", "մարկետ", "խանութ", "մայրուղի", "մայր",
           # քաղաքներ/մարզեր՝ միայն նրանցով չենք համընկնեցնում (Գյումրի «Շիրակացի 56» ≠ Գյումրի «Հաղթանակի 56»)
           "գյումրի", "վանաձոր", "հրազդան", "մասիս", "արտաշատ", "արարատ", "վեդի", "էջմիածին", "վաղարշապատ", "արմավիր",
           "գավառ", "կապան", "սևան", "եղվարդ", "աշտարակ", "դիլիջան", "իջևան", "գորիս", "չարենցավան", "շիրակի",
           "կոտայքի", "լոռու", "արարատի", "արմավիրի", "արագածոտնի", "գեղարքունիքի", "տավուշի", "սյունիքի", "քաղաք"}
SHORT_STOP = {"տար", "շին", "թաղ", "փող", "խճ", "բն", "շենք", "հարկ", "րդ", "ին", "ուղ", "նրբ", "փակ", "մոլ", "mall"}


# ------------------------------------------------------------------ ամիսներ և տվյալներ (ներկառուցված բազայից)
def months_in(start, end):
    out, d = [], start.replace(day=1)
    while d <= end:
        out.append(f"{d:%Y-%m}")
        d = (d.replace(day=28) + dt.timedelta(4)).replace(day=1)
    return out


def months_status(start, end):
    """-> ([{month, ready, name, days, events}], None)՝ ընտրված ժամանակահատվածի ամիսների համար."""
    return techmon.months_status(start, end), None


def load_period(start, end):
    """-> (data{date: [{obj, addr, errs{hour: status}}]}, missing_months[], errors[], files[])."""
    return techmon.load_period(start, end)


def clear_cache():
    """Համատեղելիության համար (քեշ չկա՝ տվյալները միշտ թարմ են)."""


# ------------------------------------------------------------------ հասցեների համընկնում
def _fold(s):
    s = str(s or "").lower().replace("․", " ").replace("ё", "е")
    return re.sub(r"[.,:;()«»\"'\-–—/\\]", " ", s)


def _tokens(s):
    raw = str(s or "").lower().replace("․", ".")
    nums = re.findall(r"\d+(?:/\d+)?", raw)
    words = [w for w in _fold(s).split() if w]
    words += [a + b for a, b in re.findall(r"([^\W\d_]+)-([^\W\d_]+)", raw)]   # «Նար-Դոս» -> «նարդոս»
    names = [w for w in words if len(w) >= 3 and not re.search(r"\d", w) and w not in GENERIC and w not in SHORT_STOP]
    return nums, names


def _same_word(a, b):
    if a == b:
        return True
    k = min(len(a), len(b))
    if k >= 5 and a[:k - 2] == b[:k - 2]:
        return True
    return difflib.SequenceMatcher(None, a, b).ratio() >= 0.8


def net_words(net_name):
    """«Երևան Սիթի սուպերմարկետների ցանց» -> ['երևան', 'սիթի'] (օբյեկտի անվան մեջ փնտրելու համար)."""
    s = re.sub(r"\s*(սուպերմարկետների ցանց|խանութների ցանց|սուպերմարկետ|մարկետ|ցանց)\s*$", "", str(net_name or "").strip(),
               flags=re.I)
    return [w for w in _fold(s).split() if w]


def _obj_has_net(obj, words):
    """Օբյեկտի անունը սկսվում է ցանցի անունով («Երևան Սիթի - Հրազդան …», «Մաքուր Տուն Վեդի …»)."""
    o = _fold(obj).split()
    if not words or len(o) < len(words):
        return False
    return all(x == w or (len(w) >= 4 and x.startswith(w[:4])) for x, w in zip(o, words))


def _floor(s):
    """«2-րդ հարկ» -> 2 (մեկ հասցեում կարող են լինել տարբեր հարկերի սարքեր)."""
    m = re.search(r"(\d+)\s*-?\s*(?:րդ|ին|-ի)?\s*հարկ", str(s or "").lower())
    return int(m[1]) if m and int(m[1]) > 1 else None     # 1-ին հարկ = սովորական (առանց նշման)


def match_one(addr, net, keys, tok_cache=None, all_nets=None):
    """Մեկ հասցե (ցանցով) -> մոնիտորինգի բանալի (obj, addr) կամ None."""
    c = candidates(addr, net, keys, tok_cache, all_nets)
    return c[0][1] if c else None


def candidates(addr, net, keys, tok_cache=None, all_nets=None):
    """Մոնիտորինգի հնարավոր օբյեկտները՝ [(score, key)] նվազման կարգով.
    1) Եթե մոնիտորինգում կան այդ ցանցի օբյեկտներ՝ փնտրում ենք ՄԻԱՅՆ դրանց մեջ.
    2) Այլապես՝ այն օբյեկտների մեջ, որոնք ուրիշ (հայտնի) ցանցի չեն պատկանում.
    Պետք է համընկնեն տան համարը, փողոցի անունը և հարկը."""
    tok_cache = tok_cache if tok_cache is not None else {}
    tn, tw = _tokens(re.sub(r"\d+\s*-?\s*(?:րդ|ին)?\s*հարկ", " ", addr))
    floor = _floor(addr)
    words = net_words(net)
    pool = [k for k in keys if _obj_has_net(k[0], words)] if words else []
    if not pool:
        others = [w for w in (all_nets or []) if w and w != words]
        pool = [k for k in keys if not any(_obj_has_net(k[0], w) for w in others)]
    found = []
    for key in pool:
        if key not in tok_cache:
            full = key[1] + " " + key[0]
            tok_cache[key] = (_tokens(re.sub(r"\d+\s*-?\s*(?:րդ|ին)?\s*հարկ", " ", full)), _floor(full))
        (n, w), kfloor = tok_cache[key]
        if kfloor != floor:              # 2-րդ հարկի սարքը ≠ 1-ին հարկի սարք
            continue
        nbase = {y.split("/")[0] for y in n}
        exact = sum(1 for x in tn if x in n)
        base = sum(1 for x in tn if x.split("/")[0] in nbase)
        hit = sum(1 for a in tw if any(_same_word(a, b) for b in w))
        if tn and not base:              # տան համարը պետք է համընկնի
            continue
        if tw and not hit:               # փողոցի անունը պետք է համընկնի
            continue
        if not tw and (not tn or exact < len(tn)):   # միայն թվեր՝ բոլորը պետք է ճիշտ համընկնեն
            continue
        found.append((hit * 2 + exact * 3 + base, key))
    found.sort(key=lambda x: -x[0])
    return found


def assign(targets, keys, all_nets=None):
    """Բոլոր հասցեները միանգամից՝ յուրաքանչյուր մոնիտորինգի օբյեկտ տրվում է ամենալավ համընկնող ՄԵԿ հասցեի
    (օր.՝ «Այնթապ 7 փ․2» և «Այնթապ, Երևան-Մեղրի 2/6»՝ օբյեկտը ստանում է երկրորդը). -> {(net, addr): key | None}"""
    cache = {}
    pairs = []
    out = {}
    for t in targets:
        k = (t.get("net", ""), t["addr"])
        if k in out:
            continue
        out[k] = None
        for score, key in candidates(t["addr"], t.get("net", ""), keys, cache, all_nets):
            pairs.append((score, k, key))
    used = set()
    for score, k, key in sorted(pairs, key=lambda x: -x[0]):
        if out[k] is None and key not in used:
            out[k] = key
            used.add(key)
    return out


def _all_net_words():
    try:
        import store
        return [net_words(n["name"]) for n in store.networks()]
    except Exception:  # noqa
        return []


def match_addresses(targets, rows):
    """Հին API՝ targets (տողեր) -> (matched{target: key}, unmatched[])."""
    keys = list(dict.fromkeys((r["obj"], r["addr"]) for r in rows))
    matched, un = {}, []
    cache, nets = {}, _all_net_words()
    for t in targets:
        k = match_one(t, "", keys, cache, nets)
        if k:
            matched[t] = k
        else:
            un.append(t)
    return matched, un


# ------------------------------------------------------------------ հաշվարկ
def hour_order(h):
    """Եթերի ժամերի կարգը՝ գիշերային ժամերը (00–04) երեկոյից հետո."""
    return h if h >= 5 else h + 24


MIN_PER_HOUR = 2      # անջատված 1 ժամ = առնվազն 2 չհեռարձակված սփոթ (նույնիսկ եթե ժամում 1 սփոթ է)


def spots_per_hour(times):
    """['9:20', '9:50', '10:20', ...] -> Counter{ժամ: սփոթ}՝ ճիշտ այնքան, որքան մեդիա պլանում է:"""
    return Counter(int(str(t).split(":")[0]) % 24 for t in dict.fromkeys(times or []))


def _missed_alloc(per_hour, off, min_per_hour):
    """Անջատված ժամերի չհեռարձակված սփոթները՝ {ժամ: n}. Ամեն անջատված ժամ՝ max(ժամի սփոթներ, min_per_hour),
    բայց օրվա գումարը չի անցնում հասցեի օրական նախատեսվածից:"""
    left = sum(per_hour.values())
    k = max(int(min_per_hour or 0), 0)
    out = {}
    for h in off:
        n = min(max(per_hour[h], k), left)
        out[h] = n
        left -= n
    return out


def compute_targets(data, targets, times, start, end, min_per_hour=MIN_PER_HOUR):
    """targets՝ [{net, addr, slots?}] (ԱԿՏ-ի հասցեները), times՝ ['9:20', ...] (հասցեի համար, որը իր slots չունի:
    մեդիա պլանում ամեն ցանց կարող է ունենալ իր եթերացանկը).
    -> days{date:{planned,played,missed}}, by_addr{(net, addr): [planned, missed]},
       outages{(net, addr): [(date, missed, full, [ժամեր])]},
       info{matches, nodata, statuses, hours{ժամ: [planned, missed]}}.
    Հաշվարկը ԺԱՄԵՐՈՎ է. նախատեսված՝ ճիշտ մեդիա պլանի սփոթները (ըստ ժամերի), չհեռարձակված՝ անջատված ժամերի
    սփոթները (անջատված 1 ժամ = առնվազն min_per_hour սփոթ)."""
    sched = {}
    for t in targets:
        sched.setdefault((t.get("net", ""), t["addr"]), spots_per_hour(t.get("slots") or times))
    keys = list(dict.fromkeys((r["obj"], r["addr"]) for d, rows in data.items() if start <= d <= end for r in rows))
    match = assign(targets, keys, _all_net_words())
    by_day = {d: {(r["obj"], r["addr"]): r["errs"] for r in rows} for d, rows in data.items()}
    days, by_addr, outages, nodata, statuses = OrderedDict(), OrderedDict(), OrderedDict(), [], Counter()
    all_hours = {h for k in match for h in sched[k]}
    hours = OrderedDict((h, [0, 0]) for h in sorted(all_hours, key=hour_order))
    for k in match:
        by_addr[k] = [0, 0]
        outages[k] = []
    d = start
    while d <= end:
        rec = dict(planned=0, played=0, missed=0)
        rows = by_day.get(d)
        if rows is None:
            nodata.append(d)
        for k, mk in match.items():
            per_hour = sched[k]
            n_slots = sum(per_hour.values())
            off, alloc = [], {}
            if rows is not None and mk is not None and mk in rows:
                errs = {h % 24: st for h, st in rows[mk].items()}
                off = sorted((h for h in errs if per_hour.get(h)), key=hour_order)
                alloc = _missed_alloc(per_hour, off, min_per_hour)
                for h in off:
                    statuses[errs[h]] += alloc[h]
            miss = sum(alloc.values())
            for h, n in per_hour.items():
                hours[h][0] += n
                hours[h][1] += alloc.get(h, 0)
            rec["planned"] += n_slots
            rec["missed"] += miss
            by_addr[k][0] += n_slots
            by_addr[k][1] += miss
            if off:
                outages[k].append((d, miss, len(off) >= len(per_hour), off))
        rec["played"] = rec["planned"] - rec["missed"]
        days[d] = rec
        d += dt.timedelta(1)
    per_day = Counter(sum(sched[k].values()) for k in match).most_common(1)
    info = dict(matches=[dict(net=k[0], addr=k[1], obj=(v[0] if v else ""), mon_addr=(v[1] if v else ""))
                         for k, v in match.items()],
                nodata=nodata, statuses=dict(statuses), monitor_objects=len(keys), hours=hours,
                hours_per_day=len(all_hours), per_day=per_day[0][0] if per_day else 0,
                schedules=len({tuple(sorted(sched[k].items())) for k in match}))
    return days, by_addr, outages, info


def hour_ranges(hours):
    """[10, 11, 12, 15] -> '10:00–13:00, 15:00–16:00' (հաջորդական ժամերը՝ միջակայքով)."""
    hs = sorted({int(h) % 24 for h in hours}, key=hour_order)
    parts, i = [], 0
    while i < len(hs):
        j = i
        while j + 1 < len(hs) and hour_order(hs[j + 1]) - hour_order(hs[j]) == 1:
            j += 1
        parts.append(f"{hs[i]:02d}:00–{(hs[j] + 1) % 24:02d}:00")
        i = j + 1
    return ", ".join(parts)


def outages(data, keys, times, start, end):
    """Հին API (թողնված համատեղելիության համար)."""
    per_hour = Counter(int(t.split(":")[0]) for t in times)
    keyset = set(keys)
    out = {k: [] for k in keys}
    d = start
    while d <= end:
        for r in data.get(d) or []:
            k = (r["obj"], r["addr"])
            if k in keyset and r["errs"]:
                miss = min(len(times), sum(per_hour.get(h % 24, 0) for h in r["errs"]))
                if miss:
                    out[k].append((d, miss, miss >= len(times)))
        d += dt.timedelta(1)
    return out


def ranges(dates):
    """[date, ...] -> '03–05.10.2026, 12.10.2026' (հաջորդական օրերը՝ միջակայքով)."""
    dates = sorted(set(dates))
    parts, i = [], 0
    while i < len(dates):
        j = i
        while j + 1 < len(dates) and (dates[j + 1] - dates[j]).days == 1:
            j += 1
        a, b = dates[i], dates[j]
        if i == j:
            parts.append(f"{a:%d.%m.%Y}")
        elif (a.year, a.month) == (b.year, b.month):
            parts.append(f"{a:%d}–{b:%d.%m.%Y}")
        else:
            parts.append(f"{a:%d.%m.%Y}–{b:%d.%m.%Y}")
        i = j + 1
    return ", ".join(parts)
