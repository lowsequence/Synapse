import time
import aiosqlite

DB = "database/dating.db"


async def init_db():
    async with aiosqlite.connect(DB) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS profiles (
                user_id     INTEGER PRIMARY KEY,
                bio         TEXT DEFAULT '',
                gender      TEXT DEFAULT '',
                age         INTEGER DEFAULT 0,
                looking_for TEXT DEFAULT '',
                interests   TEXT DEFAULT '',
                likes       INTEGER DEFAULT 0,
                dislikes    INTEGER DEFAULT 0,
                views       INTEGER DEFAULT 0,
                created_at  REAL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS marriages (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                user1_id  INTEGER NOT NULL,
                user2_id  INTEGER NOT NULL,
                guild_id  INTEGER NOT NULL,
                vow       TEXT DEFAULT '',
                couple_name TEXT DEFAULT '',
                married_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS crushes (
                user_id   INTEGER NOT NULL,
                crush_id  INTEGER NOT NULL,
                guild_id  INTEGER NOT NULL,
                set_at    REAL NOT NULL,
                PRIMARY KEY (user_id, guild_id)
            );
            CREATE TABLE IF NOT EXISTS dates (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                user1_id  INTEGER NOT NULL,
                user2_id  INTEGER NOT NULL,
                guild_id  INTEGER NOT NULL,
                location  TEXT DEFAULT '',
                date_at   REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS gifts (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                from_id   INTEGER NOT NULL,
                to_id     INTEGER NOT NULL,
                guild_id  INTEGER NOT NULL,
                item      TEXT NOT NULL,
                value     INTEGER DEFAULT 0,
                sent_at   REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS love_letters (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                from_id   INTEGER NOT NULL,
                to_id     INTEGER NOT NULL,
                guild_id  INTEGER NOT NULL,
                message   TEXT NOT NULL,
                sent_at   REAL NOT NULL,
                read      INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS blocks (
                user_id    INTEGER NOT NULL,
                blocked_id INTEGER NOT NULL,
                guild_id   INTEGER NOT NULL,
                PRIMARY KEY (user_id, blocked_id, guild_id)
            );
            CREATE TABLE IF NOT EXISTS children (
                parent1_id INTEGER NOT NULL,
                parent2_id INTEGER NOT NULL,
                child_id   INTEGER NOT NULL,
                guild_id   INTEGER NOT NULL,
                adopted_at REAL NOT NULL,
                PRIMARY KEY (child_id, guild_id)
            );
            CREATE TABLE IF NOT EXISTS cooldowns (
                user_id  INTEGER NOT NULL,
                action   TEXT NOT NULL,
                used_at  REAL NOT NULL,
                PRIMARY KEY (user_id, action)
            );
        """)
        await db.commit()



async def get_profile(user_id: int):
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM profiles WHERE user_id=?", (user_id,)) as c:
            return await c.fetchone()

async def upsert_profile(user_id: int, **kw):
    async with aiosqlite.connect(DB) as db:
        existing = await (await db.execute("SELECT 1 FROM profiles WHERE user_id=?", (user_id,))).fetchone()
        if existing:
            sets = ", ".join(f"{k}=?" for k in kw)
            await db.execute(f"UPDATE profiles SET {sets} WHERE user_id=?", (*kw.values(), user_id))
        else:
            kw["user_id"] = user_id
            kw.setdefault("created_at", time.time())
            cols = ", ".join(kw.keys())
            phs = ", ".join("?" for _ in kw)
            await db.execute(f"INSERT INTO profiles ({cols}) VALUES ({phs})", tuple(kw.values()))
        await db.commit()

async def delete_profile(user_id: int):
    async with aiosqlite.connect(DB) as db:
        await db.execute("DELETE FROM profiles WHERE user_id=?", (user_id,))
        await db.commit()

async def increment_profile(user_id: int, field: str, amount: int = 1):
    async with aiosqlite.connect(DB) as db:
        await db.execute(f"UPDATE profiles SET {field}={field}+? WHERE user_id=?", (amount, user_id))
        await db.commit()



async def get_marriage(user_id: int, guild_id: int):
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM marriages WHERE guild_id=? AND (user1_id=? OR user2_id=?)",
            (guild_id, user_id, user_id)
        ) as c:
            return await c.fetchone()

async def create_marriage(u1: int, u2: int, guild_id: int):
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "INSERT INTO marriages (user1_id, user2_id, guild_id, married_at) VALUES (?,?,?,?)",
            (u1, u2, guild_id, time.time())
        )
        await db.commit()

async def delete_marriage(user_id: int, guild_id: int):
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "DELETE FROM marriages WHERE guild_id=? AND (user1_id=? OR user2_id=?)",
            (guild_id, user_id, user_id)
        )
        await db.commit()

async def update_marriage(user_id: int, guild_id: int, **kw):
    async with aiosqlite.connect(DB) as db:
        sets = ", ".join(f"{k}=?" for k in kw)
        await db.execute(
            f"UPDATE marriages SET {sets} WHERE guild_id=? AND (user1_id=? OR user2_id=?)",
            (*kw.values(), guild_id, user_id, user_id)
        )
        await db.commit()

async def get_guild_marriages(guild_id: int, limit: int = 200):
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM marriages WHERE guild_id=? ORDER BY married_at ASC LIMIT ?",
            (guild_id, limit)
        ) as c:
            return await c.fetchall()

async def renew_marriage(user_id: int, guild_id: int):
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "UPDATE marriages SET married_at=? WHERE guild_id=? AND (user1_id=? OR user2_id=?)",
            (time.time(), guild_id, user_id, user_id)
        )
        await db.commit()



async def set_crush(user_id: int, crush_id: int, guild_id: int):
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "INSERT OR REPLACE INTO crushes (user_id, crush_id, guild_id, set_at) VALUES (?,?,?,?)",
            (user_id, crush_id, guild_id, time.time())
        )
        await db.commit()

async def get_crush(user_id: int, guild_id: int):
    async with aiosqlite.connect(DB) as db:
        async with db.execute("SELECT crush_id FROM crushes WHERE user_id=? AND guild_id=?", (user_id, guild_id)) as c:
            row = await c.fetchone()
            return row[0] if row else None

async def delete_crush(user_id: int, guild_id: int):
    async with aiosqlite.connect(DB) as db:
        await db.execute("DELETE FROM crushes WHERE user_id=? AND guild_id=?", (user_id, guild_id))
        await db.commit()

async def count_crushes_on(user_id: int, guild_id: int) -> int:
    async with aiosqlite.connect(DB) as db:
        async with db.execute("SELECT COUNT(*) FROM crushes WHERE crush_id=? AND guild_id=?", (user_id, guild_id)) as c:
            row = await c.fetchone()
            return row[0] if row else 0



async def add_date(u1: int, u2: int, guild_id: int, location: str = ""):
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "INSERT INTO dates (user1_id, user2_id, guild_id, location, date_at) VALUES (?,?,?,?,?)",
            (u1, u2, guild_id, location, time.time())
        )
        await db.commit()

async def get_date_history(user_id: int, guild_id: int, limit: int = 10):
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM dates WHERE guild_id=? AND (user1_id=? OR user2_id=?) ORDER BY date_at DESC LIMIT ?",
            (guild_id, user_id, user_id, limit)
        ) as c:
            return await c.fetchall()



async def add_gift(from_id: int, to_id: int, guild_id: int, item: str, value: int):
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "INSERT INTO gifts (from_id, to_id, guild_id, item, value, sent_at) VALUES (?,?,?,?,?,?)",
            (from_id, to_id, guild_id, item, value, time.time())
        )
        await db.commit()

async def get_gifts_received(user_id: int, guild_id: int, limit: int = 20):
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM gifts WHERE to_id=? AND guild_id=? ORDER BY sent_at DESC LIMIT ?",
            (user_id, guild_id, limit)
        ) as c:
            return await c.fetchall()

async def get_gift_stats(user_id: int, guild_id: int):
    async with aiosqlite.connect(DB) as db:
        async with db.execute(
            "SELECT COUNT(*), COALESCE(SUM(value),0) FROM gifts WHERE to_id=? AND guild_id=?",
            (user_id, guild_id)
        ) as c:
            return await c.fetchone()

async def get_gift_leaderboard(guild_id: int, limit: int = 10):
    async with aiosqlite.connect(DB) as db:
        async with db.execute(
            "SELECT to_id, COUNT(*) as cnt, SUM(value) as total FROM gifts WHERE guild_id=? GROUP BY to_id ORDER BY total DESC LIMIT ?",
            (guild_id, limit)
        ) as c:
            return await c.fetchall()



async def send_love_letter(from_id: int, to_id: int, guild_id: int, message: str):
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "INSERT INTO love_letters (from_id, to_id, guild_id, message, sent_at) VALUES (?,?,?,?,?)",
            (from_id, to_id, guild_id, message, time.time())
        )
        await db.commit()

async def get_love_letters(user_id: int, guild_id: int, limit: int = 10):
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM love_letters WHERE to_id=? AND guild_id=? ORDER BY sent_at DESC LIMIT ?",
            (user_id, guild_id, limit)
        ) as c:
            return await c.fetchall()



async def add_block(user_id: int, blocked_id: int, guild_id: int):
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "INSERT OR IGNORE INTO blocks (user_id, blocked_id, guild_id) VALUES (?,?,?)",
            (user_id, blocked_id, guild_id)
        )
        await db.commit()

async def remove_block(user_id: int, blocked_id: int, guild_id: int):
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "DELETE FROM blocks WHERE user_id=? AND blocked_id=? AND guild_id=?",
            (user_id, blocked_id, guild_id)
        )
        await db.commit()

async def is_blocked(user_id: int, target_id: int, guild_id: int) -> bool:
    async with aiosqlite.connect(DB) as db:
        async with db.execute(
            "SELECT 1 FROM blocks WHERE user_id=? AND blocked_id=? AND guild_id=?",
            (target_id, user_id, guild_id)
        ) as c:
            return await c.fetchone() is not None



async def adopt_child(p1: int, p2: int, child_id: int, guild_id: int):
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "INSERT OR REPLACE INTO children (parent1_id, parent2_id, child_id, guild_id, adopted_at) VALUES (?,?,?,?,?)",
            (p1, p2, child_id, guild_id, time.time())
        )
        await db.commit()

async def remove_child(child_id: int, guild_id: int):
    async with aiosqlite.connect(DB) as db:
        await db.execute("DELETE FROM children WHERE child_id=? AND guild_id=?", (child_id, guild_id))
        await db.commit()

async def get_children(user_id: int, guild_id: int):
    async with aiosqlite.connect(DB) as db:
        async with db.execute(
            "SELECT child_id, adopted_at FROM children WHERE guild_id=? AND (parent1_id=? OR parent2_id=?)",
            (guild_id, user_id, user_id)
        ) as c:
            return await c.fetchall()

async def get_parents(child_id: int, guild_id: int):
    async with aiosqlite.connect(DB) as db:
        async with db.execute(
            "SELECT parent1_id, parent2_id FROM children WHERE child_id=? AND guild_id=?",
            (child_id, guild_id)
        ) as c:
            return await c.fetchone()



async def remaining_cooldown(user_id: int, action: str, duration: float) -> float:
    async with aiosqlite.connect(DB) as db:
        async with db.execute(
            "SELECT used_at FROM cooldowns WHERE user_id=? AND action=?",
            (user_id, action)
        ) as c:
            row = await c.fetchone()
            if not row:
                return 0
            elapsed = time.time() - row[0]
            return max(0, duration - elapsed)

async def set_cooldown(user_id: int, action: str):
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "INSERT OR REPLACE INTO cooldowns (user_id, action, used_at) VALUES (?,?,?)",
            (user_id, action, time.time())
        )
        await db.commit()



async def wipe_guild(guild_id: int):
    async with aiosqlite.connect(DB) as db:
        for tbl in ("marriages", "crushes", "dates", "gifts", "love_letters", "blocks", "children"):
            await db.execute(f"DELETE FROM {tbl} WHERE guild_id=?", (guild_id,))
        await db.commit()
