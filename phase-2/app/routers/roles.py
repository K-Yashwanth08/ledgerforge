from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Role
from ..schemas import RoleOut

router=APIRouter(prefix="/roles",tags=["roles"])

@router.get("",response_model=list[RoleOut])
def list_roles(department_id: str | None = Query(default=None),db: Session=Depends(get_db)):
    query=db.query(Role)
    if department_id: query=query.filter(Role.department_id==department_id)
    return query.order_by(Role.role_title,Role.role_id).all()
