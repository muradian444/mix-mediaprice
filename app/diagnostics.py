# -*- coding: utf-8 -*-
"""🛠 Ֆիքսիկ՝ օգնականի ուղեղը. համակարգի ստուգում, սխալների մատյան և պատասխաններ հարցերին.

Ստուգում է այն ամենը, ինչը սովորաբար կոտրում է փաստաթղթերի պատրաստումը՝
տառատեսակներ, շաբլոններ, PDF-ի փոխարկիչ, Google Drive, ձայն, գրադարաններ, տեղ սկավառակի վրա."""
import logging
import os
import platform
import shutil
import sys
import time
import traceback
from collections import deque
from datetime import datetime
from pathlib import Path

from config import ASSETS, BASE, DATA, OUT, TPL, UPL, VAULT

LOG = deque(maxlen=400)          # վերջին դեպքերը՝ Ֆիքսիկի «Սխալներ» ներդիրի համար
_T0 = time.time()


class RingHandler(logging.Handler):
    """Բոլոր WARNING/ERROR-ները հավաքում ենք հիշողության մեջ (ֆայլից բացի)."""

    def emit(self, record):
        try:
            LOG.append(dict(at=datetime.now().isoformat(timespec="seconds"), level=record.levelname,
                            where=record.name, text=record.getMessage(),
                            trace=("".join(traceback.format_exception(*record.exc_info))[-2500:]
                                   if record.exc_info else "")))
        except Exception:
            pass


def setup_logging():
    logs = DATA / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    fh = logging.FileHandler(logs / "app.log", encoding="utf-8")
    fh.setFormatter(fmt)
    fh.setLevel(logging.INFO)
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    sh.setLevel(logging.WARNING)       # կոնսոլում՝ միայն կարևորը (որ ադմինի հրամանները չխառնվեն)
    ring = RingHandler()
    ring.setLevel(logging.WARNING)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    for h in (fh, sh, ring):
        root.addHandler(h)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    return logging.getLogger("mixweb")


def add_event(level, where, text, trace=""):
    LOG.append(dict(at=datetime.now().isoformat(timespec="seconds"), level=level, where=where,
                    text=str(text)[:1500], trace=str(trace)[-2500:]))


def events(level=None, limit=120):
    rows = [e for e in LOG if not level or e["level"] == level]
    return list(reversed(rows))[:limit]


def clear_events():
    LOG.clear()
    return True


# ------------------------------------------------------------------ ստուգումներ
def _ok(name, state, detail, fix=""):
    return dict(name=name, state=state, detail=detail, fix=fix)   # state: ok | warn | error


def _font_check():
    from mediaplan import _FONTS
    found = {}
    for key in ("regular", "bold"):
        for c in _FONTS[key]:
            p = Path(c) if Path(c).is_absolute() else BASE / c
            if p.exists():
                found[key] = str(p)
                break
    if len(found) == 2:
        return _ok("Հայերեն տառատեսակներ (PDF)", "ok", f"{Path(found['regular']).name} / {Path(found['bold']).name}")
    return _ok("Հայերեն տառատեսակներ (PDF)", "error", "Չգտնվեց",
               "Դրեք fonts/Regular.ttf և fonts/Bold.ttf (օր.՝ Sylfaen կամ Noto Sans Armenian)")


def _templates_check():
    need = ["0046.docx", "0055.docx", "0056.docx", "act.docx"]
    miss = [n for n in need if not (TPL / n).exists()]
    if miss:
        return _ok("Word շաբլոններ", "error", "Չկա՝ " + ", ".join(miss),
                   "Պատճենեք բոտի templates/ թղթապանակից")
    return _ok("Word շաբլոններ", "ok", f"{len(need)} շաբլոն՝ տեղում")


def _pdf_check():
    from docfill import pdf_available
    ready, how = pdf_available()
    if ready:
        return _ok("DOCX → PDF փոխարկիչ", "ok", how)
    return _ok("DOCX → PDF փոխարկիչ", "warn",
               "Չկա. պայմանագիրը և ԱԿՏ-ը կստացվեն Word-ով (.docx)",
               "Տեղադրեք անվճար LibreOffice-ը (libreoffice.org) — դրանից հետո PDF-ը կստացվի ինքնաբերաբար: "
               "Տպելու համար կարող եք նաև օգտագործել «🖨 Տպել» կոճակը՝ աշխատում է առանց LibreOffice-ի")


def _libs_check():
    out = []
    for mod, why, hard in (("docx", "Word փաստաթղթեր", True), ("reportlab", "PDF (մեդիա պլան, ԿՊ)", True),
                           ("openpyxl", "Excel կարդալ (ԱԿՏ)", True), ("PIL", "նկարներ և լոգո", True),
                           ("pptx", "PowerPoint արտահանում", False), ("pypdf", "PDF համեմատում", False),
                           ("edge_tts", "ձայնի սինթեզ", False), ("googleapiclient", "Google Drive", False)):
        try:
            __import__(mod)
            out.append(_ok(f"Գրադարան՝ {mod}", "ok", why))
        except Exception:
            out.append(_ok(f"Գրադարան՝ {mod}", "error" if hard else "warn", f"Տեղադրված չէ ({why})",
                           f"Գրեք՝ pip install -r requirements.txt"))
    return out


def _voice_check():
    try:
        import edge_tts  # noqa: F401
    except Exception:
        return _ok("Ձայն (TTS)", "warn", "edge-tts չկա", "pip install edge-tts")
    ff = shutil.which("ffmpeg")
    if not ff:
        try:
            import imageio_ffmpeg
            ff = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            ff = None
    if not ff:
        return _ok("Ձայն (TTS)", "warn", "edge-tts կա, բայց ffmpeg չկա (ձայնի կլոն և աուդիոյի մշակում չեն աշխատի)",
                   "pip install imageio-ffmpeg")
    return _ok("Ձայն (TTS)", "ok", "edge-tts + ffmpeg")


def _drive_check():
    import store
    s = store.settings()
    bits = []
    if os.getenv("GOOGLE_API_KEY"):
        bits.append("API key")
    if os.getenv("GOOGLE_SA_JSON"):
        bits.append("service account")
    if (DATA / "drive_token.json").exists():
        bits.append("OAuth")
    if s.get("drive_link") or os.getenv("DRIVE_LINK"):
        bits.append("պահված հղում")
    if bits:
        return _ok("Google Drive", "ok", ", ".join(bits))
    return _ok("Google Drive", "warn", "Կարգավորված չէ (հանրային հղումները դեռ աշխատում են)",
               "Կարգավորումներում դրեք Drive-ի հղումը, կամ GOOGLE_API_KEY / GOOGLE_SA_JSON միջավայրի փոփոխականը")


def _techmon_check():
    """Տեխ. մոնիտորինգ՝ նամակների ընթերցումը միացված է և աշխատո՞ւմ է."""
    try:
        import techmon
        st = techmon.status()
    except Exception as e:  # noqa
        return _ok("Տեխ. մոնիտորինգ", "error", f"Բազան չբացվեց՝ {e}", "Ստուգեք data/techmon.db-ի իրավունքները")
    if not st["configured"]:
        return _ok("Տեխ. մոնիտորինգ", "warn", f"Նամակների ընթերցումը կարգավորված չէ (բազայում {st['cells']} գրառում)",
                   "Տեխ. մոնիտորինգ -> Կարգավորումներ -> Փոստ")
    if not st["enabled"]:
        return _ok("Տեխ. մոնիտորինգ", "warn", "Փոստը կարգավորված է, բայց ավտո-ստուգումն անջատված է",
                   "Տեխ. մոնիտորինգ -> Կարգավորումներ -> միացնել")
    if st["last_result"].startswith("❌"):
        return _ok("Տեխ. մոնիտորինգ", "error", st["last_result"][:160], "Տեխ. մոնիտորինգ -> Կարգավորումներ -> Ստուգել կապը")
    return _ok("Տեխ. մոնիտորինգ", "ok", f"վերջին ստուգում՝ {st['last_run'] or '—'} · {st['cells']} գրառում")


def _disk_check():
    try:
        usage = shutil.disk_usage(str(BASE))
        free_gb = usage.free / 1024 ** 3
        state = "ok" if free_gb > 2 else ("warn" if free_gb > 0.5 else "error")
        return _ok("Ազատ տեղ սկավառակի վրա", state, f"{free_gb:.1f} ԳԲ",
                   "" if state == "ok" else "Մաքրեք output/ և uploads/ թղթապանակները")
    except OSError as e:
        return _ok("Ազատ տեղ սկավառակի վրա", "warn", str(e))


def _folders_check():
    bad = [str(d) for d in (DATA, OUT, UPL, VAULT) if not os.access(d, os.W_OK)]
    if bad:
        return _ok("Թղթապանակների իրավունքներ", "error", "Գրել չի կարելի՝ " + ", ".join(bad),
                   "Տեղափոխեք հավելվածը այն թղթապանակ, որտեղ գրելու իրավունք կա")
    return _ok("Թղթապանակների իրավունքներ", "ok", "data / output / uploads / vault՝ գրելի")


def _data_check():
    import store
    nets = store.networks()
    addrs = sum(len(n["addresses"]) for n in nets)
    if not nets:
        return _ok("Ցանցեր և հասցեներ", "warn", "Ցանցեր չկան",
                   "Ավելացրեք ցանց «Կարգավորումներ → Ցանցեր» բաժնում")
    return _ok("Ցանցեր և հասցեներ", "ok", f"{len(nets)} ցանց · {addrs} հասցե")


def _logo_check():
    if (ASSETS / "logo.png").exists():
        return _ok("Լոգո", "ok", "assets/logo.png")
    return _ok("Լոգո", "warn", "assets/logo.png չկա՝ PDF-երում կգրվի տեքստով",
               "Դրեք լոգոն assets/logo.png անունով")


def _extract_check():
    name = "Ճանաչում լուսանկարից (տեղային OCR)"
    try:
        import extract
        st = extract.status()
    except Exception as e:  # noqa
        return _ok(name, "warn", str(e))
    o, ai = st["ocr"], st["local_ai"]
    if st["ready"]:
        mode = f"Ollama · {ai['model']}" if ai["ready"] else "կանոններ / правила"
        return _ok(name, "ok", f"Tesseract · {'+'.join(o['languages'])} · {mode}")
    if not o["tesseract"]:
        return _ok(name, "warn", "Tesseract OCR տեղադրված չէ՝ նկարները չեն կարդացվի (Word/Excel/PDF՝ աշխատում են)",
                   "Գործարկեք install_ocr.bat (մեկ անգամ)")
    return _ok(name, "warn", "Չկան OCR լեզուներ՝ " + ", ".join(o["missing"]), "Գործարկեք install_ocr.bat")


_CACHE = {}


def run_checks(force=False):
    """Ստուգումներ (քեշ՝ 30 վրկ — էջերը և Ֆիքսիկը հաճախ են հարցնում, իսկ ստուգումը դանդաղ է)."""
    hit = _CACHE.get("res")
    if hit and not force and time.time() - hit[0] < 30:
        res = dict(hit[1])
        res["recent_errors"] = len([e for e in LOG if e["level"] in ("ERROR", "CRITICAL")])
        return res
    checks = [_folders_check(), _templates_check(), _font_check(), _pdf_check(), _logo_check(),
              _data_check(), _drive_check(), _techmon_check(), _extract_check(), _voice_check(), _disk_check()] + _libs_check()
    errors = sum(1 for c in checks if c["state"] == "error")
    warns = sum(1 for c in checks if c["state"] == "warn")
    res = dict(checks=checks, errors=errors, warnings=warns,
               ok=sum(1 for c in checks if c["state"] == "ok"),
               state="error" if errors else ("warn" if warns else "ok"),
               system=dict(python=sys.version.split()[0], platform=platform.platform(),
                           uptime=int(time.time() - _T0), base=str(BASE)),
               recent_errors=len([e for e in LOG if e["level"] in ("ERROR", "CRITICAL")]))
    _CACHE["res"] = (time.time(), res)
    return res


# ------------------------------------------------------------------ գիտելիքի բազա (Ֆիքսիկի պատասխանները)
KB = [
    dict(q=["pdf", "պդֆ", "չի ստացվում pdf", "pdf չկա", "печать pdf", "pdf не", "конверт"],
         hy="PDF չստացվելու պատճառը սովորաբար LibreOffice-ի բացակայությունն է: Տեղադրեք libreoffice.org-ից "
            "(անվճար) և նորից սեղմեք «Ստեղծել»: Առանց դրա փաստաթուղթը ստացվում է .docx, իսկ տպելու համար "
            "օգտագործեք «🖨 Տպել» կոճակը՝ բացվում է տպելու պատուհանը ուղիղ բրաուզերում:",
         ru="PDF не создаётся обычно из-за отсутствия LibreOffice. Установите его с libreoffice.org (бесплатно) "
            "и нажмите «Создать» снова. Без него документ выходит в .docx, а для печати есть кнопка «🖨 Печать» — "
            "она печатает прямо из браузера."),
    dict(q=["հասցե", "адрес", "search", "որոնում", "не нахожу адрес", "address"],
         hy="Հասցեները փնտրեք մեդիա պլանի 3-րդ քայլում՝ վերևի որոնման դաշտում: Գրեք փողոցի անունը կամ "
            "շենքի համարը — ցուցակը զտվում է բոլոր ցանցերով: Նոր հասցե ավելացնելու համար սեղմեք «➕ Նոր հասցե»:",
         ru="Адреса ищите на 3-м шаге медиаплана — поле поиска сверху. Введите улицу или номер дома, список "
            "фильтруется по всем сетям. Новый адрес — кнопка «➕ Новый адрес»."),
    dict(q=["ակտ", "акт", "мониторинг", "մոնիտորինգ", "xlsx", "excel"],
         hy="ԱԿՏ՝ տեխ. մոնիտորինգով. Կարգավորումներում ՄԵԿ անգամ նշեք մոնիտորինգի թղթապանակի հղումը "
            "(Anyone with the link — Viewer), ամսական ֆայլերը գտնվում են ինքնաբերաբար: Նախատեսված = բոլոր հասցեներ × օրեր × "
            "ժամեր, չհեռարձակված = ⚠ 📞 🟡 🔧 🚧 նշված ժամերը: Օրվա թերթում չգրված հասցեն այդ օրը աշխատել է:",
         ru="АКТ по тех. мониторингу: ОДИН раз укажите в Настройках ссылку на папку мониторинга (доступ «Все, у кого есть "
            "ссылка» — Читатель), месячные файлы находятся сами. План = все адреса × дни × выходы, не вышло = часы с "
            "⚠ 📞 🟡 🔧 🚧. Если адреса нет в листе дня — в этот день всё работало."),
    dict(q=["ձայն", "voice", "голос", "клон", "tts", "озвучк"],
         hy="Ձայնի բաժնում ընտրեք ձայնը և ուղարկեք տեքստը: Կլոն ձայնի համար պետք է 1-3 րոպե մաքուր խոսք, "
            "torch/torchaudio գրադարանները և համբերություն (առաջին անգամ ներբեռնվում են մոդելներ):",
         ru="В разделе «Голос» выберите голос и отправьте текст. Для клона нужны 1-3 минуты чистой речи, "
            "библиотеки torch/torchaudio и терпение — в первый раз скачиваются модели."),
    dict(q=["склад", "պահեստ", "mini pc", "warehouse", "սարք"],
         hy="Պահեստում սեղմեք «➕ Ավելացնել», գրեք ինչ է դա (օր.՝ Mini PC Lenovo M900), ապա՝ որտեղ է գտնվում "
            "(օր.՝ Երևան Սիթի, Կոմիտաս 42, սերվերային պահարան) և նկարագրությունը: Որոնումը աշխատում է բոլոր "
            "դաշտերով, ցանկը կարելի է տպել կամ արտահանել Excel-ի համար:",
         ru="На складе нажмите «➕ Добавить», напишите, что это (например, Mini PC Lenovo M900), затем где "
            "находится (например, Yerevan City, Комитаса 42, серверный шкаф) и описание. Поиск работает по всем "
            "полям, список можно распечатать или выгрузить в Excel."),
    dict(q=["отчет", "հաշվետվություն", "слайд", "սլայդ", "презентац", "pptx", "квартал", "եռամսյակ"],
         hy="«Եռամսյակային հաշվետվություն» բաժնում ստեղծեք հաշվետվություն, ավելացրեք սլայդներ (շապիկ, թվեր, "
            "գծապատկեր, աղյուսակ, նկար, ֆայլեր), բեռնեք ձեր ֆայլերը և արտահանեք PDF կամ PPTX (խմբագրելի "
            "PowerPoint): Թվերը կարող եք ներմուծել ԱԿՏ-ի ֆայլից՝ «Ներմուծել թվերը» կոճակով:",
         ru="В разделе «Квартальный отчёт» создайте отчёт, добавьте слайды (обложка, цифры, график, таблица, "
            "картинка, файлы), загрузите свои файлы и экспортируйте в PDF или PPTX (редактируемый PowerPoint). "
            "Цифры можно импортировать из файла АКТа кнопкой «Импорт цифр»."),
    dict(q=["drive", "файл", "ֆայլ", "պահոց", "хранилищ", "облако"],
         hy="«Ֆայլապահոց» բաժինը Ձեր սեփական Drive-ն է՝ թղթապանակներ, վերբեռնում, որոնում, վերանվանում, "
            "տեղափոխում: Բոլոր պատրաստված փաստաթղթերը ինքնաբերաբար պահվում են այստեղ՝ ըստ բաժինների:",
         ru="Раздел «Хранилище» — ваш собственный Drive: папки, загрузка, поиск, переименование, перемещение. "
            "Все созданные документы складываются сюда автоматически по разделам."),
    dict(q=["ошибк", "սխալ", "error", "упал", "не работает", "չի աշխատում"],
         hy="Բացեք Ֆիքսիկի «Ստուգում» ներդիրը՝ այնտեղ երևում է, թե ինչ է պակասում և ինչպես ուղղել: "
            "«Սխալներ» ներդիրում՝ վերջին սխալների մատյանը (կարելի է պատճենել և ուղարկել ծրագրավորողին):",
         ru="Откройте во Фиксике вкладку «Проверка» — там видно, чего не хватает и как починить. На вкладке "
            "«Ошибки» — журнал последних сбоев (можно скопировать и отправить разработчику)."),
    dict(q=["фото", "լուսանկար", "photo", "скан", "սկան", "распозна", "ճանաչ", "камер"],
         hy="Գրեթե յուրաքանչյուր բաժնում կա «📷 Լուսանկարից» կոճակը՝ ընտրեք փաստաթղթի նկարը (կամ PDF/Word) և դաշտերը "
            "կլրացվեն ինքնաբերաբար: Ստուգեք արդյունքը և ուղղեք, եթե պետք է: Աշխատում է Claude API բանալիով "
            "(⚙️ Կարգավորումներ → 📷 Ճանաչում, լրացնում է ադմինը):",
         ru="Почти в каждом разделе есть кнопка «📷 Из фото» — выберите фото документа (или PDF/Word), и поля заполнятся "
            "сами. Проверьте результат и поправьте при необходимости. Работает с ключом Claude API "
            "(⚙️ Настройки → 📷 Распознавание, задаёт администратор)."),
    dict(q=["уголок", "անկյուն", "мои файлы", "իմ ֆայլ", "мои договор", "сохран"],
         hy="«👤 Իմ անկյունը» բաժնում են ՁԵՐ բոլոր պատրաստած փաստաթղթերը՝ պայմանագրեր, մեդիա պլաններ, ԱԿՏ-եր, ԿՊ-ներ, "
            "խմբագրված ֆայլեր: Մյուս օգտատերերը դրանք չեն տեսնում:",
         ru="В разделе «👤 Мой уголок» лежат ВСЕ ваши документы: договоры, медиапланы, АКТы, КП, изменённые файлы. "
            "Другие пользователи их не видят."),
    dict(q=["изменить", "редакт", "խմբագր", "փոխել ֆայլ", "edit"],
         hy="«✏️ Խմբագրել» բաժնում վերբեռնեք պատրաստի ֆայլը (Word, Excel, PDF, նկար)՝ տեքստը և աղյուսակները կարող եք "
            "փոխել հենց կայքում: Եթե ֆայլը ստեղծվել է այստեղ (պայմանագիր, մեդիա պլան, ԱԿՏ, ԿՊ)՝ կարող եք բացել այն ձևում "
            "և ստեղծել նորից:",
         ru="В разделе «✏️ Изменить» загрузите готовый файл (Word, Excel, PDF, фото) — текст и таблицы можно править прямо "
            "на сайте. Если файл создан здесь (договор, медиаплан, АКТ, КП) — его можно открыть в форме и пересоздать."),
    dict(q=["доступ", "մուտք", "пароль", "գաղտնաբառ", "логин", "войти", "регистр"],
         hy="Նոր օգտատերը ուղարկում է մուտքի հարցում, ադմինը հաստատում է սերվերի պատուհանում՝ allow <լոգին>: "
            "Գաղտնաբառը մոռացե՞լ եք՝ դիմեք ադմինին (passwd <լոգին> <նոր գաղտնաբառ>):",
         ru="Новый пользователь отправляет запрос доступа, администратор подтверждает в окне сервера: allow <логин>. "
            "Забыли пароль — попросите администратора (passwd <логин> <новый пароль>)."),
    dict(q=["печать", "տպել", "print", "принтер"],
         hy="Ցանկացած պատրաստված փաստաթղթի մոտ կա «🖨 Տպել» կոճակը: PDF-ը բացվում է դիտարկիչի տպիչով, "
            "Word ֆայլը՝ տպելու համար պատրաստված էջով (առանց լրացուցիչ ծրագրերի): Կարելի է տպել նաև "
            "պահեստի ցանկը, ԱԿՏ-ի աղյուսակը և հասցեների ցանկը:",
         ru="У каждого готового документа есть кнопка «🖨 Печать». PDF открывается в печати браузера, Word-файл — "
            "как готовая к печати страница (без доп. программ). Печатать можно и список склада, таблицу АКТа и "
            "список адресов."),
]


def ask(question, lang="hy"):
    """Պարզ, հուսալի որոնում գիտելիքի բազայում (առանց արտաքին ծառայությունների)."""
    q = str(question or "").casefold().strip()
    if not q:
        return None
    best, score = None, 0
    for item in KB:
        s = sum(1 for k in item["q"] if k in q)
        if s > score:
            best, score = item, s
    if not best:
        return None
    return best.get(lang) or best["hy"]
