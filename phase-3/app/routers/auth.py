from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..schemas import LoginRequest
from ..security import ACCESS_TOKEN_SECONDS, _configured_secret, create_access_token, current_actor, hash_password, verify_password

_DUMMY_PASSWORD_HASH = hash_password("nonexistent-account-dummy-password")

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    username = payload.username.strip().casefold()
    user = db.query(User).filter(func.lower(User.username) == username).first()
    # Fail closed if JWT signing has not been configured; never issue a token
    # using the development placeholder.
    _configured_secret()
    encoded_hash = user.password_hash if user else _DUMMY_PASSWORD_HASH
    password_valid = verify_password(payload.password, encoded_hash)
    if not user or not user.is_active or not password_valid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password",
                            headers={"WWW-Authenticate": "Bearer"})
    token, expires_at = create_access_token(user)
    return {"access_token": token, "token_type": "bearer", "expires_in": ACCESS_TOKEN_SECONDS,
            "expires_at": expires_at}


@router.get("/me")
def me(actor: dict = Depends(current_actor)):
    return {key: actor[key] for key in ("user_id", "employee_id", "username", "role")}
