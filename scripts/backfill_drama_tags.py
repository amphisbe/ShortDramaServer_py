"""Preview legacy label conversion by default; --apply explicitly writes changes."""

import argparse
import json

from app.db.database import initialize_database
from app.services.tag_service import backfill_drama_tags


def main():
    parser = argparse.ArgumentParser(description='旧标签转换，默认只预览。请先运行 scripts.migrate_tags --seed')
    parser.add_argument('--apply', action='store_true', help='将可确定映射的旧标签写入 tag_weights')
    args = parser.parse_args()
    with initialize_database().connection_context():
        print(json.dumps(backfill_drama_tags(apply=args.apply), ensure_ascii=True, indent=2))


if __name__ == '__main__':
    main()
