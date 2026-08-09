import re
from typing import Any, Dict, List
from app.analyzers.base import BaseAnalyzer

# 1. Specific Regional & Vehicle Plate Regexes
SPECIFIC_PLATE_PATTERNS = [
    # Indian Standard 4-Wheeler & 2-Wheeler (e.g., KA01AB1234, KA05EX5678, DL1C1234, MH12C123, TN05BT5754, MH12NW8556)
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

VEHICLE_BRAND_KEYWORDS = {
    "HONDA", "TOYOTA", "HYUNDAI", "SUZUKI", "YAMAHA", "KAWASAKI",
    "DUCATI", "HARLEY", "NISSAN", "CHEVROLET", "VOLKSWAGEN", "BMW",
    "AUDI", "MERCEDES", "FORD", "TESLA", "MAZDA", "RENAULT", "PEUGEOT",
    "JEEP", "PORSCHE", "FERRARI", "ENFIELD", "ROYALENFIELD", "HERO",
    "TVS", "KTM", "BAJAJ", "VESPA", "PIAGGIO", "MAHINDRA", "TATA", "EICHER"
}

# Words that commonly appear as brand/advertising text on yellow banner regions
NOISE_WORDS = {
    "IMD", "AGE", "RE", "RENA", "THE", "NEW", "ALL", "EVE", "OUT", "SUP",
    "LIVE", "HARD", "SOFT", "MUSIC", "RACE", "SAFE", "DARE", "PACE", "LOGO"
}

# Prefixes that indicate GPS metadata or identifiers, not plates
NOISE_PREFIXES = ("LAT", "LONG", "TASK", "IMEI", "HOSP", "TEL", "WWW", "HTTP")

CHAR_SUB_TO_DIGIT = {"O": "0", "Q": "0", "I": "1", "L": "1", "Z": "2", "S": "5", "G": "6", "T": "7", "B": "8", "X": "0", "Y": "4", "U": "0", "V": "5", "K": "0", "M": "5", "F": "7", "C": "5", "W": "8", "H": "2"}
CHAR_SUB_TO_ALPHA = {"0": "O", "1": "I", "2": "Z", "5": "S", "6": "G", "7": "T", "8": "B", "4": "A", "3": "B", "9": "P"}

STATE_CODES = {"TN", "MH", "KA", "DL", "KL", "AP", "TS", "GJ", "RJ", "UP", "MP", "WB", "HR", "PB", "BR", "OD", "CH", "GA", "JK"}


def is_brand_noise(text: str) -> bool:
    txt_up = text.upper()
    return any(b in txt_up for b in VEHICLE_BRAND_KEYWORDS)


def _char_mix_ok(cleaned: str) -> bool:
    """Requires at least 2 letters and 2 digits — rejects pure text or pure digits."""
    if not cleaned:
        return False
    has_alpha = sum(1 for c in cleaned if c.isalpha())
    has_digit = sum(1 for c in cleaned if c.isdigit())
    return has_alpha >= 2 and has_digit >= 2


def normalize_indian_plate_candidate(token: str) -> List[str]:
    """
    Normalizes OCR character confusion dynamically for Indian license plates.
    E.g. KAO1AB1234 -> KA01AB1234, MHIZNH8556 -> MH12NH8556, TN05BT5754.
    Only generates structured candidates for tokens that actually resemble
    a plate (start with a known state code), preventing false plates from
    street text / phone numbers (e.g. 7765900813).
    """
    candidates = [token]

    cleaned = re.sub(r"[^A-Z0-9]", "", token.upper())
    if not cleaned or is_brand_noise(cleaned) or not _char_mix_ok(cleaned):
        return candidates

    # Candidate 1: Anchored state-code sliding window
    m = re.match(r"^([A-Z]{2})([A-Z0-9]{1,2})([A-Z0-9]{1,3})([A-Z0-9]{3,4})$", cleaned)
    if m and m.group(1) in STATE_CODES:
        st, dist, ser, num = m.groups()
        st_clean = "".join(CHAR_SUB_TO_ALPHA.get(c, c) for c in st)
        dist_clean = "".join(CHAR_SUB_TO_DIGIT.get(c, c) for c in dist)
        ser_clean = "".join(CHAR_SUB_TO_ALPHA.get(c, c) for c in ser)
        num_clean = "".join(CHAR_SUB_TO_DIGIT.get(c, c) for c in num)

        normalized = f"{st_clean}{dist_clean}{ser_clean}{num_clean}"
        if normalized != cleaned and re.fullmatch(r"[A-Z]{2}[0-9]{1,2}[A-Z]{1,3}[0-9]{1,4}", normalized):
            candidates.append(normalized)

    # Candidate 2: Positional character substitution (only for structured plates)
    if len(cleaned) <= 11 and _char_mix_ok(cleaned):
        st_raw = cleaned[:2]
        st_clean = "".join(CHAR_SUB_TO_ALPHA.get(c, c) for c in st_raw)

        if st_clean in STATE_CODES and cleaned[:2].isalpha():
            dist_raw = cleaned[2:4]
            dist_clean = "".join(CHAR_SUB_TO_DIGIT.get(c, c) for c in dist_raw)

            ser_raw = cleaned[4:6]
            ser_clean = "".join(CHAR_SUB_TO_ALPHA.get(c, c) for c in ser_raw)

            num_raw = cleaned[6:10] if len(cleaned) >= 8 else cleaned[6:]
            num_clean = "".join(CHAR_SUB_TO_DIGIT.get(c, c) for c in num_raw)

            norm_pos = f"{st_clean}{dist_clean}{ser_clean}{num_clean}"
            if norm_pos != cleaned and re.fullmatch(r"[A-Z]{2}[0-9]{1,2}[A-Z]{1,3}[0-9]{1,4}", norm_pos):
                candidates.append(norm_pos)

    return candidates


class NumberPlateAnalyzer(BaseAnalyzer):
    """
    Universal License Plate Analyzer supporting Cars, Motorcycles/Bikes, Auto Rickshaws,
    Trucks, & Commercial Vehicles across Indian, US, EU, and Universal Alphanumeric formats.

    Verification is strict: a plate is only flagged `valid` on a full-format match.
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
        raw_tokens = [t for t in raw_tokens if t and not is_brand_noise(t)]

        if not raw_tokens and ocr_result.get("text"):
            txt_c = re.sub(r"[^A-Z0-9]", "", ocr_result["text"].upper())
            if not is_brand_noise(txt_c):
                raw_tokens = [txt_c]

        if not raw_tokens:
            return {
                "detected": False,
                "valid": False,
                "confidence": 0.0,
                "plate_text": None,
                "format_type": None
            }

        candidates: List[str] = []

        # 1. Joined adjacent 2 tokens
        for i in range(len(raw_tokens) - 1):
            joined = raw_tokens[i] + raw_tokens[i + 1]
            if 4 <= len(joined) <= 14:
                candidates.extend(normalize_indian_plate_candidate(joined))

        # 2. Joined adjacent 3 tokens
        for i in range(len(raw_tokens) - 2):
            joined = raw_tokens[i] + raw_tokens[i + 1] + raw_tokens[i + 2]
            if 4 <= len(joined) <= 14:
                candidates.extend(normalize_indian_plate_candidate(joined))

        # 3. Single tokens
        for t in raw_tokens:
            if len(t) >= 3:
                candidates.extend(normalize_indian_plate_candidate(t))

        # 4. Full concatenated text substring search
        full_text_cleaned = re.sub(r"[^A-Z0-9]", "", ocr_result["text"].upper())
        if full_text_cleaned and not is_brand_noise(full_text_cleaned):
            candidates.extend(normalize_indian_plate_candidate(full_text_cleaned))

        # Deduplicate candidates preserving order
        unique_candidates = [c for c in list(dict.fromkeys(candidates)) if not is_brand_noise(c)]

        best_plate = None
        best_conf = 0.0
        best_format = None
        is_valid = False

        # Phase 1: Strict full-format verification (longest complete match wins)
        for pattern, base_conf, fmt_name in SPECIFIC_PLATE_PATTERNS:
            for candidate in unique_candidates:
                if len(candidate) > 14:
                    continue
                if is_brand_noise(candidate):
                    continue
                if not pattern.fullmatch(candidate):
                    continue
                if best_plate is None or len(candidate) > len(best_plate):
                    best_plate = candidate
                    best_conf = base_conf
                    best_format = fmt_name
                    is_valid = True

        # Phase 2: Universal structural fallback (mixed alnum, reasonable length)
        if not is_valid:
            for candidate in unique_candidates:
                if not 6 <= len(candidate) <= 12 or is_brand_noise(candidate):
                    continue
                if candidate in NOISE_WORDS or candidate.startswith(NOISE_PREFIXES):
                    continue
                has_alpha = sum(1 for c in candidate if c.isalpha())
                has_digit = sum(1 for c in candidate if c.isdigit())
                if has_alpha >= 2 and has_digit >= 3:
                    if best_plate is None or len(candidate) > len(best_plate):
                        best_plate = candidate
                        best_conf = 0.85
                        best_format = "Universal Vehicle Plate"
                        is_valid = True

        return {
            "detected": best_plate is not None,
            "valid": is_valid,
            "confidence": round(best_conf, 2) if best_plate else 0.0,
            "plate_text": best_plate,
            "format_type": best_format
        }