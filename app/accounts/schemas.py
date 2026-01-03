"""Schemos autentifikacijos veiksmams."""

from datetime import datetime

from ninja import Field, Schema


class UserPublicSchema(Schema):
    id: int
    email: str
    username: str
    full_name: str | None = None


class UserConsentsSchema(Schema):
    newsletter_consent: bool = False
    privacy_policy_consent: bool = False
    terms_of_service_consent: bool = False

    newsletter_consent_at: datetime | None = None
    privacy_policy_consent_at: datetime | None = None
    terms_of_service_consent_at: datetime | None = None


class UserPublicWithConsentsSchema(UserPublicSchema):
    consents: UserConsentsSchema | None = None


class SessionSchema(Schema):
    is_authenticated: bool
    csrf_token: str
    user: UserPublicWithConsentsSchema | None = None


class LoginRequestSchema(Schema):
    identifier: str = Field(..., description="Vartotojo vardas arba el. paštas")
    password: str = Field(..., description="Slaptažodis")


class RegisterRequestSchema(Schema):
    email: str = Field(..., description="El. pašto adresas")
    password: str = Field(..., description="Slaptažodis")
    username: str | None = Field(
        default=None,
        description="Vartotojo vardas (jei nenurodyta – sugeneruojamas iš el. pašto)",
    )
    full_name: str | None = Field(default=None, description="Pilnas vardas (nebūtina)")

    newsletter_consent: bool = Field(default=False, description="Sutikimas gauti naujienlaiškį")
    privacy_policy_consent: bool = Field(default=False, description="Sutikimas su privatumo politika")
    terms_of_service_consent: bool = Field(default=False, description="Sutikimas su naudojimosi taisyklėmis")


class UpdateConsentsRequestSchema(Schema):
    newsletter_consent: bool | None = Field(
        default=None, description="Sutikimas gauti naujienlaiškį"
    )
    privacy_policy_consent: bool | None = Field(
        default=None, description="Sutikimas su privatumo politika"
    )
    terms_of_service_consent: bool | None = Field(
        default=None, description="Sutikimas su naudojimosi taisyklėmis"
    )


class UpdateConsentsResponseSchema(Schema):
    consents: UserConsentsSchema


class PasswordResetRequestSchema(Schema):
    email: str = Field(..., description="Naudotojo el. pašto adresas")


class PasswordResetResponseSchema(Schema):
    sent: bool = True


class PasswordResetConfirmRequestSchema(Schema):
    uid: str = Field(..., description="UID iš password reset nuorodos (uidb64)")
    token: str = Field(..., description="Token iš password reset nuorodos")
    new_password: str = Field(..., description="Naujas slaptažodis")


class PasswordResetConfirmResponseSchema(Schema):
    changed: bool = True
