# -*- coding: utf-8 -*-
"""Պայմանագրերի հարցերը (ճիշտ այն տեքստերով, ինչ ցույց են տալիս սքրինշոթերը)."""
import re

from docfill import parse_date


def v_date(s, d):
    try:
        return parse_date(s).strftime("%d.%m.%Y")
    except Exception:
        raise ValueError("Ամսաթիվը չհասկացա: Գրեք ՕՕ.ԱԱ.ՏՏՏՏ ձևաչափով (օրինակ՝ 05.11.2026) կամ TODAY:")


def v_text(s, d):
    s = s.strip()
    if len(s) < 2:
        raise ValueError("Շատ կարճ է: Մուտքագրեք կրկին:")
    return s


def v_tin(s, d):
    s = s.strip()
    if not re.fullmatch(r"\d{8}", s):
        raise ValueError("ՀՎՀՀ-ն պետք է բաղկացած լինի 8 թվանշանից: Ստուգեք և մուտքագրեք կրկին:")
    return s


def v_account(s, d):
    s = re.sub(r"[\s\-]", "", s)
    if not re.fullmatch(r"\d{8,20}", s):
        raise ValueError("Բանկային հաշվեհամարը պետք է պարունակի միայն թվեր (8–20 թվանշան): Մուտքագրեք կրկին:")
    return s


def v_email(s, d):
    s = s.strip()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", s):
        raise ValueError("Էլ. փոստը սխալ է: Օրինակ՝ name@mail.am")
    return s


def v_int(lo=1, hi=10 ** 9):
    def f(s, d):
        s2 = re.sub(r"[\s,.]", "", s)
        if not s2.isdigit() or not (lo <= int(s2) <= hi):
            raise ValueError(f"Մուտքագրեք թիվ՝ {lo}-ից {hi}:")
        return int(s2)
    return f


def v_points(s, d):
    t = s.replace("և", " ").replace("եւ", " ").replace(",", " ").replace("&", " ").split()
    if set(t) == {"3"}:
        return "3"
    if set(t) == {"4"}:
        return "4"
    if set(t) == {"3", "4"}:
        return "3 և 4"
    raise ValueError("Գրեք 3, 4 կամ 3 և 4:")


def v_yesno(s, d):
    if s in ("yes", "Այո"):
        return True
    if s in ("no", "Ոչ"):
        return False
    raise ValueError("Ընտրեք կոճակներից:")


COMMON = [
    dict(key="date", label="Պայմանագրի ամսաթիվ", validate=v_date,
         prompt="Մուտքագրեք պայմանագրի ամսաթիվը DD.MM.YYYY ձևաչափով կամ գրեք TODAY՝ այսօրվա ամսաթվի համար.",
         buttons=[("TODAY", "TODAY")]),
    dict(key="company", label="Ընկերություն", validate=v_text,
         prompt="Մուտքագրեք Պատվիրատու ընկերության անվանումը (առանց չակերտների և առանց «ՍՊԸ»)."),
    dict(key="director", label="Տնօրեն", validate=v_text,
         prompt="Մուտքագրեք Պատվիրատուի տնօրենի անունը և ազգանունը (օրինակ՝ Արամ Պետրոսյան)."),
    dict(key="tin", label="ՀՎՀՀ", validate=v_tin, prompt="Մուտքագրեք Պատվիրատուի ՀՎՀՀ-ն՝ 8 թվանշան."),
    dict(key="bank", label="Բանկ", validate=v_text, optional=True,
         prompt="Մուտքագրեք Պատվիրատուի բանկը (օրինակ՝ Ինեկոբանկ ՓԲԸ): Պարտադիր չէ:"),
    dict(key="account", label="Բանկային հաշվեհամար", validate=v_account, optional=True,
         prompt="Մուտքագրեք Պատվիրատուի բանկային հաշվեհամարը: Պարտադիր չէ:"),
    dict(key="legal_address", label="Իրավաբանական հասցե", validate=v_text, prompt="Մուտքագրեք Պատվիրատուի հասցեն."),
    dict(key="email", label="Էլ. փոստ", validate=v_email, optional=True,
         prompt="Մուտքագրեք Պատվիրատուի էլ. փոստը: Պարտադիր չէ:"),
]

SHOP = dict(key="shop", label="Խանութ/ցանց", validate=v_text, prompt="Մուտքագրեք խանութի/ցանցի անվանումը.")
POINTS = dict(key="points", label="Կետեր", validate=v_points,
              prompt="Նշեք, թե որ աուդիո նյութերի կետերն են կիրառվում (օրինակ՝ 3, 4 կամ 3 և 4).",
              buttons=[("3", "3"), ("4", "4"), ("3 և 4", "3 և 4")])
COUNT = dict(key="addr_count", label="Հասցեների քանակ", validate=v_int(1, 2000),
             prompt="Մուտքագրեք օբյեկտների/հասցեների քանակը (օրինակ՝ 1, 32, 70, 700).")
ADDRS = dict(key="addresses", label="Հասցեներ", kind="addresses")
PRICE = dict(key="price", label="Մեկ հասցեի գումար", validate=v_int(1, 10 ** 8),
             prompt="Մուտքագրեք մեկ հասցեի ամսական գումարը (օրինակ՝ 8000).", money=True)

FLOWS = {
    "0055": dict(title="Բուբուկա վճարային պայմանագիր",
                 steps=COMMON + [SHOP, POINTS, COUNT, ADDRS, PRICE],
                 defaults=dict(upto120=6000, over120=12000, months=3)),
    "0046": dict(title="Սուպերմարկետ՝ անվճար և գովազդի 30%",
                 steps=COMMON + [SHOP, COUNT, ADDRS],
                 defaults=dict(upto120=6000, over120=12000, months=3)),
    "0056": dict(title="Գովազդատուի պայմանագիր",
                 steps=COMMON + [
                     dict(key="location", label="Մատուցման վայր", validate=v_text,
                          prompt="Մուտքագրեք ծառայության մատուցման վայրը (օրինակ՝ ք․ Երևան, Գայի պողոտա 16 հասցեում գտնվող «Մեգամոլ Արմենիա» առևտրի կենտրոն)."),
                     dict(key="price", label="Ամսական գումար", validate=v_int(1, 10 ** 8), money=True,
                          prompt="Մուտքագրեք ամսական գումարը ՀՀ դրամով, ներառյալ ԱԱՀ (օրինակ՝ 70000)."),
                     dict(key="remove44", label="4.4 կետ", validate=v_yesno,
                          prompt="Հեռացնե՞լ պայմանագրի 4.4 կետը:",
                          buttons=[("Այո, հեռացնել", "yes"), ("Ոչ, թողնել", "no")],
                          show=lambda v: "հեռացվում է" if v else "մնում է")],
                 defaults=dict(spots=24, duration=30)),
}

EXTRA_LABELS = dict(upto120="Մինչև 120 քմ սակագին", over120="120 քմ-ից ավելի սակագին",
                    months="Վճարման ժամանակահատված (ամիս)", spots="Հեռարձակում/օր (spot)",
                    duration="Հոլովակի տևողություն (վրկ)")


def show_value(step, v):
    if v == "" or v is None:
        return "—"
    if "show" in step:
        return step["show"](v)
    if step.get("money"):
        return f"{v:,}"
    if isinstance(v, int):
        return f"{v:,}" if v >= 1000 else str(v)
    return str(v)


def summary_lines(kind, data):
    flow = FLOWS[kind]
    out = []
    for s in flow["steps"]:
        k = s["key"]
        if k == "addresses":
            continue
        if k in data:
            out.append((s["label"], show_value(s, data[k])))
        if k == "price" and kind == "0055":
            out.append(("Ընդհանուր գումար", f"{data['price'] * data['addr_count']:,}"))
    for k, v in flow["defaults"].items():
        out.append((EXTRA_LABELS[k], f"{data.get(k, v):,}" if isinstance(data.get(k, v), int) and data.get(k, v) >= 1000 else str(data.get(k, v))))
    if "addresses" in data:
        out.append(("Հասցեներ", "\n" + "\n".join(f"{i}. {a}" for i, a in enumerate(data["addresses"], 1))))
    return out
