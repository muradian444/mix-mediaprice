# -*- coding: utf-8 -*-
"""🌐 Հանրային կայք (GitHub Pages)՝ docs/ թղթապանակ.

docs/index.html-ը ստատիկ էջ է (Python չի պահանջում), իսկ այս մոդուլը թարմացնում է նրա տվյալները՝
docs/stores.json (միայն թվեր, առանց գովազդատուների անունների) և docs/logos/ (ցանցերի լոգոները).

Ձեռքով գործարկում՝  python app\\pages.py"""
import json
import shutil

import adspace
from config import ASSETS, BASE

DOCS = BASE / "docs"


def build():
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / ".nojekyll").touch()          # GitHub Pages-ը թող չմշակի ֆայլերը Jekyll-ով
    logos = DOCS / "logos"
    if logos.exists():
        shutil.rmtree(logos)
    logos.mkdir()
    data = adspace.public_data()
    copied = 0
    for n in data["networks"]:
        if n["logo"]:
            src = adspace.LOGOS / n["logo"].split("/", 1)[1]
            if src.exists():
                shutil.copy(src, logos / src.name)
                copied += 1
            else:
                n["logo"] = None
    if (ASSETS / "logo.png").exists():
        shutil.copy(ASSETS / "logo.png", DOCS / "logo.png")
    with open(DOCS / "stores.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    # 💰 գնացուցակ՝ docs/price.html + price.json (նույն էջը, ինչ սերվերի /price-ը)
    import pricecalc
    price = pricecalc.public(logo_prefix="logos/")
    for g in price["groups"].values():
        for n in g["networks"]:
            if n["logo"] and not (logos / n["logo"].split("/", 1)[1]).exists():
                src = adspace.LOGOS / n["logo"].split("/", 1)[1]
                if src.exists():
                    shutil.copy(src, logos / src.name)
                else:
                    n["logo"] = None
    with open(DOCS / "price.json", "w", encoding="utf-8") as f:
        json.dump(price, f, ensure_ascii=False, indent=1)
    page = BASE / "web" / "price.html"
    if page.exists():
        shutil.copy(page, DOCS / "price.html")
    img = BASE / "web" / "price-img"
    if img.exists():
        shutil.copytree(img, DOCS / "price-img", dirs_exist_ok=True)
    return dict(folder=str(DOCS), networks=len(data["networks"]), logos=copied, updated=data["updated"],
                index=(DOCS / "index.html").exists())


if __name__ == "__main__":
    r = build()
    print(f"✅ docs/ թարմացված է՝ {r['networks']} ցանց, {r['logos']} լոգո ({r['updated']})")
