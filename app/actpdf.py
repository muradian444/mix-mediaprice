# -*- coding: utf-8 -*-
"""ԱԿՏ-ի PDF՝ Mix Media ֆիրմային դիզայնով (լոգո, գրադիենտ, նույն ոճը, ինչ մեդիա պլանում և ԿՊ-ում)."""
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import Flowable, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

import mediaplan as mp
from mediaplan import (BLUE, CONTENT_W, INK, LINE, MUTED, NAVY, SOFT, TINT, VIOLET, _GradBar, _P, _fonts,
                       _logo_flowable, _on_page, _section, fmt)

GREEN, RED = colors.HexColor("#1E9E6A"), colors.HexColor("#D64545")


def _n(v):
    return f"{int(v):,}".replace(",", " ")


def _t(s, **kw):
    return _P(escape(str(s)), **kw)


def _pct(played, planned, digits=1):
    return f"{100 * played / planned:.{digits}f}%" if planned else "—"


BASE = Path(__file__).resolve().parent.parent
SIGN_IMG, STAMP_IMG = BASE / "assets" / "signature.png", BASE / "assets" / "stamp.png"


def _image(path, max_w, max_h, align="RIGHT"):
    """Լոգո (PNG/JPG/SVG)՝ համամասնությունը պահպանելով max_w × max_h-ի մեջ. Չհաջողվեց -> None."""
    from reportlab.platypus import Image
    path = Path(path)
    try:
        if path.suffix.lower() == ".svg":
            from svglib.svglib import svg2rlg
            d = svg2rlg(str(path))
            if d is None or not d.width or not d.height:
                return None
            k = min(max_w / d.width, max_h / d.height)
            d.scale(k, k)
            d.width, d.height = d.width * k, d.height * k
            d.hAlign = align
            return d
        from PIL import Image as PILImage
        w, h = PILImage.open(path).size
        k = min(max_w / w, max_h / h)
        img = Image(str(path), width=w * k, height=h * k)
        img.hAlign = align
        return img
    except Exception:  # noqa — վնասված/չաջակցվող լոգոն չի կոտրում ԱԿՏ-ը
        return None


def _header(client, contract, start, end, store_logo=None):
    logo = _logo_flowable(36 * mm)
    right = _image(store_logo, 52 * mm, 20 * mm) if store_logo else None
    if right is None and store_logo:    # լոգոն չբացվեց՝ գրում ենք պատվիրատուի անունը
        right = _t(client, size=11, bold=True, color=NAVY, align=2)
    elif right is None:                 # խանութ ընտրված չէ՝ ընկերության տվյալները
        right = Table([[_P("«Միքս Մեդիա» ՍՊԸ", size=8.5, bold=True, align=2)],
                       [_P("ՀՀ, ք. Երևան, Լևոնյան 48", size=7.5, color=MUTED, align=2)],
                       [_P("Հեռ.՝ +374 44 702 703", size=7.5, color=MUTED, align=2)]], colWidths=[80 * mm])
    top = Table([[logo, right]], colWidths=[100 * mm, 80 * mm])
    top.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                             ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("ALIGN", (1, 0), (1, 0), "RIGHT")]))
    chip = Table([[_P("ԱԿՏ", size=6.8, bold=True, color=VIOLET, align=1)]], colWidths=[18 * mm])
    chip.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.8, VIOLET), ("ROUNDEDCORNERS", [3, 3, 3, 3]),
                              ("TOPPADDING", (0, 0), (-1, -1), 1.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    chip.hAlign = "LEFT"
    days = (end - start).days + 1
    strip = Table([[_P("ՊԱՏՎԻՐԱՏՈՒ", size=6.3, bold=True, color=MUTED),
                    _P("ՀԱՇՎԵՏՎՈՒ ԺԱՄԱՆԱԿԱՀԱՏՎԱԾ", size=6.3, bold=True, color=MUTED),
                    _P("ՊԱՅՄԱՆԱԳԻՐ №", size=6.3, bold=True, color=MUTED),
                    _P("ՕՐԵՐ", size=6.3, bold=True, color=MUTED)],
                   [_t(client, size=10.5, bold=True), _t(f"{fmt(start)} — {fmt(end)}", size=10.5, bold=True),
                    _t(contract, size=10.5, bold=True), _P(str(days), size=10.5, bold=True, color=VIOLET)]],
                  colWidths=[66 * mm, 64 * mm, 32 * mm, 18 * mm])
    strip.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), SOFT), ("LINEBEFORE", (0, 0), (0, -1), 2.2, VIOLET),
                               ("LINEAFTER", (0, 0), (2, -1), 0.5, colors.HexColor("#D9D2FB")),
                               ("LEFTPADDING", (0, 0), (-1, -1), 7), ("TOPPADDING", (0, 0), (-1, 0), 5),
                               ("BOTTOMPADDING", (0, -1), (-1, -1), 6), ("ROUNDEDCORNERS", [4, 4, 4, 4])]))
    return KeepTogether([top, Spacer(1, 4), _GradBar(CONTENT_W), Spacer(1, 7), chip, Spacer(1, 3),
                         _P("Հեռարձակման հաշվետվություն", size=15, bold=True, leading=19), Spacer(1, 5), strip])


def _table(head, rows, widths_mm, aligns=None, total=None, size=7.8):
    """Ընդհանուր աղյուսակ՝ մուգ վերնագիր, զեբրա, (ըստ ցանկության) մանուշակագույն «Ընդամենը» տող."""
    W = colors.white
    aligns = aligns or [0] * len(head)
    data = [[_P(h, size=7, bold=True, color=W, align=aligns[i]) for i, h in enumerate(head)]]
    for r in rows:
        data.append([c if isinstance(c, Paragraph) else _t(c, size=size, align=aligns[i]) for i, c in enumerate(r)])
    if total:
        data.append([_t(c, size=size, bold=True, color=W, align=aligns[i]) for i, c in enumerate(total)])
    t = Table(data, colWidths=[w * mm for w in widths_mm], repeatRows=1)
    last = len(data) - 1
    st = [("BACKGROUND", (0, 0), (-1, 0), NAVY), ("LINEBELOW", (0, 1), (-1, -1), 0.4, LINE),
          ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 3),
          ("BOTTOMPADDING", (0, 0), (-1, -1), 3), ("LEFTPADDING", (0, 0), (-1, -1), 4),
          ("RIGHTPADDING", (0, 0), (-1, -1), 4)]
    for r in range(1, last + (0 if total else 1)):
        if r % 2 == 0:
            st.append(("BACKGROUND", (0, r), (-1, r), SOFT))
    if total:
        st += [("BACKGROUND", (0, last), (-1, last), VIOLET), ("ROUNDEDCORNERS", [0, 0, 4, 4])]
    else:
        st.append(("ROUNDEDCORNERS", [4, 4, 0, 0]))
    t.setStyle(TableStyle(st))
    return t


class _SignBox(Flowable):
    """Կողմի ստորագրության բլոկ՝ վերնագիր, ստորագրության գիծ և կնիքի տեղ (կետագծային շրջան «Կ.Տ.»).
    Եթե տրված են նկարներ՝ դրանք դրվում են տեղում (ստորագրություն գծի վրա, կնիք շրջանի մեջ)."""

    def __init__(self, title, name, width=87 * mm, height=46 * mm, sign=None, stamp=None):
        super().__init__()
        self.title, self.name, self.width, self.height, self.sign, self.stamp = title, name, width, height, sign, stamp

    def _img(self, path, x, y, w_max, h_max):
        from PIL import Image as PILImage
        w, h = PILImage.open(path).size
        k = min(w_max / w, h_max / h)
        self.canv.drawImage(str(path), x, y, w * k, h * k, mask="auto")

    def draw(self):
        c = self.canv
        c.saveState()
        c.setFillColor(NAVY)
        c.setFont("MM-B", 8.5)
        c.drawString(0, self.height - 3 * mm, self.title)
        c.setFillColor(MUTED)
        c.setFont("MM", 7.5)
        c.drawString(0, self.height - 7.6 * mm, self.name[:62])
        # կնիքի տեղ
        d = 30 * mm
        cx, cy = 17 * mm, 19 * mm
        c.setStrokeColor(colors.HexColor("#B8BCD6"))
        c.setLineWidth(0.8)
        c.setDash(2.2, 2.2)
        c.circle(cx, cy, d / 2, stroke=1, fill=0)
        c.setDash()
        if self.stamp:
            self._img(self.stamp, cx - 17 * mm, cy - 16 * mm, 34 * mm, 32 * mm)
        else:
            c.setFillColor(colors.HexColor("#B8BCD6"))
            c.setFont("MM-B", 9)
            c.drawCentredString(cx, cy - 1.5 * mm, "Կ.Տ.")
        # ստորագրության գիծ
        x0, x1, y = 38 * mm, self.width, 10 * mm
        c.setStrokeColor(MUTED)
        c.setLineWidth(0.6)
        c.line(x0, y, x1, y)
        c.setFillColor(MUTED)
        c.setFont("MM", 6.8)
        c.drawString(x0, y - 3.4 * mm, "Ստորագրություն")
        if self.sign:
            self._img(self.sign, x0 + 6 * mm, y + 0.6 * mm, 28 * mm, 15 * mm)
        c.restoreState()


def _signatures(client, today, seal=True):
    """Միայն կատարողի (Mix Media) ստորագրությունը և կնիքը՝ պատվիրատուի բլոկ չկա."""
    left = _SignBox("ԿԱՏԱՐՈՂ", "«Միքս Մեդիա» ՍՊԸ", sign=SIGN_IMG if seal and SIGN_IMG.exists() else None,
                    stamp=STAMP_IMG if seal and STAMP_IMG.exists() else None)
    t = Table([[left, ""]], colWidths=[93 * mm, 87 * mm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                           ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    date_line = _P(f"Ամսաթիվ՝ <b>{fmt(today)}</b>", size=8, color=MUTED)
    return KeepTogether([t, Spacer(1, 2), date_line])


def off_rows(by_addr):
    """Անջատումները՝ ամեն ամսաթիվը առանձին տողով.
    -> [{n, addr, date, hours, missed}] (հասցեն՝ միայն իր առաջին տողում, n՝ հասցեի համարը)."""
    import monitor
    out, n = [], 0
    for a in by_addr or []:
        if not a.get("off_hours") and not a.get("off_list"):
            continue
        lst = [r for r in a.get("off_list") or [] if r.get("hours") or r.get("full")]
        n += 1
        if not lst:     # հին ձևաչափ՝ միայն տեքստ
            out.append(dict(n=n, addr=a["addr"], date="", hours=a.get("off_detail") or "",
                            missed=a.get("missed") or 0, first=True))
            continue
        per_h = (a.get("missed") or 0) / a["off_hours"] if a.get("off_hours") else monitor.MIN_PER_HOUR
        for i, r in enumerate(lst):
            hrs = r.get("hours") or []
            txt = monitor.hour_ranges(hrs)
            if r.get("full"):
                txt = f"ամբողջ օրը ({txt})" if txt else "ամբողջ օրը"
            out.append(dict(n=n, addr=a["addr"], date=r.get("date") or "", hours=txt,
                            missed=r.get("missed") or round(per_h * len(hrs)), first=i == 0))
    return out


def _off_table(rows):
    """N | Հասցե | Ամսաթիվ | Անջատված ժամերը | Չհեռ. — հասցեները խմբերով (գոտիավոր ֆոն ամեն հասցեի համար)."""
    W = colors.white
    head = ["N", "Հասցե", "Ամսաթիվ", "Անջատված ժամերը", "Չհեռ."]
    aligns = [1, 0, 1, 0, 2]
    data = [[_P(h, size=7, bold=True, color=W, align=aligns[i]) for i, h in enumerate(head)]]
    st = [("BACKGROUND", (0, 0), (-1, 0), NAVY), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
          ("TOPPADDING", (0, 0), (-1, -1), 2.6), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.6),
          ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
          ("ROUNDEDCORNERS", [4, 4, 0, 0])]
    for r in rows:
        i = len(data)
        data.append([_t(r["n"] if r["first"] else "", size=7.6, bold=True, color=VIOLET, align=1),
                     _t(r["addr"] if r["first"] else "", size=7.6, bold=True),
                     _t(r["date"], size=7.6, align=1),
                     _t(r["hours"], size=7.6),
                     _t(_n(r["missed"]), size=7.6, bold=True, color=RED, align=2)])
        if r["first"] and i > 1:
            st.append(("LINEABOVE", (0, i), (-1, i), 0.7, colors.HexColor("#C9C2F2")))
        elif not r["first"]:
            st.append(("LINEABOVE", (2, i), (-1, i), 0.3, LINE))
        if r["n"] % 2 == 0:
            st.append(("BACKGROUND", (0, i), (-1, i), SOFT))
    st.append(("LINEBELOW", (0, len(data) - 1), (-1, len(data) - 1), 0.7, colors.HexColor("#C9C2F2")))
    t = Table(data, colWidths=[w * mm for w in (9, 66, 24, 63, 18)], repeatRows=1)
    t.setStyle(TableStyle(st))
    return t


def make_pdf(client, contract, start, end, days, clips, by_addr, out_path, logo=None, seal=True, hours=None):
    """days՝ OrderedDict{date: {planned, played, missed}}, clips՝ {name: played}, by_addr՝ [dict(addr, planned,
    missed, off_hours, off_detail, ...)], hours՝ [{hour, label, planned, played, missed}] (հաշվարկ ըստ ԺԱՄԵՐԻ).
    logo՝ խանութի լոգոյի ֆայլը (վերևում աջից), seal՝ դնել Mix Media-ի ստորագրությունը և կնիքը. -> Path."""
    _fonts()
    planned = sum(v["planned"] for v in days.values())
    played = sum(v["played"] for v in days.values())
    missed = max(planned - played, 0)
    doc = SimpleDocTemplate(str(out_path), pagesize=A4, leftMargin=15 * mm - 6, rightMargin=15 * mm - 6,
                            topMargin=12 * mm - 6, bottomMargin=15 * mm - 6, title=f"ԱԿՏ — {client}")
    kv = [("Նախատեսված հեռարձակում", _n(planned), "սփոթ"), ("Փաստացի հեռարձակված", _n(played), "սփոթ"),
          ("Չհեռարձակված", _n(missed), "սփոթ"), ("Կատարում", _pct(played, planned), "")]
    story = [_header(client, contract, start, end, logo), Spacer(1, 8), mp._kv(kv)]

    if by_addr:   # առաջինը՝ երբ է գովազդն անջատված եղել՝ հասցե | օր | ժամեր (առանձին սյունակներով)
        rows = off_rows(by_addr)
        n_off = len({r["n"] for r in rows})
        story.append(_section("Գովազդի անջատումները՝ ըստ հասցեների և օրերի"))
        if rows:
            story += [_off_table(rows), Spacer(1, 4),
                      _P(f"Անջատումներ գրանցվել է <b>{n_off}</b> հասցեում՝ ընդհանուր {len(by_addr)} հասցեից: "
                         "«Չհեռ.»՝ տվյալ օրը չհեռարձակված սփոթների քանակը:", size=6.8, color=MUTED)]
        else:
            story.append(_P("Ընտրված ժամանակահատվածում անջատումներ չեն գրանցվել ✓", size=8.5, bold=True, color=GREEN))
        arows = [[i, a["addr"], _n(a["planned"]), _n(a["planned"] - a["missed"]),
                  _t(_n(a["missed"]), size=7.8, align=2, color=RED if a["missed"] else INK),
                  _pct(a["planned"] - a["missed"], a["planned"], 0)]
                 for i, a in enumerate(by_addr, 1)]
        story += [_section("Ըստ հասցեների"),
                  _table(["N", "Հասցե", "Նախատեսված", "Հեռարձակված", "Չհեռարձակված", "Կատարում"], arows,
                         [10, 78, 22, 24, 26, 20], [1, 0, 2, 2, 2, 2])]

    if hours:
        hp = sum(h["planned"] for h in hours)
        hm = min(sum(h["missed"] for h in hours), hp)
        ha = hp - hm
        rows = [[h["label"], _n(h["planned"]), _n(h["played"]),
                 _t(_n(h["missed"]), size=7.8, align=2, color=RED if h["missed"] else INK),
                 _pct(h["played"], h["planned"], 0)] for h in hours]
        story += [_section("Ըստ ժամերի (ամբողջ ժամանակահատվածի համար)"),
                  _table(["Ժամ", "Նախատեսված", "Հեռարձակված", "Չհեռարձակված", "Կատարում"], rows,
                         [40, 36, 36, 38, 30], [0, 2, 2, 2, 2],
                         total=["Ընդամենը", _n(hp), _n(ha), _n(hm), _pct(ha, hp)])]
    else:          # ֆայլում ժամեր չկան՝ օրերով
        rows = []
        for d, v in days.items():
            miss = max(v["planned"] - v["played"], 0)
            rows.append([fmt(d), _n(v["planned"]), _n(v["played"]),
                         _t(_n(miss), size=7.8, align=2, color=RED if miss else INK), _pct(v["played"], v["planned"], 0)])
        story += [_section("Ըստ օրերի"),
                  _table(["Օր", "Նախատեսված", "Հեռարձակված", "Չհեռարձակված", "Կատարում"], rows,
                         [40, 36, 36, 38, 30], [0, 2, 2, 2, 2],
                         total=["Ընդամենը", _n(planned), _n(played), _n(missed), _pct(played, planned)])]

    if clips:
        story += [_section("Ըստ հոլովակների (հեռարձակված)"),
                  _table(["Հոլովակ", "Հեռարձակված"], [[k, _n(v)] for k, v in clips.items()], [140, 40], [0, 2])]

    story += [Spacer(1, 16), _signatures(client, date.today(), seal)]
    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    return Path(out_path)
