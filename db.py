"""Database initialization and helpers."""
import os
import shutil
import sqlite3
from datetime import datetime
import config


def get_db():
    """Get a database connection with row factory."""
    conn = sqlite3.connect(config.DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Create all tables if they don't exist."""
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            tagline TEXT DEFAULT '',
            description TEXT DEFAULT '',
            price_cents INTEGER NOT NULL,
            compare_price_cents INTEGER DEFAULT 0,
            image TEXT DEFAULT '',
            gallery TEXT DEFAULT '[]',
            specs TEXT DEFAULT '{}',
            stock INTEGER DEFAULT 0,
            featured INTEGER DEFAULT 0,
            category TEXT DEFAULT 'handhelds',
            badge TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stripe_session_id TEXT UNIQUE,
            stripe_payment_intent TEXT,
            email TEXT NOT NULL,
            name TEXT DEFAULT '',
            address TEXT DEFAULT '',
            items_json TEXT NOT NULL,
            total_cents INTEGER NOT NULL,
            gst_cents INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',
            tracking TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS kb_articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            category TEXT DEFAULT 'general',
            content TEXT NOT NULL,
            sort_order INTEGER DEFAULT 0,
            published INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS kb_fts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            article_id INTEGER REFERENCES kb_articles(id) ON DELETE CASCADE,
            title TEXT,
            content TEXT
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS kb_search
        USING fts5(title, content, content=kb_fts, content_rowid=id);

        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_key TEXT UNIQUE NOT NULL,
            email TEXT NOT NULL,
            name TEXT DEFAULT '',
            subject TEXT NOT NULL,
            order_ref TEXT DEFAULT '',
            category TEXT DEFAULT 'general',
            status TEXT DEFAULT 'open',
            priority TEXT DEFAULT 'normal',
            messages_json TEXT NOT NULL DEFAULT '[]',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            visitor_name TEXT DEFAULT 'Visitor',
            message TEXT NOT NULL,
            is_admin INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_products_slug ON products(slug);
        CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);
        CREATE INDEX IF NOT EXISTS idx_orders_email ON orders(email);
        CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
        CREATE INDEX IF NOT EXISTS idx_kb_articles_slug ON kb_articles(slug);
        CREATE INDEX IF NOT EXISTS idx_kb_articles_category ON kb_articles(category);
        CREATE INDEX IF NOT EXISTS idx_tickets_key ON tickets(ticket_key);
        CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status);
        CREATE INDEX IF NOT EXISTS idx_chat_session ON chat_messages(session_id);

        CREATE TABLE IF NOT EXISTS inventory_batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_slug TEXT NOT NULL,
            units_total INTEGER NOT NULL,
            units_sold INTEGER DEFAULT 0,
            cost_per_unit_cents INTEGER NOT NULL,
            ordered_at TEXT NOT NULL,
            arrives_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_slug) REFERENCES products(slug)
        );

        CREATE INDEX IF NOT EXISTS idx_batches_product ON inventory_batches(product_slug);
        CREATE INDEX IF NOT EXISTS idx_batches_status ON inventory_batches(status);

        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name TEXT DEFAULT '',
            phone TEXT DEFAULT '',
            address TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS stripe_events (
            event_id TEXT PRIMARY KEY,
            event_type TEXT NOT NULL,
            processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_customers_email ON customers(email);
        CREATE INDEX IF NOT EXISTS idx_stripe_events_type ON stripe_events(event_type);

        CREATE TABLE IF NOT EXISTS newsletter_emails (
            email TEXT PRIMARY KEY,
            subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS workflow_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workflow_name TEXT NOT NULL,
            steps_json TEXT NOT NULL DEFAULT '[]',
            step_states_json TEXT NOT NULL DEFAULT '{}',
            step_results_json TEXT NOT NULL DEFAULT '{}',
            report TEXT DEFAULT '',
            error TEXT,
            state TEXT DEFAULT 'pending',
            started_at TEXT,
            completed_at TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS expense_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT DEFAULT '',
            is_default INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            category_id INTEGER NOT NULL,
            description TEXT NOT NULL,
            amount_cents INTEGER NOT NULL,
            gst_cents INTEGER DEFAULT 0,
            supplier TEXT DEFAULT '',
            reference TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (category_id) REFERENCES expense_categories(id)
        );

        CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(date);
        CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses(category_id);

        CREATE TABLE IF NOT EXISTS admin_activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            target_type TEXT DEFAULT '',
            target_id TEXT DEFAULT '',
            details TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_workflow_runs_name ON workflow_runs(workflow_name);
        CREATE INDEX IF NOT EXISTS idx_workflow_runs_state ON workflow_runs(state);
        CREATE INDEX IF NOT EXISTS idx_activity_log_created ON admin_activity_log(created_at);

        CREATE TABLE IF NOT EXISTS chat_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS chat_messages_store (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            text TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES chat_sessions(id)
        );

        CREATE INDEX IF NOT EXISTS idx_chat_msgs_session ON chat_messages_store(session_id);
    """)
    conn.commit()
    conn.close()


def seed_products():
    """Insert sample products if table is empty."""
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    if count > 0:
        conn.close()
        return

    import json
    products = [
        {
            "slug": "r36s",
            "name": "R36S Retro Handheld",
            "tagline": "10,000+ games in your pocket — the legend",
            "description": "The R36S is the best-selling retro gaming handheld in Australia. Pre-loaded with over 10,000 classic games across NES, SNES, Genesis, GBA, PS1, N64, and dozens more. Features a vibrant 3.5-inch IPS display, ergonomic design with clicky face buttons, and 6+ hours of battery life. The 64GB TF card is included and ready to play \u2014 just turn it on and go. Runs custom firmware beautifully for those who want to tweak. The handheld that started the retro revival.",
            "price_cents": 6999,
            "compare_price_cents": 9999,
            "image": "/static/images/r36-transparent.webp",
            "gallery": json.dumps(["/static/images/r36-transparent.webp", "/static/images/r36-hero.webp"]),
            "specs": json.dumps({
                "Display": '3.5" IPS, 640x480',
                "CPU": "RK3326 Quad-Core 1.5GHz",
                "RAM": "1GB DDR3",
                "Storage": "64GB TF Card (included)",
                "Battery": "3000mAh (6+ hours)",
                "Platforms": "NES, SNES, Genesis, GBA, N64, PS1, MAME, more",
                "Connectivity": "OTG USB-C, 3.5mm headphone",
                "Weight": "230g",
                "Colours": "Black, White",
            }),
            "stock": 50,
            "featured": 1,
            "category": "handhelds",
            "badge": "BEST SELLER",
            "estimated_cost_cents": 3500,
        },
        {
            "slug": "r36h",
            "name": "R36H Retro Handheld",
            "tagline": "PSP-style horizontal grip, dual sticks — the couch gaming king",
            "description": "The R36H takes everything great about the R36S and puts it in a horizontal PSP-style body. Dual analog sticks for PS1 and N64 games, a crisp 3.5-inch IPS display, and the same 10,000+ game library you love. The wider grip means longer sessions without cramping. 3000mAh battery for 6+ hours of play. Same RK3326 chip, same legendary compatibility, new form factor. If you prefer a PlayStation-style layout over the vertical Game Boy design, this is your handheld.",
            "price_cents": 7999,
            "compare_price_cents": 10999,
            "image": "/static/images/r36h-promax.jpg",
            "gallery": json.dumps(["/static/images/r36h-promax.jpg"]),
            "specs": json.dumps({
                "Display": '3.5" IPS, 640x480',
                "CPU": "RK3326 Quad-Core 1.5GHz",
                "RAM": "1GB DDR3",
                "Storage": "64GB TF Card (included)",
                "Battery": "3000mAh (6+ hours)",
                "Platforms": "NES, SNES, Genesis, GBA, N64, PS1, MAME, more",
                "Connectivity": "OTG USB-C, 3.5mm headphone",
                "Controls": "Dual analog sticks + D-pad",
                "Design": "Horizontal / PSP-style",
                "Weight": "220g",
            }),
            "stock": 25,
            "featured": 1,
            "category": "handhelds",
            "badge": "NEW",
            "estimated_cost_cents": 4500,
        }
    ]

    for p in products:
        conn.execute("""
            INSERT INTO products (slug, name, tagline, description, price_cents, compare_price_cents,
                image, gallery, specs, stock, featured, category, badge, estimated_cost_cents)
            VALUES (:slug, :name, :tagline, :description, :price_cents, :compare_price_cents,
                :image, :gallery, :specs, :stock, :featured, :category, :badge, :estimated_cost_cents)
        """, p)

    conn.commit()
    conn.close()
    print(f"Seeded {len(products)} products")


def seed_kb():
    """Insert sample KB articles if table is empty."""
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM kb_articles").fetchone()[0]
    if count > 0:
        conn.close()
        return

    articles = [
        {
            "slug": "r36s-getting-started",
            "title": "Getting Started with Your R36S",
            "category": "setup",
            "content": """# Getting Started with Your R36S

Welcome to your new R36S! Here's everything you need to know to start gaming.

## First Boot
1. Insert the included TF card into the slot on the back
2. Hold the power button (top-left) for 3 seconds
3. The system will boot into the game selection menu

## Navigation
- **D-Pad**: Move through game lists
- **A Button**: Select/Confirm
- **B Button**: Back/Cancel
- **Start**: Open in-game menu
- **Select**: Save state menu
- **L/R**: Quick save/load

## Charging
Use the included USB-C cable. A full charge takes about 2 hours and gives you 6+ hours of gameplay.

## Adding More Games
Simply copy ROM files to the appropriate folder on the TF card:
- `ROMS/NES/` for NES games
- `ROMS/SNES/` for SNES games
- `ROMS/GBA/` for Game Boy Advance games
- And so on for each supported platform
"""
        },
        {
            "slug": "shipping-info",
            "title": "Shipping Information",
            "category": "orders",
            "content": """# Shipping Information

## Australia
- **Standard Shipping**: 5-7 business days — FREE on orders over $50
- **Express Shipping**: 2-3 business days — $9.99

## International
- **New Zealand**: 7-10 business days — $12.99
- **Other Countries**: Contact us for a quote

## Tracking
All orders include tracking. You'll receive a tracking number via email once your order ships.

## Processing Time
Orders placed before 2pm AEST ship same business day. Orders after 2pm ship next business day.
"""
        },
        {
            "slug": "returns-policy",
            "title": "Returns & Refunds",
            "category": "orders",
            "content": """# Returns & Refunds Policy

## 30-Day Returns
We accept returns within 30 days of delivery for all products in original condition.

## Faulty Products
If your handheld arrives faulty or develops a defect within the warranty period:
1. Contact us via the [support ticket system](/tickets/new)
2. Include your order number and a description of the issue
3. We'll arrange a replacement or full refund

## Warranty
All handhelds come with a 12-month warranty covering manufacturing defects. This does not cover physical damage, water damage, or unauthorized modifications.

## How to Return
1. Submit a support ticket with your order number
2. We'll send you a return shipping label
3. Pack the item securely in original packaging if possible
4. Drop it off at the nearest post office
"""
        },
        {
            "slug": "troubleshooting-wont-turn-on",
            "title": "My Handheld Won't Turn On",
            "category": "troubleshooting",
            "content": """# My Handheld Won't Turn On

Don't panic! Most of the time this is a simple fix.

## Quick Fixes

### 1. Charge It
The battery may be completely flat. Plug in the USB-C charger and wait 15 minutes, then try again. A full charge takes about 2 hours.

### 2. Check the TF Card
Make sure the TF card is properly inserted. Remove it and reinsert it firmly.

### 3. Reset
Hold the power button for 10+ seconds to force a hard reset.

### 4. Try a Different Charger
Some USB-C chargers may not be compatible. Try the included charger or a standard 5V charger.

## Still Not Working?
If none of these steps work, your unit may be faulty. [Submit a support ticket](/tickets/new) and we'll sort it out.
"""
        },
        {
            "slug": "adding-games",
            "title": "How to Add More Games",
            "category": "setup",
            "content": """# How to Add More Games

Your R36S comes pre-loaded with thousands of games, but you can add more!

## Steps
1. Remove the TF card from the back of the handheld
2. Insert it into your computer using the included adapter
3. Open the `ROMS` folder
4. Copy your game files (`.nes`, `.smd`, `.gba`, etc.) to the appropriate platform folder
5. Safely eject the card and reinsert it into the handheld
6. Your new games will appear in the game list

## Supported Formats
| Platform | Format | Folder |
|----------|--------|--------|
| NES | .nes | ROMS/NES/ |
| SNES | .smd, .fig | ROMS/SNES/ |
| Genesis | .gen, .md | ROMS/MD/ |
| GBA | .gba | ROMS/GBA/ |
| PS1 | .bin, .pbp | ROMS/PS1/ |
| Arcade | .zip | ROMS/ARCADE/ |

## Tips
- Keep ROM filenames short (under 50 characters)
- Don't mix platforms in the same folder
- Use a quality TF card for best performance
"""
        }
    ]

    for a in articles:
        conn.execute("""
            INSERT INTO kb_articles (slug, title, category, content, sort_order, published)
            VALUES (:slug, :title, :category, :content, 0, 1)
        """, a)
        # Insert FTS row
        article_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute("""
            INSERT INTO kb_fts (article_id, title, content)
            VALUES (?, ?, ?)
        """, (article_id, a["title"], a["content"]))

    conn.commit()
    conn.close()
    print(f"Seeded {len(articles)} KB articles")


# ── Inventory Batch Pricing ──

def get_active_batch(product_slug):
    """Get the active inventory batch for a product, or None."""
    conn = get_db()
    batch = conn.execute(
        "SELECT * FROM inventory_batches WHERE product_slug = ? AND status = 'active' ORDER BY id DESC LIMIT 1",
        (product_slug,)
    ).fetchone()
    conn.close()
    return dict(batch) if batch else None


def get_batch_price(batch):
    """Three-phase pricing: pre-order (+10%), in-stock (+40%), clearance (cost).
    Clamped to minimum profitable price to prevent selling at a loss."""
    from datetime import datetime, timedelta
    from pricing import calculate_min_price
    now = datetime.utcnow()
    arrives = datetime.fromisoformat(batch['arrives_at'])
    expires = datetime.fromisoformat(batch['expires_at'])
    expiry_dump = expires - timedelta(hours=48)

    cost = batch['cost_per_unit_cents']
    slug = batch.get('product_slug', '')

    if now < arrives:
        phase_price = int(cost * 1.10)
    elif now >= expiry_dump:
        phase_price = cost
    else:
        phase_price = int(cost * 1.40)

    # Clamp to minimum profitable price
    min_price = calculate_min_price(cost, slug)
    if min_price > 0 and phase_price < min_price:
        return min_price
    return phase_price


def get_batch_phase(batch):
    """Returns current phase: 'preorder', 'instock', or 'clearance'."""
    from datetime import datetime, timedelta
    now = datetime.utcnow()
    arrives = datetime.fromisoformat(batch['arrives_at'])
    expires = datetime.fromisoformat(batch['expires_at'])
    expiry_dump = expires - timedelta(hours=48)

    if now < arrives:
        return 'preorder'
    if now >= expiry_dump:
        return 'clearance'
    return 'instock'


def get_batch_remaining(batch):
    """Units remaining in batch."""
    return batch['units_total'] - batch['units_sold']


def seed_batches():
    """Seed initial inventory batches if none exist."""
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM inventory_batches").fetchone()[0]
    if count > 0:
        conn.close()
        return

    batches = [
        {
            # R36S 64GB — AliExpress ~$22 USD landed = ~$34 AUD + $12.30 domestic + ~$1.50 Stripe = ~$48 AUD
            "product_slug": "r36s",
            "units_total": 10,
            "units_sold": 0,
            "cost_per_unit_cents": 4800,
            "ordered_at": "2026-05-19T00:00:00",
            "arrives_at": "2026-06-15T00:00:00",
            "expires_at": "2026-08-10T00:00:00",
            "status": "active",
        },
        {
            # R35H 64GB WiFi — AliExpress ~$41 USD = ~$64 AUD + $12.30 domestic + ~$2 Stripe = ~$78 AUD
            "product_slug": "r35h",
            "units_total": 10,
            "units_sold": 0,
            "cost_per_unit_cents": 7800,
            "ordered_at": "2026-05-19T00:00:00",
            "arrives_at": "2026-06-15T00:00:00",
            "expires_at": "2026-08-10T00:00:00",
            "status": "active",
        },
    ]

    for b in batches:
        conn.execute("""
            INSERT INTO inventory_batches (product_slug, units_total, units_sold, cost_per_unit_cents,
                ordered_at, arrives_at, expires_at, status)
            VALUES (:product_slug, :units_total, :units_sold, :cost_per_unit_cents,
                :ordered_at, :arrives_at, :expires_at, :status)
        """, b)

    conn.commit()
    conn.close()
    print(f"Seeded {len(batches)} inventory batches")


def seed_expense_categories():
    """Seed default expense categories if none exist."""
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM expense_categories").fetchone()[0]
    if count > 0:
        conn.close()
        return

    categories = [
        ("Inventory", "Stock purchases from suppliers (AliExpress, Alibaba, etc.)", 1),
        ("Shipping", "Domestic and international shipping costs", 1),
        ("Packaging", "Boxes, tape, labels, bubble wrap", 1),
        ("Platform Fees", "Stripe, eBay, and other marketplace fees", 1),
        ("Domain & Hosting", "Domain registration, DNS, SSL (usually $0 on Oracle)", 1),
        ("Software & Tools", "SaaS subscriptions, dev tools, accounting software", 1),
        ("Marketing", "Ads, content creation, social media promotion", 1),
        ("Office Supplies", "General business supplies", 1),
        ("Travel", "Business-related travel expenses", 1),
        ("Professional Services", "Accountant, legal, consulting fees", 1),
        ("Equipment", "Business equipment and hardware", 1),
        ("Other", "Miscellaneous business expenses", 1),
    ]

    for name, desc, is_default in categories:
        conn.execute(
            "INSERT INTO expense_categories (name, description, is_default) VALUES (?, ?, ?)",
            (name, desc, is_default),
        )

    conn.commit()
    conn.close()
    print(f"Seeded {len(categories)} expense categories")


def migrate_db():
    """Run schema migrations for existing databases."""
    conn = get_db()

    # ── Orders table migrations ──
    cols = [row[1] for row in conn.execute("PRAGMA table_info(orders)").fetchall()]
    if "gst_cents" not in cols:
        conn.execute("ALTER TABLE orders ADD COLUMN gst_cents INTEGER DEFAULT 0")
        conn.commit()
        print("Migration: added gst_cents to orders")
    if "shipping_cents" not in cols:
        conn.execute("ALTER TABLE orders ADD COLUMN shipping_cents INTEGER DEFAULT 0")
        conn.commit()
        print("Migration: added shipping_cents to orders")
    if "refund_cents" not in cols:
        conn.execute("ALTER TABLE orders ADD COLUMN refund_cents INTEGER DEFAULT 0")
        conn.commit()
        print("Migration: added refund_cents to orders")
    if "customer_id" not in cols:
        conn.execute("ALTER TABLE orders ADD COLUMN customer_id INTEGER REFERENCES customers(id)")
        conn.commit()
        print("Migration: added customer_id to orders")

    # ── Products table: min_price_cents + estimated_cost_cents ──
    prod_cols = [row[1] for row in conn.execute("PRAGMA table_info(products)").fetchall()]
    if "min_price_cents" not in prod_cols:
        conn.execute("ALTER TABLE products ADD COLUMN min_price_cents INTEGER DEFAULT 0")
        conn.commit()
        print("Migration: added min_price_cents to products")
    if "estimated_cost_cents" not in prod_cols:
        conn.execute("ALTER TABLE products ADD COLUMN estimated_cost_cents INTEGER DEFAULT 0")
        conn.commit()
        print("Migration: added estimated_cost_cents to products")

    # ── cost_parameters table (key/value) ──
    conn.execute("""CREATE TABLE IF NOT EXISTS cost_parameters (
        key TEXT PRIMARY KEY,
        value INTEGER NOT NULL,
        description TEXT DEFAULT ''
    )""")
    # Seed defaults if empty
    count = conn.execute("SELECT COUNT(*) FROM cost_parameters").fetchone()[0]
    if count == 0:
        conn.executemany(
            "INSERT INTO cost_parameters (key, value, description) VALUES (?, ?, ?)",
            [
                ("packaging_cents", 135, "Packaging materials per order"),
                ("shipping_out_cents", 850, "Average outbound shipping cost"),
                ("stripe_percent_bps", 175, "Stripe percentage fee in basis points (1.75%)"),
                ("stripe_fixed_cents", 30, "Stripe fixed fee per transaction"),
                ("gst_rate_bps", 909, "GST rate as basis points of inclusive price (~9.09%)"),
            ]
        )
        conn.commit()
        print("Migration: seeded cost_parameters")

    # ── product_cost_profiles table (per-product overrides) ──
    conn.execute("""CREATE TABLE IF NOT EXISTS product_cost_profiles (
        slug TEXT PRIMARY KEY,
        packaging_cents INTEGER DEFAULT NULL,
        shipping_out_cents INTEGER DEFAULT NULL,
        override_min_price INTEGER DEFAULT NULL,
        notes TEXT DEFAULT '',
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    # ── AI decision memory tables ──
    conn.execute("""CREATE TABLE IF NOT EXISTS ai_decisions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        decision_type TEXT NOT NULL,
        product_slug TEXT DEFAULT '',
        decision TEXT NOT NULL,
        reasoning TEXT DEFAULT '',
        data_used TEXT DEFAULT '',
        outcome TEXT DEFAULT '',
        confidence TEXT DEFAULT 'medium',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    conn.execute("""CREATE TABLE IF NOT EXISTS ai_notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT DEFAULT 'general',
        subject TEXT NOT NULL,
        body TEXT NOT NULL,
        related_slug TEXT DEFAULT '',
        importance TEXT DEFAULT 'normal',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    # FTS5 index on ai_notes (same pattern as kb_articles)
    conn.execute("""CREATE TABLE IF NOT EXISTS ai_notes_fts (
        id INTEGER PRIMARY KEY,
        note_id INTEGER REFERENCES ai_notes(id) ON DELETE CASCADE,
        subject TEXT,
        body TEXT
    )""")
    conn.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS ai_notes_search
        USING fts5(subject, body, content=ai_notes_fts, content_rowid=id)""")

    # Indexes for AI tables
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ai_decisions_type ON ai_decisions(decision_type)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ai_decisions_slug ON ai_decisions(product_slug)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ai_decisions_created ON ai_decisions(created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ai_notes_category ON ai_notes(category)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ai_notes_slug ON ai_notes(related_slug)")

    conn.commit()

    # ── Backfill estimated_cost_cents for existing products ──
    # Known AliExpress landed costs in AUD cents (product cost + shipping estimates)
    COST_ESTIMATES = {
        "r36s-black": 4800,
        "r36s-white": 4800,
        "r33s": 3200,
        "r36s-plus": 5500,
        "r36s-wifi-black": 5800,
        "r36s-wifi-white": 5800,
        "r36s-wifi-mod-black": 5800,
        "r36s-wifi-mod-white": 5800,
        "r36h-promax": 4200,
        "rgb20s": 4500,
        "rg35xx-plus": 5500,
        "rg34xx": 6200,
        "rg34xx-sp": 6800,
        "miyoo-mini-plus": 5000,
        "trimui-brick": 6500,
        "trimui-smart-pro": 6800,
        "powkiddy-v90s": 4200,
        "powkiddy-x55": 7200,
        "carry-case": 400,
        "64gb-card": 600,
        "usb-c-charger": 300,
        "bundle-r36s-wifi-pro": 6200,
        "bundle-r33s-starter": 3800,
        "bundle-r36s-plus-pro": 6100,
        "tetrahedron": 8000,
        "cube": 15000,
        "octahedron": 25000,
        "dodecahedron": 35000,
        "icosahedron": 55000,
        "oculink-egpu-kit": 5000,
        "amd-bc250-steam-box": 25000,
    }
    for slug, cost in COST_ESTIMATES.items():
        conn.execute(
            "UPDATE products SET estimated_cost_cents = ? WHERE slug = ? AND (estimated_cost_cents IS NULL OR estimated_cost_cents = 0)",
            (cost, slug)
        )
    conn.commit()

    conn.close()


def backup_db():
    """Create a timestamped backup of the database."""
    os.makedirs(config.BACKUP_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(config.BACKUP_DIR, f"retro_store_{timestamp}.db")

    # Use SQLite backup API for consistent snapshot
    src = sqlite3.connect(config.DATABASE)
    dst = sqlite3.connect(backup_path)
    src.backup(dst)
    dst.close()
    src.close()

    # Keep only last 30 backups
    backups = sorted(
        [f for f in os.listdir(config.BACKUP_DIR) if f.startswith("retro_store_") and f.endswith(".db")],
        reverse=True
    )
    for old in backups[30:]:
        os.remove(os.path.join(config.BACKUP_DIR, old))

    print(f"Database backed up to {backup_path}")
    return backup_path
