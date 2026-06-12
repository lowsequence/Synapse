import time
import random
import discord
from discord.ext import commands
import aiosqlite

from utils.Tools import blacklist_check, ignore_check
from utils.eco_db import DB_PATH, ensure_user, get_wallet, add_wallet

EMBED_COLOR = 0x2b2d31
E_OK  = "<:emoji_1769867605256:1467155817726873650>"
E_ERR = "<:emoji_1769867589372:1467155751456735326>"

def _fmt(n: int) -> str:
    return f"{n:,}"

# Simulated constant stocks
STOCKS = {
    "APPL": {"base": 150, "volatility": 0.05, "name": "Apple Inc."},
    "TSLA": {"base": 800, "volatility": 0.15, "name": "Tesla Inc."},
    "GOOG": {"base": 2800, "volatility": 0.03, "name": "Alphabet Inc."},
    "AMZN": {"base": 3300, "volatility": 0.04, "name": "Amazon.com Inc."}
}

CRYPTOS = {
    "BTC": {"base": 40000, "volatility": 0.10, "name": "Bitcoin"},
    "ETH": {"base": 2500, "volatility": 0.12, "name": "Ethereum"},
    "DOGE": {"base": 100, "volatility": 0.40, "name": "Dogecoin"},
}

def get_current_price(ticker: str, is_crypto: bool = False):
    data = CRYPTOS[ticker] if is_crypto else STOCKS[ticker]
    base = data["base"]
    vol = data["volatility"]
    
    # Simulate price based on current time (changes every hour)
    seed = int(time.time() / 3600) + sum(ord(c) for c in ticker)
    random.seed(seed)
    
    fluctuation = random.uniform(-vol, vol)
    price = base * (1 + fluctuation)
    
    # Reset random seed behavior
    random.seed()
    return max(1, int(price))

class EcoBusiness(commands.Cog):
    def __init__(self, client):
        self.client = client

    async def get_business(self, user_id: int):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT name, level, last_collect, employees FROM user_business WHERE user_id = ?", (user_id,)) as cur:
                return await cur.fetchone()

    @commands.group(invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    async def business(self, ctx):
        """Business system."""
        help_cog = ctx.bot.get_cog("Help")
        if help_cog:
            return await help_cog.send_group_help_auto(ctx, ctx.command)
        await ctx.reply("Use `help business` for a list of subcommands.")

    @business.command(name="start")
    @blacklist_check()
    @ignore_check()
    async def biz_start(self, ctx, *, name: str):
        """Start a business."""
        if len(name) > 32: return await ctx.reply(f"{E_ERR} Name too long.")
        
        biz = await self.get_business(ctx.author.id)
        if biz: return await ctx.reply(f"{E_ERR} You already own **{biz[0]}**.")
        
        wallet = await get_wallet(ctx.author.id)
        if wallet < 10000: return await ctx.reply(f"{E_ERR} You need **10,000** coins to start a business.")
        
        await add_wallet(ctx.author.id, -10000)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT INTO user_business (user_id, name, last_collect) VALUES (?, ?, ?)", (ctx.author.id, name, time.time()))
            await db.commit()
        
        await ctx.reply(f"{E_OK} Congratulations! You are now the CEO of **{name}**.")

    @business.command(name="info")
    @blacklist_check()
    @ignore_check()
    async def biz_info(self, ctx, member: discord.Member = None):
        """Check business stats."""
        member = member or ctx.author
        biz = await self.get_business(member.id)
        if not biz: return await ctx.reply(f"{E_ERR} No business found.")
        
        name, lvl, last_col, emp = biz
        income_per_hr = (lvl * 500) + (emp * 100)
        
        embed = discord.Embed(title=f"🏢 {name}", color=EMBED_COLOR)
        embed.add_field(name="Owner", value=member.mention)
        embed.add_field(name="Level", value=str(lvl))
        embed.add_field(name="Employees", value=str(emp))
        embed.add_field(name="Estimated Revenue", value=f"**{_fmt(income_per_hr)}** coins/hr", inline=False)
        await ctx.reply(embed=embed, mention_author=False)

    @business.command(name="collect")
    @blacklist_check()
    @ignore_check()
    async def biz_collect(self, ctx):
        """Collect passive income."""
        biz = await self.get_business(ctx.author.id)
        if not biz: return await ctx.reply(f"{E_ERR} You don't own a business.")
        
        name, lvl, last_col, emp = biz
        elapsed = time.time() - float(last_col)
        
        if elapsed < 3600:
            rem = int(3600 - elapsed)
            return await ctx.reply(f"{E_ERR} You can collect revenue again in **{rem//60}m {rem%60}s**.")
        
        # Max collect is 24 hours to prevent infinite stacking without logging in
        hours_to_collect = min(24.0, elapsed / 3600.0)
        income_per_hr = (lvl * 500) + (emp * 100)
        total_revenue = int(income_per_hr * hours_to_collect)
        
        await add_wallet(ctx.author.id, total_revenue)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE user_business SET last_collect = ? WHERE user_id = ?", (time.time(), ctx.author.id))
            await db.commit()
            
        await ctx.reply(f"{E_OK} You collected **{_fmt(total_revenue)}** coins from **{name}** for {hours_to_collect:.1f} hours of work.")

    @business.command(name="upgrade")
    @blacklist_check()
    @ignore_check()
    async def biz_upgrade(self, ctx):
        """Upgrade business level."""
        biz = await self.get_business(ctx.author.id)
        if not biz: return await ctx.reply(f"{E_ERR} You don't own a business.")
        
        lvl = biz[1]
        cost = lvl * 25000
        
        wallet = await get_wallet(ctx.author.id)
        if wallet < cost: return await ctx.reply(f"{E_ERR} You need **{_fmt(cost)}** coins to upgrade to Level {lvl+1}.")
        
        await add_wallet(ctx.author.id, -cost)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE user_business SET level = level + 1 WHERE user_id = ?", (ctx.author.id,))
            await db.commit()
            
        await ctx.reply(f"{E_OK} Business upgraded to **Level {lvl+1}**!")

    @business.command(name="hire")
    @blacklist_check()
    @ignore_check()
    async def biz_hire(self, ctx, amount: int = 1):
        """Hire employees."""
        biz = await self.get_business(ctx.author.id)
        if not biz: return await ctx.reply(f"{E_ERR} You don't own a business.")
        if amount <= 0: return await ctx.reply("Invalid amount.")
        
        cost = amount * 1000 # 1k signup bonus per employee
        wallet = await get_wallet(ctx.author.id)
        if wallet < cost: return await ctx.reply(f"{E_ERR} You need **{_fmt(cost)}** coins to hire {amount} employees.")
        
        await add_wallet(ctx.author.id, -cost)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE user_business SET employees = employees + ? WHERE user_id = ?", (amount, ctx.author.id))
            await db.commit()
            
        await ctx.reply(f"{E_OK} Hired {amount} employees!")

    @business.command(name="fire")
    @blacklist_check()
    @ignore_check()
    async def biz_fire(self, ctx, amount: int = 1):
        """Fire employees."""
        biz = await self.get_business(ctx.author.id)
        if not biz: return await ctx.reply(f"{E_ERR} You don't own a business.")
        if amount <= 0: return await ctx.reply("Invalid amount.")
        
        emp = biz[3]
        if emp < amount: return await ctx.reply(f"{E_ERR} You only have {emp} employees.")
        
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE user_business SET employees = employees - ? WHERE user_id = ?", (amount, ctx.author.id))
            await db.commit()
            
        await ctx.reply(f"{E_OK} Fired {amount} employees. Heartless.")

    @business.command(name="rename")
    @blacklist_check()
    @ignore_check()
    async def biz_rename(self, ctx, *, new_name: str):
        """Rename your business."""
        biz = await self.get_business(ctx.author.id)
        if not biz: return await ctx.reply(f"{E_ERR} You don't own a business.")
        if len(new_name) > 32: return await ctx.reply(f"{E_ERR} Name too long.")
        
        wallet = await get_wallet(ctx.author.id)
        if wallet < 5000: return await ctx.reply(f"{E_ERR} Renaming costs 5000 coins.")
        
        await add_wallet(ctx.author.id, -5000)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE user_business SET name = ? WHERE user_id = ?", (new_name, ctx.author.id))
            await db.commit()
        await ctx.reply(f"{E_OK} Business renamed to **{new_name}**.")

    @business.command(name="close")
    @blacklist_check()
    @ignore_check()
    async def biz_close(self, ctx):
        """Close your business permanently."""
        biz = await self.get_business(ctx.author.id)
        if not biz: return await ctx.reply(f"{E_ERR} You don't own a business.")
        
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM user_business WHERE user_id = ?", (ctx.author.id,))
            await db.commit()
        await ctx.reply(f"💥 You closed down **{biz[0]}**. All progress lost.")

    # STOCKS & CRYPTO MARKETS

    async def get_shares(self, user_id: int, ticker: str):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT shares FROM user_stocks WHERE user_id = ? AND symbol = ?", (user_id, ticker)) as cur:
                row = await cur.fetchone()
        return row[0] if row else 0

    async def add_shares(self, user_id: int, ticker: str, amount: int):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO user_stocks (user_id, symbol, shares) VALUES (?, ?, ?) "
                "ON CONFLICT(user_id, symbol) DO UPDATE SET shares = max(0, shares + ?)",
                (user_id, ticker, amount, amount)
            )
            await db.commit()

    @commands.group(invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    async def stocks(self, ctx):
        """Stock Market interface."""
        embed = discord.Embed(title="📈 Stock Market", description="Prices update every hour. Use `stock buy <ticker> <amt>`.", color=EMBED_COLOR)
        for ticker, data in STOCKS.items():
            price = get_current_price(ticker, is_crypto=False)
            embed.add_field(name=f"{data['name']} ({ticker})", value=f"Price: **{_fmt(price)}** coins", inline=False)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="stockbuy")
    @blacklist_check()
    @ignore_check()
    async def stock_buy(self, ctx, ticker: str, amount: int = 1):
        ticker = ticker.upper()
        if ticker not in STOCKS: return await ctx.reply(f"{E_ERR} Invalid ticker.")
        if amount <= 0: return await ctx.reply("Invalid amount.")
        
        price = get_current_price(ticker, is_crypto=False)
        cost = price * amount
        
        wallet = await get_wallet(ctx.author.id)
        if wallet < cost: return await ctx.reply(f"{E_ERR} You need **{_fmt(cost)}** coins to buy {amount} shares of {ticker}.")
        
        await add_wallet(ctx.author.id, -cost)
        await self.add_shares(ctx.author.id, ticker, amount)
        await ctx.reply(f"{E_OK} Bought **{amount}x {ticker}** for **{_fmt(cost)}** coins!")

    @commands.command(name="stocksell")
    @blacklist_check()
    @ignore_check()
    async def stock_sell(self, ctx, ticker: str, amount: str = "1"):
        ticker = ticker.upper()
        if ticker not in STOCKS: return await ctx.reply(f"{E_ERR} Invalid ticker.")
        
        shares = await self.get_shares(ctx.author.id, ticker)
        
        if amount.lower() == "all":
            amt = shares
        else:
            amt = int(amount)
            
        if amt <= 0 or shares < amt: return await ctx.reply(f"{E_ERR} You don't have enough shares.")
        
        price = get_current_price(ticker, is_crypto=False)
        profit = price * amt
        
        await self.add_shares(ctx.author.id, ticker, -amt)
        await add_wallet(ctx.author.id, profit)
        await ctx.reply(f"{E_OK} Sold **{amt}x {ticker}** for **{_fmt(profit)}** coins!")

    @commands.group(invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    async def crypto(self, ctx):
        """Crypto Market interface."""
        embed = discord.Embed(title="🪙 Crypto Market", description="Prices update every hour. Very volatile!", color=EMBED_COLOR)
        for ticker, data in CRYPTOS.items():
            price = get_current_price(ticker, is_crypto=True)
            embed.add_field(name=f"{data['name']} ({ticker})", value=f"Price: **{_fmt(price)}** coins", inline=False)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="cryptobuy")
    @blacklist_check()
    @ignore_check()
    async def crypto_buy(self, ctx, ticker: str, amount: int = 1):
        ticker = ticker.upper()
        if ticker not in CRYPTOS: return await ctx.reply(f"{E_ERR} Invalid crypto.")
        if amount <= 0: return await ctx.reply("Invalid amount.")
        
        price = get_current_price(ticker, is_crypto=True)
        cost = price * amount
        
        wallet = await get_wallet(ctx.author.id)
        if wallet < cost: return await ctx.reply(f"{E_ERR} You need **{_fmt(cost)}** coins.")
        
        await add_wallet(ctx.author.id, -cost)
        await self.add_shares(ctx.author.id, ticker, amount)
        await ctx.reply(f"{E_OK} Bought **{amount}x {ticker}** for **{_fmt(cost)}** coins!")

    @commands.command(name="cryptosell")
    @blacklist_check()
    @ignore_check()
    async def crypto_sell(self, ctx, ticker: str, amount: str = "1"):
        ticker = ticker.upper()
        if ticker not in CRYPTOS: return await ctx.reply(f"{E_ERR} Invalid crypto.")
        
        shares = await self.get_shares(ctx.author.id, ticker)
        
        if amount.lower() == "all":
            amt = shares
        else:
            amt = int(amount)
            
        if amt <= 0 or shares < amt: return await ctx.reply(f"{E_ERR} You don't have enough.")
        
        price = get_current_price(ticker, is_crypto=True)
        profit = price * amt
        
        await self.add_shares(ctx.author.id, ticker, -amt)
        await add_wallet(ctx.author.id, profit)
        await ctx.reply(f"{E_OK} Sold **{amt}x {ticker}** for **{_fmt(profit)}** coins!")

async def setup(client):
    await client.add_cog(EcoBusiness(client))
