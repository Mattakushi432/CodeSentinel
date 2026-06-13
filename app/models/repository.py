from __future__ import annotations

import secrets
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(Integer, ForeignKey("organizations.id"), nullable=False)
    git_host: Mapped[str] = mapped_column(String(20), nullable=False)  # github | gitlab | gitea
    repo_full_name: Mapped[str] = mapped_column(String(500), nullable=False)  # owner/repo
    base_url: Mapped[str | None] = mapped_column(String(500))  # for self-hosted instances
    access_token: Mapped[str | None] = mapped_column(String(1000))  # encrypted with Fernet if ENCRYPTION_KEY set
    webhook_secret: Mapped[str] = mapped_column(String(64), default=lambda: secrets.token_hex(32))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    organization: Mapped[Organization] = relationship(back_populates="repositories")
    review_jobs: Mapped[list[ReviewJob]] = relationship(back_populates="repository", lazy="select")

    @property
    def webhook_url_path(self) -> str:
        return f"/webhooks/{self.id}"

    def get_access_token(self) -> str | None:
        """Return decrypted access token."""
        if not self.access_token:
            return None
        from app.services.crypto import decrypt_token
        return decrypt_token(self.access_token) or None

    def set_access_token(self, plaintext: str | None) -> None:
        """Encrypt and store access token."""
        if not plaintext:
            self.access_token = None
            return
        from app.services.crypto import encrypt_token
        self.access_token = encrypt_token(plaintext)


from app.models.organization import Organization  # noqa: E402, F401
from app.models.review_job import ReviewJob  # noqa: E402, F401
