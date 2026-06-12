from __future__ import annotations
import secrets
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(Integer, ForeignKey("organizations.id"), nullable=False)
    git_host: Mapped[str] = mapped_column(String(20), nullable=False)  # github | gitlab | gitea
    repo_full_name: Mapped[str] = mapped_column(String(500), nullable=False)  # owner/repo
    base_url: Mapped[str | None] = mapped_column(String(500))  # for self-hosted instances
    access_token: Mapped[str | None] = mapped_column(String(500))
    webhook_secret: Mapped[str] = mapped_column(String(64), default=lambda: secrets.token_hex(32))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    organization: Mapped[Organization] = relationship(back_populates="repositories")
    review_jobs: Mapped[list[ReviewJob]] = relationship(back_populates="repository", lazy="select")

    @property
    def webhook_url_path(self) -> str:
        return f"/webhooks/{self.id}"


from app.models.organization import Organization  # noqa: E402, F401
from app.models.review_job import ReviewJob  # noqa: E402, F401
