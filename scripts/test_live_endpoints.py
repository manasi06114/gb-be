"""Script to test all 13 API endpoints against a running backend server."""

import httpx

BASE_URL = "http://127.0.0.1:8000"

ENDPOINTS = [
    ("E1", "GET", "/api/health"),
    ("E2", "GET", "/api/meta"),
    ("E3", "GET", "/api/actuals?date_from=2026-01-15&date_to=2026-01-15"),
    ("E4", "GET", "/api/forecasts?date_from=2026-01-15&date_to=2026-01-15&limit=5"),
    ("E5", "GET", "/api/forecasts/latest?delivery_date=2026-01-15&cutoff=09:00"),
    ("E6", "GET", "/api/comparison?delivery_date=2026-01-15&cutoff=09:00"),
    ("E7", "GET", "/api/comparison/range?date_from=2026-01-14&date_to=2026-01-15&cutoff=09:00"),
    ("E8", "GET", "/api/metrics?date_from=2026-01-01&date_to=2026-01-31&cutoff=09:00"),
    ("E9", "GET", "/api/metrics/daily?date_from=2026-01-01&date_to=2026-01-31&cutoff=09:00"),
    ("E10", "GET", "/api/metrics/by-hour?date_from=2026-01-01&date_to=2026-01-31&cutoff=09:00"),
    (
        "E11",
        "GET",
        "/api/metrics/by-horizon?date_from=2026-01-01&date_to=2026-01-31&bucket_hours=3",
    ),
    (
        "E12",
        "GET",
        "/api/errors/distribution?date_from=2026-01-01&date_to=2026-01-31&cutoff=09:00&bins=10",
    ),
]


def run_checks() -> None:
    client = httpx.Client(base_url=BASE_URL, timeout=15.0)

    print(f"Connecting to {BASE_URL}...\n")
    all_passed = True

    for eid, method, path in ENDPOINTS:
        try:
            resp = client.request(method, path)
            status = resp.status_code
            ok = status == 200
            if not ok:
                all_passed = False
            status_str = f"PASS ({status})" if ok else f"FAIL ({status})"
            print(f"[{status_str}] {eid}: {method} {path}")
        except Exception as exc:
            all_passed = False
            print(f"[ERROR] {eid}: {method} {path} -> {exc}")

    # Test E13: Unauthorized response (expected 401)
    try:
        resp = client.post("/api/admin/refresh", headers={"Authorization": "Bearer invalid_token"})
        ok = resp.status_code == 401
        if not ok:
            all_passed = False
        status_str = f"PASS ({resp.status_code})" if ok else f"FAIL ({resp.status_code})"
        print(f"[{status_str}] E13: POST /api/admin/refresh (auth validation)")
    except Exception as exc:
        all_passed = False
        print(f"[ERROR] E13: POST /api/admin/refresh -> {exc}")

    print("\n" + ("=" * 40))
    if all_passed:
        print("ALL 13 ENDPOINTS VERIFIED SUCCESSFULLY!")
    else:
        print("SOME ENDPOINTS FAILED")


if __name__ == "__main__":
    run_checks()
