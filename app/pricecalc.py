# -*- coding: utf-8 -*-
"""💰 Գնացուցակ և հաշվիչ (Խանութներ → Գներ)՝ ինչպես mix-media.am/price կայքում.

  որտեղ գովազդել  ->  Երևան Սիթի · Առևտրի կենտրոններ · Այլ սուպերմարկետներ (թվերը՝ ցանցերի ցուցակից)
  հեռարձակման ծառայություն  ->  փաթեթներ (Start / Mix / Premium …)՝ ամսական / տարեկան
  կանխատեսվող արդյունքներ  ->  ժամկետ (ամիս / 6 ամիս / տարի, զեղչով), հասցեներ, ստուդիայի ծառայություններ,
                               ընդհանուր եթերներ և գումար + PDF հաշվարկ

Գները, զեղչերը և ծառայությունները պահվում են data/pricelist.json-ում և փոխվում են էջից («✏️ Փոխել գները»)."""
import copy
import re
from datetime import date, datetime
from pathlib import Path

import adspace
import store
from config import DATA

FILE = DATA / "pricelist.json"
PERIODS = {"month": 1, "half": 6, "year": 12}
DAYS_IN_MONTH = 30
GROUPS = ("city", "malls", "other")


def _pkg(pid, name, icon, price, half=0, year=0, locations=1, spots=30, clip=20, popular=False, note="", note_ru=""):
    """price / half / year՝ ամսական գինը 1 հասցեի համար՝ ամսական, 6 ամսով և տարեկան պայմանագրով
    (0՝ հաշվվում է ամսականից զեղչով)."""
    return dict(id=pid, name=name, icon=icon, price=price, half=half, year=year, locations=locations, spots=spots,
                clip=clip, popular=popular, note=note, note_ru=note_ru)


# առևտրի կենտրոններ՝ ամսական գինը ըստ օրական եթերների (15 / 30)՝ ԱԱՀ-ն ներառյալ
MALL_DEFAULTS = ((r"մեգա|mega", 144000, 234000), (r"գարաժ|garage", 60000, 100000),
                 (r"էրեբունի|erebuni", 144000, 234000), (r"ռիո|rio", 144000, 234000))

DEFAULT = dict(
    groups=dict(
        city=dict(packages=[
            _pkg("regular", "Regular", "⚡", 60000, 38600, 27700, note="Ստանդարտ փաթեթ", note_ru="Стандартный пакет"),
            _pkg("top", "Top", "📶", 100000, 55700, 46150, popular=True, note="Բարձր տեսանելիություն",
                 note_ru="Высокая заметность"),
            _pkg("max", "Max", "👑", 50000, 32300, 23100, locations=0,
                 note="Ամբողջ ցանցը + 2 անվճար աուդիոձայնագրում", note_ru="Вся сеть + 2 бесплатные аудиозаписи"),
        ]),
        malls=dict(packages=[]),        # յուրաքանչյուր մոլ՝ իր գինը (mall_prices)
        other=dict(packages=[
            _pkg("start", "Start", "⚡", 7900, 0, 4900),
            _pkg("mix", "Mix", "📶", 14900, 0, 9900, popular=True),
            _pkg("premium", "Premium", "👑", 33900, 0, 19900),
        ]),
    ),
    mall_prices={},                     # {"Մեգա Մոլ": {"p15": 144000, "p30": 234000}}՝ դատարկ՝ MALL_DEFAULTS
    discounts=dict(month=0, half=10, year=20),
    studio=[dict(id="script", name="Սցենար", name_ru="Сценарий", price=40000),
            dict(id="voice", name="Ձայնագրում", name_ru="Запись голоса", price=26000)],
    spots=30, clip=20,
    phone="+374 44 702 703", whatsapp="37444702703", telegram="MixMediaArmenia",
)


# ------------------------------------------------------------------ կարգավորումներ
def _int(v, lo=0, hi=100_000_000, default=0):
    s = re.sub(r"[\s,.'֏]|դրամ|драм|amd", "", str(v if v is not None else ""), flags=re.I)
    if not s.lstrip("-").isdigit():
        return default
    return min(max(int(s), lo), hi)


def config():
    raw = store.read_json(FILE, {}) or {}
    cfg = copy.deepcopy(DEFAULT)
    if isinstance(raw, dict):
        for k in ("discounts", "spots", "clip", "phone", "whatsapp", "telegram", "studio", "mall_prices"):
            if k in raw:
                cfg[k] = raw[k] if not isinstance(cfg[k], dict) else {**cfg[k], **(raw[k] or {})}
        for g in GROUPS:
            pk = ((raw.get("groups") or {}).get(g) or {}).get("packages")
            if isinstance(pk, list):
                cfg["groups"][g]["packages"] = pk
        cfg["updated"], cfg["updated_by"] = raw.get("updated", ""), raw.get("updated_by", "")
    return cfg


def _clean_pkg(p, i):
    name = re.sub(r"\s+", " ", str(p.get("name") or "")).strip()[:40] or f"Փաթեթ {i + 1}"
    pid = re.sub(r"[^a-z0-9_-]+", "", str(p.get("id") or "").lower())[:30] or f"p{i + 1}"
    return dict(id=pid, name=name, icon=str(p.get("icon") or "⚡")[:4], price=_int(p.get("price")),
                half=_int(p.get("half")), year=_int(p.get("year")),
                locations=_int(p.get("locations"), 0, 1000, 1), spots=_int(p.get("spots"), 1, 500, 30),
                clip=_int(p.get("clip"), 1, 600, 20), popular=bool(p.get("popular")),
                note=str(p.get("note") or "").strip()[:120], note_ru=str(p.get("note_ru") or "").strip()[:120])


def save(data, by=""):
    """Պահում է գնացուցակը (ստուգումով). -> նոր config."""
    data = data if isinstance(data, dict) else {}
    cfg = config()
    groups = data.get("groups") or {}
    for g in GROUPS:
        pk = (groups.get(g) or {}).get("packages")
        if isinstance(pk, list):
            seen, out = set(), []
            for i, p in enumerate(pk[:6]):
                if isinstance(p, dict):
                    c = _clean_pkg(p, i)
                    while c["id"] in seen:
                        c["id"] += "x"
                    seen.add(c["id"])
                    out.append(c)
            cfg["groups"][g]["packages"] = out
    if isinstance(data.get("discounts"), dict):
        cfg["discounts"] = {k: _int(data["discounts"].get(k, cfg["discounts"].get(k)), 0, 90) for k in PERIODS}
    if isinstance(data.get("studio"), list):
        cfg["studio"] = [dict(id=re.sub(r"[^a-z0-9_-]+", "", str(s.get("id") or f"s{i}").lower())[:30] or f"s{i}",
                              name=str(s.get("name") or "").strip()[:60] or f"Ծառայություն {i + 1}",
                              name_ru=str(s.get("name_ru") or "").strip()[:60], price=_int(s.get("price")))
                         for i, s in enumerate(data["studio"][:8]) if isinstance(s, dict)]
    if isinstance(data.get("mall_prices"), dict):
        cfg["mall_prices"] = {re.sub(r"\s+", " ", str(k)).strip()[:120]: dict(p15=_int((v or {}).get("p15")),
                                                                            p30=_int((v or {}).get("p30")))
                              for k, v in list(data["mall_prices"].items())[:60] if str(k).strip() and isinstance(v, dict)}
    for k, lo, hi in (("spots", 1, 500), ("clip", 1, 600)):
        if k in data:
            cfg[k] = _int(data[k], lo, hi, cfg[k])
    for k in ("phone", "whatsapp", "telegram"):
        if k in data:
            cfg[k] = re.sub(r"[^\w+@ ]", "", str(data[k] or ""))[:40].strip()
    cfg["updated"] = datetime.now().isoformat(timespec="minutes")
    cfg["updated_by"] = by or ""
    store.write_json(FILE, cfg)
    return cfg


# ------------------------------------------------------------------ որտեղ գովազդել՝ խմբեր ցանցերից
def group_of(net_name):
    n = str(net_name or "").lower()          # casefold()-ը «և»-ը դարձնում է «եւ»
    if re.search(r"երևան\s*սիթի|yerevan\s*city", n):
        return "city"
    if re.search(r"մոլ|mall|առևտրի կենտրոն", n):
        return "malls"
    return "other"


def mall_price(cfg, address):
    """-> (p15, p30)՝ մոլի ամսական գինը օրական 15 / 30 եթերով."""
    own = (cfg.get("mall_prices") or {}).get(re.sub(r"\s+", " ", str(address or "")).strip()) or {}
    if own.get("p15") or own.get("p30"):
        return int(own.get("p15") or 0), int(own.get("p30") or 0)
    low = str(address or "").lower()
    return next(((p15, p30) for rx, p15, p30 in MALL_DEFAULTS if re.search(rx, low)), (0, 0))


def unit_price(cfg, pkg, period, month_price):
    """Ամսական գինը 1 հասցեի համար՝ ընտրված ժամկետով (փաթեթի հատուկ գինը կամ ամսականը՝ զեղչով)."""
    if pkg:
        own = int(pkg.get({"month": "price", "half": "half", "year": "year"}[period]) or 0)
        if own:
            return own
    return round((month_price or 0) * (100 - int(cfg["discounts"].get(period) or 0)) / 100)


def group_periods(cfg, g):
    """Ժամկետներ, որոնք ցույց են տրվում խմբի համար (ինչպես կայքում՝ Սիթի՝ 3, Start/Mix/Premium՝ ամիս/տարի)."""
    pk = cfg["groups"][g]["packages"]
    if g == "malls" and not pk:
        return ["month"]                 # մոլերի գինը՝ 30 օրվա համար
    if not pk:
        return list(PERIODS)
    return ["month"] + [p for p in ("half", "year") if any(int(x.get(p) or 0) for x in pk)]


def groups(cfg=None):
    """-> {city|malls|other: {networks: [{index, name, short, logo, price, addresses:[{i, address, price}]}],
    nets, count}}՝ խանութների ցուցակից (հասցե չունեցող ցանցերն՝ ոչ). Մոլերի հասցեներին՝ p15 / p30."""
    cfg = cfg or config()
    ov = adspace.overview(with_clients=False)
    out = {g: dict(networks=[], nets=0, count=0) for g in GROUPS}
    for n in ov["networks"]:
        if not n["count"]:
            continue
        gk = group_of(n["name"])
        g = out[gk]
        addrs = []
        for a in n["addresses"]:
            x = dict(i=a["i"], address=a["address"], price=a["price"], district=a["district"], free=a["free"])
            if gk == "malls":
                x["p15"], x["p30"] = mall_price(cfg, a["address"])
            addrs.append(x)
        g["networks"].append(dict(index=n["index"], name=n["name"], short=n["short"], logo=n["logo"],
                                  price=n["price"], capacity=n["capacity"], free=n["free"], addresses=addrs))
        g["nets"] += 1
        g["count"] += n["count"]
    return out, ov["capacity"]


def overview():
    cfg = config()
    gr, cap = groups(cfg)
    return dict(config=cfg, groups=gr, capacity=cap, periods=PERIODS, days_in_month=DAYS_IN_MONTH,
                group_periods={g: group_periods(cfg, g) for g in GROUPS})


def public(logo_prefix="/price/logos/"):
    """Հաճախորդի համար հանրային գնացուցակ (/price, docs/price.html)՝ առանց ներքին տվյալների
    (ով է փոխել, ցանցի ինդեքսներ չեն գաղտնի, բայց գովազդատուներ/եկամուտ՝ ոչ)."""
    d = overview()
    cfg = {k: v for k, v in d["config"].items() if k not in ("updated", "updated_by", "mall_prices")}
    for g in d["groups"].values():
        for n in g["networks"]:
            n["logo"] = logo_prefix + n["logo"].rsplit("/", 1)[1] if n.get("logo") else None
    return dict(d, config=cfg, updated=datetime.now().isoformat(timespec="minutes"))


# ------------------------------------------------------------------ հաշվարկ (նույնը, ինչ էջում՝ stores.js calcTotals)
def estimate(data):
    """data = {group, package, period, addresses:[{net, i, spots?}], studio:[id], brand, contact}.
    Նույն հաշվարկը, ինչ /price էջում և pricelist.js-ում."""
    cfg = config()
    data = data if isinstance(data, dict) else {}
    gr, _ = groups(cfg)
    group = data.get("group") if data.get("group") in GROUPS else "city"
    period = data.get("period") if data.get("period") in group_periods(cfg, group) else "month"
    months = PERIODS[period]
    pkg = next((p for p in cfg["groups"][group]["packages"] if p["id"] == data.get("package")), None)
    nets = {n["index"]: n for g in gr.values() for n in g["networks"]}
    rows, seen = [], set()
    for x in data.get("addresses") or []:
        try:
            ni, ai = int(x.get("net")), int(x.get("i"))
        except (TypeError, ValueError, AttributeError):
            continue
        n = nets.get(ni)
        if not n or (ni, ai) in seen:
            continue
        a = next((a for a in n["addresses"] if a["i"] == ai), None)
        if not a:
            continue
        seen.add((ni, ai))
        if "p15" in a:
            spots = 30 if str(x.get("spots")) == "30" else 15
            month = a["p30"] if spots == 30 else a["p15"]
            row_pkg = None
        else:
            spots = pkg["spots"] if pkg else cfg["spots"]
            month = pkg["price"] if pkg else (a["price"] or 0)
            row_pkg = pkg
        rows.append(dict(net=n["short"], net_name=n["name"], address=a["address"], spots=spots, month=month,
                         unit=unit_price(cfg, row_pkg, period, month), no_price=not month))
    clip = pkg["clip"] if pkg else cfg["clip"]
    subtotal = sum(r["month"] for r in rows) * months          # ամսական գնով
    broadcast = sum(r["unit"] for r in rows) * months          # ընտրված ժամկետի գնով
    discount = subtotal - broadcast
    studio = [s for s in cfg["studio"] if s["id"] in set(data.get("studio") or [])]
    studio_sum = sum(s["price"] for s in studio)
    days = months * DAYS_IN_MONTH
    airings = sum(r["spots"] for r in rows) * days
    total = broadcast + studio_sum
    return dict(group=group, package=pkg, period=period, months=months, days=days, rows=rows,
                addresses=len(rows), spots=rows[0]["spots"] if rows else (pkg or cfg)["spots"], clip=clip,
                airings=airings, subtotal=subtotal, broadcast=broadcast,
                discount_pct=round(discount * 100 / subtotal) if subtotal else 0, discount=discount,
                studio=studio, studio_sum=studio_sum, total=total, per_spot=round(broadcast / airings) if airings else 0,
                no_price=sum(1 for r in rows if r["no_price"]),
                brand=re.sub(r"\s+", " ", str(data.get("brand") or "")).strip()[:80],
                contact=re.sub(r"\s+", " ", str(data.get("contact") or "")).strip()[:80])


# ------------------------------------------------------------------ PDF
GROUP_TITLES = dict(city="Երևան Սիթի", malls="Առևտրի կենտրոններ", other="Այլ սուպերմարկետներ")
PERIOD_TITLES = dict(month="Ամսական", half="6 ամիս", year="Տարեկան")


def _m(v):
    return f"{int(v or 0):,}".replace(",", " ") + " ֏"


def make_pdf(est, out_path):
    from xml.sax.saxutils import escape
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import KeepTogether, SimpleDocTemplate, Spacer, Table, TableStyle
    import mediaplan as mp
    from mediaplan import CONTENT_W, LINE, MUTED, NAVY, SOFT, TINT, VIOLET, _GradBar, _P

    mp._fonts()
    t = lambda s, **kw: _P(escape(str(s)), **kw)   # noqa: E731
    W = colors.white
    logo = mp._logo_flowable(36 * mm)
    right = Table([[_P("«Միքս Մեդիա» ՍՊԸ", size=8.5, bold=True, align=2)],
                   [_P("ՀՀ, ք. Երևան, Լևոնյան 48", size=7.5, color=MUTED, align=2)],
                   [_P("Հեռ.՝ +374 44 702 703 · info@mix-media.am", size=7.5, color=MUTED, align=2)]],
                  colWidths=[80 * mm])
    right.setStyle(TableStyle([("TOPPADDING", (0, 0), (-1, -1), 0.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 0.5),
                               ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    top = Table([[logo, right]], colWidths=[100 * mm, 80 * mm])
    top.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                             ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    chip = Table([[_P("ԳՆԱՅԻՆ ՀԱՇՎԱՐԿ", size=6.8, bold=True, color=VIOLET, align=1)]], colWidths=[32 * mm])
    chip.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.8, VIOLET), ("ROUNDEDCORNERS", [3, 3, 3, 3]),
                              ("TOPPADDING", (0, 0), (-1, -1), 1.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    chip.hAlign = "LEFT"
    pkg = est["package"]
    strip = Table([[_P("ԲՐԵՆԴ", size=6.3, bold=True, color=MUTED), _P("ԿՈՆՏԱԿՏ", size=6.3, bold=True, color=MUTED),
                    _P("ԺԱՄԿԵՏ", size=6.3, bold=True, color=MUTED), _P("ՓԱԹԵԹ", size=6.3, bold=True, color=MUTED)],
                   [t(est["brand"] or "—", size=10.5, bold=True), t(est["contact"] or "—", size=10.5, bold=True),
                    t(f"{PERIOD_TITLES[est['period']]} · {est['months']} ամիս", size=10.5, bold=True),
                    t(pkg["name"] if pkg else "Ցանցի գնով", size=10.5, bold=True, color=VIOLET)]],
                  colWidths=[52 * mm, 48 * mm, 44 * mm, 36 * mm])
    strip.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), SOFT), ("LINEBEFORE", (0, 0), (0, -1), 2.2, VIOLET),
                               ("LINEAFTER", (0, 0), (2, -1), 0.5, colors.HexColor("#D9D2FB")),
                               ("LEFTPADDING", (0, 0), (-1, -1), 7), ("TOPPADDING", (0, 0), (-1, 0), 5),
                               ("BOTTOMPADDING", (0, -1), (-1, -1), 6), ("ROUNDEDCORNERS", [4, 4, 4, 4])]))
    story = [KeepTogether([top, Spacer(1, 4), _GradBar(CONTENT_W), Spacer(1, 7), chip, Spacer(1, 3),
                           _P(f"Կանխատեսվող արդյունքներ · {GROUP_TITLES[est['group']]}", size=15, bold=True, leading=19),
                           Spacer(1, 5), strip]),
             Spacer(1, 8),
             mp._kv([("Ընտրված հասցեներ", est["addresses"], "հասցե"),
                     ("Օրական եթերներ", est["spots"], f"սփոթ · {est['clip']} վ."),
                     ("Ընդհանուր եթերներ", f"{est['airings']:,}".replace(",", " "), "սփոթ"),
                     ("Ընդամենը (զեղչը ներառյալ)", f"{est['total']:,}".replace(",", " "), "֏")])]

    # հասցեները՝ ըստ ցանցերի
    story.append(mp._section("Ընտրված հասցեները"))
    head = [_P(h, size=7, bold=True, color=W, align=a) for h, a in
            (("N", 1), ("Հասցե", 0), ("Գին / ամիս", 2), (f"{est['months']} ամիս", 2))]
    data, st, cur, n = [head], [], None, 0
    for r in est["rows"]:
        if r["net"] != cur:
            cur = r["net"]
            i = len(data)
            data.append([t(cur, size=8, bold=True, color=VIOLET), "", "", ""])
            st += [("SPAN", (0, i), (-1, i)), ("BACKGROUND", (0, i), (-1, i), TINT)]
        n += 1
        addr = r["address"] + (f" · {r['spots']} եթեր/օր" if est["group"] == "malls" else "")
        data.append([t(n, size=7.5, align=1, color=MUTED), t(addr, size=7.5),
                     t(_m(r["unit"]) if r["unit"] else "—", size=7.5, align=2),
                     t(_m(r["unit"] * est["months"]) if r["unit"] else "—", size=7.5, bold=True, align=2)])
    if not est["rows"]:
        data.append([t("—", size=7.5, align=1), t("Հասցեներ ընտրված չեն", size=7.5, color=MUTED), "", ""])
    tbl = Table(data, colWidths=[12 * mm, 112 * mm, 26 * mm, 30 * mm], repeatRows=1)
    tbl.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), NAVY), ("LINEBELOW", (0, 1), (-1, -1), 0.4, LINE),
                             ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 2.6),
                             ("BOTTOMPADDING", (0, 0), (-1, -1), 2.6), ("ROUNDEDCORNERS", [4, 4, 0, 0])] + st))
    story.append(tbl)

    # գումարը
    story.append(mp._section("Արժեքը"))
    how = f" · փաթեթ «{pkg['name']}»" if pkg else (" · մոլի գնով" if est["group"] == "malls" else " · ցանցի գնով")
    lines = [("Հեռարձակում" + how + f" · {est['addresses']} հասցե × {est['months']} ամիս"
              + (" (ամսական գնով)" if est["discount"] else ""), _m(est["subtotal"]))]
    if est["discount"]:
        lines.append((f"Զեղչ՝ {est['discount_pct']}% ({PERIOD_TITLES[est['period']].lower()} պայմանագիր)",
                      "− " + _m(est["discount"])))
    for s in est["studio"]:
        lines.append((f"Ստուդիա՝ {s['name']}", "+ " + _m(s["price"])))
    rows = [[t(a, size=8.5), t(b, size=8.5, bold=True, align=2)] for a, b in lines]
    rows.append([_P("ԸՆԴԱՄԵՆԸ (ԶԵՂՉԸ ՆԵՐԱՌՅԱԼ)", size=9.5, bold=True, color=W),
                 _P(_m(est["total"]), size=11, bold=True, color=W, align=2)])
    ct = Table(rows, colWidths=[130 * mm, 50 * mm])
    last = len(rows) - 1
    ct.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, last - 1), 0.4, LINE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                            ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                            ("BACKGROUND", (0, last), (-1, last), VIOLET), ("ROUNDEDCORNERS", [4, 4, 4, 4])]))
    story.append(KeepTogether([ct]))
    notes = [f"Եթերներ՝ {est['addresses']} հասցե × {est['spots']} սփոթ օրական × {est['days']} օր:"
             if len({r["spots"] for r in est["rows"]}) <= 1 else
             f"Ընդհանուր եթերներ՝ {est['airings']:,} ({est['days']} օր):".replace(",", " "),
             *([f"1 եթերի արժեքը՝ {_m(est['per_spot'])}:"] if est["per_spot"] else []),
             f"Հաշվարկը կազմված է {date.today():%d.%m.%Y}-ին և տեղեկատվական է. վերջնական գինը՝ պայմանագրով:"]
    if est["no_price"]:
        notes.insert(0, f"{est['no_price']} հասցեի գինը նշված չէ (հաշվված է 0):")
    story += [Spacer(1, 6)] + [_P(x, size=7, color=MUTED) for x in notes]
    doc = SimpleDocTemplate(str(out_path), pagesize=A4, leftMargin=15 * mm - 6, rightMargin=15 * mm - 6,
                            topMargin=12 * mm - 6, bottomMargin=15 * mm - 6, title=f"Mix Media — {est['brand'] or 'հաշվարկ'}")
    doc.build(story, onFirstPage=mp._on_page, onLaterPages=mp._on_page)
    return Path(out_path)
