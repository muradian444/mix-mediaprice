# -*- coding: utf-8 -*-
"""Voice: տեքստ -> MP3 (անվճար, edge-tts) + ձայների բանկ (ներբեռնված MP3 ձայներ).
Ցանկացած սխալ դառնում է հասկանալի հաղորդագրություն, բոտը չի ընկնում."""
import asyncio
import json
import logging
import os
import re
import shutil
import tempfile
import time
from pathlib import Path

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

log = logging.getLogger("mixbot.voice")

DATA = Path(__file__).resolve().parent.parent / "data"
VDIR = DATA / "voices"      # ներբեռնված MP3 ձայներ
SDIR = DATA / "samples"     # անվճար ձայների նմուշների քեշ
BANK = DATA / "voices.json"  # ներբեռնված ձայների ցանկ

BUILTIN = {
    "male": {"name": "Տղամարդու ձայն", "kind": "tts", "edge": "hy-AM-HaykNeural"},
    "female": {"name": "Կնոջ ձայն", "kind": "tts", "edge": "hy-AM-AnahitNeural"},
}
SAMPLE_TEXT = "Բարև ձեզ, սա Mix Media-ի ձայնն է:"
MAX_CHARS = 4000
MAX_CLONE_CHARS = 1500       # կլոնավորված ձայնով՝ ավելի կարճ տեքստ (CPU-ն դանդաղ է)
REF_MIN_SEC = 3              # ավելի կարճ ձայնագրություն չենք ընդունում
REF_WARN_SEC = 20            # սրանից կարճի դեպքում որակը վատ է՝ զգուշացնում ենք
REF_MAX_SEC = 180            # օգտագործում ենք առավելագույնը 3 րոպե
MAX_DUB_SEC = 300            # ձայնային հաղորդագրություն՝ առավելագույնը 5 րոպե
_HEAVY = asyncio.Lock()      # միաժամանակ միայն մեկ ծանր աշխատանք (RAM-ը չի վերջանում)


# ------------------------------------------------------------------ ձայների բանկ
def _load_bank():
    try:
        return json.load(open(BANK, encoding="utf-8"))
    except Exception:
        return {}


def _save_bank(d):
    DATA.mkdir(exist_ok=True)
    json.dump(d, open(BANK, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def all_voices():
    """Բոլոր ձայները՝ սկզբում անվճար (TTS), հետո ներբեռնվածները (կլոն)."""
    out = dict(BUILTIN)
    for k, v in _load_bank().items():
        out[k] = {"name": v["name"], "kind": "clone", "file": v["file"], "ref": v.get("ref")}
    return out


def is_builtin(key):
    return key in BUILTIN


def _ffmpeg():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return shutil.which("ffmpeg")


def load_audio_16k(path, max_sec=None):
    """Ցանկացած աուդիո (mp3/ogg/wav/m4a...) -> numpy float32 mono 16 kHz."""
    import subprocess
    import numpy as np
    ff = _ffmpeg()
    if not ff:
        raise RuntimeError("ffmpeg չի գտնվել: Գրեք CMD-ում՝ pip install imageio-ffmpeg")
    cmd = [ff, "-v", "error", "-i", str(path)]
    if max_sec:
        cmd += ["-t", str(max_sec)]
    cmd += ["-vn", "-ac", "1", "-ar", "16000", "-f", "f32le", "-"]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0 or not r.stdout:
        raise ValueError("Ֆայլը աուդիո չէ կամ վնասված է")
    return np.frombuffer(r.stdout, dtype=np.float32).copy()


def check_reference(path):
    """Ստուգում է ձայնագրությունը. վերադարձնում է (վայրկյան, զգուշացում կամ None)."""
    import numpy as np
    x = load_audio_16k(path, REF_MAX_SEC)
    sec = len(x) / 16000
    if sec < REF_MIN_SEC:
        raise ValueError(f"Ձայնագրությունը շատ կարճ է ({sec:.1f} վրկ): Պետք է առնվազն {REF_MIN_SEC} վրկ, լավ է՝ 1-3 րոպե")
    if float(np.sqrt(np.mean(x ** 2))) < 1e-3:
        raise ValueError("Ձայնագրությունը գրեթե լուռ է")
    warn = None
    if sec < REF_WARN_SEC:
        warn = f"Ձայնագրությունը կարճ է ({sec:.0f} վրկ): Որակն ավելի լավ կլինի 1-3 րոպե մաքուր խոսքով (առանց երաժշտության և աղմուկի)"
    return sec, warn


def add_mp3_voice(name, src_path):
    """Ավելացնում է նոր ձայն (ձայնագրություն) բանկում. վերադարձնում է բանալին.
    Ֆայլը նախ ստուգվում է. վատ ֆայլի դեպքում ValueError և ոչինչ չի պահվում."""
    import wave
    import numpy as np
    check_reference(src_path)
    x = load_audio_16k(src_path, REF_MAX_SEC)
    VDIR.mkdir(parents=True, exist_ok=True)
    key = "u" + str(int(time.time() * 1000))
    dst = VDIR / f"{key}.mp3"
    ref = VDIR / f"{key}.ref.wav"
    with wave.open(str(ref), "wb") as o:
        o.setnchannels(1)
        o.setsampwidth(2)
        o.setframerate(16000)
        o.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())
    shutil.move(str(src_path), str(dst))
    bank = _load_bank()
    bank[key] = {"name": name.strip()[:40] or key, "file": f"voices/{key}.mp3", "ref": f"voices/{key}.ref.wav"}
    _save_bank(bank)
    return key


def delete_voice(key):
    if key in BUILTIN:
        return False
    bank = _load_bank()
    v = bank.pop(key, None)
    if v is None:
        return False
    _save_bank(bank)
    for rel in (v.get("file"), v.get("ref"), f"samples/{key}.mp3"):
        try:
            if rel:
                (DATA / rel).unlink()
        except Exception:
            pass
    return True


def _load_ref(v):
    """Ձայնի հղման ձայնագրությունը որպես numpy 16 kHz."""
    import wave
    import numpy as np
    if v.get("ref") and (DATA / v["ref"]).exists():
        with wave.open(str(DATA / v["ref"]), "rb") as w:
            return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    p = DATA / v["file"]
    if not p.exists():
        raise ValueError("Ձայնի ֆայլը չի գտնվել (գուցե ջնջվել է). Բեռնեք նորից")
    return load_audio_16k(p, REF_MAX_SEC)


# ------------------------------------------------------------------ սինթեզ
def _tmp():
    fd, p = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    return Path(p)


def _edge_version():
    try:
        from importlib.metadata import version
        return version("edge-tts")
    except Exception:
        return "?"


_EDGE_DOWN_UNTIL = 0.0   # եթե edge-tts-ը չի աշխատում՝ 10 րոպե չենք փորձում, անցնում ենք տեղական շարժիչին


async def _edge(text, voice):
    import edge_tts
    last = None
    for attempt in range(2):
        out = _tmp()
        try:
            await asyncio.wait_for(edge_tts.Communicate(text, voice).save(str(out)), timeout=30)
            if out.stat().st_size > 0:
                return out
            last = RuntimeError("դատարկ աուդիո")
        except Exception as e:  # noqa
            last = e
            log.warning("edge-tts attempt %s failed: %s", attempt + 1, e)
        out.unlink(missing_ok=True)
        await asyncio.sleep(1)
    raise last


# ------------------------------------------------------------------ տեղական շարժիչ (MMS, անվճար, օֆլայն)
MMS_REPOS = [r for r in (os.getenv("MMS_REPO"), "facebook/mms-tts-hye", "facebook/mms-tts-hyw") if r]
_mms = None


def _mms_load():
    global _mms
    if _mms:
        return _mms
    from transformers import AutoTokenizer, VitsModel
    last = None
    for repo in MMS_REPOS:
        try:
            tok = AutoTokenizer.from_pretrained(repo)
            model = VitsModel.from_pretrained(repo)
            model.eval()
            _mms = (model, tok, repo)
            log.info("MMS model loaded: %s", repo)
            return _mms
        except Exception as e:  # noqa
            last = e
            log.warning("MMS %s failed: %s", repo, e)
    raise last


def _chunks(text, size=180):
    parts, cur = [], ""
    for sent in re.split(r"(?<=[.!?։:;,])\s+", text):
        if len(cur) + len(sent) + 1 > size and cur:
            parts.append(cur)
            cur = ""
        cur = (cur + " " + sent).strip()
        while len(cur) > size:
            cut = cur.rfind(" ", 0, size)
            cut = cut if cut > 0 else size
            parts.append(cur[:cut].strip())
            cur = cur[cut:].strip()
    if cur:
        parts.append(cur)
    return parts


def _wav_to_mp3(wav_path, mp3_path, male):
    import subprocess
    ff = _ffmpeg()
    if not ff:
        raise RuntimeError("ffmpeg չի գտնվել: pip install imageio-ffmpeg")
    cmd = [ff, "-y", "-i", str(wav_path)]
    if male:  # մեկ ձայն ունենք՝ տղամարդու տարբերակը ստանում ենք ձայնը ցածրացնելով
        cmd += ["-af", "asetrate=16000*0.82,aresample=16000,atempo=1.2195"]
    cmd += ["-codec:a", "libmp3lame", "-q:a", "3", str(mp3_path)]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0 or not Path(mp3_path).exists():
        raise RuntimeError("Աուդիոն MP3 դարձնել չհաջողվեց")


def _mms_sync(text, male):
    import wave
    import numpy as np
    import torch
    model, tok, repo = _mms_load()
    sr = int(model.config.sampling_rate)
    pieces = []
    for chunk in _chunks(text.lower()):
        inputs = tok(chunk, return_tensors="pt")
        if inputs["input_ids"].shape[-1] == 0:
            continue
        with torch.no_grad():
            w = model(**inputs).waveform[0].cpu().numpy().astype(np.float32)
        pieces += [w, np.zeros(int(sr * 0.25), dtype=np.float32)]
    if not pieces:
        raise ValueError("Տեքստում հայերեն տառեր չկան (թվերը և օտար տառերը չեն կարդացվում)")
    pcm = (np.clip(np.concatenate(pieces), -1, 1) * 32767).astype(np.int16)
    fd, wav_path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        with wave.open(wav_path, "wb") as o:
            o.setnchannels(1)
            o.setsampwidth(2)
            o.setframerate(sr)
            o.writeframes(pcm.tobytes())
        out = _tmp()
        _wav_to_mp3(wav_path, out, male)
        return out
    finally:
        Path(wav_path).unlink(missing_ok=True)


# ------------------------------------------------------------------ թվերը -> հայերեն բառեր
_ONES = ["զրո", "մեկ", "երկու", "երեք", "չորս", "հինգ", "վեց", "յոթ", "ութ", "ինը"]
_TENS = {2: "քսան", 3: "երեսուն", 4: "քառասուն", 5: "հիսուն", 6: "վաթսուն", 7: "յոթանասուն", 8: "ութսուն", 9: "իննսուն"}


def arm_number(n: int) -> str:
    if n < 10:
        return _ONES[n]
    if n < 20:
        return "տասը" if n == 10 else "տասն" + _ONES[n - 10]
    if n < 100:
        t, o = divmod(n, 10)
        return _TENS[t] + (_ONES[o] if o else "")
    if n < 1000:
        h, r = divmod(n, 100)
        w = "հարյուր" if h == 1 else _ONES[h] + " հարյուր"
        return w + (" " + arm_number(r) if r else "")
    for base, word in ((10 ** 9, "միլիարդ"), (10 ** 6, "միլիոն"), (1000, "հազար")):
        if n >= base:
            q, r = divmod(n, base)
            w = word if (base == 1000 and q == 1) else arm_number(q) + " " + word
            return w + (" " + arm_number(r) if r else "")
    return str(n)


def normalize_text(text: str) -> str:
    """Թվերը և % նշանը դարձնում է հայերեն բառեր (մոդելը թվեր չի կարդում)."""
    def dec(m):
        a, b = m.group(1), m.group(2)
        return arm_number(int(a)) + " ստորակետ " + " ".join(_ONES[int(c)] for c in b)

    def num(m):
        raw = m.group(0)
        if len(raw) > 12:
            return " ".join(_ONES[int(c)] for c in raw)
        return arm_number(int(raw))

    text = re.sub(r"(\d+)[.,](\d+)", dec, text)
    text = re.sub(r"\d+", num, text)
    return text.replace("%", " տոկոս ")


# ------------------------------------------------------------------ ձայնի կլոնավորում (kNN-VC, անվճար)
_knn = None


def _knn_load():
    global _knn
    if _knn is not None:
        return _knn
    try:
        import torchaudio  # noqa: F401  (kNN-VC-ին պետք է)
    except ImportError:
        raise ImportError("torchaudio")
    import torch
    _knn = torch.hub.load("bshall/knn-vc", "knn_vc", prematched=True, trust_repo=True,
                          pretrained=True, device=os.getenv("KNN_DEVICE", "cpu"))
    log.info("kNN-VC loaded")
    return _knn


def _knn_feats(knn, arr):
    import torch
    x = torch.from_numpy(arr).unsqueeze(0)
    try:
        return knn.get_features(x, vad_trigger_level=0)
    except Exception:
        return knn.get_features(torch.from_numpy(arr), vad_trigger_level=0)


def _clone_sync(base_mp3, ref_arr):
    """base_mp3 (հայերեն խոսք) -> նույն խոսքը ref ձայնի տեմբրով. վերադարձնում է MP3."""
    import wave
    import numpy as np
    import torch
    knn = _knn_load()
    query = load_audio_16k(base_mp3)
    if len(query) < 1600:
        raise RuntimeError("Բազային ձայնը դատարկ է")
    with torch.inference_mode():
        q = _knn_feats(knn, query)
        m = _knn_feats(knn, ref_arr).cpu()
        topk = 4 if m.shape[0] > 2000 else 2
        out = knn.match(q, m, topk=topk)
    out = out.detach().cpu().numpy().astype(np.float32).reshape(-1)
    pcm = (np.clip(out, -1, 1) * 32767).astype(np.int16)
    fd, wav_path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        with wave.open(wav_path, "wb") as o:
            o.setnchannels(1)
            o.setsampwidth(2)
            o.setframerate(16000)
            o.writeframes(pcm.tobytes())
        mp3 = _tmp()
        _wav_to_mp3(wav_path, mp3, False)
        return mp3
    finally:
        Path(wav_path).unlink(missing_ok=True)


# ------------------------------------------------------------------ հիմնական սինթեզ
async def _tts_base(text: str, key: str) -> Path:
    """Անվճար ձայն: 1) edge-tts (Microsoft)  2) եթե չաշխատեց՝ տեղական MMS (Meta)."""
    global _EDGE_DOWN_UNTIL
    v = BUILTIN[key]
    errors = []
    if time.time() >= _EDGE_DOWN_UNTIL:
        try:
            return await _edge(text, v["edge"])
        except ImportError:
            errors.append("edge-tts չկա")
        except Exception as e:  # noqa
            errors.append(f"edge-tts {_edge_version()}: {type(e).__name__}")
            _EDGE_DOWN_UNTIL = time.time() + 600
            log.warning("edge-tts down, switching to local MMS for 10 min: %s", e)
    try:
        return await asyncio.get_running_loop().run_in_executor(None, _mms_sync, text, key == "male")
    except ValueError:
        raise
    except ImportError:
        errors.append("տեղական շարժիչը տեղադրված չէ")
        raise RuntimeError(" | ".join(errors) + ". Գրեք CMD-ում՝ pip install torch transformers numpy imageio-ffmpeg")
    except Exception as e:  # noqa
        log.exception("MMS failed")
        errors.append(f"MMS: {type(e).__name__}: {e}")
        raise RuntimeError(" | ".join(errors))


async def synth(text: str, key: str) -> Path:
    """Տեքստ -> MP3 ֆայլի ճանապարհ (ֆայլը ջնջել ուղարկելուց հետո)."""
    text = re.sub(r"\s+", " ", (text or "")).strip()
    if not text:
        raise ValueError("Տեքստը դատարկ է")
    v = all_voices().get(key)
    if not v:
        raise ValueError("Անհայտ ձայն (գուցե ջնջվել է). Ընտրեք ձայնը նորից")
    limit = MAX_CLONE_CHARS if v["kind"] == "clone" else MAX_CHARS
    if len(text) > limit:
        raise ValueError(f"Տեքստը շատ երկար է (առավելագույնը {limit} նիշ, Ձեր տեքստը՝ {len(text)})")
    text = normalize_text(text)
    if not re.search(r"\w", text):
        raise ValueError("Տեքստում կարդալու բան չկա (միայն նշաններ)")
    async with _HEAVY:
        if v["kind"] == "tts":
            return await _tts_base(text, key)
        # կլոն՝ նախ բազային հայերեն խոսք, հետո փոխում ենք տեմբրը
        ref = _load_ref(v)
        base = await _tts_base(text, "female")
        try:
            return await asyncio.get_running_loop().run_in_executor(None, _clone_sync, base, ref)
        except ImportError:
            raise RuntimeError("Կլոնավորման գրադարանը տեղադրված չէ: Գրեք CMD-ում՝ pip install torchaudio")
        except ValueError:
            raise
        except Exception as e:  # noqa
            log.exception("clone failed")
            raise RuntimeError(f"Կլոնավորումը չհաջողվեց ({type(e).__name__}: {e}). "
                               "Ստուգեք ինտերնետը (առաջին անգամ ներբեռնվում են մոդելներ) և python check_clone.py")
        finally:
            base.unlink(missing_ok=True)


def clone_status():
    """Պատրա՞ստ է կլոնավորումը այս համակարգչում. -> (ready, բացակայող փաթեթներ)."""
    from importlib.util import find_spec
    missing = [m for m in ("numpy", "torch", "torchaudio") if find_spec(m) is None]
    return not missing, missing


async def dub(src_path, key: str, mode: str = "convert", lang=None):
    """Ձայնային հաղորդագրություն -> դիկտորի ձայնով MP3. -> (mp3 path, ճանաչված տեքստ կամ '').
    mode='convert'՝ նույն խոսքը դիկտորի տեմբրով (ինտոնացիան պահվում է, տեքստ չի ճանաչվում).
    mode='retell'՝ խոսքը ճանաչվում է տեքստի և դիկտորը կարդում է այն նորից (մաքուր արտասանություն)."""
    v = all_voices().get(key)
    if not v:
        raise ValueError("Անհայտ ձայն (գուցե ջնջվել է). Ընտրեք դիկտորին նորից")
    if v["kind"] != "clone":
        raise ValueError("Ընտրեք դիկտորին՝ ձեր բեռնած ձայնը (MP3 նմուշով): Պատրաստի ձայները չեն կլոնավորվում")
    if mode == "retell":
        import stt
        text = await stt.transcribe(src_path, lang)
        return await synth(text, key), text
    x = load_audio_16k(src_path, MAX_DUB_SEC + 1)      # ստուգում ենք՝ աուդիո է, ոչ դատարկ, ոչ չափազանց երկար
    sec = len(x) / 16000
    if sec < 0.5:
        raise ValueError("Ձայնագրությունը շատ կարճ է")
    if sec > MAX_DUB_SEC:
        raise ValueError(f"Ձայնագրությունը շատ երկար է (առավելագույնը {MAX_DUB_SEC // 60} րոպե)")
    if float(abs(x).mean()) < 1e-4:
        raise ValueError("Ձայնագրությունը գրեթե լուռ է")
    async with _HEAVY:
        ref = _load_ref(v)
        try:
            out = await asyncio.get_running_loop().run_in_executor(None, _clone_sync, src_path, ref)
        except ImportError:
            raise RuntimeError("Կլոնավորման գրադարանը տեղադրված չէ: Գործարկեք install_voice.bat")
        except ValueError:
            raise
        except Exception as e:  # noqa
            log.exception("dub failed")
            raise RuntimeError(f"Փոխակերպումը չհաջողվեց ({type(e).__name__}: {e}). "
                               "Ստուգեք ինտերնետը (առաջին անգամ ներբեռնվում են մոդելներ)")
    return out, ""


async def sample(key: str) -> Path:
    """Ձայնի նմուշ լսելու համար. վերադարձնում է ՊԱՀՊԱՆՎԱԾ ֆայլ (չջնջել)."""
    v = all_voices().get(key)
    if not v:
        raise ValueError("Անհայտ ձայն")
    SDIR.mkdir(parents=True, exist_ok=True)
    cached = SDIR / f"{key}.mp3"
    if cached.exists() and cached.stat().st_size > 0:
        return cached
    tmp = await synth(SAMPLE_TEXT, key)
    shutil.move(str(tmp), str(cached))
    return cached
