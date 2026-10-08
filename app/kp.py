# -*- coding: utf-8 -*-
"""Առևտրային առաջարկ (ԿՊ)՝ 5 տեսակ, նոր ԲԱՑ դիզայն (սպիտակ, լոգո, կապույտ→մանուշակագույն գրադիենտ, տարիֆային քարտեր).
Հայերեն, գները՝ ՀՀ դրամով, +374 հեռախոսներ, ՍՏՈՐԱԳՐՈՒԹՅՈՒՆ / ԿՆՔԻՔ / ԱՎՏՈԳՐԱՖ ՉԿԱ.
Վերջում ավելացվում է բլոկ՝ «Առաջարկի տվյալներ» (ամեն ինչ, ինչ մուտքագրվել է բոտում)."""
import re
from datetime import date, timedelta
from pathlib import Path

from PIL import Image as PILImage
from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

import mediaplan as mp

BASE = Path(__file__).resolve().parent.parent   # նախագծի արմատը (app/-ից մեկ մակարդակ վեր)
LOGO = BASE / "assets" / "logo.png"

VIOLET, BLUE = HexColor("#6A3DE8"), HexColor("#2E8CF0")
LINE, SOFT = HexColor("#E6E8F2"), HexColor("#F5F3FF")
INK, MUTED = HexColor("#12152E"), HexColor("#6B7090")
TINT, AMBER_BG, AMBER = HexColor("#EDE8FE"), HexColor("#FFF3E6"), HexColor("#B4530A")
W, H = A4
M = 14 * mm
CONTENT_W = W - 2 * M

COMPANY = "«Միքս Մեդիա» ՍՊԸ"
ADDRESS = "ՀՀ, ք. Երևան, Լևոնյան 48"
PHONE = "+374 44 702 703"
EMAIL = "info@mix-media.am"

KINDS = {
    "1": dict(short="Օբյեկտների ցանց՝ ամսական վճար",
              chip="ԱՌԵՎՏՐԱՅԻՆ ԱՌԱՋԱՐԿ",
              subtitle="Հնչյունավորվող օբյեկտների պարամետրերը և ամսական բաժանորդավճարը"),
    "2": dict(short="BUBUKA · երաժշտություն բիզնեսի համար",
              chip="BUBUKA · ԵՐԱԺՇՏՈՒԹՅՈՒՆ ԲԻԶՆԵՍԻ ՀԱՄԱՐ",
              title="Հրավիրում ենք համագործակցության",
              subtitle="Ավելին, քան պարզապես երաժշտություն"),
    "3": dict(short="Վաճառքի գրասենյակներ",
              chip="ԱՌԵՎՏՐԱՅԻՆ ԱՌԱՋԱՐԿ · ՎԱՃԱՌՔԻ ԳՐԱՍԵՆՅԱԿՆԵՐ",
              title="Երաժշտություն ձեր վաճառքի գրասենյակների համար",
              subtitle="Օրինական երաժշտական և գովազդային հեռարձակում ձեր օբյեկտներում"),
    "4": dict(short="Մագլցման կենտրոններ",
              chip="ԱՌԵՎՏՐԱՅԻՆ ԱՌԱՋԱՐԿ · ՄԱԳԼՑՄԱՆ ԿԵՆՏՐՈՆՆԵՐ",
              title="Երաժշտություն ձեր մագլցման կենտրոնների համար",
              subtitle="Օրինական երաժշտական և գովազդային հեռարձակում ձեր օբյեկտներում"),
    "5": dict(short="Ռեստորաններ",
              chip="ԱՌԵՎՏՐԱՅԻՆ ԱՌԱՋԱՐԿ · ՌԵՍՏՈՐԱՆՆԵՐ",
              title="Երաժշտություն ձեր ռեստորանի համար",
              subtitle="Օրինական երաժշտական և գովազդային հեռարձակում ձեր օբյեկտներում"),
}

FEAT_BUBUKA = [
    ("Իրավական պաշտպանության երաշխիք", ""),
    ("250 000+ թրեք", "Ռուս և արտասահմանյան կատարողներից"),
    ("Հավելվածի պարզ ինտեգրում", "Բոլոր օպերացիոն համակարգերում"),
    ("Անհատական մոտեցում", "Փլեյլիստ ստեղծելիս"),
    ("Հեռակա կառավարում", "Օբյեկտներում աուդիոհեռարձակման"),
    ("Գովազդային կաբինետ", "Հոլովակների սինթեզի գործառույթով"),
]
FEAT_12 = [
    ("Առանց հատկացումների", "ՌԱՕ-ին և ՎՕԻՍ-ին"), ("Իրավական պաշտպանություն", "Ոչ մի պարտված դատական գործ"),
    ("150 000+ ստեղծագործություն", "Բոլոր ոճերն ու ժանրերը"), ("Անհատական փլեյլիստներ", "Ձեր կոնցեպցիայով"),
    ("Գովազդային կաբինետ", "Աուդիոհոլովակների հեռարձակում"), ("Սինթեզ", "Խոսքի ավտոմատ գեներացում"),
    ("QR-մենյու", "Կոնստրուկտոր՝ անձնական կաբինետում"), ("Հարցումներ", "Հետադարձ կապ ստանալու գործիք"),
    ("Հեռակա կառավարում", "Ցանցի մեկ կամ բոլոր օբյեկտներով"),
    ("Հավելված բոլոր ՕՀ-երի համար", "Android, iOS, Windows, macOS, Linux"),
    ("Բովանդակության ներբեռնում", "Առանց ինտերնետի օբյեկտների համար"),
    ("Լուսանկար և տեսանյութ", "Ձեր գովազդային նյութերի ցուցադրում"),
]


# ------------------------------------------------------------------ helpers
def fmt_phone(s):
    d = re.sub(r"\D", "", s)
    if d.startswith("00374"):
        d = d[2:]
    if d.startswith("0") and len(d) == 9:
        d = "374" + d[1:]
    if len(d) == 8:
        d = "374" + d
    if not (d.startswith("374") and len(d) == 11):
        raise ValueError("Հեռախոսը գրեք +374 XX XXXXXX ձևաչափով")
    return f"+374 {d[3:5]} {d[5:8]} {d[8:]}"


def num(v):
    """1290 -> '1 290'; 501.5 -> '501,50'."""
    if isinstance(v, float) and abs(v - round(v)) > 1e-9:
        return f"{v:,.2f}".replace(",", " ").replace(".", ",")
    return f"{int(round(v)):,}".replace(",", " ")


def parse_number(s):
    s = s.strip().replace(" ", "").replace(",", ".")
    try:
        v = float(s)
    except ValueError:
        raise ValueError("Մուտքագրեք թիվ (օրինակ՝ 1290)")
    if v <= 0:
        raise ValueError("Թիվը պետք է լինի մեծ զրոյից")
    return int(v) if v == int(v) else v


def parse_groups(text):
    """Յուրաքանչյուր տող՝ Խումբ; Տեսակ; Մակերես; Գին  ->  [(խումբ, [(տեսակ, մակերես, գին)])]"""
    groups, order = {}, []
    for line in [l.strip() for l in text.splitlines() if l.strip()]:
        p = [x.strip() for x in re.split(r"[;|]", line)]
        if len(p) != 4:
            raise ValueError(f"«{line}»՝ գրեք՝ Խումբ; Տեսակ; Մակերես; Գին")
        price = parse_number(p[3])
        if p[0] not in groups:
            groups[p[0]] = []
            order.append(p[0])
        groups[p[0]].append((p[1], p[2], price))
    if not groups:
        raise ValueError("Ավելացրեք առնվազն մեկ տող")
    return [(g, groups[g]) for g in order]


def parse_tariffs(text):
    """Յուրաքանչյուր տող՝ Մակերես; Գին  ->  [(մակերես, գին)]"""
    rows = []
    for line in [l.strip() for l in text.splitlines() if l.strip()]:
        p = [x.strip() for x in re.split(r"[;|]", line)]
        if len(p) != 2:
            raise ValueError(f"«{line}»՝ գրեք՝ Մակերես; Գին (օրինակ՝ մինչև 200 մ²; 1290)")
        rows.append((p[0], parse_number(p[1])))
    if not rows:
        raise ValueError("Ավելացրեք առնվազն մեկ տող")
    return rows


# ------------------------------------------------------------------ drawing kit
class Page:
    def __init__(self, path, title):
        mp._fonts()
        self.c = canvas.Canvas(str(path), pagesize=A4)
        self.c.setTitle(title)
        self.c.setAuthor("Mix Media production")
        self.n = 1
        self.y = 0
        self.y_min = 24 * mm
        iw, ih = PILImage.open(LOGO).size
        self.logo_ratio = ih / iw

    def text(self, x, y, s, size=9, bold=False, color=INK, align="l"):
        c = self.c
        c.setFont("MM-B" if bold else "MM", size)
        c.setFillColor(color)
        {"l": c.drawString, "r": c.drawRightString, "c": c.drawCentredString}[align](x, y, str(s))

    def wrap(self, s, size, width, bold=False):
        font = "MM-B" if bold else "MM"
        lines, cur = [], ""
        for word in str(s).split():
            t = (cur + " " + word).strip()
            if stringWidth(t, font, size) <= width:
                cur = t
            else:
                if cur:
                    lines.append(cur)
                cur = word
        if cur:
            lines.append(cur)
        return lines or [""]

    def para(self, x, y, s, size, width, bold=False, color=INK, lead=1.3):
        for ln in self.wrap(s, size, width, bold):
            self.text(x, y, ln, size, bold, color)
            y -= size * lead
        return y

    def rrect(self, x, y, w, h, r=3 * mm, fill=white, line=None, lw=0.6):
        c = self.c
        if fill is not None:
            c.setFillColor(fill)
        if line is not None:
            c.setStrokeColor(line)
            c.setLineWidth(lw)
        c.roundRect(x, y, w, h, r, fill=1 if fill is not None else 0, stroke=1 if line is not None else 0)

    def grad(self, x, y, w, h, radius=0, c0=BLUE, c1=VIOLET):
        c = self.c
        c.saveState()
        p = c.beginPath()
        if radius:
            p.roundRect(x, y, w, h, radius)
        else:
            p.rect(x, y, w, h)
        c.clipPath(p, stroke=0, fill=0)
        c.linearGradient(x, y, x + w, y + h * 0.3, (c0, c1))
        c.restoreState()

    def hline(self, x1, x2, y, color=LINE, w=0.6, dash=None):
        c = self.c
        c.setStrokeColor(color)
        c.setLineWidth(w)
        if dash:
            c.setDash(*dash)
        c.line(x1, y, x2, y)
        c.setDash()

    def logo(self, x, y_top, w):
        h = w * self.logo_ratio
        self.c.drawImage(str(LOGO), x, y_top - h, w, h, mask="auto")
        return h

    def dots(self, x0, y0, cols=9, rows=5, step=3.2 * mm):
        """Լոգոյի կետային մոտիվ՝ փոքր դեկոր."""
        c = self.c
        for ci in range(cols):
            t = ci / max(cols - 1, 1)
            col = HexColor("#%02x%02x%02x" % (int(46 + 60 * t), int(140 - 80 * t), 240 - int(8 * t)))
            c.setFillColor(col)
            r = 0.95 * mm * (1 - 0.75 * t)
            for ri in range(rows):
                c.circle(x0 + ci * step, y0 - ri * step, r, fill=1, stroke=0)

    def footer(self):
        self.hline(M, W - M, 14 * mm, LINE, 0.6)
        self.text(M, 9 * mm, f"{COMPANY}  ·  {ADDRESS}  ·  {PHONE}  ·  {EMAIL}", 7.2, False, MUTED)
        self.text(W - M, 9 * mm, f"{self.n}", 7.5, True, VIOLET, "r")

    def new_page(self):
        self.footer()
        self.c.showPage()
        self.n += 1
        self.logo(M, H - 10 * mm, 24 * mm)
        self.text(W - M, H - 15 * mm, "Առևտրային առաջարկ", 8, False, MUTED, "r")
        self.grad(M, H - 24 * mm, CONTENT_W, 0.9 * mm)
        self.y = H - 33 * mm

    def ensure(self, need):
        if self.y - need < self.y_min:
            self.new_page()

    def finish(self):
        self.footer()
        self.c.showPage()
        self.c.save()


# ------------------------------------------------------------------ sections
def hero(pg, d, kind):
    k = KINDS[kind]
    top = H - 12 * mm
    lh = pg.logo(M, top, 46 * mm)
    for i, (t, sz, b, col) in enumerate([(COMPANY, 9, True, INK), (ADDRESS, 8, False, MUTED),
                                        (f"Հեռ.՝ {PHONE}", 8, False, MUTED), (EMAIL, 8, False, MUTED)]):
        pg.text(W - M, top - 5 * mm - i * 4.4 * mm, t, sz, b, col, "r")
    y = top - max(lh, 20 * mm) - 5 * mm
    pg.grad(M, y, CONTENT_W, 1.1 * mm)
    y -= 11 * mm
    # chips
    parts = k["chip"].split(" · ")
    x = M
    for i, p in enumerate(parts):
        w = stringWidth(p, "MM-B", 7.3) + 8 * mm
        if i == 0:
            pg.rrect(x, y - 2.3 * mm, w, 7 * mm, r=3.5 * mm, fill=None, line=VIOLET, lw=0.9)
            pg.text(x + 4 * mm, y, p, 7.3, True, VIOLET)
        else:
            pg.rrect(x, y - 2.3 * mm, w, 7 * mm, r=3.5 * mm, fill=TINT)
            pg.text(x + 4 * mm, y, p, 7.3, True, VIOLET)
        x += w + 2.5 * mm
    pg.dots(W - M - 8 * 3.2 * mm, y + 5.5 * mm, rows=3)
    y -= 13 * mm
    # title (կլիենտի անունը՝ մանուշակագույն)
    if k.get("title"):
        segs = [(k["title"], INK)]
    else:
        segs = [(f"«{d['client']}»", VIOLET), ("կառավարող ընկերությանը", INK)]
    size = 24
    full = " ".join(s for s, _ in segs)
    while size > 14 and len(pg.wrap(full, size, CONTENT_W - 20 * mm, True)) > 2:
        size -= 1.5
    words = [(w, col) for s, col in segs for w in s.split()]
    line, lw = [], 0
    lines = []
    for w, col in words:
        ww = stringWidth(w + " ", "MM-B", size)
        if lw + ww > CONTENT_W - 20 * mm and line:
            lines.append(line)
            line, lw = [], 0
        line.append((w, col))
        lw += ww
    lines.append(line)
    for ln in lines[:2]:
        x = M
        for w, col in ln:
            pg.text(x, y, w, size, True, col)
            x += stringWidth(w + " ", "MM-B", size)
        y -= size * 0.43 * mm
    y = pg.para(M, y + 1 * mm, k["subtitle"], 9.5, CONTENT_W - 20 * mm, color=MUTED) - 5 * mm
    # info strip
    h = 15 * mm
    pg.rrect(M, y - h, CONTENT_W, h, r=3 * mm, fill=SOFT)
    pg.grad(M, y - h, 1.6 * mm, h)
    cols = [("ՊԱՏՎԻՐԱՏՈՒ", d["client"], 0.46), ("ԱՄՍԱԹԻՎ", d["date"], 0.24), ("ՎԱՎԵՐ Է ՄԻՆՉԵՎ", d["valid_until"], 0.30)]
    x = M + 7 * mm
    for i, (lab, val, frac) in enumerate(cols):
        w_ = CONTENT_W * frac
        pg.text(x, y - 5.6 * mm, lab, 6.5, True, MUTED)
        pg.text(x, y - 11 * mm, pg.wrap(val, 10.5, w_ - 10 * mm, True)[0], 10.5, True, INK)
        if i < 2:
            pg.c.setStrokeColor(HexColor("#D9D2FB"))
            pg.c.setLineWidth(0.6)
            pg.c.line(x + w_ - 5 * mm, y - 3 * mm, x + w_ - 5 * mm, y - h + 3 * mm)
        x += w_
    pg.y = y - h - 9 * mm


def section_title(pg, s, need=16 * mm):
    pg.ensure(need)
    pg.text(M, pg.y, s, 14, True, INK)
    w = stringWidth(s, "MM-B", 14)
    pg.grad(M, pg.y - 3 * mm, min(w, 28 * mm), 1 * mm)
    pg.y -= 10 * mm


def feature_grid(pg, feats, cols=2):
    gap = 5 * mm
    cw = (CONTENT_W - gap * (cols - 1)) / cols
    rh = 10.8 * mm
    for i in range(0, len(feats), cols):
        pg.ensure(rh)
        for j, (t, s) in enumerate(feats[i:i + cols]):
            x = M + j * (cw + gap)
            n = i + j + 1
            pg.grad(x, pg.y - 9 * mm, 9 * mm, 9 * mm, radius=2.4 * mm)
            pg.text(x + 4.5 * mm, pg.y - 5.9 * mm, f"{n:02d}", 8.5, True, white, "c")
            pg.text(x + 12.5 * mm, pg.y - 3.6 * mm, pg.wrap(t, 9, cw - 14 * mm, True)[0], 9, True, INK)
            if s:
                pg.text(x + 12.5 * mm, pg.y - 7.8 * mm, pg.wrap(s, 7.6, cw - 14 * mm)[0], 7.6, False, MUTED)
        pg.y -= rh
        if i + cols < len(feats):
            pg.hline(M, W - M, pg.y + 2 * mm, LINE, 0.4, dash=(1, 2))
    pg.y -= 7 * mm


def total_bar(pg, label, value, h=15 * mm):
    pg.ensure(h + 4 * mm)
    pg.grad(M, pg.y - h, CONTENT_W, h, radius=3.5 * mm)
    lines = pg.wrap(label, 9.5, CONTENT_W * 0.55, True)[:2]
    ty = pg.y - h / 2 + (len(lines) - 1) * 2.2 * mm - 1.2 * mm
    for ln in lines:
        pg.text(M + 7 * mm, ty, ln, 9.5, True, white)
        ty -= 4.4 * mm
    pg.text(W - M - 7 * mm, pg.y - h / 2 - 2.2 * mm, value, 17, True, white, "r")
    pg.y -= h + 7 * mm


def discount_pill(pg, pct, months):
    if not pct:
        return
    pg.ensure(14 * mm)
    s = f"{pct}% զեղչ՝ {months} և ավելի ամսվա համար վճարելիս"
    w = stringWidth(s, "MM-B", 9) + 18 * mm
    x = M + (CONTENT_W - w) / 2
    pg.rrect(x, pg.y - 9 * mm, w, 9 * mm, r=4.5 * mm, fill=AMBER_BG)
    pg.c.setFillColor(AMBER)
    pg.c.circle(x + 5.5 * mm, pg.y - 4.5 * mm, 2.8 * mm, fill=1, stroke=0)
    pg.text(x + 5.5 * mm, pg.y - 5.6 * mm, "%", 8, True, white, "c")
    pg.text(x + 10.5 * mm, pg.y - 5.9 * mm, s, 9, True, AMBER)
    pg.y -= 15 * mm


def plan_cards(pg, cards, cols=None):
    """cards՝ [(վերնագիր, մակերես, գին, ենթատեքստ)] -> տարիֆային քարտեր կողք կողքի."""
    cols = cols or min(len(cards), 3)
    gap = 5 * mm
    cw = (CONTENT_W - gap * (cols - 1)) / cols
    ch = 38 * mm
    for i in range(0, len(cards), cols):
        pg.ensure(ch + 4 * mm)
        for j, (title, area, price, sub) in enumerate(cards[i:i + cols]):
            x = M + j * (cw + gap)
            pg.rrect(x, pg.y - ch, cw, ch, r=3.5 * mm, fill=white, line=LINE, lw=0.8)
            pg.grad(x, pg.y - 9 * mm, cw, 9 * mm, radius=3.5 * mm)
            pg.c.setFillColor(white)
            pg.c.rect(x + 0.4, pg.y - 9 * mm, cw - 0.8, 3 * mm, fill=1, stroke=0)
            pg.grad(x, pg.y - 7 * mm, cw, 1.2 * mm)
            pg.text(x + 6 * mm, pg.y - 4.6 * mm, pg.wrap(title, 8.5, cw - 12 * mm, True)[0], 8.5, True, white)
            pg.text(x + 6 * mm, pg.y - 13.5 * mm, "ՄԱԿԵՐԵՍ", 6.5, True, MUTED)
            pg.text(x + 6 * mm, pg.y - 19 * mm, pg.wrap(area, 11, cw - 12 * mm, True)[0], 11, True, INK)
            pg.hline(x + 6 * mm, x + cw - 6 * mm, pg.y - 22.5 * mm, LINE, 0.5, dash=(1, 2))
            pg.text(x + 6 * mm, pg.y - 32 * mm, num(price), 19, True, VIOLET)
            pw = stringWidth(num(price) + " ", "MM-B", 19)
            pg.text(x + 6 * mm + pw, pg.y - 32 * mm, "դրամ/ամիս", 8, False, MUTED)
            pg.text(x + 6 * mm, pg.y - 36.8 * mm, sub, 6.8, False, MUTED)
        pg.y -= ch + 6 * mm


def kind1_body(pg, d):
    section_title(pg, "Ամսական բաժանորդավճար")
    pg.ensure(20 * mm)
    pg.rrect(M, pg.y - 8 * mm, CONTENT_W, 8 * mm, r=2.5 * mm, fill=SOFT)
    for x, s, al in ((M + 5 * mm, "Տարածքի անվանումը", "l"), (M + 88 * mm, "Հնչյունավորվող մակերեսը", "l"),
                     (W - M - 5 * mm, "Ամսական վճար", "r")):
        pg.text(x, pg.y - 5.2 * mm, s, 7.5, True, VIOLET, al)
    pg.y -= 11 * mm
    total = 0
    for gname, rows in d["groups"]:
        pg.ensure(22 * mm)
        pg.c.setFillColor(VIOLET)
        pg.c.circle(M + 2.2 * mm, pg.y - 3.6 * mm, 1.3 * mm, fill=1, stroke=0)
        pg.text(M + 6 * mm, pg.y - 4.8 * mm, pg.wrap(gname, 10, CONTENT_W - 10 * mm, True)[0], 10, True, INK)
        pg.y -= 8 * mm
        sub = 0
        for (typ, area, price) in rows:
            pg.ensure(10 * mm)
            pg.text(M + 6 * mm, pg.y - 4.8 * mm, pg.wrap(typ, 9, 76 * mm)[0], 9, False, INK)
            pg.text(M + 88 * mm, pg.y - 4.8 * mm, pg.wrap(area, 9, 50 * mm)[0], 9, False, MUTED)
            pg.text(W - M - 5 * mm, pg.y - 4.8 * mm, f"{num(price)} դրամ", 9.5, True, INK, "r")
            pg.y -= 8 * mm
            pg.hline(M + 6 * mm, W - M, pg.y + 0.8 * mm, LINE, 0.5)
            sub += price
        total += sub
        if len(rows) > 1:
            pg.text(W - M - 5 * mm, pg.y - 4 * mm, f"Ընդամենը՝  {num(sub)} դրամ", 9, True, VIOLET, "r")
            pg.y -= 7 * mm
        pg.y -= 4 * mm
    total_bar(pg, "Բոլոր օբյեկտների ամսական սպասարկման ընդհանուր արժեքը", f"{num(total)} դրամ", h=17 * mm)


def kind2_body(pg, d):
    section_title(pg, "Ինչ եք ստանում")
    feature_grid(pg, FEAT_BUBUKA)
    section_title(pg, "Առևտրային առաջարկ", need=50 * mm)
    if d.get("purpose"):
        pg.y = pg.para(M, pg.y, d["purpose"], 9, CONTENT_W, color=MUTED) - 3 * mm
    lic, lib = d["license"], d["library"]
    for t, v, note in (("«ԲՈՒԲՈՒԿԱ» ծրագրային ապահովման օգտագործման իրավունք", lic, "առանց ԱԱՀ"),
                       ("«ԲՈՒԲՈՒԿԱ» մեդիագրադարանի երաժշտական բովանդակության օգտագործման իրավունք", lib, "ներառյալ 5% ԱԱՀ")):
        pg.ensure(16 * mm)
        ty = pg.y - 4.5 * mm
        for ln in pg.wrap(t, 9.2, 105 * mm)[:2]:
            pg.text(M, ty, ln, 9.2, False, INK)
            ty -= 4.2 * mm
        pg.text(W - M, pg.y - 5 * mm, f"{num(v)}", 14, True, INK, "r")
        pg.text(W - M, pg.y - 9.6 * mm, f"դրամ/ամիս · {note}", 7.2, False, MUTED, "r")
        pg.y -= 14 * mm
        pg.hline(M, W - M, pg.y + 1.5 * mm, LINE, 0.6)
    pg.y -= 4 * mm
    total_bar(pg, "Ընդամենը՝ ամսական բաժանորդավճար մեկ օբյեկտի համար", f"{num(lic + lib)} դրամ")


def tariff_body(pg, d, kind):
    section_title(pg, "Մեզ հետ աշխատելու առավելությունները")
    feature_grid(pg, FEAT_12)
    section_title(pg, "Բաժանորդավճար", need=52 * mm)
    if kind == "3":
        plan_cards(pg, [("Վաճառքի գրասենյակ", a, p, "1 օբյեկտի համար") for a, p in d["tariffs"]])
    elif kind == "4":
        n, p = d["objects"], d["price"]
        cards = [("Մագլցման կենտրոն", d["area"], p, "1 օբյեկտի համար")]
        if n > 1:
            cards.append((f"{n} օբյեկտ", d["area"], p * n, f"Բաժանորդավճար {n} օբյեկտի համար"))
        plan_cards(pg, cards, cols=2)
    else:
        plan_cards(pg, [("Ռեստորան", d["area"], d["price"], "1 օբյեկտի համար")], cols=1)
    discount_pill(pg, d.get("discount"), d.get("discount_months"))


def info_block(pg, d):
    """Բոլոր տվյալները, որ մուտքագրվել են բոտում."""
    rows, seen = [], set()
    for k, v in [("Պատվիրատու", d["client"])] + list(d.get("answers") or []) + [
            ("Մենեջեր", d["manager"]), ("Հեռախոս", d["phone"]), ("Ամսաթիվ", d["date"]), ("Վավեր է մինչև", d["valid_until"])]:
        if k in seen or v in (None, ""):
            continue
        seen.add(k)
        rows.append((k, str(v)))
    section_title(pg, "Առաջարկի տվյալներ", need=34 * mm)
    colw = (CONTENT_W - 8 * mm) / 2
    for i in range(0, len(rows), 2):
        pair = rows[i:i + 2]
        nl = max(len(pg.wrap(v, 9, colw * 0.55, True)) for _, v in pair)
        rh = 7 * mm + 4 * mm * (nl - 1)
        pg.ensure(rh + 2 * mm)
        for j, (k, v) in enumerate(pair):
            x = M + j * (colw + 8 * mm)
            pg.text(x, pg.y - 5 * mm, k, 8.3, False, MUTED)
            ty = pg.y - 5 * mm
            for ln in pg.wrap(v, 9, colw * 0.55, True):
                pg.text(x + colw, ty, ln, 9, True, INK, "r")
                ty -= 4 * mm
            pg.hline(x, x + colw, pg.y - rh + 1 * mm, LINE, 0.5, dash=(1, 2))
        pg.y -= rh + 1 * mm


# ------------------------------------------------------------------ main
def make_kp(d, out_path):
    """d['kind'] ∈ '1'..'5'. Վերադարձնում է pdf-ի ճանապարհը."""
    kind = str(d.get("kind", "1"))
    d = dict(d)
    today = date.today()
    d.setdefault("date", mp.fmt(today))
    d.setdefault("valid_until", mp.fmt(today + timedelta(d.get("valid_days", 14))))
    pg = Page(out_path, f"Առևտրային առաջարկ — {d['client']}")
    hero(pg, d, kind)
    if kind == "1":
        kind1_body(pg, d)
    elif kind == "2":
        kind2_body(pg, d)
    else:
        tariff_body(pg, d, kind)
    info_block(pg, d)
    pg.finish()
    return Path(out_path)


# ------------------------------------------------------------------ նմուշներ (5 ԿՊ-ների նախադիտում)
def sample_data(kind):
    base = dict(kind=kind, client="Ձեր ընկերությունը", manager="Մենեջերի անուն", phone=PHONE, valid_days=14, answers=[])
    if kind == "1":
        base["groups"] = [("Առողջարան «Այ-Պետրի»", [("Ընդունարան", "100 մ²", 1290), ("Ռեստորան", "389,4 մ²", 2390)]),
                          ("Հյուրանոց «Դաչա Ռախմանինով»", [("Ռեստորան", "245 մ²", 2390)])]
    elif kind == "2":
        base.update(license=501.5, library=88.5, purpose="")
    elif kind == "3":
        base.update(tariffs=[("մինչև 200 մ²", 1290), ("մինչև 500 մ²", 1590)], discount=10, discount_months=6)
    elif kind == "4":
        base.update(area="մինչև 1 500 մ²", price=2090, objects=3, discount=10, discount_months=3)
    else:
        base.update(area="մինչև 100 մ²", price=1790, discount=10, discount_months=6)
    return base


def make_samples(out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    return [make_kp(sample_data(k), out_dir / f"KP_{k}.pdf") for k in "12345"]
