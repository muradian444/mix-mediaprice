# -*- coding: utf-8 -*-
"""👥 Օգտատերեր / Пользователи: մուտք, հարցումներ, IP-ներ և ադմինի կոնսոլ.

Ինչպես է աշխատում.
  1. Նոր մարդը կայքում ուղարկում է «Запрос доступа» (անուն, լոգին, գաղտնաբառ):
  2. Սերվերի սև պատուհանում (run.bat) երևում է հարցումը՝ IP-ով: Ադմինը գրում է՝  allow <լոգին>
  3. Մարդը ավտոմատ մտնում է կայք: Ադմինը կոնսոլում տեսնում է բոլորի IP-ները (users, ip <լոգին>, online, log):

Ամեն ինչ պահվում է data/users.json (օգտատերեր) և data/sessions.json (մուտքի նշաններ) ֆայլերում:
Նույն հրամանները աշխատում են նաև առանձին՝  python app/admin.py  (կամ admin.bat):"""
import hashlib
import hmac
import os
import re
import secrets
import shlex
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

from config import DATA
from store import read_json, write_json

USERS = DATA / "users.json"
SESS = DATA / "sessions.json"
ACCESS_LOG = DATA / "logs" / "access.log"

LOGIN_RE = re.compile(r"^[a-z0-9][a-z0-9_.\-]{2,31}$")
SESSION_DAYS = 30
ONLINE_SEC = 300
_LOCK = threading.RLock()
_CACHE = {"mtime": None, "data": None}
_SCACHE = {"mtime": None, "data": None}
_SEEN = {}            # login -> (time, ip, ua)  (հիշողությունում, պարբերաբար գրվում է ֆայլ)
_SEEN_FLUSH = [0.0]
_FAILS = {}           # ip -> [timestamps]  (սխալ գաղտնաբառի փորձեր)
_REQS = {}            # ip -> [timestamps]  (նոր հարցումներ)
_LFAILS = {}          # login -> [timestamps]  (մեկ լոգինի վրա տարբեր IP-ներից ընտրություն)
MIN_PW = 8
EVENTS = []           # վերջին իրադարձությունները (կոնսոլի «log» հրամանի համար)
NOTIFY = [True]       # սերվերի կոնսոլում տպել նոր հարցումները
EXTRA = {}            # լրացուցիչ կոնսոլի հրամաններ (server.py-ից՝ merge, ban …): name -> fn(args) -> str


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


# ================================================================== պահոց
def _mtime(p):
    try:
        return Path(p).stat().st_mtime_ns
    except OSError:
        return None


def _load():
    """Թարմ տվյալները՝ քեշով (ֆայլը փոխվել է՝ նորից կարդում ենք, օր.՝ admin.py-ից հետո)."""
    with _LOCK:
        m = _mtime(USERS)
        if _CACHE["data"] is None or m != _CACHE["mtime"]:
            d = read_json(USERS, {})
            d = d if isinstance(d, dict) else {}
            d.setdefault("users", {})
            _CACHE.update(mtime=m, data=d)
        return _CACHE["data"]


def _save(d):
    with _LOCK:
        write_json(USERS, d)
        _CACHE.update(mtime=_mtime(USERS), data=d)


def _mutate(fn):
    """Կարդում ենք ֆայլից ԹԱՐՄ (ոչ քեշից), փոխում և գրում՝ որ երկու պրոցես իրար չջնջեն."""
    with _LOCK:
        _CACHE["data"] = None
        d = _load()
        res = fn(d)
        _save(d)
        return res


def _sessions():
    with _LOCK:
        m = _mtime(SESS)
        if _SCACHE["data"] is None or m != _SCACHE["mtime"]:
            d = read_json(SESS, {})
            _SCACHE.update(mtime=m, data=d if isinstance(d, dict) else {})
        return _SCACHE["data"]


def _save_sessions(d):
    with _LOCK:
        write_json(SESS, d)
        _SCACHE.update(mtime=_mtime(SESS), data=d)


def _th(token):
    return hashlib.sha256(str(token or "").encode()).hexdigest()


# ================================================================== գաղտնաբառ
def hash_pw(pw, salt=None):
    salt = salt or secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", str(pw).encode("utf-8"), bytes.fromhex(salt), 200_000)
    return f"pbkdf2${salt}${dk.hex()}"


def check_pw(stored, pw):
    try:
        _, salt, h = str(stored).split("$")
    except ValueError:
        return False
    return hmac.compare_digest(hash_pw(pw, salt).split("$")[2], h)


WEAK = {"12345678", "123456789", "1234567890", "password", "qwerty123", "11111111", "00000000", "87654321",
        "password1", "qwertyui", "mixmedia", "admin123", "abcd1234", "12341234"}


def check_new_pw(pw):
    """Նոր գաղտնաբառի կանոններ՝ առնվազն 8 նշան, ոչ շատ պարզ."""
    pw = str(pw or "")
    if len(pw) < MIN_PW:
        raise ValueError(f"Գաղտնաբառը՝ առնվազն {MIN_PW} նշան / Пароль — минимум {MIN_PW} символов")
    if pw.lower() in WEAK or len(set(pw)) < 3:
        raise ValueError("Գաղտնաբառը շատ պարզ է / Пароль слишком простой — добавьте буквы и цифры")
    return pw


# ================================================================== մատյան
def log_event(event, login="", ip="", detail=""):
    row = dict(at=now_iso(), event=event, login=login, ip=ip, detail=str(detail)[:200])
    EVENTS.append(row)
    del EVENTS[:-500]
    try:
        ACCESS_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(ACCESS_LOG, "a", encoding="utf-8") as f:
            f.write(f"{row['at']}\t{event}\t{login}\t{ip}\t{row['detail']}\n")
    except OSError:
        pass


def _rate(bucket, ip, limit, window):
    t = time.time()
    rows = [x for x in bucket.get(ip, []) if t - x < window]
    bucket[ip] = rows
    return len(rows) >= limit


# ================================================================== օգտատեր
def norm_login(s):
    return str(s or "").strip().lower()


def public(u, login=None):
    """Օգտատիրոջ տվյալները՝ առանց գաղտնաբառի."""
    if not u:
        return None
    seen = _SEEN.get(login or u.get("login"))
    return dict(login=u.get("login") or login, name=u.get("name", ""), role=u.get("role", "user"),
                status=u.get("status", "pending"), created=u.get("created", ""), approved=u.get("approved", ""),
                last_seen=(datetime.fromtimestamp(seen[0]).isoformat(timespec="seconds") if seen else u.get("last_seen", "")),
                last_ip=(seen[1] if seen else u.get("last_ip", "")), prefs=u.get("prefs", {}))


def get(login):
    u = _load()["users"].get(norm_login(login))
    return dict(u, login=norm_login(login)) if u else None


def is_admin(u):
    return bool(u) and u.get("role") == "admin"


def count():
    return len(_load()["users"])


def _touch_ip(u, ip, ua=""):
    if not ip:
        return
    ips = u.setdefault("ips", {})
    rec = ips.setdefault(ip, dict(first=now_iso(), last="", count=0, ua=""))
    rec["last"] = now_iso()
    rec["count"] = int(rec.get("count") or 0) + 1
    if ua:
        rec["ua"] = str(ua)[:160]
    if len(ips) > 60:     # շատ հին IP-ները ջնջում ենք
        for k in sorted(ips, key=lambda k: ips[k].get("last", ""))[:len(ips) - 60]:
            ips.pop(k, None)
    u["last_ip"] = ip
    u["last_seen"] = now_iso()


def register(login, name, password, ip="", ua=""):
    """Նոր հարցում (status=pending). -> (user, token) — token-ով էջը սպասում է հաստատմանը."""
    login, name = norm_login(login), re.sub(r"\s+", " ", str(name or "")).strip()
    if not LOGIN_RE.match(login):
        raise ValueError("Լոգինը՝ 3–32 լատինատառ/թիվ (a-z, 0-9, _ . -) / Логин: 3–32 латинских букв или цифр")
    if len(name) < 2:
        raise ValueError("Գրեք ձեր անունը / Напишите ваше имя")
    check_new_pw(password)
    if _rate(_REQS, ip, 5, 3600):
        raise PermissionError("Չափազանց շատ հարցումներ / Слишком много запросов. Попробуйте через час")

    def fn(d):
        if login in d["users"]:
            raise ValueError("Այդ լոգինը զբաղված է / Этот логин уже занят")
        d["users"][login] = dict(name=name, pw=hash_pw(password), role="user", status="pending",
                                 created=now_iso(), req_ip=ip, req_ua=str(ua)[:160], ips={})
        _touch_ip(d["users"][login], ip, ua)
        return dict(d["users"][login], login=login)
    u = _mutate(fn)
    _REQS.setdefault(ip, []).append(time.time())
    token = new_session(login, ip, ua)
    log_event("request", login, ip, name)
    if NOTIFY[0]:
        _print(f"\n  >>> НОВЫЙ ЗАПРОС ДОСТУПА: {name} (логин: {login})  IP: {ip or '?'}\n"
               f"      Разрешить:  allow {login}      Отказать:  deny {login}\n")
    return u, token


def login(login_, password, ip="", ua=""):
    """-> (user, token). Սխալի դեպքում՝ ValueError/PermissionError."""
    lg = norm_login(login_)
    if _rate(_FAILS, ip, 8, 600):
        raise PermissionError("Շատ սխալ փորձեր, սպասեք 10 րոպե / Слишком много попыток, подождите 10 минут")
    if _rate(_LFAILS, lg, 10, 900):
        log_event("login-locked", lg, ip)
        raise PermissionError("Այս լոգինը ժամանակավորապես փակ է / Вход для этого логина временно закрыт "
                              "(много неверных паролей). Подождите 15 минут")
    u = get(lg)
    if not u or not check_pw(u.get("pw", ""), password):
        _FAILS.setdefault(ip, []).append(time.time())
        _LFAILS.setdefault(lg, []).append(time.time())
        log_event("login-fail", lg, ip)
        try:
            import security
            security.suspicious(ip, 10, f"неверный пароль ({lg})")
        except Exception:  # noqa
            pass
        time.sleep(0.5)
        raise ValueError("Լոգինը կամ գաղտնաբառը սխալ է / Неверный логин или пароль")
    _LFAILS.pop(lg, None)
    if u.get("status") == "blocked":
        log_event("login-blocked", lg, ip)
        raise PermissionError("Մուտքը արգելափակված է / Доступ заблокирован администратором")
    token = new_session(lg, ip, ua)

    def fn(d):
        _touch_ip(d["users"][lg], ip, ua)
    _mutate(fn)
    _SEEN[lg] = (time.time(), ip, ua)
    log_event("login", lg, ip)
    return get(lg), token


def new_session(login_, ip="", ua=""):
    token = secrets.token_urlsafe(32)
    with _LOCK:
        s = dict(_sessions())
        cutoff = time.time() - SESSION_DAYS * 86400
        s = {k: v for k, v in s.items() if v.get("t", 0) > cutoff}
        s[_th(token)] = dict(login=norm_login(login_), t=time.time(), ip=ip, ua=str(ua)[:160])
        _save_sessions(s)
    return token


def end_session(token):
    with _LOCK:
        s = dict(_sessions())
        if s.pop(_th(token), None) is not None:
            _save_sessions(s)


def kill_sessions(login_):
    lg = norm_login(login_)
    with _LOCK:
        s = {k: v for k, v in _sessions().items() if v.get("login") != lg}
        _save_sessions(s)


def session_user(token, ip="", ua=""):
    """token -> (user | None, state): state = active | pending | blocked | none."""
    if not token:
        return None, "none"
    rec = _sessions().get(_th(token))
    if not rec or rec.get("t", 0) < time.time() - SESSION_DAYS * 86400:
        return None, "none"
    u = get(rec.get("login"))
    if not u:
        return None, "none"
    st = u.get("status", "pending")
    if st != "active":
        return u, st
    _seen(u["login"], ip, ua)
    return u, "active"


def _seen(lg, ip, ua):
    """Վերջին այցելությունը՝ հիշողությունում, ֆայլ՝ առավելագույնը րոպեն մեկ (որ սերվերը չդանդաղի)."""
    prev = _SEEN.get(lg)
    _SEEN[lg] = (time.time(), ip, ua)
    new_ip = not prev or prev[1] != ip
    if new_ip and prev:
        log_event("new-ip", lg, ip)
    if new_ip or time.time() - _SEEN_FLUSH[0] > 60:
        _SEEN_FLUSH[0] = time.time()
        threading.Thread(target=_flush_seen, daemon=True).start()


def _flush_seen():
    try:
        snap = dict(_SEEN)

        def fn(d):
            for lg, (t, ip, ua) in snap.items():
                u = d["users"].get(lg)
                if u:
                    last = (u.get("ips", {}).get(ip) or {}).get("last", "")
                    if not last or last[:16] != datetime.fromtimestamp(t).isoformat(timespec="seconds")[:16]:
                        _touch_ip(u, ip, ua)
                    u["last_seen"] = datetime.fromtimestamp(t).isoformat(timespec="seconds")
        _mutate(fn)
    except Exception:  # noqa — այցելության գրառումը երբեք չպետք է կոտրի սերվերը
        pass


def set_prefs(login_, **prefs):
    lg = norm_login(login_)

    def fn(d):
        u = d["users"].get(lg)
        if u:
            u.setdefault("prefs", {}).update({k: v for k, v in prefs.items() if v is not None})
    _mutate(fn)


def ensure_bootstrap_admin():
    """Ամպում (Render) կոնսոլ չկա՝ APP_PASSWORD-ով ստեղծվում է «admin» օգտատերը, եթե ոչ մի օգտատեր չկա."""
    pw = os.getenv("APP_PASSWORD", "").strip()
    if pw and not _load()["users"]:
        try:
            add_user("admin", pw, "admin", "Administrator")
        except ValueError as e:
            _print(f"  ! APP_PASSWORD не подходит: {e}")
            return False
        return True
    return False


# ================================================================== ադմինի հրամաններ
def _find(key):
    """Լոգին կամ ցանկի համար (#3 / 3)."""
    key = str(key or "").strip().lstrip("#")
    users = _load()["users"]
    if key.isdigit():
        rows = _ordered()
        i = int(key) - 1
        if 0 <= i < len(rows):
            return rows[i][0]
    lg = norm_login(key)
    if lg in users:
        return lg
    raise ValueError(f"Пользователь «{key}» не найден (смотрите: users)")


def _ordered():
    users = _load()["users"]
    return sorted(users.items(), key=lambda kv: (kv[1].get("status") != "pending", kv[1].get("created", "")))


def add_user(login_, password, role="user", name=""):
    lg = norm_login(login_)
    if not LOGIN_RE.match(lg):
        raise ValueError("Логин: 3–32 символа (a-z, 0-9, _ . -)")
    check_new_pw(password)

    def fn(d):
        if lg in d["users"]:
            raise ValueError("Такой логин уже есть")
        d["users"][lg] = dict(name=name or lg, pw=hash_pw(password), role="admin" if role == "admin" else "user",
                              status="active", created=now_iso(), approved=now_iso(), ips={})
    _mutate(fn)
    log_event("add", lg, "", role)
    return lg


def approve(key, role=None):
    lg = _find(key)

    def fn(d):
        u = d["users"][lg]
        u["status"] = "active"
        u["approved"] = now_iso()
        if role in ("admin", "user"):
            u["role"] = role
    _mutate(fn)
    log_event("allow", lg)
    return lg


def deny(key):
    lg = _find(key)

    def fn(d):
        if d["users"][lg].get("status") == "pending":
            d["users"].pop(lg)
        else:
            d["users"][lg]["status"] = "blocked"
    _mutate(fn)
    kill_sessions(lg)
    log_event("deny", lg)
    return lg


def block(key):
    lg = _find(key)

    def fn(d):
        d["users"][lg]["status"] = "blocked"
    _mutate(fn)
    kill_sessions(lg)
    log_event("block", lg)
    return lg


def delete(key):
    lg = _find(key)
    _mutate(lambda d: d["users"].pop(lg))
    kill_sessions(lg)
    log_event("delete", lg)
    return lg


def set_password(key, pw):
    lg = _find(key)
    check_new_pw(pw)

    def fn(d):
        d["users"][lg]["pw"] = hash_pw(pw)
    _mutate(fn)
    kill_sessions(lg)
    return lg


def change_own_password(login_, old, new):
    """Օգտատերը ինքն է փոխում իր գաղտնաբառը (հին գաղտնաբառով)."""
    u = get(login_)
    if not u or not check_pw(u.get("pw", ""), old):
        raise ValueError("Ընթացիկ գաղտնաբառը սխալ է / Текущий пароль неверный")
    check_new_pw(new)
    lg = u["login"]

    def fn(d):
        d["users"][lg]["pw"] = hash_pw(new)
    _mutate(fn)
    log_event("passwd-self", lg)
    return lg


def set_name(key, name):
    lg = _find(key)
    name = re.sub(r"\s+", " ", str(name or "")).strip()[:60]
    if len(name) < 2:
        raise ValueError("Напишите имя")

    def fn(d):
        d["users"][lg]["name"] = name
    _mutate(fn)
    return lg


def disable_guests():
    """Հին «guest-xxxx» ավտոմատ ադմինները (մուտք առանց գաղտնաբառի)՝ փակում ենք. ֆայլերը մնում են."""
    hit = []

    def fn(d):
        for lg, u in d["users"].items():
            if lg.startswith("guest-") and (u.get("status") == "active" or u.get("role") == "admin"):
                u["status"], u["role"], u["guest_disabled"] = "blocked", "user", now_iso()
                hit.append(lg)
    _mutate(fn)
    for lg in hit:
        kill_sessions(lg)
        log_event("guest-disabled", lg)
    return hit


def set_role(key, role):
    lg = _find(key)

    def fn(d):
        d["users"][lg]["role"] = "admin" if role == "admin" else "user"
    _mutate(fn)
    return lg


def users_list():
    out = []
    for i, (lg, u) in enumerate(_ordered(), 1):
        p = public(u, lg)
        p["n"] = i
        p["ips"] = len(u.get("ips") or {})
        p["online"] = bool(_SEEN.get(lg) and time.time() - _SEEN[lg][0] < ONLINE_SEC)
        out.append(p)
    return out


def ip_history(key):
    lg = _find(key)
    u = _load()["users"][lg]
    rows = [dict(ip=ip, **v) for ip, v in (u.get("ips") or {}).items()]
    rows.sort(key=lambda r: r.get("last", ""), reverse=True)
    return lg, rows


def online():
    t = time.time()
    return [dict(login=lg, ip=ip, ago=int(t - ts), ua=ua) for lg, (ts, ip, ua) in _SEEN.items() if t - ts < ONLINE_SEC]


# ================================================================== կոնսոլ
HELP = """
  Команды администратора (пишите прямо в этом окне и нажмите Enter):
    users                       — все пользователи: статус, последний IP, когда заходил
    requests                    — новые запросы доступа (ожидают)
    allow <логин|N> [admin]     — дать доступ (admin — сделать администратором)
    deny <логин|N>              — отказать / закрыть доступ
    block <логин> | unblock <логин>
    ip <логин>                  — все IP-адреса пользователя
    online                      — кто сейчас на сайте и с какого IP
    log [N]                     — последние входы и события (по умолчанию 20)
    add <логин> <пароль> [admin] [Имя]  — создать пользователя сразу
    passwd <логин> <пароль>     — сменить пароль
    admin <логин> | user <логин> — сделать админом / обычным
    delete <логин>              — удалить пользователя
    name <логин> <Имя Фамилия>  — изменить имя
    merge <откуда> <куда>       — передать файлы (например, старого guest-…) другому пользователю
    bans | ban <IP> [часы] | unban <IP>  — блокировка IP (безопасность)
    help                        — эта подсказка
"""


def _fmt_dt(s):
    return str(s or "—").replace("T", " ")[:16]


def _table(rows, head):
    w = [max(len(str(h)), *(len(str(r[i])) for r in rows)) if rows else len(str(h)) for i, h in enumerate(head)]
    line = "  " + "  ".join(str(h).ljust(w[i]) for i, h in enumerate(head))
    out = [line, "  " + "  ".join("-" * x for x in w)]
    for r in rows:
        out.append("  " + "  ".join(str(c).ljust(w[i]) for i, c in enumerate(r)))
    return "\n".join(out)


STATUS_RU = dict(active="доступ есть", pending="ЖДЁТ", blocked="заблокирован")


def run_command(line):
    """Կոնսոլի մեկ հրաման -> տեքստ (ռուսերեն, քանի որ ադմինը այդպես է նախընտրում)."""
    try:
        parts = shlex.split(str(line or "").strip())
    except ValueError:
        parts = str(line or "").split()
    if not parts:
        return ""
    cmd, args = parts[0].lower().lstrip("/"), parts[1:]
    try:
        if cmd in ("help", "?", "h", "помощь"):
            return HELP
        if cmd in ("users", "list", "ls"):
            rows = users_list()
            if not rows:
                return "  Пользователей пока нет. Создайте:  add <логин> <пароль> admin"
            return _table([[r["n"], r["login"], r["name"][:24], r["role"], STATUS_RU.get(r["status"], r["status"]),
                            r["last_ip"] or "—", _fmt_dt(r["last_seen"]), "● онлайн" if r["online"] else ""]
                           for r in rows], ["N", "Логин", "Имя", "Роль", "Статус", "Последний IP", "Был", ""])
        if cmd in ("requests", "pending", "req"):
            rows = [r for r in users_list() if r["status"] == "pending"]
            if not rows:
                return "  Новых запросов нет."
            return _table([[r["n"], r["login"], r["name"], r["last_ip"] or "—", _fmt_dt(r["created"])] for r in rows],
                          ["N", "Логин", "Имя", "IP", "Когда"]) + "\n  Разрешить: allow <логин>   Отказать: deny <логин>"
        if cmd in ("allow", "approve", "ok", "yes"):
            if not args:
                return "  Укажите логин: allow <логин>"
            lg = approve(args[0], "admin" if len(args) > 1 and args[1].lower() == "admin" else None)
            return f"  ✓ Доступ открыт: {lg}" + (" (администратор)" if len(args) > 1 and args[1].lower() == "admin" else "")
        if cmd in ("deny", "reject", "no"):
            return f"  ✓ Отказано: {deny(args[0])}" if args else "  Укажите логин: deny <логин>"
        if cmd == "block":
            return f"  ✓ Заблокирован: {block(args[0])}" if args else "  Укажите логин"
        if cmd == "unblock":
            return f"  ✓ Разблокирован: {approve(args[0])}" if args else "  Укажите логин"
        if cmd in ("ip", "ips"):
            if not args:
                rows = users_list()
                return _table([[r["login"], r["last_ip"] or "—", r["ips"], _fmt_dt(r["last_seen"])] for r in rows],
                              ["Логин", "Последний IP", "Всего IP", "Был"])
            lg, rows = ip_history(args[0])
            if not rows:
                return f"  У {lg} пока нет IP-адресов."
            return f"  IP-адреса пользователя {lg}:\n" + _table(
                [[r["ip"], _fmt_dt(r.get("first")), _fmt_dt(r.get("last")), r.get("count", 0), (r.get("ua") or "")[:50]]
                 for r in rows], ["IP", "Первый раз", "Последний раз", "Раз", "Браузер"])
        if cmd == "online":
            rows = online()
            if not rows:
                return "  Сейчас никого нет на сайте."
            return _table([[r["login"], r["ip"], f"{r['ago']} сек назад", (r["ua"] or "")[:50]] for r in rows],
                          ["Логин", "IP", "Активность", "Браузер"])
        if cmd in ("log", "events"):
            n = int(args[0]) if args and args[0].isdigit() else 20
            rows = _read_log(n)
            if not rows:
                return "  Журнал пуст."
            return _table([[_fmt_dt(r[0]), r[1], r[2], r[3], r[4][:40]] for r in rows], ["Когда", "Событие", "Логин", "IP", ""])
        if cmd in ("add", "create", "new"):
            if len(args) < 2:
                return "  Формат: add <логин> <пароль> [admin] [Имя]"
            role = "admin" if len(args) > 2 and args[2].lower() == "admin" else "user"
            name = " ".join(args[3:] if role == "admin" else args[2:])
            return f"  ✓ Создан пользователь: {add_user(args[0], args[1], role, name)} ({role})"
        if cmd in ("passwd", "password"):
            if len(args) < 2:
                return "  Формат: passwd <логин> <новый пароль>"
            return f"  ✓ Пароль изменён: {set_password(args[0], args[1])} (старые входы закрыты)"
        if cmd == "admin":
            return f"  ✓ Теперь администратор: {set_role(args[0], 'admin')}" if args else "  Укажите логин"
        if cmd == "user":
            return f"  ✓ Теперь обычный пользователь: {set_role(args[0], 'user')}" if args else "  Укажите логин"
        if cmd in ("delete", "del", "rm"):
            return f"  ✓ Удалён: {delete(args[0])}" if args else "  Укажите логин"
        if cmd == "name":
            return f"  ✓ Имя изменено: {set_name(args[0], ' '.join(args[1:]))}" if len(args) > 1 else "  Формат: name <логин> <Имя>"
        if cmd in EXTRA:
            return EXTRA[cmd](args)
        if cmd in ("quiet", "notify"):
            NOTIFY[0] = cmd == "notify"
            return "  Уведомления о запросах: " + ("включены" if NOTIFY[0] else "выключены")
        return f"  Неизвестная команда «{cmd}». Напишите: help"
    except (ValueError, PermissionError) as e:
        return f"  ! {e}"
    except Exception as e:  # noqa — կոնսոլը չպետք է ընկնի
        return f"  ! Ошибка: {type(e).__name__}: {e}"


def _read_log(n):
    try:
        lines = ACCESS_LOG.read_text(encoding="utf-8").splitlines()[-n:]
    except OSError:
        return []
    out = []
    for ln in lines:
        p = ln.split("\t")
        out.append((p + [""] * 5)[:5])
    return out


def _print(s):
    try:
        print(s, flush=True)
    except Exception:  # noqa — կոնսոլը կարող է չաջակցել որոշ նշանների
        try:
            sys.stdout.buffer.write(s.encode("utf-8", "replace") + b"\n")
            sys.stdout.flush()
        except Exception:
            pass


def console_loop():
    """Սերվերի պատուհանում ադմինի հրամանները կարդալու համար (առանձին թելում)."""
    if not sys.stdin or not sys.stdin.isatty():
        return
    for line in sys.stdin:
        out = run_command(line)
        if out:
            _print(out)


def start_console():
    _print("  Вход на сайт — по логину и паролю. Команды: users, requests, allow <логин>, add <логин> <пароль>, "
           "passwd <логин> <пароль>, online, log (help — все команды)\n")
    threading.Thread(target=console_loop, name="admin-console", daemon=True).start()
