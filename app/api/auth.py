from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.db.dependencies import with_db_connection
from app.services import auth_service

router = APIRouter(prefix="/api/v1", tags=["auth"])


class GoogleAuthRequest(BaseModel):
    id_token: str = Field(min_length=1)


@router.post("/auth/google", summary="Google 登录")
@with_db_connection
def google_auth(payload: GoogleAuthRequest) -> dict[str, Any]:
    print("Google Auth Request:", payload)
    try:
        data = auth_service.login_with_google(payload.id_token)
    except auth_service.InvalidGoogleTokenError as exc:
        return {"code": 401, "message": str(exc), "data": None}
    except auth_service.AuthConfigurationError as exc:
        return {"code": 500, "message": str(exc), "data": None}
    return {"code": 0, "message": "success", "data": data}
