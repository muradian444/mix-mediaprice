# -*- coding: utf-8 -*-
"""💼 ԿՊ-ի հարցաշարերը (5 տեսակ)՝ նույն դաշտերը, ինչ բոտում, բայց web-ի համար (առանց Telegram-ի)."""
from datetime import date, timedelta

import kp
import mediaplan as mp


def _int(lo, hi):
    def f(t):
        t2 = str(t).replace(" ", "")
        if not t2.isdigit() or not lo <= int(t2) <= hi:
            raise ValueError(f"Գրեք թիվ {lo}-ից {hi}")
        return int(t2)
    return f


def _text(t):
    if len(str(t).strip()) < 2:
        raise ValueError("Շատ կարճ է, մուտքագրեք կրկին")
    return str(t).strip()


def _money(v):
    return f"{kp.num(v)} դրամ"


def _disc(v):
    return f"{v}%" if v else "Առանց զեղչի"


S_CLIENT = dict(key="client", label="Պատվիրատու", parse=_text, input="text",
                prompt="Պատվիրատու ընկերության անվանումը (օրինակ՝ Վիզանտ Գրուպ):")
S_MANAGER = dict(key="manager", label="Մենեջեր", parse=_text, input="text", prompt="Մենեջերի անուն, ազգանուն:")
S_PHONE = dict(key="phone", label="Հեռախոս", parse=lambda t: kp.fmt_phone(t), input="text",
               prompt="Մենեջերի հեռախոսը (+374 XX XXXXXX):")
S_VALID = dict(key="valid_days", label="Վավերականություն (օր)", parse=_int(1, 365), default=14, input="number",
               show=lambda v: f"{v} օր", prompt="Քանի՞ օր է վավեր առաջարկը:")
S_NOTE = dict(key="note", label="Նշում", parse=_text, optional=True, input="textarea",
              prompt="Լրացուցիչ նշում ԿՊ-ի համար (կամ բաց թողեք):")


def _disc_steps(pct, months):
    return [dict(key="discount", label="Զեղչ", parse=_int(0, 90), default=pct, show=_disc, input="number",
                 prompt="Զեղչի տոկոսը (0՝ եթե զեղչ չկա):"),
            dict(key="discount_months", label="Զեղչ՝ ամիսներից սկսած", parse=_int(1, 60), default=months,
                 show=lambda v: f"{v} և ավելի ամիս", input="number",
                 prompt="Քանի՞ ամսից սկսած է գործում զեղչը:")]


KP_STEPS = {
    "1": [S_CLIENT,
          dict(key="groups", label="Օբյեկտներ", parse=kp.parse_groups, input="lines",
               show=lambda v: f"{len(v)} խումբ, {sum(len(r) for _, r in v)} տող",
               placeholder="Առողջարան «Այ-Պետրի»; Ընդունարան; 100 մ²; 1290",
               prompt=("Օբյեկտները՝ յուրաքանչյուրը նոր տողից՝\nԽումբ; Տեսակ; Մակերես; Գին\n\nՕրինակ՝\n"
                       "Առողջարան «Այ-Պետրի»; Ընդունարան; 100 մ²; 1290\n"
                       "Առողջարան «Այ-Պետրի»; Ռեստորան; 389,4 մ²; 2390"))],
    "2": [S_CLIENT,
          dict(key="purpose", label="Նշանակություն", parse=_text, optional=True, input="textarea",
               prompt="Ինչի՞ համար է առաջարկը (օրինակ՝ Lamoda-ի պատվերների տրման կետերի համար) կամ բաց թողեք:"),
          dict(key="license", label="Ծրագրի իրավունք (առանց ԱԱՀ)", parse=kp.parse_number, default=501.5,
               show=_money, input="number",
               prompt="«ԲՈՒԲՈՒԿԱ» ծրագրի օգտագործման իրավունքի ամսական գինը (առանց ԱԱՀ):"),
          dict(key="library", label="Մեդիագրադարան (ներառյալ 5% ԱԱՀ)", parse=kp.parse_number, default=88.5,
               show=_money, input="number",
               prompt="Մեդիագրադարանի բովանդակության ամսական գինը (ներառյալ 5% ԱԱՀ):")],
    "3": [S_CLIENT,
          dict(key="tariffs", label="Սակագներ", parse=kp.parse_tariffs, input="lines",
               default=[("մինչև 200 մ²", 1290), ("մինչև 500 մ²", 1590)],
               show=lambda v: "; ".join(f"{a} — {kp.num(p)}" for a, p in v),
               placeholder="մինչև 200 մ²; 1290",
               prompt="Սակագները՝ յուրաքանչյուրը նոր տողից՝\nՄակերես; Գին\nՕրինակ՝ մինչև 200 մ²; 1290"),
          ] + _disc_steps(10, 6),
    "4": [S_CLIENT,
          dict(key="area", label="Մակերես", parse=_text, default="մինչև 1 500 մ²", input="text",
               prompt="Մակերեսը (օրինակ՝ մինչև 1 500 մ²):"),
          dict(key="price", label="Գին 1 օբյեկտի համար", parse=kp.parse_number, default=2090, show=_money,
               input="number", prompt="Բաժանորդավճար 1 օբյեկտի համար (ամսական, դրամ):"),
          dict(key="objects", label="Օբյեկտների քանակ", parse=_int(1, 500), default=3, input="number",
               prompt="Օբյեկտների քանակը:")
          ] + _disc_steps(10, 3),
    "5": [S_CLIENT,
          dict(key="area", label="Մակերես", parse=_text, default="մինչև 100 մ²", input="text",
               prompt="Մակերեսը (օրինակ՝ մինչև 100 մ²):"),
          dict(key="price", label="Գին 1 օբյեկտի համար", parse=kp.parse_number, default=1790, show=_money,
               input="number", prompt="Բաժանորդավճար 1 օբյեկտի համար (ամսական, դրամ):")
          ] + _disc_steps(10, 6),
}
for _k in KP_STEPS:
    KP_STEPS[_k] = KP_STEPS[_k] + [S_MANAGER, S_PHONE, S_VALID, S_NOTE]


def _show(step, v):
    try:
        return step["show"](v) if "show" in step else str(v)
    except Exception:
        return str(v)


def schema():
    """Դաշտերի նկարագրությունը frontend-ի համար (առանց ֆունկցիաների)."""
    out = {}
    for kind, steps in KP_STEPS.items():
        info = kp.KINDS[kind]
        fields = []
        for s in steps:
            default = s.get("default")
            if isinstance(default, list):     # սակագներ/խմբեր՝ տեքստով
                default = "\n".join("; ".join(str(x) for x in row) for row in default)
            fields.append(dict(key=s["key"], label=s["label"], prompt=s["prompt"],
                               input=s.get("input", "text"), optional=bool(s.get("optional")),
                               default=default, placeholder=s.get("placeholder", "")))
        out[kind] = dict(kind=kind, short=info["short"], chip=info["chip"],
                         title=info.get("title", ""), subtitle=info["subtitle"], fields=fields)
    return out


def build(kind, raw):
    """-> (data, errors, answers)՝ պատրաստ kp.make_kp-ի համար."""
    if str(kind) not in KP_STEPS:
        raise ValueError("Անհայտ ԿՊ տեսակ")
    kind = str(kind)
    data, errors, answers = {}, {}, []
    for s in KP_STEPS[kind]:
        k = s["key"]
        v = (raw or {}).get(k)
        empty = v is None or (isinstance(v, str) and not v.strip())
        if empty and "default" in s:
            v = s["default"]
            if isinstance(v, list):
                data[k] = v
                answers.append((s["label"], _show(s, v)))
                continue
        elif empty:
            if s.get("optional"):
                continue
            errors[k] = "Դաշտը լրացված չէ"
            continue
        try:   # թվային լռելյայն արժեքները գալիս են int/float-ով՝ parse-ը սպասում է տեքստ
            value = v if isinstance(v, (list, tuple)) else s["parse"](str(v))
        except ValueError as e:
            errors[k] = str(e)
            continue
        data[k] = value
        if k not in ("client", "manager", "phone"):
            answers.append((s["label"], _show(s, value)))
    return data, errors, answers


def finalize(kind, data, answers):
    d = dict(data, kind=str(kind), answers=answers)
    if d.get("discount") == 0:
        d["discount"] = None
    d.setdefault("valid_days", 14)
    today = date.today()
    d["date"] = mp.fmt(today)
    d["valid_until"] = mp.fmt(today + timedelta(int(d["valid_days"])))
    return d
