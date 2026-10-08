# -*- coding: utf-8 -*-
"""📷 Լուսանկար / սկան -> ձևի դաշտեր — ԱՄԲՈՂՋՈՒԹՅԱՄԲ ՏԵՂԱՅԻՆ (без облака и без API-ключей).

Ցանկացած բաժնում «📷 Из фото» կոճակը ուղարկում է նկարը (կամ PDF/Word/Excel) և դաշտերի ցանկը:
  1. ocr.py       — տեքստը՝ Tesseract OCR-ով (հայ/ռուս/անգլ) կամ ուղղակի ֆայլից (Word, Excel, PDF)
  2. fieldparse.py — դաշտերը՝ կանոններով (ՀՎՀՀ, հաշիվ, բանկ, տնօրեն, հասցե, ամսաթվեր, գումարներ…)
  3. localai.py   — եթե տեղադրված է Ollama (տեղային ԻԻ), այն ճշգրտում է դաշտերը, իսկ կանոնները ստուգում են
Ոչինչ չի ուղարկվում ինտերնետ:"""
import logging
import re
from pathlib import Path

import fieldparse
import localai
import ocr

log = logging.getLogger("mixmedia")
IMAGE_EXT = ocr.IMAGE_EXT + (".heic", ".heif")
SUPPORTED = ocr.IMAGE_EXT + ocr.TEXT_EXT
MAX_TEXT = 180_000
TYPES = ("string", "text", "date", "number", "list", "table", "enum")


def status():
    o = ocr.status()
    ai = localai.status()
    return dict(ready=o["ready"], engine="local", ocr=o, local_ai=ai,
                mode="ollama" if ai["ready"] else "rules",
                # հին էջերի համատեղելիության համար
                library=o["tesseract"], key=False, source="", key_hint="", model=ai["model"] if ai["ready"] else "")


# ================================================================== սխեմա
def clean_fields(fields):
    out = []
    for f in fields or []:
        if not isinstance(f, dict):
            continue
        key = re.sub(r"[^A-Za-z0-9_]", "_", str(f.get("key") or ""))[:60]
        if not key or any(x["key"] == key for x in out):
            continue
        ty = f.get("type") if f.get("type") in TYPES else "string"
        opts = [str(o) for o in (f.get("options") or []) if str(o).strip()][:60]
        if ty == "enum" and not opts:
            ty = "string"
        out.append(dict(key=key, type=ty, label=str(f.get("label") or key)[:200], hint=str(f.get("hint") or "")[:600],
                        options=opts))
    if not out:
        raise ValueError("Դաշտերի ցանկը դատարկ է / Нет полей для заполнения")
    return out[:60]


def schema(fields):
    props = {}
    for f in fields:
        if f["type"] == "list":
            props[f["key"]] = {"type": "array", "items": {"type": "string"}}
        elif f["type"] == "table":
            props[f["key"]] = {"type": "array", "items": {"type": "array", "items": {"type": "string"}}}
        elif f["type"] == "enum":
            props[f["key"]] = {"type": "string", "enum": f["options"] + [""]}
        else:
            props[f["key"]] = {"type": "string"}
    return {"type": "object", "properties": props, "required": list(props)}


def _norm_value(f, v):
    if f["type"] == "list":
        return [re.sub(r"\s+", " ", str(x)).strip() for x in (v or []) if str(x).strip()] if isinstance(v, list) else []
    if f["type"] == "table":
        return [[str(c).strip() for c in (r or [])] for r in (v or []) if isinstance(r, list)
                and any(str(c).strip() for c in r)] if isinstance(v, list) else []
    return str(v or "").strip()


# ================================================================== գլխավոր
def read_text(path):
    text = ocr.file_text(path)
    if not text.strip():
        raise ValueError("Փաստաթղթում տեքստ չգտնվեց / В документе не найден текст — сфотографируйте ровнее и ярче")
    if len(text) > MAX_TEXT:
        text = text[:MAX_TEXT]
    return text


def extract(path, fields, section="", note=""):
    """-> {key: value} (միայն գտնված արժեքները)."""
    fields = clean_fields(fields)
    if Path(path).suffix.lower() in (".heic", ".heif"):
        raise ValueError("HEIC-ը պահեք JPG / Сохраните фото HEIC как JPG")
    text = read_text(path)
    rules = fieldparse.fill(text, fields)
    ai = {}
    if localai.status()["ready"]:
        try:
            ai = localai.fill(text, fields, section, note, schema(fields))
        except RuntimeError as e:
            log.warning("local AI failed, rules only: %s", e)
    out = {}
    for f in fields:
        k = f["key"]
        a = _norm_value(f, ai.get(k))
        r = rules.get(k)
        a_ok = fieldparse.valid(f, a) and (f["type"] != "enum" or a in f["options"])
        if fieldparse.kind_of(f) in fieldparse.STRICT:
            v = r or (a if a_ok else "")          # ձևաչափով դաշտեր՝ կանոնը վստահելի է
        else:
            v = (a if a_ok else "") or r          # ազատ տեքստ՝ ԻԻ-ն ավելի լավ է հասկանում
        if v:
            out[k] = v
    return out


def paragraphs(path):
    """Սկան/նկար -> խմբագրելի պարբերություններ (Изменить, Юрист)."""
    text = read_text(path)
    pars, cur = [], []
    for ln in text.split("\n"):
        ln = ln.strip()
        if not ln:
            if cur:
                pars.append(" ".join(cur))
                cur = []
            continue
        cur.append(ln)
    if cur:
        pars.append(" ".join(cur))
    return pars


# ================================================================== հասցեների համընկնում (մեդիա պլան)
def match_addresses(lines):
    """Ճանաչված հասցեները -> Կարգավորումների ցանցերի հասցեները.
    -> (matched [{query, net, addr, net_name, address}], unmatched [str])."""
    import monitor
    import store
    nets = store.networks()
    known = []
    for ni, n in enumerate(nets):
        for ai, a in enumerate(n["addresses"]):
            nums, words = monitor._tokens(a + " " + n["name"])
            known.append((ni, ai, n["name"], a, set(nums), {x.split("/")[0] for x in nums}, words))
    matched, unmatched, used = [], [], set()
    for q in lines or []:
        q = str(q or "").strip()
        if not q:
            continue
        nums, words = monitor._tokens(q)
        nbase = {x.split("/")[0] for x in nums}
        best, score = None, 0
        for ni, ai, nname, a, knums, kbase, kwords in known:
            if (ni, ai) in used:
                continue
            if nbase and not (nbase & kbase):
                continue
            hit = sum(1 for w in words if any(monitor._same_word(w, k) for k in kwords))
            if words and not hit:
                continue
            s = hit * 2 + len(set(nums) & knums) * 3 + len(nbase & kbase)
            if s > score:
                best, score = (ni, ai, nname, a), s
        if best and score >= 3:
            used.add(best[:2])
            matched.append(dict(query=q, net=best[0], addr=best[1], net_name=best[2], address=best[3]))
        else:
            unmatched.append(q)
    return matched, unmatched
