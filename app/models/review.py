from __future__ import annotations
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Integer, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(Integer, ForeignKey("review_jobs.id"), unique=True, nullable=False)
    issues_json: Mapped[list | None] = mapped_column(JSON)
    severity_high: Mapped[int] = mapped_column(Integer, default=0)
    severity_medium: Mapped[int] = mapped_column(Integer, default=0)
    severity_low: Mapped[int] = mapped_column(Integer, default=0)
    posted_comment_id: Mapped[str | None] = mapped_column(String(255))
    raw_llm_output: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    job: Mapped[ReviewJob] = relationship(back_populates="review")

    @property
    def total_issues(self) -> int:
        return self.severity_high + self.severity_medium + self.severity_low


from app.models.review_job import ReviewJob  # noqa: E402, F401
