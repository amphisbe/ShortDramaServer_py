from __future__ import annotations

import json

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
