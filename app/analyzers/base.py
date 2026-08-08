from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseAnalyzer(ABC):
    @abstractmethod
    def analyze(self, image_path: str, file_bytes: bytes) -> Dict[str, Any]:
        """
        Executes analysis on image.
        Returns dictionary of metrics and status.
        """
        pass
