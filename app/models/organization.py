from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    reviews_this_month: Mapped[int] = mapped_column(Integer, default=0)
    reviews_month_key: Mapped[str | None] = mapped_column(String(7))  # "YYYY-MM"
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    owner: Mapped[User] = relationship(back_populates="organizations")
    repositories: Mapped[list[Repository]] = relationship(back_populates="organization", lazy="select")
    rules: Mapped[list[Rule]] = relationship(back_populates="organization", lazy="select")
    api_keys: Mapped[list[ApiKey]] = relationship(back_populates="organization", lazy="select")

    def increment_monthly_reviews(self) -> None:
        month_key = datetime.now(timezone.utc).strftime("%Y-%m")
        if self.reviews_month_key != month_key:
            self.reviews_this_month = 0
            self.reviews_month_key = month_key
        self.reviews_this_month += 1


from app.models.api_key import ApiKey  # noqa: E402, F401
from app.models.repository import Repository  # noqa: E402, F401
from app.models.rule import Rule  # noqa: E402, F401
from app.models.user import User  # noqa: E402, F401
