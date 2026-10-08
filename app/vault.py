# -*- coding: utf-8 -*-
"""☁️ Ֆայլապահոց (Google Drive-ի նման)՝ թղթապանակներ, վերբեռնում, որոնում, վերանվանում, տեղափոխում.

Յուրաքանչյուր օգտատեր ունի ԻՐ անկյունը՝ vault/users/<լոգին>/ (իր պայմանագրերը, մեդիա պլանները, ԱԿՏ-երը …),
իսկ vault/-ի մնացածը «Ընդհանուր» թղթապանակն է: Ուղիները ստուգվում են՝ արմատից դուրս ելք չկա."""
import re
import shutil
import time
import unicodedata
from datetime import datetime
from pathlib import Path

from config import AUDIO_EXT, DOC_EXT, IMG_EXT, VAULT
from store import safe_name

AUTO_DIRS = {"contract": "Պայմանագրեր", "plan": "Մեդիա պլան", "act": "ԱԿՏ", "kp": "ԿՊ",
             "law": "Իրավաբան", "quarterly": "Հաշվետվություններ", "voice": "Ձայն", "edited": "Խմբագրված",
             "other": "Այլ"}
KIND_BY_EXT = {**{e: "doc" for e in DOC_EXT}, **{e: "image" for e in IMG_EXT},
               **{e: "audio" for e in AUDIO_EXT}}
USERS_DIR = "users"
HIDDEN = {USERS_DIR, "_warehouse"}       # ընդհանուր արմատում չեն երևում
_STATS = {}                              # root -> (time, stats)


def user_root(login):
    """Օգտատիրոջ անկյունը (ստեղծվում է առաջին անգամ՝ բաժինների թղթապանակներով)."""
    lg = safe_name(str(login or "").lower(), 40, "_")
    root = VAULT / USERS_DIR / lg
    if not root.exists():
        for name in AUTO_DIRS.values():
            (root / name).mkdir(parents=True, exist_ok=True)
    return root


def _root(root):
    return Path(root or VAULT).resolve()


def _hidden(p: Path, root: Path):
    return root == VAULT.resolve() and p.parent == root and p.name in HIDDEN


# ------------------------------------------------------------------ ուղիներ
def _rel(path):
    """'a/b' -> մաքուր հարաբերական ուղի (.. և բացարձակ ուղիներն արգելված են)."""
    raw = unicodedata.normalize("NFC", str(path or "")).replace("\\", "/")
    parts = []
    for p in raw.split("/"):
        p = p.strip()
        if p in ("", ".",):
            continue
        if p == ".." or ":" in p:
            raise ValueError("Ուղին սխալ է")
        parts.append(p)
    return "/".join(parts)


def abs_path(path="", root=None):
    rel = _rel(path)
    base = _root(root)
    full = (base / rel).resolve() if rel else base
    if full != base and base not in full.parents:
        raise ValueError("Ուղին պահոցից դուրս է")
    if base == VAULT.resolve() and rel and rel.split("/")[0] in HIDDEN and root is not None:
        raise ValueError("Այս թղթապանակը հասանելի չէ")
    return full


def _kind(p: Path):
    if p.is_dir():
        return "folder"
    return KIND_BY_EXT.get(p.suffix.lower(), "file")


def _info(p: Path, root: Path):
    st = p.stat()
    rel = p.relative_to(root).as_posix()
    return dict(name=p.name, path=rel, kind=_kind(p), is_dir=p.is_dir(),
                size=0 if p.is_dir() else st.st_size, ext=p.suffix.lower().lstrip("."),
                modified=datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
                items=sum(1 for _ in p.iterdir()) if p.is_dir() else None)


def listdir(path="", root=None):
    full = abs_path(path, root)
    base = _root(root)
    if not full.exists():
        if full == base:
            full.mkdir(parents=True, exist_ok=True)
        else:
            raise ValueError("Թղթապանակը չգտնվեց")
    if full.is_file():
        raise ValueError("Սա ֆայլ է, ոչ թղթապանակ")
    rows = []
    for p in full.iterdir():
        if _hidden(p, base) or p.name.startswith("."):
            continue
        try:
            rows.append(_info(p, base))
        except OSError:
            continue
    rows.sort(key=lambda r: (not r["is_dir"], r["name"].casefold()))
    rel = _rel(path)
    crumbs, acc = [], []
    for part in rel.split("/") if rel else []:
        acc.append(part)
        crumbs.append(dict(name=part, path="/".join(acc)))
    return dict(path=rel, breadcrumbs=crumbs, items=rows,
                parent="/".join(rel.split("/")[:-1]) if rel else None)


def mkdir(path, name, root=None):
    name = safe_name(name, 80, "")
    if not name:
        raise ValueError("Գրեք թղթապանակի անունը")
    full = abs_path(path, root) / name
    if full.exists():
        raise ValueError("Այդ անունով արդեն կա")
    full.mkdir(parents=True)
    _STATS.clear()
    return _info(full, _root(root))


def unique(folder: Path, name):
    """Նույն անունը չի վերագրվում՝ դառնում է «անուն (2).ext»."""
    name = safe_name(name, 120, "file")
    p = folder / name
    if not p.exists():
        return p
    stem, suf = Path(name).stem, Path(name).suffix
    for i in range(2, 999):
        p = folder / f"{stem} ({i}){suf}"
        if not p.exists():
            return p
    return folder / f"{stem} ({int(datetime.now().timestamp())}){suf}"


def save_bytes(path, name, data: bytes, root=None):
    folder = abs_path(path, root)
    folder.mkdir(parents=True, exist_ok=True)
    p = unique(folder, name)
    p.write_bytes(data)
    _STATS.clear()
    return _info(p, _root(root))


def save_file(src, kind="other", subdir=None, root=None):
    """Պատրաստված փաստաթուղթը պահում է պահոցում (ավտոմատ՝ բաժնի թղթապանակում)."""
    src = Path(src)
    rel = AUTO_DIRS.get(kind, AUTO_DIRS["other"]) + (f"/{safe_name(subdir, 60, '')}" if subdir else "")
    folder = abs_path(rel, root)
    folder.mkdir(parents=True, exist_ok=True)
    dst = unique(folder, src.name)
    shutil.copy2(src, dst)
    _STATS.clear()
    return _info(dst, _root(root))


def rename(path, new_name, root=None):
    full = abs_path(path, root)
    if not full.exists() or full == _root(root):
        raise ValueError("Չգտնվեց")
    name = safe_name(new_name, 120, "")
    if not name:
        raise ValueError("Գրեք նոր անունը")
    if full.is_file() and not Path(name).suffix:
        name += full.suffix
    dst = full.parent / name
    if dst.exists() and dst != full:
        raise ValueError("Այդ անունով արդեն կա")
    full.rename(dst)
    return _info(dst, _root(root))


def move(path, to_folder, root=None):
    src = abs_path(path, root)
    dst_dir = abs_path(to_folder, root)
    if not src.exists() or src == _root(root):
        raise ValueError("Չգտնվեց")
    if not dst_dir.exists() or not dst_dir.is_dir():
        raise ValueError("Նպատակային թղթապանակը չգտնվեց")
    if src.is_dir() and (dst_dir == src or src.resolve() in dst_dir.resolve().parents):
        raise ValueError("Թղթապանակը չի կարող տեղափոխվել իր մեջ")
    dst = unique(dst_dir, src.name)
    shutil.move(str(src), str(dst))
    return _info(dst, _root(root))


def delete(path, root=None):
    full = abs_path(path, root)
    if full == _root(root):
        raise ValueError("Արմատը ջնջել չի կարելի")
    if not full.exists():
        raise ValueError("Չգտնվեց")
    if full.is_dir():
        shutil.rmtree(full)
    else:
        full.unlink()
    _STATS.clear()
    return True


def _iter(root: Path):
    """Բոլոր ֆայլերը/թղթապանակները՝ բացի թաքնվածներից (ընդհանուր արմատում՝ users/, _warehouse/)."""
    for p in root.iterdir():
        if _hidden(p, root) or p.name.startswith("."):
            continue
        yield p
        if p.is_dir():
            yield from p.rglob("*")


def search(query, limit=300, root=None):
    q = re.sub(r"\s+", " ", str(query or "")).strip().casefold()
    if len(q) < 2:
        return []
    base = _root(root)
    if not base.exists():
        return []
    out = []
    for p in _iter(base):
        if p.name.startswith("."):
            continue
        if q in p.name.casefold():
            try:
                out.append(_info(p, base))
            except OSError:
                continue
            if len(out) >= limit:
                break
    out.sort(key=lambda r: (not r["is_dir"], r["name"].casefold()))
    return out


def tree(max_depth=2, root=None):
    """Կողային ծառի համար՝ միայն թղթապանակները."""
    base = _root(root)

    def walk(folder: Path, depth):
        kids = []
        if depth >= max_depth or not folder.exists():
            return kids
        for p in sorted(folder.iterdir(), key=lambda x: x.name.casefold()):
            if p.is_dir() and not p.name.startswith(".") and not _hidden(p, base):
                kids.append(dict(name=p.name, path=p.relative_to(base).as_posix(),
                                 children=walk(p, depth + 1)))
        return kids

    return walk(base, 0)


def stats(root=None):
    """Ֆայլերի քանակը և չափը (քեշ՝ 30 վրկ, որ մեծ պահոցը չդանդաղեցնի էջերը)."""
    base = _root(root)
    hit = _STATS.get(str(base))
    if hit and time.time() - hit[0] < 30:
        return hit[1]
    files = folders = size = 0
    if base.exists():
        for p in _iter(base):
            if p.is_dir():
                folders += 1
            else:
                files += 1
                try:
                    size += p.stat().st_size
                except OSError:
                    pass
    res = dict(files=files, folders=folders, size=size)
    _STATS[str(base)] = (time.time(), res)
    return res


def categories(root):
    """«Իմ անկյունը»՝ քանի ֆայլ կա յուրաքանչյուր բաժնի թղթապանակում."""
    base = _root(root)
    out = []
    for kind, name in AUTO_DIRS.items():
        folder = base / name
        n = 0
        last = ""
        if folder.exists():
            for p in folder.rglob("*"):
                if p.is_file():
                    n += 1
                    try:
                        m = datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="seconds")
                        last = max(last, m)
                    except OSError:
                        pass
        out.append(dict(kind=kind, name=name, path=name, files=n, last=last))
    return out


def recent(root, limit=12):
    base = _root(root)
    rows = []
    if not base.exists():
        return rows
    for p in base.rglob("*"):
        if p.is_file() and not p.name.startswith("."):
            try:
                rows.append((p.stat().st_mtime, p))
            except OSError:
                continue
    rows.sort(key=lambda x: x[0], reverse=True)
    return [_info(p, base) for _, p in rows[:limit]]


def ensure_defaults():
    (VAULT / USERS_DIR).mkdir(parents=True, exist_ok=True)
