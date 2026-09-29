"""Create the schema and load demo data into Supabase Postgres.

    uv run python -m db.seed        (needs SUPABASE_DB_URL in .env)
"""

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.types.json import Jsonb

from app import seed_data as d

load_dotenv()
ACCOUNT_ID = "demo"


def main():
    with psycopg.connect(os.environ["SUPABASE_DB_URL"]) as conn, conn.cursor() as cur:
        cur.execute((Path(__file__).parent / "schema.sql").read_text())
        cur.executemany("insert into categories values (%s, %s)", list(d.CATEGORIES.items()))
        cur.executemany(
            "insert into stores values (%(id)s, %(name)s, %(categories)s, %(cashback_pct)s)", d.STORES)
        cur.executemany(
            """insert into products (id, name, brand, category, store_id, price, original_price, rating, specs)
               values (%(id)s, %(name)s, %(brand)s, %(category)s, %(store)s, %(price)s, %(original_price)s, %(rating)s, %(specs)s)""",
            [{**p, "specs": Jsonb(p["specs"])} for p in d.PRODUCTS])
        a = d.ACCOUNT
        cur.execute(
            "insert into accounts values (%s, %s, %s, %s, %s, %s, %s, %s)",
            (ACCOUNT_ID, a["name"], a["phone"], None, a["profile_completion_pct"],
             a["cashback_balance"], a["credit_limit"], Jsonb(a["referral"])))
        for o in d.ORDERS:
            cur.execute("insert into orders (id, account_id, product, store, total, plan) values (%s, %s, %s, %s, %s, %s)",
                        (o["id"], ACCOUNT_ID, o["product"], o["store"], o["total"], o["plan"]))
            cur.executemany(
                "insert into installments (id, order_id, seq, amount, due, status) values (%s, %s, %s, %s, %s, %s)",
                [(i["id"], o["id"], n + 1, i["amount"], i["due"], i["status"]) for n, i in enumerate(o["installments"])])
    print(f"Seeded {len(d.PRODUCTS)} products, {len(d.STORES)} stores, {len(d.ORDERS)} orders.")


if __name__ == "__main__":
    main()
