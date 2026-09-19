"""Metadata persistence: exactly one current row per asset, version chain."""

from __future__ import annotations

from app.models.production import Asset, MetadataRecord
from app.schemas.enums import AssetType


def _asset(db) -> Asset:
    asset = Asset(asset_type=AssetType.IMAGE, title="Metadata persistence asset")
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


def _row(db, asset_id: str, n: int, current: bool, title: str = "Title") -> MetadataRecord:
    row = MetadataRecord(
        asset_id=asset_id,
        version_number=n,
        title=title,
        keywords=["a", "b", "c"],
        is_current=current,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_exactly_one_current_row_per_asset(client, db):
    asset = _asset(db)
    _row(db, asset.id, 1, current=False)
    _row(db, asset.id, 2, current=True)

    r = client.get("/api/metadata", params={"asset_id": asset.id, "is_current": True})
    assert r.status_code == 200
    rows = r.json()["data"]
    assert len(rows) == 1
    assert rows[0]["version_number"] == 2
    assert rows[0]["is_current"] is True


def test_patch_creates_new_version_and_flips_current(client, db):
    asset = _asset(db)
    first = _row(db, asset.id, 1, current=True, title="Original title")

    r = client.patch(f"/api/metadata/{first.id}", json={"title": "Edited title"})
    assert r.status_code == 200
    body = r.json()
    assert body["version_number"] == 2
    assert body["title"] == "Edited title"
    assert body["is_current"] is True

    # Prior row flipped off.
    r = client.get(f"/api/metadata/{first.id}")
    assert r.json()["is_current"] is False

    # Still exactly one current row.
    current = db.query(MetadataRecord).filter_by(asset_id=asset.id, is_current=True).all()
    assert len(current) == 1


def test_new_version_increments_from_max(client, db):
    asset = _asset(db)
    _row(db, asset.id, 1, current=False)
    _row(db, asset.id, 2, current=False)
    third = _row(db, asset.id, 3, current=True)

    r = client.patch(f"/api/metadata/{third.id}", json={"title": "Fourth"})
    assert r.status_code == 200
    assert r.json()["version_number"] == 4
