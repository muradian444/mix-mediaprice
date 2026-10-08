# -*- coding: utf-8 -*-
"""Մեդիա պլանի PDF՝ ցանց (սլոթերի ժամեր × օրեր, ըստ ամիսների), հասցեների ցուցակ, ստորագրություն և կնիք."""
import re
from collections import OrderedDict
from datetime import date, timedelta
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Flowable, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

BASE = Path(__file__).resolve().parent.parent   # նախագծի արմատը (app/-ից մեկ մակարդակ վեր)
COMPANY_LINE = "«Միքս Մեդիա» ՍՊԸ, ՀՀ, ք. Երևան, Լևոնյան 48, Հեռ.՝ +374 44 702 703"
BLUE_D, BLUE_L, BLUE_H = colors.HexColor("#9DC3E6"), colors.HexColor("#DDEBF7"), colors.HexColor("#2F5597")
# նոր դիզայն (նույն ոճը, ինչ ԿՊ-ում)
NAVY, VIOLET, BLUE = colors.HexColor("#1D1B5E"), colors.HexColor("#6A3DE8"), colors.HexColor("#2E8CF0")
SOFT, TINT, LINE = colors.HexColor("#F5F3FF"), colors.HexColor("#EDE8FE"), colors.HexColor("#DDE0EE")
INK, MUTED = colors.HexColor("#12152E"), colors.HexColor("#6B7090")

_FONTS = {"regular": ["fonts/Regular.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                      r"C:\Windows\Fonts\sylfaen.ttf", r"C:\Windows\Fonts\arial.ttf",
                      "/Library/Fonts/Arial Unicode.ttf"],
          "bold": ["fonts/Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                   r"C:\Windows\Fonts\arialbd.ttf", r"C:\Windows\Fonts\sylfaen.ttf",
                   "/Library/Fonts/Arial Unicode.ttf"]}
_ready = False


def _fonts():
    global _ready
    if _ready:
        return
    for key, name in (("regular", "MM"), ("bold", "MM-B")):
        for c in _FONTS[key]:
            p = Path(c) if Path(c).is_absolute() else BASE / c
            if p.exists():
                pdfmetrics.registerFont(TTFont(name, str(p)))
                break
        else:
            raise RuntimeError("Հայերեն տառատեսակ չի գտնվել. Դրեք fonts/Regular.ttf և fonts/Bold.ttf")
    pdfmetrics.registerFontFamily("MM", normal="MM", bold="MM-B")
    _ready = True


# ------------------------------------------------------------------ parsing
def _t2m(s):
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def _m2t(m):
    return f"{m // 60}:{m % 60:02d}"


def parse_times(text):
    """'10:00-22:00/30', '10:00-12:00 15' կամ '9:00, 13:00, 18:30' -> ['10:00', ...]"""
    text = text.strip().replace("․", ":").replace(".", ":").replace("–", "-").replace("—", "-")
    m = re.fullmatch(r"(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})\s*[/ ]\s*(\d{1,3})", text)
    if m:
        a, b, step = _t2m(m[1]), _t2m(m[2]), int(m[3])
        if step <= 0 or b < a or b >= 24 * 60:
            raise ValueError("Ժամերի միջակայքը սխալ է")
        return [_m2t(x) for x in range(a, b + 1, step)]
    parts = [x for x in re.split(r"[,\s;]+", text) if x]
    if parts and all(re.fullmatch(r"\d{1,2}:\d{2}", x) for x in parts):
        times = sorted({_t2m(x) for x in parts})
        if times[-1] >= 24 * 60:
            raise ValueError("Ժամը սխալ է")
        return [_m2t(x) for x in times]
    raise ValueError("Չհասկացա ժամերը")


def parse_period(text, max_days=1830):
    """'01.10.2026 - 31.10.2026' -> (date, date). max_days=None՝ առանց սահմանափակման (ԱԿՏ, հաշվետվություն)."""
    text = str(text or "").replace("․", ".").replace("/", ".").replace("–", "-").replace("—", "-")
    m = re.fullmatch(r"\s*(\d{1,2})[.](\d{1,2})[.](\d{4})\s*[-–—]\s*(\d{1,2})[.](\d{1,2})[.](\d{4})\s*", text)
    if not m:
        raise ValueError("Գրեք ԸԸ.ԱԱ.ՏՏՏՏ - ԸԸ.ԱԱ.ՏՏՏՏ")
    try:
        a = date(int(m[3]), int(m[2]), int(m[1]))
        b = date(int(m[6]), int(m[5]), int(m[4]))
    except ValueError:
        raise ValueError("Այդպիսի ամսաթիվ չկա (ստուգեք օրը և ամիսը)")
    if b < a:
        raise ValueError("Ավարտի ամսաթիվը փոքր է սկզբից")
    if max_days and (b - a).days + 1 > max_days:
        raise ValueError(f"Առավելագույնը {max_days} օր")
    return a, b


def fmt(d):
    return d.strftime("%d.%m.%Y")


MONTHS = ["Հունվար", "Փետրվար", "Մարտ", "Ապրիլ", "Մայիս", "Հունիս", "Հուլիս", "Օգոստոս",
          "Սեպտեմբեր", "Հոկտեմբեր", "Նոյեմբեր", "Դեկտեմբեր"]


# ------------------------------------------------------------------ styles
def _st(size=8, bold=False, align=0, color=INK, leading=None):
    return ParagraphStyle("x", fontName="MM-B" if bold else "MM", fontSize=size,
                          leading=leading or size * 1.25, alignment=align, textColor=color)


def _P(t, **kw):
    # «․» (U+2024, հայկական կետ հասցեներում) PDF-ի տառատեսակներում չկա և երևում է □ — փոխարինում ենք «.»-ով
    return Paragraph(str(t).replace("․", "."), _st(**kw))


LOGO = BASE / "assets" / "logo.png"
CONTENT_W = 180 * mm


def _logo_flowable(width):
    """Mix Media production լոգոն (նկար) տեքստի փոխարեն."""
    from reportlab.platypus import Image
    if LOGO.exists():
        from PIL import Image as PILImage
        w, h = PILImage.open(LOGO).size
        img = Image(str(LOGO), width=width, height=width * h / w)
        img.hAlign = "LEFT"
        return img
    return _P("MIXMEDIA production", size=14, bold=True, color=NAVY)


class _GradBar(Flowable):
    """Կապույտ → մանուշակագույն գրադիենտ գիծ/ժապավեն."""

    def __init__(self, width, height=1.1 * mm, radius=0):
        super().__init__()
        self.width, self.height, self.radius = width, height, radius

    def draw(self):
        c = self.canv
        c.saveState()
        p = c.beginPath()
        if self.radius:
            p.roundRect(0, 0, self.width, self.height, self.radius)
        else:
            p.rect(0, 0, self.width, self.height)
        c.clipPath(p, stroke=0, fill=0)
        c.linearGradient(0, 0, self.width, 0, (BLUE, VIOLET))
        c.restoreState()


def _on_page(canv, doc):
    """Էջատակ՝ ընկերության տվյալներ + էջի համար."""
    canv.saveState()
    w, _ = A4
    canv.setStrokeColor(LINE)
    canv.setLineWidth(0.6)
    canv.line(15 * mm, 10 * mm, w - 15 * mm, 10 * mm)
    canv.setFont("MM", 6.8)
    canv.setFillColor(MUTED)
    canv.drawString(15 * mm, 6.3 * mm, COMPANY_LINE)
    canv.setFont("MM-B", 7.5)
    canv.setFillColor(VIOLET)
    canv.drawRightString(w - 15 * mm, 6.3 * mm, str(doc.page))
    canv.restoreState()


def _header(title, client, start, end):
    logo = _logo_flowable(36 * mm)
    right = Table([[_P("«Միքս Մեդիա» ՍՊԸ", size=8.5, bold=True, align=2)],
                   [_P("ՀՀ, ք. Երևան, Լևոնյան 48", size=7.5, color=MUTED, align=2)],
                   [_P("Հեռ.՝ +374 44 702 703", size=7.5, color=MUTED, align=2)]], colWidths=[80 * mm])
    right.setStyle(TableStyle([("TOPPADDING", (0, 0), (-1, -1), 0.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 0.5),
                               ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    top = Table([[logo, right]], colWidths=[100 * mm, 80 * mm])
    top.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                             ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    chip = Table([[_P("ՄԵԴԻԱ ՊԼԱՆ", size=6.8, bold=True, color=VIOLET, align=1)]], colWidths=[26 * mm])
    chip.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.8, VIOLET), ("ROUNDEDCORNERS", [3, 3, 3, 3]),
                              ("TOPPADDING", (0, 0), (-1, -1), 1.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    chip.hAlign = "LEFT"
    days = (end - start).days + 1
    strip = Table([[_P("ՊԱՏՎԻՐԱՏՈՒ", size=6.3, bold=True, color=MUTED),
                    _P("ՀԵՌԱՐՁԱԿՄԱՆ ԺԱՄԱՆԱԿԱՀԱՏՎԱԾ", size=6.3, bold=True, color=MUTED),
                    _P("ՕՐԵՐ", size=6.3, bold=True, color=MUTED)],
                   [_P(client, size=10.5, bold=True), _P(f"{fmt(start)} — {fmt(end)}", size=10.5, bold=True),
                    _P(str(days), size=10.5, bold=True, color=VIOLET)]],
                  colWidths=[80 * mm, 72 * mm, 28 * mm])
    strip.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), SOFT), ("LINEBEFORE", (0, 0), (0, -1), 2.2, VIOLET),
                               ("LINEAFTER", (0, 0), (1, -1), 0.5, colors.HexColor("#D9D2FB")),
                               ("LEFTPADDING", (0, 0), (-1, -1), 7), ("TOPPADDING", (0, 0), (-1, 0), 5),
                               ("BOTTOMPADDING", (0, -1), (-1, -1), 6), ("ROUNDEDCORNERS", [4, 4, 4, 4])]))
    return KeepTogether([top, Spacer(1, 4), _GradBar(CONTENT_W), Spacer(1, 7), chip, Spacer(1, 3),
                         _P(title, size=15, bold=True, leading=19), Spacer(1, 5), strip])


def _section(title):
    return KeepTogether([Spacer(1, 7), _P(title, size=10.5, bold=True), Spacer(1, 2), _GradBar(18 * mm, 0.9 * mm),
                         Spacer(1, 4)])


# ------------------------------------------------------------------ grid
def _by_month(days):
    """Օրերը՝ ըստ ամիսների (երկար մեդիա պլանի համար՝ ամեն ամիսը առանձին աղյուսակ)."""
    out = OrderedDict()
    for d in days:
        out.setdefault((d.year, d.month), []).append(d)
    return list(out.values())


def _grid(slots, days, clip_ids):
    nd = len(days)
    months = OrderedDict()
    for d in days:
        months[(d.year, d.month)] = True
    label = " / ".join(f"{MONTHS[m - 1]} {y} թ." for (y, m) in months)
    W = colors.white
    head1 = ["", _P(label, size=7.5, bold=True, color=W, align=1)] + [""] * (nd - 1) + [""]
    head2 = [_P("Ժամ", size=6.2, bold=True, color=W, align=1)] + \
            [_P(str(d.day), size=6, bold=True, color=W, align=1) for d in days] + \
            [_P("Օր", size=6.2, bold=True, color=W, align=1)]
    rows = [head1, head2]
    for i, s in enumerate(slots):
        cid = clip_ids[i % len(clip_ids)]
        rows.append([_P(s, size=6.3, bold=True, align=1, color=NAVY)] + [_P(cid, size=6, align=1)] * nd +
                    [_P(nd, size=6.2, bold=True, align=1, color=VIOLET)])
    rows.append([_P("Օրական", size=6, bold=True, align=1, color=W)] +
                [_P(len(slots), size=6, bold=True, align=1, color=W)] * nd + [""])
    tw, lw = 16 * mm, 10 * mm
    cw = max(3.6 * mm, min(6 * mm, (CONTENT_W - tw - lw) / nd))
    last = len(rows) - 1
    t = Table(rows, colWidths=[tw] + [cw] * nd + [lw], repeatRows=2)
    style = [("GRID", (0, 0), (-1, -1), 0.3, LINE),
             ("BACKGROUND", (0, 0), (-1, 0), VIOLET), ("BACKGROUND", (0, 1), (-1, 1), NAVY),
             ("SPAN", (1, 0), (nd, 0)), ("LINEBELOW", (0, 1), (-1, 1), 0, NAVY),
             ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
             ("TOPPADDING", (0, 0), (-1, -1), 1.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.2),
             ("LEFTPADDING", (0, 0), (-1, -1), 0.5), ("RIGHTPADDING", (0, 0), (-1, -1), 0.5),
             ("BACKGROUND", (0, 2), (0, last - 1), TINT), ("BACKGROUND", (-1, 2), (-1, last - 1), TINT),
             ("BACKGROUND", (0, last), (-1, last), NAVY)]
    for r in range(2, last):
        if r % 2 == 1:
            style.append(("BACKGROUND", (1, r), (nd, r), SOFT))
    t.setStyle(TableStyle(style))
    return t


def _kv(rows):
    """Ամփոփում՝ 4 «քարտ» կողք կողքի (վերջինը՝ ընդհանուր քանակը, ընդգծված)."""
    W = colors.white
    n = len(rows)
    top = [_P(k, size=6.8, color=W if i == n - 1 else MUTED) for i, (k, v, u) in enumerate(rows)]
    mid = [_P(f"{v} <font size=7>{u}</font>", size=14, bold=True, color=W if i == n - 1 else INK)
           for i, (k, v, u) in enumerate(rows)]
    gap = 3 * mm
    cw = (CONTENT_W - gap * (n - 1)) / n
    data, widths = [[], []], []
    for i in range(n):
        data[0].append(top[i])
        data[1].append(mid[i])
        widths.append(cw)
        if i < n - 1:
            data[0].append("")
            data[1].append("")
            widths.append(gap)
    t = Table(data, colWidths=widths)
    st = [("LEFTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, 0), 5),
          ("BOTTOMPADDING", (0, 1), (-1, 1), 6), ("VALIGN", (0, 0), (-1, -1), "TOP")]
    for i in range(n):
        c = i * 2
        if i == n - 1:
            st.append(("BACKGROUND", (c, 0), (c, 1), VIOLET))
        else:
            st += [("BACKGROUND", (c, 0), (c, 1), SOFT), ("LINEABOVE", (c, 0), (c, 0), 1.6, VIOLET)]
    t.setStyle(TableStyle(st))
    return t


def _clips_table(clips):
    """Ֆայլ՝ սեղմվող հղում (▶ Լսել MP3), որը բացում է MP3-ը (Google Drive / Telegram)."""
    from xml.sax.saxutils import escape
    W = colors.white
    rows = [[_P("N", size=7, bold=True, align=1, color=W), _P("Հոլովակի անվանում", size=7, bold=True, color=W),
             _P("Ֆայլ", size=7, bold=True, color=W, align=1)]]
    for c in clips:
        name = escape(str(c["name"]))
        link = c.get("link")
        if link:
            href = escape(link, {'"': "&quot;"})
            name_cell = _P(f'<a href="{href}" color="#1D1B5E"><b>{name}</b></a>', size=8)
            file_cell = _P(f'<a href="{href}" color="#6A3DE8"><u><b>▶ Լսել MP3</b></u></a>', size=8, align=1)
        else:
            name_cell = _P(f"<b>{name}</b>", size=8)
            file_cell = _P("—", size=8, color=MUTED, align=1)
        rows.append([_P(c["n"], size=8, bold=True, align=1, color=VIOLET), name_cell, file_cell])
    t = Table(rows, colWidths=[12 * mm, 128 * mm, 40 * mm], hAlign="LEFT")
    st = [("BACKGROUND", (0, 0), (-1, 0), NAVY), ("LINEBELOW", (0, 1), (-1, -1), 0.5, LINE),
          ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 4),
          ("BOTTOMPADDING", (0, 0), (-1, -1), 4), ("ROUNDEDCORNERS", [4, 4, 0, 0])]
    for r in range(1, len(rows)):
        if r % 2 == 0:
            st.append(("BACKGROUND", (0, r), (-1, r), SOFT))
    t.setStyle(TableStyle(st))
    return t


def _net_table(addrs):
    cnt = OrderedDict()
    for a in addrs:
        cnt[a["net"]] = cnt.get(a["net"], 0) + 1
    rows = [[_P("●", size=7, color=VIOLET, align=1), _P(n, size=8, bold=True),
             _P(f"<b>{c}</b> <font color='#6B7090'>հասցե</font>", size=8, align=2)] for n, c in cnt.items()]
    t = Table(rows, colWidths=[6 * mm, 144 * mm, 30 * mm], hAlign="LEFT")
    st = [("LINEBELOW", (0, 0), (-1, -1), 0.5, LINE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
          ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5)]
    t.setStyle(TableStyle(st))
    return t


def _addr_table(addrs, multi_clip):
    W = colors.white
    head = [_P("N", size=7, bold=True, align=1, color=W), _P("Հասցե", size=7, bold=True, color=W)]
    if multi_clip:
        head.append(_P("Հոլովակ №", size=7, bold=True, align=1, color=W))
    rows, styles, cur, n, zebra = [head], [], None, 0, 0
    for a in addrs:
        if a["net"] != cur:
            cur, n, zebra = a["net"], 0, 0
            idx = len(rows)
            rows.append([_P(cur, size=8, bold=True, color=VIOLET)] + [""] * (len(head) - 1))
            styles += [("SPAN", (0, idx), (-1, idx)), ("BACKGROUND", (0, idx), (-1, idx), TINT),
                       ("TOPPADDING", (0, idx), (-1, idx), 4), ("BOTTOMPADDING", (0, idx), (-1, idx), 4)]
        n += 1
        zebra += 1
        row = [_P(n, size=7.5, align=1, color=MUTED), _P(a["addr"], size=7.5)]
        if multi_clip:
            row.append(_P(", ".join(map(str, a["clips"])), size=7.5, bold=True, align=1, color=VIOLET))
        if zebra % 2 == 0:
            styles.append(("BACKGROUND", (0, len(rows)), (-1, len(rows)), SOFT))
        rows.append(row)
    widths = [12 * mm, (143 if multi_clip else 168) * mm] + ([25 * mm] if multi_clip else [])
    t = Table(rows, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), NAVY), ("LINEBELOW", (0, 1), (-1, -1), 0.4, LINE),
                           ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                           ("TOPPADDING", (0, 0), (-1, -1), 2.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2)] + styles))
    return t


def _total_bar(text):
    t = Table([[_P(text, size=10, bold=True, color=colors.white)]], colWidths=[CONTENT_W])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), VIOLET), ("LEFTPADDING", (0, 0), (-1, -1), 9),
                           ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                           ("ROUNDEDCORNERS", [4, 4, 4, 4])]))
    return t


# ------------------------------------------------------------------ main
def make_plan(data, out_path):
    """
    data = {client, start: date, end: date, slots: ['10:00', ...],
            addresses: [{net, addr, clips:[1,2]}], clips: [{n, name, file, link}]}
    """
    _fonts()
    days = [data["start"] + timedelta(i) for i in range((data["end"] - data["start"]).days + 1)]
    slots, client = data["slots"], data["client"]
    groups = OrderedDict()
    for a in data["addresses"]:
        groups.setdefault(tuple(sorted(a["clips"])), []).append(a)
    by_n = {c["n"]: c for c in data["clips"]}
    # Frame-ի 6pt ներքին լուսանցքը հաշվի առած՝ բովանդակության լայնությունը ճիշտ 180 մմ է
    doc = SimpleDocTemplate(str(out_path), pagesize=A4, leftMargin=15 * mm - 6, rightMargin=15 * mm - 6,
                            topMargin=12 * mm - 6, bottomMargin=15 * mm - 6, title=f"Media plan — {client}")
    story = []
    total_all = 0
    for key, addrs in sorted(groups.items()):
        story.append(_header("Աուդիոհոլովակների հեռարձակում", client, data["start"], data["end"]))
        story += [_section("Ցանցեր և հասցեներ"), _net_table(addrs), _section("Հեռարձակման գրաֆիկ")]
        # երկար ժամկետ՝ գրաֆիկը բաժանվում է ըստ ամիսների (յուրաքանչյուրը ≤ 31 սյունակ)
        for i, chunk in enumerate(_by_month(days)):
            if i:   # յուրաքանչյուր հաջորդ ամիսը՝ նոր թերթի վրա
                story += [PageBreak(), _section("Հեռարձակման գրաֆիկ")]
            story.append(_grid(slots, chunk, [str(k) for k in key]))
        total = len(days) * len(slots) * len(addrs)
        total_all += total
        story += [Spacer(1, 7), _kv([("Օրերի քանակ", len(days), "օր"), ("Հասցեների քանակ", len(addrs), "մասնաճյուղ"),
                                     ("Օրական հեռարձակումների քանակ", len(slots), "սփոթ"),
                                     ("Հեռարձակումների ընդհանուր քանակ", f"{total:,}".replace(",", " "), "սփոթ")]),
                  _section("Հոլովակներ"), _clips_table([by_n[k] for k in key if k in by_n]),
                  Spacer(1, 4), _P("Աղյուսակում թիվը ցույց է տալիս տվյալ ժամին հեռարձակվող հոլովակի համարը: "
                                   "Սեղմեք «▶ Լսել MP3»՝ հոլովակը լսելու համար:", size=6.8, color=MUTED),
                  PageBreak()]
    story.append(_header("Աուդիոհոլովակների հեռարձակման հասցեները", client, data["start"], data["end"]))
    story += [Spacer(1, 8), _addr_table(data["addresses"], len(data["clips"]) > 1), Spacer(1, 8),
              _total_bar(f"Ընդհանուր հեռարձակումներ՝ {total_all:,} սփոթ".replace(",", " "))]
    # վերջում՝ Mix Media-ի ստորագրությունը և կնիքը (նույնը, ինչ ԱԿՏ-ում. assets/signature.png, assets/stamp.png)
    import actpdf
    story += [Spacer(1, 18), _section("Ստորագրություն և կնիք"),
              actpdf._signatures(client, data.get("sign_date") or date.today(), data.get("seal", True))]
    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    return Path(out_path)
