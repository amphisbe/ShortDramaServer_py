"""Localized tag dictionary, administrator maintenance and private interests."""

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel, ConfigDict, Field, StrictInt

from app.core.security import get_current_user, require_admin
from app.db.dependencies import with_db_connection
from app.services import tag_service

router = APIRouter(prefix='/api/v1', tags=['tags'])


class TagWrite(BaseModel):
    model_config = ConfigDict(extra='forbid')
    translations: dict[str, str] = Field(default_factory=dict, max_length=100)
    aliases: dict[str, list[str]] = Field(default_factory=dict, max_length=100)
    status: StrictInt | None = None


class TagCreate(TagWrite):
    code: str = Field(min_length=1, max_length=64)


class DramaTagsWrite(BaseModel):
    model_config = ConfigDict(extra='forbid')
    # Preserve JSON types for service validation: bool and numeric strings are rejected.
    weights: dict[str, object] = Field(min_length=1, max_length=5)
    source: str = 'manual'
    replace_manual: bool = False


def _response(func, *args, **kwargs):
    try:
        return {'code': 0, 'message': 'success', 'data': func(*args, **kwargs)}
    except tag_service.TagError as exc:
        return {'code': exc.code, 'message': str(exc), 'data': None}


def _locale(locale: str | None = Query(default=None, max_length=35),
            accept_language: str | None = Header(default=None)):
    # Defer parsing to _response so invalid locales use the project error envelope.
    return locale, accept_language


def _localized(func, locale_args, *args, **kwargs):
    locale = tag_service.preferred_locale(*locale_args)
    return func(*args, locale=locale, **kwargs)


@router.get('/tags', summary='多语言标签字典')
@with_db_connection
def list_tags(locale_args=Depends(_locale)):
    return _response(_localized, tag_service.list_tags, locale_args)


@router.get('/admin/tags', dependencies=[Depends(require_admin)], summary='标签管理列表')
@with_db_connection
def admin_tags():
    return _response(tag_service.list_tags, admin=True)


@router.post('/admin/tags', dependencies=[Depends(require_admin)], summary='创建英文编码标签')
@with_db_connection
def create_tag(payload: TagCreate):
    return _response(tag_service.save_tag, **payload.model_dump(), create=True)


@router.put('/admin/tags/{code}', dependencies=[Depends(require_admin)], summary='维护翻译、别名和状态')
@with_db_connection
def update_tag(code: str, payload: TagWrite):
    return _response(tag_service.save_tag, code=code, **payload.model_dump(exclude_unset=True))


@router.get('/admin/dramas/{drama_id}/tags', dependencies=[Depends(require_admin)], summary='查看短剧标签管理状态')
@with_db_connection
def admin_drama_tags(drama_id: str, locale_args=Depends(_locale)):
    return _response(_localized, tag_service.get_drama_tags, locale_args, drama_id, admin=True)


@router.put('/admin/dramas/{drama_id}/tags', dependencies=[Depends(require_admin)], summary='设置短剧标签权重')
@with_db_connection
def set_drama_tags(drama_id: str, payload: DramaTagsWrite):
    return _response(tag_service.set_drama_tags, drama_id, **payload.model_dump())


@router.get('/dramas/{drama_id}/tags', summary='短剧多语言标签')
@with_db_connection
def drama_tags(drama_id: str, locale_args=Depends(_locale)):
    return _response(_localized, tag_service.get_drama_tags, locale_args, drama_id)


@router.get('/me/interests', summary='当前用户的衰减后兴趣标签')
@with_db_connection
def interests(user_id: str = Depends(get_current_user), locale_args=Depends(_locale)):
    return _response(_localized, tag_service.get_interests, locale_args, user_id)


@router.delete('/me/interests', summary='重置当前用户兴趣画像')
@with_db_connection
def reset_interests(user_id: str = Depends(get_current_user)):
    return _response(tag_service.reset_interests, user_id)
