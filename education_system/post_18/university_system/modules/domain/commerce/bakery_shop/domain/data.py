"""DataMixin — auto-split from bakery_shop.py."""
from education_system.post_18.university_system.modules.domain.commerce.bakery_shop._common import *  # noqa: F401,F403


class DataMixin:
    def _connect(self):
        from education_system.post_18.university_system.infrastructure.database.db import get_connection
        return get_connection()

    def _ensure_schema(self):
        conn = self._connect()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS bakery_orders (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id     TEXT,
                    timestamp    TEXT NOT NULL,
                    username     TEXT,
                    user_type    TEXT,
                    items_json   TEXT NOT NULL,
                    subtotal     REAL,
                    discount     REAL,
                    total        REAL,
                    payment_method   TEXT,
                    refunded         INTEGER DEFAULT 0,
                    refund_ref       TEXT,
                    refund_timestamp TEXT
                )
            """)
            # Idempotent migration for pre-existing installs.
            existing = {row[1] for row in conn.execute("PRAGMA table_info(bakery_orders)")}
            for col, ddl in (
                ("payment_method",   "TEXT"),
                ("refunded",         "INTEGER DEFAULT 0"),
                ("refund_ref",       "TEXT"),
                ("refund_timestamp", "TEXT"),
                ("promo_code",       "TEXT"),
                ("loyalty_earned",   "INTEGER DEFAULT 0"),
                ("loyalty_redeemed", "INTEGER DEFAULT 0"),
                ("discount_breakdown_json", "TEXT"),
                ("tip_amount",       "REAL DEFAULT 0"),
                ("vat_amount",       "REAL DEFAULT 0"),
                ("split_payments_json", "TEXT"),
                ("billing_code",     "TEXT"),
                ("gift_card_code",   "TEXT"),
            ):
                if col not in existing:
                    conn.execute(f"ALTER TABLE bakery_orders ADD COLUMN {col} {ddl}")

            # ---- Phase-1 feature tables ----
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS bakery_loyalty (
                    user TEXT PRIMARY KEY,
                    points INTEGER DEFAULT 0,
                    lifetime_points INTEGER DEFAULT 0,
                    updated_at TEXT
                );
                CREATE TABLE IF NOT EXISTS bakery_punch_cards (
                    user TEXT NOT NULL,
                    category TEXT NOT NULL,
                    count INTEGER DEFAULT 0,
                    redemptions INTEGER DEFAULT 0,
                    updated_at TEXT,
                    PRIMARY KEY (user, category)
                );
                CREATE TABLE IF NOT EXISTS bakery_promo_codes (
                    code TEXT PRIMARY KEY,
                    description TEXT,
                    discount_type TEXT NOT NULL,    -- 'percent' or 'fixed'
                    discount_value REAL NOT NULL,
                    min_subtotal REAL DEFAULT 0,
                    expiry_date TEXT,
                    max_uses INTEGER,
                    current_uses INTEGER DEFAULT 0,
                    active INTEGER DEFAULT 1,
                    created_at TEXT
                );
                CREATE TABLE IF NOT EXISTS bakery_promo_redemptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT,
                    user TEXT,
                    order_id TEXT,
                    amount_off REAL,
                    timestamp TEXT
                );
                CREATE TABLE IF NOT EXISTS bakery_happy_hours (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    start_time TEXT NOT NULL,   -- HH:MM
                    end_time TEXT NOT NULL,     -- HH:MM
                    days_of_week TEXT,          -- CSV of Mon..Sun or 'all'
                    category TEXT,              -- 'all' or a product category
                    discount_pct REAL NOT NULL,
                    active INTEGER DEFAULT 1,
                    created_at TEXT
                );
                CREATE TABLE IF NOT EXISTS bakery_combos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    items_json TEXT NOT NULL,   -- {"item": qty, ...}
                    combo_price REAL NOT NULL,
                    description TEXT,
                    active INTEGER DEFAULT 1,
                    created_at TEXT
                );
                CREATE TABLE IF NOT EXISTS bakery_referrals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    referrer TEXT NOT NULL,
                    referee TEXT NOT NULL UNIQUE,
                    status TEXT DEFAULT 'pending',  -- pending/redeemed
                    bonus_referrer REAL DEFAULT 0,
                    bonus_referee  REAL DEFAULT 0,
                    created_at TEXT,
                    redeemed_at TEXT
                );
                CREATE TABLE IF NOT EXISTS bakery_first_purchase_claims (
                    user TEXT PRIMARY KEY,
                    claimed_at TEXT
                );
                CREATE TABLE IF NOT EXISTS bakery_birthday_claims (
                    user TEXT NOT NULL,
                    year INTEGER NOT NULL,
                    claimed_at TEXT,
                    PRIMARY KEY (user, year)
                );

                /* ---- Phase-2 inventory / reviews tables ---- */
                CREATE TABLE IF NOT EXISTS bakery_suppliers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    contact TEXT,
                    email TEXT,
                    phone TEXT,
                    lead_time_days INTEGER DEFAULT 3,
                    active INTEGER DEFAULT 1,
                    created_at TEXT
                );
                CREATE TABLE IF NOT EXISTS bakery_purchase_orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    po_number TEXT UNIQUE NOT NULL,
                    supplier_id INTEGER,
                    status TEXT DEFAULT 'draft',  -- draft / sent / received / cancelled
                    items_json TEXT NOT NULL,
                    created_at TEXT,
                    expected_delivery TEXT,
                    received_at TEXT,
                    total_cost REAL,
                    created_by TEXT,
                    notes TEXT
                );
                CREATE TABLE IF NOT EXISTS bakery_reorder_rules (
                    item_name TEXT PRIMARY KEY,
                    min_stock INTEGER NOT NULL,
                    reorder_qty INTEGER NOT NULL,
                    supplier_id INTEGER,
                    unit_cost REAL,
                    auto INTEGER DEFAULT 0,
                    updated_at TEXT
                );
                CREATE TABLE IF NOT EXISTS bakery_stock_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_name TEXT NOT NULL,
                    threshold INTEGER,
                    current_stock INTEGER,
                    triggered_at TEXT,
                    acknowledged INTEGER DEFAULT 0,
                    acknowledged_by TEXT,
                    acknowledged_at TEXT,
                    notes TEXT
                );
                CREATE TABLE IF NOT EXISTS bakery_batches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_name TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    initial_quantity INTEGER,
                    expiry_date TEXT NOT NULL,
                    received_date TEXT,
                    lot_number TEXT,
                    supplier_id INTEGER,
                    po_id INTEGER,
                    status TEXT DEFAULT 'active'   -- active / expired / depleted
                );
                CREATE TABLE IF NOT EXISTS bakery_reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_name TEXT NOT NULL,
                    user TEXT,
                    rating INTEGER NOT NULL,
                    comment TEXT,
                    timestamp TEXT,
                    verified_purchase INTEGER DEFAULT 0
                );

                /* ---- Phase-3 ordering / favourites / currency ---- */
                CREATE TABLE IF NOT EXISTS bakery_preorders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id TEXT UNIQUE,
                    user TEXT NOT NULL,
                    user_type TEXT,
                    items_json TEXT NOT NULL,
                    collection_time TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    notes TEXT,
                    subtotal REAL,
                    discount REAL,
                    total REAL,
                    payment_method TEXT,
                    paid INTEGER DEFAULT 0,
                    created_at TEXT
                );
                CREATE TABLE IF NOT EXISTS bakery_custom_orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user TEXT NOT NULL,
                    cake_type TEXT,
                    size TEXT,
                    flavours TEXT,
                    message_on_cake TEXT,
                    dietary_requirements TEXT,
                    collection_date TEXT NOT NULL,
                    contact_email TEXT,
                    contact_phone TEXT,
                    quoted_price REAL,
                    status TEXT DEFAULT 'requested',
                    admin_notes TEXT,
                    created_at TEXT,
                    updated_at TEXT
                );
                CREATE TABLE IF NOT EXISTS bakery_bulk_orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user TEXT NOT NULL,
                    department TEXT,
                    billing_code TEXT,
                    items_json TEXT NOT NULL,
                    event_date TEXT NOT NULL,
                    event_location TEXT,
                    attendees INTEGER,
                    total REAL,
                    status TEXT DEFAULT 'submitted',
                    notes TEXT,
                    created_at TEXT,
                    updated_at TEXT
                );
                CREATE TABLE IF NOT EXISTS bakery_favourites (
                    user TEXT NOT NULL,
                    item_name TEXT NOT NULL,
                    added_at TEXT,
                    PRIMARY KEY (user, item_name)
                );
                CREATE TABLE IF NOT EXISTS bakery_recurring_orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user TEXT NOT NULL,
                    name TEXT,
                    items_json TEXT NOT NULL,
                    schedule TEXT NOT NULL,
                    next_run TEXT,
                    last_run TEXT,
                    active INTEGER DEFAULT 1,
                    created_at TEXT
                );
                CREATE TABLE IF NOT EXISTS bakery_saved_carts (
                    user TEXT PRIMARY KEY,
                    items_json TEXT NOT NULL,
                    saved_at TEXT
                );
                CREATE TABLE IF NOT EXISTS bakery_currency_rates (
                    currency TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    rate_from_gbp REAL NOT NULL,
                    updated_at TEXT
                );

                /* ---- Phase-4 payments / refunds tables ---- */
                CREATE TABLE IF NOT EXISTS bakery_gift_cards (
                    code TEXT PRIMARY KEY,
                    initial_balance REAL NOT NULL,
                    balance REAL NOT NULL,
                    issued_to TEXT,
                    expiry TEXT,
                    active INTEGER DEFAULT 1,
                    notes TEXT,
                    created_at TEXT,
                    created_by TEXT
                );
                CREATE TABLE IF NOT EXISTS bakery_gift_card_txns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL,
                    txn_type TEXT NOT NULL,   -- issue / redeem / topup / refund
                    amount REAL NOT NULL,
                    order_id TEXT,
                    user TEXT,
                    timestamp TEXT,
                    notes TEXT
                );
                CREATE TABLE IF NOT EXISTS bakery_tips (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id TEXT NOT NULL,
                    amount REAL NOT NULL,
                    user TEXT,
                    recipient TEXT,
                    timestamp TEXT
                );
                CREATE TABLE IF NOT EXISTS bakery_billing_codes (
                    code TEXT PRIMARY KEY,
                    department TEXT,
                    contact TEXT,
                    contact_email TEXT,
                    active INTEGER DEFAULT 1,
                    created_at TEXT
                );
                CREATE TABLE IF NOT EXISTS bakery_cash_drawer (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    opened_at TEXT NOT NULL,
                    opening_float REAL NOT NULL,
                    closed_at TEXT,
                    closing_amount REAL,
                    expected_amount REAL,
                    variance REAL,
                    operator TEXT,
                    status TEXT DEFAULT 'open',  -- open / closed
                    notes TEXT
                );
                CREATE TABLE IF NOT EXISTS bakery_refund_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id TEXT NOT NULL,
                    user TEXT,
                    reason TEXT NOT NULL,
                    reason_category TEXT,
                    items_json TEXT,
                    requested_amount REAL,
                    status TEXT DEFAULT 'pending',  -- pending / approved / rejected
                    admin_notes TEXT,
                    handled_by TEXT,
                    created_at TEXT,
                    updated_at TEXT
                );
                CREATE TABLE IF NOT EXISTS bakery_refund_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id TEXT NOT NULL,
                    refund_ref TEXT,
                    refund_request_id INTEGER,
                    amount REAL,
                    items_json TEXT,
                    reason TEXT,
                    reason_category TEXT,
                    method TEXT,
                    issued_by TEXT,
                    notes TEXT,
                    timestamp TEXT
                );

                /* ---- Phase-5 reporting tables ---- */
                CREATE TABLE IF NOT EXISTS bakery_report_schedules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    report_kind TEXT NOT NULL,     -- 'sales' / 'top_sellers' / 'shrinkage' / 'tier'
                    frequency TEXT NOT NULL,       -- 'daily' / 'weekly:Mon' / 'monthly:1'
                    recipients TEXT NOT NULL,      -- CSV of emails or usernames
                    format TEXT DEFAULT 'csv',     -- csv / pdf
                    last_run TEXT,
                    next_run TEXT,
                    active INTEGER DEFAULT 1,
                    created_at TEXT,
                    created_by TEXT
                );
                CREATE TABLE IF NOT EXISTS bakery_report_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    schedule_id INTEGER,
                    report_kind TEXT,
                    range_start TEXT,
                    range_end TEXT,
                    file_path TEXT,
                    delivered_to TEXT,
                    triggered_by TEXT,
                    status TEXT,
                    notes TEXT,
                    timestamp TEXT
                );

                /* ---- Phase-6 prefs / staff / feedback / kitchen ---- */
                CREATE TABLE IF NOT EXISTS bakery_user_prefs (
                    user TEXT PRIMARY KEY,
                    theme TEXT DEFAULT 'classic',
                    text_scale REAL DEFAULT 1.0,
                    language TEXT DEFAULT 'en',
                    updated_at TEXT
                );
                CREATE TABLE IF NOT EXISTS bakery_staff_shifts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    staff TEXT NOT NULL,
                    role TEXT,
                    clock_in TEXT NOT NULL,
                    clock_out TEXT,
                    notes TEXT,
                    status TEXT DEFAULT 'open'   -- open / closed
                );
                CREATE TABLE IF NOT EXISTS bakery_feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user TEXT,
                    order_id TEXT,
                    category TEXT,
                    subject TEXT,
                    message TEXT NOT NULL,
                    rating INTEGER,
                    helpdesk_ticket_id TEXT,
                    status TEXT DEFAULT 'open',
                    handled_by TEXT,
                    response TEXT,
                    created_at TEXT,
                    updated_at TEXT
                );
                CREATE TABLE IF NOT EXISTS bakery_kitchen_status (
                    preorder_id INTEGER PRIMARY KEY,
                    stage TEXT DEFAULT 'queued',   -- queued / prepping / ready
                    updated_at TEXT,
                    updated_by TEXT,
                    notes TEXT
                );

                /* ---- Phase-7 production / BOM / waste / timers ---- */
                CREATE TABLE IF NOT EXISTS bakery_ingredients (
                    name TEXT PRIMARY KEY,
                    unit TEXT NOT NULL,          -- g / ml / each
                    stock REAL DEFAULT 0,
                    reorder_level REAL DEFAULT 0,
                    unit_cost REAL DEFAULT 0,    -- cost per unit
                    allergens TEXT,              -- CSV
                    updated_at TEXT
                );
                CREATE TABLE IF NOT EXISTS bakery_recipes (
                    item_name TEXT NOT NULL,
                    ingredient TEXT NOT NULL,
                    quantity REAL NOT NULL,      -- qty per single product unit
                    PRIMARY KEY (item_name, ingredient)
                );
                CREATE TABLE IF NOT EXISTS bakery_production_plans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plan_date TEXT NOT NULL,
                    item_name TEXT NOT NULL,
                    forecast_qty INTEGER NOT NULL,
                    batch_size INTEGER NOT NULL,
                    planned_batches INTEGER NOT NULL,
                    planned_qty INTEGER NOT NULL,
                    created_by TEXT,
                    created_at TEXT,
                    UNIQUE (plan_date, item_name)
                );
                CREATE TABLE IF NOT EXISTS bakery_product_expiry (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_name TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    bake_date TEXT NOT NULL,
                    expiry_date TEXT NOT NULL,
                    shelf_life_days INTEGER,
                    status TEXT DEFAULT 'fresh', -- fresh / expired / sold-through
                    notes TEXT
                );
                CREATE TABLE IF NOT EXISTS bakery_waste_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    item_name TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    reason_code TEXT NOT NULL,   -- burnt/dropped/expired/sampled/other
                    cost REAL DEFAULT 0,
                    notes TEXT,
                    logged_by TEXT
                );
                CREATE TABLE IF NOT EXISTS bakery_yield_variance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    item_name TEXT NOT NULL,
                    expected_qty INTEGER NOT NULL,
                    actual_qty INTEGER NOT NULL,
                    variance INTEGER NOT NULL,
                    variance_pct REAL,
                    baker TEXT,
                    notes TEXT
                );
                CREATE TABLE IF NOT EXISTS bakery_oven_timers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    label TEXT NOT NULL,
                    item_name TEXT,
                    started_at TEXT NOT NULL,
                    duration_seconds INTEGER NOT NULL,
                    ends_at TEXT NOT NULL,
                    stage TEXT DEFAULT 'oven',   -- oven / proofing / cooling
                    status TEXT DEFAULT 'running', -- running / done / cancelled
                    finished_at TEXT,
                    started_by TEXT,
                    notes TEXT
                );
                CREATE TABLE IF NOT EXISTS bakery_sourdough_feeds (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    starter_name TEXT NOT NULL,
                    fed_at TEXT NOT NULL,
                    flour_grams REAL,
                    water_grams REAL,
                    notes TEXT,
                    fed_by TEXT
                );
                CREATE TABLE IF NOT EXISTS bakery_starters (
                    name TEXT PRIMARY KEY,
                    feed_interval_hours INTEGER DEFAULT 24,
                    last_fed TEXT,
                    next_due TEXT,
                    active INTEGER DEFAULT 1,
                    notes TEXT
                );
                CREATE TABLE IF NOT EXISTS bakery_substitutions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ingredient TEXT NOT NULL,
                    substitute TEXT NOT NULL,
                    ratio REAL DEFAULT 1.0,      -- substitute_qty = ingredient_qty * ratio
                    notes TEXT,
                    UNIQUE (ingredient, substitute)
                );

                /* ---- Phase-8 POS / sales / orders (features 11-25) ---- */
                CREATE TABLE IF NOT EXISTS bakery_catering_trays (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    description TEXT,
                    items_json TEXT NOT NULL,    -- {"item": qty, ...}
                    serves INTEGER,
                    price REAL NOT NULL,
                    active INTEGER DEFAULT 1,
                    created_at TEXT
                );
                CREATE TABLE IF NOT EXISTS bakery_manager_pins (
                    user TEXT PRIMARY KEY,
                    pin TEXT NOT NULL,
                    active INTEGER DEFAULT 1,
                    created_at TEXT
                );
                CREATE TABLE IF NOT EXISTS bakery_void_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id TEXT,
                    action TEXT,                 -- void / quick_refund
                    amount REAL,
                    reason TEXT,
                    manager TEXT,
                    operator TEXT,
                    timestamp TEXT
                );
                CREATE TABLE IF NOT EXISTS bakery_tip_pool_periods (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    total_pool REAL DEFAULT 0,
                    distribution_json TEXT,
                    closed_by TEXT,
                    status TEXT DEFAULT 'open'   -- open / closed
                );
                CREATE TABLE IF NOT EXISTS bakery_offline_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    queued_at TEXT NOT NULL,
                    payload_kind TEXT NOT NULL,  -- 'order' / 'feedback'
                    payload_json TEXT NOT NULL,
                    synced INTEGER DEFAULT 0,
                    synced_at TEXT,
                    error TEXT
                );
                CREATE TABLE IF NOT EXISTS bakery_offline_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    offline_mode INTEGER DEFAULT 0,
                    last_toggled_at TEXT,
                    toggled_by TEXT
                );
                CREATE TABLE IF NOT EXISTS bakery_pickup_slots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    slot_date TEXT NOT NULL,     -- YYYY-MM-DD
                    slot_time TEXT NOT NULL,     -- HH:MM
                    capacity INTEGER DEFAULT 1,
                    booked INTEGER DEFAULT 0,
                    notes TEXT,
                    UNIQUE (slot_date, slot_time)
                );
                CREATE TABLE IF NOT EXISTS bakery_notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel TEXT NOT NULL,       -- 'sms' / 'email'
                    recipient TEXT NOT NULL,
                    subject TEXT,
                    body TEXT,
                    related_order TEXT,
                    status TEXT DEFAULT 'queued', -- queued / sent / failed
                    queued_at TEXT,
                    sent_at TEXT,
                    error TEXT
                );
                CREATE TABLE IF NOT EXISTS bakery_event_quotes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    customer TEXT NOT NULL,
                    contact TEXT,
                    event_type TEXT,             -- wedding / birthday / corporate / other
                    event_date TEXT NOT NULL,
                    details TEXT,
                    servings INTEGER,
                    quoted_price REAL,
                    deposit_amount REAL DEFAULT 0,
                    deposit_paid INTEGER DEFAULT 0,
                    deposit_paid_at TEXT,
                    status TEXT DEFAULT 'draft', -- draft / sent / accepted / declined / completed
                    created_at TEXT,
                    updated_at TEXT,
                    created_by TEXT,
                    notes TEXT
                );
                CREATE TABLE IF NOT EXISTS bakery_subscriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user TEXT NOT NULL,
                    plan_name TEXT NOT NULL,
                    items_json TEXT NOT NULL,
                    frequency TEXT NOT NULL,     -- weekly / biweekly / monthly
                    price_per_delivery REAL,
                    next_delivery TEXT,
                    active INTEGER DEFAULT 1,
                    paused_until TEXT,
                    created_at TEXT,
                    cancelled_at TEXT
                );
                CREATE TABLE IF NOT EXISTS bakery_subscription_deliveries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    subscription_id INTEGER NOT NULL,
                    scheduled_for TEXT NOT NULL,
                    delivered_at TEXT,
                    order_id TEXT,
                    status TEXT DEFAULT 'scheduled', -- scheduled / delivered / skipped
                    notes TEXT
                );
                CREATE TABLE IF NOT EXISTS bakery_campus_cards (
                    card_id TEXT PRIMARY KEY,
                    user TEXT,
                    balance REAL DEFAULT 0,
                    meal_swipes INTEGER DEFAULT 0,
                    active INTEGER DEFAULT 1,
                    created_at TEXT,
                    updated_at TEXT
                );
                CREATE TABLE IF NOT EXISTS bakery_campus_card_txns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    card_id TEXT NOT NULL,
                    txn_type TEXT NOT NULL,      -- spend / topup / swipe
                    amount REAL,
                    swipes INTEGER DEFAULT 0,
                    order_id TEXT,
                    timestamp TEXT
                );

                /* ---- Phase-9 staff / customer / queue (features 26-35) ---- */
                CREATE TABLE IF NOT EXISTS bakery_walkin_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pager_number INTEGER NOT NULL,
                    customer_name TEXT,
                    party_size INTEGER DEFAULT 1,
                    joined_at TEXT NOT NULL,
                    called_at TEXT,
                    served_at TEXT,
                    status TEXT DEFAULT 'waiting', -- waiting / called / served / abandoned
                    notes TEXT
                );
                CREATE TABLE IF NOT EXISTS bakery_customer_profiles (
                    user TEXT PRIMARY KEY,
                    display_name TEXT,
                    dietary_flags TEXT,            -- CSV
                    favourites_json TEXT,          -- ["item", ...]
                    birthday TEXT,                 -- YYYY-MM-DD
                    notes TEXT,
                    created_at TEXT,
                    updated_at TEXT
                );
                CREATE TABLE IF NOT EXISTS bakery_qr_menus (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    location TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT,
                    last_printed TEXT
                );
                CREATE TABLE IF NOT EXISTS bakery_staff_skills (
                    staff TEXT NOT NULL,
                    skill TEXT NOT NULL,           -- bread / pastry / decorating / barista / front
                    level INTEGER DEFAULT 1,       -- 1-5
                    PRIMARY KEY (staff, skill)
                );
                CREATE TABLE IF NOT EXISTS bakery_shift_schedule (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    staff TEXT NOT NULL,
                    role TEXT,
                    skill_required TEXT,
                    shift_date TEXT NOT NULL,
                    start_time TEXT NOT NULL,      -- HH:MM
                    end_time TEXT NOT NULL,        -- HH:MM
                    notes TEXT,
                    created_at TEXT,
                    created_by TEXT
                );
                CREATE TABLE IF NOT EXISTS bakery_breaks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    shift_id INTEGER,
                    staff TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    kind TEXT DEFAULT 'break',     -- break / meal
                    notes TEXT
                );
                CREATE TABLE IF NOT EXISTS bakery_checklists (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    kind TEXT NOT NULL,            -- opening / closing / handover
                    items_json TEXT NOT NULL,      -- ["task1", "task2", ...]
                    active INTEGER DEFAULT 1,
                    created_at TEXT
                );
                CREATE TABLE IF NOT EXISTS bakery_checklist_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    checklist_id INTEGER NOT NULL,
                    run_date TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    completed_by TEXT,
                    results_json TEXT,             -- {"task": true/false}
                    notes TEXT
                );
                CREATE TABLE IF NOT EXISTS bakery_decorator_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    custom_order_id INTEGER,
                    description TEXT NOT NULL,
                    decorator TEXT,
                    due_date TEXT,
                    status TEXT DEFAULT 'queued',  -- queued / in-progress / done / blocked
                    priority INTEGER DEFAULT 3,
                    started_at TEXT,
                    finished_at TEXT,
                    notes TEXT,
                    created_at TEXT
                );
                CREATE TABLE IF NOT EXISTS bakery_app_flags (
                    flag TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TEXT,
                    updated_by TEXT
                );

                /* ---- Phase-10 reports / QA / compliance (36-46) ---- */
                CREATE TABLE IF NOT EXISTS bakery_temp_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    unit_name TEXT NOT NULL,       -- 'fridge-1' / 'freezer-2'
                    temp_c REAL NOT NULL,
                    expected_min REAL,
                    expected_max REAL,
                    ok INTEGER DEFAULT 1,
                    timestamp TEXT NOT NULL,
                    logged_by TEXT,
                    notes TEXT
                );
                CREATE TABLE IF NOT EXISTS bakery_haccp_ccps (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ccp_name TEXT UNIQUE NOT NULL,
                    description TEXT,
                    target_value TEXT,
                    frequency TEXT,                -- per-shift / daily / weekly
                    active INTEGER DEFAULT 1
                );
                CREATE TABLE IF NOT EXISTS bakery_haccp_checks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ccp_id INTEGER NOT NULL,
                    value TEXT,
                    pass INTEGER DEFAULT 1,
                    timestamp TEXT NOT NULL,
                    checked_by TEXT,
                    corrective_action TEXT,
                    notes TEXT
                );
                CREATE TABLE IF NOT EXISTS bakery_wash_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    area TEXT NOT NULL,
                    allergen TEXT,                 -- which allergen wash-down
                    timestamp TEXT NOT NULL,
                    performed_by TEXT,
                    verified_by TEXT,
                    notes TEXT
                );
                CREATE TABLE IF NOT EXISTS bakery_supplier_invoices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    supplier_id INTEGER,
                    invoice_number TEXT,
                    invoice_date TEXT,
                    amount REAL,
                    items_json TEXT,
                    received_at TEXT,
                    received_by TEXT,
                    status TEXT DEFAULT 'pending', -- pending / accepted / rejected
                    rejection_reason TEXT,
                    notes TEXT
                );
                CREATE TABLE IF NOT EXISTS bakery_traceability (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_batch_id INTEGER,      -- → bakery_product_expiry.id
                    item_name TEXT,
                    ingredient_lots_json TEXT,     -- {"flour":"LOT123",...}
                    produced_at TEXT,
                    produced_by TEXT,
                    notes TEXT
                );

                /* ---- Phase-11 integrations (47-50) ---- */
                CREATE TABLE IF NOT EXISTS bakery_kds_tickets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id TEXT,
                    station TEXT DEFAULT 'main',   -- main / espresso / decorating
                    items_json TEXT NOT NULL,
                    status TEXT DEFAULT 'queued',  -- queued / prepping / ready / served
                    received_at TEXT NOT NULL,
                    started_at TEXT,
                    ready_at TEXT,
                    served_at TEXT,
                    priority INTEGER DEFAULT 3,
                    notes TEXT
                );
                CREATE TABLE IF NOT EXISTS bakery_label_templates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    template TEXT NOT NULL,
                    size TEXT,                     -- '50x30mm' etc
                    created_at TEXT
                );
                CREATE TABLE IF NOT EXISTS bakery_label_jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    template_id INTEGER,
                    item_name TEXT,
                    qty INTEGER DEFAULT 1,
                    payload TEXT,
                    status TEXT DEFAULT 'queued',  -- queued / printed / failed
                    queued_at TEXT,
                    printed_at TEXT,
                    printed_by TEXT
                );
                CREATE TABLE IF NOT EXISTS bakery_scale_items (
                    item_name TEXT PRIMARY KEY,
                    price_per_kg REAL NOT NULL,
                    tare_g REAL DEFAULT 0,
                    active INTEGER DEFAULT 1
                );
                CREATE TABLE IF NOT EXISTS bakery_scale_readings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_name TEXT,
                    weight_g REAL NOT NULL,
                    price_per_kg REAL,
                    total_price REAL,
                    timestamp TEXT NOT NULL,
                    operator TEXT
                );
                CREATE TABLE IF NOT EXISTS bakery_menu_board (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    location TEXT NOT NULL,        -- 'dining-hall-north'
                    feed_url TEXT,
                    last_payload TEXT,
                    last_synced_at TEXT,
                    sync_status TEXT DEFAULT 'idle', -- idle / ok / error
                    error TEXT
                );
            """)
            # Seed currency table on first run only.
            seeded = conn.execute(
                "SELECT COUNT(*) FROM bakery_currency_rates").fetchone()[0]
            if seeded == 0:
                conn.executemany(
                    "INSERT INTO bakery_currency_rates "
                    "(currency, symbol, rate_from_gbp, updated_at) "
                    "VALUES (?, ?, ?, ?)",
                    [
                        ("GBP", "£", 1.0,    datetime.now().strftime("%Y-%m-%d")),
                        ("EUR", "€", 1.17,   datetime.now().strftime("%Y-%m-%d")),
                        ("USD", "$", 1.27,   datetime.now().strftime("%Y-%m-%d")),
                    ],
                )
            conn.commit()
        finally:
            conn.close()

    def load_data(self):
        """Load orders from the central DB into self.orders, in the
        same shape the existing GUI code expects (list of dicts)."""
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT order_id, timestamp, username, user_type, items_json, "
                "subtotal, discount, total, payment_method, refunded, refund_ref, "
                "refund_timestamp, promo_code, loyalty_earned, loyalty_redeemed, "
                "discount_breakdown_json, tip_amount, vat_amount, "
                "split_payments_json, billing_code, gift_card_code "
                "FROM bakery_orders ORDER BY id ASC"
            ).fetchall()
        finally:
            conn.close()
        self.orders = []
        for r in rows:
            try:
                items = json.loads(r[4]) if r[4] else {}
            except (TypeError, ValueError):
                items = {}
            try:
                breakdown = json.loads(r[15]) if r[15] else []
            except (TypeError, ValueError):
                breakdown = []
            try:
                splits = json.loads(r[18]) if r[18] else []
            except (TypeError, ValueError):
                splits = []
            self.orders.append({
                "order_id": r[0],
                "timestamp": r[1],
                "user": r[2] or "Guest",
                "user_type": r[3] or "Guest",
                "items": items,
                "subtotal": r[5] or 0,
                "discount": r[6] or 0,
                "total": r[7] or 0,
                "payment_method": r[8] or "cash",
                "refunded": bool(r[9]),
                "refund_ref": r[10],
                "refund_timestamp": r[11],
                "promo_code": r[12],
                "loyalty_earned": r[13] or 0,
                "loyalty_redeemed": r[14] or 0,
                "discount_breakdown": breakdown,
                "tip_amount": r[16] or 0,
                "vat_amount": r[17] or 0,
                "split_payments": splits,
                "billing_code": r[19],
                "gift_card_code": r[20],
            })

    def save_data(self):
        """Persist self.orders back to the central DB. DELETE-all +
        bulk INSERT inside one transaction keeps state consistent with
        the GUI's list-mutation patterns (append/clear/etc.)."""
        conn = self._connect()
        try:
            conn.execute("BEGIN")
            conn.execute("DELETE FROM bakery_orders")
            for o in self.orders:
                conn.execute(
                    "INSERT INTO bakery_orders (order_id, timestamp, username, "
                    "user_type, items_json, subtotal, discount, total, "
                    "payment_method, refunded, refund_ref, refund_timestamp, "
                    "promo_code, loyalty_earned, loyalty_redeemed, "
                    "discount_breakdown_json, tip_amount, vat_amount, "
                    "split_payments_json, billing_code, gift_card_code) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (o.get("order_id"), o.get("timestamp"),
                     o.get("user"), o.get("user_type"),
                     json.dumps(o.get("items", {})),
                     o.get("subtotal", 0), o.get("discount", 0),
                     o.get("total", 0),
                     o.get("payment_method"),
                     1 if o.get("refunded") else 0,
                     o.get("refund_ref"),
                     o.get("refund_timestamp"),
                     o.get("promo_code"),
                     int(o.get("loyalty_earned") or 0),
                     int(o.get("loyalty_redeemed") or 0),
                     json.dumps(o.get("discount_breakdown", [])),
                     float(o.get("tip_amount") or 0),
                     float(o.get("vat_amount") or 0),
                     json.dumps(o.get("split_payments", [])),
                     o.get("billing_code"),
                     o.get("gift_card_code")),
                )
            conn.commit()
        except sqlite3.Error as e:
            conn.rollback()
            logger.exception("Failed to save bakery orders")
            messagebox.showerror("Save Error", f"Could not save data: {e}")
        finally:
            conn.close()

    def _exec(self, sql, params=()):
        """Single-statement DB write wrapper with logging."""
        try:
            conn = self._connect()
            try:
                conn.execute(sql, params)
                conn.commit()
            finally:
                conn.close()
            return True
        except sqlite3.Error:
            logger.exception("DB write failed: %s", sql)
            return False

    def _query(self, sql, params=()):
        try:
            conn = self._connect()
            try:
                return conn.execute(sql, params).fetchall()
            finally:
                conn.close()
        except sqlite3.Error:
            logger.exception("DB read failed: %s", sql)
            return []

