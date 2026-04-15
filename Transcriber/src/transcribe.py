#!/usr/bin/env python
"""
CLI de transcripción directa — para testing y comparación de implementaciones.

Uso:
    python transcribe.py <audio.wav>
    python transcribe.py <audio.wav> --impl faster-whisper-turbo --format srt
    python transcribe.py <audio.wav> --impl whisper-cpp-medium --format vtt --output ./out/

Ejemplo de comparación rápida:
    python transcribe.py reunion.wav --impl faster-whisper-small
    python transcribe.py reunion.wav --impl faster-whisper-turbo
    python transcribe.py reunion.wav --impl whisper-cpp-medium
"""

import argparse
import logging
import sys
from pathlib import Path

import yaml

import metadata as meta_module
from engine.loader import load_engine
from formatters import write

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s %(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).parent / "config.yaml"


def main() -> None:
    config = yaml.safe_load(_CONFIG_PATH.read_text(encoding="utf-8"))

    default_impl = config["default_implementation"]
    available    = list(config["implementations"].keys())
    default_fmt  = config.get("default_format", "txt")

    parser = argparse.ArgumentParser(
        description="Transcripción directa con Whisper — elige implementación y formato"
    )
    parser.add_argument("audio", help="Ruta al archivo de audio (WAV recomendado, 16 kHz mono)")
    parser.add_argument(
        "--impl", "-i",
        choices=available,
        default=default_impl,
        metavar="IMPL",
        help=f"Implementación a usar (default: {default_impl}). Opciones: {', '.join(available)}",
    )
    parser.add_argument(
        "--format", "-f",
        choices=["txt", "srt", "vtt", "json"],
        default=default_fmt,
        help=f"Formato de salida (default: {default_fmt})",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Ruta o directorio de salida. Si es directorio, el nombre se deriva del audio.",
    )
    args = parser.parse_args()

    audio_path = Path(args.audio).resolve()
    if not audio_path.exists():
        log.error("Archivo no encontrado: %s", audio_path)
        sys.exit(1)

    # Resolve output path
    if args.output:
        out = Path(args.output)
        output_path = str(out / audio_path.with_suffix(f".{args.format}").name) if out.is_dir() else str(out)
    else:
        output_path = str(audio_path.with_suffix(f".{args.format}"))

    impl_name   = args.impl
    impl_config = config["implementations"][impl_name]

    log.info("Audio  : %s", audio_path.name)
    log.info("Impl   : %s | Modelo: %s | Formato: %s", impl_name, impl_config.get("model"), args.format)

    engine = load_engine(impl_name, config)

    collector = meta_module.MetricsCollector()
    collector.start()
    result  = engine.transcribe(str(audio_path))
    metrics = collector.stop()

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    write(result.segments, args.format, output_path)

    meta = meta_module.build(
        audio_path=str(audio_path),
        impl_name=impl_name,
        impl_config=impl_config,
        result=result,
        metrics=metrics,
        output_path=output_path,
        output_format=args.format,
    )

    metadata_dir = config["paths"].get("metadata", "./metadata")
    meta_path    = meta_module.save(meta, metadata_dir, audio_path.stem)

    # ── One-line summary ──────────────────────────────────────────────────────
    perf    = meta["performance"]
    quality = meta["quality"]
    dur_min = meta["source"]["duration_seconds"] / 60
    log.info(
        "OK | %s | %.1f min audio | %.0f s proceso | %.1fx realtime | %d segs | logprob %.3f",
        impl_name,
        dur_min,
        perf["inference_time_seconds"],
        perf["realtime_factor"] or 0,
        meta["result"]["segment_count"],
        quality["avg_logprob"],
    )
    log.info("Transcripción → %s", output_path)
    log.info("Metadatos     → %s", meta_path)

    if quality["low_confidence_segments"] > 0:
        pct = quality["low_confidence_segments"] / max(meta["result"]["segment_count"], 1) * 100
        log.warning(
            "%d segmentos con baja confianza (%.1f%%) — revisá el resultado",
            quality["low_confidence_segments"],
            pct,
        )

    print("\n--- PREVIEW (primeros 5 segmentos) ---")
    for seg in result.segments[:5]:
        print(f"  [{seg.start:.1f}s → {seg.end:.1f}s] {seg.text}")


if __name__ == "__main__":
    main()
