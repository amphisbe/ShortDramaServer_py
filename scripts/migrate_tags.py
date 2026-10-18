"""Run with: python -m scripts.migrate_tags [--seed]."""

import argparse
import json

from app.db.database import initialize_database
from app.db.tag_migration import ensure_tag_schema, seed_tag_catalog


def main():
    parser = argparse.ArgumentParser(description='创建标签表及短剧标签字段；不会回填短剧业务数据')
    parser.add_argument('--seed', action='store_true', help='补充初始词表，不覆盖已维护的翻译或状态')
    args = parser.parse_args()
    db = initialize_database()
    with db.connection_context():
        ensure_tag_schema()
        if args.seed:
            seed_tag_catalog()
        print(json.dumps({'schema': 'ready', 'seeded': args.seed}))


if __name__ == '__main__':
    main()
