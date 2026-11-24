
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone, timedelta
from threading import Lock

from scraper import extract_economy_data


app = FastAPI(
    title="Sri Lanka Economy API",
    description=(
        "Economic and financial market indicators "
        "collected from EconomyNext."
    ),
    version="1.0.0"
)


# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


CACHE_DURATION = timedelta(minutes=15)

cache = {
    "data": None,
    "updated_at": None
}

cache_lock = Lock()


def get_economy_data(force_refresh=False):

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
                "Unable to retrieve source data."
            )
        )


@app.get("/")
def home():

    return {
        "name": "Sri Lanka Economy API",
        "version": "1.0.0",
        "status": "running",
        "source": "EconomyNext",
        "documentation": "/docs"
    }


@app.get("/health")
def health():

    return {
        "status": "healthy",
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat()
    }


@app.get("/api/economy")
def economy():

    return get_economy_data()


@app.get("/api/forex")
def forex():

    return {
        "source": "EconomyNext",
        "data": get_economy_data()["forex"]
    }


@app.get("/api/asia-forex")
def asia_forex():

    return {
        "source": "EconomyNext",
        "data": get_economy_data()["asia_forex"]
    }


@app.get("/api/stocks")
def stocks():

    return {
        "source": "EconomyNext",
        "data": get_economy_data()["stocks"]
    }


@app.get("/api/bonds")
def bonds():

    return {
        "source": "EconomyNext",
        "data": get_economy_data()["bonds"]
    }


@app.get("/api/money")
def money():

    return {
        "source": "EconomyNext",
        "data": get_economy_data()["money"]
    }


@app.post("/api/refresh")
def refresh():

    data = get_economy_data(force_refresh=True)

    return {
        "message": "Refresh completed",
        "status": data["status"],
        "retrieved_at": data.get("retrieved_at")
    }
