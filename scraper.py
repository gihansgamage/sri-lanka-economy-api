
import requests
from bs4 import BeautifulSoup

SOURCE_URL = "https://economynext.com/"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9"
}


def inspect_economynext():

    try:
        response = requests.get(
            SOURCE_URL,
            headers=HEADERS,
            timeout=30
        )

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        page_text = soup.get_text(
            separator=" | ",
            strip=True
        )

        tables = []

        for table in soup.find_all("table"):
            tables.append(
                table.get_text(" | ", strip=True)[:1000]
            )

        return {
            "http_status": response.status_code,
            "content_type": response.headers.get(
                "Content-Type"
            ),
            "html_size": len(response.text),
            "page_title": (
                soup.title.get_text(strip=True)
                if soup.title else None
            ),
            "html_table_count": len(tables),
            "table_samples": tables[:10],
            "keyword_checks": {
                "forex": "Forex" in page_text,
                "us_dollar": "US Dollar" in page_text,
                "stocks": "S&P SL20" in page_text,
                "bonds": "3-m bill" in page_text,
                "money": "Overnight Money" in page_text
            },
            "page_text_preview": page_text[:5000]
        }

    except requests.RequestException as error:

        return {
            "status": "error",
            "message": str(error)
        }
