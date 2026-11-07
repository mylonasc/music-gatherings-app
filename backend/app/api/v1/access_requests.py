"""Public access requests and admin approval flow."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import check_rate_limit, get_db, get_settings, require_admin, verify_csrf
from app.api.v1.schemas import AccessRequestCreate, AccessRequestOut
from app.core.config import Settings
from app.core.security import hash_password
from app.models import AccessRequest, AuditEvent, Crew, CrewMembership, User
from app.models.base import utcnow_naive

router = APIRouter()

DEFAULT_CREW_NAME = "Jam Crew"


def get_or_create_default_crew(db: Session) -> Crew:
    crew = db.execute(select(Crew).where(Crew.name == DEFAULT_CREW_NAME)).scalar_one_or_none()
    if crew is None:
        crew = Crew(name=DEFAULT_CREW_NAME, description="Default jam crew")
        db.add(crew)
        db.flush()
    return crew


def _out(row: AccessRequest) -> AccessRequestOut:
    return AccessRequestOut(id=row.id, username=row.username, status=row.status)


@router.post(
    "/access-requests", response_model=AccessRequestOut, status_code=status.HTTP_201_CREATED
)
def create_access_request(
    body: AccessRequestCreate,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AccessRequestOut:
    username = body.username.strip()
    check_rate_limit(
        request,
        scope="access-request",
        key=username.lower(),
        max_attempts=settings.request_access_max_attempts,
        window_seconds=settings.request_access_window_seconds,
    )
    if db.execute(select(User).where(User.username == username)).scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="username taken")
    pending = db.execute(
        select(AccessRequest).where(
            AccessRequest.username == username, AccessRequest.status == "pending"
        )
    ).scalar_one_or_none()
    if pending is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="request already pending")
    row = AccessRequest(
        username=username,
        password_hash=hash_password(body.password),
        message=body.message,
    )
    db.add(row)
    db.flush()
    db.add(AuditEvent(action="access.requested", entity_type="access_request", entity_id=row.id))
    return _out(row)


@router.get("/access-requests", response_model=list[AccessRequestOut])
def list_access_requests(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> list[AccessRequestOut]:
    rows = db.execute(select(AccessRequest).order_by(AccessRequest.created_at)).scalars().all()
    return [_out(row) for row in rows]


@router.post(
    "/access-requests/{request_id}/approve",
    response_model=AccessRequestOut,
    dependencies=[Depends(verify_csrf)],
)
def approve_access_request(
    request_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> AccessRequestOut:
    row = db.get(AccessRequest, request_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    if row.status != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="already decided")
    if db.execute(select(User).where(User.username == row.username)).scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="username taken")
    user = User(username=row.username, password_hash=row.password_hash or "", status="active")
    db.add(user)
    db.flush()
    crew = get_or_create_default_crew(db)
    db.add(CrewMembership(crew_id=crew.id, user_id=user.id, role="member"))
    row.status = "approved"
    row.decided_by_id = admin.id
    row.decided_at = utcnow_naive()
    db.flush()
    db.add(
        AuditEvent(
            actor_user_id=admin.id,
            action="access.approved",
            entity_type="user",
            entity_id=user.id,
        )
    )
    return _out(row)


@router.post(
    "/access-requests/{request_id}/reject",
    response_model=AccessRequestOut,
    dependencies=[Depends(verify_csrf)],
)
def reject_access_request(
    request_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> AccessRequestOut:
    row = db.get(AccessRequest, request_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    if row.status != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="already decided")
    row.status = "rejected"
    row.decided_by_id = admin.id
    row.decided_at = utcnow_naive()
    db.flush()
    db.add(
        AuditEvent(
            actor_user_id=admin.id,
            action="access.rejected",
            entity_type="access_request",
            entity_id=row.id,
        )
    )
    return _out(row)
