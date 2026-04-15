from .base import TranscriptionResult
from .faster_whisper_engine import FasterWhisperEngine
from .openai_whisper_engine import OpenAIWhisperEngine
from .whisper_cpp_engine import WhisperCppEngine

_ENGINE_MAP = {
    "faster-whisper": FasterWhisperEngine,
    "openai-whisper": OpenAIWhisperEngine,
    "whisper-cpp":    WhisperCppEngine,
}


def load_engine(impl_name: str, config: dict):
    """
    Instantiates the engine for a given implementation name.
    The engine caches the model internally — call transcribe() multiple times
    without reloading the model.
    """
    implementations = config.get("implementations", {})
    if impl_name not in implementations:
        available = list(implementations.keys())
        raise ValueError(f"Implementación desconocida: '{impl_name}'. Disponibles: {available}")

    impl_config = implementations[impl_name]
    engine_type = impl_config.get("engine")
    cls = _ENGINE_MAP.get(engine_type)

    if cls is None:
        available_engines = list(_ENGINE_MAP.keys())
        raise ValueError(f"Engine desconocido: '{engine_type}'. Disponibles: {available_engines}")

    return cls(impl_config)
