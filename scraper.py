import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup

SOURCE_PAGE_URL = "https://www.cbsl.gov.lk/en/sri-lanka-economy-snapshot"
SOURCE_URL = "https://www.cbsl.gov.lk/cbsl_custom/param/snap-en.php"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": SOURCE_PAGE_URL,
}


def _clean_text(text: str) -> str:
    """Normalize non-breaking spaces, newlines, and repeated whitespace."""
    normalized = text.replace("\xa0", " ")
    return re.sub(r"\s+", " ", normalized).strip()


def _parse_number(text: str) -> Optional[float]:
    """Extract the first numeric value (int or float) from a string."""
    match = re.search(r"-?\d[\d,]*(?:\.\d+)?", text)
    if not match:
        return None
    raw = match.group(0).replace(",", "")
    try:
        return float(raw)
    except ValueError:
        return None


def _parse_int(text: str) -> Optional[int]:
    """Extract an integer value if whole, else None."""
    num = _parse_number(text)
    if num is None:
        return None
    return int(num) if num.is_integer() else None


def _get_card_lines(card) -> List[str]:
    """Return non-empty cleaned text lines from <p> tags inside a card."""
    if card is None:
        return []
    lines: List[str] = []
    for p in card.find_all("p"):
        text = _clean_text(p.get_text(" ", strip=True))
        if text:
            lines.append(text)
    return lines


def _get_card_heading(card, default: str) -> str:
    if card is None:
        return default
    h2 = card.find("h2")
    return _clean_text(h2.get_text(" ", strip=True)) if h2 else default


def _parse_inflation(card) -> Dict[str, Any]:
    lines = _get_card_lines(card)
    raw_value = lines[0] if len(lines) > 0 else None
    period = lines[1] if len(lines) > 1 else None

    index_name = None
    value = None
    if raw_value:
        value = _parse_number(raw_value)
        match = re.match(r"^(.*?)\s+(-?\d[\d,]*(?:\.\d+)?%?)$", raw_value)
        if match:
            index_name = match.group(1).strip()

    return {
        "label": _get_card_heading(card, "Inflation"),
        "index": index_name,
        "value": value,
        "raw_value": raw_value,
        "period": period,
    }


def _parse_area(card) -> Dict[str, Any]:
    lines = _get_card_lines(card)
    raw_value = lines[0] if len(lines) > 0 else None
    unit = lines[1] if len(lines) > 1 else None
    value = _parse_int(raw_value) if raw_value else None
    if value is None and raw_value:
        value = _parse_number(raw_value)

    return {
        "label": _get_card_heading(card, "Area"),
        "value": value,
        "raw_value": raw_value,
        "unit": unit,
    }


def _parse_economic_growth(card) -> Dict[str, Any]:
    lines = _get_card_lines(card)
    raw_value = lines[0] if len(lines) > 0 else None
    period = lines[1] if len(lines) > 1 else None

    return {
        "label": _get_card_heading(card, "Economic Growth"),
        "value": _parse_number(raw_value) if raw_value else None,
        "raw_value": raw_value,
        "unit": "%" if raw_value and "%" in raw_value else None,
        "period": period,
    }


def _parse_exchange_rate(card) -> Dict[str, Any]:
    lines = _get_card_lines(card)
    raw_value = lines[0] if len(lines) > 0 else None
    rate_type = lines[1] if len(lines) > 1 else None

    currency = None
    if raw_value:
        match = re.match(r"^([A-Za-z]+)\s+", raw_value)
        if match:
            currency = match.group(1)

    return {
        "label": "Exchange Rate",
        "currency": currency,
        "value": _parse_number(raw_value) if raw_value else None,
        "raw_value": raw_value,
        "type": rate_type,
    }


def _parse_policy_rate(card) -> Dict[str, Any]:
    lines = _get_card_lines(card)
    raw_value = lines[0] if len(lines) > 0 else None

    index_name = None
    value = None
    if raw_value:
        value = _parse_number(raw_value)
        match = re.match(r"^(.*?)\s+(-?\d[\d,]*(?:\.\d+)?%?)$", raw_value)
        if match:
            index_name = match.group(1).strip()

    return {
        "label": _get_card_heading(card, "Policy Rate"),
        "index": index_name,
        "value": value,
        "raw_value": raw_value,
    }


def _parse_interest_rates(card) -> Dict[str, Any]:
    lines = _get_card_lines(card)
    items: List[Dict[str, Any]] = []
    keyed: Dict[str, Dict[str, Any]] = {}

    for line in lines:
        match = re.match(r"^(.*?)\s+(-?\d[\d,]*(?:\.\d+)?%?)$", line)
        if match:
            name = match.group(1).strip()
            raw_val = match.group(2).strip()
            val = _parse_number(raw_val)
        else:
            name = line
            raw_val = None
            val = None

        entry = {
            "name": name,
            "value": val,
            "raw_value": raw_val,
        }
        items.append(entry)

        lower = name.lower()
        if "364" in lower:
            keyed["t_bill_364_days"] = entry
        elif "3 year" in lower:
            keyed["t_bond_3_year"] = entry
        elif "5 year" in lower:
            keyed["t_bond_5_year"] = entry

    result: Dict[str, Any] = {
        "label": _get_card_heading(card, "Interest Rates"),
        **keyed,
        "items": items,
    }
    return result


def _parse_unemployment_rate(card) -> Dict[str, Any]:
    lines = _get_card_lines(card)
    raw_value = lines[0] if len(lines) > 0 else None
    period = lines[1] if len(lines) > 1 else None

    return {
        "label": _get_card_heading(card, "Unemployment Rate"),
        "value": _parse_number(raw_value) if raw_value else None,
        "raw_value": raw_value,
        "unit": "%" if raw_value and "%" in raw_value else None,
        "period": period,
    }


def _parse_population(card) -> Dict[str, Any]:
    lines = _get_card_lines(card)
    raw_value = lines[0] if len(lines) > 0 else None

    unit = None
    if raw_value:
        match = re.match(r"^-?\d[\d,]*(?:\.\d+)?\s*(.+)$", raw_value)
        if match:
            unit = match.group(1).strip()

    return {
        "label": _get_card_heading(card, "Mid Year Population"),
        "value": _parse_number(raw_value) if raw_value else None,
        "raw_value": raw_value,
        "unit": unit,
    }


def _parse_per_capita_income(card) -> Dict[str, Any]:
    lines = _get_card_lines(card)
    lkr_raw = None
    usd_raw = None

    for line in lines:
        lower = line.lower()
        if lower.startswith("rs") or lower.startswith("lkr"):
            lkr_raw = line
        elif lower.startswith("usd") or "$" in lower:
            usd_raw = line

    return {
        "label": _get_card_heading(card, "Per Capita Income"),
        "lkr": _parse_int(lkr_raw) if lkr_raw else None,
        "lkr_raw": lkr_raw,
        "usd": _parse_int(usd_raw) if usd_raw else None,
        "usd_raw": usd_raw,
    }


def parse_cbsl_snapshot(html: str) -> Dict[str, Any]:
    """Parse CBSL economy snapshot HTML into structured indicator data."""
    soup = BeautifulSoup(html, "html.parser")

    return {
        "inflation": _parse_inflation(soup.find("div", class_="inflationsq")),
        "area": _parse_area(soup.find("div", class_="areasq")),
        "economic_growth": _parse_economic_growth(soup.find("div", class_="growthsq")),
        "exchange_rate": _parse_exchange_rate(soup.find("div", class_="exratesq")),
        "policy_rate": _parse_policy_rate(soup.find("div", class_="policyratesq")),
        "interest_rates": _parse_interest_rates(soup.find("div", class_="creditratesq")),
        "unemployment_rate": _parse_unemployment_rate(
            soup.find("div", class_="unemploymentsq")
        ),
        "mid_year_population": _parse_population(
            soup.find("div", class_="populationsq")
        ),
        "per_capita_income": _parse_per_capita_income(
            soup.find("div", class_="percapitasq")
        ),
    }


def extract_economy_data() -> Dict[str, Any]:
    """Fetch and parse Sri Lanka economy snapshot indicators from CBSL."""
    try:
        response = requests.get(SOURCE_URL, headers=HEADERS, timeout=30)
        response.raise_for_status()

        indicators = parse_cbsl_snapshot(response.text)

        return {
            "status": "success",
            "source": "Central Bank of Sri Lanka (CBSL)",
            "source_url": SOURCE_PAGE_URL,
            "data_url": SOURCE_URL,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "indicators": indicators,
        }
    except requests.RequestException as error:
        return {
            "status": "error",
            "message": f"Failed to fetch CBSL snapshot: {error}",
        }
    except Exception as error:
        return {
            "status": "error",
            "message": f"Failed to parse CBSL snapshot: {error}",
        }


def inspect_cbsl() -> Dict[str, Any]:
    """Inspect the raw CBSL snapshot iframe response for debugging."""
    try:
        response = requests.get(SOURCE_URL, headers=HEADERS, timeout=30)
        soup = BeautifulSoup(response.text, "html.parser")
        page_text = _clean_text(soup.get_text(" | ", strip=True))

        return {
            "http_status": response.status_code,
            "content_type": response.headers.get("Content-Type"),
            "html_size": len(response.text),
            "source_url": SOURCE_URL,
            "parsed_preview": parse_cbsl_snapshot(response.text),
            "page_text": page_text,
        }
    except requests.RequestException as error:
        return {
            "status": "error",
            "message": str(error),
        }
