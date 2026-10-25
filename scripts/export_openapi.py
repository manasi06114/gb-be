"""Export OpenAPI specification to JSON for frontend contract and typing."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import create_app


def export_openapi() -> None:
    """Generate OpenAPI schema and save to docs/openapi.json."""
    app = create_app()
    openapi_schema = app.openapi()

    docs_dir = Path(__file__).resolve().parent.parent / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)

    out_file = docs_dir / "openapi.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(openapi_schema, f, indent=2)

    print(f"Exported OpenAPI spec to {out_file}")


if __name__ == "__main__":
    export_openapi()
