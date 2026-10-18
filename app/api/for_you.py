"""Random short-video feed; no cursor or personalized ranking in this phase."""

from fastapi import APIRouter, Depends, Query

from app.core.security import get_current_user
from app.db.dependencies import with_db_connection
from app.services.for_you_service import random_feed

router = APIRouter(prefix='/api/v1', tags=['for-you'])


@router.get('/for-you', summary='For You 随机视频流（默认五条）')
@with_db_connection
def for_you(
    count: int = Query(default=5, ge=1, le=20),
    content_lang: str = Query(default='en', min_length=1, max_length=255),
    user_id: str = Depends(get_current_user),
):
    return {'code': 0, 'message': 'success', 'data': random_feed(user_id, count, content_lang)}
