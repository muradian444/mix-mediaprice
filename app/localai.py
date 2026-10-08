# -*- coding: utf-8 -*-
"""🧠 Տեղային ԻԻ / Локальный ИИ (Ollama) — по желанию, для более точного заполнения полей.

Ollama-ն աշխատում է ՀԵՆՑ ԱՅՍ համակարգչում (http://127.0.0.1:11434)՝ առանց ինտերնետի, առանց բանալիների,
փաստաթղթերը ոչ մի տեղ չեն ուղարկվում: Տեղադրում՝ install_local_ai.bat:
Եթե Ollama չկա՝ դաշտերը լրացվում են կանոններով (fieldparse.py), ամեն ինչ աշխատում է առանց դրա:"""
import json
import os
import time
import urllib.error
import urllib.request

from config import DATA
from store import read_json, write_json

CONF = DATA / "local_ai.json"
DEFAULT_MODEL = "gemma3:4b"
_STATUS = {"t": 0.0, "v": None}


def _conf():
    d = read_json(CONF, {})
    return d if isinstance(d, dict) else {}


def url():
    u = (os.getenv("OLLAMA_URL") or _conf().get("url") or "http://127.0.0.1:11434").rstrip("/")
    # միայն տեղային հասցե՝ փաստաթղթերը չպետք է դուրս գան համակարգչից/ցանցից
    host = u.split("//", 1)[-1].split("/", 1)[0].split(":")[0]
    if not (host in ("localhost", "127.0.0.1", "::1") or host.startswith(("192.168.", "10.", "172."))):
        return "http://127.0.0.1:11434"
    return u


def model():
    return (os.getenv("OLLAMA_MODEL") or _conf().get("model") or DEFAULT_MODEL).strip()


def enabled():
    return _conf().get("enabled", True) is not False


def set_conf(enabled_=None, model_=None):
    d = _conf()
    if enabled_ is not None:
        d["enabled"] = bool(enabled_)
    if model_:
        d["model"] = str(model_).strip()[:80]
    write_json(CONF, d)
    _STATUS["t"] = 0


def _get(path, timeout=1.5):
    with urllib.request.urlopen(url() + path, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def status(force=False):
    """{running, models, model, has_model, ready, enabled} — քեշ 20 վրկ (որ էջերը չդանդաղեն)."""
    if not force and _STATUS["v"] and time.time() - _STATUS["t"] < 20:
        return _STATUS["v"]
    models, running = [], False
    try:
        models = [m.get("name", "") for m in _get("/api/tags").get("models", [])]
        running = True
    except (urllib.error.URLError, OSError, ValueError):
        pass
    m = model()
    names = set(models) | {x.removesuffix(":latest") for x in models}
    has = m in names or m.removesuffix(":latest") in names
    v = dict(running=running, models=models, model=m, has_model=has, enabled=enabled(),
             ready=running and has and enabled(), url=url())
    _STATUS.update(t=time.time(), v=v)
    return v


SYSTEM = (
    "You extract values from the OCR text of a business document (Armenian, Russian or English) to fill a form "
    "for «Mix Media» (in-store audio advertising company in Armenia). Mix Media itself (Միքս Մեդիա / Микс Медиа, "
    "Levonyan 48) is usually the contractor — return the OTHER party's data (the customer). "
    "Return only values present in the text; if absent, return an empty string or empty list. Never invent data. "
    "Keep names and addresses in the original language and spelling. Dates as DD.MM.YYYY, numbers as digits only. "
    "The OCR text may contain recognition errors — fix obvious OCR mistakes only when you are sure."
)


def fill(text, fields, section="", note="", schema=None, timeout=240):
    """OCR տեքստ -> {key: value} Ollama-ի JSON schema-ով (structured output)."""
    keys = ", ".join(f"{f['key']} ({f['label']}{' — ' + f['hint'] if f.get('hint') else ''})" for f in fields)
    ask = (f"Form: {section or 'document form'}.\n" + (f"Context: {note}\n" if note else "")
           + f"Fields: {keys}\n\nOCR text:\n<<<\n{text[:24000]}\n>>>")
    body = dict(model=model(), stream=False, format=schema or "json",
                options=dict(temperature=0, num_ctx=8192),
                messages=[dict(role="system", content=SYSTEM), dict(role="user", content=ask)])
    req = urllib.request.Request(url() + "/api/chat", data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            res = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Ollama: {e.code} {e.read()[:200]!r}") from e
    except (urllib.error.URLError, OSError) as e:
        raise RuntimeError(f"Ollama-ն հասանելի չէ / Ollama недоступна: {e}") from e
    try:
        data = json.loads((res.get("message") or {}).get("content") or "{}")
    except ValueError as e:
        raise RuntimeError("Ollama-ի պատասխանը JSON չէ / Ответ Ollama не JSON") from e
    return data if isinstance(data, dict) else {}
