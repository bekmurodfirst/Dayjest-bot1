import aiosqlite

DB_NAME = "laptops.db"

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        # E'lonlar jadvali
        await db.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER NOT NULL,
            channel_id INTEGER NOT NULL,
            post_link TEXT NOT NULL,
            summary_text TEXT NOT NULL,
            clicks_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        # Bosishlar tarixi jadvali
        await db.execute("""
        CREATE TABLE IF NOT EXISTS clicks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER,
            user_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        # Adminlar jadvali
        await db.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY,
            added_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        await db.commit()

# Adminlar boshqaruvi
async def add_admin_db(user_id: int, added_by: int) -> bool:
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("INSERT OR IGNORE INTO admins (user_id, added_by) VALUES (?, ?)", (user_id, added_by))
            await db.commit()
            return True
    except Exception:
        return False

async def remove_admin_db(user_id: int) -> bool:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
        await db.commit()
        return cursor.rowcount > 0

async def get_all_admins():
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT user_id, added_by, created_at FROM admins") as cursor:
            return await cursor.fetchall()

async def is_user_admin(user_id: int, super_admin_id: int) -> bool:
    if user_id == super_admin_id:
        return True
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,)) as cursor:
            res = await cursor.fetchone()
            return res is not None

# Postlar bilan ishlash
async def add_post(message_id: int, channel_id: int, post_link: str, summary_text: str) -> int:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "INSERT INTO posts (message_id, channel_id, post_link, summary_text) VALUES (?, ?, ?, ?)",
            (message_id, channel_id, post_link, summary_text)
        )
        await db.commit()
        return cursor.lastrowid

async def get_today_posts():
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM posts WHERE date(created_at, 'localtime') = date('now', 'localtime') ORDER BY id ASC"
        ) as cursor:
            return await cursor.fetchall()

async def register_click(post_id: int, user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE posts SET clicks_count = clicks_count + 1 WHERE id = ?", (post_id,))
        await db.execute("INSERT INTO clicks (post_id, user_id) VALUES (?, ?)", (post_id, user_id))
        await db.commit()

async def get_post_by_id(post_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM posts WHERE id = ?", (post_id,)) as cursor:
            return await cursor.fetchone()

async def get_engagement_stats():
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT id, summary_text, clicks_count FROM posts ORDER BY clicks_count DESC LIMIT 10") as cursor:
            return await cursor.fetchall()
