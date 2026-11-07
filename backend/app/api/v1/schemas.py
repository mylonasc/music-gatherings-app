"""Pydantic schemas for S03 identity/crew endpoints."""

from pydantic import BaseModel, Field


class UserOut(BaseModel):
    id: str
    username: str
    display_name: str | None = None
    is_admin: bool


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class LoginResponse(BaseModel):
    csrf_token: str
    user: UserOut


class AccessRequestCreate(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=8, max_length=256)
    message: str | None = Field(default=None, max_length=1024)


class AccessRequestOut(BaseModel):
    id: str
    username: str
    status: str


class CrewOut(BaseModel):
    id: str
    name: str
    description: str | None = None


class CrewCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=1024)


class MemberOut(BaseModel):
    user_id: str
    username: str
    role: str


class MemberAdd(BaseModel):
    user_id: str
    role: str = "member"
