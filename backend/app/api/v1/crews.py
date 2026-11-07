"""Crew membership views (member reads, admin writes)."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_admin, verify_csrf
from app.api.v1.schemas import CrewCreate, CrewOut, MemberAdd, MemberOut
from app.models import AuditEvent, Crew, CrewMembership, User

router = APIRouter()


def _crew_out(crew: Crew) -> CrewOut:
    return CrewOut(id=crew.id, name=crew.name, description=crew.description)


def _require_membership(db: Session, crew_id: str, user: User) -> Crew:
    crew = db.get(Crew, crew_id)
    if crew is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    member = db.execute(
        select(CrewMembership).where(
            CrewMembership.crew_id == crew.id, CrewMembership.user_id == user.id
        )
    ).scalar_one_or_none()
    if member is None and not user.is_admin:
        # Hide crew existence from non-members.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    return crew


@router.get("/crews", response_model=list[CrewOut])
def list_my_crews(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[CrewOut]:
    if user.is_admin:
        crews = db.execute(select(Crew).order_by(Crew.name)).scalars().all()
    else:
        crews = (
            db.execute(
                select(Crew)
                .join(CrewMembership, CrewMembership.crew_id == Crew.id)
                .where(CrewMembership.user_id == user.id)
                .order_by(Crew.name)
            )
            .scalars()
            .all()
        )
    return [_crew_out(crew) for crew in crews]


@router.post("/crews", response_model=CrewOut, status_code=status.HTTP_201_CREATED)
def create_crew(
    body: CrewCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
    _csrf: None = Depends(verify_csrf),
) -> CrewOut:
    crew = Crew(name=body.name.strip(), description=body.description, created_by_id=admin.id)
    db.add(crew)
    db.flush()
    db.add(CrewMembership(crew_id=crew.id, user_id=admin.id, role="owner"))
    db.add(
        AuditEvent(
            actor_user_id=admin.id, action="crew.created", entity_type="crew", entity_id=crew.id
        )
    )
    return _crew_out(crew)


@router.get("/crews/{crew_id}/members", response_model=list[MemberOut])
def list_members(
    crew_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[MemberOut]:
    crew = _require_membership(db, crew_id, user)
    rows = (
        db.execute(
            select(CrewMembership, User.username)
            .join(User, User.id == CrewMembership.user_id)
            .where(CrewMembership.crew_id == crew.id)
            .order_by(User.username)
        )
        .all()
    )
    return [MemberOut(user_id=m.user_id, username=username, role=m.role) for m, username in rows]


@router.post(
    "/crews/{crew_id}/members",
    response_model=MemberOut,
    status_code=status.HTTP_201_CREATED,
)
def add_member(
    crew_id: str,
    body: MemberAdd,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
    _csrf: None = Depends(verify_csrf),
) -> MemberOut:
    crew = db.get(Crew, crew_id)
    if crew is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    member_user = db.get(User, body.user_id)
    if member_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    if body.role not in ("owner", "admin", "member"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid role")
    existing = db.execute(
        select(CrewMembership).where(
            CrewMembership.crew_id == crew.id, CrewMembership.user_id == member_user.id
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="already a member")
    membership = CrewMembership(crew_id=crew.id, user_id=member_user.id, role=body.role)
    db.add(membership)
    db.flush()
    db.add(
        AuditEvent(
            actor_user_id=admin.id,
            action="crew.member_added",
            entity_type="crew",
            entity_id=crew.id,
        )
    )
    return MemberOut(user_id=member_user.id, username=member_user.username, role=membership.role)


@router.delete("/crews/{crew_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    crew_id: str,
    user_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
    _csrf: None = Depends(verify_csrf),
) -> None:
    membership = db.execute(
        select(CrewMembership).where(
            CrewMembership.crew_id == crew_id, CrewMembership.user_id == user_id
        )
    ).scalar_one_or_none()
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    db.delete(membership)
    db.flush()
    db.add(
        AuditEvent(
            actor_user_id=admin.id,
            action="crew.member_removed",
            entity_type="crew",
            entity_id=crew_id,
        )
    )
