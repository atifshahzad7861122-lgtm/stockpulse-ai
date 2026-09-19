"""Taxonomy models: categories → subcategories → micro_niches (docs: 08 §4).

Single-user: no user_id columns (see CHANGELOG 0.2.0 / CONTRACT.md §1.1).
Seed categories carry is_system=True (not user-deletable).
"""

from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import AuditTimestampsMixin, Base, SoftDeleteMixin, UUIDPrimaryKeyMixin
from app.schemas.enums import DataProvenance


def _prov_enum() -> SAEnum:
    return SAEnum(DataProvenance, native_enum=False, length=16)


class Category(Base, UUIDPrimaryKeyMixin, AuditTimestampsMixin, SoftDeleteMixin):
    """Top-level market category (e.g. Technology). Seed rows: 39, is_system=True."""

    __tablename__ = "categories"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(140), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    subcategories: Mapped[list[Subcategory]] = relationship(
        "Subcategory", back_populates="category", cascade="all, delete-orphan"
    )

    __table_args__ = (UniqueConstraint("slug", name="uq_categories_slug"),)


class Subcategory(Base, UUIDPrimaryKeyMixin, AuditTimestampsMixin, SoftDeleteMixin):
    """Second-level classification under a category (e.g. Artificial Intelligence)."""

    __tablename__ = "subcategories"

    category_id: Mapped[str] = mapped_column(ForeignKey("categories.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(140), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    category: Mapped[Category] = relationship("Category", back_populates="subcategories")
    micro_niches: Mapped[list[MicroNiche]] = relationship(
        "MicroNiche", back_populates="subcategory", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_subcategories_category", "category_id"),
        UniqueConstraint("category_id", "slug", name="uq_subcategories_category_slug"),
    )


class MicroNiche(Base, UUIDPrimaryKeyMixin, AuditTimestampsMixin, SoftDeleteMixin):
    """Fine-grained demand unit — the level at which scoring happens (docs: 15 §6)."""

    __tablename__ = "micro_niches"

    subcategory_id: Mapped[str] = mapped_column(ForeignKey("subcategories.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    demand_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    competition_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    data_provenance: Mapped[DataProvenance] = mapped_column(
        _prov_enum(), nullable=False, default=DataProvenance.ESTIMATED
    )
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    subcategory: Mapped[Subcategory] = relationship("Subcategory", back_populates="micro_niches")

    __table_args__ = (
        Index("idx_micro_niches_subcategory", "subcategory_id"),
        UniqueConstraint("subcategory_id", "slug", name="uq_micro_niches_subcategory_slug"),
    )
