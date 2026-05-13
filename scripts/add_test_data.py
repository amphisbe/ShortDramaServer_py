from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.database import close_database, initialize_runtime
from app.db.test_data import seed_temp_test_data


def main() -> None:
    initialize_runtime(create_schema=True, seed=False)
    result = seed_temp_test_data()
    print(json.dumps({"code": 0, "message": "success", "data": result}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    finally:
        close_database()
