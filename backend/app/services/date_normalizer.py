import datetime
import re
from typing import Optional, Tuple

class DateNormalizer:
    @staticmethod
    def normalize_date(date_str: str, is_end: bool = False) -> Tuple[Optional[datetime.date], Optional[str]]:
        """
        Normalizes a date string from a resume into a Python date object.
        Returns a tuple: (normalized_date, original_end_date_str)
        For end dates like "Present", returns (today's date, "Present").
        """
        if not date_str:
            return (datetime.date.today() if is_end else None, None)

        date_clean = date_str.strip().lower()

        if any(p in date_clean for p in ("present", "current", "now")):
            return (datetime.date.today(), "Present" if is_end else None)

        MONTH_MAP = {
            "january": 1, "february": 2, "march": 3, "april": 4,
            "may": 5, "june": 6, "july": 7, "august": 8,
            "september": 9, "october": 10, "november": 11, "december": 12,
            "jan": 1, "feb": 2, "mar": 3, "apr": 4,
            "jun": 6, "jul": 7, "aug": 8, "sep": 9,
            "oct": 10, "nov": 11, "dec": 12,
        }

        year_match = re.search(r"\b(19|20)\d{2}\b", date_str)
        if not year_match:
            return (datetime.date.today() if is_end else None, None)
            
        year = int(year_match.group(0))

        month = None
        for m_name in sorted(MONTH_MAP, key=len, reverse=True):
            if re.search(r"\b" + re.escape(m_name) + r"\b", date_clean):
                month = MONTH_MAP[m_name]
                break

        if month is None:
            year_str = year_match.group(0)
            for token in re.findall(r"\b(\d{1,2})\b", date_str):
                if token not in (year_str, str(year)):
                    m_val = int(token)
                    if 1 <= m_val <= 12:
                        month = m_val
                        break

        if month is None:
            month = 12 if is_end else 1

        try:
            return (datetime.date(year, month, 1), date_str.strip() if is_end else None)
        except ValueError:
            return (None, None)
