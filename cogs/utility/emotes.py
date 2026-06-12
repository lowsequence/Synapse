import discord
from discord.ext import commands
import discord.app_commands as app_commands
import aiohttp
import random
import aiosqlite

from utils.Tools import blacklist_check, ignore_check

class EmoteView(discord.ui.View):
    def __init__(self, cog, author, target, action, action_text):
        super().__init__(timeout=60)
        self.cog = cog
        self.author = author
        self.target = target
        self.action = action
        self.action_text = action_text
        self.message = None
        
        button = discord.ui.Button(label=f"{action.capitalize()} Back", style=discord.ButtonStyle.grey)
        button.callback = self.callback
        self.add_item(button)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.target.id:
            return await interaction.response.send_message(f"Only {self.target.display_name} can use this button!", ephemeral=True)
        
        # Disable the button after use
        for item in self.children:
            item.disabled = True
        await interaction.message.edit(view=self)
        
        # Trigger the "back" emote without a button
        await self.cog.send_emote(interaction, self.author, self.action, self.action_text, is_interaction=True, show_button=False)

class Emotes(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()

        self.nekos_endpoints = [
            "hug", "kiss", "cuddle", "pat", "poke", "slap", "tickle", "bite", "blush",
            "cry", "dance", "happy", "highfive", "nom", "peck", "punch", "stare", "smug",
            "thumbsup", "wave", "wink", "baka", "bored", "facepalm", "kick", "laugh", 
            "shoot", "shrug", "sleep", "smile", "think", "throw", "yawn"
        ]
        self.waifu_endpoints = [
            "kill", "bully", "yeet", "bonk", "handhold", "lick", "cringe"
        ]

        self.fuck_gifs = [
            "https://media.tenor.com/m/h812U4oUq00AAAAC/anime-bounce.gif",
            "https://media1.tenor.com/m/XoJ8V-J_Z9AAAAAC/mushoku-tensei.gif",
            "https://media1.tenor.com/m/U70B-N0Q6S0AAAAC/scums-wish.gif",
            "https://media1.tenor.com/m/oMC8h7E2TPIAAAAC/anime-wrestling.gif",
            "https://media1.tenor.com/m/nI-1H81YJ_UAAAAd/wrestling.gif"
        ]

    async def cog_unload(self):
        await self.session.close()

    async def fetch_gif(self, action: str):
        """Dynamically fetch the right GIF based on the action"""
        if action in ("fuck", "fuckk"):
            return random.choice(self.fuck_gifs), None
        elif action in self.nekos_endpoints:
            try:
                async with self.session.get(f"https://nekos.best/api/v2/{action}") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        url = data["results"][0]["url"]
                        anime_name = data["results"][0].get("anime_name")
                        return url, anime_name
            except: pass
        elif action in self.waifu_endpoints:
            try:
                async with self.session.get(f"https://api.waifu.pics/sfw/{action}") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data["url"], None
            except: pass

        return "https://media.giphy.com/media/l3q2K5jqMtzhYj8Xq/giphy.gif", None

    async def get_count(self, user1_id: int, user2_id: int, action: str):
        async with aiosqlite.connect('database/emotes.db') as db:
            async with db.execute(
                "SELECT SUM(count) FROM emote_counts WHERE ((user_id = ? AND target_id = ?) OR (user_id = ? AND target_id = ?)) AND action = ?",
                (user1_id, user2_id, user2_id, user1_id, action)
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row and row[0] else 0

    async def increment_count(self, user_id: int, target_id: int, action: str):
        async with aiosqlite.connect('database/emotes.db') as db:
            await db.execute(
                "INSERT INTO emote_counts (user_id, target_id, action, count) VALUES (?, ?, ?, 1) ON CONFLICT(user_id, target_id, action) DO UPDATE SET count = count + 1",
                (user_id, target_id, action)
            )
            await db.commit()

    async def send_emote(self, ctx_or_inter, member: discord.User, action: str, action_text: str, is_interaction=False, show_button=True):
        author = ctx_or_inter.user if is_interaction else ctx_or_inter.author
        
        if member == author:
             if is_interaction:
                 return await ctx_or_inter.response.send_message(f"{author.mention}, you can't {action} yourself!", ephemeral=True)
             else:
                 return await ctx_or_inter.send(f"{author.mention}, you can't {action} yourself!", delete_after=5)

        api_action = action
        if action == "tease": api_action = "bully"

        url, anime_name = await self.fetch_gif(api_action)

        await self.increment_count(author.id, member.id, action)
        count = await self.get_count(author.id, member.id, action)

        ordinal = {1: 'st', 2: 'nd', 3: 'rd'}.get(count % 10, 'th') if not 11 <= (count % 100) <= 13 else 'th'

        embed = discord.Embed(
            description=f"{author.mention} **{action_text}** {member.mention} for the **{count}{ordinal}** time!",
            color=0xdbdbdb
        )
        embed.set_image(url=url)
        if anime_name:
            embed.set_footer(text=f"From: {anime_name}")
        
        if show_button:
            view = EmoteView(self, author, member, action, action_text)
            if is_interaction:
                await ctx_or_inter.response.send_message(embed=embed, view=view)
                view.message = await ctx_or_inter.original_response()
            else:
                view.message = await ctx_or_inter.send(embed=embed, view=view)
        else:
            if is_interaction:
                await ctx_or_inter.response.send_message(embed=embed)
            else:
                await ctx_or_inter.send(embed=embed)

    async def send_solo_emote(self, ctx, action: str, action_text: str):
        url, anime_name = await self.fetch_gif(action)
        embed = discord.Embed(
            description=f"{ctx.author.mention} **{action_text}**!",
            color=0xdbdbdb
        )
        embed.set_image(url=url)
        if anime_name:
            embed.set_footer(text=f"From: {anime_name}")
        await ctx.send(embed=embed)


    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @commands.hybrid_command(help="Give someone a warm hug.")
    @blacklist_check()
    @ignore_check()
    async def hug(self, ctx, member: discord.User):
        await self.send_emote(ctx, member, "hug", "hugs")

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @commands.hybrid_command(help="Cuddle with someone.")
    @blacklist_check()
    @ignore_check()
    async def cuddle(self, ctx, member: discord.User):
        await self.send_emote(ctx, member, "cuddle", "cuddles with")

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @commands.hybrid_command(help="Kiss someone.")
    @blacklist_check()
    @ignore_check()
    async def kiss(self, ctx, member: discord.User):
        await self.send_emote(ctx, member, "kiss", "kisses")

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @commands.hybrid_command(help="Slap some sense into someone.")
    @blacklist_check()
    @ignore_check()
    async def slap(self, ctx, member: discord.User):
        await self.send_emote(ctx, member, "slap", "slaps")

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @commands.hybrid_command(help="Poke someone.")
    @blacklist_check()
    @ignore_check()
    async def poke(self, ctx, member: discord.User):
        await self.send_emote(ctx, member, "poke", "pokes")

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @commands.hybrid_command(help="Punch someone.")
    @blacklist_check()
    @ignore_check()
    async def punch(self, ctx, member: discord.User):
        await self.send_emote(ctx, member, "punch", "punches")

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @commands.hybrid_command(help="Kill someone (in Minecraft).")
    @blacklist_check()
    @ignore_check()
    async def kill(self, ctx, member: discord.User):
        await self.send_emote(ctx, member, "kill", "kills")

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @commands.hybrid_command(help="Tease someone.")
    @blacklist_check()
    @ignore_check()
    async def tease(self, ctx, member: discord.User):
        await self.send_emote(ctx, member, "tease", "teases")
        
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @commands.hybrid_command(help="Tickle someone.")
    @blacklist_check()
    @ignore_check()
    async def tickle(self, ctx, member: discord.User):
        await self.send_emote(ctx, member, "tickle", "tickles")

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @commands.hybrid_command(help="Bite someone.")
    @blacklist_check()
    @ignore_check()
    async def bite(self, ctx, member: discord.User):
        await self.send_emote(ctx, member, "bite", "is kinda hungry, bites")

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @commands.hybrid_command(help="Pat someone on the head.")
    @blacklist_check()
    @ignore_check()
    async def pat(self, ctx, member: discord.User):
        await self.send_emote(ctx, member, "pat", "pats")

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @commands.hybrid_command(help="Give someone a peck.")
    @blacklist_check()
    @ignore_check()
    async def peck(self, ctx, member: discord.User):
        await self.send_emote(ctx, member, "peck", "pecks")

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @commands.hybrid_command(help="Highfive someone!")
    @blacklist_check()
    @ignore_check()
    async def highfive(self, ctx, member: discord.User):
        await self.send_emote(ctx, member, "highfive", "highfives")

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @commands.hybrid_command(help="Call someone an idiot (baka).")
    @blacklist_check()
    @ignore_check()
    async def baka(self, ctx, member: discord.User):
        await self.send_emote(ctx, member, "baka", "calls baka on")

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @commands.hybrid_command(help="Stare at someone.")
    @blacklist_check()
    @ignore_check()
    async def stare(self, ctx, member: discord.User):
        await self.send_emote(ctx, member, "stare", "stares confusingly at")

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @commands.hybrid_command(help="Give someone a thumbsup.")
    @blacklist_check()
    @ignore_check()
    async def thumbsup(self, ctx, member: discord.User):
        await self.send_emote(ctx, member, "thumbsup", "gives a thumbs up to")

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @commands.hybrid_command(help="Wink at someone.")
    @blacklist_check()
    @ignore_check()
    async def wink(self, ctx, member: discord.User):
        await self.send_emote(ctx, member, "wink", "winks at")

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @commands.hybrid_command(help="Wave at someone.")
    @blacklist_check()
    @ignore_check()
    async def wave(self, ctx, member: discord.User):
        await self.send_emote(ctx, member, "wave", "waves at")

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @commands.hybrid_command(help="Yeet someone far away.")
    @blacklist_check()
    @ignore_check()
    async def yeet(self, ctx, member: discord.User):
        await self.send_emote(ctx, member, "yeet", "yeets")

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @commands.hybrid_command(help="Bonk someone for being horny.")
    @blacklist_check()
    @ignore_check()
    async def bonk(self, ctx, member: discord.User):
        await self.send_emote(ctx, member, "bonk", "bonks")


    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @commands.hybrid_command(help="Hold hands contextually.")
    @blacklist_check()
    @ignore_check()
    async def handhold(self, ctx, member: discord.User):
        await self.send_emote(ctx, member, "handhold", "holds hands with")

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @commands.hybrid_command(help="Lick someone.")
    @blacklist_check()
    @ignore_check()
    async def lick(self, ctx, member: discord.User):
        await self.send_emote(ctx, member, "lick", "licks")


    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @commands.hybrid_command(help="Show off your dance moves.")
    @blacklist_check()
    @ignore_check()
    async def dance(self, ctx):
        await self.send_solo_emote(ctx, "dance", "starts dancing")

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @commands.hybrid_command(help="Blush intensely.")
    @blacklist_check()
    @ignore_check()
    async def blush(self, ctx):
        await self.send_solo_emote(ctx, "blush", "is blushing")

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @commands.hybrid_command(help="Cry your eyes out.")
    @blacklist_check()
    @ignore_check()
    async def cry(self, ctx):
        await self.send_solo_emote(ctx, "cry", "is crying")

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @commands.hybrid_command(help="Express pure happiness.")
    @blacklist_check()
    @ignore_check()
    async def happy(self, ctx):
        await self.send_solo_emote(ctx, "happy", "is extremely happy")

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @commands.hybrid_command(help="Act smug.")
    @blacklist_check()
    @ignore_check()
    async def smug(self, ctx):
        await self.send_solo_emote(ctx, "smug", "smirks smugly")

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @commands.hybrid_command(help="Cringe at something.")
    @blacklist_check()
    @ignore_check()
    async def cringe(self, ctx):
        await self.send_solo_emote(ctx, "cringe", "cringes")


async def setup(bot):
    async with aiosqlite.connect('database/emotes.db') as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS emote_counts (
                     user_id INTEGER,
                     target_id INTEGER,
                     action TEXT,
                     count INTEGER DEFAULT 0,
                     PRIMARY KEY (user_id, target_id, action))''')
        await db.commit()
    await bot.add_cog(Emotes(bot))
