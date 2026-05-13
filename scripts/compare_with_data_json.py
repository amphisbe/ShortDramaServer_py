from __future__ import annotations

import json
from pathlib import Path

from app.db.database import close_database, initialize_runtime
from app.services.play_service import list_play_items


def main() -> None:
    initialize_runtime(create_schema=True, seed=True)
    expected_path = Path("/home/ubuntu/upload/data.json")
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    actual, has_more = list_play_items(page=1, page_size=20)

    print(f"expected_count={len(expected)} actual_count={len(actual)} has_more={has_more}")
    if actual != expected:
        print("数据不一致，开始输出逐项差异：")
        max_len = max(len(expected), len(actual))
        for index in range(max_len):
            exp = expected[index] if index < len(expected) else None
            act = actual[index] if index < len(actual) else None
            if exp == act:
                continue
            print(f"\n# item[{index}]")
            if exp is None or act is None:
                print("expected=", exp)
                print("actual=", act)
                continue
            keys = list(dict.fromkeys([*exp.keys(), *act.keys()]))
            for key in keys:
                if exp.get(key) != act.get(key):
                    print(f"{key}: expected={exp.get(key)!r} actual={act.get(key)!r}")
        raise SystemExit(1)

    print("OK: /api/v1/video/play-list/raw 服务层输出已与 data.json 完全一致。")


if __name__ == "__main__":
    try:
        main()
    finally:
        close_database()
