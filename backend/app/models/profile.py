import uuid
from datetime import datetime
from sqlalchemy import Integer, Boolean, DateTime, ForeignKey, LargeBinary
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base, PG_UUID


class MasterProfile(Base):
    __tablename__ = "master_profiles"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    encrypted_profile_data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    encryption_iv: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="master_profiles")
