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

ITEMS = {
    "Padlock": {"cost": 500, "sell": 200, "desc": "Protects your wallet from being robbed once.", "emoji": "🔒", "type": "consumable"},
    "Bank Note": {"cost": 2500, "sell": 1000, "desc": "Expands bank capacity (if limits are enabled).", "emoji": "📜", "type": "consumable"},
    "Lottery Ticket": {"cost": 1000, "sell": 200, "desc": "A chance to win big!", "emoji": "🎟️", "type": "consumable"},
    "Gold Bar": {"cost": 10000, "sell": 9500, "desc": "A heavy bar of gold used for storing wealth safely.", "emoji": "🧈", "type": "collectible"},
    "Diamond": {"cost": 50000, "sell": 45000, "desc": "A shiny diamond.", "emoji": "💎", "type": "collectible"},
    "Fishing Rod": {"cost": 1500, "sell": 500, "desc": "Used to catch fish.", "emoji": "🎣", "type": "tool"},
    "Hunting Rifle": {"cost": 3000, "sell": 1500, "desc": "Used to hunt animals.", "emoji": "🔫", "type": "tool"},
}

CRAFTING_RECIPES = {
    "Diamond Ring": {"req": {"Diamond": 1, "Gold Bar": 1}, "cost": 1000, "emoji": "💍", "desc": "Crafted item that shows ultimate wealth."}
}

class EcoItems(commands.Cog):
    def __init__(self, client):
        self.client = client

    async def get_inv(self, user_id: int):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT item_name, count FROM user_inventory WHERE user_id = ? AND count > 0", (user_id,)) as cur:
                return await cur.fetchall()

    async def get_item(self, user_id: int, item_name: str):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT count FROM user_inventory WHERE user_id = ? AND item_name = ?", (user_id, item_name)) as cur:
                row = await cur.fetchone()
        return row[0] if row else 0

    async def add_item(self, user_id: int, item_name: str, count: int):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO user_inventory (user_id, item_name, count) VALUES (?, ?, ?) "
                "ON CONFLICT(user_id, item_name) DO UPDATE SET count = max(0, count + ?)",
                (user_id, item_name, count, count)
            )
            await db.commit()

    @commands.command(name="inventory", aliases=["inv"])
    @blacklist_check()
    @ignore_check()
    async def inventory(self, ctx, member: discord.Member = None):
        """View your items."""
        member = member or ctx.author
        items = await self.get_inv(member.id)
        if not items:
            return await ctx.reply(embed=discord.Embed(description="Inventory is empty.", color=EMBED_COLOR))

        desc = ""
        for name, count in items:
            emoji = ITEMS.get(name, {}).get("emoji", "📦")
            if name in CRAFTING_RECIPES: emoji = CRAFTING_RECIPES[name]["emoji"]
            desc += f"{emoji} **{name}** ─ {count}\n"

        embed = discord.Embed(title=f"🎒 {member.display_name}'s Inventory", description=desc, color=EMBED_COLOR)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="shop", aliases=["itemshop"])
    @blacklist_check()
    @ignore_check()
    async def shop(self, ctx):
        """View the item shop."""
        embed = discord.Embed(title="🛒 Market Shop", description="Use `buy <item>` to purchase.", color=EMBED_COLOR)
        for name, data in ITEMS.items():
            embed.add_field(name=f"{data['emoji']} {name}", value=f"Cost: **{_fmt(data['cost'])}** coins\nType: `{data['type'].title()}`", inline=True)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="buy")
    @blacklist_check()
    @ignore_check()
    async def buy_item(self, ctx, amount: int = 1, *, item_name: str = None):
        """Buy items."""
        if not item_name:
            # Maybe they didn't provide amount but provided string
            pass

        if type(amount) == str and not item_name:
            item_name = amount
            amount = 1

        item_name = item_name.title()
        if item_name not in ITEMS: return await ctx.reply(f"{E_ERR} Invalid item. Use `shop`.")
        if amount <= 0: return await ctx.reply(f"{E_ERR} Invalid amount.")

        cost = ITEMS[item_name]["cost"] * amount
        wallet = await get_wallet(ctx.author.id)
        if wallet < cost: return await ctx.reply(f"{E_ERR} You need **{_fmt(cost)}** coins to buy {amount}x {item_name}.")

        await add_wallet(ctx.author.id, -cost)
        await self.add_item(ctx.author.id, item_name, amount)
        await ctx.reply(f"{E_OK} Bought **{amount}x {item_name}** for **{_fmt(cost)}** coins!")

    @commands.command(name="sell")
    @blacklist_check()
    @ignore_check()
    async def sell_item(self, ctx, amount: int = 1, *, item_name: str = None):
        """Sell items."""
        if type(amount) == str and not item_name:
            item_name = amount
            amount = 1

        item_name = item_name.title()
        if item_name not in ITEMS and item_name not in CROPS and not item_name.endswith("Seed"):
            return await ctx.reply(f"{E_ERR} Invalid item.")
        
        has_count = await self.get_item(ctx.author.id, item_name)
        if has_count < amount: return await ctx.reply(f"{E_ERR} You only have **{has_count}x** {item_name}.")

        sell_price = ITEMS.get(item_name, {}).get("sell", 0)
        profit = sell_price * amount
        
        await self.add_item(ctx.author.id, item_name, -amount)
        await add_wallet(ctx.author.id, profit)
        await ctx.reply(f"{E_OK} Sold **{amount}x {item_name}** for **{_fmt(profit)}** coins!")

    @commands.command(name="use")
    @blacklist_check()
    @ignore_check()
    async def use_item(self, ctx, *, item_name: str):
        """Use consumable items."""
        item_name = item_name.title()
        has_count = await self.get_item(ctx.author.id, item_name)
        if has_count < 1: return await ctx.reply(f"{E_ERR} You don't have this item.")
        
        if item_name not in ITEMS or ITEMS[item_name]["type"] != "consumable":
            return await ctx.reply(f"{E_ERR} This item cannot be used.")

        await self.add_item(ctx.author.id, item_name, -1)
        
        if item_name == "Lottery Ticket":
            if random.random() < 0.10: # 10% chance
                win = random.randint(5000, 20000)
                await add_wallet(ctx.author.id, win)
                return await ctx.reply(f"🎰 The ticket was a WINNER! You won **{_fmt(win)}** coins!")
            else:
                return await ctx.reply(f"🎰 You ripped open the ticket... and it's a dud. Better luck next time.")
        
        elif item_name == "Padlock":
            return await ctx.reply(f"🔒 You used a padlock. (Functionality applied to your account passively, assuming robbing checks for this item in `economy.py`).")
        
        await ctx.reply(f"{E_OK} You used a **{item_name}**.")

    @commands.command(name="giveitem")
    @blacklist_check()
    @ignore_check()
    async def give_item(self, ctx, member: discord.Member, amount: int, *, item_name: str):
        """Give an item to another user."""
        if member.bot or member == ctx.author: return await ctx.reply(f"{E_ERR} Invalid user.")
        if amount <= 0: return await ctx.reply(f"{E_ERR} Amount must be > 0.")
        item_name = item_name.title()
        
        has_count = await self.get_item(ctx.author.id, item_name)
        if has_count < amount: return await ctx.reply(f"{E_ERR} You don't have enough {item_name}.")
        
        await self.add_item(ctx.author.id, item_name, -amount)
        await self.add_item(member.id, item_name, amount)
        await ctx.reply(f"{E_OK} Gave **{amount}x {item_name}** to {member.mention}.")

    @commands.command(name="crafting")
    @blacklist_check()
    @ignore_check()
    async def crafting(self, ctx):
        """View crafting recipes."""
        embed = discord.Embed(title="⚒️ Crafting Recipes", description="Combine items using `craft <item>`.", color=EMBED_COLOR)
        for out_name, data in CRAFTING_RECIPES.items():
            reqs = ", ".join([f"{k} x{v}" for k, v in data["req"].items()])
            embed.add_field(name=f"{data['emoji']} {out_name}", value=f"Requires: {reqs}\nCost: **{data['cost']}** coins", inline=False)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="craft")
    @blacklist_check()
    @ignore_check()
    async def craft_item(self, ctx, *, item_name: str):
        """Craft an item."""
        item_name = item_name.title()
        if item_name not in CRAFTING_RECIPES: return await ctx.reply(f"{E_ERR} Invalid recipe.")
        
        recipe = CRAFTING_RECIPES[item_name]
        
        wallet = await get_wallet(ctx.author.id)
        if wallet < recipe["cost"]: return await ctx.reply(f"{E_ERR} You need **{recipe['cost']}** coins to craft this.")

        # Verify items
        for req_item, req_amt in recipe["req"].items():
            has = await self.get_item(ctx.author.id, req_item)
            if has < req_amt: return await ctx.reply(f"{E_ERR} You are missing **{req_item}** (Need {req_amt}, have {has}).")

        await add_wallet(ctx.author.id, -recipe["cost"])
        for req_item, req_amt in recipe["req"].items():
            await self.add_item(ctx.author.id, req_item, -req_amt)
        
        await self.add_item(ctx.author.id, item_name, 1)
        await ctx.reply(f"{E_OK} Successfully crafted **{item_name}**!")

    @commands.command(name="trade")
    @blacklist_check()
    @ignore_check()
    async def trade_item(self, ctx, member: discord.Member):
        """Start a trade."""
        await ctx.reply(f"🔄 Trade feature coming soon! You can use `giveitem` and `pay` to manually trade for now.")

    @commands.command(name="iteminfo")
    @blacklist_check()
    @ignore_check()
    async def item_info(self, ctx, *, item_name: str):
        """Get info about an item."""
        item_name = item_name.title()
        data = ITEMS.get(item_name) or CRAFTING_RECIPES.get(item_name)
        if not data: return await ctx.reply(f"{E_ERR} Item not found.")
        
        embed = discord.Embed(title=f"{data.get('emoji', '📦')} {item_name}", description=data.get('desc', 'No description.'), color=EMBED_COLOR)
        if 'cost' in data: embed.add_field(name="Market Value", value=str(data['cost']))
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="lootbox")
    @blacklist_check()
    @ignore_check()
    async def lootbox(self, ctx):
        """Open a mystery lootbox for 5000 coins."""
        wallet = await get_wallet(ctx.author.id)
        if wallet < 5000: return await ctx.reply(f"{E_ERR} Lootboxes cost **5000** coins!")
        
        await add_wallet(ctx.author.id, -5000)
        pool = list(ITEMS.keys())
        won = random.choice(pool)
        
        await self.add_item(ctx.author.id, won, 1)
        emoji = ITEMS[won]["emoji"]
        await ctx.reply(f"🎁 You opened a lootbox and found: **{emoji} {won}**!")

async def setup(client):
    await client.add_cog(EcoItems(client))
