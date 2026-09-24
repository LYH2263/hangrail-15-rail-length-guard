"""杆长编辑：越界拒绝 / 可缩短 / 缩短后 first-fit 按新长计算。"""

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models.models import HangRail, RailPlacement
from tests.factories import make_order, make_placement, make_rail, make_store


def patch_length(client: TestClient, rail_id: int, length_cm: float):
    return client.patch(f"/api/rails/{rail_id}", json={"length_cm": length_cm})


def test_shrink_rejected_when_placement_out_of_range(client, db_session):
    store = make_store(db_session)
    rail = make_rail(db_session, store, length_cm=200.0)
    order = make_order(db_session, store, "HR-9001", 60.0, status="hung")
    p = make_placement(db_session, rail, order, 100.0, 160.0)
    rail_id, p_id = rail.id, p.id
    db_session.commit()

    # 最大 active end_cm = 160，缩到 150 必须被拒绝
    resp = patch_length(client, rail.id, 150.0)
    assert resp.status_code == 400
    assert "160" in resp.json()["detail"]

    # 数据库中原长度不变，且已有占位起止厘米不改写
    db_session.expunge_all()
    rail_row = db_session.get(HangRail, rail_id)
    assert rail_row.length_cm == 200.0
    p_row = db_session.get(RailPlacement, p_id)
    assert (p_row.start_cm, p_row.end_cm) == (100.0, 160.0)


def test_shrink_ok_with_no_placements(client, db_session):
    store = make_store(db_session)
    rail = make_rail(db_session, store, length_cm=200.0)
    db_session.commit()

    # 无任何占位：可随意缩短
    resp = patch_length(client, rail.id, 120.0)
    assert resp.status_code == 200
    assert resp.json()["length_cm"] == 120.0

    db_session.expunge_all()
    assert db_session.get(HangRail, rail.id).length_cm == 120.0


def test_shrink_ok_when_within_active_occupancy(client, db_session):
    store = make_store(db_session)
    rail = make_rail(db_session, store, length_cm=200.0)
    order = make_order(db_session, store, "HR-9002", 40.0, status="hung")
    make_placement(db_session, rail, order, 0.0, 40.0)
    db_session.commit()

    # 缩短到恰好等于最大 end_cm 也应成功
    resp = patch_length(client, rail.id, 40.0)
    assert resp.status_code == 200
    assert resp.json()["length_cm"] == 40.0


def test_inactive_placement_does_not_block_shrink(client, db_session):
    store = make_store(db_session)
    rail = make_rail(db_session, store, length_cm=200.0)
    order = make_order(db_session, store, "HR-9003", 60.0, status="picked")
    make_placement(db_session, rail, order, 100.0, 160.0, active=0)
    db_session.commit()

    # inactive 占位（已取件）不参与约束
    resp = patch_length(client, rail.id, 80.0)
    assert resp.status_code == 200
    assert resp.json()["length_cm"] == 80.0


def test_shrink_then_oversized_garment_rejected_by_new_length(client, db_session):
    store = make_store(db_session)
    rail = make_rail(db_session, store, length_cm=200.0)
    db_session.commit()

    assert patch_length(client, rail.id, 100.0).status_code == 200

    # 衣长 120 > 新杆长 100：first_fit 直接返回 None，上杆被拒
    long_order = make_order(db_session, store, "HR-9100", 120.0, status="ready")
    db_session.commit()
    resp = client.post("/api/hang", json={"order_id": long_order.id, "rail_id": rail.id})
    assert resp.status_code == 409

    # 未产生任何占位
    assert db_session.scalar(select(RailPlacement)) is None
    db_session.expunge_all()
    assert db_session.get(HangRail, rail.id).length_cm == 100.0


def test_shrink_then_first_fit_uses_new_gaps(client, db_session):
    store = make_store(db_session)
    rail = make_rail(db_session, store, length_cm=200.0)
    hung = make_order(db_session, store, "HR-9200", 60.0, status="hung")
    make_placement(db_session, rail, hung, 0.0, 60.0)
    db_session.commit()

    # 缩到 90：尾隙仅 30cm（旧长度下尾隙有 140cm）
    assert patch_length(client, rail.id, 90.0).status_code == 200

    too_long = make_order(db_session, store, "HR-9201", 40.0, status="ready")
    db_session.commit()
    # 40cm 的衣服在 30cm 尾隙中放不下 -> 按新杆长拒绝
    resp = client.post("/api/hang", json={"order_id": too_long.id, "rail_id": rail.id})
    assert resp.status_code == 409

    fits = make_order(db_session, store, "HR-9202", 30.0, status="ready")
    db_session.commit()
    resp = client.post("/api/hang", json={"order_id": fits.id, "rail_id": rail.id})
    assert resp.status_code == 200

    fits_id, hung_id = fits.id, hung.id
    # 新占位落在 60-90，且旧占位起止未被改写
    db_session.expunge_all()
    placed = db_session.scalars(
        select(RailPlacement).where(RailPlacement.order_id == fits_id, RailPlacement.active == 1)
    ).one()
    assert (placed.start_cm, placed.end_cm) == (60.0, 90.0)
    old = db_session.scalars(
        select(RailPlacement).where(RailPlacement.order_id == hung_id)
    ).one()
    assert (old.start_cm, old.end_cm) == (0.0, 60.0)


def test_extend_always_allowed(client, db_session):
    store = make_store(db_session)
    rail = make_rail(db_session, store, length_cm=100.0)
    order = make_order(db_session, store, "HR-9300", 40.0, status="hung")
    make_placement(db_session, rail, order, 0.0, 40.0)
    db_session.commit()

    resp = patch_length(client, rail.id, 220.0)
    assert resp.status_code == 200
    assert resp.json()["length_cm"] == 220.0


def test_shrink_nonexistent_rail_404(client):
    assert patch_length(client, 9999, 100.0).status_code == 404


def test_shrink_invalid_length_rejected(client, db_session):
    store = make_store(db_session)
    rail = make_rail(db_session, store, length_cm=100.0)
    db_session.commit()

    assert patch_length(client, rail.id, 0).status_code == 422
    assert patch_length(client, rail.id, -5).status_code == 422
