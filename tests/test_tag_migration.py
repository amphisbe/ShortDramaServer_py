from peewee import SqliteDatabase

from app.db.database import database_proxy


def test_existing_drama_schema_migration_is_idempotent(tmp_path):
    from app.db.tag_migration import ensure_tag_schema, seed_tag_catalog
    from app.models import Tag, TagTranslation

    previous = database_proxy.obj
    db = SqliteDatabase(tmp_path / 'old.db')
    database_proxy.initialize(db)
    try:
        db.connect()
        # Minimal old-schema rows exercise additive migration, without model SELECTs.
        db.execute_sql('CREATE TABLE users (id INTEGER PRIMARY KEY)')
        # A nullable column left behind by interrupted MySQL DDL must also be repaired.
        db.execute_sql('CREATE TABLE dramas (id INTEGER PRIMARY KEY, tags TEXT, tag_weights TEXT)')
        db.execute_sql("INSERT INTO dramas (id, tags) VALUES (1, '[\"legacy\"]')")
        ensure_tag_schema()
        ensure_tag_schema()
        row = db.execute_sql('SELECT tags, tag_weights, tag_status, tag_source, tag_version FROM dramas').fetchone()
        assert row == ('["legacy"]', '{}', 'pending', '', 0)
        assert next(c for c in db.get_columns('dramas') if c.name == 'tag_weights').null is False
        seed_tag_catalog()
        count = Tag.select().count()
        tag = Tag.get(Tag.code == 'ROMANCE')
        TagTranslation.update(name='Edited').where((TagTranslation.tag == tag) & (TagTranslation.locale == 'en')).execute()
        Tag.update(status=0).where(Tag.id == tag.id).execute()
        seed_tag_catalog()
        assert Tag.select().count() == count
        assert Tag.get_by_id(tag.id).status == 0
        assert TagTranslation.get((TagTranslation.tag == tag) & (TagTranslation.locale == 'en')).name == 'Edited'
        assert {field.name for field in db.get_columns('user_tag_weights')} >= {'user_id', 'tag_code', 'weight'}
        # Legacy users may have a narrower key than the ORM's BigAutoField.
        assert all(fk.column != 'user_id' for fk in db.get_foreign_keys('user_tag_weights'))
    finally:
        db.close()
        database_proxy.initialize(previous)
