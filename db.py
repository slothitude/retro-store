"""Database initialization and helpers."""
import sqlite3
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
            "slug": "r36s-black",
            "name": "R36S Retro Handheld",
            "tagline": "10,000+ games in your pocket",
            "description": "The R36S is the ultimate retro gaming handheld. Pre-loaded with over 10,000 classic games across dozens of platforms including NES, SNES, Genesis, GBA, PS1, and more. Features a vibrant 3.5\" IPS display, ergonomic design, and 6+ hours of battery life.",
            "price_cents": 5999,
            "compare_price_cents": 7999,
            "image": "/static/images/r36s-transparent.png",
            "gallery": json.dumps(["/static/images/r36s-transparent.png", "/static/images/r36s-gaming.jpg"]),
            "specs": json.dumps({
                "Display": '3.5" IPS, 640x480',
                "CPU": "RK3326 Quad-Core",
                "RAM": "1GB DDR3",
                "Storage": "64GB TF Card (included)",
                "Battery": "3000mAh, 6+ hours",
                "Platforms": "NES, SNES, GBA, N64, PS1, PSP, more",
                "Connectivity": "OTG, 3.5mm audio",
                "Weight": "230g"
            }),
            "stock": 50,
            "featured": 1,
            "category": "handhelds",
            "badge": "BEST SELLER"
        },
        {
            "slug": "r36s-white",
            "name": "R36S Retro Handheld (White)",
            "tagline": "Classic look, same legendary library",
            "description": "Same incredible R36S experience in a sleek white shell. 10,000+ pre-loaded retro games, 3.5\" IPS display, and that satisfying clicky D-pad. Perfect for collectors who want something a little different.",
            "price_cents": 5999,
            "compare_price_cents": 0,
            "image": "/static/images/r36s-transparent.png",
            "gallery": json.dumps(["/static/images/r36s-transparent.png"]),
            "specs": json.dumps({
                "Display": '3.5" IPS, 640x480',
                "CPU": "RK3326 Quad-Core",
                "RAM": "1GB DDR3",
                "Storage": "64GB TF Card (included)",
                "Battery": "3000mAh, 6+ hours",
                "Platforms": "NES, SNES, GBA, N64, PS1, PSP, more",
                "Connectivity": "OTG, 3.5mm audio",
                "Weight": "230g"
            }),
            "stock": 30,
            "featured": 1,
            "category": "handhelds",
            "badge": ""
        },
        {
            "slug": "rgb20s",
            "name": "RGB20S Handheld",
            "tagline": "Compact powerhouse for retro purists",
            "description": "The RGB20S packs a punch in a pocket-friendly form factor. Its 3.5\" IPS screen delivers crisp visuals, while the ergonomic button layout makes extended play sessions comfortable. Supports 20+ retro platforms with custom firmware support.",
            "price_cents": 7999,
            "compare_price_cents": 9999,
            "image": "/static/images/rgb20s.jpg",
            "gallery": json.dumps(["/static/images/rgb20s.jpg"]),
            "specs": json.dumps({
                "Display": '3.5" IPS, 640x480',
                "CPU": "RK3326 Quad-Core",
                "RAM": "1GB DDR3",
                "Storage": "32GB TF Card (included)",
                "Battery": "3000mAh",
                "Platforms": "NES, SNES, GBA, N64, PS1, more",
                "Connectivity": "WiFi, OTG, 3.5mm audio",
                "Weight": "210g"
            }),
            "stock": 25,
            "featured": 1,
            "category": "handhelds",
            "badge": "NEW"
        },
        {
            "slug": "r36s-wifi-black",
            "name": "R36S WiFi Retro Handheld",
            "tagline": "10,000+ games with online multiplayer",
            "description": "The R36S WiFi edition adds wireless connectivity to the legendary retro handheld. Connect to WiFi for online multiplayer, firmware updates, and scraping game artwork automatically. Same incredible 10,000+ game library with the added bonus of RetroAchievements integration — earn achievements in classic games just like modern platforms.",
            "price_cents": 7499,
            "compare_price_cents": 8999,
            "image": "/static/images/r36s-transparent.png",
            "gallery": json.dumps(["/static/images/r36s-transparent.png"]),
            "specs": json.dumps({
                "Display": '3.5" IPS, 640x480',
                "CPU": "RK3326 Quad-Core",
                "RAM": "1GB DDR3",
                "Storage": "64GB TF Card (included)",
                "Battery": "3000mAh, 6+ hours",
                "WiFi": "802.11 b/g/n",
                "Platforms": "NES, SNES, GBA, N64, PS1, PSP, more",
                "Connectivity": "WiFi, OTG, 3.5mm audio",
                "Weight": "235g"
            }),
            "stock": 30,
            "featured": 1,
            "category": "handhelds",
            "badge": "NEW"
        },
        {
            "slug": "r36s-wifi-white",
            "name": "R36S WiFi Retro Handheld (White)",
            "tagline": "Wireless gaming in classic style",
            "description": "Same WiFi-enabled R36S in the sleek white shell. Online multiplayer, automatic artwork scraping, RetroAchievements, and firmware updates over WiFi. 10,000+ pre-loaded games across every major retro platform.",
            "price_cents": 7499,
            "compare_price_cents": 0,
            "image": "/static/images/r36s-transparent.png",
            "gallery": json.dumps(["/static/images/r36s-transparent.png"]),
            "specs": json.dumps({
                "Display": '3.5" IPS, 640x480',
                "CPU": "RK3326 Quad-Core",
                "RAM": "1GB DDR3",
                "Storage": "64GB TF Card (included)",
                "Battery": "3000mAh, 6+ hours",
                "WiFi": "802.11 b/g/n",
                "Platforms": "NES, SNES, GBA, N64, PS1, PSP, more",
                "Connectivity": "WiFi, OTG, 3.5mm audio",
                "Weight": "235g"
            }),
            "stock": 20,
            "featured": 0,
            "category": "handhelds",
            "badge": ""
        },
        {
            "slug": "carry-case",
            "name": "Premium Carry Case",
            "tagline": "Protect your retro rig",
            "description": "Hard-shell carry case with custom foam insert for R36S and similar handhelds. Interior mesh pocket for cables and accessories. Carabiner clip included. Available in black.",
            "price_cents": 1999,
            "compare_price_cents": 2999,
            "image": "/static/images/case.jpg",
            "gallery": json.dumps(["/static/images/case.jpg"]),
            "specs": json.dumps({
                "Material": "EVA Hard Shell",
                "Interior": "Custom foam + mesh pocket",
                "Fits": "R36S, RGB20S, and similar 3.5\" handhelds",
                "Color": "Black",
                "Dimensions": "18 x 10 x 5 cm"
            }),
            "stock": 100,
            "featured": 0,
            "category": "accessories",
            "badge": ""
        },
        {
            "slug": "64gb-card",
            "name": "64GB Game Card (Pre-loaded)",
            "tagline": "Double your game library",
            "description": "64GB TF card pre-loaded with an expanded collection of 15,000+ retro games. Covers all major platforms from the 8-bit era through PS1. Plug and play — just swap it into your R36S or compatible handheld.",
            "price_cents": 2499,
            "compare_price_cents": 0,
            "image": "/static/images/sd-card.jpg",
            "gallery": json.dumps(["/static/images/sd-card.jpg"]),
            "specs": json.dumps({
                "Capacity": "64GB",
                "Games": "15,000+",
                "Platforms": "NES through PS1, MAME, more",
                "Format": "FAT32 (plug and play)"
            }),
            "stock": 200,
            "featured": 0,
            "category": "accessories",
            "badge": "POPULAR"
        },
        {
            "slug": "usb-c-charger",
            "name": "USB-C Fast Charger",
            "tagline": "Quick top-ups between sessions",
            "description": "Compact USB-C charger compatible with all retro handhelds. 5V/2A output for fast charging. AU plug. Includes 1m USB-C cable.",
            "price_cents": 1499,
            "compare_price_cents": 0,
            "image": "/static/images/charger.jpg",
            "gallery": json.dumps(["/static/images/charger.jpg"]),
            "specs": json.dumps({
                "Output": "5V/2A",
                "Plug": "AU",
                "Cable": "1m USB-C included",
                "Compatibility": "All USB-C handhelds"
            }),
            "stock": 150,
            "featured": 0,
            "category": "accessories",
            "badge": ""
        },
        {
            "slug": "rg35xx-plus",
            "name": "Anbernic RG35XX Plus",
            "tagline": "The people's champion of retro handhelds",
            "description": "The RG35XX Plus delivers incredible value. Allwinner H700 quad-core processor handles everything from NES through PSP with ease. The 3.5\" IPS display is bright and crisp at 640x480. 1GB LPDDR4 RAM, 64GB TF card included. Runs Linux out of the box. The custom firmware community is massive \u2014 choose from Anbernic OS, MinUI, Garlic, and more. Simply the best value retro handheld in 2025.",
            "price_cents": 8999,
            "compare_price_cents": 0,
            "image": "/static/images/rg35xx-plus.jpg",
            "gallery": json.dumps(["/static/images/rg35xx-plus.jpg"]),
            "specs": json.dumps({
                "Display": '3.5" IPS, 640x480',
                "CPU": "Allwinner H700 Quad-Core Cortex-A53",
                "RAM": "1GB LPDDR4",
                "Storage": "64GB TF Card (included)",
                "Battery": "3300mAh",
                "Platforms": "NES, SNES, GBA, N64, PS1, PSP",
                "WiFi": "No",
                "Game Streaming": "Moonlight (with WiFi USB adapter)",
                "Weight": "230g"
            }),
            "stock": 40,
            "featured": 1,
            "category": "handhelds",
            "badge": "BEST VALUE"
        },
        {
            "slug": "rg34xx",
            "name": "Anbernic RG34XX",
            "tagline": "Perfect GBA form factor, razor-sharp display",
            "description": "The RG34XX is the ultimate GBA-era handheld. Its 3.4\" IPS display at 720x480 delivers pixel-perfect Game Boy Advance games with zero scaling artifacts. Allwinner H700 quad-core, Linux-based, supports NES through PS1. The form factor is pure nostalgia \u2014 perfectly sized for pocket and hands alike. Built-in WiFi + Moonlight support means you can stream your PC games to it too.",
            "price_cents": 9999,
            "compare_price_cents": 0,
            "image": "/static/images/rg34xx.png",
            "gallery": json.dumps(["/static/images/rg34xx.png"]),
            "specs": json.dumps({
                "Display": '3.4" IPS, 720x480',
                "CPU": "Allwinner H700 Quad-Core Cortex-A53",
                "RAM": "1GB LPDDR4",
                "Storage": "64GB TF Card (included)",
                "Battery": "3300mAh",
                "Platforms": "NES, SNES, GBA, N64, PS1",
                "WiFi": "802.11 b/g/n",
                "Game Streaming": "Moonlight (stream PC games, 1080p60)",
                "Weight": "188g"
            }),
            "stock": 30,
            "featured": 1,
            "category": "handhelds",
            "badge": "NEW"
        },
        {
            "slug": "rg34xx-sp",
            "name": "Anbernic RG34XX SP",
            "tagline": "The GBA SP revival — flip it open and play",
            "description": "A faithful clamshell recreation of the iconic Game Boy Advance SP. Flip-open design protects the screen in your pocket. 3.4\" IPS 720x480 display, H700 quad-core, 2GB RAM for smoother N64 and PSP performance. Folds flat, charges via USB-C, and feels like holding a piece of history \u2014 upgraded for 2025. Built-in WiFi with Moonlight for streaming your PC game library.",
            "price_cents": 10999,
            "compare_price_cents": 0,
            "image": "/static/images/rg34xx-sp.png",
            "gallery": json.dumps(["/static/images/rg34xx-sp.png"]),
            "specs": json.dumps({
                "Display": '3.4" IPS, 720x480 (clamshell)',
                "CPU": "Allwinner H700 Quad-Core Cortex-A53",
                "RAM": "2GB LPDDR4",
                "Storage": "64GB TF Card (included)",
                "Battery": "2500mAh",
                "Platforms": "NES, SNES, GBA, N64, PS1, PSP",
                "WiFi": "802.11 b/g/n",
                "Game Streaming": "Moonlight (built into stock firmware)",
                "Weight": "195g",
                "Design": "Flip/clamshell"
            }),
            "stock": 20,
            "featured": 0,
            "category": "handhelds",
            "badge": "NEW"
        },
        {
            "slug": "miyoo-mini-plus",
            "name": "Miyoo Mini Plus",
            "tagline": "Pocket perfection with legendary software",
            "description": "The Miyoo Mini Plus is beloved for one reason: OnionOS. The custom firmware experience is the gold standard — buttery smooth UI, instant save states, perfect scaling, and WiFi for automatic artwork scraping. 3.5\" IPS display, ultra-pocketable vertical form factor, and a community that's second to none. The best software experience in retro gaming.",
            "price_cents": 8999,
            "compare_price_cents": 0,
            "image": "/static/images/miyoo-mini-plus.jpg",
            "gallery": json.dumps(["/static/images/miyoo-mini-plus.jpg"]),
            "specs": json.dumps({
                "Display": '3.5" IPS, 640x480',
                "CPU": "ARM Cortex-A7 Dual-Core 1.2GHz",
                "RAM": "2GB LPDDR4x",
                "Storage": "32GB eMMC + TF Card slot",
                "Battery": "3000mAh",
                "Platforms": "NES, SNES, GBA, PS1 (no N64/PSP)",
                "WiFi": "802.11 b/g/n",
                "Weight": "175g",
                "CFW": "OnionOS (community)"
            }),
            "stock": 25,
            "featured": 1,
            "category": "handhelds",
            "badge": "POPULAR"
        },
        {
            "slug": "trimui-brick",
            "name": "TrimUI Brick",
            "tagline": "The sharpest screen in retro gaming",
            "description": "The TrimUI Brick packs a stunning 3.2\" IPS display at 1024x768 — the highest resolution in its class. Every pixel is razor sharp. Solid ABS body with a metal back plate gives it a premium heft. Allwinner A133P chip handles NES through PS1 with ease. The new community favorite for screen purists who demand the best visuals.",
            "price_cents": 10999,
            "compare_price_cents": 0,
            "image": "/static/images/trimui-brick.png",
            "gallery": json.dumps(["/static/images/trimui-brick.png"]),
            "specs": json.dumps({
                "Display": '3.2" IPS, 1024x768',
                "CPU": "Allwinner A133P 1.8GHz",
                "GPU": "PowerVR GE8300",
                "RAM": "1GB LPDDR3",
                "Storage": "64GB TF Card (included)",
                "Battery": "3000mAh",
                "Platforms": "NES, SNES, GBA, PS1 (some N64)",
                "WiFi": "No",
                "Weight": "210g",
                "Build": "ABS + metal back plate"
            }),
            "stock": 25,
            "featured": 0,
            "category": "handhelds",
            "badge": "PREMIUM"
        },
        {
            "slug": "r33s",
            "name": "R33S Retro Handheld",
            "tagline": "Tiny, mighty, under 50 bucks",
            "description": "The R33S is the smallest and cheapest entry into retro gaming. Vertical form factor inspired by the Miyoo Mini, with a crisp 3.5\" IPS display and RK3326 quad-core chip. No analog sticks — pure D-pad precision for 8-bit and 16-bit classics. 64GB TF card included with thousands of games. Perfect first handheld for kids or anyone who wants to dip their toes in without breaking the bank.",
            "price_cents": 4999,
            "compare_price_cents": 6999,
            "image": "/static/images/r33s.jpg",
            "gallery": json.dumps(["/static/images/r33s.jpg"]),
            "specs": json.dumps({
                "Display": '3.5" IPS, 640x480',
                "CPU": "RK3326 Quad-Core",
                "RAM": "1GB DDR3",
                "Storage": "64GB TF Card (included)",
                "Battery": "3000mAh",
                "Platforms": "NES, SNES, GBA, PS1",
                "WiFi": "No",
                "Weight": "170g",
                "Analog Sticks": "No (D-pad only)"
            }),
            "stock": 35,
            "featured": 1,
            "category": "handhelds",
            "badge": "BUDGET PICK"
        },
        {
            "slug": "r36s-plus",
            "name": "R36S Plus",
            "tagline": "The legend evolves — bigger screen, WiFi, ready",
            "description": "The R36S Plus is the 2025 upgrade everyone asked for. Bigger 4.0\" IPS display at 720x720 (perfect 1:1 ratio for retro games). Allwinner A133P chip for smoother N64 and PSP. WiFi built in for artwork scraping and RetroAchievements. Bluetooth 4.2 for wireless controllers. Same legendary R36S feel, everything upgraded. The new king of budget handhelds.",
            "price_cents": 7499,
            "compare_price_cents": 9999,
            "image": "/static/images/r36s-plus.jpg",
            "gallery": json.dumps(["/static/images/r36s-plus.jpg"]),
            "specs": json.dumps({
                "Display": '4.0" IPS, 720x720 (1:1)',
                "CPU": "Allwinner A133P",
                "RAM": "1GB LPDDR4 (up to 4GB)",
                "Storage": "64GB TF Card (included)",
                "Battery": "3000mAh",
                "Platforms": "NES, SNES, GBA, N64, PS1, PSP",
                "WiFi": "802.11 b/g/n",
                "Bluetooth": "4.2",
                "Weight": "240g"
            }),
            "stock": 30,
            "featured": 1,
            "category": "handhelds",
            "badge": "NEW"
        },
        {
            "slug": "powkiddy-v90s",
            "name": "Powkiddy V90S",
            "tagline": "Flip it like it's 2003",
            "description": "The V90S brings the GBA SP clamshell back to life. Compact flip-open design protects the screen and fits any pocket. 3.5\" IPS display, upgraded Linux firmware, and a satisfying hinge that snaps shut with confidence. Perfect for GBA and SNES — the D-pad and face buttons are tuned for 2D precision. The most fun you can have for under 80 bucks.",
            "price_cents": 7999,
            "compare_price_cents": 0,
            "image": "/static/images/powkiddy-v90s.jpg",
            "gallery": json.dumps(["/static/images/powkiddy-v90s.jpg"]),
            "specs": json.dumps({
                "Display": '3.5" IPS (clamshell)',
                "CPU": "Upgraded SoC",
                "RAM": "512MB",
                "Storage": "64GB TF Card (included)",
                "Battery": "2000mAh",
                "Platforms": "NES, SNES, GBA, PS1",
                "WiFi": "No",
                "Weight": "145g",
                "Design": "Flip/clamshell"
            }),
            "stock": 25,
            "featured": 0,
            "category": "handhelds",
            "badge": ""
        },
        {
            "slug": "trimui-smart-pro",
            "name": "TrimUI Smart Pro",
            "tagline": "Big screen energy in a compact body",
            "description": "The TrimUI Smart Pro is the biggest screen in the sub-$120 category. 4.96\" IPS at 720x1280 — every game looks stunning. 5000mAh battery for marathon sessions. WiFi for scraping and updates. Dual analog sticks, rumble motor, and a form factor that feels like a mini Steam Deck. The best handheld for players who want maximum screen real estate without the premium price.",
            "price_cents": 10999,
            "compare_price_cents": 0,
            "image": "/static/images/trimui-smart-pro.jpg",
            "gallery": json.dumps(["/static/images/trimui-smart-pro.jpg"]),
            "specs": json.dumps({
                "Display": '4.96" IPS, 720x1280',
                "CPU": "Quad-core ARM",
                "RAM": "1GB",
                "Storage": "8GB eMMC + TF Card slot",
                "Battery": "5000mAh",
                "Platforms": "NES, SNES, GBA, N64, PS1, PSP",
                "WiFi": "802.11 b/g/n",
                "Weight": "280g",
                "Extras": "Dual analog, rumble"
            }),
            "stock": 20,
            "featured": 1,
            "category": "handhelds",
            "badge": "BIG SCREEN"
        },
        {
            "slug": "powkiddy-x55",
            "name": "Powkiddy X55",
            "tagline": "The 90s time machine — 5.5 inches of retro glory",
            "description": "The Powkiddy X55 is the powerhouse of the sub-$120 class. Massive 5.5\" IPS display at 1280x720 \u2014 PS1 and N64 games look incredible. RK3566 hexa-core chip powers through everything up to Dreamcast. WiFi, Bluetooth, dual analog sticks, and Jelos OS for a polished experience. Moonlight game streaming built into ROCKNIX \u2014 stream your PC games to the big 5.5\" screen. If you want the biggest, fastest retro handheld without spending $200+, this is it.",
            "price_cents": 11999,
            "compare_price_cents": 14999,
            "image": "/static/images/powkiddy-x55.jpg",
            "gallery": json.dumps(["/static/images/powkiddy-x55.jpg"]),
            "specs": json.dumps({
                "Display": '5.5" IPS, 1280x720',
                "CPU": "RK3566 Hexa-Core",
                "RAM": "1GB LPDDR4",
                "Storage": "32GB eMMC + TF Card slot",
                "Battery": "3500mAh",
                "Platforms": "NES, SNES, GBA, N64, PS1, PSP, DC",
                "WiFi": "802.11 b/g/n",
                "Bluetooth": "4.2",
                "Game Streaming": "Moonlight (720p60 via ROCKNIX)",
                "Weight": "310g",
                "OS": "Jelos"
            }),
            "stock": 20,
            "featured": 0,
            "category": "handhelds",
            "badge": "POWERHOUSE"
        },
        {
            "slug": "r36h-promax",
            "name": "R36H Pro Max",
            "tagline": "PSP style, WiFi built-in, dual sticks — the couch gaming clone",
            "description": "The R36H Pro Max is the PSP-style handheld the community has been begging for. Horizontal grip with dual analog sticks, just like holding a real PSP. 4.2\" IPS display at 1024x768 \u2014 sharper than the R36S and perfect for widescreen PS1 games. WiFi built right in, no dongle or modding needed. Runs ArkOS out of the box for RetroAchievements, box art scraping, and Moonlight game streaming. Stream your Steam library to a device that actually feels like a PlayStation. 3500mAh battery for marathon sessions. The horizontal form factor is perfect for PSP, PS1, and N64 \u2014 games that need dual sticks and a wider grip.",
            "price_cents": 7999,
            "compare_price_cents": 9999,
            "image": "/static/images/r36h-promax.jpg",
            "gallery": json.dumps(["/static/images/r36h-promax.jpg"]),
            "specs": json.dumps({
                "Display": '4.2" IPS, 1024x768',
                "CPU": "RK3326 Quad-Core",
                "RAM": "1GB DDR3",
                "Storage": "64GB TF Card (included)",
                "Battery": "3500mAh",
                "Platforms": "NES, SNES, GBA, N64, PS1, PSP",
                "WiFi": "802.11 b/g/n (built-in)",
                "Game Streaming": "Moonlight (stream PC games via WiFi)",
                "Controls": "Dual analog sticks + D-pad",
                "Design": "Horizontal / PSP-style",
                "Weight": "220g"
            }),
            "stock": 25,
            "featured": 1,
            "category": "handhelds",
            "badge": "PSP STYLE"
        },
        {
            "slug": "tetrahedron",
            "name": "Tetrahedron — Entry Stream Box",
            "tagline": "4 faces. Start streaming for under 200 bucks.",
            "description": "The Tetrahedron is the simplest Platonic solid \u2014 and the simplest way to start streaming your PC games to any room in the house. Powered by an Intel N5095 with QuickSync hardware encoding, it runs Sunshine headless and beams 720p60 gameplay to your R36S, RG34XX, or any Moonlight-compatible device. Drop it behind the TV, plug in power and ethernet, and you\u2019re done. 10W idle means it costs $1/month to run 24/7. The perfect entry point for couch gaming.",
            "price_cents": 19900,
            "compare_price_cents": 0,
            "image": "/static/images/tetrahedron.png",
            "gallery": json.dumps(["/static/images/tetrahedron.png"]),
            "specs": json.dumps({
                "CPU": "Intel N5095 Quad-Core (2.0-2.9GHz)",
                "GPU": "Intel UHD Gen 12 (QuickSync H.264)",
                "RAM": "8GB DDR4",
                "Storage": "128GB NVMe SSD",
                "Streaming": "720p60 H.264, 1080p30",
                "Software": "Sunshine (pre-configured, headless)",
                "Connectivity": "Gigabit Ethernet + WiFi 5",
                "Power Draw": "10W idle / 25W load",
                "Case": "3D printed tetrahedron (4 faces)",
                "Dimensions": "~150mm per side"
            }),
            "stock": 10,
            "featured": 0,
            "category": "steam-boxes",
            "badge": "ENTRY"
        },
        {
            "slug": "cube",
            "name": "Cube — Standard Stream Box",
            "tagline": "6 faces. 1080p60 streaming in a perfect cube.",
            "description": "The Cube is the sweet spot. Intel N100 with 8th-gen QuickSync handles 1080p60 H.264 streaming flawously \u2014 every game looks crisp on your handheld. 256GB NVMe gives room for a decent Steam library. The N100\u2019s Gen 12 iGPU also handles HEVC encode for lower bitrate streaming over WiFi. This is the one most people should buy. A perfect cube sitting on your desk, silently serving games to every screen in the house.",
            "price_cents": 29900,
            "compare_price_cents": 0,
            "image": "/static/images/cube.png",
            "gallery": json.dumps(["/static/images/cube.png"]),
            "specs": json.dumps({
                "CPU": "Intel N100 Quad-Core (0.8-3.4GHz)",
                "GPU": "Intel UHD Gen 12 24EU (QuickSync H.264 + HEVC)",
                "RAM": "8GB DDR5",
                "Storage": "256GB NVMe SSD",
                "Streaming": "1080p60 H.264 + HEVC",
                "Software": "Sunshine (pre-configured, headless)",
                "Connectivity": "Gigabit Ethernet + WiFi 6",
                "Power Draw": "8W idle / 22W load",
                "Case": "3D printed cube (6 faces)",
                "Dimensions": "~120mm per side"
            }),
            "stock": 10,
            "featured": 1,
            "category": "steam-boxes",
            "badge": "SWEET SPOT"
        },
        {
            "slug": "octahedron",
            "name": "Octahedron — Performance Stream Box",
            "tagline": "8 faces. AMD-powered 1080p HEVC streaming beast.",
            "description": "The Octahedron steps up to AMD Ryzen 5 5800H with Vega 8 graphics. Hardware HEVC encoding means smoother streams at lower bitrates \u2014 perfect for WiFi streaming to handhelds. 16GB RAM lets you run a game plus a browser plus Discord simultaneously. 512GB SSD fits a serious game library. The diamond-cut octahedron shape is a showpiece \u2014 this one lives on the entertainment unit, not hidden behind the TV.",
            "price_cents": 44900,
            "compare_price_cents": 0,
            "image": "/static/images/octahedron.png",
            "gallery": json.dumps(["/static/images/octahedron.png"]),
            "specs": json.dumps({
                "CPU": "AMD Ryzen 5 5800H (8C/16T, 3.2-4.4GHz)",
                "GPU": "AMD Radeon Vega 8 (AMF H.264 + HEVC)",
                "RAM": "16GB DDR4",
                "Storage": "512GB NVMe SSD",
                "Streaming": "1080p60 H.264 + HEVC, 1440p30",
                "Software": "Sunshine (pre-configured, headless)",
                "Connectivity": "Gigabit Ethernet + WiFi 6",
                "Power Draw": "10W idle / 45W load",
                "Case": "3D printed octahedron (8 faces)",
                "Dimensions": "~160mm tall"
            }),
            "stock": 10,
            "featured": 0,
            "category": "steam-boxes",
            "badge": "PERFORMANCE"
        },
        {
            "slug": "dodecahedron",
            "name": "Dodecahedron — High-End Stream Box",
            "tagline": "12 faces. RDNA2 graphics. 1440p streaming for the serious setup.",
            "description": "The Dodecahedron means business. AMD Ryzen 5 6800H with RDNA2 Radeon 680M graphics \u2014 the same silicon that powers the Steam Deck. Hardware AV1 encoding support for next-gen streaming quality. 16GB DDR5, 512GB Gen4 NVMe. This box doesn\u2019t just stream \u2014 it can game locally too. 12 pentagonal faces catching the light on your desk. For the enthusiast who wants the best streaming quality money can buy before going full Icosahedron.",
            "price_cents": 59900,
            "compare_price_cents": 0,
            "image": "/static/images/dodecahedron.png",
            "gallery": json.dumps(["/static/images/dodecahedron.png"]),
            "specs": json.dumps({
                "CPU": "AMD Ryzen 5 6800H (8C/16T, 3.2-4.7GHz)",
                "GPU": "AMD Radeon 680M RDNA2 (AV1 + HEVC encode)",
                "RAM": "16GB DDR5",
                "Storage": "512GB NVMe Gen4 SSD",
                "Streaming": "1440p60 HEVC, 1080p60 AV1",
                "Software": "Sunshine (pre-configured, headless)",
                "Connectivity": "2.5GbE + WiFi 6E",
                "Power Draw": "12W idle / 54W load",
                "Case": "3D printed dodecahedron (12 faces)",
                "Dimensions": "~180mm diameter"
            }),
            "stock": 5,
            "featured": 0,
            "category": "steam-boxes",
            "badge": "HIGH-END"
        },
        {
            "slug": "icosahedron",
            "name": "Icosahedron — Ultimate Stream Box",
            "tagline": "20 faces. Ryzen 7, 32GB, 4K AV1. The final form.",
            "description": "The Icosahedron is the ultimate Platonic solid and the ultimate streaming box. Ryzen 7 7840HS with RDNA3 Radeon 780M \u2014 the most powerful iGPU in any mini PC. 32GB DDR5, 1TB Gen4 NVMe. Streams 4K60 with AV1 encoding to any Moonlight client. Can also game natively at 1080p60 on most titles. 20 triangular faces form the most complex Platonic solid \u2014 a geometric masterpiece sitting at the heart of your entertainment system. The final form. The one that makes guests ask \u201cwhat IS that thing?\u201d",
            "price_cents": 89900,
            "compare_price_cents": 0,
            "image": "/static/images/icosahedron.png",
            "gallery": json.dumps(["/static/images/icosahedron.png"]),
            "specs": json.dumps({
                "CPU": "AMD Ryzen 7 7840HS (8C/16T, 3.8-5.1GHz)",
                "GPU": "AMD Radeon 780M RDNA3 (AV1 + HEVC + H.264 encode)",
                "RAM": "32GB DDR5",
                "Storage": "1TB NVMe Gen4 SSD",
                "Streaming": "4K60 AV1, 1440p120 HEVC, 1080p120 H.264",
                "Software": "Sunshine (pre-configured, headless)",
                "Connectivity": "2.5GbE + WiFi 6E + Bluetooth 5.3",
                "Power Draw": "15W idle / 65W load",
                "Case": "3D printed icosahedron (20 faces)",
                "Dimensions": "~200mm diameter"
            }),
            "stock": 5,
            "featured": 1,
            "category": "steam-boxes",
            "badge": "ULTIMATE"
        },
        {
            "slug": "r36s-wifi-mod-black",
            "name": "R36S WiFi Edition (Black)",
            "tagline": "WiFi added. Custom firmware loaded. Ready to play.",
            "description": "The R36S WiFi Edition is our exclusive upgrade. We take the legendary R36S, solder in a genuine WiFi + Bluetooth module, and flash it with ArkOS custom firmware. WiFi for RetroAchievements, automatic box art scraping, and OTA updates. Bluetooth for wireless controllers. ArkOS for the best emulation experience available. No other seller offers this. You get a fully setup, ready-to-play retro handheld with connectivity that normally costs $20 more.",
            "price_cents": 6999,
            "compare_price_cents": 8999,
            "image": "/static/images/r36s-transparent.png",
            "gallery": json.dumps(["/static/images/r36s-transparent.png", "/static/images/r36s-gaming.jpg"]),
            "specs": json.dumps({
                "Display": '3.5" IPS, 640x480',
                "CPU": "RK3326 Quad-Core",
                "RAM": "1GB DDR3",
                "Storage": "64GB TF Card (included)",
                "Battery": "3000mAh, 6+ hours",
                "WiFi": "802.11 b/g/n (RetroZone upgrade)",
                "Bluetooth": "4.2 (RetroZone upgrade)",
                "Firmware": "Arkos (custom, pre-loaded)",
                "Platforms": "NES, SNES, GBA, N64, PS1, PSP, more",
                "Features": "RetroAchievements, auto-scrape, netplay",
                "Game Streaming": "Moonlight (stream PC games via WiFi)",
                "Weight": "235g"
            }),
            "stock": 30,
            "featured": 1,
            "category": "handhelds",
            "badge": "EXCLUSIVE"
        },
        {
            "slug": "r36s-wifi-mod-white",
            "name": "R36S WiFi Edition (White)",
            "tagline": "Same exclusive WiFi upgrade in classic white",
            "description": "Our exclusive R36S WiFi Edition in the sleek white shell. Genuine WiFi + Bluetooth module professionally installed. ArkOS custom firmware pre-loaded with RetroAchievements support, automatic box art scraping, and netplay for local multiplayer. Fully configured and ready to play out of the box. The white shell is a collector favourite \u2014 grab one before they\u2019re gone.",
            "price_cents": 6999,
            "compare_price_cents": 8999,
            "image": "/static/images/r36s-transparent.png",
            "gallery": json.dumps(["/static/images/r36s-transparent.png"]),
            "specs": json.dumps({
                "Display": '3.5" IPS, 640x480',
                "CPU": "RK3326 Quad-Core",
                "RAM": "1GB DDR3",
                "Storage": "64GB TF Card (included)",
                "Battery": "3000mAh, 6+ hours",
                "WiFi": "802.11 b/g/n (RetroZone upgrade)",
                "Bluetooth": "4.2 (RetroZone upgrade)",
                "Firmware": "Arkos (custom, pre-loaded)",
                "Platforms": "NES, SNES, GBA, N64, PS1, PSP, more",
                "Features": "RetroAchievements, auto-scrape, netplay",
                "Game Streaming": "Moonlight (stream PC games via WiFi)",
                "Weight": "235g"
            }),
            "stock": 20,
            "featured": 0,
            "category": "handhelds",
            "badge": "EXCLUSIVE"
        },
        {
            "slug": "bundle-r36s-wifi-pro",
            "name": "R36S WiFi Pro Bundle",
            "tagline": "Everything you need — handheld, WiFi, case, and 128GB card",
            "description": "The ultimate starter kit. Our exclusive R36S WiFi Edition (black) with ArkOS pre-loaded, a premium carry case to protect it, and a 128GB TF card loaded with 15,000+ games. WiFi for RetroAchievements and scraping. Bluetooth for wireless controllers. Moonlight game streaming \u2014 play your Steam library from the couch. Case for protection. Bigger game library. One box, everything included. Save $25 vs buying separately.",
            "price_cents": 8999,
            "compare_price_cents": 11498,
            "image": "/static/images/r36s-transparent.png",
            "gallery": json.dumps(["/static/images/r36s-transparent.png", "/static/images/r36s-gaming.jpg"]),
            "specs": json.dumps({
                "Includes": "R36S WiFi Edition (Black) + Carry Case + 128GB Game Card",
                "Games": "15,000+ across all platforms",
                "WiFi": "802.11 b/g/n (RetroZone upgrade)",
                "Bluetooth": "4.2 (RetroZone upgrade)",
                "Firmware": "Arkos (custom, pre-loaded)",
                "Game Streaming": "Moonlight (stream PC games via WiFi)",
                "Case": "EVA hard shell with foam insert",
                "Savings": "$24.99 vs buying separately"
            }),
            "stock": 20,
            "featured": 1,
            "category": "bundles",
            "badge": "BEST VALUE"
        },
        {
            "slug": "bundle-r33s-starter",
            "name": "R33S Starter Bundle",
            "tagline": "Budget gaming, complete kit — handheld and case",
            "description": "The cheapest way into retro gaming. R33S handheld with 10,000+ games on the included 64GB card, plus a carry case to keep it safe. Pure D-pad precision for 8-bit and 16-bit classics. Perfect gift for kids or anyone curious about retro gaming. Save $5 vs buying separately.",
            "price_cents": 5999,
            "compare_price_cents": 6998,
            "image": "/static/images/r33s.jpg",
            "gallery": json.dumps(["/static/images/r33s.jpg"]),
            "specs": json.dumps({
                "Includes": "R33S Handheld + Carry Case",
                "Games": "10,000+ on included 64GB card",
                "Display": '3.5" IPS, 640x480',
                "Platforms": "NES, SNES, GBA, PS1",
                "Case": "EVA hard shell with foam insert",
                "Savings": "$5 vs buying separately"
            }),
            "stock": 25,
            "featured": 0,
            "category": "bundles",
            "badge": "GIFT IDEA"
        },
        {
            "slug": "bundle-r36s-plus-pro",
            "name": "R36S Plus Pro Bundle",
            "tagline": "The new king, fully loaded \u2014 128GB, case, WiFi ready",
            "description": "The R36S Plus is the 2025 upgrade with built-in WiFi and a gorgeous 4\" 1:1 display. This bundle adds a 128GB card packed with 15,000+ games and a carry case. WiFi for RetroAchievements, scraping, and updates. Bluetooth for wireless controllers. Bigger screen, bigger library, full protection. Save $20 vs buying separately.",
            "price_cents": 9999,
            "compare_price_cents": 11998,
            "image": "/static/images/r36s-plus.jpg",
            "gallery": json.dumps(["/static/images/r36s-plus.jpg"]),
            "specs": json.dumps({
                "Includes": "R36S Plus + Carry Case + 128GB Game Card",
                "Games": "15,000+ across all platforms",
                "Display": '4.0" IPS, 720x720 (1:1)',
                "WiFi": "802.11 b/g/n (built-in)",
                "Bluetooth": "4.2 (built-in)",
                "Platforms": "NES, SNES, GBA, N64, PS1, PSP",
                "Game Streaming": "Moonlight (with custom firmware)",
                "Case": "EVA hard shell with foam insert",
                "Savings": "$20 vs buying separately"
            }),
            "stock": 15,
            "featured": 1,
            "category": "bundles",
            "badge": "SAVE $20"
        },
        {
            "slug": "oculink-egpu-kit",
            "name": "OCuLink eGPU Upgrade Kit",
            "tagline": "Turn any Platonic Steam Box into a 4K streaming beast",
            "description": "Unlock hardware NVENC encoding on any Platonic Steam Box. This kit includes an OCuLink M.2 adapter, eGPU enclosure with 400W PSU, and all cables. Just add a desktop NVIDIA GPU (RTX 3060 or better recommended) and plug into your Steam Box via the M.2 slot. Instant NVENC encoding means 4K60 AV1 streaming with zero CPU overhead \u2014 the highest quality Moonlight experience possible. Works with Tetrahedron through Icosahedron. The simplest way to go from software encoding to hardware encoding without buying a whole new box.",
            "price_cents": 12900,
            "compare_price_cents": 16900,
            "image": "/static/images/oculink-egpu-kit.png",
            "gallery": json.dumps(["/static/images/oculink-egpu-kit.png"]),
            "specs": json.dumps({
                "Includes": "OCuLink M.2 adapter + eGPU enclosure (400W PSU) + OCuLink cable",
                "Compatible": "Any Platonic Steam Box (Tetrahedron → Icosahedron)",
                "GPU Required": "NVIDIA RTX 3060 or better (not included)",
                "Encoding": "NVENC AV1 + HEVC + H.264 hardware encoding",
                "Streaming Quality": "4K60 AV1, 1440p120 HEVC, 1080p120 H.264",
                "Interface": "PCIe Gen3 x4 via OCuLink (63 Gbps)",
                "Power Supply": "400W 80+ Bronze (included)",
                "Setup": "Plug M.2 adapter, insert GPU, install NVIDIA drivers"
            }),
            "stock": 10,
            "featured": 0,
            "category": "accessories",
            "badge": "UPGRADE"
        },
        {
            "slug": "amd-bc250-steam-box",
            "name": "BC-250 Mining APU Steam Box",
            "tagline": "Repurposed mining silicon. 16GB GDDR6. PS5-level streaming.",
            "description": "Built on the AMD BC-250 \u2014 a repurposed crypto mining APU with a secret: 16GB of unified GDDR6 memory and 6 compute cores. Originally designed for blockchain compute, now reborn as the most powerful streaming server per dollar. Paired with the ASRock BC-250 mining board in a custom 3D-printed hexagonal case. Hardware AV1 and HEVC encoding via the integrated RDNA2 GPU. Streams 4K60 to any Moonlight client. Can also game natively at 1080p60 \u2014 PS5-level performance with tuning. The sleeper hit of the Platonic Steam Box lineup. Not a Platonic solid, but the hexagon is close enough.",
            "price_cents": 49900,
            "compare_price_cents": 65000,
            "image": "/static/images/amd-bc250.png",
            "gallery": json.dumps(["/static/images/amd-bc250.png"]),
            "specs": json.dumps({
                "CPU": "AMD BC-250 (6C/12T, up to 3.0GHz, Zen 2)",
                "GPU": "Integrated RDNA2 (AV1 + HEVC + H.264 hardware encode)",
                "RAM": "16GB GDDR6 (unified, soldered)",
                "Storage": "512GB NVMe SSD",
                "Streaming": "4K60 AV1, 1440p60 HEVC, 1080p60 H.264",
                "Software": "Sunshine (pre-configured, headless)",
                "Connectivity": "GbE + WiFi 6 + Bluetooth 5.0",
                "Power Draw": "15W idle / 95W load",
                "Case": "3D printed hexagon (6 sides — almost Platonic)",
                "Dimensions": "~160mm diameter"
            }),
            "stock": 5,
            "featured": 1,
            "category": "steam-boxes",
            "badge": "SLEEPER"
        }
    ]

    for p in products:
        conn.execute("""
            INSERT INTO products (slug, name, tagline, description, price_cents, compare_price_cents,
                image, gallery, specs, stock, featured, category, badge)
            VALUES (:slug, :name, :tagline, :description, :price_cents, :compare_price_cents,
                :image, :gallery, :specs, :stock, :featured, :category, :badge)
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
    """Three-phase pricing: pre-order (+10%), in-stock (+40%), clearance (cost)."""
    from datetime import datetime, timedelta
    now = datetime.utcnow()
    arrives = datetime.fromisoformat(batch['arrives_at'])
    expires = datetime.fromisoformat(batch['expires_at'])
    expiry_dump = expires - timedelta(hours=48)

    cost = batch['cost_per_unit_cents']

    if now < arrives:
        return int(cost * 1.10)
    if now >= expiry_dump:
        return cost
    return int(cost * 1.40)


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
            "product_slug": "r36s-black",
            "units_total": 10,
            "units_sold": 0,
            "cost_per_unit_cents": 4800,
            "ordered_at": "2026-05-19T00:00:00",
            "arrives_at": "2026-06-15T00:00:00",
            "expires_at": "2026-08-10T00:00:00",
            "status": "active",
        },
        {
            # R36H Pro Max 64GB WiFi — AliExpress ~$41 USD = ~$64 AUD + $12.30 domestic + ~$2 Stripe = ~$78 AUD
            "product_slug": "r36h-promax",
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
