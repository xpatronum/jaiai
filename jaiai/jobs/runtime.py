import threading

from jaiai.configuring.prime import Config
from jaiai.modeling.mask import ILanguageModel
from jaiai.processing.prime import INFERProcessor
from jaiai.processing.tokenizer import ITokenizer
from jaiai.tooling.stl import _other_props, initialize_device_settings


class GlobalModelRuntime:
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self.model_name_or_path = Config.api["clustering"]["embedder"]["model_name_or_path"]  # type: ignore
        self.device = None
        self.model = None
        self.tokenizer = None
        self.processor = None
        self._initialized = False

    @property
    def backend(self):
        return dict(model=self.model, processor=self.processor, device=self.device)

    def constructor(self):
        if self._initialized:
            return
        self.tokenizer = ITokenizer.from_pretrained(self.model_name_or_path)
        self.processor = INFERProcessor(
            tokenizer=self.tokenizer,
            max_seq_len=512,
            content_field="text",
            prefix="query:",
        )

        device, _ = initialize_device_settings(_other_props(Config.api, include_keys=["use_gpu", "gpu_props"]))  # type: ignore
        self.device = device
        # Загрузка модели на `device`
        self.model = ILanguageModel.load(self.model_name_or_path, device=device)
        self._initialized = True

    @classmethod
    def call(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
                    cls._instance.constructor()
        return cls._instance
