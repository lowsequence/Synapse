import time
import aiosqlite

DB_PATH = "database/economy.db"



async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(
            """
            CREATE TABLE IF NOT EXISTS economy (
                user_id INTEGER PRIMARY KEY,
                wallet  INTEGER NOT NULL DEFAULT 0,
                bank    INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS cooldowns (
                user_id       INTEGER NOT NULL,
                cooldown_type TEXT    NOT NULL,
                last_used     REAL    NOT NULL DEFAULT 0,
                PRIMARY KEY (user_id, cooldown_type)
            );

            CREATE TABLE IF NOT EXISTS user_jobs (
                user_id  INTEGER NOT NULL,
                job_name TEXT    NOT NULL,
                PRIMARY KEY (user_id, job_name)
            );

            CREATE TABLE IF NOT EXISTS user_pets (
                user_id INTEGER PRIMARY KEY,
                pet_name TEXT NOT NULL,
                pet_type TEXT NOT NULL,
                level INTEGER NOT NULL DEFAULT 1,
                xp INTEGER NOT NULL DEFAULT 0,
                hunger INTEGER NOT NULL DEFAULT 100,
                happiness INTEGER NOT NULL DEFAULT 100
            );

            CREATE TABLE IF NOT EXISTS user_inventory (
                user_id INTEGER NOT NULL,
                item_name TEXT NOT NULL,
                count INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (user_id, item_name)
            );

            CREATE TABLE IF NOT EXISTS user_farm_plots (
                user_id INTEGER NOT NULL,
                plot_id INTEGER NOT NULL,
                crop TEXT,
                plant_time REAL,
                watered INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (user_id, plot_id)
            );

            CREATE TABLE IF NOT EXISTS user_business (
                user_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                level INTEGER NOT NULL DEFAULT 1,
                last_collect REAL NOT NULL DEFAULT 0,
                employees INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS user_stocks (
                user_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                shares INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (user_id, symbol)
            );
            """
        )
        await db.commit()



async def ensure_user(user_id: int, starting_wallet: int = 50) -> None:
    """Create account if it doesn't exist (INSERT OR IGNORE)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO economy (user_id, wallet, bank) VALUES (?, ?, 0)",
            (user_id, starting_wallet),
        )
        await db.commit()


async def get_balance(user_id: int) -> tuple:
    """Return (wallet, bank) tuple. Ensures account exists first."""
    await ensure_user(user_id)
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT wallet, bank FROM economy WHERE user_id = ?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
    return row or (0, 0)


async def get_wallet(user_id: int) -> int:
    w, _ = await get_balance(user_id)
    return w


async def get_bank(user_id: int) -> int:
    _, b = await get_balance(user_id)
    return b


async def add_wallet(user_id: int, amount: int) -> int:
    """Add amount to wallet (can be negative). Returns new wallet value."""
    await ensure_user(user_id)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE economy SET wallet = wallet + ? WHERE user_id = ?",
            (amount, user_id),
        )
        await db.commit()
        async with db.execute(
            "SELECT wallet FROM economy WHERE user_id = ?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
    return row[0] if row else 0


async def add_bank(user_id: int, amount: int) -> int:
    """Add amount to bank (can be negative). Returns new bank value."""
    await ensure_user(user_id)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE economy SET bank = bank + ? WHERE user_id = ?",
            (amount, user_id),
        )
        await db.commit()
        async with db.execute(
            "SELECT bank FROM economy WHERE user_id = ?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
    return row[0] if row else 0


async def set_wallet(user_id: int, amount: int) -> None:
    await ensure_user(user_id)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE economy SET wallet = ? WHERE user_id = ?", (amount, user_id)
        )
        await db.commit()


async def set_bank(user_id: int, amount: int) -> None:
    await ensure_user(user_id)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE economy SET bank = ? WHERE user_id = ?", (amount, user_id)
        )
        await db.commit()


async def transfer(from_id: int, to_id: int, amount: int) -> bool:
    """Move amount from from_id's wallet to to_id's wallet atomically."""
    await ensure_user(from_id)
    await ensure_user(to_id)
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT wallet FROM economy WHERE user_id = ?", (from_id,)
        ) as cur:
            row = await cur.fetchone()
        if not row or row[0] < amount:
            return False
        await db.execute(
            "UPDATE economy SET wallet = wallet - ? WHERE user_id = ?", (amount, from_id)
        )
        await db.execute(
            "UPDATE economy SET wallet = wallet + ? WHERE user_id = ?", (amount, to_id)
        )
        await db.commit()
    return True


async def get_leaderboard(limit: int = 200) -> list:
    """Return list of (user_id, wallet, bank, total) sorted by total desc."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT user_id, wallet, bank, wallet+bank AS total "
            "FROM economy ORDER BY total DESC LIMIT ?",
            (limit,),
        ) as cur:
            return await cur.fetchall()



async def get_cooldown(user_id: int, cooldown_type: str) -> float:
    """Return timestamp of last use, or 0.0 if never used."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT last_used FROM cooldowns WHERE user_id = ? AND cooldown_type = ?",
            (user_id, cooldown_type),
        ) as cur:
            row = await cur.fetchone()
    return row[0] if row else 0.0


async def set_cooldown(user_id: int, cooldown_type: str) -> None:
    """Record current timestamp as last use."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO cooldowns (user_id, cooldown_type, last_used) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id, cooldown_type) DO UPDATE SET last_used = excluded.last_used",
            (user_id, cooldown_type, time.time()),
        )
        await db.commit()


async def remaining_cooldown(user_id: int, cooldown_type: str, duration: float) -> float:
    """Return seconds remaining on cooldown (0.0 if ready)."""
    last = await get_cooldown(user_id, cooldown_type)
    remaining = duration - (time.time() - last)
    return max(0.0, remaining)



async def get_user_jobs(user_id: int) -> list:
    """Return list of job names owned by user."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT job_name FROM user_jobs WHERE user_id = ?", (user_id,)
        ) as cur:
            rows = await cur.fetchall()
    return [r[0] for r in rows]


async def add_user_job(user_id: int, job_name: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO user_jobs (user_id, job_name) VALUES (?, ?)",
            (user_id, job_name),
        )
        await db.commit()


async def remove_user_job(user_id: int, job_name: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM user_jobs WHERE user_id = ? AND job_name = ?",
            (user_id, job_name),
        )
        await db.commit()
