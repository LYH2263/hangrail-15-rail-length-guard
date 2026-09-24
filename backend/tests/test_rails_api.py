from datetime import datetime, timedelta

from app.models.models import HangRail, RailPlacement, Store, WorkOrder


def _store_rail(session_factory, length_cm=100.0):
    db = session_factory()
    store = Store(name="测试门店")
    db.add(store)
    db.flush()
    rail = HangRail(store_id=store.id, label="T 杆", length_cm=length_cm)
    db.add(rail)
    db.commit()
    ids = (store.id, rail.id)
    db.close()
    return ids


def _order(session_factory, store_id, code, length_cm, status="ready"):
    db = session_factory()
    order = WorkOrder(
        store_id=store_id,
        ticket_code=code,
        garment_name="测试衣物",
        length_cm=length_cm,
        status=status,
        due_at=datetime.utcnow() + timedelta(days=1),
    )
    db.add(order)
    db.commit()
    oid = order.id
    db.close()
    return oid


def _placement(session_factory, rail_id, order_id, start_cm, end_cm, active=1):
    db = session_factory()
    db.add(
        RailPlacement(
            rail_id=rail_id,
            order_id=order_id,
            start_cm=start_cm,
            end_cm=end_cm,
            active=active,
        )
    )
    db.commit()
    db.close()


def _rail_length(session_factory, rail_id):
    db = session_factory()
    length = db.get(HangRail, rail_id).length_cm
    db.close()
    return length


def test_shrink_below_active_placement_rejected(client, db_session_factory):
    store_id, rail_id = _store_rail(db_session_factory, length_cm=100)
    order_id = _order(db_session_factory, store_id, "HR-T01", length_cm=60, status="hung")
    _placement(db_session_factory, rail_id, order_id, 0, 60)

    resp = client.patch(f"/api/rails/{rail_id}", json={"length_cm": 50})

    assert resp.status_code == 409
    assert "60" in resp.json()["detail"]
    # 数据库中的原长度不变
    assert _rail_length(db_session_factory, rail_id) == 100
    # 已有占位起止厘米不改写
    db = db_session_factory()
    p = db.query(RailPlacement).filter_by(rail_id=rail_id, active=1).one()
    assert (p.start_cm, p.end_cm) == (0, 60)
    db.close()


def test_shrink_without_placements_allowed(client, db_session_factory):
    _, rail_id = _store_rail(db_session_factory, length_cm=100)

    resp = client.patch(f"/api/rails/{rail_id}", json={"length_cm": 60})

    assert resp.status_code == 200
    assert resp.json()["length_cm"] == 60
    assert _rail_length(db_session_factory, rail_id) == 60


def test_shrink_to_active_placement_end_boundary_allowed(client, db_session_factory):
    store_id, rail_id = _store_rail(db_session_factory, length_cm=100)
    order_id = _order(db_session_factory, store_id, "HR-T02", length_cm=60, status="hung")
    _placement(db_session_factory, rail_id, order_id, 0, 60)

    resp = client.patch(f"/api/rails/{rail_id}", json={"length_cm": 60})

    assert resp.status_code == 200
    assert resp.json()["length_cm"] == 60


def test_inactive_placement_does_not_block_shrink(client, db_session_factory):
    store_id, rail_id = _store_rail(db_session_factory, length_cm=200)
    order_id = _order(db_session_factory, store_id, "HR-T03", length_cm=150, status="picked")
    _placement(db_session_factory, rail_id, order_id, 0, 150, active=0)

    resp = client.patch(f"/api/rails/{rail_id}", json={"length_cm": 80})

    assert resp.status_code == 200
    assert resp.json()["length_cm"] == 80


def test_oversized_garment_rejected_by_new_length_after_shrink(client, db_session_factory):
    store_id, rail_id = _store_rail(db_session_factory, length_cm=100)
    hung_id = _order(db_session_factory, store_id, "HR-T04", length_cm=40, status="hung")
    _placement(db_session_factory, rail_id, hung_id, 0, 40)
    assert client.patch(f"/api/rails/{rail_id}", json={"length_cm": 60}).status_code == 200

    # 50cm 衣物在旧杆长 100 时本可放入 40-90 的空隙；缩短后仅剩 40-60，必须拒绝
    long_id = _order(db_session_factory, store_id, "HR-T05", length_cm=50)
    resp = client.post("/api/hang", json={"order_id": long_id, "rail_id": rail_id})
    assert resp.status_code == 409

    db = db_session_factory()
    assert db.query(RailPlacement).filter_by(rail_id=rail_id, active=1).count() == 1
    db.close()

    # 20cm 衣物仍能按新杆长落入 40-60 空隙
    fit_id = _order(db_session_factory, store_id, "HR-T06", length_cm=20)
    resp = client.post("/api/hang", json={"order_id": fit_id, "rail_id": rail_id})
    assert resp.status_code == 200
    db = db_session_factory()
    p = db.query(RailPlacement).filter_by(order_id=fit_id, active=1).one()
    assert (p.start_cm, p.end_cm) == (40, 60)
    db.close()
