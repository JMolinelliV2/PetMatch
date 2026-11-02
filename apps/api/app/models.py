from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, Boolean, CheckConstraint, Date, DateTime, Float, ForeignKey, Index, Integer, JSON, Numeric, String, Text, Uuid, UniqueConstraint, func, insert
from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.db.base import Base
from app.species import is_supported_species, SCOPE_MESSAGE


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class Donation(TimestampMixin, Base):
    """Anonymous one-time contributions; never store payer or card information."""
    __tablename__ = "donations"
    __table_args__ = (CheckConstraint("amount_uyu >= 1 AND amount_uyu <= 9007199254740991", name="ck_donation_amount"),)
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    request_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), unique=True, nullable=False)
    browser_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    amount_uyu: Mapped[int] = mapped_column(BigInteger, nullable=False)
    environment: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="CREATING", nullable=False, index=True)
    collector_id: Mapped[str] = mapped_column(String(64), nullable=False)
    application_id: Mapped[str] = mapped_column(String(64), nullable=False)
    public_base_url: Mapped[str] = mapped_column(String(512), nullable=False)
    provider_order_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    checkout_url: Mapped[str | None] = mapped_column(String(2048))
    provider_status: Mapped[str | None] = mapped_column(String(64))
    provider_status_detail: Mapped[str | None] = mapped_column(String(80))
    provider_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(64))


class DonationSync(Base):
    """Durable, deduplicated resource lookup queue; no webhook bodies or signatures."""
    __tablename__ = "donation_sync"
    __table_args__ = (UniqueConstraint("environment", "provider_order_id", name="uq_donation_sync_resource"),)
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    environment: Mapped[str] = mapped_column(String(16), nullable=False)
    provider_order_id: Mapped[str] = mapped_column(String(64), nullable=False)
    pending: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(64))


class PublicationNumber(Base):
    """Shared allocator; retain issued numbers after deleting a publication."""
    __tablename__ = "publication_numbers"
    __table_args__ = {"sqlite_autoincrement": True}
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer(), "sqlite"), primary_key=True, autoincrement=True)


def allocate_publication_number(context) -> int:
    # The database allocates atomically on the publication's own transaction.
    return context.connection.execute(insert(PublicationNumber.__table__).values()).inserted_primary_key[0]


class PublicationIdentityMixin:
    public_number: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("publication_numbers.id"), unique=True, nullable=False,
        default=allocate_publication_number,
    )

    @property
    def public_id(self) -> str:
        return f"MM-{self.public_number:06d}"


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    pending_email: Mapped[str | None] = mapped_column(String(320))
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    avatar_storage_key: Mapped[str | None] = mapped_column(String(512))
    avatar_version: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    notification_preferences: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="ACTIVE", nullable=False)
    role: Mapped[str] = mapped_column(String(24), default="USER", server_default="USER", nullable=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    pets: Mapped[list["Pet"]] = relationship(back_populates="owner")
    administrator_assignment: Mapped["AdminAccess | None"] = relationship(back_populates="owner", uselist=False, passive_deletes=True)

    @property
    def admin_access(self) -> bool:
        return self.status == "ACTIVE" and self.role == "ADMIN" and self.email_verified and self.administrator_assignment is not None

    @property
    def email_verified(self):
        return self.email_verified_at is not None


class AdminAccess(Base):
    __tablename__ = "admin_access"
    __table_args__ = (CheckConstraint("id = 1", name="ck_single_admin_access"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    user_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), unique=True)
    pending_email: Mapped[str | None] = mapped_column(String(320))
    owner: Mapped["User | None"] = relationship(back_populates="administrator_assignment")


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OperationalTracking(Base):
    __tablename__ = "operational_tracking"
    __table_args__ = (CheckConstraint("id = 1", name="ck_single_operational_tracking"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class UserActivity(Base):
    """One authenticated activity bucket per account and UTC minute; no browsing details."""
    __tablename__ = "user_activity"
    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True, index=True)


class EmailDeliveryLog(Base):
    """One SMTP attempt, including grouped alerts. Never persist email content or tokens."""
    __tablename__ = "email_delivery_log"
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    source_type: Mapped[str] = mapped_column(String(24), nullable=False)
    source_ids: Mapped[list] = mapped_column(JSON, nullable=False)
    recipient_user_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True)
    status: Mapped[str] = mapped_column(String(24), index=True, nullable=False)
    item_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True, nullable=False)


class AccountToken(Base):
    __tablename__ = "account_tokens"
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    destination_email: Mapped[str | None] = mapped_column(String(320))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    encrypted_token: Mapped[str] = mapped_column(String(512), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    email_status: Mapped[str] = mapped_column(String(24), default="PENDING", nullable=False)
    email_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    email_available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Pet(TimestampMixin, Base):
    __tablename__ = "pets"

    @validates("species")
    def validate_species(self, key, value):
        if not is_supported_species(value):
            raise ValueError(SCOPE_MESSAGE)
        return value

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    species: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    breed: Mapped[str] = mapped_column(String(120), default="unknown", nullable=False)
    sex: Mapped[str] = mapped_column(String(24), default="unknown", nullable=False)
    size: Mapped[str] = mapped_column(String(24), default="unknown", nullable=False)
    age_estimate: Mapped[str | None] = mapped_column(String(80))
    primary_color: Mapped[str] = mapped_column(String(40), default="unknown", nullable=False)
    secondary_colors: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    coat_type: Mapped[str] = mapped_column(String(40), default="unknown", nullable=False)
    distinctive_features: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    collar_description: Mapped[str | None] = mapped_column(String(255))
    microchip_reference: Mapped[str | None] = mapped_column(String(80))
    evaluation_consent: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    evaluation_consent_version: Mapped[str | None] = mapped_column(String(40))
    evaluation_consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    owner: Mapped[User] = relationship(back_populates="pets")
    lost_cases: Mapped[list["LostCase"]] = relationship(back_populates="pet")


class LostCase(PublicationIdentityMixin, TimestampMixin, Base):
    __tablename__ = "lost_cases"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    pet_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("pets.id", ondelete="RESTRICT"), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="ACTIVE", index=True, nullable=False)
    moderation_status: Mapped[str] = mapped_column(String(24), default="VISIBLE", server_default="VISIBLE", nullable=False)
    lost_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    location_accuracy_meters: Mapped[int | None] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(String(4000), default="", nullable=False)
    description_format: Mapped[str] = mapped_column(String(16), default="USER_TEXT", server_default="USER_TEXT", nullable=False)
    public_location: Mapped[str | None] = mapped_column(String(350))
    analytics_geo: Mapped[dict] = mapped_column(JSON, default=dict, server_default="{}", nullable=False)
    search_radius_meters: Mapped[int] = mapped_column(Integer, default=15000, nullable=False)
    pet: Mapped[Pet] = relationship(back_populates="lost_cases")


class PhotoReminder(Base):
    __tablename__ = "photo_reminders"
    __table_args__ = (Index("ix_photo_reminders_due", "status", "available_at"),)
    lost_case_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("lost_cases.id", ondelete="CASCADE"), primary_key=True)
    status: Mapped[str] = mapped_column(String(24), default="PENDING", nullable=False)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PhotoDeletion(Base):
    __tablename__ = "photo_deletions"
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    storage_key: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class Observation(PublicationIdentityMixin, TimestampMixin, Base):
    __tablename__ = "observations"

    @validates("species")
    def validate_species(self, key, value):
        if not is_supported_species(value):
            raise ValueError(SCOPE_MESSAGE)
        return value

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    author_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True)
    species: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    sex: Mapped[str] = mapped_column(String(24), default="unknown", server_default="unknown", nullable=False)
    primary_color: Mapped[str] = mapped_column(String(40), default="unknown", server_default="unknown", nullable=False)
    size: Mapped[str] = mapped_column(String(24), default="unknown", server_default="unknown", nullable=False)
    description: Mapped[str] = mapped_column(String(4000), nullable=False)
    description_format: Mapped[str] = mapped_column(String(16), default="USER_TEXT", server_default="USER_TEXT", nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    location_accuracy_meters: Mapped[int | None] = mapped_column(Integer)
    source_type: Mapped[str] = mapped_column(String(24), default="USER_SIGHTING", index=True, nullable=False)
    moderation_status: Mapped[str] = mapped_column(String(24), default="VISIBLE", server_default="VISIBLE", nullable=False)
    share_contact: Mapped[bool] = mapped_column(Boolean,default=False,server_default="false",nullable=False)
    confidence: Mapped[float] = mapped_column(Numeric(4, 3), default=0.5, nullable=False)
    linked_case_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("lost_cases.id", ondelete="SET NULL"), index=True)
    submission_hash: Mapped[str | None] = mapped_column(String(64))
    public_location: Mapped[str | None] = mapped_column(String(350))
    analytics_geo: Mapped[dict] = mapped_column(JSON, default=dict, server_default="{}", nullable=False)
    matching_status: Mapped[str] = mapped_column(String(32), default="NOT_REQUESTED", server_default="NOT_REQUESTED", index=True, nullable=False)
    matching_score: Mapped[float | None] = mapped_column(Float)
    matching_reasons: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    matching_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Notification(TimestampMixin, Base):
    __tablename__ = "notifications"
    __table_args__ = (UniqueConstraint("lost_case_id", "observation_id", name="uq_notification_case_observation"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    lost_case_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("lost_cases.id", ondelete="CASCADE"), index=True, nullable=False)
    observation_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("observations.id", ondelete="CASCADE"), nullable=False)
    match_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("matches.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    body: Mapped[str] = mapped_column(String(1000), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    email_status: Mapped[str] = mapped_column(String(24), default="PENDING", server_default="PENDING", nullable=False)
    email_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    email_available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    email_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Photo(TimestampMixin, Base):
    __tablename__ = "photos"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    owner_type: Mapped[str] = mapped_column(String(24), index=True, nullable=False)
    owner_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), index=True, nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    url: Mapped[str | None] = mapped_column(String(2048))
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)


class PhotoCover(Base):
    __tablename__ = "photo_covers"

    owner_type: Mapped[str] = mapped_column(String(24), primary_key=True)
    owner_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    photo_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("photos.id", ondelete="CASCADE"), index=True, nullable=False)


class AnalysisJob(TimestampMixin, Base):
    __tablename__ = "analysis_jobs"
    __table_args__ = (Index("ix_analysis_jobs_created_at", "created_at"), Index("ix_analysis_jobs_finished_at", "finished_at"), Index("ix_analysis_jobs_dispatch", "status", "priority", "available_at"))

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    deduplication_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    owner_type: Mapped[str] = mapped_column(String(24), index=True, nullable=False)
    owner_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), index=True, nullable=False)
    photo_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("photos.id", ondelete="CASCADE"), index=True)
    source_type: Mapped[str] = mapped_column(String(16), nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(80), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    input_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=50, server_default="50", nullable=False)
    preprocessing_version: Mapped[str] = mapped_column(String(240), default="legacy", server_default="legacy", nullable=False)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict, server_default="{}", nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="PENDING", index=True, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    dispatch_generation: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    run_token: Mapped[str | None] = mapped_column(String(36))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(80))


class FeatureSet(TimestampMixin, Base):
    __tablename__ = "feature_sets"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    analysis_job_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("analysis_jobs.id", ondelete="CASCADE"), unique=True, nullable=False)
    features: Mapped[dict] = mapped_column(JSON, nullable=False)


class Embedding(TimestampMixin, Base):
    __tablename__ = "embeddings"
    analysis_job_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("analysis_jobs.id", ondelete="CASCADE"), primary_key=True)
    photo_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("photos.id", ondelete="CASCADE"), index=True, nullable=False)
    model: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    vector: Mapped[list[float]] = mapped_column(Vector(512).with_variant(JSON(), "sqlite"), nullable=False)
    provider: Mapped[str] = mapped_column(String(40), default="legacy", server_default="legacy", nullable=False)
    revision: Mapped[str] = mapped_column(String(80), default="legacy", server_default="legacy", nullable=False)
    preprocessing_version: Mapped[str] = mapped_column(String(240), default="legacy", server_default="legacy", nullable=False)
    space_id: Mapped[str] = mapped_column(String(64), default="legacy", server_default="legacy", index=True, nullable=False)
    quality: Mapped[dict] = mapped_column(JSON, default=dict, server_default="{}", nullable=False)


class Match(TimestampMixin, Base):
    __tablename__ = "matches"
    __table_args__ = (UniqueConstraint("lost_case_id", "observation_id", name="uq_match_case_observation"),)
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    lost_case_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("lost_cases.id", ondelete="CASCADE"), index=True, nullable=False)
    observation_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("observations.id", ondelete="CASCADE"), index=True, nullable=False)
    feature_score: Mapped[float] = mapped_column(Float, nullable=False)
    visual_score: Mapped[float | None] = mapped_column(Float)
    visual_similarity: Mapped[float | None] = mapped_column(Float)
    geo_score: Mapped[float] = mapped_column(Float, nullable=False)
    temporal_score: Mapped[float] = mapped_column(Float, nullable=False)
    final_score: Mapped[float] = mapped_column(Float, index=True, nullable=False)
    evidence_coverage: Mapped[float] = mapped_column(Float, nullable=False)
    distance_meters: Mapped[float] = mapped_column(Float, nullable=False)
    explanation: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="NEW", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    feedback_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    recommended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    recommendation_source: Mapped[str | None] = mapped_column(String(24))
    recommended_score: Mapped[float | None] = mapped_column(Float)
    recommendation_snapshot: Mapped[dict] = mapped_column(JSON, default=dict, server_default="{}", nullable=False)
    first_shown_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_viewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    first_viewed_rank: Mapped[int | None] = mapped_column(Integer)
    best_viewed_rank: Mapped[int | None] = mapped_column(Integer)
    viewed_snapshot: Mapped[dict | None] = mapped_column(JSON)


class MatchFeedbackEvent(Base):
    __tablename__ = "match_feedback_events"
    __table_args__ = (Index("ix_match_feedback_latest", "match_id", "created_at", "id"),)
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    match_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("matches.id", ondelete="CASCADE"), index=True, nullable=False)
    actor_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    previous_status: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    recovered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    score: Mapped[float | None] = mapped_column(Float)
    legacy: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    context_snapshot: Mapped[dict] = mapped_column(JSON, default=dict, server_default="{}", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AnalyticsTracking(Base):
    __tablename__ = "analytics_tracking"
    __table_args__ = (CheckConstraint("id = 1", name="ck_single_analytics_tracking"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AnalyticsVisitor(Base):
    __tablename__ = "analytics_visitors"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)


class AnalyticsSession(Base):
    __tablename__ = "analytics_sessions"
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    visitor_id: Mapped[str] = mapped_column(String(64), ForeignKey("analytics_visitors.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    returning: Mapped[bool] = mapped_column("is_returning",Boolean, nullable=False)


class ProductEvent(Base):
    """Bounded first-party facts; never arbitrary properties, URLs, coordinates or contact data."""
    __tablename__ = "product_events"
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    deduplication_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    page: Mapped[str] = mapped_column(String(24), nullable=False)
    visitor_id: Mapped[str | None] = mapped_column(String(64), index=True)
    session_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    user_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True)
    actor_key: Mapped[str] = mapped_column(String(64), nullable=False)
    case_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True),ForeignKey("lost_cases.id",ondelete="SET NULL"),index=True)
    country: Mapped[str] = mapped_column(String(2), nullable=False)
    department: Mapped[str] = mapped_column(String(80), nullable=False)
    locality: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    aggregated: Mapped[bool] = mapped_column(Boolean,default=False,server_default="false",nullable=False,index=True)


class ProductMilestone(Base):
    """Compact durable deduplication ledger, including photo thresholds after deletion/retry."""
    __tablename__ = "product_milestones"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))


class ProductDaily(Base):
    """Daily per-actor/session counters with optional case context, without individual event timestamps."""
    __tablename__ = "product_daily"
    __table_args__ = (Index("ix_product_daily_day_name", "day", "name"), Index("ix_product_daily_geo_day", "country", "department", "locality", "day"))
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    day: Mapped[date] = mapped_column(Date, nullable=False)
    name: Mapped[str] = mapped_column(String(40), nullable=False)
    page: Mapped[str] = mapped_column(String(24), nullable=False)
    visitor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    session_key: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_key: Mapped[str] = mapped_column(String(64), nullable=False)
    case_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True),ForeignKey("lost_cases.id",ondelete="SET NULL"),index=True)
    country: Mapped[str] = mapped_column(String(2), nullable=False)
    department: Mapped[str] = mapped_column(String(80), nullable=False)
    locality: Mapped[str] = mapped_column(String(80), nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False)


class MatchExposure(Base):
    __tablename__ = "match_exposures"
    __table_args__ = (UniqueConstraint("session_id", "match_id", "context", name="uq_match_exposure"),)
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("analytics_sessions.id", ondelete="CASCADE"), nullable=False)
    match_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("matches.id", ondelete="CASCADE"), index=True, nullable=False)
    context: Mapped[str] = mapped_column(String(24), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    shown_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    viewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RecoveryOutcome(Base):
    __tablename__ = "recovery_outcomes"
    lost_case_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("lost_cases.id", ondelete="CASCADE"), primary_key=True)
    owner_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    reason: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    match_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("matches.id", ondelete="SET NULL"))
    observation_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("observations.id", ondelete="SET NULL"))
    recovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CaseReview(TimestampMixin, Base):
    __tablename__ = "case_reviews"
    __table_args__ = (
        UniqueConstraint("lost_case_id", name="uq_case_review_case"),
        CheckConstraint("rating >= 1 AND rating <= 5", name="ck_case_review_rating"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    lost_case_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("lost_cases.id", ondelete="CASCADE"), nullable=False)
    author_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str] = mapped_column(String(800), nullable=False)
    visibility: Mapped[str] = mapped_column(String(24), default="VISIBLE", server_default="VISIBLE", nullable=False)
    consent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ModerationReport(TimestampMixin, Base):
    __tablename__="moderation_reports"
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True),primary_key=True,default=uuid4)
    reporter_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True),ForeignKey("users.id",ondelete="SET NULL"))
    target_type: Mapped[str] = mapped_column(String(24),nullable=False)
    target_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True),index=True,nullable=False)
    reason: Mapped[str] = mapped_column(String(40),nullable=False)
    detail: Mapped[str] = mapped_column(String(1000),default="",nullable=False)
    status: Mapped[str] = mapped_column(String(24),default="OPEN",index=True,nullable=False)


class ContactMessage(Base):
    __tablename__ = "contact_messages"
    __table_args__ = (Index("ix_contact_messages_delivery", "email_status", "email_available_at"),)
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    topic: Mapped[str] = mapped_column(String(24), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    email_status: Mapped[str] = mapped_column(String(24), default="PENDING", nullable=False)
    email_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    email_available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    email_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AdminAudit(TimestampMixin, Base):
    __tablename__="admin_audit"
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True),primary_key=True,default=uuid4)
    actor_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True),ForeignKey("users.id",ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(40),nullable=False)
    target_type: Mapped[str] = mapped_column(String(24),nullable=False)
    target_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True),nullable=False)
    report_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True),ForeignKey("moderation_reports.id",ondelete="SET NULL"))
    details: Mapped[dict] = mapped_column(JSON,default=dict,nullable=False)

