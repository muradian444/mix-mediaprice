# -*- coding: utf-8 -*-
"""Թվերը հայերեն բառերով (մինչև միլիարդ)."""
ONES = ["", "մեկ", "երկու", "երեք", "չորս", "հինգ", "վեց", "յոթ", "ութ", "ինը"]
TEENS = ["տասը", "տասնմեկ", "տասներկու", "տասներեք", "տասնչորս", "տասնհինգ",
         "տասնվեց", "տասնյոթ", "տասնութ", "տասնինը"]
TENS = ["", "", "քսան", "երեսուն", "քառասուն", "հիսուն", "վաթսուն",
        "յոթանասուն", "ութսուն", "իննսուն"]


def _below_1000(n):
    parts = []
    h, r = divmod(n, 100)
    if h:
        parts.append("հարյուր" if h == 1 else ONES[h] + " հարյուր")
    t, o = divmod(r, 10)
    if r:
        if 10 <= r < 20:
            parts.append(TEENS[r - 10])
        else:
            parts.append(TENS[t] + ONES[o])
    return " ".join(parts)


def words(n: int) -> str:
    n = int(n)
    if n == 0:
        return "զրո"
    parts = []
    for size, name in ((10 ** 9, "միլիարդ"), (10 ** 6, "միլիոն"), (1000, "հազար")):
        q, n = divmod(n, size)
        if q:
            parts.append(name if (q == 1 and name == "հազար") else _below_1000(q) + " " + name)
    if n:
        parts.append(_below_1000(n))
    return " ".join(parts)


def money(n: int) -> str:
    return f"{int(n):,}"


if __name__ == "__main__":
    for x in (8000, 136000, 70000, 840000, 6000, 12000, 80000, 1250000):
        print(x, words(x))
