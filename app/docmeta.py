# -*- coding: utf-8 -*-
"""Պատրաստված փաստաթղթի մեջ թաքնված տվյալներ (ինչ լրացվել էր ձևում).

Պայմանագրի DOCX-ը, մեդիա պլանի / ԱԿՏ-ի / ԿՊ-ի PDF-ը իրենց մեջ պահում են մուտքագրված դաշտերը:
«✏️ Изменить» բաժնում այդ ֆայլը վերբեռնելիս ձևը բացվում է նույն տվյալներով՝ փոխում ես և նորից ստեղծում:"""
import base64
import json
import zlib
from pathlib import Path

PREFIX = "mixmedia:v1:"
PDF_KEY = "/MixMediaData"
DOCX_REL = "http://schemas.mix-media.am/relationships/formdata"
DOCX_PART = "/mixmedia/formdata.txt"


def pack(payload):
    raw = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
    return PREFIX + base64.b64encode(zlib.compress(raw, 9)).decode("ascii")


def unpack(s):
    s = str(s or "").strip()
    if not s.startswith(PREFIX):
        return None
    try:
        return json.loads(zlib.decompress(base64.b64decode(s[len(PREFIX):])).decode("utf-8"))
    except Exception:  # noqa — վնասված տվյալ՝ անտեսում ենք
        return None


def _docx_part(d):
    for rel in d.part.rels.values():
        if rel.reltype == DOCX_REL and not rel.is_external:
            return rel, rel.target_part
    return None, None


def embed_docx(path, payload):
    """DOCX-ի ներսում՝ առանձին մաս (/mixmedia/formdata.txt). Word-ում անտեսանելի է:
    (core_properties.comments-ը սահմանափակված է 255 նշանով՝ ձևի տվյալները այնտեղ չեն տեղավորվում)."""
    try:
        import docx
        from docx.opc.packuri import PackURI
        from docx.opc.part import Part
        d = docx.Document(str(path))
        blob = pack(payload).encode("ascii")
        rel, part = _docx_part(d)
        if part is not None:
            part._blob = blob
        else:
            part = Part(PackURI(DOCX_PART), "text/plain", blob, d.part.package)
            d.part.relate_to(part, DOCX_REL)
        d.save(str(path))
        return True
    except Exception:  # noqa — տվյալը պարտադիր չէ, ֆայլը մնում է
        return False


def clear_docx(d):
    """Ձեռքով խմբագրված DOCX՝ ձևի հին տվյալները հանվում են (python-docx Document օբյեկտ)."""
    try:
        rel, part = _docx_part(d)
        if rel is not None:
            d.part.drop_rel(rel.rId)
    except Exception:  # noqa
        pass


def read_docx(d):
    try:
        rel, part = _docx_part(d)
        if part is not None:
            return unpack(part.blob.decode("ascii", "ignore"))
        return unpack(d.core_properties.comments)
    except Exception:  # noqa
        return None


def embed_pdf(path, payload):
    try:
        from pypdf import PdfWriter
        w = PdfWriter(clone_from=str(path))
        w.add_metadata({PDF_KEY: pack(payload)})
        tmp = Path(path).with_suffix(".meta.tmp")
        with open(tmp, "wb") as f:
            w.write(f)
        tmp.replace(path)
        return True
    except Exception:  # noqa
        return False


def embed(path, payload):
    ext = Path(path).suffix.lower()
    if ext == ".docx":
        return embed_docx(path, payload)
    if ext == ".pdf":
        return embed_pdf(path, payload)
    return False


def read(path):
    """-> payload dict կամ None."""
    p = Path(path)
    ext = p.suffix.lower()
    try:
        if ext == ".docx":
            import docx
            return read_docx(docx.Document(str(p)))
        if ext == ".pdf":
            from pypdf import PdfReader
            info = PdfReader(str(p)).metadata or {}
            return unpack(info.get(PDF_KEY))
    except Exception:  # noqa
        return None
    return None
