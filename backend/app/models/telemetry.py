import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base, PG_UUID, PG_JSONB


class SelectorDriftEvent(Base):
    __tablename__ = "selector_drift_events"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID, primary_key=True, default=uuid.uuid4)
    report_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    host: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    ats_provider: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    failed_selectors: Mapped[list] = mapped_column(PG_JSONB, default=list, nullable=False)
    summary: Mapped[dict] = mapped_column(PG_JSONB, default=dict, nullable=False)
    client_version: Mapped[str] = mapped_column(String(32), default="2.0.0", nullable=False)
    timestamp: Mapped[str] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("idx_drift_provider_host", "ats_provider", "host"),
    )

