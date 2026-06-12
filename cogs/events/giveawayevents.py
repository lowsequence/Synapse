import os
import time
import random
import asyncio
import aiosqlite
import discord
from discord.ext import commands, tasks

DB_PATH = os.path.join("database", "giveaways.db")

COLOR_GW = 0x2b2d31
FOOTER = "Synapse · Giveaways"

class GiveawayEvents(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.gw_poller.start()

    async def cog_unload(self):
        self.gw_poller.cancel()

    @tasks.loop(seconds=15)
    async def gw_poller(self):
        """Checks for expired giveaways every 15 seconds."""
        await self.bot.wait_until_ready()

        current_time = time.time()

        try:
            async with aiosqlite.connect(DB_PATH) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute("SELECT * FROM giveaways WHERE status = 'active' AND end_time <= ?", (current_time,)) as cursor:
                    expired_gws = await cursor.fetchall()

                for gw in expired_gws:
                    message_id = gw["message_id"]

                    await db.execute("UPDATE giveaways SET status = 'ended' WHERE message_id = ?", (message_id,))
                    await db.commit()

                    await self.process_giveaway_end(gw)

        except Exception as e:
            print(f"[Giveaway Poller] Error: {e}")

    async def process_giveaway_end(self, gw):
        """Draws winners from reactions and updates the discord message."""
        guild = self.bot.get_guild(gw["guild_id"])
        if not guild: return

        channel = guild.get_channel(gw["channel_id"])
        if not channel: return

        try:
            message = await channel.fetch_message(gw["message_id"])
        except discord.NotFound:
            return

        prize = gw["prize"]
        winners_count = gw["winners_count"]
        host_id = gw["host_id"]

        entrants = []
        for reaction in message.reactions:
            if str(reaction.emoji) == "<a:synapsegiveaway:1481504400420765840>":
                async for user in reaction.users():
                    if not user.bot:
                        entrants.append(user.id)
                break

        winners = []
        if len(entrants) > 0:
            winner_ids = random.sample(entrants, min(winners_count, len(entrants)))
            winners = [guild.get_member(wid) or f"<@{wid}>" for wid in winner_ids]

        embed = message.embeds[0] if message.embeds else discord.Embed(title=f"<a:synapsegiveaway:1481504400420765840> {prize}", color=COLOR_GW)

        if winners:
            winners_str = ", ".join(w.mention if isinstance(w, discord.Member) else w for w in winners)
            embed.description = (
                f"- **Ended**: <t:{int(gw['end_time'])}:R>\n"
                f"- **Hosted by**: <@{host_id}>\n"
                f"- **Entries**: **{len(entrants)}**\n"
                f"- **Winners**: {winners_str}"
            )
            embed.set_footer(text=f"Ended • {len(winners)} Winner{'s' if len(winners) > 1 else ''}")

            msg_link = f"https://discord.com/channels/{gw['guild_id']}/{gw['channel_id']}/{gw['message_id']}"
            await channel.send(f"<a:synapsegiveaway:1481504400420765840> Congratulations {winners_str}! You won the **{prize}**!\n{msg_link}")
        else:
            embed.description = (
                f"- **Ended**: <t:{int(gw['end_time'])}:R>\n"
                f"- **Hosted by**: <@{host_id}>\n"
                f"- **Entries**: **0**\n"
                f"- Nobody won the giveaway."
            )
            embed.set_footer(text="Ended • Invalid Entries")
            await channel.send(f"A giveaway for **{prize}** ended, but nobody joined!")

        await message.edit(content="<a:synapsegiveaway:1481504400420765840> **GIVEAWAY ENDED** <a:synapsegiveaway:1481504400420765840>", embed=embed, view=None)

async def setup(bot):
    await bot.add_cog(GiveawayEvents(bot))
