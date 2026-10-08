# -*- coding: utf-8 -*-
"""🏪 Խանութներ և գովազդային տեղեր՝ յուրաքանչյուր ցանցի/հասցեի համար քանի տեղ է զբաղված և քանիսն է ազատ.

Ցանցերն ու հասցեները վերցվում են data/networks.json-ից (store.networks), իսկ զբաղվածությունը
պահվում է data/ad_space.json-ում՝ «ցանց + հասցե» բանալիով (ինդեքսներից անկախ, որ հասցե ջնջելիս չխառնվի)."""
import re
from datetime import date, datetime
from pathlib import Path

import store
from config import ASSETS, DATA

FILE = DATA / "ad_space.json"
LOGOS = ASSETS / "logos"
LOGO_EXT = (".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif")
DEFAULT_CAPACITY = 20          # «Հասանելի է 20 ընկերության համար»
SEP = "||"

LOGOS.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------------ թաղամասեր
DISTRICTS = ["Կենտրոն", "Արաբկիր", "Աջափնյակ", "Ավան", "Դավթաշեն", "Էրեբունի", "Մալաթիա-Սեբաստիա",
             "Նոր Նորք", "Նորք-Մարաշ", "Նուբարաշեն", "Շենգավիթ", "Քանաքեռ-Զեյթուն", "Երևան", "Մարզեր"]

# Եթե հասցեում գրված է թաղամասի անունը՝ վերցնում ենք այն
_DISTRICT_WORDS = [
    ("դավթաշեն", "Դավթաշեն"), ("դավիթաշեն", "Դավթաշեն"), ("նոր նորք", "Նոր Նորք"), ("նոր-նորք", "Նոր Նորք"),
    ("նորք-մարաշ", "Նորք-Մարաշ"), ("նուբարաշեն", "Նուբարաշեն"), ("շենգավիթ", "Շենգավիթ"),
    ("էրեբունի վարչ", "Էրեբունի"), ("էրեբունու համայնք", "Էրեբունի"), ("էրեբունի տիտոգրադ", "Էրեբունի"),
    ("արաբկիր", "Արաբկիր"), ("աջափնյակ", "Աջափնյակ"), ("մալաթիա", "Մալաթիա-Սեբաստիա"),
    ("քանաքեռ-զեյթուն", "Քանաքեռ-Զեյթուն"), ("կենտրոն ", "Կենտրոն"), ("ավան,", "Ավան"), ("ավան ", "Ավան"),
]
# Հայտնի փողոցներ → թաղամաս (միայն վստահելի համընկնումներ, մնացածը՝ «Երևան», կարելի է փոխել ձեռքով)
_STREETS = [
    ("կոմիտաս", "Արաբկիր"), ("մամիկոնյանց", "Արաբկիր"), ("կիևյան", "Արաբկիր"), ("քոչար", "Արաբկիր"),
    ("գյուլբենկյան", "Արաբկիր"), ("վաղարշյան", "Արաբկիր"), ("ադոնց", "Արաբկիր"), ("փափազյան", "Արաբկիր"),
    ("մաշտոց", "Կենտրոն"), ("աբովյան", "Կենտրոն"), ("բաղրամյան", "Կենտրոն"), ("սայաթ", "Կենտրոն"),
    ("հանրապետության", "Կենտրոն"), ("զաքյան", "Կենտրոն"), ("դեմիրճյան", "Կենտրոն"), ("տպագրիչների", "Կենտրոն"),
    ("խորենացի", "Կենտրոն"), ("իսահակյան", "Կենտրոն"), ("թումանյան", "Կենտրոն"),
    ("ծարավ աղբյուր", "Ավան"), ("խուդյակով", "Ավան"), ("տաշկենտ", "Ավան"), ("առինջ", "Ավան"),
    ("բաշինջաղյան", "Աջափնյակ"), ("մարգարյան", "Աջափնյակ"), ("լենինգրադյան", "Աջափնյակ"),
    ("հալաբյան", "Աջափնյակ"), ("սիլիկյան", "Աջափնյակ"), ("նազարբեկյան", "Աջափնյակ"), ("նորաշեն", "Աջափնյակ"),
    ("անդրանիկ", "Մալաթիա-Սեբաստիա"), ("շերամ", "Մալաթիա-Սեբաստիա"), ("րաֆֆ", "Մալաթիա-Սեբաստիա"),
    ("սեբաստիա", "Մալաթիա-Սեբաստիա"),
    ("գայի", "Նոր Նորք"), ("բակունց", "Նոր Նորք"), ("մեգա մոլ", "Նոր Նորք"),
    ("բագրատունյաց", "Շենգավիթ"), ("նժդեհ", "Շենգավիթ"), ("շիրակի", "Շենգավիթ"), ("մանթաշյան", "Շենգավիթ"),
    ("խաղաղ դոնի", "Էրեբունի"), ("տիտոգրադյան", "Էրեբունի"), ("արցախի", "Էրեբունի"), ("նոր արեշ", "Էրեբունի"),
    ("էրեբունի մոլ", "Էրեբունի"), ("էրեբունի", "Էրեբունի"),
    ("լեփսիուս", "Քանաքեռ-Զեյթուն"), ("քանաքեռ", "Քանաքեռ-Զեյթուն"),
    ("սասնա ծռեր", "Դավթաշեն"),
]
_REGION_HINTS = ("մարզ", "գյումրի", "վանաձոր", "աշտարակ", "էջմիածին", "վաղարշապատ", "արտաշատ", "մասիս",
                 "կապան", "գորիս", "վեդի", "բյուրեղավան", "արմավիր", "եղվարդ", "հրազդան", "սևան", "մարտունի",
                 "արարատ,", "ակնալիճ", "քասախ", "ջրվեժ", "զովունի", "այնթապ", "հայանիստ", "նոր հաճն")


def _norm(s):
    # casefold()-ը «և»-ը դարձնում է «եւ», իսկ բանալի բառերում «և» է՝ վերադարձնում ենք
    s = str(s or "").casefold().replace("եւ", "և").replace("․", ".").replace("՝", " ")
    return re.sub(r"\s+", " ", s)


def auto_district(addr):
    """Հասցեից փորձում ենք գուշակել թաղամասը (կամ «Մարզեր»)."""
    a = _norm(addr)
    if "մարզ" in a:          # «Կոտայքի մարզ, ք․Եղվարդ, Երևանյան 1/6»՝ մարզ է, թեև «Երևան» բառ կա
        return "Մարզեր"
    if "երևան" not in a and any(h in a for h in _REGION_HINTS):
        return "Մարզեր"
    if re.search(r"ք\.\s*(?!երևան)[^\s,]", a) and "երևան" not in a:
        return "Մարզեր"
    if re.search(r"(^|\s)գ\.\s*\S", a) and "երևան" not in a:
        return "Մարզեր"
    for w, d in _DISTRICT_WORDS:
        if w in a + " ":
            return d
    for w, d in _STREETS:
        if w in a:
            return d
    return "Երևան"


def short_name(name):
    """«Երևան Սիթի սուպերմարկետների ցանց» → «Երևան Սիթի»՝ քարտերի վերնագրի համար."""
    s = re.sub(r"\s*(սուպերմարկետների ցանց|խանութների ցանց|սուպերմարկետ|մարկետ)\s*$", "", name.strip(),
               flags=re.I)
    return s.strip(" -") or name


def slug(name):
    s = store.latin(short_name(name).replace("և", "եվ"))   # «Երևան» → erevan (ոչ ere-an)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "network"


# ------------------------------------------------------------------ պահոց
def _load():
    d = store.read_json(FILE, {})
    if not isinstance(d, dict):
        d = {}
    d.setdefault("capacity", DEFAULT_CAPACITY)
    d.setdefault("networks", {})
    d.setdefault("addresses", {})
    return d


def _save(d):
    store.write_json(FILE, d)


def _key(net_name, addr):
    return f"{net_name}{SEP}{addr}"


def _today():
    return date.today().isoformat()


def _active(b, today=None):
    """Ամրագրումը զբաղեցնում է տեղը, քանի դեռ ավարտի ամսաթիվը չի անցել (կամ ավարտ չկա)."""
    end = (b.get("end") or "").strip()
    return not end or end >= (today or _today())


def _parse_day(v):
    s = str(v or "").strip()
    if not s:
        return ""
    for f in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, f).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f"Սխալ ամսաթիվ՝ {s}")


def logo_file(net_name, meta=None):
    """Ցանցի լոգոյի ֆայլի անունը assets/logos/-ում (կամ None)."""
    meta = meta if meta is not None else _load()
    f = (meta["networks"].get(net_name) or {}).get("logo")
    if f and (LOGOS / f).exists():
        return f
    base = slug(net_name)
    for ext in LOGO_EXT:
        if (LOGOS / f"{base}{ext}").exists():
            return f"{base}{ext}"
    return None


def _net_capacity(meta, net_name):
    c = (meta["networks"].get(net_name) or {}).get("capacity")
    return int(c) if c else int(meta.get("capacity") or DEFAULT_CAPACITY)


def _net_price(meta, net_name):
    p = (meta["networks"].get(net_name) or {}).get("price")
    return int(p) if p not in (None, "") else None


def _parse_price(v):
    """'' / None -> None (գին չկա կամ՝ ցանցի գինը), '25 000' -> 25000."""
    s = re.sub(r"[\s,. '֏]|դրամ|драм|amd", "", str(v if v is not None else ""), flags=re.I)
    if s == "":
        return None
    if not s.isdigit():
        raise ValueError("Գինը՝ միայն թվեր (ՀՀ դրամ) / Цена — только цифры (драм)")
    n = int(s)
    if n > 100_000_000:
        raise ValueError("Գինը շատ մեծ է / Цена слишком большая")
    return n


def _log_price(meta, by, net_name, addr, old, new):
    meta.setdefault("price_log", []).append(dict(at=datetime.now().isoformat(timespec="seconds"), by=by or "",
                                                 network=net_name, address=addr or "", old=old, new=new))
    meta["price_log"] = meta["price_log"][-500:]


def _clip(b):
    return dict(clip=b.get("clip", ""), clip_url=b.get("clip_url", ""))


# ------------------------------------------------------------------ տեսք
def overview(with_clients=True):
    meta = _load()
    today = _today()
    out = []
    for ni, n in enumerate(store.networks()):
        cap_net = _net_capacity(meta, n["name"])
        price_net = _net_price(meta, n["name"])
        rows, occ_sum, cap_sum, income = [], 0, 0, 0
        for ai, a in enumerate(n["addresses"]):
            info = meta["addresses"].get(_key(n["name"], a)) or {}
            cap = int(info.get("capacity") or cap_net)
            books = info.get("bookings") or []
            active = [b for b in books if _active(b, today) and (not b.get("start") or b["start"] <= today)]
            occ = len([b for b in books if _active(b, today)])
            occ_sum += min(occ, cap)
            cap_sum += cap
            price = info.get("price") if info.get("price") not in (None, "") else price_net
            income += (price or 0) * len(active)
            row = dict(i=ai, address=a, district=info.get("district") or auto_district(a),
                       district_manual=bool(info.get("district")), capacity=cap,
                       capacity_custom=bool(info.get("capacity")), occupied=occ, free=max(0, cap - occ),
                       price=price, price_custom=info.get("price") not in (None, ""),
                       playing=len(active), clips=[b.get("clip") for b in active if b.get("clip")])
            if with_clients:
                row["bookings"] = sorted(books, key=lambda b: (not _active(b, today), b.get("end") or "9999"))
            rows.append(row)
        logo = logo_file(n["name"], meta)
        out.append(dict(index=ni, name=n["name"], short=short_name(n["name"]), slug=slug(n["name"]),
                        logo=f"/logos/{logo}" if logo else None, capacity=cap_net,
                        price=price_net, price_note=(meta["networks"].get(n["name"]) or {}).get("price_note", ""),
                        price_updated=(meta["networks"].get(n["name"]) or {}).get("price_updated", ""),
                        income=income if with_clients else None,
                        addresses=rows, count=len(rows), slots=cap_sum, occupied=occ_sum,
                        free=max(0, cap_sum - occ_sum),
                        full=sum(1 for r in rows if r["free"] == 0)))
    return dict(capacity=int(meta.get("capacity") or DEFAULT_CAPACITY), districts=DISTRICTS, networks=out,
                today=today, currency="֏")


def _net(ni):
    nets = store.networks()
    if not 0 <= ni < len(nets):
        raise ValueError("Ցանցը չգտնվեց")
    return nets[ni]


def _addr(ni, ai):
    n = _net(ni)
    if not 0 <= ai < len(n["addresses"]):
        raise ValueError("Հասցեն չգտնվեց")
    return n, n["addresses"][ai]


# ------------------------------------------------------------------ փոփոխություններ
def set_default_capacity(value):
    v = int(value)
    if not 1 <= v <= 500:
        raise ValueError("Տեղերի քանակը՝ 1-ից 500")
    meta = _load()
    meta["capacity"] = v
    _save(meta)


def set_network(ni, capacity=None):
    n = _net(ni)
    meta = _load()
    entry = meta["networks"].setdefault(n["name"], {})
    if capacity in (None, "", 0, "0"):
        entry.pop("capacity", None)
    else:
        v = int(capacity)
        if not 1 <= v <= 500:
            raise ValueError("Տեղերի քանակը՝ 1-ից 500")
        entry["capacity"] = v
    _save(meta)


def set_logo(ni, filename, data):
    n = _net(ni)
    ext = Path(filename).suffix.lower()
    if ext not in LOGO_EXT:
        raise ValueError("Լոգոն պետք է լինի նկար՝ " + ", ".join(LOGO_EXT))
    meta = _load()
    base = slug(n["name"])
    for old in LOGOS.glob(f"{base}.*"):
        old.unlink(missing_ok=True)
    name = f"{base}{ext}"
    (LOGOS / name).write_bytes(data)
    meta["networks"].setdefault(n["name"], {})["logo"] = name
    _save(meta)
    return f"/logos/{name}"


def delete_logo(ni):
    n = _net(ni)
    meta = _load()
    f = logo_file(n["name"], meta)
    if f:
        (LOGOS / f).unlink(missing_ok=True)
    meta["networks"].setdefault(n["name"], {}).pop("logo", None)
    _save(meta)


def set_address(ni, ai, capacity=None, district=None):
    n, a = _addr(ni, ai)
    meta = _load()
    entry = meta["addresses"].setdefault(_key(n["name"], a), {})
    if capacity is not None:
        if capacity in ("", 0, "0"):
            entry.pop("capacity", None)
        else:
            v = int(capacity)
            if not 1 <= v <= 500:
                raise ValueError("Տեղերի քանակը՝ 1-ից 500")
            entry["capacity"] = v
    if district is not None:
        if district and district not in DISTRICTS:
            raise ValueError("Անհայտ թաղամաս")
        if district and district != auto_district(a):
            entry["district"] = district
        else:
            entry.pop("district", None)
    _save(meta)


def set_price(ni, price, note=None, by=""):
    """Ցանցի (խանութի) գինը՝ մեկ հասցեի համար ամսական, ՀՀ դրամ. դատարկ՝ գին չկա."""
    n = _net(ni)
    v = _parse_price(price)
    meta = _load()
    entry = meta["networks"].setdefault(n["name"], {})
    old = entry.get("price")
    if v is None:
        entry.pop("price", None)
    else:
        entry["price"] = v
    if note is not None:
        entry["price_note"] = str(note).strip()[:200]
    entry["price_updated"] = datetime.now().isoformat(timespec="minutes")
    if old != v:
        _log_price(meta, by, n["name"], "", old, v)
    _save(meta)


def set_prices(rows, by=""):
    """Մի քանի ցանցի գինը միանգամից՝ [{index, price, note}]."""
    meta = _load()
    nets = store.networks()
    changed = 0
    for r in rows or []:
        ni = int(r.get("index", -1))
        if not 0 <= ni < len(nets):
            continue
        name = nets[ni]["name"]
        v = _parse_price(r.get("price"))
        entry = meta["networks"].setdefault(name, {})
        old = entry.get("price")
        if r.get("note") is not None:
            entry["price_note"] = str(r["note"]).strip()[:200]
        if old == v:
            continue
        if v is None:
            entry.pop("price", None)
        else:
            entry["price"] = v
        entry["price_updated"] = datetime.now().isoformat(timespec="minutes")
        _log_price(meta, by, name, "", old, v)
        changed += 1
    _save(meta)
    return changed


def set_address_price(ni, ai, price, by=""):
    """Առանձին հասցեի գին (դատարկ՝ ցանցի գինը)."""
    n, a = _addr(ni, ai)
    v = _parse_price(price)
    meta = _load()
    entry = meta["addresses"].setdefault(_key(n["name"], a), {})
    old = entry.get("price")
    if v is None:
        entry.pop("price", None)
    else:
        entry["price"] = v
    if old != v:
        _log_price(meta, by, n["name"], a, old, v)
    _save(meta)


def price_log(limit=200):
    return list(reversed(_load().get("price_log", [])))[:limit]


def update_booking(ni, ai, booking_id, data):
    """Գովազդատուի ամրագրումը՝ հոլովակ, ժամկետ, նշում."""
    n, a = _addr(ni, ai)
    meta = _load()
    entry = meta["addresses"].get(_key(n["name"], a)) or {}
    b = next((x for x in entry.get("bookings") or [] if x.get("id") == booking_id), None)
    if not b:
        raise ValueError("Ամրագրումը չգտնվեց")
    if "clip" in data:
        b["clip"] = str(data.get("clip") or "").strip()[:160]
    if "clip_url" in data:
        b["clip_url"] = _clean_url(data.get("clip_url"))
    if "note" in data:
        b["note"] = str(data.get("note") or "").strip()[:200]
    if "start" in data:
        b["start"] = _parse_day(data.get("start"))
    if "end" in data:
        b["end"] = _parse_day(data.get("end"))
    if b.get("start") and b.get("end") and b["end"] < b["start"]:
        raise ValueError("Ավարտի ամսաթիվը փոքր է սկզբից")
    _save(meta)


def set_clip_all(client, clip, clip_url=None):
    """Մեկ գովազդատուի ԲՈԼՈՐ ակտիվ ամրագրումներում՝ նոր հոլովակ (օր.՝ ամսվա նոր ռոլիկ)."""
    client = str(client or "").strip().casefold()
    meta = _load()
    today = _today()
    n = 0
    for entry in meta["addresses"].values():
        for b in entry.get("bookings") or []:
            if b.get("client", "").casefold() == client and _active(b, today):
                b["clip"] = str(clip or "").strip()[:160]
                if clip_url is not None:
                    b["clip_url"] = _clean_url(clip_url)
                n += 1
    _save(meta)
    return n


def _clean_url(u):
    u = str(u or "").strip()[:500]
    if u and not re.match(r"^https?://", u, re.I):
        raise ValueError("Հղումը պետք է սկսվի http:// կամ https:// / Ссылка должна начинаться с http(s)://")
    return u


def now_playing(day=None):
    """Ինչ է հնչում հիմա՝ ցանց → հասցե → գովազդատու → հոլովակ."""
    day = _parse_day(day) if day else _today()
    meta = _load()
    rows = []
    for ni, n in enumerate(store.networks()):
        for ai, a in enumerate(n["addresses"]):
            info = meta["addresses"].get(_key(n["name"], a)) or {}
            for b in info.get("bookings") or []:
                if _active(b, day) and (not b.get("start") or b["start"] <= day):
                    rows.append(dict(net=ni, network=n["name"], short=short_name(n["name"]), addr=ai, address=a,
                                     district=info.get("district") or auto_district(a), id=b.get("id"),
                                     client=b.get("client", ""), start=b.get("start", ""), end=b.get("end", ""),
                                     note=b.get("note", ""), **_clip(b)))
    return dict(day=day, rows=rows, clients=sorted({r["client"] for r in rows}, key=str.casefold),
                no_clip=sum(1 for r in rows if not r["clip"]))


def add_booking(ni, addr_indexes, client, start="", end="", note="", clip="", clip_url=""):
    """Գովազդատուին ավելացնում է ընտրված հասցեներում. Լցված հասցեները բաց են թողնվում."""
    client = re.sub(r"\s+", " ", str(client or "")).strip()
    if len(client) < 2:
        raise ValueError("Գրեք գովազդատուի անունը")
    start, end = _parse_day(start), _parse_day(end)
    if start and end and end < start:
        raise ValueError("Ավարտի ամսաթիվը փոքր է սկզբից")
    clip, clip_url = str(clip or "").strip()[:160], _clean_url(clip_url)
    n = _net(ni)
    meta = _load()
    cap_net = _net_capacity(meta, n["name"])
    added, full, dup = [], [], []
    today = _today()
    for ai in sorted({int(x) for x in addr_indexes}):
        if not 0 <= ai < len(n["addresses"]):
            continue
        a = n["addresses"][ai]
        entry = meta["addresses"].setdefault(_key(n["name"], a), {})
        books = entry.setdefault("bookings", [])
        active = [b for b in books if _active(b, today)]
        if any(b.get("client", "").casefold() == client.casefold() for b in active):
            dup.append(a)
            continue
        if len(active) >= int(entry.get("capacity") or cap_net):
            full.append(a)
            continue
        books.append(dict(id=store.new_id("b"), client=client, start=start, end=end,
                          note=str(note or "").strip()[:200], created=today, clip=clip, clip_url=clip_url))
        added.append(a)
    _save(meta)
    store.add_client(client)
    return dict(added=len(added), full=full, duplicates=dup)


def delete_booking(ni, ai, booking_id):
    n, a = _addr(ni, ai)
    meta = _load()
    entry = meta["addresses"].get(_key(n["name"], a)) or {}
    books = entry.get("bookings") or []
    keep = [b for b in books if b.get("id") != booking_id]
    if len(keep) == len(books):
        raise ValueError("Ամրագրումը չգտնվեց")
    entry["bookings"] = keep
    _save(meta)


# ------------------------------------------------------------------ հանրային կայքի համար
def public_data():
    """GitHub Pages-ի համար՝ միայն թվեր (առանց գովազդատուների անունների)."""
    ov = overview(with_clients=False)
    nets = []
    for n in ov["networks"]:
        logo = logo_file(n["name"])
        nets.append(dict(name=n["name"], short=n["short"], slug=n["slug"],
                         logo=f"logos/{logo}" if logo else None,
                         count=n["count"], slots=n["slots"], occupied=n["occupied"], free=n["free"],
                         addresses=[dict(address=r["address"], district=r["district"], capacity=r["capacity"],
                                         occupied=min(r["occupied"], r["capacity"]), free=r["free"])
                                    for r in n["addresses"]]))
    return dict(updated=datetime.now().isoformat(timespec="minutes"), capacity=ov["capacity"],
                districts=ov["districts"], networks=nets)
