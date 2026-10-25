# UK Wind Forecast Analysis Backend

A production-grade FastAPI backend serving UK national wind generation actuals, decision-time forecasts, and accuracy analytics (MAE, RMSE, bias) for January 2026 using Elexon BMRS data.

---

## Architecture Overview

Built on a **snapshot-first, layered architecture**:
- **Clients Layer (`app/clients`)**: Robust HTTP client for Elexon BMRS API (`FUELHH` and `WINDFOR` streams) with retry logic and date chunking.
- **Repository Layer (`app/repositories`)**: In-memory, thread-safe `DataRepository` loading pre-cached, cleaned Parquet snapshots.
- **Domain Layer (`app/domain`)**: Pure, testable computational logic with zero I/O or HTTP dependencies:
  - `decision_time`: Timezone-aware cutoff calculations (`Europe/London` to UTC).
  - `forecast_selector`: Strict decision-time selection enforcing **BR-1** (no future lookahead) and **BR-2** (latest forecast at or before cutoff).
  - `metrics`: Standard accuracy metrics (MAE, RMSE, bias, normalised MAE, percentiles).
  - `aggregations`: Heatmaps by day × hour, hourly profiles, lead-time horizon buckets, and error distributions.
- **Services Layer (`app/services`)**: Business workflow coordination, metric calculations, and uncertainty bands.
- **API Routers Layer (`app/api/routers`)**: Thin FastAPI routers handling parameter validation, dependency injection, and OpenAPI response formatting.

---

## Directory Structure

```
Backend/
├── app/
│   ├── api/
│   │   ├── deps.py               # FastAPI dependency injection
│   │   └── routers/              # E1 - E13 endpoint routers
│   ├── clients/
│   │   └── elexon_client.py      # Elexon BMRS API client
│   ├── core/
│   │   ├── config.py             # Pydantic Settings
│   │   ├── constants.py          # Metric definitions & resolutions
│   │   ├── errors.py             # AppError hierarchy & exception handlers
│   │   └── logging.py            # Structured logging & request middleware
│   ├── domain/
│   │   ├── aggregations.py       # Aggregation & distribution logic
│   │   ├── decision_time.py      # Cutoff time & timezone logic
│   │   ├── forecast_selector.py  # Latest-at-cutoff selection logic
│   │   └── metrics.py            # Accuracy metric calculations
│   ├── repositories/
│   │   └── data_repository.py    # Thread-safe in-memory Parquet cache
│   ├── schemas/                  # Pydantic request & response models
│   ├── services/                 # Workflow & business services
│   └── main.py                   # FastAPI application factory
├── data/
│   └── snapshot/                 # Pre-fetched January 2026 Parquet files
├── docs/
│   └── openapi.json              # Exported OpenAPI 3.1 specification
├── scripts/
│   ├── fetch_snapshot.py         # Snapshot ingestion CLI script
│   └── export_openapi.py         # OpenAPI export script
├── tests/
│   ├── unit/                     # Pure domain & repository unit tests
│   └── api/                      # Full API integration tests
├── Dockerfile                    # Container definition
├── pyproject.toml                # Dependencies, ruff, mypy, pytest config
└── README.md
```

---

## Environment Variables

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

| Variable | Default | Description |
|---|---|---|
| `APP_ENV` | `development` | Environment (`development`, `production`, `test`) |
| `API_V1_PREFIX` | `/api` | Base path prefix for all API routes |
| `CORS_ORIGINS` | `["http://localhost:5173", "http://localhost:3000"]` | Allowed CORS origins for frontend |
| `SNAPSHOT_DATA_DIR` | `data/snapshot` | Directory containing Parquet files |
| `DEFAULT_CUTOFF_TIME` | `09:00` | Default decision cutoff in Europe/London |
| `DELIVERY_WINDOW_START`| `2026-01-01` | Earliest valid delivery date |
| `DELIVERY_WINDOW_END` | `2026-01-31` | Latest valid delivery date |
| `ADMIN_TOKEN` | `secret` | Bearer token for POST `/api/admin/refresh` |
| `SERVE_FRONTEND` | `false` | When `true`, serves built frontend static files |

---

## Quickstart

### 1. Setup Virtual Environment

```bash
python -m venv venv
# Linux / macOS
source venv/bin/activate
# Windows PowerShell
.\venv\Scripts\Activate.ps1
```

### 2. Install Dependencies

```bash
pip install -e ".[dev]"
```

### 3. Run the Development Server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Interactive API documentation will be available at:
- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## Running Tests & Coverage

Execute the full test suite with coverage enforcement (target ≥ 85%):

```bash
pytest --cov=app --cov-report=term-missing
```

Run code formatting and linting:

```bash
ruff check app tests
ruff format --check app tests
```

---

## API Endpoints Reference

| ID | Method | Endpoint | Description |
|---|---|---|---|
| **E1** | `GET` | `/api/health` | Health check and snapshot status |
| **E2** | `GET` | `/api/meta` | Delivery window, available cutoffs, metric definitions |
| **E3** | `GET` | `/api/actuals` | Actual wind generation series (`FUELHH`) |
| **E4** | `GET` | `/api/forecasts` | Raw wind generation forecasts (`WINDFOR`) |
| **E5** | `GET` | `/api/forecasts/latest` | Latest-at-cutoff forecast for delivery day |
| **E6** | `GET` | `/api/comparison` | Actual vs forecast comparison for a single day |
| **E7** | `GET` | `/api/comparison/range` | Actual vs forecast comparison over date range |
| **E8** | `GET` | `/api/metrics` | Overall accuracy KPIs (MAE, RMSE, bias, percentiles) |
| **E9** | `GET` | `/api/metrics/daily` | Per-day accuracy metrics breakdown |
| **E10** | `GET` | `/api/metrics/by-hour` | Day × hour error heatmap and hourly profile |
| **E11** | `GET` | `/api/metrics/by-horizon`| Accuracy by forecast lead-time horizon bucket |
| **E12** | `GET` | `/api/errors/distribution`| Error distribution histogram and quantiles |
| **E13** | `POST`| `/api/admin/refresh` | Trigger re-fetch from Elexon BMRS (Admin token required) |

---

## Refreshing Snapshot Data

To pull fresh data directly from Elexon BMRS into Parquet files:

```bash
python scripts/fetch_snapshot.py --start 2026-01-01 --end 2026-01-31 --out-dir data/snapshot
```

To export an updated OpenAPI specification:

```bash
python scripts/export_openapi.py
```

---

## Docker Deployment

Build and run using Docker:

```bash
# Build image
docker build -t wind-forecast-backend .

# Run container
docker run -p 8000:8000 -e PORT=8000 wind-forecast-backend
```
