from flask import Flask, jsonify
import requests
import time
import os

app = Flask(__name__)

# Have I Been Pwned API URL
HIBP_API_URL = "https://haveibeenpwned.com/api/v3/breaches"

# Simple in-memory TTL cache settings
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "1800"))  # default: 30 minutes
REQUEST_TIMEOUT_SECONDS = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "10"))

# Cache state (in-memory; resets on app restart)
_cached_breaches = None
_cached_at_epoch = 0


def _cache_is_fresh() -> bool:
    return _cached_breaches is not None and (time.time() - _cached_at_epoch) < CACHE_TTL_SECONDS


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

