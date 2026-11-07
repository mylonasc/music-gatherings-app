"""Regenerate checked-in JSON Schema snapshots for processor v1 contracts.

Run as ``python -m processor.gen_schemas`` from ``services/``.
"""

import json
from pathlib import Path

from processor.models import CONTRACT_MODELS

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_DIR = REPO_ROOT / "contracts" / "processor" / "v1"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, model in sorted(CONTRACT_MODELS.items()):
        schema = model.model_json_schema(ref_template=f"#/$defs/{name}.{{model}}")
        schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        schema["$id"] = f"https://example.local/contracts/processor/v1/{name}.json"
        schema["title"] = f"processor.v1.{name}"
        (OUT_DIR / f"{name}.json").write_text(json.dumps(schema, indent=2) + "\n")
    print(f"wrote {len(CONTRACT_MODELS)} schemas to {OUT_DIR}")


if __name__ == "__main__":
    main()
