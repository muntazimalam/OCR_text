from typing import Any, Dict
from app.analyzers.base import BaseAnalyzer

EDITING_SOFTWARE_KEYWORDS = [
    "photoshop", "gimp", "lightroom", "canva", "picsart",
    "snapseed", "affinity", "paint.net"
]


class TamperingAnalyzer(BaseAnalyzer):
    """
    Combines metadata hints, software flags, and noise indicators to detect suspicious editing.
    Note: Heuristic indication of potential editing, not absolute forensic proof.
    """
    def analyze(self, image_path: str, file_bytes: bytes, metadata_result: Dict[str, Any] = None) -> Dict[str, Any]:
        suspicious = False
        confidence = 0.0

        if metadata_result:
            software = (metadata_result.get("software") or "").lower()
            if any(kw in software for kw in EDITING_SOFTWARE_KEYWORDS):
                suspicious = True
                confidence = 0.85

        return {
            "suspicious_editing": suspicious,
            "confidence": round(confidence, 2)
        }
