import time

from faster_whisper import WhisperModel

from .base import Segment, TranscriptionEngine, TranscriptionInfo, TranscriptionResult


class FasterWhisperEngine:
    """
    Engine adapter para faster-whisper (CTranslate2).
    El modelo se carga en la primera llamada a transcribe() y se reutiliza.
    """

    def __init__(self, config: dict):
        self._model_name   = config["model"]
        self._device       = config.get("device", "cpu")
        self._compute_type = config.get("compute_type", "int8")
        self._beam_size    = config.get("beam_size", 5)
        self._language     = config.get("language", "es")
        self._vad_filter   = config.get("vad_filter", True)
        self._vad_min_silence_ms = config.get("vad_min_silence_ms", 500)
        self._model: WhisperModel | None = None
        self._model_load_time: float = 0.0

    @property
    def name(self) -> str:
        return f"faster-whisper/{self._model_name}"

    def _ensure_model(self) -> float:
        """Loads the model on first call. Returns load time (0.0 if already loaded)."""
        if self._model is not None:
            return 0.0
        t0 = time.perf_counter()
        self._model = WhisperModel(
            self._model_name,
            device=self._device,
            compute_type=self._compute_type,
        )
        return round(time.perf_counter() - t0, 3)

    def transcribe(self, audio_path: str) -> TranscriptionResult:
        model_load_time = self._ensure_model()

        t0 = time.perf_counter()
        raw_segments, raw_info = self._model.transcribe(  # type: ignore[union-attr]
            audio_path,
            beam_size=self._beam_size,
            language=self._language,
            vad_filter=self._vad_filter,
            vad_parameters={"min_silence_duration_ms": self._vad_min_silence_ms},
        )
        segments_list = list(raw_segments)  # force evaluation before stopping the timer
        inference_time = round(time.perf_counter() - t0, 3)

        segments = [
            Segment(
                id=i,
                start=round(s.start, 3),
                end=round(s.end, 3),
                text=s.text.strip(),
                avg_logprob=round(s.avg_logprob, 4),
                no_speech_prob=round(s.no_speech_prob, 4),
            )
            for i, s in enumerate(segments_list, start=1)
        ]

        info = TranscriptionInfo(
            language=raw_info.language,
            language_probability=round(raw_info.language_probability, 4),
            duration=round(raw_info.duration, 2),
        )

        return TranscriptionResult(
            segments=segments,
            info=info,
            model_load_time=model_load_time,
            inference_time=inference_time,
        )
