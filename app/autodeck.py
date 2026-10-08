# -*- coding: utf-8 -*-
"""✨ Ավտո-պրեզենտացիա (NotebookLM-ի նման) / Автосборка квартального отчёта из текста + фото.

Մարդը գրում է՝ ինչ է արվել 3 ամսում (ազատ տեքստ), ավելացնում է լուսանկարներ.
Համակարգը ինքն է՝
  1. բաժանում տեքստը բաժինների (ամիսներ, վերնագրեր, պարբերություններ) -> սլայդներ
  2. գտնում թվերը («120 հասցե», «45 000 выходов», «98%») -> «Թվեր» սլայդ, ամիսներով՝ գծապատկեր
  3. գտնում ապագա պլանները -> «Պլաններ» սլայդ
  4. ԻՆՔՆ Է ԸՆՏՐՈՒՄ ՆԿԱՐԸ յուրաքանչյուր սլայդի համար՝ նկարի ստորագրությունից, ֆայլի անունից,
     նկարահանման ամսաթվից (EXIF), նկարի վրայի տեքստից (OCR) և՝ եթե կա՝ տեղային ԻԻ-ի նկարագրությունից
  5. չօգտագործված նկարները՝ «Ֆոտոշարք» սլայդներ
Ամեն ինչ՝ տեղային (առանց ամպի և բանալիների). Ollama-ն (եթե կա) բարելավում է կառուցվածքը:"""
import base64
import io
import json
import logging
import re
from datetime import date

import localai

log = logging.getLogger("mixmedia")

MONTHS_RX = [
    (1, r"հունվար|январ|january|\bjan\b"), (2, r"փետրվար|феврал|february|\bfeb\b"), (3, r"մարտ|март|march"),
    (4, r"ապրիլ|апрел|april"), (5, r"մայիս|ма[йя]\b|\bmay\b"), (6, r"հունիս|июн|june"), (7, r"հուլիս|июл|july"),
    (8, r"օգոստոս|август|august"), (9, r"սեպտեմբեր|сентябр|september"), (10, r"հոկտեմբեր|октябр|october"),
    (11, r"նոյեմբեր|ноябр|november"), (12, r"դեկտեմբեր|декабр|december"),
]
MONTH_NAMES = {
    "hy": ["Հունվար", "Փետրվար", "Մարտ", "Ապրիլ", "Մայիս", "Հունիս", "Հուլիս", "Օգոստոս", "Սեպտեմբեր",
           "Հոկտեմբեր", "Նոյեմբեր", "Դեկտեմբեր"],
    "ru": ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь",
           "Ноябрь", "Декабрь"],
}
T = {
    "hy": dict(metrics="Հիմնական թվերը", chart="Դինամիկա ըստ ամիսների", plans="Հաջորդ եռամսյակի պլանները",
               results="Արդյունքներ", gallery="Ֆոտոշարք", summary="Ամփոփում", thanks="Շնորհակալություն",
               work="Կատարված աշխատանքներ"),
    "ru": dict(metrics="Ключевые цифры", chart="Динамика по месяцам", plans="Планы на следующий квартал",
               results="Результаты", gallery="Фотоотчёт", summary="Итоги", thanks="Спасибо",
               work="Проделанная работа"),
}
PLAN_RX = re.compile(r"պլան|նախատես|հաջորդ\s+եռամսյակ|կանենք|план|планиру|следующ\w*\s+квартал|будем|next\s+quarter|"
                     r"we\s+plan|goal", re.I)
SUMMARY_RX = re.compile(r"ամփոփ|ընդհանուր|արդյունքում|итог|в\s+итоге|всего|summary|in\s+total", re.I)
UNITS = [  # (regex, hy, ru)
    (r"հասցե\w*|адрес\w*|address\w*", "Հասցեներ", "Адресов"),
    (r"խանութ\w*|магазин\w*|shops?|stores?", "Խանութներ", "Магазинов"),
    (r"սփոթ\w*|հեռարձակ\w*|выход\w*|спот\w*|broadcast\w*|spots?", "Հեռարձակումներ", "Выходов"),
    (r"հաճախորդ\w*|գովազդատու\w*|клиент\w*|рекламодател\w*|clients?|advertisers?", "Հաճախորդներ", "Клиентов"),
    (r"հոլովակ\w*|ռոլիկ\w*|ролик\w*|clips?|videos?", "Հոլովակներ", "Роликов"),
    (r"օբյեկտ\w*|կետ\w*|точ\w*|объект\w*|points?|objects?", "Օբյեկտներ", "Точек"),
    (r"ցանց\w*|сет\w*|networks?", "Ցանցեր", "Сетей"),
    (r"պայմանագ\w*|договор\w*|contracts?", "Պայմանագրեր", "Договоров"),
    (r"սարք\w*|оборудован\w*|устройств\w*|devices?|players?", "Սարքեր", "Устройств"),
    (r"դրամ|драм|֏|amd", "Գումար, ֏", "Сумма, ֏"),
]
STOP = set("""և ու որ էր են է եմ ենք էին այս այդ այն մեր մենք նաև ինչպես համար հետ վրա մեջ իսկ բայց կամ
the and for with that this from were was have has our also into than then
и в во на с со по к ко из за от до для что как это мы наш наши также был была были было или но а же
""".split())


# ================================================================== օգնականներ
def lang_of(text):
    hy = len(re.findall(r"[Ա-Ֆա-ֆ]", text))
    ru = len(re.findall(r"[А-Яа-яЁё]", text))
    return "hy" if hy >= ru else "ru"


def _fold(s):
    return str(s or "").casefold().replace("եւ", "և")


def stems(text):
    """Բառերի «արմատներ» (առաջին 5 տառը)՝ հայերեն/ռուսերեն հոլովները համընկնեն («Կոմիտասի» ~ «Կոմիտաս»)."""
    out = set()
    for w in re.findall(r"[0-9A-Za-zА-Яа-яЁёԱ-Ֆա-ֆև]{3,}", _fold(text)):
        if w in STOP or w.isdigit():
            continue
        out.add(w[:5] if len(w) > 5 else w)
    return out


def month_of(text):
    t = _fold(text)
    for n, rx in MONTHS_RX:
        if re.search(rx, t):
            return n
    return 0


def _clean(s):
    return re.sub(r"\s+", " ", str(s or "")).strip(" -–—•*·:;")


def _sentences(text):
    parts = re.split(r"(?<=[.!?։])\s+|\n+", text)
    return [_clean(p) for p in parts if len(_clean(p)) > 2]


def _title_from(text, maxw=7):
    words = _clean(text).split()
    t = " ".join(words[:maxw])
    return t + ("…" if len(words) > maxw else "")


# ================================================================== տեքստ -> բաժիններ
def split_sections(prompt):
    """-> [{title, lines:[...], month}] — վերնագրերով, ամիսներով կամ պարբերություններով."""
    lines = [ln.rstrip() for ln in str(prompt or "").replace("\r", "").split("\n")]
    sections, cur = [], None

    def new(title, month=0):
        s = dict(title=_clean(title), lines=[], month=month)
        sections.append(s)
        return s

    for raw in lines:
        ln = raw.strip()
        if not ln:
            cur = None if cur and cur["lines"] else cur
            continue
        is_list = bool(re.match(r"^([-•*–—]|\d{1,2}[.)])\s+", ln))
        # «Պլաններ՝ …», «Итоги: …» տողը՝ նոր բաժին (նույնիսկ առանց դատարկ տողի)
        lab = re.match(r"^([^:։՝]{2,50})[:։՝]\s*(\S.*?)[:։.]?$", ln)
        if lab and not is_list and (PLAN_RX.search(lab.group(1)) or SUMMARY_RX.search(lab.group(1))) \
                and not month_of(lab.group(1)):
            cur = new(lab.group(1), 0)
            cur["lines"].append(lab.group(2))
            continue
        # վերնագիր՝ «## …» կամ կարճ տող «…:» (առանց թվերի և ստորակետների, ոչ թե նախադասություն)
        short = len(ln.split()) <= 6 and not re.search(r"\d|,", ln) and not re.search(r"[:։՝]\s*\S", ln)
        head = re.match(r"^#+\s*(.+)$", ln) or (None if is_list or not short else re.match(r"^(.{2,60})[:։՝]\s*$", ln))
        m = month_of(ln[:40])
        head_month = m and len(ln) < 70 and short and (ln.endswith((":", "։", "՝")) or len(ln.split()) <= 3)
        if head or head_month:
            title = head.group(1) if head else ln.rstrip(":։՝ ")
            cur = new(title, m)
            continue
        if PLAN_RX.match(ln) and cur is not None and cur["month"]:
            cur = new("", 0)
        # «Հոկտեմբերին …» պարբերություն՝ նոր բաժին այդ ամսով
        lead_m = month_of(" ".join(ln.split()[:3]))
        if lead_m:
            ln = re.sub(r"^[A-Za-zА-Яа-яЁёԱ-Ֆա-ֆև]+\s*[:։՝\-–—]\s*", "", ln) if month_of(ln.split()[0]) else ln
        if lead_m and not is_list and (cur is None or (cur["month"] and cur["month"] != lead_m) or not cur["month"]):
            cur = new("", lead_m)
        if cur is None:
            cur = new("", 0)
        cur["lines"].append(re.sub(r"^([-•*–—]|\d{1,2}[.)])\s+", "", ln) if is_list else ln)
        cur.setdefault("list", False)
        cur["list"] = cur["list"] or is_list
    return [s for s in sections if s["lines"] or s["title"]]


def find_metrics(text, lang):
    """«120 հասցե», «45 000 выходов», «98%» -> [{label, value, note}] (առանց կրկնությունների)."""
    found = {}          # label -> [(is_total, value, note, pos)]
    order = []
    t = _norm_spaces(text)
    for m in re.finditer(r"(\d{1,3}(?:[  .,]\d{3})+(?![\d])|\d+(?:[.,]\d+)?)\s*(%?)", t):
        num, pct = m.group(1), m.group(2)
        ctx = t[max(0, m.start() - 30):m.start()]
        total = bool(SUMMARY_RX.search(ctx))
        if pct:
            before = re.findall(r"[A-Za-zА-Яа-яЁёԱ-Ֆա-ֆև]+", t[max(0, m.start() - 40):m.start()])
            label = (" ".join(before[-2:]) or ("Կատարում" if lang == "hy" else "Выполнение"))[:40]
            label = label[:1].upper() + label[1:]
            found.setdefault(label, []).append((total, f"{num}%", "", m.start()))
            if label not in order:
                order.append(label)
            continue
        # միավորը՝ թվից հետո 1–3 բառի մեջ («15 նոր խանութ», «8 новых клиентов»)
        after = re.findall(r"[A-Za-zА-Яа-яЁёԱ-Ֆա-ֆև֏]+", t[m.end():m.end() + 40])[:3]
        for word in after:
            hit = next(((hy, ru) for rx, hy, ru in UNITS if re.fullmatch(rx, _fold(word))), None)
            if hit:
                label = hit[0] if lang == "hy" else hit[1]
                found.setdefault(label, []).append((total, _fmt_num(num), word, m.start()))
                if label not in order:
                    order.append(label)
                break
    out = []
    for label in order:
        rows = found[label]
        # «ընդամենը / всего / итого» թիվը, հակառակ դեպքում՝ ամենամեծը
        best = next((r for r in rows if r[0]), None) or max(rows, key=lambda r: _as_float(r[1]))
        out.append(dict(label=label, value=best[1], note=best[2]))
    return out[:8]


def _as_float(v):
    try:
        return float(re.sub(r"[^\d.]", "", str(v).replace(",", ".")) or 0)
    except ValueError:
        return 0.0


def _norm_spaces(s):
    return str(s or "").replace(" ", " ")


def _fmt_num(s):
    d = re.sub(r"[  ]", "", s)
    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", d):
        d = re.sub(r"[.,]", "", d)
    if d.isdigit() and len(d) > 3:
        return f"{int(d):,}".replace(",", " ")
    return d


def month_chart(sections, lang):
    """Եթե տարբեր ամիսներում նույն միավորով թիվ կա (օր.՝ հեռարձակումներ) -> գծապատկեր."""
    by_unit = {}
    for s in sections:
        if not s["month"]:
            continue
        for mt in find_metrics(" ".join(s["lines"]), lang):
            if "%" in mt["value"]:
                continue
            by_unit.setdefault(mt["label"], {})[s["month"]] = mt["value"]
    best = max(by_unit.items(), key=lambda kv: len(kv[1]), default=None)
    if not best or len(best[1]) < 2:
        return None
    unit, vals = best
    items = [dict(label=MONTH_NAMES[lang][m - 1], value=v.replace(" ", ""), note="") for m, v in sorted(vals.items())]
    return dict(type="chart", title=f"{T[lang]['chart']} · {unit}", items=items, unit=unit)


# ================================================================== նկարներ
def describe_photo(path, att, use_ai=True):
    """Նկարի «նկարագրություն» ընտրության համար՝ ստորագրություն + ֆայլի անուն + ամիս (EXIF) + OCR + ԻԻ."""
    desc = dict(caption=att.get("caption", ""), name=re.sub(r"[_\-.]+|\d{3,}", " ", att.get("name", "")).strip(),
                month=0, ocr="", ai=att.get("ai", ""))
    try:
        from PIL import Image
        im = Image.open(path)
        exif = im.getexif()
        raw = exif.get(36867) or exif.get(306) or (exif.get_ifd(0x8769) or {}).get(36867)   # DateTimeOriginal / DateTime
        if raw:
            desc["month"] = int(str(raw)[5:7])
    except Exception:  # noqa
        pass
    if not att.get("ocr_done"):
        try:
            import ocr
            if ocr.status()["ready"]:
                txt = ocr.image_text(path.read_bytes(), psm=11)
                desc["ocr"] = " ".join(w for w in re.findall(r"[A-Za-zА-Яа-яЁёԱ-Ֆա-ֆև]{4,}", txt))[:300]
        except Exception:  # noqa — OCR-ը միայն օգնում է, պարտադիր չէ
            pass
    else:
        desc["ocr"] = att.get("ocr", "")
    if use_ai and not desc["ai"] and localai.status()["ready"]:
        desc["ai"] = _ai_caption(path)
    return desc


def _ai_caption(path):
    """Ollama (gemma3 և այլ vision մոդելներ)՝ կարճ նկարագրություն բանալի բառերով."""
    try:
        from PIL import Image, ImageOps
        im = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
        im.thumbnail((768, 768))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=80)
        body = dict(model=localai.model(), stream=False, options=dict(temperature=0),
                    messages=[dict(role="user", images=[base64.b64encode(buf.getvalue()).decode()],
                                   content="Describe this photo in one short sentence in Russian and give 6 keywords "
                                           "(objects, place, shop name if visible). Plain text.")])
        import urllib.request
        req = urllib.request.Request(localai.url() + "/api/chat", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as r:
            return (json.loads(r.read().decode()).get("message") or {}).get("content", "")[:400]
    except Exception as e:  # noqa
        log.info("photo caption skipped: %s", e)
        return ""


def _photo_stems(desc):
    return stems(" ".join([desc["caption"], desc["caption"], desc["name"], desc["ocr"], desc["ai"]]))


def assign_photos(slides, photos):
    """Ամեն սլայդին՝ ամենահամապատասխան նկարը (յուրաքանչյուր նկար՝ մեկ անգամ). -> չօգտագործվածները."""
    pst = {p["path"]: _photo_stems(p["desc"]) for p in photos}
    used = set()
    cands = []
    for si, s in enumerate(slides):
        if s["type"] not in ("text", "bullets"):
            continue
        st = stems(" ".join([s.get("title", ""), s.get("body", ""), " ".join(s.get("items") or []),
                             " ".join(s.get("keywords") or [])]))
        for p in photos:
            score = 3 * len(st & pst[p["path"]])
            if s.get("month") and p["desc"]["month"] == s["month"]:
                score += 2
            if score:
                cands.append((score, si, p["path"]))
    taken_slide = set()
    for score, si, path in sorted(cands, reverse=True):
        if si in taken_slide or path in used:
            continue
        taken_slide.add(si)
        used.add(path)
        _with_photo(slides[si], path, photos)
    # «անխոս» նկարները (առանց ստորագրության, տեքստի, նկարագրության)՝ բովանդակային սլայդներին առանց նկարի.
    # Իսկ նկարագրված, բայց չհամընկնողները՝ «Ֆոտոշարք» (որ նկարը չդրվի անտեղի)
    free = [p for p in photos if p["path"] not in used and not pst[p["path"]]]
    empty = [i for i, s in enumerate(slides) if s["type"] in ("text", "bullets") and i not in taken_slide
             and not s.get("no_photo")]
    for si in empty:
        if not free:
            break
        p = free.pop(0)
        used.add(p["path"])
        _with_photo(slides[si], p["path"], photos)
    return [p for p in photos if p["path"] not in used]


def _with_photo(s, path, photos):
    p = next(x for x in photos if x["path"] == path)
    s["type"] = "photo_text"
    s["image"] = path
    s["caption"] = p["desc"]["caption"] or ""


# ================================================================== կառուցում (կանոններ)
def build_rules(prompt, lang, deck):
    secs = split_sections(prompt)
    slides = []
    metrics = find_metrics(prompt, lang)
    if metrics:
        slides.append(dict(type="metrics", title=T[lang]["metrics"], items=metrics[:8]))
    chart = month_chart(secs, lang)
    if chart:
        slides.append(chart)
    plans, summary = [], []
    for s in secs:
        if not s["lines"]:          # վերնագիր առանց բովանդակության
            continue
        text = " ".join(s["lines"])
        title = s["title"] or (MONTH_NAMES[lang][s["month"] - 1] if s["month"] else "")
        if PLAN_RX.search(title + " " + text[:60]) and not s["month"]:
            plans += s["lines"] if s.get("list") else _sentences(text)
            continue
        if SUMMARY_RX.search(title) and not s["month"]:
            summary += s["lines"] if s.get("list") else _sentences(text)
            continue
        items = s["lines"] if s.get("list") else _sentences(text)
        if not title:
            title = _title_from(items[0] if items else text, 6) if len(secs) > 1 else T[lang]["work"]
        if len(items) >= 2 or s.get("list"):
            for k in range(0, len(items), 6):        # երկար ցուցակ՝ մի քանի սլայդ
                slides.append(dict(type="bullets", title=title if not k else f"{title} ({k // 6 + 1})",
                                   items=items[k:k + 6], month=s["month"]))
        else:
            slides.append(dict(type="text", title=title, body=text, month=s["month"]))
    if summary:
        slides.append(dict(type="bullets", title=T[lang]["summary"], items=summary[:8], no_photo=True))
    if plans:
        slides.append(dict(type="bullets", title=T[lang]["plans"], items=plans[:8], no_photo=True))
    return slides


# ================================================================== կառուցում (տեղային ԻԻ)
AI_SCHEMA = {"type": "object", "properties": {
    "slides": {"type": "array", "items": {"type": "object", "properties": {
        "type": {"type": "string", "enum": ["text", "bullets", "metrics", "chart"]},
        "title": {"type": "string"}, "body": {"type": "string"},
        "items": {"type": "array", "items": {"type": "string"}},
        "metrics": {"type": "array", "items": {"type": "object", "properties": {
            "label": {"type": "string"}, "value": {"type": "string"}, "note": {"type": "string"}},
            "required": ["label", "value"]}},
        "month": {"type": "integer"},
        "keywords": {"type": "array", "items": {"type": "string"}}},
        "required": ["type", "title"]}}},
    "required": ["slides"]}


def build_ai(prompt, lang, deck, photos):
    """Ollama-ն կազմում է սլայդների կառուցվածքը. ցանկացած սխալի դեպքում՝ None (կօգտագործվեն կանոնները)."""
    import urllib.request
    language = "Armenian" if lang == "hy" else "Russian"
    pics = "\n".join(f"- photo {i + 1}: {p['desc']['caption'] or ''} {p['desc']['ai'] or p['desc']['name']}"
                     for i, p in enumerate(photos)) or "(no photos)"
    ask = (f"Make a quarterly report presentation (6–12 slides) for Mix Media (in-store audio advertising) "
           f"from the employee's notes below. Write ALL slide text in {language}. Use only facts from the notes, "
           f"never invent numbers. Slide types: 'metrics' (key numbers: label, value, note), 'chart' (same unit by "
           f"month: metrics with label=month name, value=number), 'bullets' (3–6 short items), 'text' (short "
           f"paragraph). Order: key numbers, work by month/topic, results, plans for next quarter. Set 'month' "
           f"(1–12) when a slide is about one month, and 'keywords' (3–6 words) to match photos.\n"
           f"Client: {deck.get('client') or '-'}; quarter {deck.get('quarter')} {deck.get('year')}.\n"
           f"Photos available:\n{pics}\n\nNotes:\n<<<\n{prompt[:12000]}\n>>>")
    body = dict(model=localai.model(), stream=False, format=AI_SCHEMA, options=dict(temperature=0.2, num_ctx=8192),
                messages=[dict(role="user", content=ask)])
    try:
        req = urllib.request.Request(localai.url() + "/api/chat", data=json.dumps(body).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=300) as r:
            data = json.loads((json.loads(r.read().decode()).get("message") or {}).get("content") or "{}")
    except Exception as e:  # noqa
        log.warning("autodeck AI failed, rules used: %s", e)
        return None
    out = []
    for s in data.get("slides") or []:
        t = s.get("type")
        sl = dict(type=t, title=_clean(s.get("title"))[:120], month=int(s.get("month") or 0),
                  keywords=[str(k) for k in (s.get("keywords") or [])][:8])
        if t in ("metrics", "chart"):
            sl["items"] = [dict(label=_clean(m.get("label"))[:40], value=_clean(m.get("value"))[:20],
                                note=_clean(m.get("note"))[:30]) for m in (s.get("metrics") or []) if m.get("label")][:12]
            if not sl["items"]:
                continue
        elif t == "bullets":
            sl["items"] = [_clean(x)[:200] for x in (s.get("items") or []) if _clean(x)][:8]
            if not sl["items"]:
                continue
        else:
            sl["type"] = "text"
            sl["body"] = str(s.get("body") or "").strip()[:1200]
            if not sl["body"]:
                continue
        out.append(sl)
    return out or None


# ================================================================== գլխավոր
def build(deck, prompt, photos, use_ai=True, lang=None):
    """deck՝ quarterly-ի տվյալները, photos՝ [{path, abs, att}] -> (slides, info)."""
    prompt = str(prompt or "").strip()
    if len(prompt) < 20:
        raise ValueError("Գրեք ավելի մանրամասն, ինչ է արվել եռամսյակում / Опишите подробнее, что сделано за квартал")
    lang = lang or lang_of(prompt)
    ai_ready = use_ai and localai.status()["ready"]
    for p in photos:
        p["desc"] = describe_photo(p["abs"], p["att"], ai_ready)
    body = build_ai(prompt, lang, deck, photos) if ai_ready else None
    engine = "ollama" if body else "rules"
    if not body:
        body = build_rules(prompt, lang, deck)
    left = assign_photos(body, photos)
    q_names = {1: "I", 2: "II", 3: "III", 4: "IV"}
    sub = f"{deck.get('client') or ''}".strip() or (f"{q_names.get(deck.get('quarter'), '')} "
                                                     f"{'եռամսյակ' if lang == 'hy' else 'квартал'} {deck.get('year')}")
    slides = [dict(type="cover", title=deck.get("title") or "", subtitle=sub)] + body
    for k in range(0, len(left), 6):
        slides.append(dict(type="gallery", title=T[lang]["gallery"] + (f" ({k // 6 + 1})" if len(left) > 6 else ""),
                           images=[dict(path=p["path"], caption=p["desc"]["caption"]) for p in left[k:k + 6]]))
    slides.append(dict(type="closing", title=T[lang]["thanks"], body=""))
    for s in slides:
        for k in ("keywords", "month", "no_photo"):
            s.pop(k, None)
    info = dict(engine=engine, lang=lang, slides=len(slides), photos=len(photos),
                matched=len(photos) - len(left), gallery=len(left),
                photo_meta={p["path"]: dict(ocr=p["desc"]["ocr"], ai=p["desc"]["ai"], ocr_done=True) for p in photos})
    return slides, info


def today_quarter():
    return (date.today().month - 1) // 3 + 1
