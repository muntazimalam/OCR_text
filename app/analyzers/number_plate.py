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


CHAR_SUB_TO_DIGIT = {"O": "0", "Q": "0", "I": "1", "L": "1", "Z": "2", "S": "5", "G": "6", "T": "7", "B": "8"}
CHAR_SUB_TO_ALPHA = {"0": "O", "1": "I", "2": "Z", "5": "S", "6": "G", "7": "T", "8": "B"}


def normalize_indian_plate_candidate(token: str) -> List[str]:
    """
    Attempts to normalize OCR character confusion for Indian license plate formats.
    E.g. KAO1AB1234 -> KA01AB1234, MH12NAQUNEWITUH8556 -> MH12NA8556
    """
    candidates = [token]
    
    # Try sliding window extraction of Indian standard pattern [A-Z]{2}...[0-9]{4}
    # Standard format: State(2 letters) + District(1-2 digits) + Series(1-3 letters) + Number(1-4 digits)
    m = re.search(r"([A-Z0-9]{2})([A-Z0-9]{1,2})([A-Z0-9]{1,3})([A-Z0-9]{3,4})", token)
    if m:
        st, dist, ser, num = m.groups()
        # Clean state code (letters)
        st_clean = "".join(CHAR_SUB_TO_ALPHA.get(c, c) for c in st)
        # Clean district code (digits)
        dist_clean = "".join(CHAR_SUB_TO_DIGIT.get(c, c) for c in dist)
        # Clean series code (letters)
        ser_clean = "".join(CHAR_SUB_TO_ALPHA.get(c, c) for c in ser)
        # Clean number (digits)
        num_clean = "".join(CHAR_SUB_TO_DIGIT.get(c, c) for c in num)
        
        normalized = f"{st_clean}{dist_clean}{ser_clean}{num_clean}"
        if normalized not in candidates:
            candidates.append(normalized)

    return candidates


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

        # Build Candidate Combinations (Single, 2-adjacent, and 3-adjacent tokens)
        candidates: List[str] = []

        # Single tokens
        for t in raw_tokens:
            if len(t) >= 4:
                candidates.extend(normalize_indian_plate_candidate(t))

        # Joined adjacent 2 tokens (handles motorcycle 2-line plates e.g. "KA05" + "EX5678" -> "KA05EX5678")
        for i in range(len(raw_tokens) - 1):
            joined = raw_tokens[i] + raw_tokens[i + 1]
            if 5 <= len(joined) <= 14:
                candidates.extend(normalize_indian_plate_candidate(joined))

        # Joined adjacent 3 tokens (handles 3-segmented plates e.g. "DL" + "1C" + "1234" -> "DL1C1234")
        for i in range(len(raw_tokens) - 2):
            joined = raw_tokens[i] + raw_tokens[i + 1] + raw_tokens[i + 2]
            if 6 <= len(joined) <= 14:
                candidates.extend(normalize_indian_plate_candidate(joined))

        # Full concatenated text substring search
        full_text_cleaned = re.sub(r"[^A-Z0-9]", "", ocr_result["text"].upper())
        if full_text_cleaned:
            candidates.extend(normalize_indian_plate_candidate(full_text_cleaned))

        # Deduplicate candidates preserving order
        unique_candidates = list(dict.fromkeys(candidates))

        best_plate = None
        best_conf = 0.0
        best_format = None
        is_valid = False

        # Phase 1: Test against Specific Regional & Standard Patterns
        for candidate in unique_candidates:
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
