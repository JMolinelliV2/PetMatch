from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

from app.species import Species
Sex = Literal["male", "female", "unknown"]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class RegisterRequest(BaseModel):
    email: str = Field(min_length=5, max_length=320)
    password: str = Field(min_length=12, max_length=128)
    name: str = Field(min_length=1, max_length=120)
    phone: str | None = Field(default=None, max_length=32)


class LoginRequest(BaseModel):
    email: str = Field(min_length=5, max_length=320)
    password: str = Field(min_length=1, max_length=128)


class UserRead(ORMModel):
    id: UUID
    email: str
    pending_email: str | None = None
    name: str
    avatar_version: UUID | None = None
    phone: str | None
    notification_preferences: dict
    status: str
    role: str
    admin_access: bool = False
    email_verified: bool
    created_at: datetime

    @computed_field
    @property
    def email_verification_required(self) -> bool:
        return True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 3600
    user: UserRead


class PetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    species: Species
    breed: str = Field(default="unknown", max_length=120)
    sex: Sex = "unknown"
    size: str = Field(default="unknown", max_length=24)
    age_estimate: str | None = Field(default=None, max_length=80)
    primary_color: str = Field(default="unknown", max_length=40)
    secondary_colors: list[str] = Field(default_factory=list)
    coat_type: str = Field(default="unknown", max_length=40)
    distinctive_features: list[str] = Field(default_factory=list)
    collar_description: str | None = Field(default=None, max_length=255)
    microchip_reference: str | None = Field(default=None, max_length=80)


class PetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    species: Species | None = None
    breed: str | None = Field(default=None, max_length=120)
    sex: Sex | None = None
    size: str | None = Field(default=None, max_length=24)
    age_estimate: str | None = Field(default=None, max_length=80)
    primary_color: str | None = Field(default=None, max_length=40)
    secondary_colors: list[str] | None = None
    coat_type: str | None = Field(default=None, max_length=40)
    distinctive_features: list[str] | None = None
    collar_description: str | None = Field(default=None, max_length=255)
    microchip_reference: str | None = Field(default=None, max_length=80)

    @field_validator("species")
    @classmethod
    def species_cannot_be_null(cls, value):
        if value is None:
            raise ValueError("La especie debe ser perro o gato")
        return value

    @field_validator("sex")
    @classmethod
    def sex_cannot_be_null(cls, value):
        if value is None:
            raise ValueError("Use 'unknown' when sex is not known")
        return value


class PetRead(ORMModel):
    id: UUID
    owner_id: UUID
    name: str
    species: str
    breed: str
    sex: str
    size: str
    age_estimate: str | None
    primary_color: str
    secondary_colors: list
    coat_type: str
    distinctive_features: list
    collar_description: str | None
    microchip_reference: str | None
    created_at: datetime
    updated_at: datetime


class CoarseGeo(BaseModel):
    model_config=ConfigDict(extra="forbid")
    country: str=Field(default="ZZ",pattern="^[A-Z]{2}$")
    department: str=Field(default="unknown",max_length=80)
    locality: str=Field(default="unknown",max_length=80)

    @field_validator("department","locality")
    @classmethod
    def coarse_label(cls,value):
        value=value.strip()
        if not value or any(not (char.isalpha() or char in " '-.,()") for char in value):
            raise ValueError("Indicar únicamente una zona general, sin direcciones ni datos de contacto.")
        return value


RecoveryReason=Literal["MASCOMATCH_MATCH","MASCOMATCH_SIGHTING","SOCIAL_MEDIA","WHATSAPP","VET_OR_SHELTER",
                       "STREET_OR_POSTERS","RETURNED_ALONE","OTHER","PREFER_NOT_TO_SAY"]


class RecoveryData(BaseModel):
    recovery_reason: RecoveryReason="PREFER_NOT_TO_SAY"
    recovery_match_id: UUID | None=None
    recovery_observation_id: UUID | None=None


class LostCaseCreate(BaseModel):
    analytics_geo: CoarseGeo=Field(default_factory=CoarseGeo)
    pet_id: UUID
    lost_at: datetime
    last_seen_at: datetime | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    location_accuracy_meters: int | None = Field(default=None, ge=0)
    description: str = Field(default="", max_length=4000)
    public_location: str | None = Field(default=None, max_length=350)
    search_radius_meters: int = Field(default=15000, ge=100, le=200000)

    @model_validator(mode="after")
    def paired_coordinates(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        return self


class LostCaseUpdate(RecoveryData):
    analytics_geo: CoarseGeo | None=None
    status: Literal["ACTIVE", "FOUND", "CLOSED", "CANCELLED"] | None = None
    lost_at: datetime | None = None
    last_seen_at: datetime | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    location_accuracy_meters: int | None = Field(default=None, ge=0)
    description: str | None = Field(default=None, max_length=4000)
    public_location: str | None = Field(default=None, max_length=350)
    search_radius_meters: int | None = Field(default=None, ge=100, le=200000)

    @field_validator("analytics_geo")
    @classmethod
    def non_null_geo(cls,value):
        if value is None:raise ValueError("La zona general no puede ser null.")
        return value


class LostCaseRead(ORMModel):
    id: UUID
    public_id: str
    pet_id: UUID
    status: str
    moderation_status: str
    lost_at: datetime
    last_seen_at: datetime | None
    latitude: float | None
    longitude: float | None
    location_accuracy_meters: int | None
    description: str
    description_format: str = "LEGACY"
    public_location: str | None
    search_radius_meters: int
    created_at: datetime
    updated_at: datetime


class PublicPhotoRead(BaseModel):
    id: UUID
    is_primary: bool = False


class PublicPhotoList(BaseModel):
    items: list[PublicPhotoRead]


class PublicLostDogRead(BaseModel):
    id: UUID
    public_id: str
    name: str
    species: Species
    sex: str
    breed: str
    size: str
    primary_color: str
    description: str
    public_location: str | None
    lost_at: datetime
    photo_url: str | None
    publisher_name: str | None = None


class PublicLostDogList(BaseModel):
    items: list[PublicLostDogRead]
    total: int
    limit: int
    offset: int


class ObservationCreate(BaseModel):
    analytics_geo: CoarseGeo=Field(default_factory=CoarseGeo)
    species: Species
    sex: Sex = "unknown"
    primary_color: str = Field(default="unknown",max_length=40)
    size: str = Field(default="unknown",max_length=24)
    public_location: str | None = Field(default=None,max_length=350)
    share_contact: bool = False
    description: str = Field(min_length=1, max_length=4000)
    observed_at: datetime
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    location_accuracy_meters: int | None = Field(default=None, ge=0)
    source_type: Literal["USER_SIGHTING", "FOUND_ANIMAL"] = "USER_SIGHTING"
    confidence: float = Field(default=0.5, ge=0, le=1)

    @model_validator(mode="after")
    def paired_coordinates(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        return self


class ObservationUpdate(BaseModel):
    analytics_geo: CoarseGeo | None=None
    species: Species | None = None
    sex: Sex | None = None
    primary_color: str | None = Field(default=None,max_length=40)
    size: str | None = Field(default=None,max_length=24)
    public_location: str | None = Field(default=None,max_length=350)
    share_contact: bool | None = None
    description: str | None = Field(default=None, max_length=4000)
    observed_at: datetime | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    location_accuracy_meters: int | None = Field(default=None, ge=0)
    confidence: float | None = Field(default=None, ge=0, le=1)

    @field_validator("species")
    @classmethod
    def species_cannot_be_null(cls, value):
        if value is None:
            raise ValueError("La especie debe ser perro o gato")
        return value

    @field_validator("share_contact")
    @classmethod
    def contact_cannot_be_null(cls,value):
        if value is None:raise ValueError("Choose true or false for contact sharing")
        return value

    @field_validator("sex", "primary_color", "size")
    @classmethod
    def sex_cannot_be_null(cls, value):
        if value is None:
            raise ValueError("Use 'unknown' when sex is not known")
        return value


class OwnedObservationRead(ORMModel):
    """Private edit data. Exact coordinates are returned only to the report author."""
    id: UUID
    public_id: str
    species: str
    sex: str
    primary_color: str
    size: str
    description: str
    description_format: str = "LEGACY"
    source_type: str
    observed_at: datetime
    public_location: str | None
    latitude: float | None
    longitude: float | None
    location_accuracy_meters: int | None
    share_contact: bool
    linked_case_id: UUID | None


class ObservationRead(ORMModel):
    id: UUID
    public_id: str
    species: str
    sex: str
    primary_color: str
    size: str
    public_location: str | None
    description: str
    description_format: str = "LEGACY"
    observed_at: datetime
    latitude: float | None
    longitude: float | None
    location_accuracy_meters: int | None
    source_type: str
    confidence: float
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def hide_exact_public_location(self):
        # Precise coordinates remain in storage for future internal matching.
        if self.latitude is not None and self.longitude is not None:
            self.latitude = round(self.latitude, 2)
            self.longitude = round(self.longitude, 2)
        return self


class PhotoCreate(BaseModel):
    owner_type: Literal["pet", "lost_case", "observation"]
    owner_id: UUID
    storage_key: str = Field(min_length=1, max_length=512)
    mime_type: Literal["image/jpeg", "image/png", "image/webp"]
    width: int | None = Field(default=None, ge=1, le=30000)
    height: int | None = Field(default=None, ge=1, le=30000)


class PhotoRead(ORMModel):
    id: UUID
    owner_type: str
    owner_id: UUID
    storage_key: str
    url: str | None
    mime_type: str
    width: int | None
    height: int | None
    created_at: datetime
    is_primary: bool = False


class PhotoAlbumRead(BaseModel):
    items: list[PhotoRead]
    primary_photo_id: UUID | None
    max_photos: int = 5


class PhotoCoverInput(BaseModel):
    owner_type: Literal["pet", "lost_case", "observation"]
    owner_id: UUID
    photo_id: UUID


class PhotoUpdate(BaseModel):
    width: int | None = Field(default=None, ge=1, le=30000)
    height: int | None = Field(default=None, ge=1, le=30000)


class PhotoUploadRead(BaseModel):
    photo: PhotoRead
    signed_url: str


class LinkedSightingRead(BaseModel):
    id: UUID
    public_id: str
    status: str
    owner_notified: bool


class NotificationRead(BaseModel):
    presentation: str | None=None
    id: UUID
    kind: str
    title: str
    body: str
    read_at: datetime | None
    archived_at: datetime | None = None
    created_at: datetime
    lost_case_id: UUID
    lost_case_public_id: str
    observation_public_id: str
    pet_name: str
    observed_at: datetime
    public_location: str | None
    latitude: float | None
    longitude: float | None
    reasons: list[str]
    photo_ids: list[UUID]
    email_status: str
    match_id: UUID | None = None
    match_status: str | None = None
    reporter_contact: str | None = None
    matching_status: str | None = None
    linked_to_notice: bool = False


class MatchRead(ORMModel):
    presentation: str | None=None
    id: UUID
    lost_case_id: UUID
    observation_id: UUID
    feature_score: float
    visual_score: float | None
    geo_score: float
    temporal_score: float
    final_score: float
    evidence_coverage: float
    distance_meters: float
    explanation: list[str]
    status: str
    created_at: datetime


class MatchFeedback(RecoveryData):
    model_config = ConfigDict(extra="forbid")
    status: Literal["CONFIRMED_RELEVANT", "FALSE_MATCH", "RESOLVED"]
    recovered: bool = Field(default=False, strict=True)

    @model_validator(mode="after")
    def recovered_match(self):
        if self.recovered and self.status != "RESOLVED":
            raise ValueError("Recuperar la mascota requiere confirmar la coincidencia.")
        return self


class CaseEdit(BaseModel):
    model_config=ConfigDict(extra="forbid")
    pet: PetUpdate
    case: LostCaseUpdate


class NotificationList(BaseModel):
    items: list[NotificationRead]
    unread_count: int
    total: int


class NotificationPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: bool

