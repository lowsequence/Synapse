import os
import time
import asyncio
import aiosqlite
import discord
from discord import ui
from discord.ext import commands
from typing import Optional
from utils.Tools import blacklist_check, ignore_check

DB_PATH = os.path.join("database", "giveaways.db")

COLOR_GW = 0x2b2d31
FOOTER = "Synapse · Giveaways"

def parse_time(time_str: str) -> Optional[int]:
    time_str = time_str.lower().strip()
    if not time_str: return None

    multipliers = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400, 'w': 604800}

    if time_str[-1] in multipliers:
        try:
            val = int(time_str[:-1])
            return val * multipliers[time_str[-1]]
        except ValueError:
            return None
    try:
        return int(time_str)
    except ValueError:
        return None

def _err(desc: str) -> discord.Embed:
    return discord.Embed(description=f"<:SynapseExcl:1477234549552320634> {desc}", color=COLOR_GW)

def _ok(desc: str) -> discord.Embed:
    return discord.Embed(description=f"<:emoji_1769867605256:1467155817726873650> {desc}", color=COLOR_GW)

async def _init_db() -> None:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS giveaways (
                message_id    INTEGER PRIMARY KEY,
                channel_id    INTEGER,
                guild_id      INTEGER,
                host_id       INTEGER,
                prize         TEXT,
                winners_count INTEGER,
                end_time      REAL,
                status        TEXT
            );
        """)
        await db.commit()

class GiveawayCreateModal(ui.Modal, title="Create Giveaway"):
    duration_input = ui.TextInput(label="Duration (e.g., 10m, 1h, 1d)", placeholder="1h", max_length=10)
    winners_input = ui.TextInput(label="Number of Winners", placeholder="1", max_length=3)
    prize_input = ui.TextInput(label="Prize", placeholder="Discord Nitro", max_length=256)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()

        duration_secs = parse_time(self.duration_input.value)
        if not duration_secs or duration_secs < 10:
            return await interaction.followup.send(embed=_err("Invalid duration! Please provide a valid time (min 10s). Example: `10m`, `1h`"), ephemeral=True)

        try:
            winners = int(self.winners_input.value)
            if winners < 1: raise ValueError
        except ValueError:
            return await interaction.followup.send(embed=_err("Invalid number of winners!"), ephemeral=True)

        prize = self.prize_input.value
        end_time = time.time() + duration_secs
        end_timestamp = int(end_time)

        embed = discord.Embed(
            title=f"<a:synapsegiveaway:1481504400420765840> {prize}",
            description=(
                f"- **Ends**: <t:{end_timestamp}:R> (<t:{end_timestamp}:f>)\n"
                f"- **Hosted by**: {interaction.user.mention}\n"
                f"- **Entries**: **0**\n"
                f"- **Winners**: **{winners}**"
            ),
            color=COLOR_GW
        )
        embed.set_footer(text=f"Ends • {winners} Winner{'s' if winners > 1 else ''}")

        msg = await interaction.channel.send("<a:synapsegiveaway:1481504400420765840> **GIVEAWAY** <a:synapsegiveaway:1481504400420765840>", embed=embed)
        await msg.add_reaction("<a:synapsegiveaway:1481504400420765840>")

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO giveaways (message_id, channel_id, guild_id, host_id, prize, winners_count, end_time, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (msg.id, msg.channel.id, interaction.guild.id, interaction.user.id, prize, winners, end_time, "active")
            )
            await db.commit()

        await interaction.followup.send(embed=_ok("Giveaway created successfully!"), ephemeral=True)


class GiveawayDropView(ui.View):
    def __init__(self, prize: str, host: discord.Member):
        super().__init__(timeout=None)
        self.prize = prize
        self.host = host

    @ui.button(label="Claim Drop!", emoji="<a:synapsegiveaway:1481504400420765840>", style=discord.ButtonStyle.success, custom_id="gw_drop_btn")
    async def claim_btn(self, interaction: discord.Interaction, button: ui.Button):
        self.stop()
        for item in self.children:
            item.disabled = True

        embed = discord.Embed(
            title=f"<a:synapsegiveaway:1481504400420765840> Drop Claimed: {self.prize}",
            description=f"Winner: {interaction.user.mention}\nHosted by: {self.host.mention}",
            color=COLOR_GW
        )
        embed.set_footer(text="Drop Ended")

        await interaction.response.edit_message(content="<a:synapsegiveaway:1481504400420765840> **DROP ENDED** <a:synapsegiveaway:1481504400420765840>", embed=embed, view=self)
        await interaction.channel.send(f"Congratulations {interaction.user.mention}! You claimed the drop for **{self.prize}**!")


class GiveawayCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot



    @commands.command(name="gstart", aliases=["gwstart"])
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def gstart(self, ctx, duration: str, winners: int, *, prize: str):
        """Start a giveaway quickly via command (e.g. `gstart 1h 1 Nitro`)."""

        duration_secs = parse_time(duration)
        if not duration_secs or duration_secs < 10:
            return await ctx.send(embed=_err("Invalid duration! Example: `10m`, `1h`, `1d`"))

        if winners < 1:
            return await ctx.send(embed=_err("Winners must be at least 1."))

        end_time = time.time() + duration_secs
        end_timestamp = int(end_time)

        embed = discord.Embed(
            title=f"{prize}",
            description=(
                f"- **Ends**: <t:{end_timestamp}:R> (<t:{end_timestamp}:f>)\n"
                f"- **Hosted by**: {ctx.author.mention}\n"
                f"- **Winners**: **{winners}**"
            ),
            color=COLOR_GW
        )
        embed.set_footer(text=f"{winners} Winner{'s' if winners > 1 else ''}")

        try: await ctx.message.delete()
        except: pass

        msg = await ctx.send("<a:synapsegiveaway:1481504400420765840> **GIVEAWAY** <a:synapsegiveaway:1481504400420765840>", embed=embed)
        try: await msg.add_reaction("<a:synapsegiveaway:1481504400420765840>")
        except: pass

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO giveaways (message_id, channel_id, guild_id, host_id, prize, winners_count, end_time, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (msg.id, msg.channel.id, ctx.guild.id, ctx.author.id, prize, winners, end_time, "active")
            )
            await db.commit()




    @commands.command(name="gdrop", aliases=["gwdrop"])
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    async def gdrop(self, ctx, *, prize: str):
        """Start a quick drop. The first person to click wins!"""
        embed = discord.Embed(
            title=f"Quick Drop: {prize}",
            description=f"First to click the button claims the prize!\nHosted by: {ctx.author.mention}",
            color=COLOR_GW
        )
        view = GiveawayDropView(prize, ctx.author)
        try: await ctx.message.delete()
        except: pass

        await ctx.send("<a:synapsegiveaway:1481504400420765840> **FIRST TO CLICK WINS** <a:synapsegiveaway:1481504400420765840>", embed=embed, view=view)


    @commands.command(name="gend", aliases=["gwend"])
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    async def gend(self, ctx, message_id: int):
        """Force a giveaway to end immediately and pick a winner."""
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM giveaways WHERE message_id = ? AND guild_id = ? AND status = 'active'", (message_id, ctx.guild.id)) as cursor:
                gw = await cursor.fetchone()

            if not gw:
                return await ctx.send(embed=_err("Could not find an **active** giveaway with that message ID."))

            await db.execute("UPDATE giveaways SET end_time = ? WHERE message_id = ?", (time.time() - 10, message_id))
            await db.commit()

        await ctx.send(embed=_ok(f"Giveaway will end and pick a winner momentarily."))


    @commands.command(name="greroll", aliases=["gwreroll"])
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    async def greroll(self, ctx, message_id: int):
        """Reroll a winner for a decided giveaway based on reactions."""
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM giveaways WHERE message_id = ? AND guild_id = ? AND status = 'ended'", (message_id, ctx.guild.id)) as cursor:
                gw = await cursor.fetchone()

            if not gw:
                return await ctx.send(embed=_err("Could not find an **ended** giveaway with that message ID in the database."))

        ch = ctx.guild.get_channel(gw["channel_id"])
        if not ch:
            return await ctx.send(embed=_err("The original channel for that giveaway no longer exists."))

        try:
            msg = await ch.fetch_message(message_id)
        except discord.NotFound:
            return await ctx.send(embed=_err("The giveaway message was deleted. Cannot reroll."))

        entrants = []
        for reaction in msg.reactions:
            if str(reaction.emoji) == "<a:synapsegiveaway:1481504400420765840>":
                async for user in reaction.users():
                    if not user.bot:
                        entrants.append(user.id)
                break

        if not entrants:
            return await ctx.send(embed=_err("No one joined that giveaway (or reactions were removed), cannot reroll."))

        import random
        winner_id = random.choice(entrants)
        winner = ctx.guild.get_member(winner_id)

        msg_link = f"https://discord.com/channels/{ctx.guild.id}/{gw['channel_id']}/{message_id}"
        await ch.send(f"<a:synapsegiveaway:1481504400420765840> The new winner is {winner.mention if winner else f'<@{winner_id}>'}! Congratulations! ({msg_link})")
        await ctx.send(embed=_ok("Winner rerolled successfully!"))


    @commands.command(name="glist", aliases=["gwlist"])
    @commands.has_permissions(manage_guild=True)
    @blacklist_check()
    @ignore_check()
    async def glist(self, ctx):
        """List all active giveaways in the server."""
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM giveaways WHERE guild_id = ? AND status = 'active'", (ctx.guild.id,)) as cursor:
                gws = await cursor.fetchall()

        if not gws:
            return await ctx.send(embed=_err("There are no active giveaways in this server."))

        desc = ""
        for gw in gws:
            ch = ctx.guild.get_channel(gw["channel_id"])
            ch_str = ch.mention if ch else f"`#{gw['channel_id']}`"
            desc += f"• **{gw['prize']}** in {ch_str} (ID: `{gw['message_id']}`) - Ends <t:{int(gw['end_time'])}:R>\n"

        embed = discord.Embed(title="Active Giveaways", description=desc, color=COLOR_GW)
        await ctx.send(embed=embed)


async def setup(bot):
    await _init_db()
    await bot.add_cog(GiveawayCommands(bot))
