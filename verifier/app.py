import os
import json
import uuid
import time
import datetime
from flask import Flask, jsonify
import requests

from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

app = Flask(__name__)

def utc_now_iso():
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

def get_env_int(name: str, default: int) -> int:
    val = os.getenv(name, "").strip()
    if not val:
        return default
    try:
        return int(val)
    except ValueError:
        return default

def build_blob_name(check_id: str) -> str:
    # YYYY/MM/DD/HHMMSSZ-<checkid>.json
    now = datetime.datetime.utcnow()
    prefix = now.strftime("%Y/%m/%d")
    stamp = now.strftime("%H%M%SZ")
    return f"{prefix}/{stamp}-{check_id}.json"

def get_container_client():
    storage_account = os.getenv("STORAGE_ACCOUNT_NAME")
    raw_container = os.getenv("RESULTS_RAW_CONTAINER", "results-raw")

    if not storage_account:
        raise RuntimeError("Missing STORAGE_ACCOUNT_NAME app setting")

    credential = DefaultAzureCredential(exclude_interactive_browser_credential=True)
    account_url = f"https://{storage_account}.blob.core.windows.net"
    svc = BlobServiceClient(account_url=account_url, credential=credential)
    return svc.get_container_client(raw_container)

@app.get("/health")
def health():
    return "ok", 200

@app.get("/version")
def version():
    return jsonify({
        "app_role": os.getenv("APP_ROLE", "verifier"),
        "app_env": os.getenv("APP_ENV", "dev"),
        "ts": utc_now_iso()
    }), 200

@app.post("/verify/breaches")
def verify_breaches():
    target_base = os.getenv("TARGET_BASE_URL", "").rstrip("/")
    timeout_s = get_env_int("REQUEST_TIMEOUT_SECONDS", 10)
    max_latency_ms = get_env_int("EXPECTED_MAX_LATENCY_MS", 1500)

    if not target_base:
        return jsonify({"error": "Missing TARGET_BASE_URL app setting"}), 500

    check_id = str(uuid.uuid4())
    endpoint = "/breaches"
    url = f"{target_base}{endpoint}"

    errors = []
    status_code = None
    timeout = False

    start = time.perf_counter()
    try:
        resp = requests.get(url, timeout=timeout_s)
        status_code = resp.status_code

        if status_code != 200:
            errors.append(f"Expected 200, got {status_code}")

        try:
            data = resp.json()
        except Exception as e:
            errors.append(f"Invalid JSON: {e}")
            data = None

        if data is not None and not isinstance(data, (list, dict)):
            errors.append(f"Unexpected JSON type: {type(data).__name__}")

    except requests.exceptions.Timeout:
        timeout = True
        errors.append(f"Timeout after {timeout_s}s")
    except Exception as e:
        errors.append(f"Request failed: {e}")
    finally:
        latency_ms = int((time.perf_counter() - start) * 1000)

    if latency_ms > max_latency_ms:
        errors.append(f"Latency {latency_ms}ms exceeded threshold {max_latency_ms}ms")

    passed = (len(errors) == 0) and (not timeout) and (status_code == 200)

    result = {
        "timestamp_utc": utc_now_iso(),
        "check_id": check_id,
        "verifier": {
            "app_role": os.getenv("APP_ROLE", "verifier"),
            "app_env": os.getenv("APP_ENV", "dev"),
        },
        "target": {
            "base_url": target_base,
            "endpoint": endpoint
        },
        "http": {
            "status_code": status_code,
            "timeout": timeout
        },
        "validation": {
            "passed": passed,
            "errors": errors
        },
        "performance": {
            "latency_ms": latency_ms,
            "max_latency_ms": max_latency_ms
        },
        "storage": {
            "account": os.getenv("STORAGE_ACCOUNT_NAME"),
            "container": os.getenv("RESULTS_RAW_CONTAINER", "results-raw"),
            "blob_name": None
        }
    }

    # Upload evidence
    try:
        container_client = get_container_client()
        blob_name = build_blob_name(check_id)
        result["storage"]["blob_name"] = blob_name

        payload = json.dumps(result, indent=2).encode("utf-8")
        container_client.get_blob_client(blob_name).upload_blob(payload, overwrite=True)

    except Exception as e:
        result["validation"]["passed"] = False
        result["validation"]["errors"].append(f"Storage write failed: {e}")

    return jsonify(result), (200 if result["validation"]["passed"] else 500)

