from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, RootModel

Password = Annotated[str, Field(min_length=8, max_length=128)]


class UserBase(BaseModel):
    email: EmailStr


class UserCreate(UserBase):
    password: Password
    is_admin: bool = False


class UserUpdate(BaseModel):
    is_active: bool | None = None
    is_admin: bool | None = None


class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    is_admin: bool
    created_at: datetime
    last_login_at: datetime | None


class UserCredentialResponse(UserResponse):
    bearer_token: str | None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LandCoverResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    land_cover_class: int = Field(alias="class")


class LandCoverFractionsResponse(RootModel[dict[str, float]]):
    pass


class ResetPasswordRequest(BaseModel):
    code: str = Field(min_length=1)
    password: Password
