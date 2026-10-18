"""Idempotent additive schema migration; does not backfill legacy drama labels."""

from peewee import MySQLDatabase
from playhouse.migrate import MySQLMigrator, SqliteMigrator, migrate

from app.db.database import initialize_database
from app.models import Drama, Tag, TagAlias, TagTranslation
from app.models.tag import TAG_MODELS


def ensure_tag_schema():
    db = initialize_database()
    db.create_tables(TAG_MODELS, safe=True)
    if not db.table_exists('dramas'):
        return
    existing = {column.name for column in db.get_columns('dramas')}
    migrator = MySQLMigrator(db) if isinstance(db, MySQLDatabase) else SqliteMigrator(db)
    for name in ('tag_weights', 'tag_status', 'tag_source', 'tag_version'):
        field = Drama._meta.fields[name]
        if name not in existing:
            # Peewee migrator fills existing rows with defaults before NOT NULL.
            migrate(migrator.add_column('dramas', name, field))
        # MySQL DDL autocommits. Resume add_column if a previous process stopped
        # after ADD COLUMN but before filling defaults or applying NOT NULL.
        column = next(c for c in db.get_columns('dramas') if c.name == name)
        if column.null:
            Drama.update({field: field.default}).where(field.is_null(True)).execute()
            migrate(migrator.add_not_null('dramas', name))


def seed_tag_catalog():
    from app.core.tag_catalog import DEFAULT_ALIASES, DEFAULT_TAGS

    db = initialize_database()
    with db.atomic():
        for code, names in DEFAULT_TAGS.items():
            tag, _ = Tag.get_or_create(code=code)
            for locale, name in names.items():
                TagTranslation.get_or_create(tag=tag, locale=locale, defaults={'name': name})
            for locale, values in DEFAULT_ALIASES.get(code, {}).items():
                for alias in values:
                    # Never steal an alias that an operator already assigned.
                    TagAlias.get_or_create(locale=locale, alias=alias, defaults={'tag': tag})
