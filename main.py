from datetime import datetime, timedelta, timezone
from threading import Lock

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from scraper import SOURCE_PAGE_URL, extract_economy_data, inspect_cbsl


app = FastAPI(
    title="Sri Lanka Economy API",
    description=(
        "Sri Lanka macroeconomic snapshot indicators "
        "collected from the Central Bank of Sri Lanka (CBSL)."
    ),
    version="2.0.0",
)


# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


CACHE_DURATION = timedelta(minutes=15)

cache = {
    "data": None,
    "updated_at": None,
}

cache_lock = Lock()


def get_economy_data(force_refresh: bool = False):
    with cache_lock:
        now = datetime.now(timezone.utc)

        if not force_refresh and cache["data"] is not None:
            age = now - cache["updated_at"]
            if age < CACHE_DURATION:
                return cache["data"]

        new_data = extract_economy_data()

        if new_data.get("status") == "success":
            cache["data"] = new_data
            cache["updated_at"] = now
            return new_data

        # Use previously retrieved data if available
        if cache["data"] is not None:
            fallback = dict(cache["data"])
            fallback["status"] = "stale"
            fallback["warning"] = (
                "The source could not be refreshed. "
                "Showing previously retrieved data."
            )
            return fallback

        raise HTTPException(
            status_code=502,
            detail=new_data.get(
                "message",
                "Unable to retrieve source data.",
            ),
        )


def _indicator_response(key: str):
    snapshot = get_economy_data()
    return {
        "status": snapshot["status"],
        "source": snapshot["source"],
        "source_url": snapshot["source_url"],
        "retrieved_at": snapshot.get("retrieved_at"),
        "data": snapshot["indicators"][key],
    }


@app.get("/")
def home():
    return {
        "name": "Sri Lanka Economy API",
        "version": "2.0.0",
        "status": "running",
        "source": "Central Bank of Sri Lanka (CBSL)",
        "source_url": SOURCE_PAGE_URL,
        "documentation": "/docs",
        "endpoints": [
            "/api/economy",
            "/api/inflation",
            "/api/area",
            "/api/economic-growth",
            "/api/exchange-rate",
            "/api/policy-rate",
            "/api/interest-rates",
            "/api/unemployment-rate",
            "/api/population",
            "/api/per-capita-income",
            "/api/refresh",
            "/api/debug-source",
        ],
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/economy")
def economy():
    return get_economy_data()


@app.get("/api/inflation")
def inflation():
    return _indicator_response("inflation")


@app.get("/api/area")
def area():
    return _indicator_response("area")


@app.get("/api/economic-growth")
def economic_growth():
    return _indicator_response("economic_growth")


@app.get("/api/exchange-rate")
def exchange_rate():
    return _indicator_response("exchange_rate")


@app.get("/api/policy-rate")
def policy_rate():
    return _indicator_response("policy_rate")


@app.get("/api/interest-rates")
def interest_rates():
    return _indicator_response("interest_rates")


@app.get("/api/unemployment-rate")
def unemployment_rate():
    return _indicator_response("unemployment_rate")


@app.get("/api/population")
def population():
    return _indicator_response("mid_year_population")


@app.get("/api/per-capita-income")
def per_capita_income():
    return _indicator_response("per_capita_income")


@app.post("/api/refresh")
def refresh():
    data = get_economy_data(force_refresh=True)
    return {
        "message": "Refresh completed",
        "status": data["status"],
        "retrieved_at": data.get("retrieved_at"),
    }


@app.get("/api/debug-source")
def debug_source():
    return inspect_cbsl()
