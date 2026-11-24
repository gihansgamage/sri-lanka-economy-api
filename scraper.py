
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone


SOURCE_URL = "https://economynext.com/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/130.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9"
}


def normalize(value):
    return " ".join(value.split()).strip()


def extract_table_rows(table):
    """Extract headers and rows from an HTML table."""

    rows = []

    for tr in table.find_all("tr"):
        cells = tr.find_all(["th", "td"])

        values = [
            normalize(cell.get_text(" ", strip=True))
            for cell in cells
        ]

        if values and any(values):
            rows.append(values)

    return rows


def classify_table(rows):
    """Identify the market data table."""

    text = " ".join(
        cell.lower()
        for row in rows
        for cell in row
    )

    if "s&p sl20" in text or "cse all share" in text:
        return "stocks"

    if (
        "3-m bill" in text
        or "6-m bill" in text
        or "12-m bill" in text
        or "3-yr bond" in text
    ):
        return "bonds"

    if "overnight money" in text or "gilt repo" in text:
        return "money"

    if (
        "us dollar" in text
        or "uk pound" in text
        or "aus dollar" in text
    ):
        return "forex"

    if (
        "indian rupee" in text
        or "korean won" in text
        or "saudi riyal" in text
        or "oman rial" in text
    ):
        return "asia_forex"

    return None


def rows_to_records(rows):
    """Convert table rows into structured JSON records."""

    if len(rows) < 2:
        return []

    headers = [
        normalize(item).lower()
        for item in rows[0]
    ]

    records = []

    for row in rows[1:]:

        if len(row) < 2:
            continue

        record = {
            "name": row[0]
        }

        for index, value in enumerate(row[1:], start=1):

            if index < len(headers):
                key = headers[index]
            else:
                key = f"value_{index}"

            record[key] = value

        records.append(record)

    return records


def extract_economy_data():

    try:

        response = requests.get(
            SOURCE_URL,
            headers=HEADERS,
            timeout=30
        )

        response.raise_for_status()

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        tables = soup.find_all("table")

        result = {
            "source": SOURCE_URL,
            "source_name": "EconomyNext",
            "retrieved_at": datetime.now(
                timezone.utc
            ).isoformat(),
            "status": "success",
            "forex": [],
            "asia_forex": [],
            "stocks": [],
            "bonds": [],
            "money": []
        }

        seen = set()

        for table in tables:

            rows = extract_table_rows(table)

            if not rows:
                continue

            category = classify_table(rows)

            if category is None:
                continue

            # Avoid duplicate responsive tables
            signature = (
                category,
                tuple(tuple(row) for row in rows)
            )

            if signature in seen:
                continue

            seen.add(signature)

            records = rows_to_records(rows)

            if records:
                result[category] = records

        # Check whether useful data was found
        total_records = sum(
            len(result[key])
            for key in [
                "forex",
                "asia_forex",
                "stocks",
                "bonds",
                "money"
            ]
        )

        if total_records == 0:
            return {
                "status": "error",
                "source": SOURCE_URL,
                "message": (
                    "No recognized market tables found. "
                    "The website structure may have changed."
                )
            }

        result["total_records"] = total_records

        return result

    except requests.RequestException as error:

        return {
            "status": "error",
            "source": SOURCE_URL,
            "message": str(error)
        }

    except Exception as error:

        return {
            "status": "error",
            "source": SOURCE_URL,
            "message": str(error)
        }
