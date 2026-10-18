"""Language-independent tag identities and localized display names."""

from peewee import CharField, DecimalField, ForeignKeyField, IntegerField, TextField, DateTimeField

from app.models.drama import BaseModel, User, _utcnow


class Tag(BaseModel):
    code = CharField(max_length=64, unique=True)
    status = IntegerField(default=1)

    class Meta:
        table_name = 'tags'


class TagTranslation(BaseModel):
    tag = ForeignKeyField(Tag, backref='translations', column_name='tag_id')
    locale = CharField(max_length=35)
    name = CharField(max_length=100)
    description = TextField(default='')

    class Meta:
        table_name = 'tag_translations'
        indexes = ((("tag", "locale"), True),)


class TagAlias(BaseModel):
    tag = ForeignKeyField(Tag, backref='aliases', column_name='tag_id')
    locale = CharField(max_length=35)
    alias = CharField(max_length=100)

    class Meta:
        table_name = 'tag_aliases'
        indexes = ((("locale", "alias"), True),)


class UserTagWeight(BaseModel):
    # Legacy MySQL users.id is INT, while the current User model declares BIGINT.
    # Keep the ORM relation but omit a physical FK whose column types would clash.
    # User ownership/existence is validated at the authenticated service boundary.
    user = ForeignKeyField(User, backref='tag_weights', column_name='user_id', _deferred=True)
    tag_code = ForeignKeyField(Tag, field=Tag.code, column_name='tag_code', lazy_load=False)
    weight = DecimalField(max_digits=24, decimal_places=6, auto_round=True, default=0)
    weight_updated_at = DateTimeField(default=_utcnow)

    class Meta:
        table_name = 'user_tag_weights'
        indexes = ((("user", "tag_code"), True),)


TAG_MODELS = [Tag, TagTranslation, TagAlias, UserTagWeight]
