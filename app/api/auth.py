from typing import Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.db.dependencies import with_db_connection
from app.services import auth_service

router = APIRouter(prefix="/api/v1", tags=["auth"])


class GoogleAuthRequest(BaseModel):
    id_token: str = Field(min_length=1)
    # Optional device fingerprint; omitted by older clients - do not require.
    android_id: Optional[str] = Field(default=None, min_length=1)


class DeviceAuthRequest(BaseModel):
    android_id: str = Field(min_length=1)


@router.post("/auth/google", summary="Google login")
@with_db_connection
def google_auth(payload: GoogleAuthRequest) -> dict[str, Any]:
    # Never log id_token / auth tokens.
    try:
        data = auth_service.login_with_google(payload.id_token, android_id=payload.android_id)
    except auth_service.InvalidGoogleTokenError as exc:
        return {"code": 401, "message": str(exc), "data": None}
    except auth_service.AuthConfigurationError as exc:
        return {"code": 500, "message": str(exc), "data": None}
    return {"code": 0, "message": "success", "data": data}


@router.post("/auth/device", summary="Device login by android_id")
@with_db_connection
def device_auth(payload: DeviceAuthRequest) -> dict[str, Any]:
    try:
        print(f"Device login attempt with android_id: {payload.android_id}")
        data = auth_service.login_with_device(payload.android_id)
    except auth_service.InvalidDeviceAuthError as exc:
        return {"code": 400, "message": str(exc), "data": None}
    return {"code": 0, "message": "success", "data": data}
