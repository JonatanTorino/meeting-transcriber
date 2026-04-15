"""
Formateadores de salida. Todos reciben list[Segment] y escriben al path indicado.
"""
import json
from engine.base import Segment


def _fmt_srt(seconds: float) -> str:
    h  = int(seconds // 3600)
    m  = int((seconds % 3600) // 60)
    s  = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _fmt_vtt(seconds: float) -> str:
    return _fmt_srt(seconds).replace(",", ".")


def write_txt(segments: list[Segment], path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for seg in segments:
            f.write(seg.text + "\n")


def write_srt(segments: list[Segment], path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for seg in segments:
            f.write(f"{seg.id}\n")
            f.write(f"{_fmt_srt(seg.start)} --> {_fmt_srt(seg.end)}\n")
            f.write(f"{seg.text}\n\n")


def write_vtt(segments: list[Segment], path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write("WEBVTT\n\n")
        for seg in segments:
            f.write(f"{_fmt_vtt(seg.start)} --> {_fmt_vtt(seg.end)}\n")
            f.write(f"{seg.text}\n\n")


def write_json(segments: list[Segment], path: str) -> None:
    data = [
        {
            "id": seg.id,
            "start": seg.start,
            "end": seg.end,
            "text": seg.text,
            "avg_logprob": seg.avg_logprob,
            "no_speech_prob": seg.no_speech_prob,
        }
        for seg in segments
    ]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


_WRITERS = {
    "txt":  write_txt,
    "srt":  write_srt,
    "vtt":  write_vtt,
    "json": write_json,
}


def write(segments: list[Segment], fmt: str, path: str) -> None:
    writer = _WRITERS.get(fmt)
    if writer is None:
        raise ValueError(f"Formato desconocido: '{fmt}'. Disponibles: {list(_WRITERS)}")
    writer(segments, path)
