# -*- coding: utf-8 -*-
"""DOCX -> տպելու պատրաստ HTML (որպեսզի տպելը աշխատի նաև առանց LibreOffice-ի/Word-ի).

Պահպանվում է՝ պարբերությունների հավասարեցումը, թավ/շեղ/ընդգծված, աղյուսակները, ցանկերը."""
import html
from pathlib import Path

ALIGN = {0: "left", 1: "center", 2: "right", 3: "justify", None: ""}
CSS = """
@page { size: A4; margin: 18mm 16mm; }
:root { --ink:#12152E; --muted:#6B7090; --line:#DDE0EE; --violet:#6A3DE8; --navy:#1D1B5E; }
* { box-sizing: border-box; }
body { margin:0; background:#F2F3F8; color:var(--ink);
       font-family: Sylfaen, "Segoe UI", "Noto Sans Armenian", Arial, sans-serif; font-size:11pt; }
.sheet { width:210mm; min-height:297mm; margin:14px auto; padding:18mm 16mm; background:#fff;
         box-shadow:0 10px 30px rgba(18,21,46,.12); }
p { margin:0 0 6pt; line-height:1.45; }
p.empty { margin:0 0 10pt; }
h1,h2,h3 { color:var(--navy); margin:12pt 0 6pt; line-height:1.3; }
h1 { font-size:16pt; } h2 { font-size:14pt; } h3 { font-size:12pt; }
table { border-collapse:collapse; width:100%; margin:8pt 0 12pt; font-size:10pt; }
td, th { border:1px solid var(--line); padding:4pt 6pt; vertical-align:top; }
thead td, thead th, tr:first-child td.hdr { background:#DDEBF7; font-weight:700; }
.docx-toolbar { position:sticky; top:0; display:flex; gap:8px; justify-content:center; padding:10px;
                background:#fff; border-bottom:1px solid var(--line); }
.docx-toolbar button { font:inherit; font-size:13px; padding:8px 16px; border-radius:10px; cursor:pointer;
                border:1px solid var(--line); background:#fff; color:var(--ink); }
.docx-toolbar button.primary { background:linear-gradient(135deg,#2E8CF0,#6A3DE8); color:#fff; border:0; }
@media print { body { background:#fff; } .sheet { width:auto; min-height:0; margin:0; padding:0; box-shadow:none; }
               .docx-toolbar { display:none; } }
"""


def _runs_html(p):
    out = []
    for r in p.runs:
        t = html.escape(r.text).replace("\n", "<br>")
        if not t:
            continue
        if r.font and r.font.size and r.font.size.pt and r.font.size.pt >= 14:
            t = f'<span style="font-size:{r.font.size.pt:.0f}pt">{t}</span>'
        if r.underline:
            t = f"<u>{t}</u>"
        if r.italic:
            t = f"<em>{t}</em>"
        if r.bold:
            t = f"<strong>{t}</strong>"
        out.append(t)
    return "".join(out) or html.escape(p.text)


def _par_html(p):
    style = (p.style.name if p.style is not None else "") or ""
    inner = _runs_html(p)
    if not inner.strip():
        return '<p class="empty">&nbsp;</p>'
    align = ALIGN.get(p.alignment.real if hasattr(p.alignment, "real") else p.alignment, "")
    attr = f' style="text-align:{align}"' if align else ""
    low = style.lower()
    if low.startswith("heading 1") or low.startswith("title"):
        return f"<h1{attr}>{inner}</h1>"
    if low.startswith("heading 2"):
        return f"<h2{attr}>{inner}</h2>"
    if low.startswith("heading 3"):
        return f"<h3{attr}>{inner}</h3>"
    if "list" in low:
        return f'<p{attr} style="margin-left:14pt">• {inner}</p>'
    return f"<p{attr}>{inner}</p>"


def _table_html(t):
    rows = []
    for ri, row in enumerate(t.rows):
        cells, seen = [], set()
        for c in row.cells:
            if id(c._tc) in seen:
                continue
            seen.add(id(c._tc))
            body = "".join(_par_html(p) for p in c.paragraphs) or "&nbsp;"
            cls = ' class="hdr"' if ri == 0 else ""
            cells.append(f"<td{cls}>{body}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return "<table>" + "".join(rows) + "</table>"


def body_html(path):
    """DOCX-ի բովանդակությունը՝ HTML (առանց <html> պատյանի)."""
    import docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    doc = docx.Document(str(path))
    parts = []
    for el in doc.element.body.iterchildren():
        tag = el.tag.split("}")[-1]
        if tag == "p":
            parts.append(_par_html(Paragraph(el, doc)))
        elif tag == "tbl":
            parts.append(_table_html(Table(el, doc)))
    return "".join(parts)


def page_html(path, title=None, toolbar=True):
    """Ամբողջական էջ՝ «Տպել» կոճակով (բրաուզերի տպիչով, առանց լրացուցիչ ծրագրերի)."""
    title = html.escape(title or Path(path).stem)
    bar = ('<div class="docx-toolbar">'
           '<button class="primary" onclick="window.print()">🖨 Տպել / Печать</button>'
           '<button onclick="window.close()">✕ Փակել</button></div>'
           '<script>if (location.search.indexOf("auto=1") >= 0) '
           'window.addEventListener("load", function(){ setTimeout(function(){ window.print(); }, 350); });'
           '</script>') if toolbar else ""
    return (f"<!doctype html><html lang='hy'><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{title}</title><style>{CSS}</style></head><body>{bar}"
            f"<div class='sheet'>{body_html(path)}</div></body></html>")
