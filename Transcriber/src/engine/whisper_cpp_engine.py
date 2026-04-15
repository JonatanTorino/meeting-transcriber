import time

from pywhispercpp.model import Model

from .base import Segment, TranscriptionInfo, TranscriptionResult


class WhisperCppEngine:
    """
    Engine adapter para whisper.cpp (pywhispercpp, GGML/SIMD).
    Segmentos en centisegundos (t0/t1). Sin avg_logprob ni no_speech_prob.
    language_probability no está disponible en esta implementación.
    """

    def __init__(self, config: dict):
        self._model_name = config["model"]
        self._language   = config.get("language", "es")
        self._n_threads  = config.get("n_threads", 4)
        self._model: Model | None = None

    @property
    def name(self) -> str:
        return f"whisper-cpp/{self._model_name}"

    def _ensure_model(self) -> float:
        if self._model is not None:
            return 0.0
        t0 = time.perf_counter()
        self._model = Model(self._model_name, n_threads=self._n_threads)
        return round(time.perf_counter() - t0, 3)

    def transcribe(self, audio_path: str) -> TranscriptionResult:
        model_load_time = self._ensure_model()

        t0 = time.perf_counter()
        raw_segments = self._model.transcribe(audio_path, language=self._language)  # type: ignore[union-attr]
        inference_time = round(time.perf_counter() - t0, 3)

        segments = [
            Segment(
                id=i,
                start=round(s.t0 / 100.0, 3),  # centiseconds → seconds
                end=round(s.t1 / 100.0, 3),
                text=s.text.strip(),
                avg_logprob=0.0,   # not available in whisper.cpp
                no_speech_prob=0.0,
            )
            for i, s in enumerate(raw_segments, start=1)
        ]

        duration = round(segments[-1].end, 2) if segments else 0.0

        info = TranscriptionInfo(
            language=self._language,
            language_probability=None,  # whisper.cpp no expone este valor
            duration=duration,
        )

        return TranscriptionResult(
            segments=segments,
            info=info,
            model_load_time=model_load_time,
            inference_time=inference_time,
        )
