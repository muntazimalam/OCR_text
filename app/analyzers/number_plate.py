import re
from typing import Any, Dict, List
from app.analyzers.base import BaseAnalyzer

# 1. Specific Regional & Vehicle Plate Regexes
SPECIFIC_PLATE_PATTERNS = [
    # Indian Standard 4-Wheeler & 2-Wheeler (e.g., KA01AB1234, DL1C1234, MH12C123)
    (re.compile(r"^[A-Z]{2}[0-9]{1,2}[A-Z]{1,3}[0-9]{1,4}$"), 0.95, "India Standard"),
    # Indian BH (Bharat) Series (e.g., 22BH1234AB)
    (re.compile(r"^[0-9]{2}BH[0-9]{4}[A-Z]{1,2}$"), 0.95, "India BH Series"),
    # European / UK Standard (e.g., AB12CDE, ABC123, B1234AB)
    (re.compile(r"^[A-Z]{2}[0-9]{2}[A-Z]{3}$"), 0.90, "EU/UK Standard"),
    (re.compile(r"^[A-Z]{3}[0-9]{3}$"), 0.88, "EU Standard"),
    (re.compile(r"^[A-Z]{1,2}[0-9]{1,4}[A-Z]{1,3}$"), 0.88, "EU/Intl Standard"),
    # US / North American Standard (e.g., 7ABC123, 1ABC234, ABC1234)
    (re.compile(r"^[0-9][A-Z]{3}[0-9]{3}$"), 0.88, "US Standard"),
    (re.compile(r"^[A-Z]{3}[0-9]{4}$"), 0.88, "US Standard"),
]

# Vehicle brand words to filter out noise
VEHICLE_BRAND_KEYWORDS = {
    "HONDA", "TOYOTA", "HYUNDAI", "SUZUKI", "YAMAHA", "KAWASAKI",
    "DUCATI", "HARLEY", "NISSAN", "CHEVROLET", "VOLKSWAGEN", "BMW",
    "AUDI", "MERCEDES", "FORD", "TESLA", "MAZDA", "RENAULT", "PEUGEOT",
    "JEEP", "PORSCHE", "FERRARI", "ENFIELD", "ROYALENFIELD", "HERO",
    "TVS", "KTM", "BAJAJ", "VESPA", "PIAGGIO", "MAHINDRA", "TATA", "EICHER"
}


class NumberPlateAnalyzer(BaseAnalyzer):
    """
    Universal License Plate Analyzer supporting Cars, Motorcycles/Bikes, Trucks, & Commercial Vehicles
    across Indian, US, EU, and Universal Alphanumeric formats.
    """
    def analyze(self, image_path: str, file_bytes: bytes, ocr_result: Dict[str, Any] = None) -> Dict[str, Any]:
        if not ocr_result or not ocr_result.get("text"):
            return {
                "detected": False,
                "valid": False,
                "confidence": 0.0,
                "plate_text": None,
                "format_type": None
            }

        detections = ocr_result.get("detections", [])
        raw_tokens = [re.sub(r"[^A-Z0-9]", "", item.get("text", "").upper()) for item in detections]
        raw_tokens = [t for t in raw_tokens if t and t not in VEHICLE_BRAND_KEYWORDS]

        # Build Candidate Combinations (Individual OCR tokens + Merged adjacent tokens for 2-line bike plates)
        candidates: List[str] = []

        # Single tokens
        for t in raw_tokens:
            if len(t) >= 4:
                candidates.append(t)

        # Joined adjacent 2 tokens (handles motorcycle 2-line plates e.g. "KA05" + "EX5678" -> "KA05EX5678")
        for i in range(len(raw_tokens) - 1):
            joined = raw_tokens[i] + raw_tokens[i + 1]
            if 5 <= len(joined) <= 12:
                candidates.append(joined)

        # Full concatenated text substring search
        full_text_cleaned = re.sub(r"[^A-Z0-9]", "", ocr_result["text"].upper())
        if full_text_cleaned and full_text_cleaned not in candidates:
            candidates.append(full_text_cleaned)

        best_plate = None
        best_conf = 0.0
        best_format = None
        is_valid = False

        # Phase 1: Test against Specific Regional & Standard Patterns
        for candidate in candidates:
            for pattern, base_conf, fmt_name in SPECIFIC_PLATE_PATTERNS:
                if pattern.match(candidate):
                    best_plate = candidate
                    best_conf = base_conf
                    best_format = fmt_name
                    is_valid = True
                    break
                # Substring search if candidate is long
                match = pattern.search(candidate)
                if match:
                    best_plate = match.group(0)
                    best_conf = base_conf * 0.95
                    best_format = fmt_name
                    is_valid = True
                    break
            if is_valid:
                break

        # Phase 2: Universal Fallback Heuristic (for any Car, Bike, Truck plate format worldwide)
        if not is_valid:
            for candidate in candidates:
                if 5 <= len(candidate) <= 10:
                    has_alpha = any(c.isalpha() for c in candidate)
                    has_digit = any(c.isdigit() for c in candidate)
                    if has_alpha and has_digit and candidate not in VEHICLE_BRAND_KEYWORDS:
                        best_plate = candidate
                        best_conf = 0.75
                        best_format = "Universal Vehicle Plate"
                        is_valid = True
                        break

        return {
            "detected": best_plate is not None,
            "valid": is_valid,
            "confidence": round(best_conf, 2) if best_plate else 0.0,
            "plate_text": best_plate,
            "format_type": best_format
        }
