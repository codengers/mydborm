# =============================================================================
# File        : examples/query_builder_example.py
# Project     : mydborm - Lightweight ORM for MySQL and YugabyteDB
# Description : QueryBuilder demo — chaining where()/or_where(), operators
#               like __gt/__lt/__in, joins, group_by/having, subqueries,
#               ordering, pagination, and bulk update/delete via the
#               query builder (as opposed to BaseModel.update()/delete()).
# =============================================================================

from mydborm import db, BaseModel, IntField, StrField, FloatField, BoolField

db.configure(
    dialect  = "mysql",
    host     = "127.0.0.1",
    port     = 3307,
    user     = "root",
    password = "root",
    database = "testdb",
)


class QBCustomer(BaseModel):
    __tablename__ = "qb_customers"
    id      = IntField(primary_key=True)
    name    = StrField(max_length=100, nullable=False)
    country = StrField(max_length=2, nullable=False)
    vip     = BoolField(default=False)


class QBOrder(BaseModel):
    __tablename__ = "qb_orders"
    id          = IntField(primary_key=True)
    customer_id = IntField(nullable=False)
    total       = FloatField(nullable=False)
    shipped     = BoolField(default=False)


def main():
    print("=" * 60)
    print("  mydborm — QueryBuilder demo")
    print("=" * 60)

    QBCustomer.create_table()
    QBOrder.create_table()
    with db.connect() as conn:
        conn.cursor().execute("DELETE FROM qb_orders")
        conn.cursor().execute("DELETE FROM qb_customers")

    # ------------------------------------------------------------------ #
    #  Seed data                                                           #
    # ------------------------------------------------------------------ #
    alice = QBCustomer.create(name="Alice", country="US", vip=True)
    bob   = QBCustomer.create(name="Bob",   country="US", vip=False)
    carol = QBCustomer.create(name="Carol", country="UK", vip=True)

    for cust_id, total, shipped in [
        (alice, 250.0, True), (alice, 80.0, False),
        (bob,   15.0,  True),
        (carol, 500.0, True), (carol, 60.0, True),
    ]:
        QBOrder.create(customer_id=cust_id, total=total, shipped=shipped)

    # ------------------------------------------------------------------ #
    #  where() with operator suffixes — __gt, __lt, __in, __like         #
    # ------------------------------------------------------------------ #
    print("\n── Operator suffixes ───────────────────────────────────")

    big_orders = (QBOrder.query()
                          .where("total__gt", 100)
                          .order_by("total", desc=True)
                          .all())
    print(f"  Orders over $100: {[o['total'] for o in big_orders]}")

    us_or_uk = QBCustomer.query().where("country__in", ["US", "UK"]).all()
    print(f"  Customers in US/UK: {[c['name'] for c in us_or_uk]}")

    # ------------------------------------------------------------------ #
    #  or_where() — adds an OR group, AND'ed with the regular where()s    #
    # ------------------------------------------------------------------ #
    print("\n── or_where() ──────────────────────────────────────────")

    # or_where() calls OR together with each other, but that whole OR
    # group is AND'ed with any regular where() conditions. So this reads
    # as: "shipped orders, where the order is either over $400 OR
    # belongs to Bob" — not a simple "match either condition" union.
    flexible = (QBOrder.query()
                       .where("shipped", True)
                       .or_where("total__gt", 400)
                       .or_where("customer_id", bob)
                       .all())
    print(f"  Shipped, and (over $400 OR Bob's): "
          f"{[o['total'] for o in flexible]}")

    # ------------------------------------------------------------------ #
    #  join() — combine rows from two tables                              #
    # ------------------------------------------------------------------ #
    print("\n── Joins ───────────────────────────────────────────────")

    shipped_for_vips = (QBOrder.query()
                                .select("qb_orders.total", "qb_customers.name")
                                .inner_join("qb_customers",
                                            "qb_customers.id = qb_orders.customer_id")
                                .where("qb_customers.vip", True)
                                .where("qb_orders.shipped", True)
                                .all())
    print("  Shipped orders for VIP customers: " +
          str([(row["name"], row["total"]) for row in shipped_for_vips]))

    # ------------------------------------------------------------------ #
    #  group_by() + having() — aggregate, then filter on the aggregate    #
    # ------------------------------------------------------------------ #
    print("\n── Group by + having ───────────────────────────────────")

    big_spenders = (QBOrder.query()
                            .select("customer_id", "SUM(total) as spent")
                            .group_by("customer_id")
                            .having("SUM(total) > %s", 200)
                            .all())
    print("  Customers who spent over $200: " +
          str([(row["customer_id"], row["spent"]) for row in big_spenders]))

    # ------------------------------------------------------------------ #
    #  subquery() — use one query's result inside another                #
    # ------------------------------------------------------------------ #
    print("\n── Subquery ────────────────────────────────────────────")

    vip_ids = QBCustomer.query().where("vip", True).subquery("id")
    vip_orders = QBOrder.query().where(f"customer_id__in", vip_ids).all()
    print(f"  Orders belonging to VIP customers: {len(vip_orders)}")

    # ------------------------------------------------------------------ #
    #  paginate() — page through results                                  #
    # ------------------------------------------------------------------ #
    print("\n── Pagination ──────────────────────────────────────────")

    page = QBOrder.query().order_by("id").paginate(page=1, per_page=2)
    print(f"  Page {page['page']} of {page['pages']} "
          f"({page['total']} total rows): "
          f"{[o['total'] for o in page['data']]}")

    # ------------------------------------------------------------------ #
    #  Bulk update/delete via the query builder                           #
    # ------------------------------------------------------------------ #
    print("\n── Bulk update / delete via QueryBuilder ───────────────")

    updated = QBOrder.query().where("shipped", False).update(shipped=True)
    print(f"  Marked {updated} unshipped order(s) as shipped")

    deleted = QBOrder.query().where("total__lt", 20).delete()
    print(f"  Deleted {deleted} order(s) under $20")

    # ------------------------------------------------------------------ #
    #  Cleanup                                                             #
    # ------------------------------------------------------------------ #
    with db.connect() as conn:
        conn.cursor().execute("DELETE FROM qb_orders")
        conn.cursor().execute("DELETE FROM qb_customers")
        conn.cursor().execute("DROP TABLE qb_orders")
        conn.cursor().execute("DROP TABLE qb_customers")
    db.close()
    print("\n✔ Demo complete.\n")


if __name__ == "__main__":
    main()
