from datetime import datetime, timezone
from peewee import *

db = SqliteDatabase(':memory:')

def _utcnow():
    return datetime.now(timezone.utc)

class BaseModel(Model):
    class Meta:
        database = db

class TimestampMixin:
    created_at = DateTimeField(default=_utcnow)
    updated_at = DateTimeField(default=_utcnow)

class User(TimestampMixin, BaseModel):
    name = CharField()

db.create_tables([User])

print("User fields:", User._meta.fields.keys())
