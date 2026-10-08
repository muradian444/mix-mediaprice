# -*- coding: utf-8 -*-
"""🛡 Կիբեռանվտանգություն / Кибербезопасность сайта.

Ամեն հարցում անցնում է այս շերտով (Shield)՝ մինչև մուտքի ստուգումը.
  • արգելափակված IP-ներ (ավտոմատ և ձեռքով), ժամկետով
  • հարձակման նշաններ՝ սկաներներ (/wp-admin, /.env, ../, .php …), մեծ հոսք (flood), գաղտնաբառի ընտրություն
  • CSRF՝ POST/PUT/DELETE միայն մեր էջից (Origin = Host)
  • Host-ի ստուգում (երբ կա դոմեն՝ APP_DOMAIN) — կեղծ դոմեններով հարցումները մերժվում են
  • պաշտպանիչ վերնագրեր (CSP, X-Frame-Options, nosniff, Referrer-Policy, HSTS՝ https-ի դեպքում)
  • չափազանց մեծ հարցումներ (Content-Length)
Ամեն ինչ գրվում է data/security.json և data/logs/security.log; ադմինը տեսնում է ⚙️ Настройки → 🛡 Безопасность:"""
import ipaddress
import json
import os
import re
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path

from config import DATA, MAX_UPLOAD
from store import read_json, write_json

FILE = DATA / "security.json"
LOG = DATA / "logs" / "security.log"
_LOCK = threading.RLock()
_HITS = {}                 # ip -> deque[time]   (հոսքի սահմանափակում)
_SCORE = {}                # ip -> [(time, points)]
EVENTS = deque(maxlen=400)
_STATE = {"data": None}

FLOOD_PER_MIN = int(os.getenv("SEC_FLOOD_PER_MIN", "900"))     # էջը բեռնելիս ~40 հարցում է, սա մեծ պաշար է
BAN_SCORE = 100
BAN_HOURS = 24
BAN_HOURS_LAN = 1           # գրասենյակի ցանցից՝ կարճ (գործընկերը սխալվել է)

SCANNER = re.compile(
    r"(\.\./|%2e%2e|/\.env|/\.git|/\.aws|/\.ssh|wp-admin|wp-login|wp-content|xmlrpc|phpmyadmin|/pma/|"
    r"\.php\b|\.asp\b|\.aspx\b|\.jsp\b|/cgi-bin|/boaform|/HNAP1|/actuator|/solr/|/vendor/phpunit|/etc/passwd|"
    r"/manager/html|/owa/|/autodiscover|/\.DS_Store|/server-status|"
    r"\.sql\b|/_ignition|/telescope|<script|union\s+select|union%20select)", re.I)
UNSAFE = ("POST", "PUT", "PATCH", "DELETE")


# ================================================================== պահոց
def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def _data():
    with _LOCK:
        if _STATE["data"] is None:
            d = read_json(FILE, {})
            d = d if isinstance(d, dict) else {}
            d.setdefault("bans", {})          # ip -> {until, reason, at, by, times}
            d.setdefault("allow", [])         # երբեք չարգելափակել (օր.՝ գրասենյակի IP)
            d.setdefault("settings", {})
            d.setdefault("stats", {})
            _STATE["data"] = d
        return _STATE["data"]


def _save():
    with _LOCK:
        write_json(FILE, _STATE["data"])


def settings():
    s = dict(internet=True, csrf=True, autoban=True, domains="")
    s.update(_data()["settings"])
    return s


def set_settings(**kw):
    with _LOCK:
        d = _data()
        for k in ("internet", "csrf", "autoban"):
            if kw.get(k) is not None:
                d["settings"][k] = bool(kw[k])
        if kw.get("domains") is not None:
            doms = [x.strip().lower().lstrip(".") for x in re.split(r"[,\s]+", str(kw["domains"])) if x.strip()]
            for x in doms:
                if not re.fullmatch(r"[a-z0-9]([a-z0-9\-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9\-]*[a-z0-9])?)+", x):
                    raise ValueError(f"Неверный домен: {x}")
            d["settings"]["domains"] = ",".join(doms)
        _save()
    event("settings", "", json.dumps({k: v for k, v in kw.items() if v is not None}, ensure_ascii=False), "info")
    return settings()


# ================================================================== IP
def is_private(ip):
    try:
        a = ipaddress.ip_address(ip)
        return a.is_private or a.is_loopback
    except ValueError:
        return False


def is_loopback(ip):
    try:
        return ipaddress.ip_address(ip).is_loopback
    except ValueError:
        return False


def event(kind, ip, detail="", level="warn"):
    row = dict(at=now_iso(), kind=kind, ip=ip, detail=str(detail)[:300], level=level)
    EVENTS.append(row)
    with _LOCK:
        st = _data()["stats"]
        st[kind] = int(st.get(kind) or 0) + 1
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"{row['at']}\t{level}\t{kind}\t{ip}\t{row['detail']}\n")
    except OSError:
        pass
    if level in ("alert", "ban"):
        try:
            print(f"\n  [БЕЗОПАСНОСТЬ] {kind}: {ip} {row['detail']}\n", flush=True)
        except Exception:  # noqa
            pass


def banned(ip):
    """-> ban record կամ None (ժամկետանց արգելքները ջնջվում են)."""
    if not ip or is_loopback(ip):
        return None
    with _LOCK:
        d = _data()
        b = d["bans"].get(ip)
        if not b:
            return None
        if b.get("until") and b["until"] < time.time():
            b["until"] = -1               # պահում ենք «times»-ը՝ կրկնվող հարձակման համար
            d["bans"][ip] = b
            _save()
            return None
        if b.get("until") == -1:
            return None
        return b


def ban(ip, hours=BAN_HOURS, reason="", by="auto"):
    try:
        ipaddress.ip_address(ip)
    except ValueError:
        raise ValueError(f"Неверный IP: {ip}")
    if is_loopback(ip) or ip in _data()["allow"]:
        return False
    with _LOCK:
        d = _data()
        prev = d["bans"].get(ip) or {}
        times = int(prev.get("times") or 0) + 1
        if by == "auto" and times > 1:          # կրկնվող հարձակում՝ ավելի երկար
            hours = hours * min(times, 7)
        d["bans"][ip] = dict(until=time.time() + hours * 3600 if hours else 0, reason=str(reason)[:200],
                             at=now_iso(), by=by, times=times)
        _save()
    _SCORE.pop(ip, None)
    event("ban", ip, f"{hours or '∞'} ч · {reason} · {by}", "ban")
    return True


def unban(ip, by="admin"):
    with _LOCK:
        ok = _data()["bans"].pop(ip, None) is not None
        _save()
    _SCORE.pop(ip, None)
    if ok:
        event("unban", ip, by, "info")
    return ok


def set_allow(ip, on=True):
    ipaddress.ip_address(ip)       # ValueError՝ եթե IP չէ
    with _LOCK:
        d = _data()
        lst = [x for x in d["allow"] if x != ip]
        if on:
            lst.append(ip)
            d["bans"].pop(ip, None)
        d["allow"] = lst
        _save()


def suspicious(ip, points, reason):
    """Կասկածելի գործողություն. միավորները գումարվում են 1 ժամում, BAN_SCORE-ից ավել՝ արգելափակում."""
    if not ip or is_loopback(ip) or not settings()["autoban"] or ip in _data()["allow"]:
        return
    t = time.time()
    rows = [(ts, p) for ts, p in _SCORE.get(ip, []) if t - ts < 3600] + [(t, points)]
    _SCORE[ip] = rows
    if len(_SCORE) > 5000:
        for k in list(_SCORE)[:1000]:
            _SCORE.pop(k, None)
    if sum(p for _, p in rows) >= BAN_SCORE:
        ban(ip, BAN_HOURS_LAN if is_private(ip) else BAN_HOURS, reason)


def _flood(ip):
    if is_loopback(ip):
        return False
    t = time.time()
    q = _HITS.setdefault(ip, deque())
    q.append(t)
    while q and t - q[0] > 60:
        q.popleft()
    if len(_HITS) > 5000:          # հիշողությունը չլցնենք
        for k in list(_HITS)[:1000]:
            _HITS.pop(k, None)
    return len(q) > FLOOD_PER_MIN


# ================================================================== Host / Origin
def allowed_hosts():
    """APP_DOMAIN=mixmedia.am (կամ մի քանիսը ստորակետով) + Настройки-ում գրված դոմենները."""
    raw = os.getenv("APP_DOMAIN", "") + "," + str(settings().get("domains") or "")
    try:
        raw += "," + (DATA / "domain.txt").read_text(encoding="utf-8").strip()     # setup_domain.bat
    except OSError:
        pass
    return sorted({x.strip().lower().lstrip(".") for x in raw.split(",") if x.strip()})


def host_ok(host):
    h = (host or "").split(",")[0].strip().lower()
    h = h[1:h.index("]")] if h.startswith("[") and "]" in h else h.rsplit(":", 1)[0] if h.count(":") == 1 else h
    doms = allowed_hosts()
    if not doms or not h:
        return True
    if h == "localhost" or h.endswith(".trycloudflare.com"):
        return True
    try:
        ipaddress.ip_address(h)
        return True                 # http://192.168.10.131:8000 և այլ IP-ներ՝ միշտ աշխատում են
    except ValueError:
        pass
    return any(h == d or h.endswith("." + d) for d in doms)


def origin_ok(headers):
    """CSRF. բրաուզերը POST-ի ժամանակ ուղարկում է Origin; այն պետք է համընկնի մեր Host-ի հետ."""
    origin = headers.get("origin") or ""
    if not origin:
        ref = headers.get("referer") or ""
        if not ref:
            return True             # ոչ բրաուզերային գործիք (curl, admin.py)՝ մուտքը միևնույնն է պետք է
        origin = ref
    m = re.match(r"^https?://([^/]+)", origin, re.I)
    if not m:
        return False
    hosts = {(headers.get("host") or "").lower()}
    if headers.get("x-forwarded-host"):
        hosts.add(headers["x-forwarded-host"].split(",")[0].strip().lower())
    oh = m.group(1).lower()
    if oh in hosts:
        return True
    name = oh.rsplit(":", 1)[0]       # մեր սեփական դոմենը (թունելի/պրոքսիի հետևում Host-ը կարող է տարբեր լինել)
    return any(name == d or name.endswith("." + d) for d in allowed_hosts())


# ================================================================== վերնագրեր
CSP = ("default-src 'self'; "
       "script-src 'self' 'unsafe-inline'; "
       "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
       "font-src 'self' data: https://fonts.gstatic.com; "
       "img-src 'self' data: blob: https:; "
       "media-src 'self' data: blob: https:; "
       "connect-src 'self'; "
       "frame-src 'self' blob:; "
       "frame-ancestors 'self'; object-src 'none'; base-uri 'self'; form-action 'self'")


def headers_for(https):
    hs = [(b"x-content-type-options", b"nosniff"),
          (b"x-frame-options", b"SAMEORIGIN"),
          (b"referrer-policy", b"same-origin"),
          (b"permissions-policy", b"camera=(self), microphone=(self), geolocation=(), payment=(), usb=()"),
          (b"cross-origin-opener-policy", b"same-origin"),
          (b"content-security-policy", CSP.encode())]
    if https:
        hs.append((b"strict-transport-security", b"max-age=31536000"))
    return hs


# ================================================================== ASGI շերտ
def _plain(status, text):
    body = text.encode("utf-8")

    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": status,
                    "headers": [(b"content-type", b"text/plain; charset=utf-8"),
                                (b"content-length", str(len(body)).encode())] + headers_for(False)})
        await send({"type": "http.response.body", "body": body})
    return app


class Shield:
    """Առաջին շերտը՝ ամեն HTTP հարցում. ip_of(scope, headers) -> իրական IP (Cloudflare/պրոքսի հաշվի առած)."""

    def __init__(self, app_, ip_of):
        self.app = app_
        self.ip_of = ip_of

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
        ip = self.ip_of(scope, headers)
        path = scope.get("path", "")
        raw = path + "?" + scope.get("query_string", b"").decode("latin-1", "replace")
        method = scope.get("method", "GET")

        if banned(ip):
            return await _plain(403, "Доступ с вашего IP заблокирован системой безопасности. "
                                     "Обратитесь к администратору.")(scope, receive, send)
        if not settings()["internet"] and not is_private(ip):
            event("internet-off", ip, path)
            return await _plain(403, "Сайт сейчас доступен только из офисной сети.")(scope, receive, send)
        if path != "/api/meta/public" and not host_ok(headers.get("x-forwarded-host") or headers.get("host")):
            event("bad-host", ip, headers.get("host", ""))
            return await _plain(421, "Unknown host")(scope, receive, send)
        if SCANNER.search(raw):
            event("scanner", ip, raw[:200], "alert")
            suspicious(ip, 50, "сканер уязвимостей: " + raw[:80])
            return await _plain(404, "Not found")(scope, receive, send)
        if _flood(ip):
            if len(_HITS.get(ip, ())) == FLOOD_PER_MIN + 1:
                event("flood", ip, f">{FLOOD_PER_MIN}/мин", "alert")
            suspicious(ip, 2, "слишком много запросов")
            return await _plain(429, "Слишком много запросов. Подождите минуту.")(scope, receive, send)
        try:
            clen = int(headers.get("content-length") or 0)
        except ValueError:
            clen = 0
        if clen > MAX_UPLOAD + 5 * 1024 * 1024:
            event("too-big", ip, f"{clen} байт {path}")
            return await _plain(413, "Файл слишком большой")(scope, receive, send)
        if method in UNSAFE and settings()["csrf"] and not origin_ok(headers):
            event("csrf", ip, f"{method} {path} origin={headers.get('origin') or headers.get('referer')}", "alert")
            suspicious(ip, 20, "чужой сайт (CSRF)")
            return await _plain(403, "Запрос отклонён: чужой источник (CSRF)")(scope, receive, send)

        https = scope.get("scheme") == "https" or headers.get("x-forwarded-proto", "").startswith("https")
        extra = headers_for(https)
        status_box = [0]

        async def send2(msg):
            if msg["type"] == "http.response.start":
                status_box[0] = msg.get("status", 0)
                names = {k.lower() for k, _ in msg.get("headers", [])}
                msg = dict(msg, headers=list(msg.get("headers", [])) + [h for h in extra if h[0] not in names])
            await send(msg)
        await self.app(scope, receive, send2)
        if status_box[0] == 401 and path.startswith("/api/") and method in UNSAFE:
            suspicious(ip, 3, "много отказов в доступе")


# ================================================================== ադմինի տեսք
def overview():
    d = _data()
    t = time.time()
    bans = []
    for ip, b in list(d["bans"].items()):
        if b.get("until") == -1 or (b.get("until") and b["until"] < t):
            continue
        bans.append(dict(ip=ip, reason=b.get("reason", ""), at=b.get("at", ""), by=b.get("by", ""),
                         times=b.get("times", 1),
                         until=datetime.fromtimestamp(b["until"]).isoformat(timespec="minutes") if b.get("until") else ""))
    watch = sorted(({"ip": ip, "score": sum(p for ts, p in rows if t - ts < 3600)} for ip, rows in _SCORE.items()),
                   key=lambda r: -r["score"])
    return dict(settings=settings(), bans=sorted(bans, key=lambda r: r["at"], reverse=True), allow=d["allow"],
                events=read_log(150), stats=d["stats"], watch=[w for w in watch if w["score"] > 0][:30],
                domains=allowed_hosts(), ban_score=BAN_SCORE, env_domain=os.getenv("APP_DOMAIN", ""))


def read_log(n=200):
    try:
        lines = Path(LOG).read_text(encoding="utf-8").splitlines()[-n:]
    except OSError:
        return list(EVENTS)[-n:][::-1]
    out = []
    for ln in lines[::-1]:
        p = (ln.split("\t") + [""] * 5)[:5]
        out.append(dict(at=p[0], level=p[1], kind=p[2], ip=p[3], detail=p[4]))
    return out
