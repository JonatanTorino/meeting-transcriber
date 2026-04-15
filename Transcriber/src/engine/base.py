from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class Segment:
    id: int
    start: float
    end: float
    text: str
    avg_logprob: float = 0.0
    no_speech_prob: float = 0.0


@dataclass
class TranscriptionInfo:
    language: str
    duration: float
    language_probability: float | None = None  # not all engines expose this


@dataclass
class TranscriptionResult:
    segments: list[Segment]
    info: TranscriptionInfo
    model_load_time: float   # seconds — first call only; 0.0 when model is cached
    inference_time: float    # seconds — pure transcription time
