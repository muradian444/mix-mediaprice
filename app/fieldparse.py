# -*- coding: utf-8 -*-
"""🧩 Տեքստ -> ձևի դաշտեր (կանոններով, առանց ինտերնետի) / Текст -> поля формы по правилам.

OCR-ի տեքստից գտնում է ՀՎՀՀ, հաշվեհամար, բանկ, տնօրեն, ընկերություն, հասցե, ամսաթվեր, գումարներ…
Հայերեն, ռուսերեն և անգլերեն պիտակներով: «Միքս Մեդիա»-ի սեփական ռեկվիզիտները (հին պայմանագրում)
բաց են թողնվում՝ վերցվում են հաճախորդինը:"""
import re

# ------------------------------------------------------------------ բառարաններ
OWN_NAMES = ("միքս մեդիա", "mix media", "mix-media", "микс медиа", "միքս-մեդիա")
OWN_VALUES = ("mix-media.am", "702703", "702 703", "լևոնյան 48", "левонян 48")
LEGAL_WORDS = r"ՍՊԸ|ՓԲԸ|ԲԲԸ|ԱՁ|ՀԿ|ՊՈԱԿ|ООО|ОАО|ЗАО|ПАО|АО|ИП|LLC|CJSC|OJSC|LTD|Ltd|Inc|SPY|SPE"
LETTER = r"A-Za-zА-Яа-яЁёԱ-Ֆա-ֆևԵ"
LEGAL = r"(?<![" + LETTER + r"])(?:" + LEGAL_WORDS + r")(?![" + LETTER + r"])"
MONTHS = {
    1: ("հունվար", "январ", "jan"), 2: ("փետրվար", "феврал", "feb"), 3: ("մարտ", "март", "mar"),
    4: ("ապրիլ", "апрел", "apr"), 5: ("մայիս", "ма", "may"), 6: ("հունիս", "июн", "jun"),
    7: ("հուլիս", "июл", "jul"), 8: ("օգոստոս", "август", "aug"), 9: ("սեպտեմբեր", "сентябр", "sep"),
    10: ("հոկտեմբեր", "октябр", "oct"), 11: ("նոյեմբեր", "ноябр", "nov"), 12: ("դեկտեմբեր", "декабр", "dec"),
}
BANKS = [  # (որոնման ձևեր, արդյունք)
    (("ամերիա", "америа", "ameria"), "Ամերիաբանկ ՓԲԸ"),
    (("ակբա", "акба", "acba"), "ԱԿԲԱ բանկ ԲԲԸ"),
    (("արդշին", "ардшин", "ardshin"), "Արդշինբանկ ՓԲԸ"),
    (("ինեկո", "инеко", "ineco"), "Ինեկոբանկ ՓԲԸ"),
    (("էվոկա", "эвока", "evoca"), "Էվոկաբանկ ՓԲԸ"),
    (("կոնվերս", "конверс", "converse"), "Կոնվերս Բանկ ՓԲԸ"),
    (("յունիբանկ", "юнибанк", "unibank"), "Յունիբանկ ՓԲԸ"),
    (("հայէկոնոմ", "հայէկոնոմբանկ", "армэконом", "armeconom"), "Հայէկոնոմբանկ ԲԲԸ"),
    (("արարատբանկ", "араратбанк", "araratbank", "ararat bank"), "Արարատբանկ ԲԲԸ"),
    (("արմսվիս", "армсвис", "armswiss"), "ԱրմՍվիսԲանկ ՓԲԸ"),
    (("բիբլոս", "библос", "byblos"), "Բիբլոս Բանկ Արմենիա ՓԲԸ"),
    (("hsbc",), "ԷՅՉ-ԷՍ-ԲԻ-ՍԻ Բանկ Հայաստան ՓԲԸ"),
    (("վտբ", "втб", "vtb"), "ՎՏԲ-Հայաստան Բանկ ՓԲԸ"),
    (("ֆասթ", "фаст банк", "fast bank", "fastbank"), "Ֆասթ Բանկ ՓԲԸ"),
    (("այդի բանկ", "айди банк", "idbank", "id bank"), "ԱյԴի Բանկ ՓԲԸ"),
    (("արցախբանկ", "арцахбанк", "artsakhbank"), "Արցախբանկ ՓԲԸ"),
    (("մելլաթ", "меллат", "mellat"), "Մելլաթ Բանկ ՓԲԸ"),
    (("հայբիզնես", "армбизнес", "armbusiness", "armenian business bank"), "Հայբիզնեսբանկ ՓԲԸ"),
]
ADDR_MARK = re.compile(
    r"(փող|պող|խճուղ|նրբ|թաղ|շենք|տուն|մ/շ|հարկ|\bք\s*\.|\bգ\s*\.|ул\.?|улиц|просп|пр-т|пер\.|шоссе|\bг\s*\.|"
    r"дом|\bд\.|street|\bst\.|avenue|\bave\b|\bstr\b|\bblvd)", re.I)
FIELD_SEP = r"\s*[:՝։\-–—=]?\s*"

LABELS = {   # կանոնի տեսակ -> պիտակներ
    "tin": [r"ՀՎՀՀ", r"Հ\s*\.?\s*Վ\s*\.?\s*Հ\s*\.?\s*Հ", r"ИНН", r"TIN", r"Tax\s*ID", r"ՀՎՀ"],
    "account": [r"հ\s*/\s*հ", r"հաշվեհամար", r"հաշիվ", r"р\s*/\s*с(?:ч)?", r"расч[её]тн\S*\s+сч[её]т", r"сч[её]т",
                r"account(?:\s*(?:no|number|#))?", r"IBAN", r"a/c"],
    "bank": [r"բանկ(?:ը)?", r"банк", r"bank"],
    "director": [r"գլխավոր\s+տնօրեն", r"գործադիր\s+տնօրեն", r"տնօրեն", r"ղեկավար", r"генеральн\S*\s+директор\S*",
                 r"директор\S*", r"руководител\S*", r"director", r"CEO", r"manager"],
    "legal_address": [r"իրավաբանական\s+հասցե", r"իրավ\.\s*հասցե", r"юридическ\S*\s+адрес", r"юр\.\s*адрес",
                      r"legal\s+address", r"registered\s+address", r"հասցե", r"адрес", r"address"],
    "company": [r"պատվիրատու", r"ընկերություն", r"կազմակերպություն", r"գովազդատու", r"заказчик", r"компания",
                r"организация", r"рекламодатель", r"company", r"customer", r"client", r"advertiser"],
    "email": [r"e-?mail", r"էլ\.\s*փոստ", r"эл\.\s*почта", r"почта"],
    "phone": [r"հեռ\.?", r"հեռախոս", r"тел\.?", r"телефон", r"phone", r"tel\.?", r"mob\.?"],
    "serial": [r"S\s*/\s*N", r"SN", r"serial(?:\s*(?:no|number))?", r"сер\.?\s*№", r"серийный\s+номер", r"IMEI",
               r"սերիական\s+համար"],
    "contract_no": [r"պայմանագիր\S*\s*(?:N|№|No|#)", r"договор\S*\s*(?:N|№|No|#)", r"contract\s*(?:N|№|No\.?|#)"],
    "price": [r"ամսական\s+գումար", r"գումար\S*", r"արժեք\S*", r"վճար\S*", r"гонорар", r"стоимост\S*", r"сумм\S*",
              r"цен\S*", r"price", r"amount", r"cost", r"fee"],
    "location": [r"մատուցման\s+վայր", r"место\s+оказания", r"location"],
}


# ------------------------------------------------------------------ օգնականներ
def _norm(s):
    s = str(s or "").replace(" ", " ").replace("եւ", "և").replace("․", ".")
    for rx, good in OCR_FIX:
        s = re.sub(rx, good, s)
    return re.sub(r"[ \t]+", " ", s)


# OCR-ի հաճախակի սխալներ («և» տառը երբեմն կարդացվում է «ե» կամ «եվ»)
OCR_FIX = [(r"\bԵրեան", "Երևան"), (r"\bերեան", "երևան"), (r"\bԵրեվան", "Երևան")]


def _fold(s):
    # casefold()-ը «և»-ը դարձնում է «եւ»՝ վերադարձնում ենք, որ բառարանների հետ համընկնի
    return str(s or "").casefold().replace("եւ", "և")


def _lines(text):
    return [ln.strip() for ln in _norm(text).split("\n")]


def _digits(s):
    return re.sub(r"\D", "", str(s or ""))


def _clean_val(v, maxlen=200):
    v = re.sub(r"_{2,}|\.{3,}|\s{2,}", " ", str(v or ""))
    v = v.strip(" \t:;,՝։-–—|\"'«»“”`´’")
    return v[:maxlen].strip()


def _label_re(labels):
    return re.compile(r"(?<![" + LETTER + r"])(?:" + "|".join(labels) + r")(?![" + LETTER + r"])", re.I)


class Doc:
    """Տեքստը՝ տողերով + «սեփական» գոտիները (Միքս Մեդիա-ի ռեկվիզիտներ)."""

    def __init__(self, text):
        self.text = _norm(text)
        self.lines = _lines(text)
        self.low = _fold(self.text)
        # ընկերությունների հիշատակումներ՝ (դիրք, սեփական է?)
        marks = []
        for nm in OWN_NAMES:
            for m in re.finditer(re.escape(nm), self.low):
                marks.append((m.start(), True))
        for m in re.finditer(r"[«\"“„]([^»\"”\n]{2,60})[»\"”]", self.text):
            own = any(nm in _fold(m.group(1)) for nm in OWN_NAMES)
            marks.append((m.start(), own))
        # ռեկվիզիտների բլոկի վերնագիր. «Կատարող» = Միքս Մեդիա, «Պատվիրատու» = հաճախորդ
        for m in re.finditer(r"(?:^|\n)\s*(Պատվիրատու|Կատարող|Заказчик|Исполнитель|Customer|Contractor)", self.text):
            marks.append((m.start(), m.group(1) in ("Կատարող", "Исполнитель", "Contractor")))
        self.marks = sorted(marks)

    def own_at(self, pos):
        """Տվյալ դիրքից առաջ վերջին նշված ընկերությունը «Միքս Մեդիա»-ն է?"""
        last = None
        for p, own in self.marks:
            if p > pos:
                break
            if pos - p < 900:
                last = own
        return bool(last)

    def pick(self, cands):
        """[(pos, value)] -> լավագույնը. սեփականը՝ միայն եթե այլ տարբերակ չկա."""
        cands = [(p, v) for p, v in cands if v and not any(o in _fold(v) for o in OWN_VALUES)]
        if not cands:
            return ""
        foreign = [c for c in cands if not self.own_at(c[0])]
        return (foreign or cands)[0][1]

    def after_label(self, labels, maxlen=160):
        """«Պիտակ: արժեք» -> [(pos, արժեք)] (նույն տողում, կամ հաջորդ տողում, եթե տողը դատարկ է)."""
        rx = _label_re(labels)
        out, pos = [], 0
        for i, ln in enumerate(self.lines):
            for m in rx.finditer(ln):
                rest = _clean_val(ln[m.end():], maxlen)
                if not rest and i + 1 < len(self.lines):
                    rest = _clean_val(self.lines[i + 1], maxlen)
                if rest:
                    out.append((pos + m.start(), rest))
            pos += len(ln) + 1
        return out


# ------------------------------------------------------------------ ամսաթվեր
def _mk_date(d, m, y):
    try:
        d, m, y = int(d), int(m), int(y)
    except (TypeError, ValueError):
        return ""
    if y < 100:
        y += 2000
    if not (1 <= d <= 31 and 1 <= m <= 12 and 1990 <= y <= 2100):
        return ""
    return f"{d:02d}.{m:02d}.{y}"


def _month(word):
    w = _fold(word)
    for n, stems in MONTHS.items():
        for s in stems:
            if w.startswith(s) and (n != 5 or w[:3] in ("մայ", "may", "мая", "май")):
                return n
    return 0


def find_dates(text):
    """-> [(pos, 'DD.MM.YYYY')] փաստաթղթի հերթականությամբ."""
    t = _norm(text)
    out = []
    for m in re.finditer(r"(?<!\d)(\d{1,2})\s*[./\-]\s*(\d{1,2})\s*[./\-]\s*(\d{4}|\d{2})(?!\d)", t):
        v = _mk_date(m.group(1), m.group(2), m.group(3))
        if v:
            out.append((m.start(), v))
    for m in re.finditer(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)", t):
        v = _mk_date(m.group(3), m.group(2), m.group(1))
        if v:
            out.append((m.start(), v))
    word = r"([" + LETTER + r"]{3,12})"
    for m in re.finditer(r"(?<!\d)[«\"]?(\d{1,2})[»\"]?\s+" + word + r"\s+(\d{4})", t):
        mo = _month(m.group(2))
        v = mo and _mk_date(m.group(1), mo, m.group(3))
        if v:
            out.append((m.start(), v))
    for m in re.finditer(r"(\d{4})\s*թ?\.?\s*" + word + r"\s+[«\"]?(\d{1,2})(?!\d)", t):
        mo = _month(m.group(2))
        v = mo and _mk_date(m.group(3), mo, m.group(1))
        if v:
            out.append((m.start(), v))
    for m in re.finditer(word + r"\s+(\d{1,2}),?\s+(\d{4})", t):
        mo = _month(m.group(1))
        v = mo and _mk_date(m.group(2), mo, m.group(3))
        if v:
            out.append((m.start(), v))
    seen, res = set(), []
    for p, v in sorted(out):
        if (p, v) not in seen:
            seen.add((p, v))
            res.append((p, v))
    return res


def _iso(d):
    return d[6:] + d[3:5] + d[:2]


def date_range(text):
    """Ժամանակահատված՝ «01.10.2026 – 31.10.2026», «с … по …», «… -ից մինչև …» -> (սկիզբ, ավարտ)."""
    ds = find_dates(text)
    t = _norm(text)
    for (p1, d1), (p2, d2) in zip(ds, ds[1:]):
        between = t[p1:p2]
        if p2 - p1 < 60 and re.search(r"[-–—]|до|по|մինչև|to|until|ից", between, re.I) and _iso(d2) >= _iso(d1):
            return d1, d2
    return "", ""


# ------------------------------------------------------------------ առանձին դաշտեր
def f_tin(doc):
    c = []
    for p, v in doc.after_label(LABELS["tin"], 40):
        m = re.match(r"[\s№N:]*(\d[\d ]{6,10}\d)", v)
        if m and len(_digits(m.group(1))) == 8:
            c.append((p, _digits(m.group(1))))
    if not c:   # պիտակ չկա՝ առանձին 8-նիշ թիվ (ոչ հեռախոս, ոչ ամսաթիվ)
        for m in re.finditer(r"(?<![\d+.\-/])(\d{8})(?![\d.\-/])", doc.text):
            c.append((m.start(), m.group(1)))
    return doc.pick(c)


def f_account(doc):
    c = []
    for p, v in doc.after_label(LABELS["account"], 60):
        m = re.search(r"(\d[\d \-]{9,28}\d)", v)
        if m and 11 <= len(_digits(m.group(1))) <= 20:
            c.append((p, _digits(m.group(1))))
    if not c:   # ՀՀ բանկային հաշիվ՝ 16 թվանշան (կարող է գրված լինել 4-ական խմբերով)
        for m in re.finditer(r"(?<![\d])(\d{4}[ \-]?\d{4}[ \-]?\d{4}[ \-]?\d{4})(?![\d])", doc.text):
            c.append((m.start(), _digits(m.group(1))))
    return doc.pick(c)


def f_bank(doc):
    c = []
    for keys, name in BANKS:
        for k in keys:
            for m in re.finditer(re.escape(k), doc.low):
                c.append((m.start(), name))
    c.sort()
    v = doc.pick(c)
    if v:
        return v
    for p, val in doc.after_label(LABELS["bank"], 60):
        val = re.split(r"\d{6,}|հ/հ|р/с|swift|ՀՎՀՀ|ИНН", val, flags=re.I)[0]
        val = _clean_val(val, 60)
        if len(val) >= 3 and re.search("[" + LETTER + "]", val):
            c.append((p, val))
    return doc.pick(c)


def _person(v):
    v = re.split(r"[,;|(/]|\s{2,}|_{2,}|ստորագր|подпис|signature|ՀՎՀՀ|ИНН|հեռ|тел", v, flags=re.I)[0]
    words = re.findall(r"[" + LETTER + r"]+\.?(?:-[" + LETTER + r"]+)?", v)
    words = [w for w in words if _fold(w).strip(".") not in ("տնօրեն", "директор", "director", "պրն", "տիկին",
                                                                   "г-н", "mr", "mrs", "ms", "ի", "դեմս")]
    if not words:
        return ""
    name = " ".join(words[:3])
    return re.sub(r"(յան|ունց|ենց|եան|ով)ի$", r"\1", name)   # «Պետրոսյանի» -> «Պետրոսյան»


def f_director(doc):
    c = []
    for m in re.finditer(r"ի\s+դեմս\s+(?:գլխավոր\s+|գործադիր\s+)?տնօրեն\s+([^,\n]{3,60})", doc.text, re.I):
        c.append((m.start(), _person(m.group(1))))
    for m in re.finditer(r"в\s+лице\s+(?:генерального\s+)?директора\s+([^,\n]{3,60})", doc.text, re.I):
        c.append((m.start(), _person(m.group(1))))
    for p, v in doc.after_label(LABELS["director"], 80):
        pv = _person(v)
        if pv and len(pv) >= 4:
            c.append((p, pv))
    c.sort()
    return doc.pick([(p, v) for p, v in c if v and len(v.split()) >= 1 and len(v) >= 4])


def _company_cands(doc):
    c = []
    t = doc.text
    q = r"[«\"“„]\s*([^»\"”\n]{2,60}?)\s*[»\"”]"
    for m in re.finditer(LEGAL + r"[ \t]*" + q, t):
        c.append((m.start(), m.group(1)))
    for m in re.finditer(q + r"[ \t]*-?[ \t]*" + LEGAL, t):
        c.append((m.start(), m.group(1)))
    for m in re.finditer(r"([" + LETTER + r"0-9][" + LETTER + r"0-9&.\- ]{1,40}?)[ \t]+" + LEGAL, t):
        nm = " ".join(m.group(1).split()[-3:])
        if _fold(nm) not in ("և", "и", "and") and not re.fullmatch(r"[\d\s]+", nm):
            c.append((m.start(), nm))
    for p, v in doc.after_label(LABELS["company"], 80):
        v = re.sub(r"^" + LEGAL + r"\s*", "", v)
        v = re.split(r"\s+" + LEGAL + r"|[,;|]", v)[0]
        v = _clean_val(v, 60)
        if len(v) >= 2:
            c.append((p, v))
    c = [(p, _clean_val(v, 60)) for p, v in sorted(c)]
    return [(p, v) for p, v in c if v and not any(o in _fold(v) for o in OWN_NAMES)]


def f_company(doc):
    return doc.pick(_company_cands(doc))


def f_email(doc):
    c = [(m.start(), m.group(0)) for m in re.finditer(r"[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+", doc.text)]
    return doc.pick(c)


def f_phone(doc):
    rx = r"(?:\+?374|\(?0\d{2}\)?)[\s\-()]*\d{2}[\s\-]?\d{2}[\s\-]?\d{2}(?:[\s\-]?\d{0,2})"
    c = [(m.start(), re.sub(r"\s+", " ", m.group(0)).strip()) for m in re.finditer(rx, doc.text)]
    return doc.pick([(p, v) for p, v in c if 8 <= len(_digits(v)) <= 12])


def f_legal_address(doc):
    c = []
    for p, v in doc.after_label(LABELS["legal_address"], 160):
        v = re.split(r"ՀՎՀՀ|ИНН|հ/հ|р/с|հեռ|тел\.|e-?mail|էլ\.", v, flags=re.I)[0]
        v = _clean_val(v, 160)
        if len(v) >= 6 and re.search(r"\d", v):
            c.append((p, v))
    if not c:
        pos = 0
        for ln in doc.lines:
            if ADDR_MARK.search(ln) and re.search(r"\d", ln) and len(ln) < 160:
                c.append((pos, _clean_val(ln)))
            pos += len(ln) + 1
    return doc.pick(c)


def f_addresses(doc):
    """Խանութների հասցեների ցուցակ (յուրաքանչյուր տող՝ մեկ հասցե)."""
    out = []
    skip = re.compile(r"իրավաբանական|юридическ|legal|ՀՎՀՀ|ИНН|հ/հ|р/с|^\s*(?:հասցե|адрес|address)", re.I)
    for ln in doc.lines:
        if not ln or skip.search(ln) or find_dates(ln):      # ռեկվիզիտներ և «ք. Երևան, 05.11.2026» վերնագիր
            continue
        cells = [x.strip() for x in ln.split("|")] if "|" in ln else [ln]
        for cell in cells:
            cell = re.sub(r"^\s*(?:\d{1,4}\s*[.)]|[-•*–])\s*", "", cell)
            if ADDR_MARK.search(cell) and re.search(r"\d", cell) and 6 <= len(cell) <= 160:
                if not any(o in _fold(cell) for o in OWN_VALUES) and cell not in out:
                    out.append(_clean_val(cell, 160))
    return [x for x in out if x]


def f_contract_no(doc):
    c = []
    for m in re.finditer(r"(?:պայմանագիր\S*|договор\S*|contract)\s*(?:N|№|No\.?|#)\s*([A-Za-zԱ-Ֆ0-9][\w\-/]{0,20})",
                         doc.text, re.I):
        c.append((m.start(), m.group(1)))
    if not c:
        c = [(m.start(), m.group(1)) for m in re.finditer(r"(?:№|N\s)\s*([0-9][\w\-/]{1,15})", doc.text)]
    return c[0][1] if c else ""


def _amount(s):
    m = re.search(r"(\d{1,3}(?:[ ,. ]\d{3})+|\d+)(?:[.,]\d{1,2})?", s)
    return _digits(m.group(1)) if m else ""


def f_price(doc):
    c = []
    for p, v in doc.after_label(LABELS["price"], 60):
        a = _amount(v)
        if a and len(a) <= 9 and int(a) > 0:
            c.append((p, a))
    for m in re.finditer(r"(\d{1,3}(?:[ ,. ]\d{3})+|\d{3,9})\s*(?:ՀՀ\s*)?(?:դրամ|դր\.|AMD|֏|драм|руб|USD|\$|€)",
                         doc.text, re.I):
        c.append((m.start(), _digits(m.group(1))))
    c.sort()
    return doc.pick(c)


def f_count(doc, addresses=None):
    m = re.search(r"(\d{1,4})\s*(?:հասցե|օբյեկտ|խանութ|кет|адрес\S*|объект\S*|магазин\S*|address|shops?|objects?)",
                  doc.text, re.I)
    if m:
        return m.group(1)
    return str(len(addresses)) if addresses else ""


def f_times(doc):
    t = doc.text
    m = re.search(r"(\d{1,2})[:.](\d{2})\s*[-–—]\s*(\d{1,2})[:.](\d{2})", t)
    if m:
        step = re.search(r"/\s*(\d{1,3})|(?:каждые|кажд\.|ամեն|every)\s*(\d{1,3})|(\d{1,3})\s*(?:րոպե|мин|min)",
                         t[m.end():m.end() + 80], re.I)
        rng = f"{int(m.group(1))}:{m.group(2)}-{int(m.group(3))}:{m.group(4)}"
        return rng + (f"/{next(g for g in step.groups() if g)}" if step else "")
    ts = re.findall(r"(?<![\d.])(\d{1,2}):(\d{2})(?![\d])", t)
    ts = [f"{int(h)}:{mm}" for h, mm in ts if int(h) < 24 and int(mm) < 60]
    return ", ".join(dict.fromkeys(ts)) if ts else ""


def f_serial(doc):
    c = []
    for p, v in doc.after_label(LABELS["serial"], 40):
        m = re.match(r"[\s#№:]*([A-Z0-9][A-Z0-9\-:]{3,30})", v, re.I)
        if m:
            c.append((p, m.group(1)))
    m = re.search(r"\b([0-9A-F]{2}(?:[:\-][0-9A-F]{2}){5})\b", doc.text, re.I)
    if m:
        c.append((m.start(), m.group(1)))
    return sorted(c)[0][1] if c else ""


def f_quarter(doc):
    t = doc.low
    m = re.search(r"\bq\s*([1-4])\b", t) or re.search(r"([1-4])\s*-?\s*(?:й|ին|րդ|-?th|-?st|-?nd|-?rd)?\s*(?:квартал|եռամսյակ|quarter)", t)
    if m:
        return m.group(1)
    m = re.search(r"\b(iv|iii|ii|i)\s*(?:квартал|եռամսյակ|quarter)", t)
    return {"i": "1", "ii": "2", "iii": "3", "iv": "4"}[m.group(1)] if m else ""


def f_year(doc):
    ys = re.findall(r"(?<!\d)(20[2-4]\d)(?!\d)", doc.text)
    return max(set(ys), key=ys.count) if ys else ""


def f_shop(doc):
    try:
        import adspace
        import store
        nets = store.networks()
    except Exception:  # noqa
        return ""
    for n in nets:
        short = _fold(adspace.short_name(n["name"]))
        if len(short) >= 3 and short in doc.low:
            return n["name"]
    return ""


def f_location(doc):
    for p, v in doc.after_label(LABELS["location"], 160):
        return v
    for ln in doc.lines:
        if re.search(r"առևտրի\s+կենտրոն|մոլ|ТЦ|ТРЦ|торгов\S*\s+центр|mall", ln, re.I) and len(ln) < 200:
            return _clean_val(ln, 200)
    return ""


def f_note(doc):
    parts = []
    no = f_contract_no(doc)
    if no:
        parts.append(f"№{no}")
    m = re.search(r"(\d{1,3})\s*(?:վրկ|վայրկ|сек|sec|s\b)", doc.text, re.I)
    if m:
        parts.append(f"{m.group(1)} сек")
    return ", ".join(parts)


def f_points(doc):
    m = re.search(r"կետ\S*\D{0,12}(3\s*(?:և|и|,|and)\s*4|3|4)(?!\d)", doc.text, re.I)
    if not m:
        return ""
    v = m.group(1)
    return "3 և 4" if "4" in v and "3" in v else v.strip()


def f_item_name(doc):
    brands = r"(Lenovo|HP|Dell|Asus|Acer|Intel|NUC|Raspberry|Beelink|Xiaomi|TP-?Link|Mikrotik|Keenetic|Huawei|ZTE|" \
             r"JBL|Yamaha|Behringer|Bose|Sony|Samsung|LG|Logitech|Ubiquiti|Cisco|D-?Link|Tenda|Microsoft|Apple)"
    for ln in doc.lines:
        m = re.search(brands + r"[^\n,;]{0,40}", ln, re.I)
        if m:
            return _clean_val(m.group(0), 80)
    return ""


def _option(doc, options):
    for o in sorted(options, key=len, reverse=True):
        if o and _fold(o) in doc.low:
            return o
    return ""


def f_generic(doc, f):
    """Անհայտ դաշտ՝ փնտրում ենք իր պիտակով («Պիտակ: արժեք»)."""
    words = [w for w in re.findall(r"[" + LETTER + r"]{4,}", f["label"]) if _fold(w) not in (
        "name", "date", "number", "with", "from", "this", "that", "only", "customer", "document")][:3]
    for w in words:
        hits = doc.after_label([re.escape(w)], 160)
        if hits:
            return hits[0][1]
    return ""


# ------------------------------------------------------------------ բաշխիչ
def kind_of(f):
    """Դաշտի տեսակը՝ բանալուց, պիտակից և հուշումից."""
    k = f["key"].lower()
    s = _fold(f"{k} {f.get('label', '')} {f.get('hint', '')}")
    if f["type"] == "date":
        if re.search(r"start|begin|from|սկիզբ|начал", s):
            return "start"
        if re.search(r"\bend\b|until|finish|ավարտ|оконч|конец", s) or k.endswith("end"):
            return "end"
        return "date"
    rules = [
        ("tin", k in ("tin", "inn", "hvhh") or re.search(r"tax id|ՀՎՀՀ|инн\b|\btin\b", s, re.I)),
        ("account", k == "account" or re.search(r"bank account|հաշվեհամար|iban", s)),
        ("bank", k == "bank" or (re.search(r"\bbank\b|բանկ", s) and "account" not in s)),
        ("email", "mail" in k or "e-mail" in s),
        ("phone", re.search(r"phone|tel\b|հեռախոս|телефон", s)),
        ("director", re.search(r"director|տնօրեն|директор", s)),
        ("addresses", f["type"] == "list" and re.search(r"address|հասցե|адрес", s)),
        ("legal_address", re.search(r"address|հասցե|адрес", s) and f["type"] != "list"),
        ("contract_no", re.search(r"contract number|№|номер договора", s) or k == "contract"),
        ("times", k == "times" or re.search(r"schedule|ժամեր|график", s)),
        ("count", k in ("addr_count", "count") or re.search(r"number of", s)),
        ("price", k in ("price", "amount", "sum") or re.search(r"price|amount|գումար|сумма", s)),
        ("serial", re.search(r"serial|imei|\bmac\b", s)),
        ("quarter", k == "quarter"),
        ("year", k == "year"),
        ("shop", k == "shop"),
        ("location", k == "location"),
        ("points", k == "points"),
        ("note", k == "note"),
        ("company", k in ("company", "client", "customer", "advertiser")
         or re.search(r"company name|ընկերություն|компани|advertiser", s)),
        ("item_name", k == "name" and re.search(r"item|device|model|brand", s)),
        ("title", k == "title"),
    ]
    for name, ok in rules:
        if ok:
            return name
    return f["type"] if f["type"] in ("text", "list", "table", "enum") else "generic"


def fill(text, fields):
    """text (OCR) + fields [{key,type,label,hint,options}] -> {key: value} (միայն գտնվածները)."""
    doc = Doc(text)
    out = {}
    dates = find_dates(doc.text)
    rng = date_range(doc.text)
    addr_cache = {}

    def addresses():
        if "v" not in addr_cache:
            addr_cache["v"] = f_addresses(doc)
        return addr_cache["v"]

    for f in fields:
        kind = kind_of(f)
        v = ""
        if kind == "date":
            near = [(p, d) for p, d in dates if re.search(r"պայմանագ|договор|contract|ամսաթիվ|дата|date",
                                                         doc.text[max(0, p - 120):p], re.I)]
            v = (near or dates or [(0, "")])[0][1]
        elif kind == "start":
            v = rng[0] or (dates[0][1] if len(dates) >= 2 else "")
        elif kind == "end":
            v = rng[1] or (dates[-1][1] if len(dates) >= 2 else "")
        elif kind == "addresses":
            v = addresses()
        elif kind == "count":
            v = f_count(doc, addresses())
        elif kind == "text":
            v = "\n".join(ln for ln in doc.lines if ln)[:6000]
        elif kind == "list":
            v = [ln for ln in doc.lines if len(ln) > 1][:400]
        elif kind == "table":
            v = [[c.strip() for c in re.split(r"\s*\|\s*|\t|\s{3,}", ln)] for ln in doc.lines if ln][:400]
        elif kind == "enum":
            v = _option(doc, f.get("options") or [])
        elif kind == "title":
            v = next((ln for ln in doc.lines if len(ln) > 3), "")[:120]
        elif kind == "generic":
            v = f_generic(doc, f)
        else:
            v = globals()["f_" + kind](doc)
        if f["type"] == "number" and isinstance(v, str):
            v = _digits(v) if kind not in ("times",) else v
        if f["type"] == "enum" and v and f.get("options") and v not in f["options"]:
            v = _option(Doc(str(v)), f["options"])
        if v:
            out[f["key"]] = v
    return out


# ------------------------------------------------------------------ ստուգում (տեղային ԻԻ-ի պատասխանի համար)
def valid(f, v):
    """Ձևաչափի ստուգում՝ սխալ արժեքը չենք դնում ձևում."""
    if v in ("", None, []):
        return False
    kind = kind_of(f)
    s = str(v).strip()
    if kind == "tin":
        return bool(re.fullmatch(r"\d{8}", _digits(s))) and len(_digits(s)) == len(re.sub(r"\s", "", s))
    if kind == "account":
        return 11 <= len(_digits(s)) <= 20
    if kind == "email":
        return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", s))
    if kind in ("date", "start", "end"):
        return bool(re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", s)) and bool(_mk_date(s[:2], s[3:5], s[6:]))
    if f["type"] == "number":
        return bool(_digits(s))
    return True


STRICT = ("tin", "account", "email", "phone", "date", "start", "end", "times", "serial", "contract_no", "year",
          "quarter")
