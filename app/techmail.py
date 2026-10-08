# -*- coding: utf-8 -*-
"""📬 Մոնիտորինգի նամակներ (Gmail API-ի փոխարեն՝ սովորական IMAP) + ավտոմատ հաշվետվություն (SMTP).

Նամակը՝ «Мониторинг проигрывания музыки на объекте. {Net} [404] Անուն ( հասցե )» -> ավտոմատ ⚠ ըստ ժամի.
Տարբերությունը սկրիպտից՝
  • Google-ի 6 րոպեանոց սահմանափակում և 20 տրիգերի սահման չկա, աշխատում է հավելվածի ֆոնում
  • նամակը մշակվում է ՄԵԿ անգամ (mails աղյուսակ), չճանաչվածները՝ մեկ անգամ unrec-ում + ձեռքով լուծման հնարավորություն
  • եթե նամակում ամսաթիվ-ժամ չկա՝ վերցնում ենք նամակի Date-ը (նախկինում՝ «չճանաչված»)
  • HTML-միայն նամակները նույնպես կարդացվում են"""
import datetime as dt
import email
import email.header
import email.utils
import html as _html
import imaplib
import re
import smtplib
import threading
import time
from email.message import EmailMessage

import techmon as tm
from techmon import TZ, S_PROBLEM, clean, db, kv_get, kv_set, log, settings

RE_OBJ_BODY = re.compile(r"На объекте\s*(?:\{[^}]+\}\s*)?\[(\d+)\]\s*([^(]+?)\s*\(\s*([^)]+?)\s*\)", re.I)
RE_OBJ_SUBJ = re.compile(r"\[(\d+)\]\s*([^(]+?)\s*\(\s*([^)]+?)\s*\)")
RE_NET = re.compile(r"\{([^}]+)\}")
RE_DT = re.compile(r"(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2}):(\d{2})")

RUN_LOCK = threading.Lock()


# ------------------------------------------------------------------ նամակի վերլուծություն
def parse_message(subject, text, mail_dt=None):
    """-> dict(ok, reason, obj, addr, ext_id, net_code, day, hour, event) — առանց բազայի."""
    subject, text = subject or "", text or ""
    if not text.strip():
        return dict(ok=False, reason="Пустое тело письма")
    m = RE_OBJ_BODY.search(text) or RE_OBJ_SUBJ.search(subject)
    if not m:
        return dict(ok=False, reason="Не распарсили объект/адрес: нет шаблона [id] Объект (Адрес)")
    net = RE_NET.search(text) or RE_NET.search(subject)
    found = list(RE_DT.finditer(text))                    # ժամանակը՝ ՎԵՐՋԻՆ հանդիպումը (ինչպես սկրիպտում)
    fallback = False
    if found:
        g = [int(x) for x in found[-1].groups()]
        event = dt.datetime(g[0], g[1], g[2], g[3], g[4], g[5])
    elif mail_dt:
        event, fallback = mail_dt.astimezone(TZ).replace(tzinfo=None), True
    else:
        return dict(ok=False, reason="Не найдена дата/время события формата YYYY-MM-DD HH:mm:ss")
    return dict(ok=True, obj=clean(m.group(2)), addr=clean(m.group(3)), ext_id=m.group(1),
                net_code=net.group(1) if net else "", event=event, day=f"{event:%Y-%m-%d}",
                hour=24 if event.hour == 0 else event.hour, fallback=fallback)


def apply_parsed(p, msg_id="", con=None):
    """Մշակված նամակը -> ավտոմատ ⚠. -> (result, details) result՝ ok | exists | out | fail."""
    s = settings()
    if not p["ok"]:
        return "fail", p["reason"]
    if p["hour"] < s["work_start"] or p["hour"] > s["work_end"]:
        return "out", f"Час {p['hour']} вне диапазона {s['work_start']}-{s['work_end']}"

    def _do(c):
        cur = tm.get_cell(c, p["day"], p["obj"], p["addr"], p["hour"])
        if cur and tm.norm_status(cur["status"]):
            return "exists", f"Уже было \"{cur['status']}\" (не перезаписываю) | {p['day']} {p['hour']}:00"
        note = (f"❌ СТАТУС: ПРОБЛЕМА ({tm.AUTO_MARK}) (⚠)\nID: {p['ext_id']}\nОбъект: {p['obj']}\nАдрес: {p['addr']}\n"
                f"Время сбоя: {p['hour'] % 24:02d}:00\nДата обнаружения: {tm.now_text()}\n---\n"
                f"Автоматически обнаружена проблема с воспроизведением музыки"
                + ("\n(время события взято из даты письма)" if p.get("fallback") else ""))
        tm.set_cell(p["day"], p["obj"], p["addr"], p["hour"], S_PROBLEM, auto=True, note=note, source="mail",
                    ext_id=p["ext_id"], net_code=p["net_code"], con=c)
        return "ok", f"Поставили ⚠ | {p['day']} {p['hour']:02d}:00 | id={p['ext_id']}"

    if con is not None:
        return _do(con)
    with db() as c:
        return _do(c)


def decode_header(raw):
    out = []
    for part, enc in email.header.decode_header(raw or ""):
        if isinstance(part, bytes):
            try:
                out.append(part.decode(enc or "utf-8", "replace"))
            except LookupError:
                out.append(part.decode("utf-8", "replace"))
        else:
            out.append(part)
    return "".join(out)


def message_text(msg):
    """text/plain մասերը (ա՛ռանց HTML), չկա՝ HTML-ը առանց թեգերի."""
    plain, htmls = [], []
    for part in msg.walk():
        if part.is_multipart():
            continue
        ct = part.get_content_type()
        if ct not in ("text/plain", "text/html"):
            continue
        try:
            payload = part.get_payload(decode=True) or b""
            txt = payload.decode(part.get_content_charset() or "utf-8", "replace")
        except (LookupError, ValueError):
            continue
        (plain if ct == "text/plain" else htmls).append(txt)
    if any(t.strip() for t in plain):
        return "\n".join(plain)
    h = "\n".join(htmls)
    h = re.sub(r"(?is)<(script|style).*?</\1>", " ", h)
    h = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>", "\n", h)
    return _html.unescape(re.sub(r"<[^>]+>", " ", h))


def process_raw(msg_id, raw):
    """Մեկ նամակ (bytes) -> արդյունք ('ok'|'exists'|'out'|'fail'), մանրամասն."""
    msg = email.message_from_bytes(raw)
    subject = decode_header(msg.get("Subject"))
    text = message_text(msg)
    try:
        mail_dt = email.utils.parsedate_to_datetime(msg.get("Date")) if msg.get("Date") else None
        if mail_dt and mail_dt.tzinfo is None:
            mail_dt = mail_dt.replace(tzinfo=dt.timezone.utc)
    except (TypeError, ValueError):
        mail_dt = None
    p = parse_message(subject, text, mail_dt)
    with db() as c:
        result, details = apply_parsed(p, msg_id, c)
        if result in ("ok", "exists", "out"):
            c.execute("INSERT OR REPLACE INTO mails(msg_id,ts,result,reason) VALUES(?,?,?,?)",
                      (msg_id, tm.now().isoformat(timespec="seconds"), result, details))
            if result == "out":
                log("INFO", f"🕒 IGNORED msg={msg_id} | {details}", c)
            else:
                log("INFO", f"✅ OK msg={msg_id} | {details}", c)
        else:                                            # չճանաչված՝ մեկ անգամ unrec-ում
            seen = c.execute("SELECT 1 FROM unrec WHERE msg_id=?", (msg_id,)).fetchone()
            if not seen:
                c.execute("INSERT INTO unrec(msg_id,mail_date,subject,reason,snippet,body) VALUES(?,?,?,?,?,?)",
                          (msg_id, (mail_dt.astimezone(TZ) if mail_dt else tm.now()).strftime("%d.%m.%Y %H:%M"),
                           subject[:300], details, re.sub(r"\s+", " ", text)[:200], text[:4000]))
                log("WARN", f"⚠ SKIP msg={msg_id} | {details}", c)
            c.execute("INSERT OR REPLACE INTO mails(msg_id,ts,result,reason) VALUES(?,?,?,?)",
                      (msg_id, tm.now().isoformat(timespec="seconds"), "unrec", details))
    return result, details


# ------------------------------------------------------------------ IMAP
def _connect(s, factory=None):
    if factory:
        return factory(s)
    if not (s["imap_user"] and s["imap_password"]):
        raise ValueError("Укажите почту и пароль приложения (Настройки → Почта)")
    imap = imaplib.IMAP4_SSL(s["imap_host"], s["imap_port"], timeout=60)
    imap.login(s["imap_user"], s["imap_password"])
    return imap


def test_connection(factory=None):
    """-> dict(ok, message, mailbox). Սխալը վերադարձվում է հասկանալի տեքստով."""
    s = settings()
    try:
        imap = _connect(s, factory)
        typ, data = imap.select(s["imap_folder"], readonly=True)
        if typ != "OK":
            raise ValueError(f"Папка «{s['imap_folder']}» не открылась")
        n = int(data[0] or 0)
        try:
            imap.logout()
        except Exception:  # noqa
            pass
        return dict(ok=True, message=f"Подключено ✓ · писем в «{s['imap_folder']}»: {n}")
    except imaplib.IMAP4.error as e:
        msg = str(e)
        hint = (" Для Gmail нужен «пароль приложения» (Аккаунт Google → Безопасность → Пароли приложений), "
                "а не обычный пароль, и включённый IMAP.") if "imap.gmail" in s["imap_host"] else ""
        return dict(ok=False, message=f"Ошибка входа: {msg}.{hint}")
    except (OSError, ValueError) as e:
        return dict(ok=False, message=f"Нет соединения: {e}")


def _since(days):
    d = tm.now().date() - dt.timedelta(days=days)
    return d.strftime("%d-") + ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][d.month - 1] \
        + d.strftime("-%Y")


def _fetch_headers(imap, uids):
    """{uid: subject} փաթեթով (արագ՝ առանց մարմնի)."""
    out = {}
    for i in range(0, len(uids), 150):
        chunk = uids[i:i + 150]
        typ, data = imap.uid("FETCH", ",".join(chunk), "(BODY.PEEK[HEADER.FIELDS (SUBJECT)])")
        if typ != "OK":
            continue
        for item in data:
            if isinstance(item, tuple):
                m = re.search(rb"UID (\d+)", item[0])
                if m:
                    raw = item[1].decode("utf-8", "replace")
                    subj = re.sub(r"(?im)^subject:\s*", "", raw, count=1)
                    subj = re.sub(r"\r?\n[ \t]+", " ", subj).strip()
                    out[m.group(1).decode()] = decode_header(subj)
    return out


def check_mail(factory=None, max_seconds=300):
    """Նոր նամակների ստուգում. -> dict(found, ok, exists, out, unrec, errors, scanned, skipped, message)."""
    if not RUN_LOCK.acquire(blocking=False):
        return dict(ok=False, message="Проверка уже выполняется")
    st = dict(ok=True, found=0, done=0, exists=0, out=0, unrec=0, errors=0, scanned=0, message="")
    t0 = time.time()
    kv_set("running", "1")
    try:
        s = settings()
        imap = _connect(s, factory)
        typ, _ = imap.select(s["imap_folder"], readonly=not s["mark_read"])
        if typ != "OK":
            raise ValueError(f"Папка «{s['imap_folder']}» не открылась")
        server_filtered = False
        uids = []
        try:                                             # արագ ճանապարհ՝ թեմայով որոնումը սերվերում
            typ, data = imap.uid("SEARCH", "CHARSET", "UTF-8", "SINCE", _since(s["since_days"]),
                                 "SUBJECT", s["subject"].encode("utf-8"))
            if typ == "OK":
                uids = (data[0] or b"").decode().split()
                server_filtered = True
        except Exception:  # noqa
            server_filtered = False
        if not server_filtered:
            typ, data = imap.uid("SEARCH", None, "SINCE", _since(s["since_days"]))
            uids = (data[0] or b"").decode().split()
        validity = ""
        try:
            typ_v, dv = imap.response("UIDVALIDITY")
            validity = (dv[0] or b"").decode() if dv and dv[0] else ""
        except Exception:  # noqa
            pass
        with db() as c:
            known = {r["msg_id"] for r in c.execute("SELECT msg_id FROM mails")}
        key = lambda u: f"{s['imap_user']}:{validity}:{u}"            # noqa: E731
        fresh = [u for u in uids if key(u) not in known]
        st["scanned"] = len(uids)
        if server_filtered:
            mine = fresh
        else:
            heads = _fetch_headers(imap, fresh) if fresh else {}
            needle = s["subject"].casefold()
            mine = [u for u in fresh if needle in heads.get(u, "").casefold()]
            with db() as c:                              # ոչ մեր նամակները՝ նշում ենք, որ հաջորդ անգամ չստուգենք
                for u in fresh:
                    if u not in mine and u in heads:
                        c.execute("INSERT OR IGNORE INTO mails(msg_id,ts,result,reason) VALUES(?,?,?,?)",
                                  (key(u), tm.now().isoformat(timespec="seconds"), "skip", "другая тема"))
        st["found"] = len(mine)
        if mine:
            log("INFO", f"🔍 checkMail: найдено писем={len(mine)} (из {len(fresh)} новых)")
        label_ok = None
        for i in range(0, len(mine), 25):
            if time.time() - t0 > max_seconds:
                log("INFO", f"⏳ Лимит времени: обработано {st['done']}/{len(mine)}, остальные — в следующий запуск")
                break
            chunk = mine[i:i + 25]
            raws = {}
            try:                                         # 25 նամակ՝ մեկ հարցումով
                typ, d = imap.uid("FETCH", ",".join(chunk), "(BODY.PEEK[])")
                for it in d or []:
                    if isinstance(it, tuple):
                        m = re.search(rb"UID (\d+)", it[0])
                        if m:
                            raws[m.group(1).decode()] = it[1]
            except Exception as e:  # noqa
                st["errors"] += len(chunk)
                log("ERROR", f"❌ ERROR fetch {chunk[0]}..{chunk[-1]} | {type(e).__name__}: {e}")
                continue
            marked = []
            for u in chunk:
                if u not in raws:
                    st["errors"] += 1
                    continue
                try:
                    result, _det = process_raw(key(u), raws[u])
                    st["done"] += 1
                    if result == "exists":
                        st["exists"] += 1
                    elif result == "out":
                        st["out"] += 1
                    elif result == "fail":
                        st["unrec"] += 1
                    else:
                        marked.append(u)
                    if result == "exists" or result == "out":
                        marked.append(u)
                except Exception as e:  # noqa — մեկ նամակի սխալը չի կանգնեցնում մնացածը
                    st["errors"] += 1
                    log("ERROR", f"❌ ERROR msg={u} | {type(e).__name__}: {e}")
            if marked and s["mark_read"]:
                ids = ",".join(marked)
                try:                                     # նշանները՝ մեկ հարցումով ամբողջ փաթեթի համար
                    imap.uid("STORE", ids, "+FLAGS", "(\\Seen)")
                    if s["gmail_label"] and "imap.gmail" in s["imap_host"] and label_ok is not False:
                        r = imap.uid("STORE", ids, "+X-GM-LABELS", f'("{s["gmail_label"]}")')
                        label_ok = r[0] == "OK"
                except Exception:  # noqa — նշանը կամընտրական է
                    pass
            kv_set("progress", f"{st['done']}/{len(mine)}")
        try:
            imap.logout()
        except Exception:  # noqa
            pass
        _cover_until_today(s)
        st["message"] = (f"писем в окне {st['scanned']} · наших {st['found']} · обработано {st['done']} "
                         f"(⚠ новых {st['done'] - st['exists'] - st['out'] - st['unrec']}, уже было {st['exists']}, "
                         f"вне часов {st['out']}, не распознано {st['unrec']}, ошибок {st['errors']})")
    except Exception as e:  # noqa
        st.update(ok=False, message=f"{type(e).__name__}: {e}")
        log("ERROR", f"❌ checkMail: {type(e).__name__}: {e}")
    finally:
        kv_set("running", "0")
        kv_set("progress", "")
        kv_set("last_run", tm.now().strftime("%d.%m.%Y %H:%M:%S"))
        kv_set("last_result", ("✅ " if st["ok"] else "❌ ") + st["message"])
        RUN_LOCK.release()
    return st


def _cover_until_today(s):
    """Մոնիտորինգն աշխատել է -> վերջին հաջող ստուգումից մինչև այսօր բոլոր օրերը «ծածկված» են (խնդիր չկա = ամեն ինչ OK)."""
    today = tm.now().date()
    last = kv_get("last_ok_day")
    start = dt.date.fromisoformat(last) if last else today
    start = max(start, today - dt.timedelta(days=s["since_days"]))
    with db() as c:
        d = start
        while d <= today:
            tm.mark_covered(c, d, "mail")
            d += dt.timedelta(1)
    kv_set("last_ok_day", f"{today:%Y-%m-%d}")


# ------------------------------------------------------------------ ձեռքով լուծում (չճանաչված նամակ)
def resolve_unrec(msg_id, obj, addr, day, hour, status=S_PROBLEM, user=""):
    with db() as c:
        row = c.execute("SELECT 1 FROM unrec WHERE msg_id=?", (msg_id,)).fetchone()
        if not row:
            raise ValueError("Письмо не найдено")
        tm.set_cell(day, obj, addr, hour, status, user=user, source="unrec", con=c)
        c.execute("UPDATE unrec SET resolved=1 WHERE msg_id=?", (msg_id,))
        log("INFO", f"✍ UNREC resolved msg={msg_id} | {obj} | {day} {hour}:00 | {status} | {user}", c)


def dismiss_unrec(msg_id):
    with db() as c:
        c.execute("UPDATE unrec SET resolved=1 WHERE msg_id=?", (msg_id,))


# ------------------------------------------------------------------ SMTP՝ ամսական հաշվետվություն
def send_report(month, recipients=None):
    s = settings()
    to = recipients or [x.strip() for x in re.split(r"[,;\s]+", s["report_emails"]) if x.strip()] or \
        ([s["imap_user"]] if s["imap_user"] else [])
    if not to:
        raise ValueError("Укажите получателей отчёта (Настройки → Почта)")
    if not (s["imap_user"] and s["imap_password"]):
        raise ValueError("Для отправки нужна почта и пароль приложения")
    rep = tm.report_month(month)
    xlsx = tm.export_month_xlsx(month)
    msg = EmailMessage()
    msg["Subject"] = f"📊 Авто-отчёт тех. мониторинга — {rep['label']}"
    msg["From"] = s["imap_user"]
    msg["To"] = ", ".join(to)
    t = rep["totals"]
    msg.set_content(
        f"Авто-отчёт за {rep['label']}\n\n"
        f"Событий: {rep['events']} · объектов с проблемами: {rep['objects_affected']}\n"
        f"⚠ {t['⚠']} · 📞 {t['📞']} · 🟡 {t['🟡']} · 🔧 {t['🔧']} · 🚧 {t['🚧']} · ✅ {t['✅']}\n\n"
        f"Подробности — в приложении Mix Media (Тех. мониторинг → Месяц). Excel во вложении.")
    msg.add_attachment(xlsx, maintype="application",
                       subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       filename=f"{rep['label']} Тех мониторинг.xlsx")
    with smtplib.SMTP_SSL(s["smtp_host"], s["smtp_port"], timeout=60) as smtp:
        smtp.login(s["imap_user"], s["imap_password"])
        smtp.send_message(msg)
    log("INFO", f"📧 Report {month} sent to {', '.join(to)}")
    return to


# ------------------------------------------------------------------ ֆոնային պլանավորող
_started = False


def _loop():
    time.sleep(8)
    while True:
        try:
            s = settings()
            if s["enabled"] and s["imap_user"] and s["imap_password"]:
                last = kv_get("last_run")
                due = True
                if last:
                    try:
                        t = dt.datetime.strptime(last, "%d.%m.%Y %H:%M:%S").replace(tzinfo=TZ)
                        due = (tm.now() - t).total_seconds() >= s["interval_min"] * 60
                    except ValueError:
                        due = True
                if due:
                    check_mail()
                _maybe_monthly_report(s)
        except Exception:  # noqa — ցիկլը երբեք չի մահանում
            try:
                log("ERROR", "scheduler failed", None)
            except Exception:  # noqa
                pass
        time.sleep(30)


def _maybe_monthly_report(s):
    """Ամսվա 1-ին՝ 09:00-ից հետո՝ նախորդ ամսվա հաշվետվությունը նամակով (մեկ անգամ)."""
    n = tm.now()
    if not s["auto_report"] or n.day != 1 or n.hour < 9:
        return
    month = tm.prev_month(f"{n:%Y-%m}")
    if kv_get(f"report_sent_{month}") or not tm.report_month(month)["events"]:
        return
    try:
        send_report(month)
        kv_set(f"report_sent_{month}", tm.now().isoformat(timespec="seconds"))
    except Exception as e:  # noqa
        log("ERROR", f"❌ monthly report: {type(e).__name__}: {e}")
        kv_set(f"report_sent_{month}", "error")        # չենք կրկնում ամեն 30 վրկ


def start_background():
    global _started
    if _started:
        return
    _started = True
    kv_set("running", "0")
    threading.Thread(target=_loop, name="techmon-mail", daemon=True).start()
