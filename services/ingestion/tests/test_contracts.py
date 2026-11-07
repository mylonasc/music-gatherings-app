"""Checked-in contract schemas must match the Pydantic models."""

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SCHEMA_DIR = REPO_ROOT / "contracts" / "ingestion" / "v1"


def test_contracts_match_checked_in_schemas() -> None:
    from common.contracts import CONTRACT_MODELS

    assert SCHEMA_DIR.is_dir(), "contracts/ingestion/v1 missing"
    checked_in = sorted(p.stem for p in SCHEMA_DIR.glob("*.json"))
    assert checked_in == sorted(CONTRACT_MODELS), (
        f"schema files out of sync: {checked_in} vs {sorted(CONTRACT_MODELS)}. "
        "Run `python -m common.gen_schemas` from services/ingestion and commit the result."
    )
    for name, model in sorted(CONTRACT_MODELS.items()):
        on_disk = json.loads((SCHEMA_DIR / f"{name}.json").read_text())
        fresh = model.model_json_schema(ref_template=f"#/$defs/{name}.{{model}}")
        # Compare the structural core; volatile metadata is asserted separately.
        for key in ("properties", "required", "$defs"):
            assert on_disk.get(key) == fresh.get(key), f"schema drift in {name}.json"
