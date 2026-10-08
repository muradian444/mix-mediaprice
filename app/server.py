# -*- coding: utf-8 -*-
"""Mix Media web հավելված՝ Պայմանագրեր · Մեդիա պլան · ԱԿՏ · ԿՊ · Իրավաբան ·
Եռամսյակային հաշվետվություն · Պահեստ · Իմ անկյունը · Խմբագրիչ · Ձայն · Ֆիքսիկ (օգնական).

Մուտքը՝ օգտատերերով (users.py). Նոր մարդուն մուտք է տալիս ադմինը սերվերի պատուհանում՝ allow <լոգին>:
Գործարկում՝  python server.py   (կամ run.bat) -> http://127.0.0.1:8000"""
import asyncio
import contextvars
import ipaddress
import json
import mimetypes
import os
import re
import secrets
import shutil
import threading
import time
import traceback
from datetime import date, datetime
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import quote

from fastapi import Body, FastAPI, File, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.gzip import GZipMiddleware

import actsvc
import adspace
import autodeck
import diagnostics
import docfill
import docmeta
import docx_html
import drive_mp3
import editor
import extract
import flows
import kp
import kpsteps
import lawyer
import localai
import mediaplan as mp
import monitor
import mpimport
import pages
import pricecalc
import quarterly
import security
import store
import techimport
import techmail
import techmon
import users
import vault
import warehouse
from config import (BASE, COMPANY, DATA, HOST, IMG_EXT, LAW_LIB, MAX_UPLOAD, MAX_UPLOAD_MB, OUT, PORT, TPL, UPL,
                    VAULT, WEB)

log = diagnostics.setup_logging()
app = FastAPI(title="Mix Media", docs_url=None, redoc_url=None, openapi_url=None)

VERSION = "2.0"
PRESETS = ["9:20-23:50/30", "9:00-23:00/20", "10:00-22:00/60", "9:15-23:45/15"]
FILES_DB = DATA / "files.json"
ACT_UPLOADS = UPL / "act"
LAW_UPLOADS = UPL / "law"
VOICE_UPLOADS = UPL / "voice"
for _d in (ACT_UPLOADS, LAW_UPLOADS, VOICE_UPLOADS):
    _d.mkdir(parents=True, exist_ok=True)
vault.ensure_defaults()

CUR = contextvars.ContextVar("mm_user", default=None)     # ընթացիկ օգտատերը (Guard-ը դնում է)
IPV = contextvars.ContextVar("mm_ip", default="")
COOKIE = "mm_session"
PUBLIC_API = {"/api/login", "/api/register", "/api/me", "/api/logout", "/api/meta/public"}


# ================================================================== օգնականներ
def _err(msg, code=400):
    raise HTTPException(status_code=code, detail=str(msg))


def me():
    u = CUR.get()
    if not u:
        _err("Մուտքը փակ է: Մտեք կրկին / Войдите снова", 401)
    return u


def is_admin():
    u = CUR.get()
    return bool(u) and u.get("role") == "admin"


def admin_only():
    u = me()
    if u.get("role") != "admin":
        _err("Միայն ադմինի համար / Только для администратора", 403)
    return u


def my_root():
    return vault.user_root(me()["login"])


def parse_day(v, name="ամսաթիվ"):
    s = str(v or "").strip()
    for f in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, f).date()
        except ValueError:
            continue
    _err(f"Սխալ {name} ({s or 'դատարկ'}): Ձևաչափը՝ ՕՕ.ԱԱ.ՏՏՏՏ")


def parse_range(data, max_days=None):
    start = parse_day(data.get("start"), "սկզբի ամսաթիվ")
    end = parse_day(data.get("end"), "ավարտի ամսաթիվ")
    if end < start:
        _err("Ավարտի ամսաթիվը փոքր է սկզբից")
    if max_days and (end - start).days + 1 > max_days:
        _err(f"Առավելագույնը {max_days} օր")
    return start, end


# ------------------------------------------------------------------ ֆայլերի գրանցամատյան
_FDB_LOCK = threading.Lock()


def _files_db():
    d = store.read_json(FILES_DB, {})
    return d if isinstance(d, dict) else {}


def register(path, kind="other", title="", save_vault=True, meta=None, sample=False):
    """Պատրաստված ֆայլը՝ հղումով հասանելի և ինքնաբերաբար ՕԳՏԱՏԻՐՈՋ անկյունում (vault/users/<լոգին>)."""
    path = Path(path)
    owner = (CUR.get() or {}).get("login", "")
    if meta:
        docmeta.embed(path, meta)
    fid = store.new_id("f")
    vault_path = None
    if save_vault and owner:
        try:
            vault_path = vault.save_file(path, kind, root=vault.user_root(owner))["path"]
        except Exception:  # noqa
            log.warning("vault save failed for %s", path.name, exc_info=True)
    with _FDB_LOCK:
        db = _files_db()
        db[fid] = dict(path=str(path), name=path.name, kind=kind, title=title or path.stem,
                       ext=path.suffix.lower().lstrip("."), size=path.stat().st_size if path.exists() else 0,
                       created=datetime.now().isoformat(timespec="seconds"), vault=vault_path, owner=owner,
                       sample=bool(sample))
        for k in list(db)[:-3000]:      # չենք կուտակում անվերջ
            db.pop(k, None)
        store.write_json(FILES_DB, db)
    return dict(id=fid, name=path.name, ext=path.suffix.lower().lstrip("."), kind=kind,
                size=db[fid]["size"], vault=vault_path,
                url=f"/api/files/{fid}", download=f"/api/files/{fid}?download=1",
                print_url=f"/api/files/{fid}/print")


def file_entry(fid):
    e = _files_db().get(str(fid))
    u = me()
    if not e or (e.get("owner") != u["login"] and u.get("role") != "admin"):
        _err("Ֆայլը չգտնվեց / Файл не найден", 404)
    p = Path(e["path"])
    if not p.exists():
        _err("Ֆայլը ջնջված է սկավառակից", 404)
    return e, p


def send(path, filename=None, download=False):
    path = Path(path)
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    name = filename or path.name
    disp = "attachment" if download else "inline"
    headers = {"Content-Disposition": f"{disp}; filename*=UTF-8''{quote(name)}", "Cache-Control": "private, no-cache"}
    return FileResponse(path, media_type=mime, headers=headers)


def read_upload(f: UploadFile, allowed=None, folder=None, prefix="", max_bytes=None):
    """Վերբեռնված ֆայլը՝ ստուգում (չափ, ձևաչափ) և պահում. -> Path."""
    limit = max_bytes or MAX_UPLOAD
    name = store.safe_name(f.filename or "file", 100, "file")
    ext = Path(name).suffix.lower()
    if allowed and ext not in allowed:
        _err(f"«{ext or '?'}» ձևաչափը չի աջակցվում: Ընդունվում է՝ {', '.join(allowed)}")
    data = f.file.read(limit + 1)
    if not data:
        _err("Ֆայլը դատարկ է")
    if len(data) > limit:
        _err(f"Ֆայլը մեծ է {limit // 1024 // 1024} ՄԲ-ից")
    folder = Path(folder or UPL)
    folder.mkdir(parents=True, exist_ok=True)
    p = folder / f"{prefix}{int(time.time() * 1000)}_{name}"
    p.write_bytes(data)
    return p


def body(data, *required):
    data = data if isinstance(data, dict) else {}
    miss = [k for k in required if data.get(k) in (None, "", [])]
    if miss:
        _err("Լրացրեք դաշտերը՝ " + ", ".join(miss))
    return data


# ================================================================== միջնաշերտեր
def _private(ip):
    try:
        a = ipaddress.ip_address(ip)
        return a.is_loopback or a.is_private
    except ValueError:
        return False


TRUST_PROXY = os.getenv("TRUST_PROXY", "").strip() in ("1", "true", "yes")


def _trusted_peer(ip):
    """Վերնագրերին (X-Forwarded-For…) հավատում ենք միայն այս համակարգչի պրոքսիից (cloudflared, Caddy),
    կամ ամպում (TRUST_PROXY=1). Այլապես ցանցի ցանկացած մարդ կկեղծեր իր IP-ն և կշրջանցեր արգելքը:"""
    try:
        a = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return a.is_loopback or (TRUST_PROXY and a.is_private)


def client_ip(scope, headers):
    """Իրական IP. Cloudflare թունելի (share_internet.bat) և ամպի պրոքսիի հետևում՝ վերնագրերից."""
    peer = (scope.get("client") or ("", 0))[0] or ""
    if _trusted_peer(peer):
        for h in ("cf-connecting-ip", "x-real-ip", "x-forwarded-for"):
            v = headers.get(h)
            if v:
                ip = v.split(",")[0].strip()
                try:
                    ipaddress.ip_address(ip)
                    return ip
                except ValueError:
                    continue
    return peer


def _cookie(raw, name):
    try:
        c = SimpleCookie()
        c.load(raw or "")
        return c[name].value if name in c else ""
    except Exception:  # noqa
        return ""


class Guard:
    """Մուտքի ստուգում (յուրաքանչյուր հարցում) + ցանկացած սխալ՝ JSON պատասխան, ոչ թե սերվերի անկում.
    Մաքուր ASGI (առանց BaseHTTPMiddleware-ի)՝ արագ է և չի խանգարում մեծ ֆայլերի ներբեռնմանը."""

    def __init__(self, app_):
        self.app = app_

    async def __call__(self, scope, receive, send_):
        if scope["type"] != "http":
            return await self.app(scope, receive, send_)
        path = scope.get("path", "")
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
        ip = client_ip(scope, headers)
        user, state = None, "none"
        token = _cookie(headers.get("cookie", ""), COOKIE)
        if token:
            try:
                user, state = users.session_user(token, ip, headers.get("user-agent", ""))
            except Exception:  # noqa
                log.warning("session check failed", exc_info=True)
        # Մուտքը՝ ՄԻԱՅՆ անձնական լոգինով և գաղտնաբառով (ավտոմատ «guest» ադմիններ այլևս չկան)
        active = user if state == "active" else None
        t_user, t_ip = CUR.set(active), IPV.set(ip)
        try:
            protected = path.startswith(("/api/", "/print/", "/logos/")) and path not in PUBLIC_API
            if protected and not active:
                if path.startswith("/api/"):
                    msg = {"pending": "Սպասում է ադմինի հաստատմանը / Ожидает подтверждения администратора",
                           "blocked": "Մուտքը արգելափակված է / Доступ заблокирован"}.get(
                        state, "Մուտքը փակ է: Մտեք / Войдите в систему")
                    resp = JSONResponse({"detail": msg, "auth": True, "state": state}, status_code=401)
                else:
                    resp = RedirectResponse("/", status_code=303)
                return await resp(scope, receive, send_)
            started = False

            async def send2(msg):
                nonlocal started
                if msg["type"] == "http.response.start":
                    started = True
                await send_(msg)

            try:
                await self.app(scope, receive, send2)
            except Exception as e:  # noqa — ոչ մի սխալ չի գցում սերվերը
                log.exception("unhandled error on %s", path)
                diagnostics.add_event("ERROR", path, f"{type(e).__name__}: {e}", traceback.format_exc())
                if started:
                    raise
                await JSONResponse({"detail": f"Անսպասելի սխալ՝ {type(e).__name__}: {e}"}, status_code=500)(
                    scope, receive, send_)
        finally:
            CUR.reset(t_user)
            IPV.reset(t_ip)


class StaticCache:
    """/static/*՝ բրաուզերը պահում է, բայց ամեն անգամ ստուգում է (304)՝ թարմացումները երևում են անմիջապես."""

    def __init__(self, app_):
        self.app = app_

    async def __call__(self, scope, receive, send_):
        if scope["type"] != "http" or not scope.get("path", "").startswith(("/static/", "/logo.png", "/favicon")):
            return await self.app(scope, receive, send_)

        async def send2(msg):
            if msg["type"] == "http.response.start":
                hs = [(k, v) for k, v in msg.get("headers", []) if k.lower() != b"cache-control"]
                hs.append((b"cache-control", b"no-cache"))
                msg = dict(msg, headers=hs)
            await send_(msg)
        await self.app(scope, receive, send2)


BINARY_PREFIXES = ("/api/files/", "/api/vault/file", "/api/quarterly/", "/logos/", "/api/drive/mp3/",
                   "/api/warehouse/photo", "/api/edit/", "/logo.png", "/favicon.ico")


class SelectiveGZip:
    """JSON/HTML/JS/CSS՝ սեղմված (արագ բեռնում), PDF/DOCX/MP3/նկարներ՝ առանց (արդեն սեղմված են)."""

    def __init__(self, app_):
        self.app = app_
        self.gz = GZipMiddleware(app_, minimum_size=1200)

    async def __call__(self, scope, receive, send_):
        if scope["type"] == "http" and not scope.get("path", "").startswith(BINARY_PREFIXES):
            return await self.gz(scope, receive, send_)
        return await self.app(scope, receive, send_)


app.add_middleware(Guard)
app.add_middleware(StaticCache)
app.add_middleware(SelectiveGZip)
app.add_middleware(security.Shield, ip_of=client_ip)     # 🛡 ամենաառաջին շերտը (վերջին ավելացվածը՝ արտաքինն է)


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    if exc.status_code >= 500:
        diagnostics.add_event("ERROR", request.url.path, exc.detail)
    elif exc.status_code not in (401, 404):
        diagnostics.add_event("WARNING", request.url.path, exc.detail)
    extra = {"auth": True} if exc.status_code == 401 else {}
    return JSONResponse({"detail": exc.detail, **extra}, status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    """FastAPI-ի ստանդարտ 422-ը ցուցակ է՝ բրաուզերում երևում էր «[object Object]». Հիմա՝ ընթեռնելի տեքստ."""
    parts = []
    for e in exc.errors()[:4]:
        loc = ".".join(str(x) for x in (e.get("loc") or [])[1:]) or "?"
        parts.append(f"{loc}: {e.get('msg', '')}")
    diagnostics.add_event("WARNING", request.url.path, "; ".join(parts))
    return JSONResponse({"detail": "Սխալ կամ թերի տվյալներ / Неверные или неполные данные — " + "; ".join(parts)},
                        status_code=422)


# ================================================================== մուտք / օգտատերեր
def _set_cookie(resp, token, request: Request):
    secure = request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"
    resp.set_cookie(COOKIE, token, httponly=True, samesite="lax", secure=secure, max_age=users.SESSION_DAYS * 86400)


@app.get("/api/me")
def auth_me(request: Request):
    token = request.cookies.get(COOKIE)
    ip = IPV.get()
    if not token:
        return dict(state="none", ip=ip, users=users.count())
    u, state = users.session_user(token, ip)
    return dict(state=state, ip=ip, user=users.public(u) if u else None)


@app.post("/api/login")
def auth_login(request: Request, data: dict = Body(default={})):
    ip = IPV.get()
    try:
        u, token = users.login(data.get("login"), str(data.get("password") or ""), ip,
                               request.headers.get("user-agent", ""))
    except ValueError as e:
        _err(e, 401)
    except PermissionError as e:
        _err(e, 403)
    r = JSONResponse(dict(ok=True, state=u.get("status"), user=users.public(u)))
    _set_cookie(r, token, request)
    return r


@app.post("/api/register")
def auth_register(request: Request, data: dict = Body(default={})):
    ip = IPV.get()
    try:
        u, token = users.register(data.get("login"), data.get("name"), str(data.get("password") or ""), ip,
                                  request.headers.get("user-agent", ""))
    except ValueError as e:
        _err(e)
    except PermissionError as e:
        _err(e, 429)
    r = JSONResponse(dict(ok=True, state="pending", user=users.public(u), ip=ip))
    _set_cookie(r, token, request)
    return r


@app.post("/api/logout")
def auth_logout(request: Request):
    token = request.cookies.get(COOKIE)
    if token:
        users.end_session(token)
        users.log_event("logout", (CUR.get() or {}).get("login", ""), IPV.get())
    r = JSONResponse({"ok": True})
    r.delete_cookie(COOKIE)
    return r


@app.get("/api/meta/public")
def meta_public():
    return dict(company=COMPANY, auth_required=True, version=VERSION)


@app.get("/api/admin/users")
def admin_users():
    admin_only()
    return dict(users=users.users_list(), online=users.online())


@app.get("/api/admin/users/{login}/ips")
def admin_user_ips(login: str):
    admin_only()
    try:
        lg, rows = users.ip_history(login)
    except ValueError as e:
        _err(e, 404)
    return dict(login=lg, ips=rows)


def merge_files(src, dst):
    """Մի օգտատիրոջ ֆայլերը (անկյուն + գրանցամատյան) -> մյուսին (օր.՝ հին guest-xxxx -> իսկական լոգին)."""
    src, dst = users._find(src), users._find(dst)
    if src == dst:
        raise ValueError("Это один и тот же пользователь")
    a, b = vault.user_root(src), vault.user_root(dst)
    moved = 0
    for p in sorted(a.rglob("*"), key=lambda x: len(x.parts), reverse=True):
        if p.is_file():
            rel = p.relative_to(a)
            target = b / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                target = target.with_name(f"{target.stem}_{src}{target.suffix}")
            shutil.move(str(p), str(target))
            moved += 1
    with _FDB_LOCK:
        db = _files_db()
        for e in db.values():
            if e.get("owner") == src:
                e["owner"] = dst
                if e.get("vault"):
                    e["vault"] = None
        store.write_json(FILES_DB, db)
    users.log_event("merge", dst, "", f"{src} -> {dst}: {moved}")
    return dict(src=src, dst=dst, moved=moved)


def _console_merge(args):
    if len(args) < 2:
        return "  Формат: merge <откуда> <куда>"
    r = merge_files(args[0], args[1])
    return f"  ✓ Передано файлов: {r['moved']} ({r['src']} → {r['dst']})"


def _console_ban(args):
    if not args:
        return "  Формат: ban <IP> [часы]"
    hours = float(args[1]) if len(args) > 1 else security.BAN_HOURS
    return "  ✓ Заблокирован" if security.ban(args[0], hours, "вручную (консоль)", "admin") else "  ! Нельзя (свой/разрешённый IP)"


def _console_bans(args):
    rows = security.overview()["bans"]
    if not rows:
        return "  Заблокированных IP нет."
    return users._table([[r["ip"], r["until"] or "навсегда", r["reason"][:50], r["by"]] for r in rows],
                        ["IP", "До", "Причина", "Кто"])


users.EXTRA.update(merge=_console_merge, ban=_console_ban, bans=_console_bans,
                   unban=lambda a: ("  ✓ Разблокирован" if a and security.unban(a[0]) else "  ! IP не найден"))


@app.post("/api/admin/users")
def admin_user_create(data: dict = Body(default={})):
    """Ադմինը ստեղծում է մարդու անձնական մուտքը (լոգին + գաղտնաբառ)."""
    admin_only()
    d = body(data, "login", "password")
    try:
        lg = users.add_user(d["login"], str(d["password"]), "admin" if d.get("role") == "admin" else "user",
                            str(d.get("name") or "").strip())
    except ValueError as e:
        _err(e)
    users.log_event("add-web", lg, IPV.get(), me()["login"])
    return dict(ok=True, login=lg, users=users.users_list())


@app.post("/api/admin/users/{login}/{action}")
def admin_user_action(login: str, action: str, data: dict = Body(default={})):
    """allow | block | unblock | delete | passwd | role | name | merge"""
    u = admin_only()
    data = data if isinstance(data, dict) else {}
    try:
        target = users._find(login)
        if target == u["login"] and action in ("block", "delete", "role"):
            _err("Нельзя сделать это с собственной учётной записью")
        if action in ("allow", "unblock"):
            users.approve(target, data.get("role"))
        elif action == "block":
            users.block(target)
        elif action == "delete":
            users.delete(target)
        elif action == "passwd":
            users.set_password(target, str(data.get("password") or ""))
        elif action == "role":
            users.set_role(target, data.get("role"))
        elif action == "name":
            users.set_name(target, data.get("name"))
        elif action == "merge":
            res = merge_files(target, str(data.get("to") or ""))
            return dict(ok=True, **res, users=users.users_list())
        else:
            _err("Неизвестное действие", 404)
    except ValueError as e:
        _err(e)
    users.log_event(f"web-{action}", target, IPV.get(), u["login"])
    return dict(ok=True, users=users.users_list())


@app.post("/api/me/password")
def me_password(data: dict = Body(default={})):
    u = me()
    d = body(data, "old", "new")
    try:
        users.change_own_password(u["login"], str(d["old"]), str(d["new"]))
    except ValueError as e:
        _err(e)
    return dict(ok=True)


# ------------------------------------------------------------------ 🛡 անվտանգություն
@app.get("/api/admin/security")
def admin_security():
    admin_only()
    return dict(security.overview(), users_log=[dict(at=r[0], event=r[1], login=r[2], ip=r[3], detail=r[4])
                                                 for r in users._read_log(60)[::-1]])


@app.post("/api/admin/security")
def admin_security_set(data: dict = Body(default={})):
    admin_only()
    data = data if isinstance(data, dict) else {}
    try:
        security.set_settings(internet=data.get("internet"), csrf=data.get("csrf"), autoban=data.get("autoban"),
                              domains=data.get("domains"))
    except ValueError as e:
        _err(e)
    return security.overview()


@app.post("/api/admin/security/{action}")
def admin_security_action(action: str, data: dict = Body(default={})):
    """ban | unban | allow | disallow  ({ip, hours, reason})"""
    u = admin_only()
    ip = str((data or {}).get("ip") or "").strip()
    try:
        if action == "ban":
            if ip == IPV.get():
                _err("Это ваш собственный IP")
            if not security.ban(ip, float(data.get("hours") or 0), data.get("reason") or "вручную", u["login"]):
                _err("Этот IP нельзя заблокировать (локальный или в списке разрешённых)")
        elif action == "unban":
            security.unban(ip, u["login"])
        elif action in ("allow", "disallow"):
            security.set_allow(ip, action == "allow")
        else:
            _err("Неизвестное действие", 404)
    except ValueError as e:
        _err(e)
    return security.overview()


# ================================================================== META
def flows_schema():
    out = {}
    for kind, flow in flows.FLOWS.items():
        steps = []
        for s in flow["steps"]:
            steps.append(dict(key=s["key"], label=s["label"], prompt=s.get("prompt", ""),
                              kind=s.get("kind", "input"), money=bool(s.get("money")),
                              optional=bool(s.get("optional")),
                              buttons=[dict(label=l, value=v) for l, v in (s.get("buttons") or [])]))
        extras_ = [dict(key=k, label=flows.EXTRA_LABELS.get(k, k), default=v) for k, v in flow["defaults"].items()]
        out[kind] = dict(kind=kind, title=flow["title"], steps=steps, defaults=extras_)
    return out


@app.get("/api/meta")
def meta():
    pdf_ready, pdf_how = docfill.pdf_available()
    nets = store.networks()
    u = me()
    return dict(company=COMPANY, settings=store.settings(), clients=store.clients(),
                flows=flows_schema(), kp=kpsteps.schema(), presets=PRESETS,
                networks=[dict(name=n["name"], count=len(n["addresses"])) for n in nets],
                addresses_total=sum(len(n["addresses"]) for n in nets),
                law_formats=list(lawyer.SUPPORTED), slide_types=quarterly.SLIDE_TYPES,
                slide_names=quarterly.TYPE_NAMES, quarters=quarterly.QUARTERS,
                warehouse=dict(categories=warehouse.CATEGORIES, statuses=warehouse.STATUSES,
                               units=warehouse.UNITS),
                pdf=dict(ready=pdf_ready, how=pdf_how), auth_required=True,
                user=users.public(u), ip=IPV.get(), extract=extract.status(),
                edit_formats=list(editor.SUPPORTED), version=VERSION)


@app.get("/api/settings")
def get_settings():
    return store.settings()


@app.post("/api/settings")
def set_settings(data: dict = Body(default={})):
    data = data if isinstance(data, dict) else {}
    u = me()
    prefs = {k: data.pop(k) for k in ("lang", "theme") if k in data}   # լեզուն/թեման՝ ամեն մեկինը իրենը
    if prefs:
        users.set_prefs(u["login"], **prefs)
    s = store.save_settings(data) if data else store.settings()
    if data.get("mp3_folder"):
        try:
            drive_mp3.set_folder(data["mp3_folder"])
        except ValueError as e:
            _err(str(e))
    return s


# ------------------------------------------------------------------ հաճախորդներ
@app.get("/api/clients")
def clients():
    return store.clients()


@app.post("/api/clients")
def client_add(data: dict = Body(default={})):
    return store.add_client(body(data, "name")["name"])


@app.delete("/api/clients")
def client_del(name: str = Query(...)):
    return store.delete_client(name)


# ------------------------------------------------------------------ ցանցեր / հասցեներ
@app.get("/api/networks")
def networks():
    return [dict(index=i, name=n["name"], addresses=n["addresses"]) for i, n in enumerate(store.networks())]


@app.post("/api/networks")
def network_add(data: dict = Body(default={})):
    try:
        store.add_network(body(data, "name")["name"])
    except ValueError as e:
        _err(str(e))
    return networks()


@app.post("/api/networks/{index}/addresses")
def addresses_add(index: int, data: dict = Body(default={})):
    lines = data.get("lines") or re.split(r"[\r\n]+", str(data.get("text") or ""))
    lines = [l for l in (str(x).strip() for x in lines) if l]
    if not lines:
        _err("Գրեք հասցեն")
    try:
        nets, added = store.add_addresses(index, lines)
    except ValueError as e:
        _err(str(e))
    return dict(added=len(added), indexes=added, addresses=nets[index]["addresses"],
                skipped=len(lines) - len(added))


@app.delete("/api/networks/{index}/addresses/{addr}")
def address_del(index: int, addr: int):
    try:
        store.delete_address(index, addr)
    except ValueError as e:
        _err(str(e))
    return networks()


@app.get("/api/addresses/search")
def addresses_search(q: str = "", nets: str = ""):
    idx = [int(x) for x in re.findall(r"\d+", nets)] or None
    return store.search_addresses(q, idx)


# ================================================================== 🏪 ԽԱՆՈՒԹՆԵՐ ԵՎ ԳՈՎԱԶԴԱՅԻՆ ՏԵՂԵՐ
def _ads(fn, *a, **k):
    try:
        return fn(*a, **k)
    except ValueError as e:
        _err(str(e))


@app.get("/api/stores")
def stores_list():
    return adspace.overview()


@app.post("/api/stores/capacity")
def stores_capacity(data: dict = Body(default={})):
    _ads(adspace.set_default_capacity, body(data, "capacity")["capacity"])
    return adspace.overview()


@app.put("/api/stores/{ni}")
def stores_net(ni: int, data: dict = Body(default={})):
    _ads(adspace.set_network, ni, data.get("capacity"))
    return adspace.overview()


@app.post("/api/stores/{ni}/logo")
def stores_logo(ni: int, file: UploadFile = File(...)):
    blob = file.file.read(10 * 1024 * 1024 + 1)
    if not blob:
        _err("Ֆայլը դատարկ է")
    if len(blob) > 10 * 1024 * 1024:
        _err("Լոգոն մեծ է 10 ՄԲ-ից")
    return dict(ok=True, logo=_ads(adspace.set_logo, ni, file.filename or "logo.png", blob))


@app.delete("/api/stores/{ni}/logo")
def stores_logo_del(ni: int):
    _ads(adspace.delete_logo, ni)
    return dict(ok=True)


@app.put("/api/stores/{ni}/addresses/{ai}")
def stores_addr(ni: int, ai: int, data: dict = Body(default={})):
    _ads(adspace.set_address, ni, ai, data.get("capacity"), data.get("district"))
    return adspace.overview()


@app.post("/api/stores/{ni}/bookings")
def stores_book(ni: int, data: dict = Body(default={})):
    d = body(data, "client", "addresses")
    res = _ads(adspace.add_booking, ni, d["addresses"], d["client"], data.get("start"), data.get("end"),
               data.get("note"), data.get("clip"), data.get("clip_url"))
    return dict(res, overview=adspace.overview())


# ------------------------------------------------------------------ 💰 գներ և 🎵 հոլովակներ
@app.put("/api/stores/{ni}/price")
def stores_price(ni: int, data: dict = Body(default={})):
    _ads(adspace.set_price, ni, (data or {}).get("price"), (data or {}).get("note"), me()["login"])
    return adspace.overview()


@app.post("/api/stores/prices")
def stores_prices(data: dict = Body(default={})):
    n = _ads(adspace.set_prices, (data or {}).get("rows") or [], me()["login"])
    users.log_event("prices", me()["login"], IPV.get(), f"{n} изменено")
    return dict(changed=n, overview=adspace.overview())


@app.get("/api/stores/prices/log")
def stores_prices_log():
    return dict(rows=adspace.price_log())


@app.get("/api/stores/pricelist")
def stores_pricelist():
    """Գնացուցակ (փաթեթներ, զեղչեր, ստուդիա) + որտեղ գովազդել՝ Երևան Սիթի / ԱԿ / այլ ցանցեր."""
    return pricecalc.overview()


@app.post("/api/stores/pricelist")
def stores_pricelist_save(data: dict = Body(default={})):
    pricecalc.save(data, me()["login"])
    users.log_event("prices", me()["login"], IPV.get(), "գնացուցակ (փաթեթներ) փոխված")
    return pricecalc.overview()


@app.post("/api/stores/estimate")
def stores_estimate(data: dict = Body(default={})):
    """Կանխատեսվող արդյունքներ -> PDF հաշվարկ (Mix Media ձևավորումով)."""
    est = pricecalc.estimate(data)
    if not est["addresses"]:
        _err("Ընտրեք գոնե մեկ հասցե / Выберите хотя бы один адрес")
    safe = store.safe_name(est["brand"] or "Mix Media", 30, "estimate")
    out = OUT / f"Estimate_{safe}_{datetime.now():%d%m%Y_%H%M}.pdf"
    try:
        pricecalc.make_pdf(est, out)
    except RuntimeError as e:
        _err(str(e))
    return dict(ok=True, estimate={k: v for k, v in est.items() if k != "rows"},
                file=register(out, "kp", f"Գնային հաշվարկ · {est['brand'] or '—'}"))


@app.put("/api/stores/{ni}/addresses/{ai}/price")
def stores_addr_price(ni: int, ai: int, data: dict = Body(default={})):
    _ads(adspace.set_address_price, ni, ai, (data or {}).get("price"), me()["login"])
    return adspace.overview()


@app.put("/api/stores/{ni}/addresses/{ai}/bookings/{bid}")
def stores_book_edit(ni: int, ai: int, bid: str, data: dict = Body(default={})):
    _ads(adspace.update_booking, ni, ai, bid, data if isinstance(data, dict) else {})
    return adspace.overview()


@app.get("/api/stores/playing")
def stores_playing(day: str = ""):
    return _ads(adspace.now_playing, day or None)


@app.post("/api/stores/clip")
def stores_clip_all(data: dict = Body(default={})):
    d = body(data, "client")
    return dict(changed=_ads(adspace.set_clip_all, d["client"], d.get("clip"), d.get("clip_url")))


@app.delete("/api/stores/{ni}/addresses/{ai}/bookings/{bid}")
def stores_unbook(ni: int, ai: int, bid: str):
    _ads(adspace.delete_booking, ni, ai, bid)
    return adspace.overview()


@app.post("/api/stores/publish")
def stores_publish():
    """docs/ թղթապանակի թարմացում (GitHub Pages-ի հանրային էջի տվյալները)."""
    return pages.build()


@app.get("/logos/{name}")
def logo_file(name: str):
    p = adspace.LOGOS / store.safe_name(name, 120, "x")
    if not p.exists() or p.parent.resolve() != adspace.LOGOS.resolve():
        return Response(status_code=404)
    return send(p)


# ------------------------------------------------------------------ 💰 հանրային գնացուցակ (առանց մուտքի՝ հաճախորդին ուղարկելու համար)
@app.get("/price")
def price_page():
    f = WEB / "price.html"
    if not f.exists():
        return HTMLResponse("<h1>web/price.html չգտնվեց</h1>", status_code=500)
    return FileResponse(f, media_type="text/html", headers={"Cache-Control": "no-cache"})


@app.get("/price.json")
def price_data():
    return JSONResponse(pricecalc.public(), headers={"Cache-Control": "no-cache"})


@app.get("/price/logos/{name}")
def price_logo(name: str):
    return logo_file(name)


PRICE_IMG = WEB / "price-img"


@app.get("/price-img/{path:path}")
def price_img(path: str):
    """Գնացուցակի նկարներ (մոլեր, գործընկերների լոգոներ)՝ առանց մուտքի."""
    f = (PRICE_IMG / path).resolve()
    if not f.is_file() or PRICE_IMG.resolve() not in f.parents or f.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
        return JSONResponse({"detail": "not found"}, status_code=404)
    return FileResponse(f, headers={"Cache-Control": "public, max-age=86400"})


@app.get("/api/stores/share")
def stores_share(request: Request):
    """Հղումներ հաճախորդի համար՝ դոմեն, ինտերնետ (Cloudflare) և գրասենյակ."""
    out = [dict(kind="domain", url=f"https://{d}/price") for d in security.allowed_hosts()]
    if PUBLIC_URL["url"]:
        out.append(dict(kind="internet", url=PUBLIC_URL["url"] + "/price"))
    out += [dict(kind="office", url=f"http://{ip}:{PORT}/price") for ip in lan_ips()] if HOST in ("0.0.0.0", "::") else []
    host = (request.headers.get("x-forwarded-host") or request.headers.get("host") or "").split(",")[0].strip()
    proto = (request.headers.get("x-forwarded-proto") or request.url.scheme).split(",")[0].strip()
    if host.endswith(".trycloudflare.com"):
        proto = "https"
    cur = f"{proto}://{host}/price" if host else str(request.base_url).rstrip("/") + "/price"
    if not any(x["url"] == cur for x in out):
        if host.endswith(".trycloudflare.com"):
            out.insert(0, dict(kind="internet", url=cur))
        else:
            out.append(dict(kind="current", url=cur))
    return dict(links=out)


# ================================================================== 📄 ՊԱՅՄԱՆԱԳՐԵՐ
def contract_data(kind, raw):
    if kind not in flows.FLOWS:
        _err("Անհայտ շաբլոն")
    flow = flows.FLOWS[kind]
    raw = raw if isinstance(raw, dict) else {}
    data, errors = {}, {}
    for s in flow["steps"]:
        k = s["key"]
        if s.get("kind") == "addresses":
            addrs = [str(a).strip() for a in (raw.get(k) or []) if str(a).strip()]
            need = data.get("addr_count")
            if need and len(addrs) != need:
                errors[k] = f"Պետք է {need} հասցե, մուտքագրված է {len(addrs)}"
            elif not addrs:
                errors[k] = "Ավելացրեք հասցեները"
            data[k] = addrs
            continue
        v = raw.get(k)
        if isinstance(v, bool):
            data[k] = v
            continue
        if v is None or str(v).strip() == "":
            if s.get("optional"):
                data[k] = ""
            else:
                errors[k] = "Դաշտը լրացված չէ"
            continue
        try:
            data[k] = s["validate"](str(v).strip(), data)
        except ValueError as e:
            errors[k] = str(e)
    for k, dv in flow["defaults"].items():
        v = raw.get(k, dv)
        try:
            data[k] = int(re.sub(r"[\s,]", "", str(v))) if str(v).strip() else dv
        except ValueError:
            errors[k] = "Գրեք թիվ"
            data[k] = dv
    return data, errors


@app.post("/api/contracts/validate")
def contract_validate(payload: dict = Body(default={})):
    data, errors = contract_data(str(payload.get("kind")), payload.get("data"))
    lines = []
    if not errors:
        try:
            lines = [dict(label=k, value=v) for k, v in flows.summary_lines(str(payload.get("kind")), data)]
        except Exception as e:  # noqa
            log.warning("summary failed: %s", e)
    return dict(ok=not errors, errors=errors, summary=lines)


@app.post("/api/contracts/create")
def contract_create(payload: dict = Body(default={})):
    kind = str(payload.get("kind"))
    data, errors = contract_data(kind, payload.get("data"))
    if errors:
        return JSONResponse(dict(ok=False, errors=errors), status_code=422)
    merged = {**flows.FLOWS[kind]["defaults"], **data}
    try:
        docx_path = docfill.make_contract(kind, merged, OUT)
    except KeyError as e:
        _err(f"Շաբլոնում չգտնվեց դաշտը՝ {e}")
    except FileNotFoundError:
        _err(f"Շաբլոնը չգտնվեց՝ templates/{kind}.docx")
    # ձևի տվյալները ֆայլի մեջ՝ «✏️ Изменить»-ով այն կարելի է բացել նույն ձևում
    docmeta.embed(docx_path, dict(kind="contract", flow=kind, data=payload.get("data") or {}))
    files = [register(docx_path, "contract", f"Պայմանագիր {kind}")]
    pdf = docfill.to_pdf(docx_path)
    if pdf:
        files.insert(0, register(pdf, "contract", f"Պայմանագիր {kind}"))
    store.add_client(merged.get("company", ""))
    ready, how = docfill.pdf_available()
    return dict(ok=True, files=files,
                note="" if pdf else "PDF չստացվեց (" + how + "): ուղարկվեց Word տարբերակը, "
                                    "տպելու համար օգտագործեք «🖨 Տպել» կոճակը")


# ================================================================== 📊 ՄԵԴԻԱ ՊԼԱՆ
@app.post("/api/plan/times")
def plan_times(data: dict = Body(default={})):
    try:
        slots = mp.parse_times(str(data.get("text") or ""))
    except ValueError as e:
        _err(f"{e}: Օրինակ՝ 10:00-22:00/30 կամ 9:00, 13:00, 18:30")
    return dict(slots=slots, count=len(slots))


@app.post("/api/plan/create")
def plan_create(payload: dict = Body(default={})):
    p = body(payload, "client", "slots", "addresses", "clips")
    start, end = parse_range(p, max_days=1830)        # ցանկացած ժամկետ (5 տարին՝ սխալից պաշտպանություն)
    slots = [str(s) for s in p["slots"]]
    addresses = []
    for a in p["addresses"]:
        try:
            clips_ = [int(c) for c in (a.get("clips") or [1])]
        except (TypeError, ValueError):
            clips_ = [1]
        addresses.append(dict(net=str(a.get("net") or ""), addr=str(a.get("addr") or ""), clips=clips_))
    clips = []
    for i, c in enumerate(p["clips"], 1):
        clips.append(dict(n=int(c.get("n") or i), name=str(c.get("name") or f"Հոլովակ {i}"),
                          file=str(c.get("file") or ""), link=c.get("link") or None))
    if not addresses:
        _err("Ընտրեք գոնե մեկ հասցե")
    if not slots:
        _err("Ընտրեք եթերացանկը (ժամերը)")
    if not clips:
        _err("Ավելացրեք գոնե մեկ հոլովակ")
    safe = store.safe_name(p["client"], 30, "client")
    out = OUT / f"MediaPlan_{safe}_{start:%d%m%Y}_{end:%d%m%Y}.pdf"
    try:
        path = mp.make_plan(dict(client=str(p["client"]).strip(), start=start, end=end, slots=slots,
                                 addresses=addresses, clips=clips, seal=p.get("seal", True) is not False), out)
    except RuntimeError as e:
        _err(str(e))
    store.add_client(p["client"])
    total = ((end - start).days + 1) * len(slots) * len(addresses)
    meta = dict(kind="plan", data=dict(client=str(p["client"]).strip(), start=start.isoformat(),
                                       end=end.isoformat(), slots=slots, addresses=addresses, clips=clips))
    return dict(ok=True, files=[register(path, "plan", "Մեդիա պլան", meta=meta)], total=total)


# ------------------------------------------------------------------ Drive MP3
@app.get("/api/drive/folder")
def drive_folder():
    return dict(folder=drive_mp3.get_folder() or "")


@app.post("/api/drive/folder")
def drive_folder_set(data: dict = Body(default={})):
    try:
        url = drive_mp3.set_folder(str(data.get("link") or ""))
    except ValueError as e:
        _err(str(e))
    store.save_settings(dict(mp3_folder=url))
    return dict(folder=url)


@app.get("/api/drive/mp3")
def drive_list(folder: str = ""):
    link = folder or drive_mp3.get_folder()
    if not link:
        _err("Drive թղթապանակը կարգավորված չէ")
    try:
        files = drive_mp3.list_mp3(link)
    except Exception as e:  # noqa
        log.warning("drive list failed: %s", e)
        _err(str(e))
    return dict(folder=link, files=[dict(id=i, name=n, link=drive_mp3.file_link(i)) for i, n in files])


@app.get("/api/drive/mp3/{file_id}")
def drive_preview(file_id: str, name: str = "clip.mp3"):
    try:
        data = drive_mp3.download(file_id)
    except Exception as e:  # noqa
        _err(f"Նվագարկել չհաջողվեց՝ {e}")
    safe = store.safe_name(name, 60, "clip.mp3")
    return Response(data, media_type="audio/mpeg",
                    headers={"Content-Disposition": f"inline; filename*=UTF-8''{quote(safe)}"})


@app.post("/api/plan/clip-upload")
async def clip_upload(file: UploadFile = File(...)):
    """MP3 ֆայլ՝ պահոց + հղում (եթե Google Drive-ը կարգավորված է՝ հղումն ավտոմատ)."""
    p = await asyncio.to_thread(read_upload, file, (".mp3",), UPL / "clips")
    link, src, err = None, None, None
    try:
        import mp3link
        link = await asyncio.to_thread(mp3link._drive_upload, p, p.name, "")
        src = "drive" if link else None
    except Exception as e:  # noqa
        err = str(e)
        log.warning("clip drive upload failed: %s", e)
    info = await asyncio.to_thread(vault.save_file, p, "plan", "MP3", my_root())
    return dict(name=p.name, link=link, source=src, error=err, vault=info["path"],
                local=f"/api/vault/file?path={quote(info['path'])}")


# ================================================================== 🧾 ԱԿՏ
@app.post("/api/act/upload")
def act_upload(files: list[UploadFile] = File(...)):
    paths = [read_upload(f, allowed=(".xlsx", ".xlsm", ".csv"), folder=ACT_UPLOADS) for f in files]
    token = store.new_id("a")
    store.write_json(ACT_UPLOADS / f"{token}.json", [str(p) for p in paths])
    return dict(token=token, files=[p.name for p in paths])


def _act_paths(token):
    rows = store.read_json(ACT_UPLOADS / f"{store.safe_name(token, 40, 'x')}.json", None)
    if not rows:
        _err("Ֆայլերը չգտնվեցին, վերբեռնեք կրկին")
    return [Path(p) for p in rows if Path(p).exists()]


@app.post("/api/act/preview")
def act_preview(payload: dict = Body(default={})):
    p = body(payload, "source")
    start, end = parse_range(p, max_days=400)
    try:
        planned = max(0, int(float(p.get("planned_per_day") or 0)))
    except (TypeError, ValueError):
        planned = 0
    src = p["source"]
    if src == "file":
        paths = _act_paths(p.get("token"))
    else:
        _err("Անհայտ աղբյուր")
    hours = {}
    try:
        days, clips, errors = actsvc.from_files(paths, start, end, planned, hours_out=hours)
    except ValueError as e:
        _err(str(e))
    return actsvc.summary(days, clips, hours=hours,
                          extra=dict(warnings=errors, source=src, files=[Path(x).name for x in paths],
                                     net_guess=actsvc.guess_network(p.get("client")),
                                     no_hours=not hours))


@app.post("/api/act/mediaplan")
def act_mediaplan(file: UploadFile = File(...)):
    """Պատրաստի մեդիա պլանի ֆայլ -> պատվիրատու, ժամանակահատված, ժամեր, հասցեներ (ԱԿՏ-ի համար)."""
    p = read_upload(file, allowed=mpimport.SUPPORTED, folder=ACT_UPLOADS, prefix="mp_")
    meta = docmeta.read(p)
    if meta and meta.get("kind") == "plan":     # մեր մեդիա պլանը՝ ճշգրիտ տվյալներով
        d = meta.get("data") or {}
        res = dict(source="meta", client=d.get("client", ""), start=d.get("start", ""), end=d.get("end", ""),
                   slots=d.get("slots") or [], warnings=[], file=file.filename,
                   clips=[dict(n=c.get("n"), name=c.get("name", "")) for c in d.get("clips") or [] if isinstance(c, dict)],
                   addresses=[dict(net=a.get("net", ""), addr=a.get("addr", "")) for a in d.get("addresses") or []])
    else:
        try:
            res = mpimport.parse(p)
        except ValueError as e:
            _err(str(e))
        except Exception as e:  # noqa — վնասված/անընթեռնելի ֆայլը չի գցում սերվերը
            log.warning("mediaplan parse failed: %s", p.name, exc_info=True)
            _err(f"Ֆայլը չհաջողվեց կարդալ՝ {type(e).__name__}: {e}")
        res["file"] = file.filename
    # ամեն հասցե՝ մեդիա պլանի ԻՐ ժամերով (ընդհանուր եթերացանկը՝ այն հասցեներին, որոնց բաժինը չգտնվեց),
    # որ ԱԿՏ-ը հաշվվի ճիշտ մեդիա պլանի ժամերով, և ժամերի ընտրությունը էջում դրանք չփոխի
    if res["slots"]:
        for a in res["addresses"]:
            if not a.get("slots"):
                a["slots"] = list(res["slots"])
    if res["slots"] and not res.get("schedules"):
        res["schedules"] = [dict(nets=sorted({a["net"] for a in res["addresses"] if a.get("net")}),
                                 count=len(res["addresses"]), slots=res["slots"])]
    # ԱԿՏ-ի դաշտերի համար՝ խանութի լոգո (ցանց), օրական սփոթներ (ճիշտ մեդիա պլանի պես)
    names = [n["name"] for n in store.networks()]
    nets_used = {a["net"] for a in res["addresses"] if a.get("net")}
    if len(nets_used) == 1 and next(iter(nets_used)) in names:
        res["net_guess"] = names.index(next(iter(nets_used)))
    else:
        res["net_guess"] = actsvc.guess_network(res.get("client"), [a["addr"] for a in res["addresses"]])
    res["nets"] = sorted(nets_used)
    per_addr = [len(set(a.get("slots") or res["slots"])) for a in res["addresses"]]
    res["per_day"] = max(set(per_addr), key=per_addr.count) if per_addr else len(set(res["slots"]))
    res["per_day_total"] = sum(per_addr)
    return res


@app.get("/api/act/monitor/months")
def act_months(start: str, end: str):
    s, e = parse_range(dict(start=start, end=end), max_days=400)
    return actsvc.monitor_months(s, e)


@app.post("/api/act/monitor/addresses")
def act_monitor_addresses(data: dict = Body(default={})):
    s, e = parse_range(body(data, "start", "end"), max_days=400)
    try:
        rows, missing, errors = actsvc.monitor_addresses(s, e)
    except ValueError as er:
        _err(str(er))
    return dict(addresses=rows, missing_months=missing, warnings=errors)


@app.post("/api/act/monitor/preview")
def act_monitor_preview(data: dict = Body(default={})):
    d = body(data, "start", "end")
    asked = parse_range(d, max_days=400)
    try:
        per_hour = int(d.get("per_hour") if d.get("per_hour") not in (None, "") else monitor.MIN_PER_HOUR)
    except (TypeError, ValueError):
        per_hour = monitor.MIN_PER_HOUR
    try:
        # մեդիա պլանից՝ ԱԿՏ-ը հաշվվում է միայն մեդիա պլանի ժամանակահատվածի օրերով
        s, e = actsvc.clip_to_plan(*asked, d.get("plan_start"), d.get("plan_end"))
        raw = d.get("times") or []
        times = raw if isinstance(raw, list) else mp.parse_times(str(raw))
        days, by_addr, extra, off, hours = actsvc.from_monitor(s, e, times, d.get("addr_mode", "all"),
                                                               d.get("targets"), d.get("nets"),
                                                               min(max(per_hour, 0), 12))
    except ValueError as er:
        _err(str(er))
    extra.update(start=s.isoformat(), end=e.isoformat())
    if (s, e) != asked:
        extra["warnings"] = list(extra.get("warnings") or []) + [
            f"ԱԿՏ-ը հաշվվեց մեդիա պլանի ժամանակահատվածով՝ {s:%d.%m.%Y} – {e:%d.%m.%Y} "
            f"(ընտրված էր {asked[0]:%d.%m.%Y} – {asked[1]:%d.%m.%Y})"]
    nets_used = {k[0] for k in by_addr if k[0]}
    names = [n["name"] for n in store.networks()]
    if len(nets_used) == 1 and next(iter(nets_used)) in names:   # բոլոր հասցեները մեկ ցանցից
        guess = names.index(next(iter(nets_used)))
    else:
        guess = actsvc.guess_network(d.get("client"), [k[1] for k in by_addr],
                                     d.get("nets") if d.get("addr_mode") == "net" else None)
    return actsvc.summary(days, {}, by_addr, extra=dict(extra, source="monitor", net_guess=guess), outages=off,
                          hours=hours)


@app.get("/api/act/logos")
def act_logos(client: str = "", addresses: str = ""):
    """Խանութների լոգոները (ԱԿՏ-ի PDF-ի աջ վերևի անկյուն) + ավտոմատ գուշակություն պատվիրատուի անունից."""
    return dict(networks=actsvc.logo_networks(), guess=actsvc.guess_network(client, [a for a in addresses.split("|") if a]))


@app.post("/api/act/create")
def act_create(payload: dict = Body(default={})):
    p = body(payload, "client", "days")
    start, end = parse_range(p, max_days=400)
    try:
        days = actsvc.days_from_json(p["days"])
        docx_path, pdf = actsvc.make(p["client"], p.get("contract"), start, end, days,
                                     p.get("clips"), p.get("by_addr"), p.get("logo_net"),
                                     p.get("seal", True) is not False, p.get("hours"))
    except ValueError as e:
        _err(str(e))
    meta = dict(kind="act", data={k: payload.get(k) for k in ("client", "contract", "start", "end", "logo_net", "seal")},
                result={k: payload.get(k) for k in ("days", "hours", "clips", "by_addr")})
    files = [register(docx_path, "act", "ԱԿՏ", meta=meta)]
    if pdf:
        files.insert(0, register(pdf, "act", "ԱԿՏ", meta=meta))
    store.add_client(p["client"])
    ready, how = docfill.pdf_available()
    return dict(ok=True, files=files,
                note="" if pdf else f"PDF չստացվեց ({how}): ուղարկվեց Word տարբերակը")


# ================================================================== 📡 ՏԵԽ. ՄՈՆԻՏՈՐԻՆԳ
def _tm(fn, *a, **k):
    try:
        return fn(*a, **k)
    except ValueError as e:
        _err(str(e))


def _month_arg(month):
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", str(month or "")):
        _err("Սխալ ամիս (ՏՏՏՏ-ԱԱ)")
    return month


@app.get("/api/techmon/status")
def tm_status():
    return techmon.status()


@app.get("/api/techmon/day")
def tm_day(day: str, show_all: int = 0):
    return _tm(techmon.day_view, day, bool(show_all))


@app.post("/api/techmon/cell")
def tm_cell(data: dict = Body(default={})):
    d = body(data, "day", "obj", "addr", "hour")
    cell = _tm(techmon.set_cell, d["day"], d["obj"], d["addr"], d["hour"], d.get("status", ""),
               user=me()["login"], comment=d.get("comment", ""))
    return dict(ok=True, cell=cell)


@app.post("/api/techmon/remark")
def tm_remark(data: dict = Body(default={})):
    """Վանդակի սմայլիկ + մեկնաբանություն. Դատարկ երկուսն էլ = հեռացնել."""
    d = body(data, "day", "obj", "addr", "hour")
    cell = _tm(techmon.set_remark, d["day"], d["obj"], d["addr"], d["hour"], d.get("emoji", ""),
               d.get("remark", ""), user=me()["login"])
    return dict(ok=True, cell=cell)


@app.post("/api/techmon/cells")
def tm_cells(data: dict = Body(default={})):
    """Մի քանի վանդակ միանգամից (տողի բոլոր ⚠-ը -> 🟡 և այլն)."""
    items = (data or {}).get("items") or []
    if not isinstance(items, list) or not items:
        _err("Վանդակներ չկան")
    if len(items) > 600:
        _err("Առավելագույնը 600 վանդակ")
    user = me()["login"]
    n = 0
    with techmon.db() as con:
        for it in items:
            b = body(it, "day", "obj", "addr", "hour")
            _tm(techmon.set_cell, b["day"], b["obj"], b["addr"], b["hour"], b.get("status", ""), user=user,
                comment=(data or {}).get("comment", ""), con=con)
            n += 1
    return dict(ok=True, changed=n)


@app.get("/api/techmon/history")
def tm_history(day: str, obj: str, addr: str, hour: int):
    return techmon.cell_history(day, obj, addr, hour)


@app.get("/api/techmon/month")
def tm_month(month: str):
    return techmon.report_month(_month_arg(month))


@app.get("/api/techmon/month.xlsx")
def tm_month_xlsx(month: str):
    _month_arg(month)
    blob = techmon.export_month_xlsx(month)
    name = f"{techmon.month_label(month)} Тех мониторинг.xlsx"
    return Response(content=blob, headers={
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}", "Cache-Control": "private, no-cache"},
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.get("/print/techmon")
def print_techmon(month: str = Query("")):
    import html as _h
    rep = techmon.report_month(_month_arg(month))
    S = techmon.STATUS_LIST
    head = ["N", "Օբյեկտ", "Հասցե", *S, "Ընդամենը", "Օր", "Հասանելիություն"]
    rows = [[i, r["obj"], r["addr"], *[r["counts"][k] or "" for k in S], r["total"], r["days"],
             f"{r['uptime']}%" if r["uptime"] is not None else "—"] for i, r in enumerate(rep["rows"], 1)]
    cmp_html = ("<h2 style='color:#1D1B5E;margin:18px 0 6px'>Համեմատություն՝ " + _h.escape(rep["prev_label"]) + "</h2>"
                "<table><thead><tr><th>Ցուցանիշ</th><th>" + _h.escape(rep["label"]) + "</th><th>"
                + _h.escape(rep["prev_label"]) + "</th><th>Δ</th><th>%</th></tr></thead><tbody>"
                + "".join(f"<tr><td>{c['status']} {techmon.STATUS_INFO[c['status']]['ru']}</td><td>{c['cur']}</td>"
                          f"<td>{c['prev']}</td><td>{c['delta']:+d}</td>"
                          f"<td>{'—' if c['pct'] is None else str(c['pct']) + '%'}</td></tr>" for c in rep["compare"])
                + "</tbody></table>")
    sub = (f"{rep['label']} · {rep['events']} իրադարձություն · {rep['objects_affected']} օբյեկտ · "
           f"⚠ {rep['totals']['⚠']} · 📞 {rep['totals']['📞']}")
    return print_page("Տեխ. մոնիտորինգ · ամսական հաշվետվություն", sub, head, rows, extra_html=cmp_html)


@app.get("/api/techmon/log")
def tm_log(level: str = "", limit: int = 200):
    return techmon.events(level if level in ("INFO", "WARN", "ERROR") else "", min(max(limit, 1), 1000))


@app.get("/api/techmon/unrec")
def tm_unrec():
    return techmon.events(unrec=True, limit=300)


@app.post("/api/techmon/unrec/resolve")
def tm_unrec_resolve(data: dict = Body(default={})):
    d = body(data, "msg_id", "obj", "addr", "day", "hour")
    _tm(techmail.resolve_unrec, d["msg_id"], d["obj"], d["addr"], d["day"], d["hour"],
        d.get("status") or techmon.S_PROBLEM, me()["login"])
    return dict(ok=True)


@app.post("/api/techmon/unrec/dismiss")
def tm_unrec_dismiss(data: dict = Body(default={})):
    techmail.dismiss_unrec(str(body(data, "msg_id")["msg_id"]))
    return dict(ok=True)


@app.get("/api/techmon/settings")
def tm_settings():
    return dict(settings=techmon.settings(public=True), is_admin=is_admin())


@app.post("/api/techmon/settings")
def tm_settings_save(data: dict = Body(default={})):
    admin_only()
    return dict(settings=techmon.save_settings(data if isinstance(data, dict) else {}))


@app.post("/api/techmon/test")
def tm_test(data: dict = Body(default={})):
    admin_only()
    if isinstance(data, dict) and data:
        techmon.save_settings(data)
    return techmail.test_connection()


@app.post("/api/techmon/run")
def tm_run():
    if techmail.RUN_LOCK.locked():
        return dict(ok=True, running=True)
    threading.Thread(target=techmail.check_mail, name="techmon-run", daemon=True).start()
    return dict(ok=True, started=True)


@app.post("/api/techmon/parse-test")
def tm_parse_test(data: dict = Body(default={})):
    p = techmail.parse_message(str((data or {}).get("subject") or ""), str((data or {}).get("text") or ""),
                               techmon.now())
    if p.get("event"):
        p["event"] = p["event"].strftime("%d.%m.%Y %H:%M:%S")
    s = techmon.settings()
    p["in_hours"] = bool(p.get("ok") and s["work_start"] <= p["hour"] <= s["work_end"])
    return p


@app.post("/api/techmon/import/xlsx")
def tm_import_xlsx(files: list[UploadFile] = File(...)):
    admin_only()
    paths = [read_upload(f, allowed=(".xlsx", ".xlsm"), folder=UPL / "techmon", prefix="imp_") for f in files]
    res = techimport.import_files(paths)
    for p in paths:
        p.unlink(missing_ok=True)
    return res


@app.post("/api/techmon/import/drive")
def tm_import_drive(data: dict = Body(default={})):
    admin_only()
    link = str(body(data, "link")["link"]).strip()
    _tm(techimport.start_drive_import, link)
    store.save_settings(dict(monitor_folder=link))
    return dict(ok=True)


@app.get("/api/techmon/import/state")
def tm_import_state():
    return dict(techimport.state(), link=store.settings().get("monitor_folder", ""))


@app.post("/api/techmon/report/send")
def tm_report_send(data: dict = Body(default={})):
    admin_only()
    to = _tm(techmail.send_report, _month_arg(body(data, "month")["month"]))
    return dict(ok=True, to=to)


# ================================================================== 💼 ԿՊ
@app.post("/api/kp/samples")
def kp_samples():
    paths = kp.make_samples(OUT / "kp_samples")
    out = []
    for i, p in enumerate(paths, 1):
        info = register(p, "kp", f"ԿՊ նմուշ {i}", save_vault=False, sample=True)
        info["sample_kind"] = str(i)
        info["short"] = kp.KINDS[str(i)]["short"]
        out.append(info)
    return dict(files=out)


@app.post("/api/kp/create")
def kp_create(payload: dict = Body(default={})):
    kind = str(payload.get("kind") or "1")
    try:
        data, errors, answers = kpsteps.build(kind, payload.get("data"))
    except ValueError as e:
        _err(str(e))
    if errors:
        return JSONResponse(dict(ok=False, errors=errors), status_code=422)
    d = kpsteps.finalize(kind, data, answers)
    safe = store.safe_name(d.get("client", "client"), 30, "client")
    path = kp.make_kp(d, OUT / f"KP{kind}_{safe}_{date.today():%d%m%Y}.pdf")
    store.add_client(d.get("client", ""))
    meta = dict(kind="kp", kp_kind=kind, data=payload.get("data") or {})
    return dict(ok=True, files=[register(path, "kp", f"ԿՊ {kind}", meta=meta)])


# ================================================================== ⚖️ ԻՐԱՎԱԲԱՆ
def _law_folders():
    """Որտեղ փնտրել բնօրինակը՝ շաբլոններ, իրավաբանի գրադարան, ՕԳՏԱՏԻՐՈՋ անկյունը և ընդհանուր պահոցը
    (ուրիշների անկյունները՝ ոչ)."""
    shared = [p for p in VAULT.iterdir() if p.is_dir() and p.name not in vault.HIDDEN] if VAULT.exists() else []
    return [TPL, LAW_LIB, my_root(), *shared]


def _law_allowed(p: Path):
    rp = p.resolve()
    roots = [TPL, LAW_LIB, LAW_UPLOADS, *_law_folders()]
    return any(rp == r.resolve() or r.resolve() in rp.parents for r in roots)


def _law_result(path_a, name_a, path_b, name_b, best_score=None, candidates=None):
    res = lawyer.compare(path_a, path_b)
    report = None
    try:
        rp = OUT / f"LAW_{date.today():%d%m%Y}_{store.safe_name(Path(name_b).stem, 30, 'file')}.pdf"
        lawyer.make_report(name_a, name_b, res, rp)
        report = register(rp, "law", "Իրավաբանական համեմատություն")
    except Exception as e:  # noqa
        log.warning("law report failed: %s", e)
    changes = []
    for i, c in enumerate(res["changes"][:400], 1):
        changes.append(dict(n=i, kind=c["kind"], where=(c["where_a"] or c["where_b"]),
                            where_b=c["where_b"], old=c["old"][:1200], new=c["new"][:1200],
                            details=c["details"][:20], fmt=c["fmt"][:10], important=c["important"],
                            html=lawyer.html_inline(c["old"], c["new"], 900) if c["kind"] == "change" else ""))
    return dict(ok=True, stats=res["stats"], mode=res["mode"], total=len(res["changes"]),
                changes=changes, truncated=max(0, len(res["changes"]) - 400),
                files=[report] if report else [], original=name_a, checked=name_b,
                checked_path=str(path_b), score=best_score, candidates=candidates or [])


LAW_IMG = tuple(e for e in extract.IMAGE_EXT)


def _law_upload(f: UploadFile):
    """Փաստաթուղթ կամ ստորագրված պայմանագրի ԼՈՒՍԱՆԿԱՐ (տեքստը ճանաչվում է և համեմատվում)."""
    p = read_upload(f, allowed=tuple(lawyer.SUPPORTED) + LAW_IMG, folder=LAW_UPLOADS)
    if p.suffix.lower() not in LAW_IMG:
        return p
    try:
        pars = _scan_to_text(p)
    except RuntimeError as e:
        _err(e, 503)
    if not pars:
        _err("Նկարում տեքստ չգտնվեց / На фото не найден текст")
    txt = p.with_suffix(".txt")
    txt.write_text("\n".join(pars), encoding="utf-8")
    return txt


@app.post("/api/law/compare")
def law_compare(original: UploadFile = File(...), changed: UploadFile = File(...), remember: bool = Form(True)):
    a = _law_upload(original)
    b = _law_upload(changed)
    if remember and a.suffix.lower() in lawyer.SUPPORTED:
        dst = LAW_LIB / store.safe_name(original.filename or a.name, 90, a.name)
        if not dst.exists():
            shutil.copy(a, dst)
    try:
        return _law_result(a, original.filename or a.name, b, changed.filename or b.name)
    except ValueError as e:
        _err(str(e))


@app.post("/api/law/auto")
def law_auto(file: UploadFile = File(...)):
    b = _law_upload(file)
    cands = lawyer.find_original(b, _law_folders())
    listed = [dict(name=Path(c).name, path=str(c), score=round(s * 100, 1)) for s, c in cands]
    if not cands or cands[0][0] < 0.5:
        return dict(ok=False, candidates=listed, checked=file.filename or b.name, checked_path=str(b),
                    detail="Բնօրինակը չգտնվեց (նմանությունը 50%-ից պակաս է): Ընտրեք ցանկից կամ ուղարկեք բնօրինակը ձեռքով")
    score, best = cands[0]
    try:
        return _law_result(best, Path(best).name, b, file.filename or b.name,
                           round(score * 100, 1), listed[1:])
    except ValueError as e:
        _err(str(e))


@app.post("/api/law/compare-with")
def law_compare_with(payload: dict = Body(default={})):
    """Ավտոմատ ռեժիմում՝ ընտրել այլ բնօրինակ (ցանկից)."""
    d = body(payload, "original", "checked")
    a, b = Path(d["original"]), Path(d["checked"])
    for p in (a, b):
        if not p.exists():
            _err("Ֆայլը չգտնվեց, վերբեռնեք կրկին")
        if not _law_allowed(p) or p.suffix.lower() not in lawyer.SUPPORTED:
            _err("Ուղին սխալ է")
    return _law_result(a, a.name, b, b.name)


@app.get("/api/law/originals")
def law_originals():
    rows = []
    for p in sorted(LAW_LIB.glob("*")):
        if p.suffix.lower() in lawyer.SUPPORTED:
            rows.append(dict(name=p.name, path=str(p), size=p.stat().st_size))
    return rows


# ================================================================== 📈 ԵՌԱՄՍՅԱԿԱՅԻՆ ՀԱՇՎԵՏՎՈՒԹՅՈՒՆ
def _deck(deck_id):
    d = quarterly.get(deck_id)
    if not d or not quarterly.visible(d, me()):
        _err("Հաշվետվությունը չգտնվեց", 404)
    return d


@app.get("/api/quarterly")
def q_list():
    return quarterly.decks(me())


@app.post("/api/quarterly")
def q_create(data: dict = Body(default={})):
    return quarterly.create(data, me()["login"])


@app.post("/api/quarterly/{deck_id}/auto")
def q_auto(deck_id: str, data: dict = Body(default={})):
    """✨ Տեքստից (ինչ է արվել եռամսյակում) + նկարներից՝ պատրաստի սլայդներ. նկարները ընտրվում են ինքնաբերաբար."""
    d = _deck(deck_id)
    data = data if isinstance(data, dict) else {}
    prompt = str(data.get("prompt") or d.get("prompt") or "")
    photos = []
    for a in d["attachments"]:
        if a.get("kind") != "image":
            continue
        try:
            photos.append(dict(path=a["path"], abs=quarterly.attachment_path(a["path"]), att=a))
        except ValueError:
            continue
    try:
        slides, info = autodeck.build(d, prompt, photos, data.get("use_ai", True) is not False,
                                      data.get("lang") if data.get("lang") in ("hy", "ru") else None)
    except ValueError as e:
        _err(e)
    atts = [dict(a, **info["photo_meta"].get(a.get("path"), {})) for a in d["attachments"]]
    if data.get("append"):
        slides = d["slides"] + slides[1:-1]
    deck = quarterly.update(deck_id, dict(slides=slides, prompt=prompt, attachments=atts))
    users.log_event("autodeck", me()["login"], IPV.get(), f"{info['engine']} · {info['slides']} слайдов")
    info.pop("photo_meta", None)
    return dict(deck=deck, info=info)


@app.get("/api/quarterly/{deck_id}")
def q_get(deck_id: str):
    return _deck(deck_id)


@app.put("/api/quarterly/{deck_id}")
def q_update(deck_id: str, data: dict = Body(default={})):
    _deck(deck_id)
    try:
        return quarterly.update(deck_id, data)
    except ValueError as e:
        _err(str(e), 404)


@app.delete("/api/quarterly/{deck_id}")
def q_delete(deck_id: str):
    _deck(deck_id)
    try:
        quarterly.delete(deck_id)
    except ValueError as e:
        _err(str(e), 404)
    return dict(ok=True)


@app.post("/api/quarterly/{deck_id}/attach")
def q_attach(deck_id: str, files: list[UploadFile] = File(...)):
    _deck(deck_id)
    out = []
    for f in files:
        name = store.safe_name(f.filename or "file", 90, "file")
        data = f.file.read(MAX_UPLOAD + 1)
        if len(data) > MAX_UPLOAD:
            _err(f"«{name}»՝ ֆայլը մեծ է {MAX_UPLOAD_MB} ՄԲ-ից")
        if not data:
            continue
        try:
            out.append(quarterly.attach(deck_id, name, data))
        except ValueError as e:
            _err(str(e))
    return dict(ok=True, attachments=out, deck=quarterly.get(deck_id))


@app.delete("/api/quarterly/{deck_id}/attach")
def q_detach(deck_id: str, path: str = Query(...)):
    d = _deck(deck_id)
    keep = [a for a in d["attachments"] if a.get("path") != path]
    try:
        p = quarterly.attachment_path(path)
        if p.parent.name == store.safe_name(deck_id, 40, "deck"):
            p.unlink(missing_ok=True)
    except ValueError:
        pass
    return quarterly.update(deck_id, dict(attachments=keep))


@app.get("/api/quarterly/{deck_id}/media")
def q_media(deck_id: str, path: str = Query(...)):
    _deck(deck_id)
    try:
        p = quarterly.attachment_path(path)
    except ValueError as e:
        _err(str(e), 404)
    return send(p)


@app.post("/api/quarterly/{deck_id}/render")
def q_render(deck_id: str, fmt: str = Query("pdf")):
    d = _deck(deck_id)
    safe = store.safe_name(f"{d['title']}_{d['quarter']}Q{d['year']}", 50, "report")
    if fmt == "pptx":
        path = quarterly.render_pptx(d, OUT / f"Report_{safe}.pptx")
    else:
        path = quarterly.render_pdf(d, OUT / f"Report_{safe}.pdf")
    return dict(ok=True, files=[register(path, "quarterly", d["title"])])


@app.post("/api/quarterly/import")
def q_import(file: UploadFile = File(...)):
    p = read_upload(file, allowed=(".xlsx", ".xlsm", ".csv"), folder=UPL / "quarterly")
    try:
        return quarterly.import_numbers(p)
    except Exception as e:  # noqa
        _err(f"Ֆայլից թվերը կարդալ չհաջողվեց՝ {e}")


# ================================================================== 🏷 ՊԱՀԵՍՏ
@app.get("/api/warehouse")
def wh_list(q: str = "", category: str = "", status: str = "", location: str = "", sort: str = "updated"):
    return dict(items=warehouse.items(q, category, status, location, sort), stats=warehouse.stats(),
                meta=dict(categories=warehouse.CATEGORIES, statuses=warehouse.STATUSES, units=warehouse.UNITS))


@app.post("/api/warehouse")
def wh_add(data: dict = Body(default={})):
    try:
        return warehouse.add(data, me()["login"])
    except ValueError as e:
        _err(str(e))


@app.put("/api/warehouse/{item_id}")
def wh_update(item_id: str, data: dict = Body(default={})):
    try:
        return warehouse.update(item_id, data, me()["login"])
    except ValueError as e:
        _err(str(e), 404)


@app.delete("/api/warehouse/{item_id}")
def wh_delete(item_id: str):
    try:
        warehouse.delete(item_id)
    except ValueError as e:
        _err(str(e), 404)
    return dict(ok=True)


@app.post("/api/warehouse/{item_id}/photo")
def wh_photo(item_id: str, file: UploadFile = File(...)):
    if not warehouse.get(item_id):
        _err("Միավորը չգտնվեց", 404)
    name = store.safe_name(file.filename or "photo.jpg", 60, "photo.jpg")
    if Path(name).suffix.lower() not in IMG_EXT:
        _err("Ընդունվում են նկարներ՝ " + ", ".join(IMG_EXT))
    data = file.file.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        _err(f"Նկարը մեծ է {MAX_UPLOAD_MB} ՄԲ-ից")
    info = vault.save_bytes(f"_warehouse/{store.safe_name(item_id, 40, 'x')}", name, data)
    return warehouse.add_photo(item_id, info["path"])


@app.get("/api/warehouse/photo")
def wh_photo_get(path: str = Query(...)):
    if not str(path).replace("\\", "/").startswith("_warehouse/"):
        _err("Ուղին սխալ է", 404)
    try:
        p = vault.abs_path(path)
    except ValueError as e:
        _err(e, 404)
    if not p.exists() or p.is_dir():
        _err("Նկարը չգտնվեց", 404)
    return send(p)


@app.get("/api/warehouse/export")
def wh_export():
    return PlainTextResponse(warehouse.to_csv(), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": "attachment; filename=warehouse.csv"})


# ================================================================== 👤 ԻՄ ԱՆԿՅՈՒՆԸ / ☁️ ՖԱՅԼԱՊԱՀՈՑ
def _vroot(scope=""):
    """me՝ իմ անկյունը, shared՝ ընդհանուր պահոցը, u:<լոգին>՝ ուրիշի անկյունը (միայն ադմին)."""
    u = me()
    s = str(scope or "me")
    if s == "me":
        return vault.user_root(u["login"])
    if s == "shared":
        return VAULT
    if s.startswith("u:"):
        lg = users.norm_login(s[2:])
        if lg != u["login"] and u.get("role") != "admin":
            _err("Միայն ադմինի համար / Только для администратора", 403)
        if not users.get(lg):
            _err("Օգտատերը չգտնվեց / Пользователь не найден", 404)
        return vault.user_root(lg)
    _err("Սխալ թղթապանակ")


def _vault_guard(fn, *a, **k):
    try:
        return fn(*a, **k)
    except ValueError as e:
        _err(str(e))
    except OSError as e:
        _err(f"Ֆայլային սխալ՝ {e}")


def _shared_write(scope):
    if str(scope or "me") == "shared" and not is_admin():
        _err("Ընդհանուր թղթապանակում փոխել/ջնջել կարող է միայն ադմինը / В общей папке менять и удалять "
             "может только администратор", 403)


@app.get("/api/vault/corner")
def v_corner(scope: str = "me"):
    root = _vroot(scope)
    u = me()
    owner = users.get(scope[2:]) if scope.startswith("u:") else u
    return dict(profile=users.public(owner), ip=IPV.get(), categories=_vault_guard(vault.categories, root),
                recent=_vault_guard(vault.recent, root, 10), stats=_vault_guard(vault.stats, root),
                decks=len(quarterly.decks(owner)) if owner else 0,
                users=[dict(login=x["login"], name=x["name"]) for x in users.users_list()] if is_admin() else [])


@app.get("/api/vault/list")
def v_list(path: str = "", scope: str = "me"):
    return _vault_guard(vault.listdir, path, _vroot(scope))


@app.get("/api/vault/tree")
def v_tree(scope: str = "me"):
    return _vault_guard(vault.tree, 2, _vroot(scope))


@app.get("/api/vault/search")
def v_search(q: str = "", scope: str = "me"):
    return _vault_guard(vault.search, q, 300, _vroot(scope))


@app.get("/api/vault/stats")
def v_stats(scope: str = "me"):
    return _vault_guard(vault.stats, _vroot(scope))


@app.post("/api/vault/upload")
def v_upload(path: str = Form(""), scope: str = Form("me"), files: list[UploadFile] = File(...)):
    root = _vroot(scope)
    out = []
    for f in files:
        name = store.safe_name(f.filename or "file", 110, "file")
        data = f.file.read(MAX_UPLOAD + 1)
        if len(data) > MAX_UPLOAD:
            _err(f"«{name}»՝ ֆայլը մեծ է {MAX_UPLOAD_MB} ՄԲ-ից")
        if not data:
            continue
        out.append(_vault_guard(vault.save_bytes, path, name, data, root))
    return dict(ok=True, items=out)


@app.post("/api/vault/mkdir")
def v_mkdir(data: dict = Body(default={})):
    d = body(data, "name")
    return _vault_guard(vault.mkdir, data.get("path", ""), d["name"], _vroot(data.get("scope")))


@app.post("/api/vault/rename")
def v_rename(data: dict = Body(default={})):
    d = body(data, "path", "name")
    _shared_write(data.get("scope"))
    return _vault_guard(vault.rename, d["path"], d["name"], _vroot(data.get("scope")))


@app.post("/api/vault/move")
def v_move(data: dict = Body(default={})):
    d = body(data, "path")
    _shared_write(data.get("scope"))
    return _vault_guard(vault.move, d["path"], data.get("to", ""), _vroot(data.get("scope")))


@app.delete("/api/vault/item")
def v_delete(path: str = Query(...), scope: str = "me"):
    _shared_write(scope)
    _vault_guard(vault.delete, path, _vroot(scope))
    return dict(ok=True)


@app.post("/api/vault/copy")
def v_copy(data: dict = Body(default={})):
    """Ընդհանուր/ուրիշի ֆայլը՝ պատճեն իմ անկյունում."""
    d = body(data, "path")
    src = _vault_guard(vault.abs_path, d["path"], _vroot(data.get("scope")))
    if not src.exists() or src.is_dir():
        _err("Ֆայլը չգտնվեց", 404)
    return _vault_guard(vault.save_bytes, data.get("to", ""), src.name, src.read_bytes(), my_root())


@app.get("/api/vault/file")
def v_file(path: str = Query(...), download: int = 0, scope: str = "me"):
    p = _vault_guard(vault.abs_path, path, _vroot(scope))
    if not p.exists() or p.is_dir():
        _err("Ֆայլը չգտնվեց", 404)
    return send(p, p.name, bool(download))


@app.get("/api/vault/print")
def v_print(path: str = Query(...), scope: str = "me"):
    p = _vault_guard(vault.abs_path, path, _vroot(scope))
    if not p.exists() or p.is_dir():
        _err("Ֆայլը չգտնվեց", 404)
    if p.suffix.lower() == ".docx":
        return HTMLResponse(docx_html.page_html(p, p.stem))
    return send(p, p.name)


# ================================================================== 📷 ՃԱՆԱՉՈՒՄ ԼՈՒՍԱՆԿԱՐԻՑ
@app.get("/api/extract/status")
def extract_status():
    return extract.status()


@app.post("/api/extract/local-ai")
def extract_local_ai(data: dict = Body(default={})):
    """Տեղային ԻԻ (Ollama)՝ միացնել/անջատել, մոդելը ընտրել (միայն ադմին)."""
    admin_only()
    localai.set_conf(data.get("enabled"), data.get("model"))
    localai.status(force=True)
    return extract.status()


@app.post("/api/extract")
def extract_fields(file: UploadFile = File(...), spec: str = Form("{}")):
    """Նկար/PDF/Word -> ձևի դաշտեր. spec՝ {section, note, fields:[{key,label,type,hint,options}], match_addresses}."""
    try:
        sp = json.loads(spec or "{}")
    except ValueError:
        _err("Սխալ հարցում (spec)")
    sp = sp if isinstance(sp, dict) else {}
    p = read_upload(file, allowed=extract.SUPPORTED, folder=UPL / "extract", max_bytes=30 * 1024 * 1024)
    try:
        values = extract.extract(p, sp.get("fields"), str(sp.get("section") or ""), str(sp.get("note") or ""))
    except ValueError as e:
        _err(e)
    except RuntimeError as e:
        _err(e, 503)
    finally:
        p.unlink(missing_ok=True)
    res = dict(ok=True, values=values, filled=len(values), engine=extract.status()["mode"])
    key = sp.get("match_addresses")
    if key and isinstance(values.get(key), list):
        res["matched"], res["unmatched"] = extract.match_addresses(values[key])
    if isinstance(values.get("times"), str):
        try:
            res["slots"] = mp.parse_times(values["times"])
        except ValueError:
            res["slots"] = []
    users.log_event("extract", me()["login"], IPV.get(), f"{sp.get('section', '')}: {len(values)}")
    return res


# ================================================================== ✏️ ԽՄԲԱԳՐԻՉ
def _scan_to_text(path):
    """Սկան/նկար -> պարբերություններ (տեղային OCR, առանց ինտերնետի)."""
    try:
        return extract.paragraphs(path)
    except ValueError:          # տեքստ չգտնվեց՝ կանչողը ինքը կասի «տեքստ չկա»
        return []


def _edit_model(token):
    try:
        return editor.model(token, me(), _scan_to_text)
    except LookupError as e:
        _err(e, 404)
    except PermissionError as e:
        _err(e, 403)
    except ValueError as e:
        _err(e)
    except RuntimeError as e:
        _err(e, 503)


@app.post("/api/edit/open")
def edit_open(file: UploadFile = File(...)):
    p = read_upload(file, allowed=editor.SUPPORTED, folder=UPL / "edit_in")
    try:
        token = editor.open_copy(p, file.filename or p.name, me()["login"])
    finally:
        p.unlink(missing_ok=True)
    return _edit_model(token)


@app.post("/api/edit/open-vault")
def edit_open_vault(data: dict = Body(default={})):
    d = body(data, "path")
    p = _vault_guard(vault.abs_path, d["path"], _vroot(data.get("scope")))
    if not p.exists() or p.is_dir():
        _err("Ֆայլը չգտնվեց", 404)
    if p.suffix.lower() not in editor.SUPPORTED:
        _err(f"«{p.suffix}» ձևաչափը չի խմբագրվում / Этот формат нельзя редактировать")
    return _edit_model(editor.open_copy(p, p.name, me()["login"]))


@app.post("/api/edit/open-file")
def edit_open_file(data: dict = Body(default={})):
    e, p = file_entry(body(data, "fid")["fid"])
    if p.suffix.lower() not in editor.SUPPORTED:
        _err("Այս ֆայլը չի խմբագրվում / Этот файл нельзя редактировать")
    return _edit_model(editor.open_copy(p, e["name"], me()["login"]))


@app.get("/api/edit/{token}")
def edit_get(token: str):
    return _edit_model(token)


@app.get("/api/edit/{token}/file")
def edit_file(token: str, download: int = 0):
    try:
        _, p, info = editor.session(token, me())
    except (LookupError, PermissionError) as e:
        _err(e, 404)
    return send(p, p.name, bool(download))


@app.post("/api/edit/{token}/save")
def edit_save(token: str, payload: dict = Body(default={})):
    try:
        out, n = editor.save(token, me(), payload if isinstance(payload, dict) else {})
    except LookupError as e:
        _err(e, 404)
    except PermissionError as e:
        _err(e, 403)
    except ValueError as e:
        _err(e)
    files = [register(out, "edited", "✏️ " + out.stem)]
    note = ""
    if payload.get("pdf") and out.suffix.lower() == ".docx":
        pdf = docfill.to_pdf(out)
        if pdf:
            files.insert(0, register(pdf, "edited", "✏️ " + out.stem))
        else:
            note = "PDF չստացվեց (" + docfill.pdf_available()[1] + ")"
    users.log_event("edit", me()["login"], IPV.get(), out.name)
    return dict(ok=True, files=files, changes=n, note=note)


# ================================================================== 🎙 ՁԱՅՆ
def _voice_mod():
    try:
        import voice_tts
        return voice_tts
    except Exception as e:  # noqa
        _err(f"Ձայնի մոդուլը հասանելի չէ՝ {e}. Գրեք՝ pip install -r requirements_voice.txt")


@app.get("/api/voice/voices")
def voice_list():
    v = _voice_mod()
    return [dict(key=k, name=val["name"], kind=val["kind"]) for k, val in v.all_voices().items()]


@app.post("/api/voice/sample")
async def voice_sample(data: dict = Body(default={})):
    v = _voice_mod()
    key = str(body(data, "key")["key"])
    try:
        path = await asyncio.wait_for(v.sample(key), timeout=900)
    except asyncio.TimeoutError:
        _err("Շատ երկար տևեց (15 րոպե)")
    except ValueError as e:
        _err(str(e))
    except Exception as e:  # noqa
        log.exception("voice sample failed")
        _err(f"Նմուշը չստացվեց՝ {type(e).__name__}: {e}")
    return dict(ok=True, files=[register(path, "voice", "Ձայնի նմուշ", save_vault=False, sample=True)])


@app.post("/api/voice/synth")
async def voice_synth(data: dict = Body(default={})):
    v = _voice_mod()
    d = body(data, "key", "text")
    try:
        path = await asyncio.wait_for(v.synth(str(d["text"]), str(d["key"])), timeout=900)
    except asyncio.TimeoutError:
        _err("Շատ երկար տևեց (15 րոպե): Փորձեք ավելի կարճ տեքստ")
    except ValueError as e:
        _err(str(e))
    except Exception as e:  # noqa
        log.exception("voice synth failed")
        _err(f"Ձայնագրման սխալ՝ {type(e).__name__}: {e}")
    final = OUT / f"voice_{int(time.time() * 1000)}.mp3"
    shutil.move(str(path), final)
    return dict(ok=True, files=[await asyncio.to_thread(register, final, "voice", "Ձայն")])


@app.post("/api/voice/upload")
def voice_upload(name: str = Form(...), file: UploadFile = File(...)):
    v = _voice_mod()
    from config import AUDIO_EXT
    p = read_upload(file, allowed=AUDIO_EXT, folder=VOICE_UPLOADS)
    try:
        sec, warn = v.check_reference(p)
        key = v.add_mp3_voice(name, str(p))
    except ValueError as e:
        p.unlink(missing_ok=True)
        _err(str(e))
    except Exception as e:  # noqa
        p.unlink(missing_ok=True)
        log.exception("voice add failed")
        _err(f"Ձայնը ավելացնել չհաջողվեց՝ {e}")
    return dict(ok=True, key=key, seconds=round(sec), warning=warn)


@app.delete("/api/voice/{key}")
def voice_delete(key: str):
    v = _voice_mod()
    if not v.delete_voice(key):
        _err("Այս ձայնը ջնջել չի կարելի")
    return dict(ok=True)


@app.get("/api/voice/status")
def voice_status():
    """Պատրա՞ստ է դիկտորը (ձայնի կլոնավորում) այս համակարգչում."""
    v = _voice_mod()
    ready, missing = v.clone_status()
    return dict(clone_ready=ready, missing=missing)


@app.post("/api/voice/dub")
async def voice_dub(file: UploadFile = File(...), key: str = Form(...), mode: str = Form("convert")):
    """Դիկտոր. ձայնային հաղորդագրություն -> պատրաստի MP3՝ ընտրված դիկտորի ձայնով."""
    v = _voice_mod()
    from config import AUDIO_EXT
    p = await asyncio.to_thread(read_upload, file, AUDIO_EXT + (".webm", ".mp4"), VOICE_UPLOADS)
    try:
        path, text = await asyncio.wait_for(v.dub(p, key, "retell" if mode == "retell" else "convert"), timeout=1200)
    except asyncio.TimeoutError:
        _err("Շատ երկար տևեց (20 րոպե): Փորձեք ավելի կարճ ձայնագրություն")
    except ValueError as e:
        _err(str(e))
    except ImportError:
        _err("Դիկտորի գրադարանները տեղադրված չեն: Գործարկեք install_voice.bat և վերագործարկեք run.bat-ը")
    except Exception as e:  # noqa
        log.exception("voice dub failed")
        _err(f"Դիկտորի սխալ՝ {type(e).__name__}: {e}")
    finally:
        p.unlink(missing_ok=True)
    final = OUT / f"diktor_{int(time.time() * 1000)}.mp3"
    shutil.move(str(path), final)
    return dict(ok=True, text=text, files=[await asyncio.to_thread(register, final, "voice", "Դիկտոր")])


@app.post("/api/voice/stt")
async def voice_stt(file: UploadFile = File(...)):
    from config import AUDIO_EXT
    p = await asyncio.to_thread(read_upload, file, AUDIO_EXT + (".webm", ".mp4"), VOICE_UPLOADS)
    try:
        import stt
        text = await stt.transcribe(p)
    except Exception as e:  # noqa
        _err(f"Ճանաչումը չհաջողվեց՝ {e}")
    finally:
        p.unlink(missing_ok=True)
    return dict(ok=True, text=text)


# ================================================================== ՖԱՅԼԵՐ (պատրաստված)
@app.get("/api/files/{fid}")
def file_get(fid: str, download: int = 0):
    e, p = file_entry(fid)
    return send(p, e["name"], bool(download))


@app.get("/api/files/{fid}/print")
def file_print(fid: str):
    """DOCX՝ տպելու պատրաստ HTML էջ, մնացածը՝ բրաուզերի դիտիչով."""
    e, p = file_entry(fid)
    if p.suffix.lower() == ".docx":
        try:
            return HTMLResponse(docx_html.page_html(p, e.get("title") or p.stem))
        except Exception as ex:  # noqa
            log.exception("docx print failed")
            _err(f"Տպելու տեսքը չստացվեց՝ {ex}")
    return send(p, e["name"])


@app.post("/api/files/{fid}/vault")
def file_to_vault(fid: str, data: dict = Body(default={})):
    e, p = file_entry(fid)
    info = _vault_guard(vault.save_bytes, data.get("path", ""), p.name, p.read_bytes(), my_root())
    return dict(ok=True, item=info)


@app.get("/api/files")
def files_recent(limit: int = 30, all: int = 0):  # noqa: A002
    db = _files_db()
    u = me()
    everyone = bool(all) and u.get("role") == "admin"
    rows = []
    for fid, e in list(db.items())[::-1]:
        if e.get("sample") or (not everyone and e.get("owner") != u["login"]):
            continue
        if not Path(e["path"]).exists():
            continue
        rows.append(dict(id=fid, name=e["name"], kind=e["kind"], ext=e["ext"], size=e["size"],
                         created=e["created"], owner=e.get("owner", ""), url=f"/api/files/{fid}",
                         download=f"/api/files/{fid}?download=1", print_url=f"/api/files/{fid}/print"))
        if len(rows) >= limit:
            break
    return rows


# ================================================================== 🛠 ՖԻՔՍԻԿ
@app.get("/api/diagnostics")
def diag(force: int = 0):
    return diagnostics.run_checks(bool(force))


@app.get("/api/logs")
def logs(level: str = "", limit: int = 120):
    return diagnostics.events(level or None, limit)


@app.delete("/api/logs")
def logs_clear():
    admin_only()
    diagnostics.clear_events()
    return dict(ok=True)


@app.post("/api/fixik/ask")
def fixik_ask(data: dict = Body(default={})):
    q = str(data.get("q") or "")
    lang = "ru" if str(data.get("lang")) == "ru" else "hy"
    answer = diagnostics.ask(q, lang)
    if not answer:
        d = diagnostics.run_checks()
        problems = [c for c in d["checks"] if c["state"] != "ok"]
        if problems:
            answer = ("Չգտա ճիշտ պատասխանը, բայց տեսնում եմ այս խնդիրները՝\n"
                      if lang == "hy" else "Точного ответа не нашёл, но вижу такие проблемы:\n")
            answer += "\n".join(f"• {c['name']}: {c['detail']}" + (f" → {c['fix']}" if c["fix"] else "")
                                for c in problems[:5])
        else:
            answer = ("Համակարգը կարգին է: Գրեք հարցը այլ բառերով (օր.՝ «pdf», «ակտ», «հասցե», «պահեստ»)."
                      if lang == "hy" else
                      "Система в порядке. Спросите другими словами (например: «pdf», «акт», «адрес», «склад»).")
    return dict(answer=answer, questions=[k["q"][0] for k in diagnostics.KB])


@app.post("/api/client-error")
def client_error(data: dict = Body(default={})):
    diagnostics.add_event("ERROR", "browser", str(data.get("message"))[:800], str(data.get("stack") or "")[:1500])
    return dict(ok=True)


# ================================================================== ՏՊԵԼ (HTML էջեր)
PRINT_CSS = """
@page { size: A4; margin: 14mm; }
body { font-family: Sylfaen, "Segoe UI", Arial, sans-serif; color:#12152E; margin:0; padding:18px; background:#fff; }
h1 { color:#1D1B5E; font-size:20pt; margin:0 0 4px; }
.sub { color:#6B7090; font-size:10pt; margin-bottom:14px; }
table { border-collapse:collapse; width:100%; font-size:9.5pt; }
th { background:#DDEBF7; color:#1D1B5E; }
th, td { border:1px solid #DDE0EE; padding:5px 7px; text-align:left; vertical-align:top; }
tr:nth-child(even) td { background:#F7F8FC; }
.bar { height:4px; background:linear-gradient(90deg,#2E8CF0,#6A3DE8); margin:0 0 12px; border-radius:2px; }
.foot { margin-top:14px; color:#6B7090; font-size:8.5pt; }
button { font:inherit; padding:8px 16px; border:0; border-radius:10px; cursor:pointer;
         background:linear-gradient(135deg,#2E8CF0,#6A3DE8); color:#fff; }
@media print { .noprint { display:none } }
"""


def print_page(title, sub, head, rows, foot="", extra_html=""):
    import html as _h
    th = "".join(f"<th>{_h.escape(str(h))}</th>" for h in head)
    body_rows = "".join("<tr>" + "".join(f"<td>{_h.escape(str(c))}</td>" for c in r) + "</tr>" for r in rows)
    return HTMLResponse(
        f"<!doctype html><html lang='hy'><head><meta charset='utf-8'>"
        f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{_h.escape(title)}</title><style>{PRINT_CSS}</style></head><body>"
        f"<div class='noprint' style='text-align:center;margin-bottom:14px'>"
        f"<button onclick='window.print()'>🖨 Տպել / Печать</button></div>"
        f"<h1>{_h.escape(title)}</h1><div class='sub'>{_h.escape(sub)}</div><div class='bar'></div>"
        f"<table><thead><tr>{th}</tr></thead><tbody>{body_rows}</tbody></table>{extra_html}"
        f"<div class='foot'>{_h.escape(foot or mp.COMPANY_LINE)}</div></body></html>")


@app.get("/print/warehouse")
def print_warehouse(q: str = "", category: str = "", status: str = "", location: str = ""):
    rows = warehouse.items(q, category, status, location, "name")
    return print_page("Պահեստի ցանկ", f"{len(rows)} միավոր · {datetime.now():%d.%m.%Y %H:%M}",
                      ["N", "Անվանում", "Տեսակ", "Որտեղ է", "Քանակ", "Վիճակ", "Սերիական", "Նկարագրություն"],
                      [[i, r["name"], r["category"], r["location"], f"{r['qty']} {r['unit']}",
                        r["status"], r["serial"], r["description"]] for i, r in enumerate(rows, 1)])


def _n(v):
    try:
        return f"{int(v):,}".replace(",", " ")
    except (TypeError, ValueError):
        return str(v)


@app.get("/print/act")
def print_act(token: str = Query("")):
    import html as _h
    data = store.read_json(UPL / "print" / f"{store.safe_name(token, 40, 'x')}.json", None)
    if not data or (data.get("owner") and data["owner"] != me()["login"] and not is_admin()):
        _err("Տպելու տվյալները չգտնվեցին", 404)
    hours = data.get("hours") or []
    pct = lambda d: f"{d['pct']}%" if d.get("pct") is not None else "—"   # noqa: E731
    src = hours if hours else data.get("days") or []
    rows = [[d["label"], _n(d["planned"]), _n(d["played"]), _n(d["missed"]), pct(d)] for d in src]
    rows.append(["Ընդամենը", _n(data.get("planned")), _n(data.get("played")), _n(data.get("missed")), pct(data)])
    extra = ""
    import actpdf
    by = [dict(addr=str(a.get("addr") or ""), off_hours=actsvc._int(a.get("off_hours")), missed=actsvc._int(a.get("missed")),
               off_detail=str(a.get("off_detail") or ""), off_list=actsvc._off_list(a))
          for a in data.get("by_addr") or [] if isinstance(a, dict)]
    off = actpdf.off_rows(by)
    if off:
        extra = ("<h2 style='color:#1D1B5E;margin:18px 0 6px'>Գովազդի անջատումները՝ ըստ հասցեների և օրերի</h2>"
                 "<table><thead><tr><th>N</th><th>Հասցե</th><th>Ամսաթիվ</th><th>Անջատված ժամերը</th><th>Չհեռ.</th>"
                 "</tr></thead><tbody>"
                 + "".join(f"<tr><td>{r['n'] if r['first'] else ''}</td>"
                           f"<td>{_h.escape(r['addr']) if r['first'] else ''}</td><td>{_h.escape(r['date'])}</td>"
                           f"<td>{_h.escape(r['hours'])}</td><td>{_n(r['missed'])}</td></tr>" for r in off)
                 + "</tbody></table>")
    return print_page("ԱԿՏ · հեռարձակման հաշվետվություն",
                      f"{data.get('client', '')} · {data.get('period', '')}",
                      ["Ժամ" if hours else "Օր", "Նախատեսված", "Հեռարձակված", "Չհեռարձակված", "Կատարում"], rows,
                      extra_html=extra)


@app.post("/api/print/act")
def print_act_token(data: dict = Body(default={})):
    token = store.new_id("p")
    (UPL / "print").mkdir(parents=True, exist_ok=True)
    store.write_json(UPL / "print" / f"{token}.json", dict(data if isinstance(data, dict) else {}, owner=me()["login"]))
    return dict(url=f"/print/act?token={token}")


@app.get("/print/addresses")
def print_addresses(nets: str = ""):
    idx = [int(x) for x in re.findall(r"\d+", nets)]
    nets_all = store.networks()
    rows, n = [], 0
    for i, net in enumerate(nets_all):
        if idx and i not in idx:
            continue
        for a in net["addresses"]:
            n += 1
            rows.append([n, net["name"], a])
    return print_page("Հասցեների ցանկ", f"{len(rows)} հասցե · {datetime.now():%d.%m.%Y}",
                      ["N", "Ցանց", "Հասցե"], rows)


@app.get("/print/stores")
def print_stores(nets: str = "", district: str = ""):
    idx = [int(x) for x in re.findall(r"\d+", nets)]
    rows, n = [], 0
    for net in adspace.overview()["networks"]:
        if idx and net["index"] not in idx:
            continue
        for a in net["addresses"]:
            if district and a["district"] != district:
                continue
            n += 1
            active = [b["client"] for b in a.get("bookings", []) if adspace._active(b)]
            rows.append([n, net["short"], a["address"], a["district"], f"{a['occupied']}/{a['capacity']}",
                         a["free"], ", ".join(active)])
    free = sum(r[5] for r in rows)
    return print_page("Գովազդային տեղեր", f"{len(rows)} հասցե · ազատ՝ {free} տեղ · {datetime.now():%d.%m.%Y}",
                      ["N", "Ցանց", "Հասցե", "Թաղամաս", "Զբաղված", "Ազատ", "Գովազդատուներ"], rows)


@app.get("/print/playing")
def print_playing(nets: str = "", client: str = ""):
    """🎵 Ինչ է հնչում՝ ցանց / հասցե / գովազդատու / հոլովակ."""
    idx = [int(x) for x in re.findall(r"\d+", nets)]
    d = adspace.now_playing()
    rows = []
    for r in d["rows"]:
        if (idx and r["net"] not in idx) or (client and r["client"].casefold() != client.casefold()):
            continue
        rows.append([len(rows) + 1, r["short"], r["address"], r["client"], r["clip"] or "—",
                     f"{r['start'] or '…'} — {r['end'] or '∞'}"])
    return print_page("Ինչ է հնչում / Что играет", f"{len(rows)} · {datetime.now():%d.%m.%Y}",
                      ["N", "Ցանց", "Հասցե", "Գովազդատու", "Հոլովակ", "Ժամկետ"], rows)


@app.get("/print/prices")
def print_prices():
    rows = []
    for n in adspace.overview()["networks"]:
        custom = sum(1 for a in n["addresses"] if a["price_custom"])
        rows.append([len(rows) + 1, n["short"], n["count"], f"{n['price']:,}".replace(",", " ") if n["price"] else "—",
                     custom or "", n["price_note"]])
    return print_page("Գներ / Цены", f"ՀՀ դրամ, մեկ հասցե, ամսական · {datetime.now():%d.%m.%Y}",
                      ["N", "Ցանց", "Հասցե", "Գին ֏", "Առանձին գներ", "Նշում"], rows)


@app.get("/print/quarterly/{deck_id}")
def print_quarterly(deck_id: str):
    import html as _h
    d = _deck(deck_id)
    parts = []
    for i, s in enumerate(d["slides"], 1):
        bits = [f"<h2 style='color:#1D1B5E;margin:18px 0 6px'>{i}. {_h.escape(s['title'] or quarterly.TYPE_NAMES.get(s['type'], ''))}</h2>"]
        if s["subtitle"]:
            bits.append(f"<p style='color:#6A3DE8;font-weight:700'>{_h.escape(s['subtitle'])}</p>")
        if s["body"]:
            bits.append(f"<p>{_h.escape(s['body'])}</p>")
        if s["type"] in ("bullets", "photo_text") and s["items"]:
            bits.append("<ul>" + "".join(f"<li>{_h.escape(x)}</li>" for x in s["items"]) + "</ul>")
        if s["type"] in ("metrics", "chart") and s["items"]:
            bits.append("<table><tr>" + "".join(f"<th>{_h.escape(x['label'])}</th>" for x in s["items"]) + "</tr><tr>"
                        + "".join(f"<td><b>{_h.escape(x['value'])}</b><br><small>{_h.escape(x['note'])}</small></td>"
                                  for x in s["items"]) + "</tr></table>")
        if s["type"] == "table" and (s["head"] or s["rows"]):
            head = s["head"] or (s["rows"][0] if s["rows"] else [])
            rws = s["rows"] if s["head"] else s["rows"][1:]
            bits.append("<table><thead><tr>" + "".join(f"<th>{_h.escape(str(h))}</th>" for h in head)
                        + "</tr></thead><tbody>"
                        + "".join("<tr>" + "".join(f"<td>{_h.escape(str(c))}</td>" for c in r) + "</tr>" for r in rws)
                        + "</tbody></table>")
        parts.append("".join(bits))
    return HTMLResponse(
        f"<!doctype html><html lang='hy'><head><meta charset='utf-8'><title>{_h.escape(d['title'])}</title>"
        f"<style>{PRINT_CSS}</style></head><body>"
        f"<div class='noprint' style='text-align:center;margin-bottom:14px'>"
        f"<button onclick='window.print()'>🖨 Տպել / Печать</button></div>"
        f"<h1>{_h.escape(d['title'])}</h1>"
        f"<div class='sub'>{quarterly.QUARTERS[d['quarter']]} {d['year']} · {_h.escape(d['client'])}</div>"
        f"<div class='bar'></div>{''.join(parts)}"
        f"<div class='foot'>{mp.COMPANY_LINE}</div></body></html>")


# ================================================================== ՍՏԱՏԻԿ
app.mount("/static", StaticFiles(directory=str(WEB)), name="static")


@app.get("/")
def index():
    f = WEB / "index.html"
    if not f.exists():
        return HTMLResponse("<h1>web/index.html չգտնվեց</h1>", status_code=500)
    return FileResponse(f, media_type="text/html", headers={"Cache-Control": "no-cache"})


@app.get("/favicon.ico")
def favicon():
    p = BASE / "assets" / "logo.png"
    return send(p) if p.exists() else Response(status_code=204)


@app.get("/logo.png")
def logo():
    p = BASE / "assets" / "logo.png"
    if not p.exists():
        return Response(status_code=404)
    return send(p)


def lan_ips():
    """Այս համակարգչի հասցեները տեղական ցանցում (192.168.x.x, 10.x.x.x ...), որով կարելի է բացել հավելվածը."""
    import socket
    found = []
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith(("127.", "169.254.")) and ip not in found:
                found.append(ip)
    except OSError:
        pass
    try:   # ակտիվ ելքի ինտերֆեյսը (UDP-ով, փաթեթ չի ուղարկվում)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            ip = s.getsockname()[0]
            if not ip.startswith(("127.", "169.254.")):
                if ip in found:
                    found.remove(ip)
                found.insert(0, ip)
    except OSError:
        pass
    return found


@app.get("/api/network")
def network_info(request: Request):
    """Ո՞ր հասցեով կարող են բացել մյուսները (Կարգավորումներ -> կիսվել)."""
    return dict(port=PORT, shared=HOST in ("0.0.0.0", "::"), password=True,
                urls=[f"http://{ip}:{PORT}" for ip in lan_ips()], current=str(request.base_url).rstrip("/"))


# ================================================================== մաքրում (հին ժամանակավոր ֆայլեր)
def _cleanup():
    """uploads/-ի հին ժամանակավոր ֆայլերը (3 օրից հին) ջնջվում են՝ սկավառակը չի լցվում."""
    try:
        editor.cleanup(3)
        cutoff = time.time() - 3 * 86400
        for folder in (ACT_UPLOADS, LAW_UPLOADS, VOICE_UPLOADS, UPL / "print", UPL / "extract", UPL / "edit_in",
                       UPL / "quarterly"):
            if not folder.exists():
                continue
            for p in folder.iterdir():
                try:
                    if p.is_file() and p.stat().st_mtime < cutoff:
                        p.unlink()
                except OSError:
                    continue
    except Exception:  # noqa
        log.warning("cleanup failed", exc_info=True)


def print_office_link():
    ips = lan_ips() if HOST in ("0.0.0.0", "::") else []
    for ip in ips:
        print(f"\n      http://{ip}:{PORT}\n", flush=True)


PUBLIC_URL = {"url": ""}       # Cloudflare-ի ժամանակավոր հղումը (գնացուցակի կոճակի համար)


def start_public_link():
    """Եթե cloudflared-ը տեղադրված է՝ բացում է հանրային հղում և տպում այն սերվերի պատուհանում."""
    import shutil as _sh
    import subprocess
    exe = _sh.which("cloudflared")
    if not exe or os.getenv("NO_PUBLIC_LINK"):
        return

    def run():
        try:
            p = subprocess.Popen([exe, "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{PORT}"],
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                                 errors="replace")
        except OSError:
            return
        for line in p.stdout:
            m = re.search(r"https://[a-z0-9\-]+\.trycloudflare\.com", line)
            if m:
                PUBLIC_URL["url"] = m.group(0)
                print("\n  " + "=" * 62)
                print(f"   ССЫЛКА ДЛЯ ОФИСА / ЧАТА (откроется из любого места):\n\n      {m.group(0)}\n")
                print("   Отправьте её людям — они просто открывают и заходят.")
                print("  " + "=" * 62 + "\n", flush=True)
                print_office_link()
                break
        for _ in p.stdout:      # читаем дальше, чтобы процесс не завис
            pass

    threading.Thread(target=run, name="public-link", daemon=True).start()


def main():
    import uvicorn
    try:
        import sys
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa
        pass
    threading.Thread(target=_cleanup, daemon=True).start()
    techmail.start_background()          # տեխ. մոնիտորինգ՝ նամակների ստուգում + ամսական հաշվետվություն (եթե միացված է)
    if users.ensure_bootstrap_admin():
        print("  Создан пользователь «admin» (пароль — APP_PASSWORD)")
    off = users.disable_guests()
    if off:
        print(f"  🛡 Отключены гостевые входы без пароля: {', '.join(off)} (их файлы сохранены; "
              f"передать человеку: merge <guest-…> <логин>)")
    admins = [r for r in users.users_list() if r["role"] == "admin" and r["status"] == "active"]
    if not admins:
        print("\n  !!! Нет администратора. Создайте вход прямо здесь:  add <логин> <пароль> admin <Имя>\n")
    else:
        print(f"  Администраторы: {', '.join(r['login'] for r in admins)}  "
              f"(забыли пароль? напишите: passwd <логин> <новый пароль>)")
    checks = diagnostics.run_checks(True)
    log.info("Mix Media web · ստուգում՝ %s (սխալ %s, զգուշացում %s)",
             checks["state"], checks["errors"], checks["warnings"])
    for c in checks["checks"]:
        if c["state"] == "error":
            log.warning("%s: %s %s", c["name"], c["detail"], f"-> {c['fix']}" if c["fix"] else "")
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        busy = s.connect_ex(("127.0.0.1", PORT)) == 0
    if busy:   # սերվերը արդեն աշխատում է (մեկ այլ պատուհանում)՝ սխալ չենք տալիս, միայն հղումը
        print(f"\n  Сервер уже запущен в другом окне (порт {PORT} занят). Ссылка та же:")
        print_office_link()
        return
    print(f"\n  Mix Media  ->  http://127.0.0.1:{PORT}   (на этом компьютере)")
    users.start_console()
    if HOST in ("0.0.0.0", "::"):
        if lan_ips():
            print("  " + "=" * 60)
            print("   Отправьте эту ссылку тем, кто в той же сети / Wi-Fi:")
            print_office_link()
            print("  " + "=" * 60, flush=True)
        else:
            print("  Сетевой адрес не найден: подключитесь к Wi-Fi или кабелю", flush=True)
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning", access_log=False,
                timeout_keep_alive=30, server_header=False)


if __name__ == "__main__":
    main()
