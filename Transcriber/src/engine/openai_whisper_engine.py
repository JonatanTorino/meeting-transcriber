import time

import whisper

from .base import Segment, TranscriptionInfo, TranscriptionResult


class OpenAIWhisperEngine:
    """
    Engine adapter para openai-whisper (PyTorch).
    language_probability no está disponible en esta implementación.
    """

    def __init__(self, config: dict):
        self._model_name = config["model"]
        self._device     = config.get("device", "cpu")
        self._language   = config.get("language", "es")
        self._beam_size  = config.get("beam_size", 5)
        self._model = None
        self._model_load_time: float = 0.0

    @property
    def name(self) -> str:
        return f"openai-whisper/{self._model_name}"

    def _ensure_model(self) -> float:
        if self._model is not None:
            return 0.0
        t0 = time.perf_counter()
        self._model = whisper.load_model(self._model_name, device=self._device)
        return round(time.perf_counter() - t0, 3)

    def transcribe(self, audio_path: str) -> TranscriptionResult:
        model_load_time = self._ensure_model()

        t0 = time.perf_counter()
        result = self._model.transcribe(  # type: ignore[union-attr]
            audio_path,
            language=self._language,
            beam_size=self._beam_size,
            fp16=False,
        )
        inference_time = round(time.perf_counter() - t0, 3)

        raw_segments = result["segments"]
        segments = [
            Segment(
                id=i,
                start=round(s["start"], 3),
                end=round(s["end"], 3),
                text=s["text"].strip(),
                avg_logprob=round(s.get("avg_logprob", 0.0), 4),
                no_speech_prob=round(s.get("no_speech_prob", 0.0), 4),
            )
            for i, s in enumerate(raw_segments, start=1)
        ]

        duration = round(segments[-1].end, 2) if segments else 0.0

        info = TranscriptionInfo(
            language=result.get("language", self._language),
            language_probability=None,  # openai-whisper no expone este valor
            duration=duration,
        )

        return TranscriptionResult(
            segments=segments,
            info=info,
            model_load_time=model_load_time,
            inference_time=inference_time,
        )
