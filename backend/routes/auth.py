"""Authentication endpoints for the deterministic synthetic demo workspace."""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from backend.security import DEMO_USERS, ROLE_LABELS, authenticate, get_current_user, issue_token, CurrentUser

router = APIRouter(prefix="/auth", tags=["authentication"])


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=120)
    password: str = Field(min_length=1, max_length=120)


@router.post("/login")
def login(payload: LoginRequest) -> dict:
    user = authenticate(payload.email, payload.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")
    return {"access_token": issue_token(user), "token_type": "bearer", "expires_in": 8 * 60 * 60,
            "user": {"user_id": user.user_id, "name": user.name, "email": user.email,
                      "role": user.role, "role_label": ROLE_LABELS[user.role]},
            "synthetic": True}


@router.get("/me")
def me(user: CurrentUser = Depends(get_current_user)) -> dict:
    return {"user_id": user.user_id, "name": user.name, "email": user.email,
            "role": user.role, "role_label": ROLE_LABELS[user.role],
            "authenticated_at": datetime.now(timezone.utc).isoformat(), "synthetic": True}


@router.get("/demo-users")
def demo_users() -> dict:
    return {"synthetic": True, "users": [{"email": email, "name": data[0], "role": data[1],
                                            "role_label": ROLE_LABELS[data[1]]} for email, data in DEMO_USERS.items()],
            "notice": "Demo credentials are for local synthetic evaluation only."}
