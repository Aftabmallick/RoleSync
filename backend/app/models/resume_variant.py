import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base, PG_JSONB, PG_UUID


class ResumeVariant(Base):
    __tablename__ = "resume_variants"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    target_role: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    target_company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    __table_args__ = (
        Index("ix_resume_variants_user_target_role", "user_id", "target_role"),
    )

    user: Mapped["User"] = relationship("User")
    variant_bullets: Mapped[List["ResumeVariantBullet"]] = relationship(
        "ResumeVariantBullet",
        back_populates="variant",
        cascade="all, delete-orphan",
        order_by="ResumeVariantBullet.position",
    )

    @property
    def branch_name(self) -> str:
        """Alias for name conforming to roadmap persona branch terminology."""
        return self.name

    @branch_name.setter
    def branch_name(self, value: str) -> None:
        self.name = value

    @property
    def bullets(self) -> List["ResumeVariantBullet"]:
        """Alias for variant_bullets collection."""
        return self.variant_bullets

    def __repr__(self) -> str:
        return f"<ResumeVariant id={self.id} user_id={self.user_id} name='{self.name}'>"


class MasterBullet(Base):
    __tablename__ = "master_bullets"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    section: Mapped[str] = mapped_column(String(100), nullable=False)
    bullet_text: Mapped[str] = mapped_column(Text, nullable=False)
    metrics: Mapped[Optional[Dict[str, Any]]] = mapped_column(PG_JSONB, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    user: Mapped["User"] = relationship("User")
    variant_bullets: Mapped[List["ResumeVariantBullet"]] = relationship(
        "ResumeVariantBullet",
        back_populates="bullet",
        cascade="all, delete-orphan",
    )

    @property
    def raw_text(self) -> str:
        """Alias for bullet_text conforming to roadmap bullet schema."""
        return self.bullet_text

    @raw_text.setter
    def raw_text(self, value: str) -> None:
        self.bullet_text = value

    def __repr__(self) -> str:
        return f"<MasterBullet id={self.id} user_id={self.user_id} section='{self.section}'>"


class ResumeVariantBullet(Base):
    __tablename__ = "resume_variant_bullets"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID, primary_key=True, default=uuid.uuid4)
    variant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("resume_variants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    bullet_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("master_bullets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_tailored: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    tailored_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_resume_variant_bullets_variant_bullet", "variant_id", "bullet_id"),
    )

    variant: Mapped["ResumeVariant"] = relationship("ResumeVariant", back_populates="variant_bullets")
    bullet: Mapped["MasterBullet"] = relationship("MasterBullet", back_populates="variant_bullets")

    @property
    def position_order(self) -> int:
        """Alias for position conforming to roadmap positional ordering."""
        return self.position

    @position_order.setter
    def position_order(self, value: int) -> None:
        self.position = value

    def __repr__(self) -> str:
        return f"<ResumeVariantBullet id={self.id} variant_id={self.variant_id} bullet_id={self.bullet_id} pos={self.position}>"
