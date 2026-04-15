# Transcriber — Arquitectura del Sistema

**Transcriber** es el segundo componente del pipeline `meeting-transcriber`.
Recibe archivos WAV de 16 kHz mono producidos por **AudioExtractor**, los
transcribe usando uno de tres backends Whisper intercambiables, y escribe la
salida en cuatro formatos posibles (TXT, SRT, VTT, JSON) junto con un JSON de
métricas por transcripción.

El sistema expone dos modos de operación independientes:

- **`transcribe.py`** — CLI one-shot para uso interactivo, testing y comparación
  de implementaciones.
- **`watcher.py`** — Servicio continuo event-driven que monitorea el directorio
  de salida de AudioExtractor y transcribe automáticamente cada WAV nuevo.

---

## Tabla de contenidos

1. [Arquitectura de alto nivel](#1-arquitectura-de-alto-nivel)
2. [Diagrama de clases](#2-diagrama-de-clases)
3. [Pipeline completo — flujo de control](#3-pipeline-completo--flujo-de-control)
4. [Secuencia del watcher — happy path](#4-secuencia-del-watcher--happy-path)
5. [Estados del archivo transcrito](#5-estados-del-archivo-transcrito)
6. [Comparación de engines](#6-comparacion-de-engines)
7. [Decisiones de diseño](#7-decisiones-de-diseño)

---

## 1. Arquitectura de alto nivel

El sistema se organiza en cinco capas bien delimitadas. La capa de entrada
contiene los dos entrypoints (`transcribe.py` y `watcher.py`). La capa de
orquestación (`loader.py`) actúa como Factory que resuelve el engine correcto
según configuración. Los tres engines implementan una interfaz uniforme (Strategy
Pattern). La capa de salida separa los formateadores de texto del recolector de
métricas. La configuración centralizada en `config.yaml` fluye hacia todas las
capas en tiempo de arranque.

```mermaid
graph TD
    subgraph ENTRADA["Capa de Entrada"]
        CLI["transcribe.py\none-shot CLI"]
        WATCH["watcher.py\nservicio continuo"]
    end

    subgraph CONFIG["Configuración"]
        YAML["config.yaml\ndefault_implementation\ndefault_format\npaths"]
    end

    subgraph ORQUESTACION["Orquestación"]
        LOADER["engine/loader.py\nload_engine(impl, config)"]
    end

    subgraph ENGINES["Motores de Transcripción — Strategy Pattern"]
        FW["FasterWhisperEngine\nCTranslate2 · GPU/CPU · VAD"]
        OW["OpenAIWhisperEngine\nPyTorch · GPU/CPU"]
        WC["WhisperCppEngine\nGGML/C++ · CPU only"]
    end

    subgraph SALIDA["Capa de Salida"]
        FMT["formatters.py\ntxt · srt · vtt · json"]
        META["metadata.py\nMetricsCollector + build + save"]
    end

    subgraph FS["Filesystem"]
        IN["../AudioExtractor/output/\n*.wav"]
        OUT_T["./transcriptions/\n*.txt | *.srt | *.vtt | *.json"]
        OUT_M["./metadata/\n*.meta.json"]
    end

    subgraph EXT["Dependencias externas"]
        WD["watchdog\nFileSystemEventHandler"]
        PS["psutil\nCPU + RSS sampling"]
        CTC2["CTranslate2 / PyTorch / GGML\nbackends de inferencia"]
    end

    YAML -->|carga al arranque| CLI
    YAML -->|carga al arranque| WATCH
    IN -->|archivo .wav| CLI
    IN -->|evento on_created| WATCH
    WATCH -->|usa| WD
    CLI -->|load_engine| LOADER
    WATCH -->|load_engine| LOADER
    LOADER -->|instancia| FW
    LOADER -->|instancia| OW
    LOADER -->|instancia| WC
    FW -->|TranscriptionResult| FMT
    OW -->|TranscriptionResult| FMT
    WC -->|TranscriptionResult| FMT
    FW -->|TranscriptionResult| META
    OW -->|TranscriptionResult| META
    WC -->|TranscriptionResult| META
    META -->|usa| PS
    FW -.->|backend| CTC2
    OW -.->|backend| CTC2
    WC -.->|backend| CTC2
    FMT -->|escribe| OUT_T
    META -->|escribe| OUT_M
```

---

## 2. Diagrama de clases

Muestra la jerarquía completa: las dataclasses del contrato de datos
(`engine/base.py`), los tres engines concretos con su lazy-load interno, la
clase `WavHandler` del watcher, y las dos clases de métricas. Las relaciones de
composición reflejan qué produce qué en tiempo de ejecución.

```mermaid
classDiagram
    class Segment {
        +int id
        +float start
        +float end
        +str text
        +float avg_logprob
        +float no_speech_prob
    }

    class TranscriptionInfo {
        +str language
        +float duration
        +float|None language_probability
    }

    class TranscriptionResult {
        +list~Segment~ segments
        +TranscriptionInfo info
        +float model_load_time
        +float inference_time
    }

    class Engine {
        <<abstract>>
        +_ensure_model() float
        +transcribe(audio_path) TranscriptionResult
    }

    class FasterWhisperEngine {
        -str _model_name
        -str _device
        -str _compute_type
        -int _beam_size
        -str _language
        -bool _vad_filter
        -int _vad_min_silence_ms
        -WhisperModel|None _model
        +_ensure_model() float
        +transcribe(audio_path) TranscriptionResult
    }

    class OpenAIWhisperEngine {
        -str _model_name
        -str _device
        -int _beam_size
        -str _language
        -model|None _model
        +_ensure_model() float
        +transcribe(audio_path) TranscriptionResult
    }

    class WhisperCppEngine {
        -str _model_name
        -str _language
        -int _n_threads
        -Whisper|None _model
        +_ensure_model() float
        +transcribe(audio_path) TranscriptionResult
    }

    class ProcessingMetrics {
        +str timestamp_start
        +str timestamp_end
        +float peak_memory_mb
        +float avg_cpu_percent
    }

    class MetricsCollector {
        -Process _process
        -list _cpu_samples
        -int _peak_memory_bytes
        -Event _stop_event
        -Thread|None _thread
        +start() void
        +stop() ProcessingMetrics
        -_sample_loop() void
    }

    class WavHandler {
        -dict _config
        -str _impl_name
        -dict _impl_config
        -Path _output_dir
        -str _metadata_dir
        -str _fmt
        -Engine _engine
        +on_created(event) void
        -_process(audio_path) void
    }

    Engine <|-- FasterWhisperEngine : implements
    Engine <|-- OpenAIWhisperEngine : implements
    Engine <|-- WhisperCppEngine : implements

    TranscriptionResult "1" *-- "many" Segment : contains
    TranscriptionResult "1" *-- "1" TranscriptionInfo : contains

    FasterWhisperEngine ..> TranscriptionResult : produces
    OpenAIWhisperEngine ..> TranscriptionResult : produces
    WhisperCppEngine ..> TranscriptionResult : produces

    MetricsCollector ..> ProcessingMetrics : produces
    WavHandler *-- Engine : owns (singleton)
    WavHandler ..> MetricsCollector : creates per file
```

---

## 3. Pipeline completo — flujo de control

Cubre ambos entrypoints en un solo diagrama. El branching superior separa el
modo CLI del modo watcher. En el watcher, el engine se instancia una sola vez al
startup y el modelo queda en cache en memoria para todas las transcripciones
subsiguientes. Los dos caminos de error (excepción en transcripción y segmentos
de baja confianza) se muestran explícitamente.

```mermaid
flowchart TD
    Start([Inicio]) --> LoadConfig[Cargar config.yaml]
    LoadConfig --> EntryPoint{Entrypoint?}

    EntryPoint -->|transcribe.py| CLIArgs[/Parsear CLI args\naudio · impl · format · output/]
    EntryPoint -->|watcher.py| WatchArgs[/Parsear CLI args\nimpl override/]

    CLIArgs --> CLIValidate{audio existe?}
    CLIValidate -->|No| CLIError[/log.error\nsys.exit 1/]
    CLIValidate -->|Si| CLILoad[load_engine una vez]

    WatchArgs --> WatchValidate{input_dir existe?}
    WatchValidate -->|No| WatchError[/log.error\nsys.exit 1/]
    WatchValidate -->|Si| WatchLoad[load_engine UNA SOLA VEZ\nWavHandler.__init__]

    WatchLoad --> ProcessExisting[_process_existing\nescanear *.wav al startup]
    ProcessExisting --> ObserverStart[Observer.schedule + start\nwatchdog activo]
    ObserverStart --> WatchLoop{KeyboardInterrupt?}
    WatchLoop -->|No — time.sleep 1| WatchLoop
    WatchLoop -->|on_created evento| FilterExt{es .wav?}
    FilterExt -->|No| Ignored([Ignorado])
    FilterExt -->|Si| WatchProcess[WavHandler._process]

    WatchLoop -->|Si — Ctrl+C| Shutdown[Observer.stop + join]
    Shutdown --> End([Fin ordenado])

    CLILoad --> CLIProcess[transcripción]
    WatchProcess --> CommonPath

    CLIProcess --> CommonPath

    subgraph CommonPath["Pipeline compartido"]
        direction TD
        MC_Start[MetricsCollector.start\nUTC timestamp + hilo daemon]
        EnsureModel{modelo\ncargado?}
        ModelLoad[_ensure_model\ncargar modelo — mide tiempo]
        Transcribe[engine.transcribe\ninferencia Whisper]
        MC_Stop[MetricsCollector.stop\ndetener hilo · calcular avg_cpu · peak_mb]
        WriteOutput[formatters.write\nsegments → archivo]
        FormatChoice{formato?}
        WriteTXT[write_txt\nuna linea por segmento]
        WriteSRT[write_srt\nSubRip HH:MM:SS,mmm]
        WriteVTT[write_vtt\nWebVTT HH:MM:SS.mmm]
        WriteJSON[write_json\narray completo con logprob]
        BuildMeta[metadata.build\nUUID · source · engine · result · perf · quality]
        SaveMeta[metadata.save\nbase_name.meta.json]
        CheckConf{low_confidence\n> 0?}
        LogOK[/log.info OK\nduracion · inference · realtime · segs/]
        LogWarn[/log.warning\nN segs baja confianza/]
        Done([Transcripcion completa])
        ErrHandler[/log.error + exception/]
    end

    CommonPath --> MC_Start
    MC_Start --> EnsureModel
    EnsureModel -->|No| ModelLoad
    EnsureModel -->|Si — cached| Transcribe
    ModelLoad --> Transcribe
    Transcribe -->|Exception| ErrHandler
    Transcribe -->|Ok| MC_Stop
    MC_Stop --> WriteOutput
    WriteOutput --> FormatChoice
    FormatChoice -->|txt| WriteTXT
    FormatChoice -->|srt| WriteSRT
    FormatChoice -->|vtt| WriteVTT
    FormatChoice -->|json| WriteJSON
    WriteTXT & WriteSRT & WriteVTT & WriteJSON --> BuildMeta
    BuildMeta --> SaveMeta
    SaveMeta --> CheckConf
    CheckConf -->|Si| LogWarn
    CheckConf -->|No| LogOK
    LogWarn --> LogOK
    LogOK --> Done
```

---

## 4. Secuencia del watcher — happy path

Muestra el ciclo de vida completo del servicio: startup con procesamiento de
archivos preexistentes, luego el loop de eventos. El lazy model load aparece
diferenciado entre la primera llamada (carga efectiva) y las subsiguientes
(modelo ya en cache). El bloque `alt` cubre el camino de error por excepción.

```mermaid
sequenceDiagram
    participant FS as FileSystem
    participant Main as watcher.main
    participant Handler as WavHandler
    participant Loader as engine/loader
    participant Engine as Engine
    participant Collector as MetricsCollector
    participant Fmt as formatters
    participant MetaBuilder as metadata

    Main->>Main: yaml.safe_load(config.yaml)
    Main->>Loader: load_engine(impl_name, config)
    Loader->>Engine: Engine.__init__(impl_config)
    Engine-->>Loader: engine instance (model=None)
    Loader-->>Main: engine
    Main->>Handler: WavHandler(config, impl_name, engine)
    Handler-->>Main: handler ready

    Note over Main,Handler: Startup — archivos preexistentes
    Main->>Handler: _process_existing(watch_dir)
    loop cada .wav encontrado al startup
        Handler->>Handler: _process(audio_path)
    end

    Main->>FS: Observer.schedule(handler, input_dir)
    Main->>FS: Observer.start()
    Note over Main,FS: Watcher activo — loop time.sleep(1)

    FS-->>Handler: on_created(FileCreatedEvent)
    Handler->>Handler: filtrar .wav (case-insensitive)

    Note over Handler,Engine: Primera transcripcion — lazy load
    Handler->>Collector: MetricsCollector()
    Handler->>Collector: start()
    activate Collector
    Note right of Collector: hilo daemon: CPU + RSS cada 0.5s

    Handler->>Engine: transcribe(audio_path)
    activate Engine
    Engine->>Engine: _ensure_model() — model is None
    Engine->>Engine: WhisperModel(...) — carga modelo
    Note right of Engine: model_load_time registrado
    Engine->>Engine: model.transcribe(audio_path)
    Engine-->>Handler: TranscriptionResult
    deactivate Engine

    Handler->>Collector: stop()
    deactivate Collector
    Collector-->>Handler: ProcessingMetrics

    alt Transcripcion exitosa
        Handler->>Fmt: write(segments, fmt, output_path)
        Fmt-->>Handler: archivo escrito

        Handler->>MetaBuilder: build(audio_path, impl, result, metrics, ...)
        MetaBuilder-->>Handler: dict metadata
        Handler->>MetaBuilder: save(meta, metadata_dir, base_name)
        MetaBuilder-->>Handler: ruta .meta.json

        Handler->>Handler: log.info OK (duracion / realtime / segs)

        opt low_confidence_segments > 0
            Handler->>Handler: log.warning N segs baja confianza
        end
    else Exception en transcripcion
        Handler->>Handler: log.exception error procesando
    end

    Note over Handler,Engine: Siguiente archivo — modelo ya cargado
    FS-->>Handler: on_created(FileCreatedEvent)
    Handler->>Engine: transcribe(audio_path)
    activate Engine
    Engine->>Engine: _ensure_model() — model is not None, return 0.0
    Engine->>Engine: model.transcribe(audio_path)
    Engine-->>Handler: TranscriptionResult (model_load_time=0.0)
    deactivate Engine
```

---

## 5. Estados del archivo transcrito

Cada archivo WAV que entra al sistema atraviesa estos estados. El estado
`Processing` es compuesto: contiene cuatro sub-estados secuenciales que reflejan
las cuatro responsabilidades del pipeline. Los estados terminales `Transcribed`
y `Failed` generan artefactos distintos; `Ignored` no produce ninguno.

```mermaid
stateDiagram-v2
    [*] --> Detected : evento on_created\no escaneo startup

    Detected --> Ignored : sufijo != .wav\n(case-insensitive)
    Detected --> Validated : sufijo == .wav

    Ignored --> [*]

    Validated --> Processing : _process() invocado

    state Processing {
        [*] --> ModelLoading
        ModelLoading --> Transcribing : modelo listo\n(cargado o cached)
        Transcribing --> Formatting : TranscriptionResult OK
        Formatting --> SavingMetadata : archivo de texto escrito

        state ModelLoading {
            [*] --> CheckCache
            CheckCache --> LoadFromDisk : model is None
            CheckCache --> CacheHit : model is not None
            LoadFromDisk --> [*] : model_load_time > 0
            CacheHit --> [*] : model_load_time = 0.0
        }
    }

    Processing --> Transcribed : SavingMetadata completo
    Processing --> Failed : Exception en cualquier sub-estado

    Transcribed --> [*]
    Failed --> [*]

    note right of Transcribed
        Genera dos artefactos:
        transcriptions/nombre.{fmt}
        metadata/nombre.meta.json
    end note

    note right of Failed
        Solo log.exception —
        no se genera ningun archivo
    end note

    note right of Ignored
        Sin artefactos.
        El watcher sigue activo.
    end note
```

---

## 6. Comparacion de engines

Posiciona los tres engines en dos ejes relevantes para la decisión de
implementación: velocidad de inferencia relativa y riqueza de métricas de
calidad disponibles. FasterWhisper domina en ambas dimensiones para CPU; el eje
de precisión de métricas refleja si el engine expone `avg_logprob`,
`no_speech_prob` y `language_probability`.

```mermaid
quadrantChart
    title Engines Whisper — Velocidad vs Precision de metricas
    x-axis Metricas limitadas --> Metricas completas
    y-axis Inferencia lenta --> Inferencia rapida
    quadrant-1 Optimo
    quadrant-2 Rapido pero ciego
    quadrant-3 Lento y ciego
    quadrant-4 Rico pero lento
    WhisperCpp: [0.15, 0.90]
    FasterWhisper: [0.85, 0.80]
    OpenAIWhisper: [0.65, 0.20]
```

Detalle de capacidades por engine:

```mermaid
graph LR
    subgraph FW["FasterWhisper — CTranslate2"]
        FW1["avg_logprob ✓"]
        FW2["no_speech_prob ✓"]
        FW3["language_probability ✓"]
        FW4["VAD Filter ✓"]
        FW5["GPU cuda ✓"]
        FW6["Timestamps: segundos"]
    end

    subgraph OW["OpenAIWhisper — PyTorch"]
        OW1["avg_logprob ✓"]
        OW2["no_speech_prob ✓"]
        OW3["language_probability — None"]
        OW4["VAD Filter ✗"]
        OW5["GPU cuda ✓"]
        OW6["Timestamps: segundos"]
    end

    subgraph WC["WhisperCpp — GGML/C++"]
        WC1["avg_logprob — 0.0"]
        WC2["no_speech_prob — 0.0"]
        WC3["language_probability — None"]
        WC4["VAD Filter ✗"]
        WC5["GPU ✗ — CPU only"]
        WC6["Timestamps: centisegundos / 100"]
    end
```

---

## 7. Decisiones de diseño

### Strategy Pattern — engine/

**Problema**: tres backends Whisper con APIs radicalmente distintas
(CTranslate2, PyTorch, GGML/C++), timestamps en unidades diferentes,
disponibilidad de métricas dispar, y necesidad de intercambiarlos sin tocar el
código de orquestación.

**Solución**: cada engine implementa la misma interfaz (`_ensure_model()` +
`transcribe() → TranscriptionResult`). La normalización ocurre dentro de cada
adapter: WhisperCppEngine divide centisegundos por 100, fija `avg_logprob=0.0`
y `no_speech_prob=0.0`, y devuelve `language_probability=None`. El resto del
sistema trabaja siempre con `TranscriptionResult`.

**Tradeoff**: el adapter WhisperCpp pierde información (métricas fijadas en
cero) a cambio de uniformidad. `quality.low_confidence_segments` siempre
reporta 0 con ese backend porque no hay logprob real. Esto está documentado
en config.yaml como limitación conocida.

---

### Factory + Registry — engine/loader.py y formatters.py

**Problema**: necesidad de seleccionar en runtime la clase concreta del engine
(entre tres) y la función de escritura (entre cuatro), sin condicionales
`if/elif` dispersos en el código de orquestación.

**Solución**: `_ENGINE_MAP` y `_WRITERS` son diccionarios que mapean strings a
clases/funciones. `load_engine()` y `write()` hacen un `dict.get()` y levantan
`ValueError` explícito si la clave no existe. Agregar un nuevo engine o formato
requiere solo registrar una entrada en el dict y no tocar nada más.

**Tradeoff**: la validación es en runtime, no en tiempo de import. Un typo en
`config.yaml` falla al arrancar el watcher, no antes. Aceptable porque el error
es claro e inmediato.

---

### Lazy Model Load — _ensure_model()

**Problema**: cargar un modelo Whisper grande (turbo, large-v3) toma entre 5 y
30 segundos dependiendo del hardware. Hacerlo en `__init__` bloquea el arranque
del watcher aunque no haya archivos pendientes. Hacerlo en cada `transcribe()`
destruye el rendimiento en el modo watcher.

**Solución**: el modelo se carga en la primera llamada a `transcribe()` mediante
`_ensure_model()`, que retorna `0.0` si el modelo ya está en memoria. El tiempo
de carga se propaga en `TranscriptionResult.model_load_time` para que los
metadatos lo registren fielmente. En `watcher.py` el engine es un singleton:
todas las transcripciones subsiguientes tienen `model_load_time=0.0`.

**Tradeoff**: la primera transcripción en un watcher recién iniciado tiene
latencia alta. Si el primer archivo llega inmediatamente al startup, el usuario
ve un delay antes del primer log de OK. Para uso interactivo con `transcribe.py`
este costo es inevitable y esperado.

---

### Observer Pattern — watcher.py + watchdog

**Problema**: el servicio necesita reaccionar a archivos nuevos sin polling
activo, respetar el ciclo de vida del proceso (Ctrl+C ordenado), y procesar los
archivos ya presentes al momento de arranque (race condition entre el scan
inicial y el inicio del observer).

**Solución**: `watchdog.Observer` maneja el evento `on_created` via
`WavHandler(FileSystemEventHandler)`. El arranque llama primero a
`_process_existing()` antes de `Observer.start()`, eliminando el race condition:
cualquier archivo presente al inicio se procesa sincrónicamente antes de
activar el listener. `KeyboardInterrupt` dispara `observer.stop()` + `join()`
para shutdown limpio.

**Tradeoff**: `_process_existing()` es bloqueante — el observer no está activo
mientras se procesan los archivos previos. Si hay muchos WAVs al startup, el
servicio no reacciona a nuevos archivos durante ese tiempo. Para el caso de uso
de reuniones (volumen bajo, archivos de minutos de duración) este tradeoff es
aceptable.

---

### Thread-Safe Metrics — MetricsCollector

**Problema**: medir CPU y memoria durante la inferencia requiere muestreo
concurrente — la inferencia bloquea el hilo principal durante segundos o
minutos.

**Solución**: `MetricsCollector` lanza un hilo daemon que usa
`threading.Event.wait(timeout=0.5)` como mecanismo de sleep interrumpible. El
evento `_stop_event` señaliza la terminación sin depender de `Thread.join()`
con timeout arbitrario. El primer sample de `cpu_percent()` es descartado
intencionalmente (psutil siempre retorna `0.0` en la primera llamada).

**Tradeoff**: el hilo daemon muere si el proceso termina abruptamente, pero en
ese caso los metadatos no se escriben de todas formas. La granularidad de 0.5s
da suficiente resolución para transcripciones de más de 10 segundos; para
archivos muy cortos el promedio puede ser de un solo sample.
