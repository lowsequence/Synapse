import random
import discord
from discord.ext import commands
import aiosqlite

from utils.Tools import blacklist_check, ignore_check
from utils.eco_db import DB_PATH, ensure_user, get_wallet, add_wallet, remaining_cooldown, set_cooldown

EMBED_COLOR = 0x2b2d31
E_OK  = "<:emoji_1769867605256:1467155817726873650>"
E_ERR = "<:emoji_1769867589372:1467155751456735326>"

def _fmt(n: int) -> str:
    return f"{n:,}"

PET_TYPES = {
    "Dog": {"emoji": "🐶", "cost": 1000},
    "Cat": {"emoji": "🐱", "cost": 1000},
    "Bird": {"emoji": "🐦", "cost": 2000},
    "Dragon": {"emoji": "🐉", "cost": 15000},
    "Wolf": {"emoji": "🐺", "cost": 8000},
    "Fox": {"emoji": "🦊", "cost": 5000},
}

class EcoPets(commands.Cog):
    def __init__(self, client):
        self.client = client

    async def get_pet(self, user_id: int):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT pet_name, pet_type, level, xp, hunger, happiness FROM user_pets WHERE user_id = ?", (user_id,)) as cur:
                return await cur.fetchone()

    async def update_pet(self, user_id: int, col: str, val: int):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(f"UPDATE user_pets SET {col} = ? WHERE user_id = ?", (val, user_id))
            await db.commit()

    @commands.group(invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    async def pet(self, ctx):
        """Pet system commands."""
        help_cog = ctx.bot.get_cog("Help")
        if help_cog:
            return await help_cog.send_group_help_auto(ctx, ctx.command)
        await ctx.reply("Use `help pet` for a list of subcommands.")

    @pet.command(name="shop")
    @blacklist_check()
    @ignore_check()
    async def pet_shop(self, ctx):
        """View available pets."""
        embed = discord.Embed(title="🏪 Pet Shop", description="Adopt a new pet! Use `pet buy <type>`.", color=EMBED_COLOR)
        for ptype, data in PET_TYPES.items():
            embed.add_field(name=f"{data['emoji']} {ptype}", value=f"Cost: **{_fmt(data['cost'])}** coins", inline=True)
        await ctx.reply(embed=embed, mention_author=False)

    @pet.command(name="buy")
    @blacklist_check()
    @ignore_check()
    async def pet_buy(self, ctx, ptype: str = None):
        """Adopt a new pet."""
        if not ptype:
            return await ctx.reply(f"{E_ERR} Please specify a pet type. Use `pet shop`.")
        ptype = ptype.title()
        if ptype not in PET_TYPES:
            return await ctx.reply(f"{E_ERR} Invalid pet type. Use `pet shop`.")

        pet = await self.get_pet(ctx.author.id)
        if pet:
            return await ctx.reply(f"{E_ERR} You already have a pet! Use `pet release` to free it first.")

        cost = PET_TYPES[ptype]["cost"]
        wallet = await get_wallet(ctx.author.id)
        if wallet < cost:
            return await ctx.reply(f"{E_ERR} You need **{_fmt(cost)}** coins to buy a {ptype}.")

        await add_wallet(ctx.author.id, -cost)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT INTO user_pets (user_id, pet_name, pet_type) VALUES (?, ?, ?)", (ctx.author.id, f"{ctx.author.name}'s {ptype}", ptype))
            await db.commit()

        await ctx.reply(f"{E_OK} You successfully adopted a {PET_TYPES[ptype]['emoji']} **{ptype}**!")

    @pet.command(name="info")
    @blacklist_check()
    @ignore_check()
    async def pet_info(self, ctx, member: discord.Member = None):
        """Check pet stats."""
        member = member or ctx.author
        pet = await self.get_pet(member.id)
        if not pet:
            return await ctx.reply(f"{E_ERR} {'You do' if member == ctx.author else 'They do'} not own a pet.")

        pname, ptype, lvl, xp, hunger, happiness = pet
        emoji = PET_TYPES.get(ptype, {}).get("emoji", "🐾")

        embed = discord.Embed(title=f"{emoji} {pname}", color=EMBED_COLOR)
        embed.add_field(name="Type", value=ptype, inline=True)
        embed.add_field(name="Level", value=str(lvl), inline=True)
        embed.add_field(name="XP", value=f"{xp}/{lvl*100}", inline=True)
        embed.add_field(name="Hunger", value=f"{hunger}/100", inline=True)
        embed.add_field(name="Happiness", value=f"{happiness}/100", inline=True)
        await ctx.reply(embed=embed, mention_author=False)

    @pet.command(name="feed")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 300, commands.BucketType.user)
    async def pet_feed(self, ctx):
        """Feed your pet (Costs 50 coins)."""
        pet = await self.get_pet(ctx.author.id)
        if not pet:
            return await ctx.reply(f"{E_ERR} You don't have a pet.")
        
        _, _, _, _, hunger, _ = pet
        if hunger >= 100:
            return await ctx.reply(f"{E_ERR} Your pet is already full!")

        wallet = await get_wallet(ctx.author.id)
        if wallet < 50:
            return await ctx.reply(f"{E_ERR} You need 50 coins to buy pet food.")

        await add_wallet(ctx.author.id, -50)
        new_hunger = min(100, hunger + random.randint(15, 30))
        await self.update_pet(ctx.author.id, "hunger", new_hunger)
        await ctx.reply(f"{E_OK} You fed your pet! Hunger is now **{new_hunger}/100**.")

    @pet.command(name="play")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 300, commands.BucketType.user)
    async def pet_play(self, ctx):
        """Play with your pet."""
        pet = await self.get_pet(ctx.author.id)
        if not pet:
            return await ctx.reply(f"{E_ERR} You don't have a pet.")
        
        _, _, _, _, _, happiness = pet
        if happiness >= 100:
            return await ctx.reply(f"{E_ERR} Your pet is already extremely happy!")

        new_happiness = min(100, happiness + random.randint(15, 30))
        await self.update_pet(ctx.author.id, "happiness", new_happiness)
        await ctx.reply(f"{E_OK} You played with your pet! Happiness is now **{new_happiness}/100**.")

    @pet.command(name="train")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 1800, commands.BucketType.user)
    async def pet_train(self, ctx):
        """Train your pet for XP."""
        pet = await self.get_pet(ctx.author.id)
        if not pet:
            return await ctx.reply(f"{E_ERR} You don't have a pet.")
        
        pname, _, lvl, xp, hunger, happiness = pet
        if hunger < 20 or happiness < 20:
            return await ctx.reply(f"{E_ERR} Your pet is too hungry or sad to train. Feed or play with it first.")

        gained_xp = random.randint(20, 50)
        new_xp = xp + gained_xp
        new_lvl = lvl

        res = f"{E_OK} Your pet trained hard and gained **{gained_xp} XP**!"
        
        if new_xp >= lvl * 100:
            new_lvl += 1
            new_xp -= (lvl * 100)
            res += f"\n🎉 **{pname}** leveled up to **Level {new_lvl}**!"

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE user_pets SET xp = ?, level = ?, hunger = max(0, hunger - 10), happiness = max(0, happiness - 10) WHERE user_id = ?", (new_xp, new_lvl, ctx.author.id))
            await db.commit()

        await ctx.reply(res)

    @pet.command(name="rename")
    @blacklist_check()
    @ignore_check()
    async def pet_rename(self, ctx, *, new_name: str):
        """Rename your pet."""
        if len(new_name) > 32:
            return await ctx.reply(f"{E_ERR} Name too long.")
        pet = await self.get_pet(ctx.author.id)
        if not pet:
            return await ctx.reply(f"{E_ERR} You don't have a pet.")
        
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE user_pets SET pet_name = ? WHERE user_id = ?", (new_name, ctx.author.id))
            await db.commit()
        await ctx.reply(f"{E_OK} Pet renamed to **{new_name}**.")

    @pet.command(name="clean")
    @blacklist_check()
    @ignore_check()
    async def pet_clean(self, ctx):
        """Maintain pet hygiene."""
        pet = await self.get_pet(ctx.author.id)
        if not pet: return await ctx.reply(f"{E_ERR} You don't have a pet.")
        await ctx.reply(f"🧼 You gave your pet a nice bath. It looks squeaky clean!")

    @pet.command(name="heal")
    @blacklist_check()
    @ignore_check()
    async def pet_heal(self, ctx):
        """Heal sick pet."""
        pet = await self.get_pet(ctx.author.id)
        if not pet: return await ctx.reply(f"{E_ERR} You don't have a pet.")
        wallet = await get_wallet(ctx.author.id)
        if wallet < 200: return await ctx.reply(f"{E_ERR} Vet bills cost 200 coins.")
        await add_wallet(ctx.author.id, -200)
        await self.update_pet(ctx.author.id, "happiness", 100)
        await ctx.reply(f"🩺 You paid 200 coins and healed your pet to full health.")

    @pet.command(name="release")
    @blacklist_check()
    @ignore_check()
    async def pet_release(self, ctx):
        """Release your pet into the wild."""
        pet = await self.get_pet(ctx.author.id)
        if not pet:
            return await ctx.reply(f"{E_ERR} You don't have a pet.")
        
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM user_pets WHERE user_id = ?", (ctx.author.id,))
            await db.commit()
        await ctx.reply(f"🕊 The pet was released into the wild. Goodbye, {pet[0]}.")

    @pet.command(name="battle")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 300, commands.BucketType.user)
    async def pet_battle(self, ctx, member: discord.Member):
        """Battle another user's pet."""
        if member.bot or member == ctx.author:
            return await ctx.reply(f"{E_ERR} You cannot battle this user.")
        
        my_pet = await self.get_pet(ctx.author.id)
        their_pet = await self.get_pet(member.id)

        if not my_pet: return await ctx.reply(f"{E_ERR} You don't have a pet.")
        if not their_pet: return await ctx.reply(f"{E_ERR} {member.name} doesn't have a pet.")

        my_pname, _, my_lvl, _, _, _ = my_pet
        th_pname, _, th_lvl, _, _, _ = their_pet

        my_power = random.randint(1, my_lvl * 10)
        th_power = random.randint(1, th_lvl * 10)

        if my_power > th_power:
            await add_wallet(ctx.author.id, 100)
            await ctx.reply(f"⚔️ **{my_pname}** ({my_power} dmg) defeated **{th_pname}** ({th_power} dmg)!\n{E_OK} You won 100 coins!")
        elif th_power > my_power:
            await add_wallet(member.id, 100)
            await ctx.reply(f"⚔️ **{th_pname}** ({th_power} dmg) defeated **{my_pname}** ({my_power} dmg)!\n{E_ERR} You lost!")
        else:
            await ctx.reply("⚔️ It's a tie! Both pets retreat.")

    @pet.command(name="leaderboard", aliases=["lb"])
    @blacklist_check()
    @ignore_check()
    async def pet_leaderboard(self, ctx):
        """Highest level pets."""
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT user_id, pet_name, level FROM user_pets ORDER BY level DESC LIMIT 10") as cur:
                rows = await cur.fetchall()

        if not rows:
            return await ctx.reply(embed=discord.Embed(description="No pets found.", color=EMBED_COLOR))

        desc = ""
        for i, (uid, pname, lvl) in enumerate(rows):
            member = ctx.guild.get_member(uid)
            name = member.display_name if member else f"User {uid}"
            desc += f"`{i+1}.` **{pname}** (Lvl {lvl}) — Owned by {name}\n"

        embed = discord.Embed(title="🏆 Pet Leaderboard", description=desc, color=EMBED_COLOR)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="petlist")
    @blacklist_check()
    @ignore_check()
    async def pet_list(self, ctx):
        """Global command to list your pet."""
        await ctx.invoke(self.pet_info)

async def setup(client):
    await client.add_cog(EcoPets(client))
