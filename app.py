from flask import Flask, jsonify
import requests
import time
import os
from datetime import datetime, timezone


app = Flask(__name__)

# Have I Been Pwned API URL
HIBP_API_URL = "https://haveibeenpwned.com/api/v3/breaches"

# Config vars
APP_NAME = os.getenv("APP_NAME", "azure-release-verifier-target")
APP_VERSION = os.getenv("APP_VERSION", "0.1.0")
APP_ENV = os.getenv("APP_ENV", "dev")


# Simple in-memory TTL cache settings
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "1800"))  # default: 30 minutes
REQUEST_TIMEOUT_SECONDS = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "10"))

# Cache state (in-memory; resets on app restart)
_cached_breaches = None
_cached_at_epoch = 0


def _cache_is_fresh() -> bool:
    return _cached_breaches is not None and (time.time() - _cached_at_epoch) < CACHE_TTL_SECONDS

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@app.route("/version", methods=["GET"])
def version():
    return jsonify(
        {
            "app": APP_NAME,
            "version": APP_VERSION,
            "environment": APP_ENV,
            "utc": datetime.now(timezone.utc).isoformat(),
        }
    ), 200


@app.route("/ready", methods=["GET"])
def ready():
    global _cached_breaches, _cached_at_epoch

    # Ready if we already have any cached data (even if stale)
    if _cached_breaches is not None:
        return jsonify({"ready": True, "reason": "cache_available"}), 200

    # Otherwise, test if dependency is reachable quickly
    try:
        resp = requests.get(
            HIBP_API_URL,
            headers={"User-Agent": "Breach-Tracker-App"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return jsonify({"ready": True, "reason": "hibp_reachable"}), 200
    except Exception as e:
        return jsonify({"ready": False, "reason": "no_cache_and_hibp_unreachable", "error": str(e)}), 503

@app.route("/breaches", methods=["GET"])
def get_breaches():
    """
    Fetches all breaches from the Have I Been Pwned API and sorts them by ModifiedDate.

    Caching behavior:
      - If cache is fresh: return cached data (no HIBP call)
      - Otherwise: attempt HIBP call
          - On success: update cache and return fresh data
          - On failure: if cached exists, return stale cached data; else return 500
    """
    global _cached_breaches, _cached_at_epoch

    # 1) Serve from cache if fresh
    if _cache_is_fresh():
        age = int(time.time() - _cached_at_epoch)
        return jsonify(
            {
                "message": "Breaches returned from cache.",
                "cached": True,
                "stale": False,
                "cache_age_seconds": age,
                "cache_ttl_seconds": CACHE_TTL_SECONDS,
                "breaches": _cached_breaches,
            }
        ), 200

    # 2) Try live fetch
    try:
        response = requests.get(
            HIBP_API_URL,
            headers={"User-Agent": "Breach-Tracker-App"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()

        sorted_breaches = sorted(data, key=lambda x: x.get("ModifiedDate", ""), reverse=True)

        # Update cache
        _cached_breaches = sorted_breaches
        _cached_at_epoch = time.time()

        return jsonify(
            {
                "message": "Breaches fetched successfully.",
                "cached": False,
                "stale": False,
                "cache_ttl_seconds": CACHE_TTL_SECONDS,
                "breaches": sorted_breaches,
            }
        ), 200

    except Exception as e:
        # 3) Fallback to stale cache if available
        if _cached_breaches is not None:
            age = int(time.time() - _cached_at_epoch)
            return jsonify(
                {
                    "message": "HIBP fetch failed. Returning stale cached data.",
                    "cached": True,
                    "stale": True,
                    "cache_age_seconds": age,
                    "cache_ttl_seconds": CACHE_TTL_SECONDS,
                    "error": str(e),
                    "breaches": _cached_breaches,
                }
            ), 200

        return jsonify({"message": "An error occurred and no cache is available.", "error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)

