import re
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Employee, User
from ..schemas import UserCreate, UserOut, UserPasswordChange, UserPatch
from ..security import ROLES, admin_actor, hash_password

router = APIRouter(prefix="/users", tags=["user administration"])
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _normalized_role(role: str) -> str:
    match = next((value for value in ROLES if value.casefold() == role.strip().casefold()), None)
    if not match:
        raise HTTPException(422, "Role must be Admin, HR, or Employee")
    return match


def _normalized_username(username: str) -> str:
    value = username.strip().casefold()
    if not EMAIL_RE.fullmatch(value):
        raise HTTPException(422, "Username must be a valid email address")
    return value


@router.get("", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), _admin: dict = Depends(admin_actor)):
    return db.query(User).order_by(User.username).all()


@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: str, db: Session = Depends(get_db), _admin: dict = Depends(admin_actor)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    return user


@router.post("", response_model=UserOut, status_code=201)
def create_user(payload: UserCreate, db: Session = Depends(get_db), _admin: dict = Depends(admin_actor)):
    username = _normalized_username(payload.username)
    role = _normalized_role(payload.role)
    if role == "Employee" and not payload.employee_id:
        raise HTTPException(422, "Employee accounts require an employee ID")
    if role == "Admin" and not payload.employee_id:
        raise HTTPException(422, "Standalone Admin accounts can be created only by the one-time local bootstrap")
    if payload.employee_id and not db.get(Employee, payload.employee_id):
        raise HTTPException(422, "Employee ID does not exist")
    if db.query(User).filter(func.lower(User.username) == username).first():
        raise HTTPException(409, "Username already exists")
    try:
        user = User(user_id=uuid.uuid4().hex[:24], employee_id=payload.employee_id, username=username,
                    password_hash=hash_password(payload.password), role=role, is_active=True)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Username or employee already has an account") from exc
    db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserOut)
def update_user(user_id: str, payload: UserPatch, db: Session = Depends(get_db), _admin: dict = Depends(admin_actor)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    was_active_admin = user.role == "Admin" and user.is_active
    changes = payload.model_dump(exclude_unset=True)
    if "username" in changes and changes["username"] is not None:
        username = _normalized_username(changes["username"])
        duplicate = db.query(User).filter(func.lower(User.username) == username, User.user_id != user_id).first()
        if duplicate:
            raise HTTPException(409, "Username already exists")
        user.username = username
    if "role" in changes and changes["role"] is not None:
        user.role = _normalized_role(changes["role"])
    if "is_active" in changes and changes["is_active"] is not None:
        user.is_active = changes["is_active"]
    if was_active_admin and (user.role != "Admin" or not user.is_active):
        another_admin = db.query(User).filter(User.role == "Admin", User.is_active.is_(True), User.user_id != user_id).first()
        if not another_admin:
            db.rollback()
            raise HTTPException(409, "Cannot remove the last active Admin")
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "User update conflicts with existing data") from exc
    db.refresh(user)
    return user


@router.post("/{user_id}/password", status_code=204)
def reset_password(user_id: str, payload: UserPasswordChange, db: Session = Depends(get_db),
                   _admin: dict = Depends(admin_actor)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    try:
        user.password_hash = hash_password(payload.password)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    db.commit()
    return None
