from datetime import datetime, timedelta

from app.models.models import HangRail, RailPlacement, Store, WorkOrder


def make_store(db, name="测试门店"):
    s = Store(name=name)
    db.add(s)
    db.flush()
    return s


def make_rail(db, store, label="A 杆", length_cm=200.0):
    r = HangRail(store_id=store.id, label=label, length_cm=length_cm)
    db.add(r)
    db.flush()
    return r


def make_order(db, store, ticket, length_cm, status="ready"):
    o = WorkOrder(
        store_id=store.id,
        ticket_code=ticket,
        garment_name="测试衣物",
        length_cm=length_cm,
        status=status,
        due_at=datetime.utcnow() + timedelta(days=1),
    )
    db.add(o)
    db.flush()
    return o


def make_placement(db, rail, order, start_cm, end_cm, active=1):
    p = RailPlacement(
        rail_id=rail.id,
        order_id=order.id,
        start_cm=start_cm,
        end_cm=end_cm,
        active=active,
    )
    db.add(p)
    db.flush()
    return p
