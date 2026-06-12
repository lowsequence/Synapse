import time
import asyncio
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

CROPS = {
    "Wheat": {"emoji": "🌾", "seed_cost": 10, "sell_price": 25, "growth_time": 600}, # 10 mins
    "Carrot": {"emoji": "🥕", "seed_cost": 30, "sell_price": 75, "growth_time": 1800}, # 30 mins
    "Potato": {"emoji": "🥔", "seed_cost": 50, "sell_price": 120, "growth_time": 3600}, # 1 hr
    "Corn": {"emoji": "🌽", "seed_cost": 100, "sell_price": 250, "growth_time": 7200}, # 2 hrs
    "Tomato": {"emoji": "🍅", "seed_cost": 250, "sell_price": 600, "growth_time": 14400}, # 4 hrs
}

class EcoFarm(commands.Cog):
    def __init__(self, client):
        self.client = client

    async def get_farm_inv(self, user_id: int):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT item_name, count FROM user_inventory WHERE user_id = ? AND item_name LIKE '% Seed'", (user_id,)) as cur:
                seeds = await cur.fetchall()
            async with db.execute("SELECT item_name, count FROM user_inventory WHERE user_id = ? AND item_name IN ('Wheat', 'Carrot', 'Potato', 'Corn', 'Tomato')", (user_id,)) as cur:
                crops = await cur.fetchall()
        return seeds, crops

    async def add_item(self, user_id: int, item_name: str, count: int):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO user_inventory (user_id, item_name, count) VALUES (?, ?, ?) "
                "ON CONFLICT(user_id, item_name) DO UPDATE SET count = count + ?",
                (user_id, item_name, count, count)
            )
            await db.commit()

    @commands.group(invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    async def farm(self, ctx):
        """View your farm status."""
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT plot_id, crop, plant_time, watered FROM user_farm_plots WHERE user_id = ? ORDER BY plot_id ASC", (ctx.author.id,)) as cur:
                plots = await cur.fetchall()

        if not plots:
            # Give free plot on first use
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("INSERT INTO user_farm_plots (user_id, plot_id) VALUES (?, 1)", (ctx.author.id,))
                await db.commit()
            plots = [(1, None, None, 0)]

        desc = "Your farm plots. Use `farm shop` and `buyseed` to start planting.\n\n"
        for plot_id, crop, plant_time, watered in plots:
            if not crop:
                desc += f"**Plot {plot_id}**: 🟫 Empty (Use `plant <plot> <seed>`)\n"
            else:
                elapsed = time.time() - float(plant_time)
                grow_time = CROPS[crop]["growth_time"]
                if watered: grow_time *= 0.5 
                
                if elapsed >= grow_time:
                    desc += f"**Plot {plot_id}**: {CROPS[crop]['emoji']} Ready to harvest! (Use `harvest {plot_id}`)\n"
                else:
                    rem = int(max(0, grow_time - elapsed))
                    water_str = "💧 Watered (2x speed)" if watered else "❌ Not watered (Use `water <plot>`)"
                    desc += f"**Plot {plot_id}**: 🌱 Growing {crop}... ({rem//60}m {rem%60}s remaining) - {water_str}\n"

        embed = discord.Embed(title="🚜 Your Farm", description=desc, color=EMBED_COLOR)
        await ctx.reply(embed=embed, mention_author=False)

    @farm.command(name="shop")
    @blacklist_check()
    @ignore_check()
    async def farm_shop(self, ctx):
        """Seed Shop."""
        embed = discord.Embed(title="🌻 Seed Shop", description="Buy seeds using `buyseed <crop> [amount]`", color=EMBED_COLOR)
        for crop, data in CROPS.items():
            embed.add_field(name=f"{data['emoji']} {crop} Seed", value=f"Cost: **{data['seed_cost']}** coins\nSells for: **{data['sell_price']}**\nGrowth: {data['growth_time']//60}m", inline=True)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="buyseed")
    @blacklist_check()
    @ignore_check()
    async def buy_seed(self, ctx, crop: str = None, amount: int = 1):
        """Buy seeds for your farm."""
        if not crop: return await ctx.reply(f"{E_ERR} Please specify a crop.")
        crop = crop.title()
        if crop not in CROPS: return await ctx.reply(f"{E_ERR} Invalid crop. Check `farm shop`.")
        if amount <= 0: return await ctx.reply(f"{E_ERR} Amount must be > 0.")
        
        cost = CROPS[crop]["seed_cost"] * amount
        wallet = await get_wallet(ctx.author.id)
        if wallet < cost: return await ctx.reply(f"{E_ERR} You need **{cost}** coins to buy {amount}x {crop} seeds.")
        
        await add_wallet(ctx.author.id, -cost)
        await self.add_item(ctx.author.id, f"{crop} Seed", amount)
        await ctx.reply(f"{E_OK} You bought **{amount}x {crop} Seed(s)** for **{cost}** coins!")

    @commands.command(name="plant")
    @blacklist_check()
    @ignore_check()
    async def plant_seed(self, ctx, plot_id: int = None, crop: str = None):
        """Plant a seed in a plot."""
        if plot_id is None or crop is None:
            return await ctx.reply(f"{E_ERR} Usage: `plant <plot_id> <crop>`")
        crop = crop.title()
        if crop not in CROPS: return await ctx.reply(f"{E_ERR} Invalid crop.")

        # Check if user has seed
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT count FROM user_inventory WHERE user_id = ? AND item_name = ?", (ctx.author.id, f"{crop} Seed")) as cur:
                row = await cur.fetchone()
        if not row or row[0] < 1:
            return await ctx.reply(f"{E_ERR} You don't have any **{crop} Seeds**.")

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT crop FROM user_farm_plots WHERE user_id = ? AND plot_id = ?", (ctx.author.id, plot_id)) as cur:
                plot = await cur.fetchone()
            
            if not plot: return await ctx.reply(f"{E_ERR} Invalid plot ID. Use `farm` to see plots.")
            if plot[0] is not None: return await ctx.reply(f"{E_ERR} Plot {plot_id} already has something planted.")

            await db.execute("UPDATE user_inventory SET count = count - 1 WHERE user_id = ? AND item_name = ?", (ctx.author.id, f"{crop} Seed"))
            await db.execute("UPDATE user_farm_plots SET crop = ?, plant_time = ?, watered = 0 WHERE user_id = ? AND plot_id = ?", (crop, time.time(), ctx.author.id, plot_id))
            await db.commit()
            
        await ctx.reply(f"{E_OK} You planted a **{crop} Seed** in Plot {plot_id}.")

    @commands.command(name="water")
    @blacklist_check()
    @ignore_check()
    async def water_crop(self, ctx, plot_id: int):
        """Water a crop to double growth speed."""
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT crop, watered FROM user_farm_plots WHERE user_id = ? AND plot_id = ?", (ctx.author.id, plot_id)) as cur:
                plot = await cur.fetchone()
            if not plot or not plot[0]: return await ctx.reply(f"{E_ERR} Plot is empty or invalid.")
            if plot[1] == 1: return await ctx.reply(f"{E_ERR} Plot is already watered.")

            await db.execute("UPDATE user_farm_plots SET watered = 1 WHERE user_id = ? AND plot_id = ?", (ctx.author.id, plot_id))
            await db.commit()
        await ctx.reply(f"💧 You watered Plot {plot_id}. Growth speed doubled!")

    @commands.command(name="harvest")
    @blacklist_check()
    @ignore_check()
    async def harvest_crop(self, ctx, plot_id: int):
        """Harvest your fully grown crop."""
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT crop, plant_time, watered FROM user_farm_plots WHERE user_id = ? AND plot_id = ?", (ctx.author.id, plot_id)) as cur:
                plot = await cur.fetchone()
            if not plot or not plot[0]: return await ctx.reply(f"{E_ERR} Plot is empty or invalid.")

            crop, plant_time, watered = plot
            grow_time = CROPS[crop]["growth_time"]
            if watered: grow_time *= 0.5

            if time.time() - float(plant_time) < grow_time:
                return await ctx.reply(f"{E_ERR} The crop is not ready yet.")

            yield_amt = random.randint(1, 3)
            await db.execute("UPDATE user_farm_plots SET crop = NULL, plant_time = NULL, watered = 0 WHERE user_id = ? AND plot_id = ?", (ctx.author.id, plot_id))
            await db.execute("INSERT INTO user_inventory (user_id, item_name, count) VALUES (?, ?, ?) ON CONFLICT(user_id, item_name) DO UPDATE SET count = count + ?", (ctx.author.id, crop, yield_amt, yield_amt))
            await db.commit()
        
        await ctx.reply(f"{E_OK} Harvested Plot {plot_id} and got **{yield_amt}x {crop}**!")

    @commands.command(name="sellcrop")
    @blacklist_check()
    @ignore_check()
    async def sell_crop(self, ctx, crop: str = None, amount: str = "1"):
        """Sell harvested crops for profit."""
        if not crop: return await ctx.reply(f"{E_ERR} Usage: `sellcrop <crop> [amount|all]`")
        crop = crop.title()
        if crop not in CROPS: return await ctx.reply(f"{E_ERR} Invalid crop.")
        
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT count FROM user_inventory WHERE user_id = ? AND item_name = ?", (ctx.author.id, crop)) as cur:
                row = await cur.fetchone()
        if not row or row[0] <= 0: return await ctx.reply(f"{E_ERR} You don't have any {crop} to sell.")

        has_amt = row[0]
        sell_amt = has_amt if amount.lower() == "all" else min(has_amt, int(amount))
        
        profit = CROPS[crop]["sell_price"] * sell_amt
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE user_inventory SET count = count - ? WHERE user_id = ? AND item_name = ?", (sell_amt, ctx.author.id, crop))
            await db.commit()
        await add_wallet(ctx.author.id, profit)

        await ctx.reply(f"{E_OK} Sold **{sell_amt}x {crop}** for **{profit}** coins!")

    @farm.command(name="expand")
    @blacklist_check()
    @ignore_check()
    async def farm_expand(self, ctx):
        """Buy a new farm plot (max 5)."""
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT COUNT(plot_id) FROM user_farm_plots WHERE user_id = ?", (ctx.author.id,)) as cur:
                count = (await cur.fetchone())[0]
        
        if count >= 5: return await ctx.reply(f"{E_ERR} You have reached the maximum of 5 plots.")
        cost = count * 1000 # 1000, 2000, 3000...
        
        wallet = await get_wallet(ctx.author.id)
        if wallet < cost: return await ctx.reply(f"{E_ERR} You need **{cost}** coins to expand your farm.")
        
        await add_wallet(ctx.author.id, -cost)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT INTO user_farm_plots (user_id, plot_id) VALUES (?, ?)", (ctx.author.id, count + 1))
            await db.commit()
        await ctx.reply(f"{E_OK} Farm expanded! You now have **{count + 1}** plots.")

    @farm.command(name="inv")
    @blacklist_check()
    @ignore_check()
    async def farm_inv(self, ctx):
        """View seeds and crops in inventory."""
        seeds, crops = await self.get_farm_inv(ctx.author.id)
        desc = "**Seeds:**\n"
        for s, c in seeds: desc += f"{c}x {s}\n"
        desc += "\n**Harvested Crops:**\n"
        for s, c in crops: desc += f"{c}x {s}\n"
        
        embed = discord.Embed(title="🎒 Farm Inventory", description=desc or "Empty.", color=EMBED_COLOR)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="fertilize")
    @blacklist_check()
    @ignore_check()
    async def fertilize(self, ctx, plot_id: int):
        """Use 100 coins to instantly grow crop."""
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT crop FROM user_farm_plots WHERE user_id = ? AND plot_id = ?", (ctx.author.id, plot_id)) as cur:
                plot = await cur.fetchone()
        if not plot or not plot[0]: return await ctx.reply(f"{E_ERR} Plot is empty.")

        wallet = await get_wallet(ctx.author.id)
        if wallet < 100: return await ctx.reply(f"{E_ERR} Fertilizer costs 100 coins.")

        await add_wallet(ctx.author.id, -100)
        async with aiosqlite.connect(DB_PATH) as db:
            # Set time way back to ensure growth
            await db.execute("UPDATE user_farm_plots SET plant_time = ? WHERE user_id = ? AND plot_id = ?", (time.time() - 100000, ctx.author.id, plot_id))
            await db.commit()
        await ctx.reply(f"✨ Applied fertilizer to Plot {plot_id}. The crops are instantly ready for harvest!")

    @commands.command(name="tractor")
    @blacklist_check()
    @ignore_check()
    async def tractor_use(self, ctx, cmd: str = "use"):
        if cmd == "buy":
            wallet = await get_wallet(ctx.author.id)
            if wallet < 5000: return await ctx.reply(f"{E_ERR} Tractor costs 5000 coins.")
            await add_wallet(ctx.author.id, -5000)
            await self.add_item(ctx.author.id, "Tractor", 1)
            await ctx.reply(f"{E_OK} Bought a Tractor!")
        else:
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute("SELECT count FROM user_inventory WHERE user_id = ? AND item_name = 'Tractor'", (ctx.author.id,)) as cur:
                    row = await cur.fetchone()
            if not row or row[0] < 1: return await ctx.reply(f"{E_ERR} You don't own a Tractor. `tractor buy`")

            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("UPDATE user_farm_plots SET watered = 1 WHERE user_id = ? AND crop IS NOT NULL", (ctx.author.id,))
                await db.commit()
            await ctx.reply(f"🚜 Tractor watered all your active plots!")

    @farm.command(name="leaderboard", aliases=["lb"])
    @blacklist_check()
    @ignore_check()
    async def farm_leaderboard(self, ctx):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT user_id, COUNT(plot_id) FROM user_farm_plots GROUP BY user_id ORDER BY COUNT(plot_id) DESC LIMIT 10") as cur:
                rows = await cur.fetchall()
        
        desc = ""
        for i, (uid, plots) in enumerate(rows):
            m = ctx.guild.get_member(uid)
            n = m.display_name if m else f"User {uid}"
            desc += f"`{i+1}.` **{n}** — {plots} Plots\n"
        embed = discord.Embed(title="🏆 Farm Leaderboard", description=desc or "No data.", color=EMBED_COLOR)
        await ctx.reply(embed=embed, mention_author=False)

async def setup(client):
    await client.add_cog(EcoFarm(client))
