"""Tag management. All persisted recommendation identities use English codes."""

import csv
import json
import math
import re
from datetime import datetime, timezone

from peewee import IntegrityError, SqliteDatabase

from app.db.database import initialize_database
from app.models import Drama, Tag, TagAlias, TagTranslation, User, UserTagWeight


class TagError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def normalize_locale(locale):
    raw = (locale or 'en').strip().replace('_', '-')
    if not re.fullmatch(r'[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*', raw) or len(raw) > 35:
        raise TagError(400, '无效的语言代码')
    # Existing content codes are accepted only as locale aliases; content language is unchanged.
    aliases = {'ind': 'id', 'vie': 'vi'}
    parts = raw.split('-')
    parts[0] = aliases.get(parts[0].lower(), parts[0].lower())
    return '-'.join([parts[0]] + [p.title() if len(p) == 4 else p.upper() if len(p) == 2 else p.lower() for p in parts[1:]])


def preferred_locale(locale=None, accept_language=None):
    if locale:
        return normalize_locale(locale)
    candidates = []
    for index, entry in enumerate((accept_language or '').split(',')):
        pieces = entry.strip().split(';')
        try:
            quality = 1.0
            for param in pieces[1:]:
                key, _, value = param.strip().partition('=')
                if key == 'q':
                    quality = float(value)
            if not 0 < quality <= 1:
                continue
            candidates.append((-quality, index, normalize_locale(pieces[0])))
        except (ValueError, TagError):
            continue
    return min(candidates)[2] if candidates else 'en'


def _check_code(code):
    if not isinstance(code, str) or len(code) > 64 or not re.fullmatch(r'[A-Z]+(?:_[A-Z]+)*', code):
        raise TagError(400, '标签编码必须为大写英文单词，以单下划线分隔')


def _get_tag(code):
    tag = Tag.get_or_none(Tag.code == code)
    if tag is None:
        raise TagError(404, '标签不存在')
    return tag


def _localized_names(tags, locale):
    locale = normalize_locale(locale)
    ids = [t.id for t in tags]
    translations = {}
    for row in TagTranslation.select().where(TagTranslation.tag.in_(ids)):
        translations.setdefault(row.tag_id, {})[row.locale] = row.name
    result = {}
    for tag in tags:
        names = translations.get(tag.id, {})
        fallbacks = [locale, locale.split('-')[0], 'en', 'en-US', 'en-GB']
        fallbacks.extend(sorted(key for key in names if key.startswith('en-')))
        result[tag.code] = next((names[key] for key in fallbacks if names.get(key)), tag.code)
    return result


def list_tags(locale='en', admin=False):
    query = Tag.select().order_by(Tag.code)
    if not admin:
        query = query.where(Tag.status == 1)
    tags = list(query)
    if not admin:
        names = _localized_names(tags, locale)
        return [{'code': t.code, 'name': names[t.code]} for t in tags]
    translations = {}
    aliases = {}
    for row in TagTranslation.select():
        translations.setdefault(row.tag_id, {})[row.locale] = row.name
    for row in TagAlias.select().order_by(TagAlias.locale, TagAlias.alias):
        aliases.setdefault(row.tag_id, {}).setdefault(row.locale, []).append(row.alias)
    return [{'code': t.code, 'status': t.status, 'translations': translations.get(t.id, {}),
             'aliases': aliases.get(t.id, {})} for t in tags]


def save_tag(code, translations=None, aliases=None, status=None, create=False):
    _check_code(code)
    names = {}
    for locale, name in (translations or {}).items():
        if not name.strip() or len(name.strip()) > 100:
            raise TagError(400, '标签名称长度应为 1～100')
        normalized = normalize_locale(locale)
        if normalized in names:
            raise TagError(400, '语言代码重复')
        names[normalized] = name.strip()
    if create and not any(key == 'en' or key.startswith('en-') for key in names):
        raise TagError(400, '新建标签必须提供英文名称')
    if status is not None and (type(status) is not int or status not in (0, 1)):
        raise TagError(400, '标签状态只能为 0 或 1')
    normalized_aliases = {}
    for locale, values in (aliases or {}).items():
        normalized = normalize_locale(locale)
        if normalized in normalized_aliases:
            raise TagError(400, '别名语言代码重复')
        if any(not v.strip() or len(v.strip()) > 100 for v in values):
            raise TagError(400, '标签别名长度应为 1～100')
        normalized_aliases[normalized] = sorted({v.strip() for v in values})
    db = initialize_database()
    try:
        with db.atomic():
            if create:
                tag = Tag.create(code=code, status=1 if status is None else status)
            else:
                tag = _get_tag(code)
                if not isinstance(db, SqliteDatabase):
                    tag = Tag.select().where(Tag.id == tag.id).for_update().get()
                if status is not None:
                    tag.status = status
                    tag.save()
            for locale, name in names.items():
                row, _ = TagTranslation.get_or_create(tag=tag, locale=locale, defaults={'name': name})
                row.name = name
                row.save()
            # Supplied locales replace aliases for those locales; omitted locales remain intact.
            for locale, values in normalized_aliases.items():
                TagAlias.delete().where((TagAlias.tag == tag) & (TagAlias.locale == locale)).execute()
                for value in values:
                    TagAlias.create(tag=tag, locale=locale, alias=value)
    except IntegrityError as exc:
        raise TagError(409, '标签编码或同语言别名已存在') from exc
    return next(t for t in list_tags(admin=True) if t['code'] == code)


def _positive_finite_number(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value) and value > 0
    except OverflowError:
        return False


def normalize_weights(weights):
    if not isinstance(weights, dict) or not 1 <= len(weights) <= 5:
        raise TagError(400, '每部短剧需要 1～5 个标签')
    for code, value in weights.items():
        _check_code(code)
        if not _positive_finite_number(value):
            raise TagError(400, '标签权重必须为有限正数')
    valid = {t.code for t in Tag.select().where((Tag.code.in_(list(weights))) & (Tag.status == 1))}
    if valid != set(weights):
        raise TagError(400, '包含不存在或已停用的标签')
    # Scale first, avoiding overflow for multiple large but finite values.
    largest = max(weights.values())
    scaled = {code: value / largest for code, value in weights.items()}
    total = math.fsum(scaled.values())
    normalized = {code: value / total for code, value in scaled.items()}
    if any(value <= 0 for value in normalized.values()):
        raise TagError(400, '标签权重差异过大')
    return normalized


def set_drama_tags(drama_id, weights, source='manual', replace_manual=False):
    if source not in ('manual', 'auto'):
        raise TagError(400, '标签来源必须为 manual 或 auto')
    db = initialize_database()
    with db.atomic():
        query = Drama.select().where(Drama.external_drama_id == drama_id)
        if not isinstance(db, SqliteDatabase):
            query = query.for_update()
        drama = query.first()
        if drama is None:
            raise TagError(404, '短剧不存在')
        if drama.tag_source == 'manual' and source == 'auto' and not replace_manual:
            raise TagError(409, '自动任务不能覆盖人工标签')
        normalized = normalize_weights(weights)
        tags = list(Tag.select().where(Tag.code.in_(list(normalized))))
        names = _localized_names(tags, 'en')
        drama.tag_weights = json.dumps(normalized, allow_nan=False)
        drama.tags = json.dumps([names[code] for code in normalized], ensure_ascii=False)
        drama.tag_status = 'done'
        drama.tag_source = source
        drama.tag_version += 1
        drama.save()
        return {'dramaId': drama.external_drama_id, 'weights': normalized, 'source': source, 'version': drama.tag_version}


def get_drama_tags(drama_id, locale='en', admin=False):
    query = Drama.select().where(Drama.external_drama_id == drama_id)
    if not admin:
        query = query.where(Drama.status == 1)
    drama = query.first()
    if drama is None:
        raise TagError(404, '短剧不存在')
    try:
        weights = json.loads(drama.tag_weights)
    except (TypeError, ValueError):
        weights = {}
    if not isinstance(weights, dict):
        weights = {}
    tags = list(Tag.select().where((Tag.code.in_(list(weights))) & (Tag.status == 1)).order_by(Tag.code))
    names = _localized_names(tags, locale)
    items = [{'code': t.code, 'name': names[t.code], 'weight': weights[t.code]} for t in tags
             if _positive_finite_number(weights[t.code])]
    if admin:
        return {'dramaId': drama.external_drama_id, 'weights': weights, 'status': drama.tag_status,
                'source': drama.tag_source, 'version': drama.tag_version, 'tags': items}
    return items


def _current_user(user_id):
    user = User.get_or_none((User.external_user_id == user_id) & (User.status == 1))
    if user is None:
        raise TagError(401, '用户不存在或已停用')
    return user


def _as_utc(value):
    # Peewee's SQLite DateTimeField may return ISO strings with UTC offsets.
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def get_interests(user_id, locale='en'):
    user = _current_user(user_id)
    rows = list(UserTagWeight.select(UserTagWeight, Tag).join(Tag).where(
        (UserTagWeight.user == user) & (Tag.status == 1)))
    tags = list(Tag.select().where(Tag.code.in_([r.tag_code_id for r in rows])))
    names = _localized_names(tags, locale)
    now = datetime.now(timezone.utc)
    items = []
    for row in rows:
        days = max(0, (now - _as_utc(row.weight_updated_at)).total_seconds()) / 86400
        weight = float(row.weight) * 0.95 ** days
        if math.isfinite(weight) and weight > 0:
            items.append({'code': row.tag_code_id, 'name': names[row.tag_code_id], 'weight': weight})
    return sorted(items, key=lambda item: (-item['weight'], item['code']))


def reset_interests(user_id):
    user = _current_user(user_id)
    with initialize_database().atomic():
        deleted = UserTagWeight.delete().where(UserTagWeight.user == user).execute()
    return {'deleted': deleted}


def backfill_drama_tags(apply=False):
    """Conservative migration: ambiguous/unknown labels leave the whole drama unchanged."""
    mapping = {}
    def add(label, code):
        mapping.setdefault(label.strip().casefold(), set()).add(code)
    active = {t.id: t.code for t in Tag.select().where(Tag.status == 1)}
    for code in active.values():
        add(code, code)
    for row in TagTranslation.select().where(TagTranslation.tag.in_(list(active))):
        add(row.name, active[row.tag_id])
    for row in TagAlias.select().where(TagAlias.tag.in_(list(active))):
        add(row.alias, active[row.tag_id])
    report = {'convertible': 0, 'updated': 0, 'unresolved': [], 'skipped': 0}
    db = initialize_database()
    def assess(drama):
        if drama.tag_source == 'manual' or drama.tag_status == 'done' or drama.tag_weights not in ('', '{}', None):
            return 'skipped', None
        text = (drama.tags or '').strip()
        try:
            if text.startswith(('[', '{', '"')):
                raw = json.loads(text)
            else:
                raw = next(csv.reader([text], skipinitialspace=True, strict=True)) if text else []
        except (TypeError, ValueError, csv.Error):
            raw = None
        if not isinstance(raw, list) or not raw or any(not isinstance(v, str) or not v.strip() for v in raw):
            return 'unresolved', {'dramaId': drama.external_drama_id, 'tags': raw,
                                  'rawTags': drama.tags, 'reason': 'invalid_or_empty'}
        codes = set()
        unresolved = []
        for label in raw:
            matches = mapping.get(label.strip().casefold(), set())
            if len(matches) != 1:
                unresolved.append(label)
            else:
                codes.update(matches)
        if unresolved or len(codes) > 5:
            return 'unresolved', {'dramaId': drama.external_drama_id, 'tags': unresolved or raw,
                                  'rawTags': drama.tags, 'reason': 'unknown_ambiguous_or_too_many'}
        return 'convertible', codes

    def record(drama, state, data, write):
        if state == 'unresolved':
            report['unresolved'].append(data)
        else:
            report[state] += 1
            if state == 'convertible' and write:
                # Imported labels have no proven manual provenance; do not fabricate it.
                normalized = normalize_weights({code: 1 for code in sorted(data)})
                drama.tag_weights = json.dumps(normalized)
                drama.tag_status = 'done'
                drama.tag_source = 'auto'
                drama.tag_version += 1
                drama.save()
                report['updated'] += 1

    # Preview in one SELECT, without a transaction and round trip per drama.
    # Actual writes re-read and lock only convertible rows, then recheck manual state.
    for drama in Drama.select().order_by(Drama.id):
        state, data = assess(drama)
        if not apply or state != 'convertible':
            record(drama, state, data, False)
            continue
        with db.atomic():
            query = Drama.select().where(Drama.id == drama.id)
            if not isinstance(db, SqliteDatabase):
                query = query.for_update()
            current = query.get()
            state, data = assess(current)
            record(current, state, data, True)
    return report
