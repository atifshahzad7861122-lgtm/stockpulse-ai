"""DB-level invariants: settings key uniqueness, one current metadata row per asset."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.production import Asset, MetadataRecord
from app.models.settings import Setting
from app.schemas.enums import AssetType


def test_settings_key_unique(db):
    db.add(Setting(key="theme", value={"mode": "dark"}))
    db.commit()
    db.add(Setting(key="theme", value={"mode": "light"}))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_metadata_current_row_unique_per_asset(db):
    asset = Asset(asset_type=AssetType.IMAGE, title="constraint asset")
    db.add(asset)
    db.commit()

    db.add(
        MetadataRecord(
            asset_id=asset.id,
            version_number=1,
            title="v1",
            keywords=["a"],
            is_current=True,
        )
    )
    db.commit()

    db.add(
        MetadataRecord(
            asset_id=asset.id,
            version_number=2,
            title="v2",
            keywords=["a"],
            is_current=True,
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

    # Two non-current rows are fine.
    db.add(
        MetadataRecord(
            asset_id=asset.id,
            version_number=2,
            title="v2",
            keywords=["a"],
            is_current=False,
        )
    )
    db.commit()
    assert db.query(MetadataRecord).filter_by(asset_id=asset.id).count() == 2
