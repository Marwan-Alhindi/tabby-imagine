"""Demo data loaded into Supabase by `db/seed.py`.

Stands in for Tabby's catalog, payments, and account services. Installment
due dates are relative to the day you seed.
"""

from datetime import date, timedelta

CATEGORIES = {
    "mobiles": "Mobiles",
    "electronics": "Electronics",
    "travel": "Travel",
    "spa_salon": "Spa & Salon",
    "fashion": "Fashion",
    "beauty": "Beauty & Health",
}

STORES = [
    {"id": "jarir", "name": "Jarir Bookstore", "categories": ["mobiles", "electronics"], "cashback_pct": 2},
    {"id": "extra", "name": "eXtra", "categories": ["mobiles", "electronics"], "cashback_pct": 3},
    {"id": "noon", "name": "noon", "categories": ["mobiles", "electronics", "fashion", "beauty"], "cashback_pct": 5},
    {"id": "apple", "name": "Apple Store", "categories": ["mobiles", "electronics"], "cashback_pct": 0},
    {"id": "samsung", "name": "Samsung Store", "categories": ["mobiles", "electronics"], "cashback_pct": 4},
    {"id": "namshi", "name": "Namshi", "categories": ["fashion", "beauty"], "cashback_pct": 6},
    {"id": "almosafer", "name": "Almosafer", "categories": ["travel"], "cashback_pct": 3},
    {"id": "flyadeal", "name": "flyadeal", "categories": ["travel"], "cashback_pct": 2},
    {"id": "topspa", "name": "Top Spa", "categories": ["spa_salon"], "cashback_pct": 8},
    {"id": "in2", "name": "IN2 Fitness", "categories": ["spa_salon"], "cashback_pct": 5},
    {"id": "khalid_halabi", "name": "Khalid Halabi Jewellery", "categories": ["fashion"], "cashback_pct": 1},
]


def _p(id, name, brand, category, price, store, rating, specs, was=None):
    return {
        "id": id, "name": name, "brand": brand, "category": category,
        "price": price, "original_price": was, "store": store,
        "rating": rating, "specs": specs,
    }


PRODUCTS = [
    # Mobiles
    _p("m1", "iPhone 17 Pro Max 256GB", "Apple", "mobiles", 5299, "apple", 4.8, {"storage_gb": 256, "ram_gb": 12, "color": "Cosmic Orange", "screen_in": 6.9}),
    _p("m2", "iPhone 17 Pro Max 512GB", "Apple", "mobiles", 6299, "jarir", 4.8, {"storage_gb": 512, "ram_gb": 12, "color": "Deep Blue", "screen_in": 6.9}),
    _p("m3", "iPhone 17 Pro 256GB", "Apple", "mobiles", 4799, "extra", 4.7, {"storage_gb": 256, "ram_gb": 12, "color": "Silver", "screen_in": 6.3}),
    _p("m4", "iPhone 17 256GB", "Apple", "mobiles", 3799, "noon", 4.6, {"storage_gb": 256, "ram_gb": 8, "color": "Lavender", "screen_in": 6.3}),
    _p("m5", "iPhone 16 128GB", "Apple", "mobiles", 2699, "noon", 4.5, {"storage_gb": 128, "ram_gb": 8, "color": "Black", "screen_in": 6.1}, was=2999),
    _p("m6", "Galaxy S25 Ultra 256GB", "Samsung", "mobiles", 3699, "samsung", 4.7, {"storage_gb": 256, "ram_gb": 12, "color": "Titanium Gray", "screen_in": 6.9}, was=4299),
    _p("m7", "Galaxy S25 Ultra 512GB", "Samsung", "mobiles", 4499, "extra", 4.7, {"storage_gb": 512, "ram_gb": 12, "color": "Titanium Black", "screen_in": 6.9}),
    _p("m8", "Galaxy S25 256GB", "Samsung", "mobiles", 2999, "jarir", 4.5, {"storage_gb": 256, "ram_gb": 12, "color": "Icy Blue", "screen_in": 6.2}),
    _p("m9", "Galaxy A56 128GB", "Samsung", "mobiles", 1399, "noon", 4.3, {"storage_gb": 128, "ram_gb": 8, "color": "Awesome Graphite", "screen_in": 6.7}),
    _p("m10", "Galaxy Z Flip7 256GB", "Samsung", "mobiles", 4199, "samsung", 4.4, {"storage_gb": 256, "ram_gb": 12, "color": "Blue Shadow", "screen_in": 6.9}),
    _p("m11", "Pixel 10 Pro 256GB", "Google", "mobiles", 3899, "noon", 4.6, {"storage_gb": 256, "ram_gb": 16, "color": "Obsidian", "screen_in": 6.3}),
    _p("m12", "Xiaomi 15 512GB", "Xiaomi", "mobiles", 2899, "extra", 4.4, {"storage_gb": 512, "ram_gb": 12, "color": "Green", "screen_in": 6.4}),
    _p("m13", "HONOR Magic7 Pro 512GB", "HONOR", "mobiles", 3299, "jarir", 4.4, {"storage_gb": 512, "ram_gb": 12, "color": "Lunar Shadow Grey", "screen_in": 6.8}, was=3699),
    _p("m14", "HUAWEI Pura 80 Pro 512GB", "HUAWEI", "mobiles", 3999, "extra", 4.3, {"storage_gb": 512, "ram_gb": 12, "color": "Glazed Black", "screen_in": 6.8}),
    # Electronics
    _p("e1", "MacBook Air 13\" M4 16GB/512GB", "Apple", "electronics", 4999, "jarir", 4.8, {"storage_gb": 512, "ram_gb": 16, "color": "Sky Blue"}),
    _p("e2", "AirPods Pro 3", "Apple", "electronics", 999, "apple", 4.7, {"color": "White"}),
    _p("e3", "PlayStation 5 Slim Digital", "Sony", "electronics", 1799, "extra", 4.8, {"storage_gb": 1000, "color": "White"}, was=1999),
    _p("e4", "Samsung 65\" Neo QLED 4K TV", "Samsung", "electronics", 3499, "samsung", 4.5, {"screen_in": 65}, was=4199),
    _p("e5", "Dyson V15 Detect", "Dyson", "electronics", 2799, "noon", 4.6, {"color": "Nickel"}),
    _p("e6", "iPad Air 11\" M3 128GB", "Apple", "electronics", 2599, "jarir", 4.7, {"storage_gb": 128, "color": "Purple", "screen_in": 11}),
    # Travel
    _p("t1", "Riyadh to Dubai return flight + 3 nights hotel", "Almosafer", "travel", 2450, "almosafer", 4.5, {"nights": 3, "destination": "Dubai"}),
    _p("t2", "Jeddah to Istanbul return flight", "flyadeal", "travel", 1290, "flyadeal", 4.2, {"destination": "Istanbul"}, was=1590),
    _p("t3", "AlUla weekend package (2 nights)", "Almosafer", "travel", 3100, "almosafer", 4.7, {"nights": 2, "destination": "AlUla"}),
    # Spa & Salon
    _p("s1", "90-min Moroccan bath + massage", "Top Spa", "spa_salon", 450, "topspa", 4.6, {"duration_min": 90}, was=600),
    _p("s2", "IN2 Fitness 12-month membership", "IN2 Fitness", "spa_salon", 3200, "in2", 4.4, {"months": 12}),
    # Fashion & beauty
    _p("f1", "Men's linen shirt", "H&M", "fashion", 149, "namshi", 4.1, {"color": "Beige", "gender": "men"}),
    _p("f2", "Women's leather tote bag", "Charles & Keith", "fashion", 389, "namshi", 4.4, {"color": "Chalk", "gender": "women"}, was=459),
    _p("f3", "18K gold bracelet", "Khalid Halabi", "fashion", 2350, "khalid_halabi", 4.8, {"gender": "women"}),
    _p("b1", "Dior Sauvage EDP 100ml", "Dior", "beauty", 595, "noon", 4.8, {}),
]




_today = date.today()

ACCOUNT = {
    "name": "Mrwan",
    "phone": "+966 5X XXX 1234",
    "home_address": None,
    "profile_completion_pct": 40,
    "cashback_balance": 37.5,
    "referral": {"code": "MRWAN200", "reward_per_friend": 50, "max_reward": 200, "earned": 0},
    "credit_limit": 8000,
}

# Orders the user already paid with Tabby. Installments are mutated by actions.
ORDERS = [
    {
        "id": "ord_1001",
        "product": "AirPods Pro 3",
        "store": "Apple Store",
        "total": 999.0,
        "plan": "split_in_4",
        "installments": [
            {"id": "ins_1001_1", "amount": 249.75, "due": str(_today - timedelta(days=45)), "status": "paid"},
            {"id": "ins_1001_2", "amount": 249.75, "due": str(_today - timedelta(days=15)), "status": "paid"},
            {"id": "ins_1001_3", "amount": 249.75, "due": str(_today + timedelta(days=6)), "status": "upcoming"},
            {"id": "ins_1001_4", "amount": 249.75, "due": str(_today + timedelta(days=36)), "status": "upcoming"},
        ],
    }
]


