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



# Saved cards. The Visa expired last month: the story behind "why does my Visa fail?".
PAYMENT_METHODS = [
    {"id": "pm_mada", "brand": "mada", "last4": "4821", "exp_month": 3, "exp_year": 2029, "is_default": True},
    {"id": "pm_visa", "brand": "visa", "last4": "1177", "exp_month": 8, "exp_year": 2026, "is_default": False},
]

PAYMENT_ATTEMPTS = [
    {"id": "pa_1", "method_id": "pm_mada", "installment_id": "ins_1001_1", "amount": 249.75,
     "status": "succeeded", "failure_code": None, "days_ago": 45},
    {"id": "pa_2", "method_id": "pm_mada", "installment_id": "ins_1001_2", "amount": 249.75,
     "status": "succeeded", "failure_code": None, "days_ago": 15},
    {"id": "pa_3", "method_id": "pm_visa", "installment_id": "ins_1001_3", "amount": 249.75,
     "status": "failed", "failure_code": "expired_card", "days_ago": 1},
]

# Illustrative help-center content for the demo (not Tabby's official policy text).
HELP_ARTICLES = [
    ("card-declined", "Payment methods", "Why was my card declined?",
     "Common reasons a card is declined: the card has expired; insufficient balance; the bank blocked online or "
     "international transactions; 3-D Secure (OTP) verification failed or timed out; or the card type is not "
     "supported (some prepaid and virtual cards). Fix: update the expiry date or add a new card, make sure online "
     "payments are enabled with your bank, and retry. If the bank shows no attempt, contact Tabby support."),
    ("payment-methods", "Payment methods", "Which payment methods can I use?",
     "Tabby accepts mada, Visa, Mastercard and Apple Pay. You can save several cards and choose a default card; "
     "upcoming installments are charged to the default card automatically on the due date."),
    ("change-card", "Payment methods", "How do I change my default card?",
     "Go to Profile > Payment methods, add a card or pick an existing one, and set it as default. Future "
     "installments for all your orders are charged to the new default card."),
    ("pay-early", "Payments", "Can I pay an installment early?",
     "Yes. Open Payments, choose the installment and tap Pay. Paying early has no extra fees and frees up your "
     "spending limit straight away."),
    ("missed-payment", "Payments", "What happens if I miss a payment?",
     "We retry the charge and send reminders. While an installment is overdue you can't make new purchases with "
     "Tabby. Paying the overdue amount restores your account; repeated late payments can lower your spending limit."),
    ("spending-limit", "Account", "How is my spending limit decided and how can I increase it?",
     "Your limit depends on your payment history with Tabby, your verified identity, and your current outstanding "
     "balance. Paying on time, completing your profile and verifying your identity help increase it. The amount "
     "you still owe on open orders is deducted from your available limit."),
    ("order-declined", "Shopping", "Why was my order declined at checkout?",
     "An order can be declined when it exceeds your available limit, when you have an overdue installment, when "
     "your default card can't be charged, when your identity isn't verified, or when the amount is outside the plan "
     "range (split in 4 up to 5,000 SAR; monthly plans from 500 to 50,000 SAR)."),
    ("plans", "Shopping", "What payment plans does Tabby offer?",
     "Split in 4: four equal interest-free payments, the first today and the rest monthly, for purchases up to "
     "5,000 SAR. Monthly plans: 6 or 12 months for purchases from 500 to 50,000 SAR; the 12-month plan includes a "
     "fee shown before you confirm."),
    ("refunds", "Shopping", "How do refunds and returns work?",
     "Return the item through the store's return policy. Once the store processes the refund, Tabby reduces your "
     "remaining installments; any amount you already paid beyond the new total is refunded to your card within "
     "5-10 business days."),
    ("cashback", "Rewards", "How does cashback work?",
     "Stores show a cashback percentage. After the store confirms your order, the cashback is added to your "
     "balance and is used automatically on your next Tabby payment."),
    ("referrals", "Rewards", "How do referral rewards work?",
     "Share your invite link. You earn 50 SAR for each friend who signs up and completes their first purchase, "
     "up to 200 SAR."),
    ("contact-support", "Support", "How do I contact support or dispute a charge?",
     "Chat with the assistant first; if the issue needs a person, it can open a support ticket for you and an "
     "agent will reply in the app, usually within 24 hours. For a disputed charge, include the order and the amount."),
]
