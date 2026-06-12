from __future__ import annotations
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    plan: Mapped[str] = mapped_column(String(20), default="free")
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    owner: Mapped[User] = relationship(back_populates="organizations")
    repositories: Mapped[list[Repository]] = relationship(back_populates="organization", lazy="select")
    rules: Mapped[list[Rule]] = relationship(back_populates="organization", lazy="select")
    api_keys: Mapped[list[ApiKey]] = relationship(back_populates="organization", lazy="select")

    @property
    def repo_limit(self) -> int:
        return {"free": 1, "pro": 5, "team": 999}.get(self.plan, 1)


from app.models.user import User  # noqa: E402, F401
from app.models.repository import Repository  # noqa: E402, F401
from app.models.rule import Rule  # noqa: E402, F401
from app.models.api_key import ApiKey  # noqa: E402, F401
