"""
Recolecta métricas de sistema durante la transcripción y construye el JSON de metadatos.
"""
import json
import os
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import psutil

from engine.base import TranscriptionResult


@dataclass
class ProcessingMetrics:
    timestamp_start: str
    timestamp_end: str
    peak_memory_mb: float
    avg_cpu_percent: float


class MetricsCollector:
    """
    Muestrea CPU y memoria RSS en un hilo de fondo mientras corre la inferencia.
    Uso:
        collector = MetricsCollector()
        collector.start()
        result = engine.transcribe(path)
        metrics = collector.stop()
    """

    _SAMPLE_INTERVAL = 0.5  # seconds

    def __init__(self):
        self._process = psutil.Process(os.getpid())
        self._cpu_samples: list[float] = []
        self._peak_memory_bytes: int = 0
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._ts_start = ""
        self._ts_end   = ""

    def start(self) -> None:
        self._ts_start = datetime.now(timezone.utc).isoformat()
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._sample_loop, daemon=True)
        self._thread.start()

    def stop(self) -> ProcessingMetrics:
        self._ts_end = datetime.now(timezone.utc).isoformat()
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)

        avg_cpu = (
            round(sum(self._cpu_samples) / len(self._cpu_samples), 1)
            if self._cpu_samples else 0.0
        )
        peak_mb = round(self._peak_memory_bytes / 1024 / 1024, 1)

        return ProcessingMetrics(
            timestamp_start=self._ts_start,
            timestamp_end=self._ts_end,
            peak_memory_mb=peak_mb,
            avg_cpu_percent=avg_cpu,
        )

    def _sample_loop(self) -> None:
        # Primer sample en cero inicializa psutil correctamente (siempre retorna 0.0)
        self._process.cpu_percent(interval=None)
        while not self._stop_event.is_set():
            try:
                self._cpu_samples.append(self._process.cpu_percent(interval=None))
                rss = self._process.memory_info().rss
                if rss > self._peak_memory_bytes:
                    self._peak_memory_bytes = rss
            except psutil.NoSuchProcess:
                break
            self._stop_event.wait(timeout=self._SAMPLE_INTERVAL)


# ── Builder ───────────────────────────────────────────────────────────────────

_LOW_CONFIDENCE_THRESHOLD = -0.5


def build(
    audio_path: str,
    impl_name: str,
    impl_config: dict,
    result: TranscriptionResult,
    metrics: ProcessingMetrics,
    output_path: str,
    output_format: str,
) -> dict:
    segments = result.segments
    info     = result.info

    avg_logprob = (
        round(sum(s.avg_logprob for s in segments) / len(segments), 4)
        if segments else 0.0
    )
    avg_no_speech = (
        round(sum(s.no_speech_prob for s in segments) / len(segments), 4)
        if segments else 0.0
    )
    low_conf_count = sum(1 for s in segments if s.avg_logprob < _LOW_CONFIDENCE_THRESHOLD)
    word_count     = sum(len(s.text.split()) for s in segments)

    realtime_factor = (
        round(info.duration / result.inference_time, 2)
        if result.inference_time > 0 else None
    )

    audio_file = Path(audio_path)

    return {
        "transcription_id": str(uuid.uuid4()),
        "timestamp_start":  metrics.timestamp_start,
        "timestamp_end":    metrics.timestamp_end,
        "source": {
            "file":             audio_file.name,
            "duration_seconds": info.duration,
            "size_bytes":       audio_file.stat().st_size,
        },
        "engine": {
            "implementation": impl_name,
            "model":          impl_config.get("model", ""),
            "device":         impl_config.get("device", "cpu"),
            "compute_type":   impl_config.get("compute_type") or None,
        },
        "result": {
            "language_detected":    info.language,
            "language_probability": info.language_probability,
            "segment_count":        len(segments),
            "word_count":           word_count,
            "output_format":        output_format,
            "output_path":          str(Path(output_path).resolve()),
        },
        "performance": {
            "model_load_time_seconds": result.model_load_time,
            "inference_time_seconds":  result.inference_time,
            "realtime_factor":         realtime_factor,
            "peak_memory_mb":          metrics.peak_memory_mb,
            "avg_cpu_percent":         metrics.avg_cpu_percent,
        },
        "quality": {
            "avg_logprob":              avg_logprob,
            "avg_no_speech_prob":       avg_no_speech,
            "low_confidence_segments":  low_conf_count,
        },
    }


def save(meta: dict, metadata_dir: str, base_name: str) -> str:
    out_dir = Path(metadata_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{base_name}.meta.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    return str(out_path)
