# -*- coding: utf-8 -*-
"""Ձայնային հաղորդագրություն -> տեքստ (անվճար, առանց API բանալու).
Օգտագործում է Google Web Speech (SpeechRecognition գրադարան) + ffmpeg (imageio-ffmpeg-ից):
Լեզուն՝ STT_LANG միջավայրի փոփոխականով (լռելյայն hy-AM; ռուսերենի համար՝ ru-RU)."""
import asyncio
import logging
import os
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path

log = logging.getLogger("mixbot.stt")
CHUNK_SEC = 45


def _ffmpeg():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return shutil.which("ffmpeg")


def _to_wav(src, dst):
    ff = _ffmpeg()
    if not ff:
        raise RuntimeError("ffmpeg չի գտնվել: Գրեք CMD-ում՝ pip install imageio-ffmpeg")
    r = subprocess.run([ff, "-y", "-i", str(src), "-ac", "1", "-ar", "16000", "-f", "wav", str(dst)],
                       capture_output=True)
    if r.returncode != 0 or not Path(dst).exists():
        raise RuntimeError("Աուդիոն չհաջողվեց կարդալ (ֆայլը վնասված է կամ աուդիո չէ)")


def _split(wav_path, workdir):
    parts = []
    with wave.open(str(wav_path), "rb") as w:
        rate, width, ch = w.getframerate(), w.getsampwidth(), w.getnchannels()
        step = rate * CHUNK_SEC
        i = 0
        while True:
            frames = w.readframes(step)
            if not frames:
                break
            p = Path(workdir) / f"part{i}.wav"
            with wave.open(str(p), "wb") as o:
                o.setnchannels(ch)
                o.setsampwidth(width)
                o.setframerate(rate)
                o.writeframes(frames)
            parts.append(p)
            i += 1
    return parts


def _recognize(src, lang):
    import speech_recognition as sr
    rec = sr.Recognizer()
    with tempfile.TemporaryDirectory() as td:
        wav = Path(td) / "all.wav"
        _to_wav(src, wav)
        texts = []
        for part in _split(wav, td):
            with sr.AudioFile(str(part)) as source:
                audio = rec.record(source)
            try:
                t = rec.recognize_google(audio, language=lang)
                if t:
                    texts.append(t)
            except sr.UnknownValueError:
                continue
            except sr.RequestError as e:
                raise RuntimeError(f"Խոսքի ճանաչման ծառայությունը անհասանելի է ({e}): Ստուգեք ինտերնետը")
    text = " ".join(texts).strip()
    if not text:
        raise ValueError("Խոսքը չճանաչվեց: Փորձեք ավելի պարզ ձայնագրել կամ ուղարկեք տեքստով")
    return text


async def transcribe(src, lang=None):
    lang = lang or os.getenv("STT_LANG", "hy-AM")
    try:
        return await asyncio.get_running_loop().run_in_executor(None, _recognize, src, lang)
    except ImportError:
        raise RuntimeError("SpeechRecognition-ը տեղադրված չէ: Գրեք CMD-ում՝ pip install SpeechRecognition imageio-ffmpeg")
