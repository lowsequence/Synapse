from __future__ import annotations
import random
import time
import math
import discord
from discord.ext import commands
from utils.Tools import blacklist_check, ignore_check
from utils import dating_db as db

COLOR = 0x2b2d31
E_TICK = "<:emoji_1769867605256:1467155817726873650>"
E_CROSS = "<:emoji_1769867589372:1467155751456735326>"
E_HEART = "\u2764\ufe0f"
E_RING = "\U0001F48D"
E_ROSE = "\U0001F339"
E_CHOC = "\U0001F36B"
E_TEDDY = "\U0001F9F8"
E_LETTER = "\U0001F48C"
E_STAR = "\u2B50"
FOOTER = "Synapse \u00b7 Dating System"

GIFT_CATALOG = {
    "rose": {"emoji": E_ROSE, "value": 10, "name": "Rose"},
    "chocolate": {"emoji": E_CHOC, "value": 15, "name": "Chocolate"},
    "teddy": {"emoji": E_TEDDY, "value": 25, "name": "Teddy Bear"},
    "ring": {"emoji": E_RING, "value": 100, "name": "Ring"},
    "star": {"emoji": E_STAR, "value": 50, "name": "Star"},
    "letter": {"emoji": E_LETTER, "value": 5, "name": "Love Letter"},
}

DATE_LOCATIONS = [
    "\U0001F3D6\ufe0f a sunset beach", "\U0001F3A1 an amusement park", "\U0001F374 a fancy restaurant",
    "\U0001F3AC a movie theater", "\U0001F3E1 a cozy cabin", "\U0001F304 a rooftop at sunset",
    "\U0001F3B6 a live concert", "\U0001F490 a flower garden", "\u2615 a cute caf\u00e9",
    "\U0001F30C a stargazing hill", "\U0001F3A8 an art museum", "\U0001F389 a carnival",
]

PICKUP_LINES = [
    "Are you a magician? Because whenever I look at you, everyone else disappears.",
    "Do you have a map? I just got lost in your eyes.",
    "Is your name Google? Because you have everything I\u2019ve been searching for.",
    "Are you a campfire? Because you\u2019re hot and I want s\u2019more.",
    "Do you believe in love at first sight, or should I walk by again?",
    "If you were a vegetable, you\u2019d be a cute-cumber.",
    "Are you Wi-Fi? Because I\u2019m feeling a connection.",
    "Is your dad a boxer? Because you\u2019re a knockout.",
    "Do you have a Band-Aid? Because I just scraped my knee falling for you.",
    "Are you a parking ticket? Because you\u2019ve got fine written all over you.",
    "If beauty were time, you\u2019d be an eternity.",
    "Your hand looks heavy, can I hold it for you?",
    "I must be a snowflake, because I\u2019ve fallen for you.",
    "Are you a bank loan? Because you\u2019ve got my interest.",
    "Was your dad an alien? Because there\u2019s nothing else like you on Earth.",
]

LOVE_QUOTES = [
    "The best thing to hold onto in life is each other. \u2014 Audrey Hepburn",
    "You know you\u2019re in love when you can\u2019t fall asleep because reality is finally better than your dreams. \u2014 Dr. Seuss",
    "In all the world, there is no heart for me like yours. \u2014 Maya Angelou",
    "I have found the one whom my soul loves. \u2014 Song of Solomon",
    "Love is composed of a single soul inhabiting two bodies. \u2014 Aristotle",
    "Whatever our souls are made of, his and mine are the same. \u2014 Emily Bront\u00eb",
    "The heart was made to be broken. \u2014 Oscar Wilde",
    "Love looks not with the eyes, but with the mind. \u2014 Shakespeare",
]

BREAKUP_SONGS = [
    "\U0001F3B5 *Someone Like You* \u2014 Adele\n> Never mind, I\u2019ll find someone like you\u2026",
    "\U0001F3B5 *We Are Never Getting Back Together* \u2014 Taylor Swift\n> Like, ever.",
    "\U0001F3B5 *Irreplaceable* \u2014 Beyonc\u00e9\n> To the left, to the left\u2026",
    "\U0001F3B5 *Thank U, Next* \u2014 Ariana Grande\n> I\u2019m so grateful for my ex.",
    "\U0001F3B5 *Somebody That I Used to Know* \u2014 Gotye\n> But you didn\u2019t have to cut me off\u2026",
    "\U0001F3B5 *Drivers License* \u2014 Olivia Rodrigo\n> I still hear your voice in the traffic\u2026",
]

HOROSCOPES = {
    "aries": "Bold passion is headed your way! Your fire energy attracts admirers like moths to a flame \U0001F525",
    "taurus": "Slow and steady wins the heart. A surprise gesture of love is coming \U0001F339",
    "gemini": "Communication is key today. Express what\u2019s in your heart \U0001F4AC",
    "cancer": "Your nurturing nature draws someone special closer. Open up emotionally \U0001F312",
    "leo": "The spotlight of love shines on you. Confidence is your best accessory \U0001F451",
    "virgo": "Pay attention to the details in love. Small gestures mean everything \U0001F4DD",
    "libra": "Balance in relationships brings peace. A harmonious connection awaits \u2696\ufe0f",
    "scorpio": "Intensity is your superpower. Deep emotional bonds are forming \U0001F982",
    "sagittarius": "Adventure awaits in love! Be open to unexpected romantic journeys \U0001F3F9",
    "capricorn": "Commitment pays off. Your loyalty is about to be rewarded \U0001F3D4\ufe0f",
    "aquarius": "Unconventional love is in the stars. Embrace what makes your bond unique \U0001F30A",
    "pisces": "Dreamy romance is written in the stars. Trust your intuition \U0001F41F",
}

WYR_QUESTIONS = [
    "Would you rather have a partner who\u2019s an amazing cook or an incredible dancer?",
    "Would you rather get 1000 love letters or 1 perfect gift?",
    "Would you rather date someone funny or someone romantic?",
    "Would you rather have a long-distance relationship or live together from day one?",
    "Would you rather forget your anniversary or your partner\u2019s birthday?",
    "Would you rather go on a mountain adventure or a beach vacation with your partner?",
    "Would you rather have a public proposal or a private one?",
    "Would you rather share every meal together or every hobby?",
]

EIGHT_BALL_LOVE = [
    "The stars say YES! \u2728", "Love is definitely in the air \U0001F496",
    "My sources say no\u2026 sorry \U0001F494", "It\u2019s complicated\u2026 \U0001F914",
    "100% yes! Go for it! \U0001F49D", "Better not tell you now\u2026 \U0001F648",
    "Signs point to maybe \U0001F52E", "Absolutely not. Run. \U0001F3C3",
    "The universe is shipping it! \U0001F6A2", "Ask again after a date \u2615",
    "Without a doubt! \U0001F970", "Very doubtful\u2026 \U0001F62C",
]

FLIRT_LINES = [
    "winks at", "blows a kiss to", "sends heart eyes to",
    "writes a poem for", "serenades", "draws a portrait of",
    "gives bedroom eyes to", "sends sparkles to", "gazes lovingly at",
]

SERENADE_SONGS = [
    "\U0001F3B6 *Can\u2019t Help Falling in Love* \u2014 Elvis",
    "\U0001F3B6 *All of Me* \u2014 John Legend",
    "\U0001F3B6 *Perfect* \u2014 Ed Sheeran",
    "\U0001F3B6 *At Last* \u2014 Etta James",
    "\U0001F3B6 *Thinking Out Loud* \u2014 Ed Sheeran",
    "\U0001F3B6 *I Will Always Love You* \u2014 Whitney Houston",
]

def _ts(ts: float) -> str:
    return f"<t:{int(ts)}:R>"

def _err(text: str) -> discord.Embed:
    return discord.Embed(description=f"{E_CROSS} {text}", color=COLOR)

def _ok(text: str) -> discord.Embed:
    return discord.Embed(description=f"{E_TICK} {text}", color=COLOR)


class ProposalView(discord.ui.View):
    def __init__(self, author: discord.Member, target: discord.Member):
        super().__init__(timeout=60)
        self.author = author
        self.target = target
        self.result = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.target.id:
            await interaction.response.send_message("This isn't for you!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Accept \u2764\ufe0f", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.result = True
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()

    @discord.ui.button(label="Decline \U0001F494", style=discord.ButtonStyle.red)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.result = False
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()


class DateRequestView(discord.ui.View):
    def __init__(self, author: discord.Member, target: discord.Member):
        super().__init__(timeout=60)
        self.author = author
        self.target = target
        self.result = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.target.id:
            await interaction.response.send_message("This isn't for you!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Let's go! \U0001F493", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.result = True
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()

    @discord.ui.button(label="Not today \U0001F44B", style=discord.ButtonStyle.grey)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.result = False
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()


class LetterPager(discord.ui.View):
    PER_PAGE = 5

    def __init__(self, ctx, letters):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.letters = letters
        self.page = 0
        self.pages = max(1, math.ceil(len(letters) / self.PER_PAGE))
        self.message = None
        self._update()

    def _update(self):
        self.prev_btn.disabled = self.page == 0
        self.next_btn.disabled = self.page >= self.pages - 1

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("Not yours!", ephemeral=True)
            return False
        return True

    def _build(self) -> discord.Embed:
        start = self.page * self.PER_PAGE
        chunk = self.letters[start:start + self.PER_PAGE]
        lines = []
        for i, lt in enumerate(chunk, start + 1):
            lines.append(f"**#{i}** \u2014 {_ts(lt['sent_at'])}\n> {lt['message'][:100]}")
        embed = discord.Embed(description="\n\n".join(lines) or "No letters.", color=COLOR)
        embed.set_author(name=f"{E_LETTER} Your Love Letters", icon_url=self.ctx.author.display_avatar.url)
        embed.set_footer(text=f"Page {self.page+1}/{self.pages} \u00b7 {FOOTER}")
        return embed

    @discord.ui.button(label="\u25c0", style=discord.ButtonStyle.secondary)
    async def prev_btn(self, interaction: discord.Interaction, _):
        self.page -= 1
        self._update()
        await interaction.response.edit_message(embed=self._build(), view=self)

    @discord.ui.button(label="\u25b6", style=discord.ButtonStyle.secondary)
    async def next_btn(self, interaction: discord.Interaction, _):
        self.page += 1
        self._update()
        await interaction.response.edit_message(embed=self._build(), view=self)


class Dating(commands.Cog):
    """Dating & Marriage System \u2014 58 commands."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _blocked(self, ctx, target):
        if await db.is_blocked(ctx.author.id, target.id, ctx.guild.id):
            await ctx.reply(embed=_err("That user has blocked you from dating interactions."), mention_author=False)
            return True
        return False




    @commands.group(name="dating", invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    async def dating(self, ctx):
        """Dating system commands."""
        embed = discord.Embed(
            description=(
                f"**{E_HEART} Dating System**\n\n"
                "Use `dating setup` to create your profile!\n\n"
                "**Categories:**\n"
                "> \U0001F464 `dating profile / setup / bio / gender / age / lookingfor / interests / deleteprofile`\n"
                "> \U0001F48D `marry / divorce / married / marriageinfo / anniversary / vow / coupleinfo / couplename / marriages / remarry`\n"
                "> \U0001F493 `crush / crushreveal / crushlist / confess / loveletter / loveletters / flirt / rizz / friendzone`\n"
                "> \U0001F3E0 `date / datenight / datehistory / dategift / datemood / blinddate / speeddate / dateidea`\n"
                "> \U0001F381 `gift / gifts / gifttop / rose / chocolate / serenade / lovebomb / breakupsong`\n"
                "> \U0001F52E `compatibility / lovetest / horoscope / pickup / wouldyourather / lovequote / love8ball / shiplb`\n"
                "> \U0001F46A `adopt / disown / children / family`\n"
                "> \u2699\ufe0f `dating block / unblock / resetall`"
            ),
            color=COLOR,
        )
        embed.set_footer(text=FOOTER)
        await ctx.send(embed=embed)

    @dating.command(name="profile")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def dating_profile(self, ctx, member: discord.Member = None):
        """View a dating profile."""
        target = member or ctx.author
        profile = await db.get_profile(target.id)
        if not profile:
            return await ctx.reply(embed=_err(f"{'You don' if target == ctx.author else f'{target.display_name} doesn'}'t have a dating profile. Use `dating setup`."), mention_author=False)
        if target != ctx.author:
            await db.increment_profile(target.id, "views")
        embed = discord.Embed(color=COLOR)
        embed.set_author(name=f"{target.display_name}'s Dating Profile", icon_url=target.display_avatar.url)
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="\U0001F4DD Bio", value=profile["bio"] or "*Not set*", inline=False)
        embed.add_field(name="\U0001F464 Gender", value=profile["gender"] or "*Not set*", inline=True)
        embed.add_field(name="\U0001F382 Age", value=str(profile["age"]) if profile["age"] else "*Not set*", inline=True)
        embed.add_field(name="\U0001F50D Looking For", value=profile["looking_for"] or "*Not set*", inline=True)
        embed.add_field(name="\u2728 Interests", value=profile["interests"] or "*Not set*", inline=False)
        embed.add_field(name="\U0001F4CA Stats", value=f"\U0001F441\ufe0f {profile['views']} views \u00b7 \U0001F44D {profile['likes']} likes \u00b7 \U0001F44E {profile['dislikes']} dislikes", inline=False)
        marriage = await db.get_marriage(target.id, ctx.guild.id)
        if marriage:
            pid = marriage["user2_id"] if marriage["user1_id"] == target.id else marriage["user1_id"]
            partner = ctx.guild.get_member(pid)
            pname = partner.display_name if partner else f"User {pid}"
            embed.add_field(name=f"{E_RING} Married To", value=f"{pname} ({_ts(marriage['married_at'])})", inline=False)
        embed.set_footer(text=FOOTER)
        await ctx.reply(embed=embed, mention_author=False)

    @dating.command(name="setup")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def dating_setup(self, ctx):
        """Create your dating profile."""
        existing = await db.get_profile(ctx.author.id)
        if existing:
            return await ctx.reply(embed=_err("You already have a profile! Use `dating bio`, `dating gender`, etc. to edit."), mention_author=False)
        await db.upsert_profile(ctx.author.id, bio="", gender="", age=0, looking_for="", interests="")
        embed = discord.Embed(
            description=(
                f"{E_TICK} **Dating profile created!**\n\n"
                "Set it up with:\n"
                "> `dating bio <text>` \u2014 Set your bio\n"
                "> `dating gender <gender>` \u2014 Set your gender\n"
                "> `dating age <age>` \u2014 Set your age\n"
                "> `dating lookingfor <type>` \u2014 What you're looking for\n"
                "> `dating interests <list>` \u2014 Your interests"
            ),
            color=COLOR,
        )
        embed.set_footer(text=FOOTER)
        await ctx.reply(embed=embed, mention_author=False)

    @dating.command(name="bio")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    async def dating_bio(self, ctx, *, text: str):
        """Set your profile bio."""
        if len(text) > 200:
            return await ctx.reply(embed=_err("Bio must be 200 characters or less."), mention_author=False)
        p = await db.get_profile(ctx.author.id)
        if not p:
            return await ctx.reply(embed=_err("Create a profile first with `dating setup`."), mention_author=False)
        await db.upsert_profile(ctx.author.id, bio=text)
        await ctx.reply(embed=_ok(f"Bio updated!"), mention_author=False)

    @dating.command(name="gender")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    async def dating_gender(self, ctx, *, gender: str):
        """Set your gender."""
        if len(gender) > 30:
            return await ctx.reply(embed=_err("Keep it under 30 characters."), mention_author=False)
        p = await db.get_profile(ctx.author.id)
        if not p:
            return await ctx.reply(embed=_err("Create a profile first with `dating setup`."), mention_author=False)
        await db.upsert_profile(ctx.author.id, gender=gender)
        await ctx.reply(embed=_ok("Gender updated!"), mention_author=False)

    @dating.command(name="age")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    async def dating_age(self, ctx, age: int):
        """Set your age (13-99)."""
        if age < 13 or age > 99:
            return await ctx.reply(embed=_err("Age must be between 13 and 99."), mention_author=False)
        p = await db.get_profile(ctx.author.id)
        if not p:
            return await ctx.reply(embed=_err("Create a profile first with `dating setup`."), mention_author=False)
        await db.upsert_profile(ctx.author.id, age=age)
        await ctx.reply(embed=_ok("Age updated!"), mention_author=False)

    @dating.command(name="lookingfor")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    async def dating_lookingfor(self, ctx, *, text: str):
        """Set what you're looking for."""
        if len(text) > 100:
            return await ctx.reply(embed=_err("Keep it under 100 characters."), mention_author=False)
        p = await db.get_profile(ctx.author.id)
        if not p:
            return await ctx.reply(embed=_err("Create a profile first with `dating setup`."), mention_author=False)
        await db.upsert_profile(ctx.author.id, looking_for=text)
        await ctx.reply(embed=_ok("Looking-for updated!"), mention_author=False)

    @dating.command(name="interests")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    async def dating_interests(self, ctx, *, text: str):
        """Set your interests (comma-separated)."""
        if len(text) > 200:
            return await ctx.reply(embed=_err("Keep it under 200 characters."), mention_author=False)
        p = await db.get_profile(ctx.author.id)
        if not p:
            return await ctx.reply(embed=_err("Create a profile first with `dating setup`."), mention_author=False)
        await db.upsert_profile(ctx.author.id, interests=text)
        await ctx.reply(embed=_ok("Interests updated!"), mention_author=False)

    @dating.command(name="deleteprofile")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    async def dating_deleteprofile(self, ctx):
        """Delete your dating profile."""
        p = await db.get_profile(ctx.author.id)
        if not p:
            return await ctx.reply(embed=_err("You don't have a profile."), mention_author=False)
        await db.delete_profile(ctx.author.id)
        await ctx.reply(embed=_ok("Profile deleted."), mention_author=False)





    @commands.command(name="marry")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def marry(self, ctx, member: discord.Member = None):
        """Propose to someone!"""
        if member is None:
            return await ctx.reply(embed=_err("Usage: `marry <@user>`"), mention_author=False)
        if member.bot or member.id == ctx.author.id:
            return await ctx.reply(embed=_err("Invalid target."), mention_author=False)
        if await self._blocked(ctx, member):
            return
        existing = await db.get_marriage(ctx.author.id, ctx.guild.id)
        if existing:
            return await ctx.reply(embed=_err("You're already married! Divorce first."), mention_author=False)
        target_m = await db.get_marriage(member.id, ctx.guild.id)
        if target_m:
            return await ctx.reply(embed=_err(f"{member.display_name} is already married!"), mention_author=False)
        embed = discord.Embed(
            description=f"{E_RING} **{ctx.author.display_name}** is proposing to **{member.display_name}**!\n\n{member.mention}, do you accept?",
            color=COLOR,
        )
        embed.set_footer(text=FOOTER)
        view = ProposalView(ctx.author, member)
        msg = await ctx.send(embed=embed, view=view)
        await view.wait()
        if view.result is True:
            await db.create_marriage(ctx.author.id, member.id, ctx.guild.id)
            embed = discord.Embed(
                description=f"{E_HEART} **{ctx.author.display_name}** and **{member.display_name}** are now married! Congratulations! {E_RING}\U0001F389",
                color=COLOR,
            )
            embed.set_footer(text=FOOTER)
            await msg.edit(embed=embed, view=None)
        elif view.result is False:
            await msg.edit(embed=discord.Embed(description=f"\U0001F494 **{member.display_name}** declined the proposal...", color=COLOR), view=None)
        else:
            await msg.edit(embed=discord.Embed(description=f"\u23F0 Proposal timed out.", color=COLOR), view=None)

    @commands.command(name="divorce")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def divorce(self, ctx):
        """Divorce your partner."""
        marriage = await db.get_marriage(ctx.author.id, ctx.guild.id)
        if not marriage:
            return await ctx.reply(embed=_err("You're not married!"), mention_author=False)
        pid = marriage["user2_id"] if marriage["user1_id"] == ctx.author.id else marriage["user1_id"]
        partner = ctx.guild.get_member(pid)
        pname = partner.display_name if partner else f"User {pid}"
        await db.delete_marriage(ctx.author.id, ctx.guild.id)
        embed = discord.Embed(description=f"\U0001F494 **{ctx.author.display_name}** divorced **{pname}**...", color=COLOR)
        embed.set_footer(text=FOOTER)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="married")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def married(self, ctx, member: discord.Member = None):
        """Check if someone is married."""
        target = member or ctx.author
        marriage = await db.get_marriage(target.id, ctx.guild.id)
        if not marriage:
            return await ctx.reply(embed=_err(f"{'You are' if target == ctx.author else f'{target.display_name} is'} not married."), mention_author=False)
        pid = marriage["user2_id"] if marriage["user1_id"] == target.id else marriage["user1_id"]
        partner = ctx.guild.get_member(pid)
        pname = partner.display_name if partner else f"User {pid}"
        embed = discord.Embed(description=f"{E_RING} **{target.display_name}** is married to **{pname}** ({_ts(marriage['married_at'])})", color=COLOR)
        embed.set_footer(text=FOOTER)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="marriageinfo")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def marriageinfo(self, ctx, member: discord.Member = None):
        """Detailed marriage info."""
        target = member or ctx.author
        m = await db.get_marriage(target.id, ctx.guild.id)
        if not m:
            return await ctx.reply(embed=_err("Not married."), mention_author=False)
        pid = m["user2_id"] if m["user1_id"] == target.id else m["user1_id"]
        partner = ctx.guild.get_member(pid)
        pname = partner.display_name if partner else f"User {pid}"
        kids = await db.get_children(target.id, ctx.guild.id)
        days = int((time.time() - m["married_at"]) / 86400)
        embed = discord.Embed(color=COLOR)
        embed.set_author(name=f"Marriage Info", icon_url=target.display_avatar.url)
        embed.add_field(name=f"{E_RING} Partners", value=f"{target.display_name} & {pname}", inline=False)
        if m["couple_name"]:
            embed.add_field(name="\U0001F3F7\ufe0f Couple Name", value=m["couple_name"], inline=True)
        embed.add_field(name="\U0001F4C5 Married For", value=f"{days} days", inline=True)
        embed.add_field(name="\U0001F4DD Vow", value=m["vow"] or "*No vow set*", inline=False)
        embed.add_field(name="\U0001F46A Children", value=str(len(kids)) if kids else "None", inline=True)
        embed.set_footer(text=FOOTER)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="anniversary")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def anniversary(self, ctx):
        """View your wedding anniversary."""
        m = await db.get_marriage(ctx.author.id, ctx.guild.id)
        if not m:
            return await ctx.reply(embed=_err("You're not married!"), mention_author=False)
        embed = discord.Embed(description=f"{E_RING} Your anniversary: <t:{int(m['married_at'])}:D> ({_ts(m['married_at'])})", color=COLOR)
        embed.set_footer(text=FOOTER)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="vow")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    async def vow(self, ctx, *, text: str):
        """Set your marriage vows."""
        m = await db.get_marriage(ctx.author.id, ctx.guild.id)
        if not m:
            return await ctx.reply(embed=_err("You're not married!"), mention_author=False)
        if len(text) > 300:
            return await ctx.reply(embed=_err("Vow must be 300 characters or less."), mention_author=False)
        await db.update_marriage(ctx.author.id, ctx.guild.id, vow=text)
        await ctx.reply(embed=_ok("Marriage vow updated!"), mention_author=False)

    @commands.command(name="coupleinfo")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def coupleinfo(self, ctx):
        """View combined couple stats."""
        m = await db.get_marriage(ctx.author.id, ctx.guild.id)
        if not m:
            return await ctx.reply(embed=_err("You're not married!"), mention_author=False)
        pid = m["user2_id"] if m["user1_id"] == ctx.author.id else m["user1_id"]
        partner = ctx.guild.get_member(pid)
        pname = partner.display_name if partner else f"User {pid}"
        g1 = await db.get_gift_stats(ctx.author.id, ctx.guild.id)
        g2 = await db.get_gift_stats(pid, ctx.guild.id)
        d1 = await db.get_date_history(ctx.author.id, ctx.guild.id)
        kids = await db.get_children(ctx.author.id, ctx.guild.id)
        embed = discord.Embed(color=COLOR)
        embed.set_author(name=m["couple_name"] or f"{ctx.author.display_name} & {pname}")
        embed.add_field(name="\U0001F381 Gifts Received", value=f"{ctx.author.display_name}: {g1[0]}\n{pname}: {g2[0]}", inline=True)
        embed.add_field(name="\U0001F3E0 Total Dates", value=str(len(d1)), inline=True)
        embed.add_field(name="\U0001F46A Children", value=str(len(kids)) if kids else "None", inline=True)
        days = int((time.time() - m["married_at"]) / 86400)
        embed.add_field(name="\U0001F4C5 Together For", value=f"{days} days", inline=True)
        embed.set_footer(text=FOOTER)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="couplename")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    async def couplename(self, ctx, *, name: str):
        """Set a couple nickname."""
        m = await db.get_marriage(ctx.author.id, ctx.guild.id)
        if not m:
            return await ctx.reply(embed=_err("You're not married!"), mention_author=False)
        if len(name) > 50:
            return await ctx.reply(embed=_err("Name must be 50 characters or less."), mention_author=False)
        await db.update_marriage(ctx.author.id, ctx.guild.id, couple_name=name)
        await ctx.reply(embed=_ok(f"Couple name set to **{name}**!"), mention_author=False)

    @commands.command(name="marriages")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def marriages_lb(self, ctx):
        """Server marriage leaderboard."""
        rows = await db.get_guild_marriages(ctx.guild.id, 20)
        if not rows:
            return await ctx.reply(embed=_err("No marriages in this server yet!"), mention_author=False)
        lines = []
        for i, r in enumerate(rows, 1):
            u1 = ctx.guild.get_member(r["user1_id"])
            u2 = ctx.guild.get_member(r["user2_id"])
            n1 = u1.display_name if u1 else f"User {r['user1_id']}"
            n2 = u2.display_name if u2 else f"User {r['user2_id']}"
            days = int((time.time() - r["married_at"]) / 86400)
            lines.append(f"**{i}.** {n1} & {n2} \u2014 {days}d")
        embed = discord.Embed(description="\n".join(lines), color=COLOR)
        embed.set_author(name=f"{E_RING} Marriages", icon_url=ctx.guild.icon.url if ctx.guild.icon else None)
        embed.set_footer(text=FOOTER)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="remarry")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 86400, commands.BucketType.user)
    async def remarry(self, ctx):
        """Renew your vows (resets anniversary)."""
        m = await db.get_marriage(ctx.author.id, ctx.guild.id)
        if not m:
            return await ctx.reply(embed=_err("You're not married!"), mention_author=False)
        await db.renew_marriage(ctx.author.id, ctx.guild.id)
        pid = m["user2_id"] if m["user1_id"] == ctx.author.id else m["user1_id"]
        partner = ctx.guild.get_member(pid)
        pname = partner.display_name if partner else f"User {pid}"
        embed = discord.Embed(description=f"{E_HEART} **{ctx.author.display_name}** renewed their vows with **{pname}**! {E_RING}\u2728", color=COLOR)
        embed.set_footer(text=FOOTER)
        await ctx.reply(embed=embed, mention_author=False)




    @commands.command(name="crush")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def crush(self, ctx, member: discord.Member = None):
        """Set a secret crush."""
        if member is None:
            return await ctx.reply(embed=_err("Usage: `crush <@user>`"), mention_author=False)
        if member.bot or member.id == ctx.author.id:
            return await ctx.reply(embed=_err("Invalid target."), mention_author=False)
        if await self._blocked(ctx, member):
            return
        await db.set_crush(ctx.author.id, member.id, ctx.guild.id)
        await ctx.reply(embed=_ok("Secret crush set! Only you can see who it is. Use `crushreveal` to go public."), mention_author=False)

    @commands.command(name="crushreveal")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def crushreveal(self, ctx):
        """Reveal your crush publicly!"""
        crush_id = await db.get_crush(ctx.author.id, ctx.guild.id)
        if not crush_id:
            return await ctx.reply(embed=_err("You haven't set a crush! Use `crush <@user>`."), mention_author=False)
        crush = ctx.guild.get_member(crush_id)
        cname = crush.mention if crush else f"User {crush_id}"
        await db.delete_crush(ctx.author.id, ctx.guild.id)
        embed = discord.Embed(
            description=f"\U0001F4E2 **{ctx.author.display_name}** just revealed their crush!\n\n{E_HEART} It's {cname}!",
            color=COLOR,
        )
        embed.set_footer(text=FOOTER)
        await ctx.send(embed=embed)

    @commands.command(name="crushlist")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def crushlist(self, ctx, member: discord.Member = None):
        """See how many secret crushes someone has."""
        target = member or ctx.author
        count = await db.count_crushes_on(target.id, ctx.guild.id)
        embed = discord.Embed(
            description=f"{E_HEART} **{target.display_name}** has **{count}** secret crush{'es' if count != 1 else ''}!",
            color=COLOR,
        )
        embed.set_footer(text=FOOTER)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="confesslove")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 120, commands.BucketType.user)
    async def confesslove(self, ctx, member: discord.Member = None, *, message: str = None):
        """Send an anonymous confession."""
        if member is None or message is None:
            return await ctx.reply(embed=_err("Usage: `confesslove <@user> <message>`"), mention_author=False)
        if member.bot or member.id == ctx.author.id:
            return await ctx.reply(embed=_err("Invalid target."), mention_author=False)
        if await self._blocked(ctx, member):
            return
        if len(message) > 500:
            return await ctx.reply(embed=_err("Keep confessions under 500 characters."), mention_author=False)
        try:
            embed = discord.Embed(
                description=f"{E_LETTER} **Anonymous Confession**\n\n> {message}",
                color=COLOR,
            )
            embed.set_footer(text=f"From someone in {ctx.guild.name} \u00b7 {FOOTER}")
            await member.send(embed=embed)
            await ctx.reply(embed=_ok("Confession sent anonymously!"), mention_author=False)
        except discord.Forbidden:
            await ctx.reply(embed=_err("Couldn't DM that user. They may have DMs disabled."), mention_author=False)
        try:
            await ctx.message.delete()
        except Exception:
            pass

    @commands.command(name="loveletter")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def loveletter(self, ctx, member: discord.Member = None, *, message: str = None):
        """Send a love letter (stored, viewable later)."""
        if member is None or message is None:
            return await ctx.reply(embed=_err("Usage: `loveletter <@user> <message>`"), mention_author=False)
        if member.bot or member.id == ctx.author.id:
            return await ctx.reply(embed=_err("Invalid target."), mention_author=False)
        if await self._blocked(ctx, member):
            return
        if len(message) > 500:
            return await ctx.reply(embed=_err("Keep it under 500 characters."), mention_author=False)
        await db.send_love_letter(ctx.author.id, member.id, ctx.guild.id, message)
        embed = discord.Embed(description=f"{E_LETTER} Love letter sent to **{member.display_name}**!", color=COLOR)
        embed.set_footer(text=FOOTER)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="loveletters")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def loveletters(self, ctx):
        """View your received love letters."""
        rows = await db.get_love_letters(ctx.author.id, ctx.guild.id, 50)
        if not rows:
            return await ctx.reply(embed=_err("You haven't received any love letters yet!"), mention_author=False)
        view = LetterPager(ctx, rows)
        view.message = await ctx.reply(embed=view._build(), view=view, mention_author=False)

    @commands.command(name="flirt")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def flirt(self, ctx, member: discord.Member = None):
        """Flirt with someone."""
        if member is None:
            return await ctx.reply(embed=_err("Usage: `flirt <@user>`"), mention_author=False)
        if member.bot or member.id == ctx.author.id:
            return await ctx.reply(embed=_err("Invalid target."), mention_author=False)
        if await self._blocked(ctx, member):
            return
        action = random.choice(FLIRT_LINES)
        line = random.choice(PICKUP_LINES)
        embed = discord.Embed(
            description=f"\U0001F48B **{ctx.author.display_name}** {action} **{member.display_name}**!\n\n> *\"{line}\"*",
            color=COLOR,
        )
        embed.set_footer(text=FOOTER)
        await ctx.send(embed=embed)

    @commands.command(name="rizz")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def rizz(self, ctx, member: discord.Member = None):
        """Ultimate rizz attempt!"""
        if member is None:
            return await ctx.reply(embed=_err("Usage: `rizz <@user>`"), mention_author=False)
        if member.bot or member.id == ctx.author.id:
            return await ctx.reply(embed=_err("Invalid target."), mention_author=False)
        if await self._blocked(ctx, member):
            return
        score = random.randint(0, 100)
        line = random.choice(PICKUP_LINES)
        if score >= 80:
            result = f"\U0001F525 **UNSPOKEN RIZZ!** ({score}/100)\n{member.display_name} is absolutely swooning!"
        elif score >= 50:
            result = f"\U0001F60F **Decent rizz.** ({score}/100)\n{member.display_name} is mildly impressed."
        elif score >= 20:
            result = f"\U0001F62C **Weak rizz...** ({score}/100)\n{member.display_name} cringes a little."
        else:
            result = f"\U0001F480 **NEGATIVE RIZZ!** ({score}/100)\n{member.display_name} has left the chat."
        embed = discord.Embed(
            description=f"\U0001F3AF **{ctx.author.display_name}** tries to rizz up **{member.display_name}**!\n\n> *\"{line}\"*\n\n{result}",
            color=COLOR,
        )
        embed.set_footer(text=FOOTER)
        await ctx.send(embed=embed)

    @commands.command(name="friendzone")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def friendzone(self, ctx, member: discord.Member = None):
        """Friendzone someone publicly."""
        if member is None:
            return await ctx.reply(embed=_err("Usage: `friendzone <@user>`"), mention_author=False)
        if member.bot or member.id == ctx.author.id:
            return await ctx.reply(embed=_err("Invalid target."), mention_author=False)
        responses = [
            f"I think of you as a brother/sister, {member.display_name}. \U0001F605",
            f"You're like family to me, {member.display_name}! \U0001F46A",
            f"Aww you're such a good FRIEND, {member.display_name}. \U0001F62C",
            f"I love you... as a friend, {member.display_name}! \U0001F972",
            f"Let's just stay friends, {member.display_name}. \U0001F494",
        ]
        embed = discord.Embed(
            description=f"\U0001F6D1 **{ctx.author.display_name}** friendzoned **{member.display_name}**!\n\n> *{random.choice(responses)}*",
            color=COLOR,
        )
        embed.set_footer(text=FOOTER)
        await ctx.send(embed=embed)





    @commands.command(name="date")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def date_cmd(self, ctx, member: discord.Member = None):
        """Ask someone on a date!"""
        if member is None:
            return await ctx.reply(embed=_err("Usage: `date <@user>`"), mention_author=False)
        if member.bot or member.id == ctx.author.id:
            return await ctx.reply(embed=_err("Invalid target."), mention_author=False)
        if await self._blocked(ctx, member):
            return
        location = random.choice(DATE_LOCATIONS)
        embed = discord.Embed(
            description=f"\U0001F493 **{ctx.author.display_name}** is asking **{member.display_name}** on a date to {location}!\n\n{member.mention}, what do you say?",
            color=COLOR,
        )
        embed.set_footer(text=FOOTER)
        view = DateRequestView(ctx.author, member)
        msg = await ctx.send(embed=embed, view=view)
        await view.wait()
        if view.result is True:
            await db.add_date(ctx.author.id, member.id, ctx.guild.id, location)
            embed = discord.Embed(
                description=f"{E_HEART} **{ctx.author.display_name}** and **{member.display_name}** went on a date to {location}! \U0001F389",
                color=COLOR,
            )
            embed.set_footer(text=FOOTER)
            await msg.edit(embed=embed, view=None)
        elif view.result is False:
            await msg.edit(embed=discord.Embed(description=f"\U0001F494 **{member.display_name}** turned down the date...", color=COLOR), view=None)
        else:
            await msg.edit(embed=discord.Embed(description="\u23F0 Date request timed out.", color=COLOR), view=None)

    @commands.command(name="datenight")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 120, commands.BucketType.user)
    async def datenight(self, ctx, member: discord.Member = None):
        """Surprise date night!"""
        if member is None:
            return await ctx.reply(embed=_err("Usage: `datenight <@user>`"), mention_author=False)
        if member.bot or member.id == ctx.author.id:
            return await ctx.reply(embed=_err("Invalid target."), mention_author=False)
        if await self._blocked(ctx, member):
            return
        location = random.choice(DATE_LOCATIONS)
        scenarios = [
            f"They gazed at the stars and whispered sweet nothings. \u2728",
            f"They danced under the moonlight like nobody was watching. \U0001F483",
            f"They shared a dessert and accidentally touched hands. \U0001F36B",
            f"They got lost but found their way together. \U0001F5FA\ufe0f",
            f"They laughed until their stomachs hurt. \U0001F602",
            f"They took a thousand selfies and made memories. \U0001F4F8",
        ]
        await db.add_date(ctx.author.id, member.id, ctx.guild.id, location)
        embed = discord.Embed(
            description=f"\U0001F31F **Date Night!**\n\n**{ctx.author.display_name}** surprised **{member.display_name}** with a night at {location}!\n\n> {random.choice(scenarios)}",
            color=COLOR,
        )
        embed.set_footer(text=FOOTER)
        await ctx.send(embed=embed)

    @commands.command(name="datehistory")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def datehistory(self, ctx, member: discord.Member = None):
        """View past dates."""
        target = member or ctx.author
        rows = await db.get_date_history(target.id, ctx.guild.id, 10)
        if not rows:
            return await ctx.reply(embed=_err("No dates on record!"), mention_author=False)
        lines = []
        for r in rows:
            other_id = r["user2_id"] if r["user1_id"] == target.id else r["user1_id"]
            other = ctx.guild.get_member(other_id)
            oname = other.display_name if other else f"User {other_id}"
            lines.append(f"\u2022 **{oname}** at {r['location'] or 'somewhere'} {_ts(r['date_at'])}")
        embed = discord.Embed(description="\n".join(lines), color=COLOR)
        embed.set_author(name=f"\U0001F4C5 {target.display_name}'s Date History", icon_url=target.display_avatar.url)
        embed.set_footer(text=FOOTER)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="dategift")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def dategift(self, ctx, member: discord.Member = None, *, item: str = None):
        """Gift an item during a date."""
        if member is None or item is None:
            items_list = " / ".join(f"`{k}` {v['emoji']}" for k, v in GIFT_CATALOG.items())
            return await ctx.reply(embed=_err(f"Usage: `dategift <@user> <item>`\nItems: {items_list}"), mention_author=False)
        if member.bot or member.id == ctx.author.id:
            return await ctx.reply(embed=_err("Invalid target."), mention_author=False)
        item_key = item.lower().strip()
        if item_key not in GIFT_CATALOG:
            return await ctx.reply(embed=_err("Unknown item! Use: " + ", ".join(f"`{k}`" for k in GIFT_CATALOG)), mention_author=False)
        if await self._blocked(ctx, member):
            return
        gi = GIFT_CATALOG[item_key]
        await db.add_gift(ctx.author.id, member.id, ctx.guild.id, gi["name"], gi["value"])
        embed = discord.Embed(
            description=f"{gi['emoji']} **{ctx.author.display_name}** gifted a **{gi['name']}** to **{member.display_name}** during their date!",
            color=COLOR,
        )
        embed.set_footer(text=FOOTER)
        await ctx.send(embed=embed)

    @commands.command(name="datemood")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def datemood(self, ctx):
        """Check your current dating mood."""
        moods = [
            ("\U0001F60D", "Hopelessly Romantic", "You're in full love mode! Time to shoot your shot!"),
            ("\U0001F914", "Cautiously Curious", "You're open to love but being careful. Smart move."),
            ("\U0001F634", "Not In The Mood", "Love can wait. Netflix and a blanket it is."),
            ("\U0001F525", "Feeling Spicy", "Watch out everyone, you're on fire today!"),
            ("\U0001F62D", "Post-Heartbreak", "Still healing... take your time, king/queen."),
            ("\U0001F60E", "Main Character Energy", "You don't chase, you attract. Period."),
            ("\U0001F970", "Butterflies Everywhere", "Someone's got you feeling some type of way!"),
            ("\U0001F47B", "Ghost Mode", "You've been ghosting or getting ghosted. Yikes."),
        ]
        emoji, mood, desc = random.choice(moods)
        embed = discord.Embed(
            description=f"{emoji} **{ctx.author.display_name}'s Dating Mood**\n\n**{mood}**\n> {desc}",
            color=COLOR,
        )
        embed.set_footer(text=FOOTER)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="blinddate")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 120, commands.BucketType.user)
    async def blinddate(self, ctx):
        """Get matched with a random server member!"""
        members = [m for m in ctx.guild.members if not m.bot and m.id != ctx.author.id]
        if not members:
            return await ctx.reply(embed=_err("No other members to match with!"), mention_author=False)
        match = random.choice(members)
        compat = random.randint(10, 100)
        location = random.choice(DATE_LOCATIONS)
        outcome = "Looks promising! \U0001F525" if compat >= 60 else "Could be interesting... \U0001F914" if compat >= 30 else "Uh oh... \U0001F62C"
        embed = discord.Embed(
            description=(
                f"\U0001F3B0 **Blind Date Match!**\n\n"
                f"**{ctx.author.display_name}** has been matched with **{match.display_name}**!\n\n"
                f"\U0001F4CD Location: {location}\n"
                f"\U0001F496 Compatibility: **{compat}%**\n\n"
                f"{outcome}"
            ),
            color=COLOR,
        )
        embed.set_footer(text=FOOTER)
        await ctx.send(embed=embed)

    @commands.command(name="speeddate")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def speeddate(self, ctx):
        """Quick 3-question speed dating game!"""
        questions = [
            "What's your ideal first date?", "Describe yourself in 3 words.",
            "What's your love language?", "Pineapple on pizza: yes or no?",
            "What's the most romantic thing you've done?", "Morning person or night owl?",
            "What's your biggest red flag?", "Cats or dogs?",
            "Coffee or tea?", "What's your go-to karaoke song?",
        ]
        picked = random.sample(questions, 3)
        embed = discord.Embed(
            description=(
                f"\u23F1\ufe0f **Speed Date Questions for {ctx.author.display_name}!**\n\n"
                f"Answer these in chat:\n\n"
                f"**1.** {picked[0]}\n"
                f"**2.** {picked[1]}\n"
                f"**3.** {picked[2]}"
            ),
            color=COLOR,
        )
        embed.set_footer(text=FOOTER)
        await ctx.send(embed=embed)

    @commands.command(name="dateidea")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def dateidea(self, ctx):
        """Get a random creative date idea!"""
        ideas = [
            "\U0001F3A8 Have a paint-and-sip night together",
            "\U0001F3AC Watch a movie marathon of your favourite genre",
            "\U0001F374 Cook a 3-course meal together",
            "\u2615 Visit every coffee shop in town and rate them",
            "\U0001F3D6\ufe0f Build the ultimate blanket fort",
            "\U0001F3B2 Board game tournament with snacks",
            "\U0001F30C Go stargazing and find constellations",
            "\U0001F4F7 Do a photo scavenger hunt around the city",
            "\U0001F3B5 Create a collaborative playlist",
            "\U0001F9D1\u200d\U0001F373 Take a cooking class together",
            "\U0001F3A4 Karaoke night — duets only!",
            "\U0001F6B2 Explore a new neighbourhood on bikes",
        ]
        embed = discord.Embed(
            description=f"\U0001F4A1 **Date Idea:**\n\n{random.choice(ideas)}",
            color=COLOR,
        )
        embed.set_footer(text=FOOTER)
        await ctx.reply(embed=embed, mention_author=False)





    @commands.command(name="gift")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def gift_cmd(self, ctx, member: discord.Member = None, *, item: str = None):
        """Gift an item to someone."""
        if member is None or item is None:
            items_list = " / ".join(f"`{k}` {v['emoji']}" for k, v in GIFT_CATALOG.items())
            return await ctx.reply(embed=_err(f"Usage: `gift <@user> <item>`\nItems: {items_list}"), mention_author=False)
        if member.bot or member.id == ctx.author.id:
            return await ctx.reply(embed=_err("Invalid target."), mention_author=False)
        item_key = item.lower().strip()
        if item_key not in GIFT_CATALOG:
            return await ctx.reply(embed=_err("Unknown item! Use: " + ", ".join(f"`{k}`" for k in GIFT_CATALOG)), mention_author=False)
        if await self._blocked(ctx, member):
            return
        gi = GIFT_CATALOG[item_key]
        await db.add_gift(ctx.author.id, member.id, ctx.guild.id, gi["name"], gi["value"])
        embed = discord.Embed(
            description=f"{gi['emoji']} **{ctx.author.display_name}** gifted a **{gi['name']}** to **{member.display_name}**!",
            color=COLOR,
        )
        embed.set_footer(text=FOOTER)
        await ctx.send(embed=embed)

    @commands.command(name="gifts")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def gifts_cmd(self, ctx, member: discord.Member = None):
        """View gift inventory."""
        target = member or ctx.author
        rows = await db.get_gifts_received(target.id, ctx.guild.id, 20)
        if not rows:
            return await ctx.reply(embed=_err(f"{'You have' if target == ctx.author else f'{target.display_name} has'} no gifts!"), mention_author=False)
        stats = await db.get_gift_stats(target.id, ctx.guild.id)
        lines = []
        for r in rows:
            sender = ctx.guild.get_member(r["from_id"])
            sname = sender.display_name if sender else f"User {r['from_id']}"
            lines.append(f"\u2022 **{r['item']}** from {sname} {_ts(r['sent_at'])}")
        embed = discord.Embed(description="\n".join(lines[:15]), color=COLOR)
        embed.set_author(name=f"\U0001F381 {target.display_name}'s Gifts", icon_url=target.display_avatar.url)
        embed.set_footer(text=f"Total: {stats[0]} gifts ({stats[1]} value) \u00b7 {FOOTER}")
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="gifttop")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def gifttop(self, ctx):
        """Gift leaderboard."""
        rows = await db.get_gift_leaderboard(ctx.guild.id, 10)
        if not rows:
            return await ctx.reply(embed=_err("No gifts sent in this server yet!"), mention_author=False)
        rank_emoji = {0: "\U0001F947", 1: "\U0001F948", 2: "\U0001F949"}
        lines = []
        for i, (uid, cnt, total) in enumerate(rows):
            emoji = rank_emoji.get(i, f"`{i+1}.`")
            member = ctx.guild.get_member(uid)
            name = member.display_name if member else f"User {uid}"
            lines.append(f"{emoji} **{name}** \u2014 {cnt} gifts ({total} value)")
        embed = discord.Embed(description="\n".join(lines), color=COLOR)
        embed.set_author(name="\U0001F381 Gift Leaderboard", icon_url=ctx.guild.icon.url if ctx.guild.icon else None)
        embed.set_footer(text=FOOTER)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="rose")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def rose(self, ctx, member: discord.Member = None):
        """Quick send a rose!"""
        if member is None:
            return await ctx.reply(embed=_err("Usage: `rose <@user>`"), mention_author=False)
        if member.bot or member.id == ctx.author.id:
            return await ctx.reply(embed=_err("Invalid target."), mention_author=False)
        if await self._blocked(ctx, member):
            return
        await db.add_gift(ctx.author.id, member.id, ctx.guild.id, "Rose", 10)
        embed = discord.Embed(description=f"{E_ROSE} **{ctx.author.display_name}** sent a beautiful rose to **{member.display_name}**!", color=COLOR)
        embed.set_footer(text=FOOTER)
        await ctx.send(embed=embed)

    @commands.command(name="chocolate")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def chocolate(self, ctx, member: discord.Member = None):
        """Quick send chocolate!"""
        if member is None:
            return await ctx.reply(embed=_err("Usage: `chocolate <@user>`"), mention_author=False)
        if member.bot or member.id == ctx.author.id:
            return await ctx.reply(embed=_err("Invalid target."), mention_author=False)
        if await self._blocked(ctx, member):
            return
        await db.add_gift(ctx.author.id, member.id, ctx.guild.id, "Chocolate", 15)
        embed = discord.Embed(description=f"{E_CHOC} **{ctx.author.display_name}** sent some delicious chocolate to **{member.display_name}**!", color=COLOR)
        embed.set_footer(text=FOOTER)
        await ctx.send(embed=embed)

    @commands.command(name="serenade")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def serenade(self, ctx, member: discord.Member = None):
        """Serenade someone with a love song!"""
        if member is None:
            return await ctx.reply(embed=_err("Usage: `serenade <@user>`"), mention_author=False)
        if member.bot or member.id == ctx.author.id:
            return await ctx.reply(embed=_err("Invalid target."), mention_author=False)
        if await self._blocked(ctx, member):
            return
        song = random.choice(SERENADE_SONGS)
        embed = discord.Embed(
            description=f"\U0001F3A4 **{ctx.author.display_name}** serenades **{member.display_name}**!\n\n{song}",
            color=COLOR,
        )
        embed.set_footer(text=FOOTER)
        await ctx.send(embed=embed)

    @commands.command(name="lovebomb")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 120, commands.BucketType.user)
    async def lovebomb(self, ctx, member: discord.Member = None):
        """Send a barrage of love!"""
        if member is None:
            return await ctx.reply(embed=_err("Usage: `lovebomb <@user>`"), mention_author=False)
        if member.bot or member.id == ctx.author.id:
            return await ctx.reply(embed=_err("Invalid target."), mention_author=False)
        if await self._blocked(ctx, member):
            return
        hearts = " ".join(random.choices(["\u2764\ufe0f", "\U0001F9E1", "\U0001F49B", "\U0001F49A", "\U0001F499", "\U0001F49C", "\U0001F90E", "\U0001F90D", "\U0001F5A4", "\U0001F496", "\U0001F49D", "\U0001F49E", "\U0001F493", "\U0001F497"], k=20))
        embed = discord.Embed(
            description=f"\U0001F4A3 **{ctx.author.display_name}** love-bombed **{member.display_name}**!\n\n{hearts}",
            color=COLOR,
        )
        embed.set_footer(text=FOOTER)
        await ctx.send(embed=embed)

    @commands.command(name="breakupsong")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def breakupsong(self, ctx):
        """Get a breakup anthem."""
        embed = discord.Embed(
            description=f"\U0001F494 **Breakup Anthem for {ctx.author.display_name}:**\n\n{random.choice(BREAKUP_SONGS)}",
            color=COLOR,
        )
        embed.set_footer(text=FOOTER)
        await ctx.reply(embed=embed, mention_author=False)




    @commands.command(name="compatibility")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def compatibility(self, ctx, member: discord.Member = None):
        """Detailed compatibility analysis."""
        if member is None:
            return await ctx.reply(embed=_err("Usage: `compatibility <@user>`"), mention_author=False)
        if member.id == ctx.author.id:
            return await ctx.reply(embed=_err("Can't check compatibility with yourself!"), mention_author=False)
        sorted_ids = sorted([ctx.author.id, member.id])
        rng = random.Random(f"{sorted_ids[0]}:{sorted_ids[1]}:compat")
        scores = {
            "\U0001F525 Physical": rng.randint(5, 100),
            "\U0001F9E0 Intellectual": rng.randint(5, 100),
            "\U0001F493 Emotional": rng.randint(5, 100),
            "\U0001F60A Humor": rng.randint(5, 100),
            "\U0001F91D Trust": rng.randint(5, 100),
        }
        overall = sum(scores.values()) // len(scores)
        bars = []
        for k, v in scores.items():
            filled = int(v / 10)
            bars.append(f"{k}: {'█' * filled}{'░' * (10 - filled)} **{v}%**")
        if overall >= 80:
            verdict = "Soulmates! You two were made for each other! \U0001F496"
        elif overall >= 60:
            verdict = "Strong connection! Definitely worth pursuing. \U0001F60D"
        elif overall >= 40:
            verdict = "Some potential, but it'll take work. \U0001F914"
        else:
            verdict = "Maybe just stay friends... \U0001F605"
        embed = discord.Embed(
            description=(
                f"**{ctx.author.display_name}** \u00d7 **{member.display_name}**\n\n"
                + "\n".join(bars) +
                f"\n\n**Overall: {overall}%**\n> {verdict}"
            ),
            color=COLOR,
        )
        embed.set_author(name="\U0001F52E Compatibility Analysis")
        embed.set_footer(text=FOOTER)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="lovetest")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def lovetest(self, ctx, user1: discord.Member = None, user2: discord.Member = None):
        """Love percentage test."""
        if user1 is None:
            return await ctx.reply(embed=_err("Usage: `lovetest <@user1> [<@user2>]`"), mention_author=False)
        if user2 is None:
            user2 = user1
            user1 = ctx.author
        sorted_ids = sorted([user1.id, user2.id])
        rng = random.Random(f"{sorted_ids[0]}:{sorted_ids[1]}:love")
        pct = rng.randint(0, 100)
        heart_bar = "\u2764\ufe0f" * (pct // 10) + "\U0001F5A4" * (10 - pct // 10)
        embed = discord.Embed(
            description=f"**{user1.display_name}** {E_HEART} **{user2.display_name}**\n\n{heart_bar}\n\n**{pct}%** Love!",
            color=COLOR,
        )
        embed.set_footer(text=FOOTER)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="horoscope")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def horoscope(self, ctx, *, sign: str = None):
        """Love horoscope for your zodiac sign."""
        if sign is None:
            return await ctx.reply(embed=_err("Usage: `horoscope <sign>`\nSigns: " + ", ".join(f"`{s}`" for s in HOROSCOPES)), mention_author=False)
        sign = sign.lower().strip()
        if sign not in HOROSCOPES:
            return await ctx.reply(embed=_err("Unknown sign! Use: " + ", ".join(f"`{s}`" for s in HOROSCOPES)), mention_author=False)
        embed = discord.Embed(
            description=f"\u2728 **Love Horoscope for {sign.capitalize()}**\n\n> {HOROSCOPES[sign]}",
            color=COLOR,
        )
        embed.set_footer(text=FOOTER)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="pickup")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def pickup(self, ctx):
        """Get a random pickup line."""
        embed = discord.Embed(
            description=f"\U0001F48B **Pickup Line:**\n\n> *\"{random.choice(PICKUP_LINES)}\"*",
            color=COLOR,
        )
        embed.set_footer(text=FOOTER)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="wouldyourather", aliases=["wyr"])
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def wouldyourather(self, ctx):
        """Dating-themed Would You Rather!"""
        embed = discord.Embed(
            description=f"\U0001F914 **Would You Rather...**\n\n> {random.choice(WYR_QUESTIONS)}",
            color=COLOR,
        )
        embed.set_footer(text=FOOTER)
        await ctx.send(embed=embed)

    @commands.command(name="lovequote")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def lovequote(self, ctx):
        """Random love quote."""
        embed = discord.Embed(
            description=f"{E_HEART} {random.choice(LOVE_QUOTES)}",
            color=COLOR,
        )
        embed.set_footer(text=FOOTER)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="love8ball", aliases=["l8ball"])
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def love8ball(self, ctx, *, question: str = None):
        """Love-themed 8ball."""
        if question is None:
            return await ctx.reply(embed=_err("Usage: `love8ball <question>`"), mention_author=False)
        embed = discord.Embed(
            description=f"\U0001F52E **Love 8-Ball**\n\n> **Q:** {question}\n\n**A:** {random.choice(EIGHT_BALL_LOVE)}",
            color=COLOR,
        )
        embed.set_footer(text=FOOTER)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="shiplb")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def shiplb(self, ctx):
        """Server shipping leaderboard based on gifts + dates."""
        rows = await db.get_guild_marriages(ctx.guild.id, 10)
        if not rows:
            return await ctx.reply(embed=_err("No couples to rank yet!"), mention_author=False)
        lines = []
        for i, r in enumerate(rows, 1):
            u1 = ctx.guild.get_member(r["user1_id"])
            u2 = ctx.guild.get_member(r["user2_id"])
            n1 = u1.display_name if u1 else "?"
            n2 = u2.display_name if u2 else "?"
            g1 = await db.get_gift_stats(r["user1_id"], ctx.guild.id)
            g2 = await db.get_gift_stats(r["user2_id"], ctx.guild.id)
            total = (g1[1] or 0) + (g2[1] or 0)
            lines.append(f"**{i}.** {n1} & {n2} \u2014 {total} gift value")
        embed = discord.Embed(description="\n".join(lines), color=COLOR)
        embed.set_author(name="\U0001F6A2 Ship Leaderboard", icon_url=ctx.guild.icon.url if ctx.guild.icon else None)
        embed.set_footer(text=FOOTER)
        await ctx.reply(embed=embed, mention_author=False)




    @commands.command(name="adopt")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def adopt(self, ctx, member: discord.Member = None):
        """Adopt a user as your child (must be married)."""
        if member is None:
            return await ctx.reply(embed=_err("Usage: `adopt <@user>`"), mention_author=False)
        if member.bot or member.id == ctx.author.id:
            return await ctx.reply(embed=_err("Invalid target."), mention_author=False)
        m = await db.get_marriage(ctx.author.id, ctx.guild.id)
        if not m:
            return await ctx.reply(embed=_err("You must be married to adopt!"), mention_author=False)
        existing_parents = await db.get_parents(member.id, ctx.guild.id)
        if existing_parents:
            return await ctx.reply(embed=_err(f"{member.display_name} already has parents!"), mention_author=False)
        pid = m["user2_id"] if m["user1_id"] == ctx.author.id else m["user1_id"]
        if member.id == pid:
            return await ctx.reply(embed=_err("You can't adopt your spouse!"), mention_author=False)
        kids = await db.get_children(ctx.author.id, ctx.guild.id)
        if len(kids) >= 10:
            return await ctx.reply(embed=_err("Maximum 10 children per couple!"), mention_author=False)
        await db.adopt_child(ctx.author.id, pid, member.id, ctx.guild.id)
        partner = ctx.guild.get_member(pid)
        pname = partner.display_name if partner else f"User {pid}"
        embed = discord.Embed(
            description=f"\U0001F46A **{ctx.author.display_name}** & **{pname}** adopted **{member.display_name}**! Welcome to the family! \U0001F389",
            color=COLOR,
        )
        embed.set_footer(text=FOOTER)
        await ctx.send(embed=embed)

    @commands.command(name="disown")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def disown(self, ctx, member: discord.Member = None):
        """Remove an adopted child."""
        if member is None:
            return await ctx.reply(embed=_err("Usage: `disown <@user>`"), mention_author=False)
        parents = await db.get_parents(member.id, ctx.guild.id)
        if not parents or ctx.author.id not in (parents[0], parents[1]):
            return await ctx.reply(embed=_err(f"{member.display_name} is not your child!"), mention_author=False)
        await db.remove_child(member.id, ctx.guild.id)
        embed = discord.Embed(description=f"\U0001F494 **{ctx.author.display_name}** disowned **{member.display_name}**...", color=COLOR)
        embed.set_footer(text=FOOTER)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="children")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def children_cmd(self, ctx, member: discord.Member = None):
        """View adopted children."""
        target = member or ctx.author
        kids = await db.get_children(target.id, ctx.guild.id)
        if not kids:
            return await ctx.reply(embed=_err("No children!"), mention_author=False)
        lines = []
        for cid, adopted_at in kids:
            child = ctx.guild.get_member(cid)
            cname = child.display_name if child else f"User {cid}"
            lines.append(f"\u2022 **{cname}** {_ts(adopted_at)}")
        embed = discord.Embed(description="\n".join(lines), color=COLOR)
        embed.set_author(name=f"\U0001F46A {target.display_name}'s Children", icon_url=target.display_avatar.url)
        embed.set_footer(text=FOOTER)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="family")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def family(self, ctx, member: discord.Member = None):
        """View full family tree."""
        target = member or ctx.author
        m = await db.get_marriage(target.id, ctx.guild.id)
        parents = await db.get_parents(target.id, ctx.guild.id)
        kids = await db.get_children(target.id, ctx.guild.id)
        lines = [f"**{target.display_name}'s Family**\n"]
        if parents:
            p1 = ctx.guild.get_member(parents[0])
            p2 = ctx.guild.get_member(parents[1])
            n1 = p1.display_name if p1 else f"User {parents[0]}"
            n2 = p2.display_name if p2 else f"User {parents[1]}"
            lines.append(f"\U0001F9D1\u200d\U0001F9D1\u200d\U0001F9D2 **Parents:** {n1} & {n2}")
        if m:
            pid = m["user2_id"] if m["user1_id"] == target.id else m["user1_id"]
            partner = ctx.guild.get_member(pid)
            pname = partner.display_name if partner else f"User {pid}"
            lines.append(f"{E_RING} **Spouse:** {pname}")
        if kids:
            knames = []
            for cid, _ in kids:
                child = ctx.guild.get_member(cid)
                knames.append(child.display_name if child else f"User {cid}")
            lines.append(f"\U0001F476 **Children:** {', '.join(knames)}")
        if len(lines) == 1:
            lines.append("> No family connections yet.")
        embed = discord.Embed(description="\n".join(lines), color=COLOR)
        embed.set_footer(text=FOOTER)
        await ctx.reply(embed=embed, mention_author=False)




    @dating.command(name="block")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    async def dating_block(self, ctx, member: discord.Member = None):
        """Block someone from dating interactions with you."""
        if member is None:
            return await ctx.reply(embed=_err("Usage: `dating block <@user>`"), mention_author=False)
        if member.id == ctx.author.id:
            return await ctx.reply(embed=_err("Can't block yourself."), mention_author=False)
        await db.add_block(ctx.author.id, member.id, ctx.guild.id)
        await ctx.reply(embed=_ok(f"Blocked **{member.display_name}** from dating interactions."), mention_author=False)

    @dating.command(name="unblock")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    async def dating_unblock(self, ctx, member: discord.Member = None):
        """Unblock someone from dating interactions."""
        if member is None:
            return await ctx.reply(embed=_err("Usage: `dating unblock <@user>`"), mention_author=False)
        await db.remove_block(ctx.author.id, member.id, ctx.guild.id)
        await ctx.reply(embed=_ok(f"Unblocked **{member.display_name}**."), mention_author=False)

    @dating.command(name="resetall")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    async def dating_resetall(self, ctx):
        """Server owner only: wipe all dating data for this server."""
        if ctx.author.id != ctx.guild.owner_id:
            return await ctx.reply(embed=_err("Only the server owner can use this."), mention_author=False)
        await db.wipe_guild(ctx.guild.id)
        await ctx.reply(embed=_ok("All dating data for this server has been wiped."), mention_author=False)


    @marry.error
    @divorce.error
    @remarry.error
    async def _marriage_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            m, s = divmod(int(error.retry_after), 60)
            await ctx.reply(embed=_err(f"On cooldown! Try again in **{m}m {s}s**"), mention_author=False)
        elif isinstance(error, commands.MemberNotFound):
            await ctx.reply(embed=_err("Member not found."), mention_author=False)

    @crush.error
    @flirt.error
    @rizz.error
    @confesslove.error
    @loveletter.error
    @friendzone.error
    async def _relationship_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            m, s = divmod(int(error.retry_after), 60)
            await ctx.reply(embed=_err(f"On cooldown! Try again in **{m}m {s}s**"), mention_author=False)
        elif isinstance(error, commands.MemberNotFound):
            await ctx.reply(embed=_err("Member not found."), mention_author=False)

    @date_cmd.error
    @datenight.error
    @blinddate.error
    async def _date_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            m, s = divmod(int(error.retry_after), 60)
            await ctx.reply(embed=_err(f"On cooldown! Try again in **{m}m {s}s**"), mention_author=False)
        elif isinstance(error, commands.MemberNotFound):
            await ctx.reply(embed=_err("Member not found."), mention_author=False)

    @gift_cmd.error
    @rose.error
    @chocolate.error
    @serenade.error
    @lovebomb.error
    async def _gift_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            m, s = divmod(int(error.retry_after), 60)
            await ctx.reply(embed=_err(f"On cooldown! Try again in **{m}m {s}s**"), mention_author=False)
        elif isinstance(error, commands.MemberNotFound):
            await ctx.reply(embed=_err("Member not found."), mention_author=False)

    @adopt.error
    @disown.error
    async def _family_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            m, s = divmod(int(error.retry_after), 60)
            await ctx.reply(embed=_err(f"On cooldown! Try again in **{m}m {s}s**"), mention_author=False)
        elif isinstance(error, commands.MemberNotFound):
            await ctx.reply(embed=_err("Member not found."), mention_author=False)

    @dating_age.error
    async def _age_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.reply(embed=_err("Age must be a number between 13 and 99."), mention_author=False)


async def setup(bot: commands.Bot) -> None:
    await db.init_db()
    await bot.add_cog(Dating(bot))

