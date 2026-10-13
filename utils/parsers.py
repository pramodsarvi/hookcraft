from datetime import datetime
import re
from typing import Optional, Union


def parse_compact_number(val: Union[int, float, str, None]) -> Optional[int]:
    """
    Parses human-readable metric strings commonly used on X and Instagram
    into exact integer representations.
    
    Examples:
        "12.4K" -> 12400
        "1.2M"  -> 1200000
        "1,432" -> 1432
        "42"    -> 42
        None    -> None
    """
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return int(val)

    clean_str = str(val).strip().replace(",", "").upper()
    if not clean_str or clean_str in {"N/A", "NONE", "-"}:
        return None

    # Handle multipliers (K, M, B)
    multipliers = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}
    for suffix, multiplier in multipliers.items():
        if clean_str.endswith(suffix):
            numeric_part = clean_str[:-1].strip()
            try:
                return int(float(numeric_part) * multiplier)
            except ValueError:
                return None

    # Try standard integer or float conversion
    try:
        return int(float(clean_str))
    except ValueError:
        # Fallback regex to find first numeric group
        match = re.search(r"(\d+(?:\.\d+)?)", clean_str)
        if match:
            try:
                return int(float(match.group(1)))
            except ValueError:
                return None
        return None


def clean_text_content(val: Optional[str]) -> Optional[str]:
    """Cleans extracted DOM/OCR text, normalizes spaces and breaks."""
    if not val:
        return None
    # Normalize multiple whitespace characters except newlines
    cleaned = re.sub(r"[ \t]+", " ", val)
    # Remove consecutive empty lines
    cleaned = re.sub(r"\n\s*\n+", "\n\n", cleaned)
    return cleaned.strip()
