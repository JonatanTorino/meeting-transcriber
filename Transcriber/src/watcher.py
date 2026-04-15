#!/usr/bin/env python
"""
Servicio de watch — monitorea la carpeta output/ del AudioExtractor.
Transcribe automáticamente cada .wav nuevo usando la implementación configurada.

Uso:
    python watcher.py
    python watcher.py --impl faster-whisper-small   # override de impl para esta sesión
"""

import argparse
import logging
import sys
import time
from pathlib import Path

import yaml
from watchdog.events import FileCreatedEvent, FileSystemEventHandler
from watchdog.observers import Observer

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


class WavHandler(FileSystemEventHandler):
    """
    Procesa cada .wav nuevo detectado en el directorio de entrada.
    El engine se instancia una sola vez y reutiliza el modelo en memoria.
    """

    def __init__(self, config: dict, impl_name: str):
        self._config      = config
        self._impl_name   = impl_name
        self._impl_config = config["implementations"][impl_name]
        self._output_dir  = Path(config["paths"]["transcriptions"])
        self._metadata_dir = config["paths"].get("metadata", "./metadata")
        self._fmt         = config.get("default_format", "txt")
        self._output_dir.mkdir(parents=True, exist_ok=True)

        log.info("Cargando engine: %s ...", impl_name)
        self._engine = load_engine(impl_name, config)
        log.info("Engine listo. Esperando archivos...")

    def on_created(self, event: FileCreatedEvent) -> None:
        if event.is_directory:
            return
        path = Path(str(event.src_path))
        if path.suffix.lower() != ".wav":
            return
        log.info("Nuevo archivo: %s", path.name)
        self._process(path)

    def _process(self, audio_path: Path) -> None:
        output_path = str(self._output_dir / audio_path.with_suffix(f".{self._fmt}").name)

        try:
            collector = meta_module.MetricsCollector()
            collector.start()
            result  = self._engine.transcribe(str(audio_path))
            metrics = collector.stop()

            write(result.segments, self._fmt, output_path)

            meta = meta_module.build(
                audio_path=str(audio_path),
                impl_name=self._impl_name,
                impl_config=self._impl_config,
                result=result,
                metrics=metrics,
                output_path=output_path,
                output_format=self._fmt,
            )
            meta_module.save(meta, self._metadata_dir, audio_path.stem)

            perf = meta["performance"]
            log.info(
                "OK | %s | %.1f min | %.0f s | %.1fx | %d segs",
                audio_path.name,
                meta["source"]["duration_seconds"] / 60,
                perf["inference_time_seconds"],
                perf["realtime_factor"] or 0,
                meta["result"]["segment_count"],
            )

            quality = meta["quality"]
            if quality["low_confidence_segments"] > 0:
                log.warning(
                    "%s — %d segmentos con baja confianza",
                    audio_path.name,
                    quality["low_confidence_segments"],
                )

        except Exception:
            log.exception("Error procesando: %s", audio_path.name)


def _process_existing(watch_dir: Path, handler: WavHandler) -> None:
    """Procesa archivos .wav que ya estaban en la carpeta al iniciar."""
    existing = list(watch_dir.glob("*.wav"))
    if not existing:
        return
    log.info("Procesando %d archivo(s) existente(s) al inicio...", len(existing))
    for wav in existing:
        handler._process(wav)


def main() -> None:
    config = yaml.safe_load(_CONFIG_PATH.read_text(encoding="utf-8"))

    default_impl = config["default_implementation"]
    available    = list(config["implementations"].keys())

    parser = argparse.ArgumentParser(description="Watcher de transcripción automática")
    parser.add_argument(
        "--impl", "-i",
        choices=available,
        default=default_impl,
        metavar="IMPL",
        help=f"Override de implementación (default: {default_impl})",
    )
    args = parser.parse_args()

    watch_dir = Path(config["paths"]["input"]).resolve()
    if not watch_dir.exists():
        log.error("Directorio de entrada no existe: %s", watch_dir)
        sys.exit(1)

    log.info("Directorio watched : %s", watch_dir)
    log.info("Implementación     : %s", args.impl)
    log.info("Formato de salida  : %s", config.get("default_format", "txt"))

    handler  = WavHandler(config, args.impl)
    observer = Observer()
    observer.schedule(handler, str(watch_dir), recursive=False)

    _process_existing(watch_dir, handler)

    observer.start()
    log.info("Watcher activo. Ctrl+C para detener.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Deteniendo watcher...")
        observer.stop()

    observer.join()
    log.info("Watcher detenido.")


if __name__ == "__main__":
    main()
