import math
import random
import datetime
import discord
from discord.ext import commands
from utils.Tools import blacklist_check, ignore_check
from utils.eco_db import (
    init_db, ensure_user, get_balance, get_wallet, get_bank,
    add_wallet, add_bank, set_wallet, set_bank, transfer,
    get_leaderboard, remaining_cooldown, set_cooldown,
)

EMBED_COLOR = 0x2b2d31
E_OK  = "<:SynapseDoubleTick:1477237283286679647>"
E_ERR = "<:emoji_1769867589372:1467155751456735326>"

W_ICON = "<:wallet:1459855844689838195>"
B_ICON = "<:benk:1459855846904172544>"


def _fmt(n: int) -> str:
    return f"{n:,}"


def _footer(ctx) -> str:
    return f"Synapse - Economy • {ctx.author.name}"



class LeaderboardView(discord.ui.View):
    PER_PAGE = 10

    def __init__(self, ctx, rows: list):
        super().__init__(timeout=60)
        self.ctx    = ctx
        self.rows   = rows
        self.page   = 0
        self.pages  = max(1, math.ceil(len(rows) / self.PER_PAGE))
        self.message = None
        self._update_buttons()

    def _update_buttons(self):
        self.prev_btn.disabled = self.page == 0
        self.next_btn.disabled = self.page >= self.pages - 1

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("Not your leaderboard!", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        try:
            await self.message.edit(view=self)
        except Exception:
            pass

    def _build_embed(self) -> discord.Embed:
        start = self.page * self.PER_PAGE
        chunk = self.rows[start: start + self.PER_PAGE]
        rank_emoji = {0: "🥇", 1: "🥈", 2: "🥉"}
        lines = []
        for i, (uid, wallet, bank, total) in enumerate(chunk):
            rank  = start + i
            emoji = rank_emoji.get(rank, f"`{rank + 1}.`")
            member = self.ctx.guild.get_member(uid)
            name   = member.display_name if member else f"User {uid}"
            lines.append(f"{emoji} **{name}** — {_fmt(total)} coins")
        embed = discord.Embed(
            description="\n".join(lines) or "No data yet.",
            color=EMBED_COLOR,
            timestamp=discord.utils.utcnow(),
        )
        embed.set_author(name="Balance Leaderboard", icon_url=self.ctx.guild.icon.url if self.ctx.guild.icon else None)
        embed.set_footer(text=f"Page {self.page + 1}/{self.pages} • Synapse - Economy")
        return embed

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def prev_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.page -= 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self._build_embed(), view=self)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def next_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.page += 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self._build_embed(), view=self)



class EcoGuideDropdown(discord.ui.Select):
    def __init__(self, guide_view):
        self.guide_view = guide_view
        options = [
            discord.SelectOption(label="Getting Started", description="Basic commands to start your journey", emoji="🪙"),
            discord.SelectOption(label="Shop & Items", description="Buy items, weapons, and manage inventory", emoji="🛒"),
            discord.SelectOption(label="Jobs & Work", description="Earn money by working", emoji="💼"),
            discord.SelectOption(label="Farming", description="Grow crops and expand your farm", emoji="🌾"),
            discord.SelectOption(label="Pets", description="Adopt and train cute pets", emoji="🐶"),
            discord.SelectOption(label="Business", description="Run your own corporate empire", emoji="🏢"),
            discord.SelectOption(label="Gambling & Crime", description="High risk, high reward", emoji="🎲"),
        ]
        super().__init__(placeholder="Select a guide category...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        await self.guide_view.update_category(interaction, self.values[0])


class EcoGuideView(discord.ui.View):
    def __init__(self, ctx):
        super().__init__(timeout=120)
        self.ctx = ctx
        self.message = None
        self.current_category = "Getting Started"
        self.dropdown = EcoGuideDropdown(self)
        self.add_item(self.dropdown)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("This guide is not for you!", ephemeral=True)
            return False
        return True

    def get_embed(self, category: str) -> discord.Embed:
        embed = discord.Embed(color=EMBED_COLOR, timestamp=discord.utils.utcnow())
        embed.set_author(name="Synapse Economy Guide", icon_url=self.ctx.guild.icon.url if self.ctx.guild.icon else None)
        if category == "Getting Started":
            embed.title = "🪙 Getting Started"
            embed.description = (
                "Welcome to the **Synapse Economy**! Your journey to unimaginable wealth starts right here.\n\n"
                "> Begin by claiming your **`daily`** and **`weekly`** allowances to establish a solid financial foundation. "
                "If times get tough, you can always **`beg`** for some spare change from generous strangers. "
                "Keep a close eye on your growing fortune using **`bal`**, and ensure your hard-earned coins are safe "
                "by using **`deposit`** to store them in the bank, or **`withdraw`** when you need them on hand.\n\n"
                "**<:SynapseUsage:1487700535120363561> Commands**\n"
                "`daily`, `weekly`, `beg`, `bal`, `deposit`, `withdraw`, `pay`, `baltop`"
            )
            embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/3141/3141595.png")
        elif category == "Shop & Items":
            embed.title = "🛒 Shop & Items"
            embed.description = (
                "Equip yourself with the best gear and items to thrive in the competitive market.\n\n"
                "> Browse the **`shop`** to discover a wide variety of goods, ranging from essential tools to powerful weapons like the Hunting Rifle. "
                "Purchase what you need using **`buy`** or liquidate your assets with **`sell`**, and always keep track of your stash in your **`inventory`**. "
                "You can **`use`** specific items (such as firing your rifle to hunt for loot), **`trade`** valuables with other players, "
                "and even **`craft`** unique gear to gain an ultimate advantage!\n\n"
                "**<:SynapseUsage:1487700535120363561> Commands**\n"
                "`shop`, `inventory`, `buy`, `sell`, `use`, `trade`, `craft`, `crafting`, `giveitem`, `iteminfo`, `lootbox`"
            )
            embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/1170/1170678.png")
        elif category == "Jobs & Work":
            embed.title = "💼 Jobs & Work"
            embed.description = (
                "A steady career is the backbone of a successful empire. Dive into the job market to earn a consistent income.\n\n"
                "> Browse through the available careers using **`jobs`** and use **`buyjob`** to secure your desired position. "
                "Once hired, put in the effort and **`work`** your shifts to get paid. You can review your active employment "
                "with **`myjobs`**, and if you're ready for a career change, simply **`removejob`** to step down and explore new opportunities.\n\n"
                "**<:SynapseUsage:1487700535120363561> Commands**\n"
                "`jobs`, `buyjob`, `work`, `myjobs`, `removejob`"
            )
            embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/3061/3061341.png")
        elif category == "Farming":
            embed.title = "🌾 Farming"
            embed.description = (
                "Cultivate the land and watch your profits grow organically by managing your very own agricultural enterprise.\n\n"
                "> Use the **`farm`** command to survey your land and visit the **`farm shop`** to purchase seeds and essential tools. "
                "Carefully **`plant`**, **`water`**, and eventually **`harvest`** your thriving crops. Once you've gathered your yield, "
                "**`sellcrop`** for a handsome profit, and reinvest your earnings to **`farm expand`** your territory into a massive plantation.\n\n"
                "**<:SynapseUsage:1487700535120363561> Commands**\n"
                "`farm`, `farm shop`, `buyseed`, `plant`, `water`, `harvest`, `fertilize`, `sellcrop`, `farm expand`, `farm inv`, `tractor buy`, `tractor use`, `farm leaderboard`"
            )
            embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/2627/2627191.png")
        elif category == "Pets":
            embed.title = "🐶 Pets"
            embed.description = (
                "Companionship meets fierce competition! Adopt, nurture, and train virtual pets to stand by your side.\n\n"
                "> Explore the **`pet shop`** to find your perfect companion and use **`pet buy`** to bring them home. "
                "Keep them healthy and happy by choosing to **`pet feed`** and **`pet play`** with them regularly. Check their progress "
                "using **`pet info`**, and when they're strong enough, enter the arena for an intense **`pet battle`** against rivals!\n\n"
                "**<:SynapseUsage:1487700535120363561> Commands**\n"
                "`pet`, `pet shop`, `pet buy`, `pet info`, `pet feed`, `pet play`, `pet train`, `pet rename`, `pet clean`, `pet heal`, `pet release`, `pet battle`, `pet leaderboard`, `petlist`"
            )
            embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/616/616408.png")
        elif category == "Business":
            embed.title = "🏢 Business"
            embed.description = (
                "Transform from an entrepreneur into a corporate mogul by building and managing your own lucrative business empire.\n\n"
                "> Take the leap and **`business start`** your company from the ground up. Monitor your daily operations with "
                "**`business info`**, and strategically **`business upgrade`** your facilities to multiply your revenue. Expand your "
                "workforce when you **`business hire`** new employees, and don't forget to **`business collect`** your massive profits!\n\n"
                "**<:SynapseUsage:1487700535120363561> Commands**\n"
                "`business start`, `business info`, `business collect`, `business upgrade`, `business hire`, `business fire`, `business rename`, `business close`"
            )
            embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/2830/2830284.png")
        elif category == "Gambling & Crime":
            embed.title = "🎲 Gambling & Crime"
            embed.description = (
                "For those who crave adrenaline, the shadows and the casinos offer shortcuts to wealth—if you're willing to take the risk.\n\n"
                "> Test your luck and potentially double your fortune by playing **`coinflip`**, spinning the **`slots`**, dealing in **`blackjack`**, "
                "or taking a general **`gamble`**. If you prefer the illicit route, attempt to **`rob`** unsuspecting users of their wallet cash, "
                "or commit a daring **`crime`** for a chance at an enormous payout—just beware of the heavy fines if you're caught!\n\n"
                "**<:SynapseUsage:1487700535120363561> Commands**\n"
                "`coinflip`, `slots`, `blackjack`, `gamble`, `rob`, `crime`"
            )
            embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/1055/1055673.png")
        embed.set_footer(text=f"Requested by {self.ctx.author.name}", icon_url=self.ctx.author.display_avatar.url)
        return embed

    async def update_category(self, interaction: discord.Interaction, category: str):
        self.current_category = category
        embed = self.get_embed(category)
        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        try:
            if self.message:
                await self.message.edit(view=self)
        except Exception:
            pass



class EconomyCog(commands.Cog):
    def __init__(self, client):
        self.client = client

    @commands.command(name="ecoguide", aliases=["economyguide", "ecohelp"])
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def ecoguide(self, ctx):
        """Interactive guide for the economy system."""
        view = EcoGuideView(ctx)
        embed = view.get_embed("Getting Started")
        view.message = await ctx.reply(embed=embed, view=view, mention_author=False)


    @staticmethod
    def _parse(amount_str: str, pool: int):
        """Parse 'all', '50%', or an integer. Returns int or None."""
        s = str(amount_str).lower().strip()
        if s == "all":
            return pool
        if "%" in s:
            try:
                pct = int(s.replace("%", ""))
                if not 1 <= pct <= 100:
                    return None
                return max(1, int(pool * pct / 100))
            except ValueError:
                return None
        try:
            return int(s)
        except ValueError:
            return None

    def _err(self, text: str) -> discord.Embed:
        return discord.Embed(description=f"{E_ERR} {text}", color=EMBED_COLOR)


    @commands.command(name="balance", aliases=["bal"])
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def balance(self, ctx, member: discord.Member = None):
        """Show your (or another user's) balance."""
        target = member or ctx.author
        await ensure_user(target.id)
        wallet, bank = await get_balance(target.id)

        embed = discord.Embed(color=EMBED_COLOR, timestamp=discord.utils.utcnow())
        embed.set_author(name=f"{target.display_name}'s Balance", icon_url=target.display_avatar.url)
        embed.add_field(name=f"{W_ICON} Wallet", value=f"{_fmt(wallet)} coins", inline=True)
        embed.add_field(name=f"{B_ICON} Bank",   value=f"{_fmt(bank)} coins",   inline=True)
        embed.add_field(name="💰 Total",          value=f"{_fmt(wallet + bank)} coins", inline=True)
        embed.set_footer(text=_footer(ctx))
        await ctx.reply(embed=embed, mention_author=False)


    @commands.command(name="deposit", aliases=["dep"])
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def deposit(self, ctx, amount: str = None):
        """Deposit coins from wallet into bank."""
        await ensure_user(ctx.author.id)
        if amount is None:
            return await ctx.reply(embed=self._err("Usage: `deposit <amount|all|%>`"), mention_author=False)

        wallet = await get_wallet(ctx.author.id)
        amt    = self._parse(amount, wallet)
        if amt is None or amt <= 0:
            return await ctx.reply(embed=self._err("Enter a valid positive amount."), mention_author=False)
        if amt > wallet:
            return await ctx.reply(embed=self._err(f"You only have **{_fmt(wallet)}** coins in your wallet."), mention_author=False)

        new_wallet = await add_wallet(ctx.author.id, -amt)
        new_bank   = await add_bank(ctx.author.id,    amt)

        embed = discord.Embed(
            description=f"{E_OK} Deposited **{_fmt(amt)}** coins into your bank.",
            color=EMBED_COLOR, timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name=f"{W_ICON} Wallet", value=f"{_fmt(new_wallet)}", inline=True)
        embed.add_field(name=f"{B_ICON} Bank",   value=f"{_fmt(new_bank)}",   inline=True)
        embed.set_footer(text=_footer(ctx))
        await ctx.reply(embed=embed, mention_author=False)


    @commands.command(name="withdraw")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def withdraw(self, ctx, amount: str = None):
        """Withdraw coins from bank into wallet."""
        await ensure_user(ctx.author.id)
        if amount is None:
            return await ctx.reply(embed=self._err("Usage: `withdraw <amount|all|%>`"), mention_author=False)

        bank = await get_bank(ctx.author.id)
        amt  = self._parse(amount, bank)
        if amt is None or amt <= 0:
            return await ctx.reply(embed=self._err("Enter a valid positive amount."), mention_author=False)
        if amt > bank:
            return await ctx.reply(embed=self._err(f"You only have **{_fmt(bank)}** coins in your bank."), mention_author=False)

        new_bank   = await add_bank(ctx.author.id,   -amt)
        new_wallet = await add_wallet(ctx.author.id,  amt)

        embed = discord.Embed(
            description=f"{E_OK} Withdrew **{_fmt(amt)}** coins from your bank.",
            color=EMBED_COLOR, timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name=f"{W_ICON} Wallet", value=f"{_fmt(new_wallet)}", inline=True)
        embed.add_field(name=f"{B_ICON} Bank",   value=f"{_fmt(new_bank)}",   inline=True)
        embed.set_footer(text=_footer(ctx))
        await ctx.reply(embed=embed, mention_author=False)


    @commands.command(name="beg")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 86400, commands.BucketType.user)
    async def beg(self, ctx):
        """Beg for a small amount of coins. (24h cooldown)"""
        await ensure_user(ctx.author.id)
        reward     = random.randint(10, 100)
        new_wallet = await add_wallet(ctx.author.id, reward)

        embed = discord.Embed(
            description=f"{E_OK} Someone took pity on you and gave you **{_fmt(reward)}** coins!",
            color=EMBED_COLOR, timestamp=discord.utils.utcnow(),
        )
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
        embed.set_footer(text=f"Wallet: {_fmt(new_wallet)} coins • Synapse - Economy")
        await ctx.reply(embed=embed, mention_author=False)

    @beg.error
    async def beg_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            h, rem = divmod(int(error.retry_after), 3600)
            m, s   = divmod(rem, 60)
            await ctx.reply(
                embed=discord.Embed(
                    description=f"{E_ERR} You already begged recently!\n> Try again in **{h}h {m}m {s}s**",
                    color=EMBED_COLOR,
                ),
                mention_author=False,
            )


    @commands.command(name="daily")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    async def daily(self, ctx):
        """Claim your daily reward. (24h cooldown, DB-persisted)"""
        await ensure_user(ctx.author.id)
        rem = await remaining_cooldown(ctx.author.id, "daily", 86400)
        if rem > 0:
            h, r = divmod(int(rem), 3600)
            m, s = divmod(r, 60)
            return await ctx.reply(
                embed=discord.Embed(
                    description=f"{E_ERR} Already claimed!\n> Come back in **{h}h {m}m {s}s**",
                    color=EMBED_COLOR,
                ),
                mention_author=False,
            )

        reward     = random.randint(200, 500)
        new_wallet = await add_wallet(ctx.author.id, reward)
        await set_cooldown(ctx.author.id, "daily")

        embed = discord.Embed(
            description=f"{E_OK} Daily reward claimed! **+{_fmt(reward)}** coins.",
            color=EMBED_COLOR, timestamp=discord.utils.utcnow(),
        )
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
        embed.set_footer(text=f"Wallet: {_fmt(new_wallet)} coins • Synapse - Economy")
        await ctx.reply(embed=embed, mention_author=False)


    @commands.command(name="weekly")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    async def weekly(self, ctx):
        """Claim your weekly reward. (7d cooldown, DB-persisted)"""
        await ensure_user(ctx.author.id)
        rem = await remaining_cooldown(ctx.author.id, "weekly", 604800)
        if rem > 0:
            d, r  = divmod(int(rem), 86400)
            h, r  = divmod(r, 3600)
            m, _  = divmod(r, 60)
            return await ctx.reply(
                embed=discord.Embed(
                    description=f"{E_ERR} Already claimed!\n> Come back in **{d}d {h}h {m}m**",
                    color=EMBED_COLOR,
                ),
                mention_author=False,
            )

        reward     = random.randint(1500, 3000)
        new_wallet = await add_wallet(ctx.author.id, reward)
        await set_cooldown(ctx.author.id, "weekly")

        embed = discord.Embed(
            description=f"{E_OK} Weekly reward claimed! **+{_fmt(reward)}** coins.",
            color=EMBED_COLOR, timestamp=discord.utils.utcnow(),
        )
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
        embed.set_footer(text=f"Wallet: {_fmt(new_wallet)} coins • Synapse - Economy")
        await ctx.reply(embed=embed, mention_author=False)


    @commands.command(name="baltop", aliases=["balancetop"])
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def baltop(self, ctx):
        """Show the richest members."""
        rows = await get_leaderboard(200)
        if not rows:
            return await ctx.reply(
                embed=discord.Embed(description="No economy data yet!", color=EMBED_COLOR),
                mention_author=False,
            )
        view         = LeaderboardView(ctx, rows)
        view.message = await ctx.reply(embed=view._build_embed(), view=view, mention_author=False)


    @commands.command(name="pay")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def pay(self, ctx, member: discord.Member = None, amount: int = None):
        """Transfer coins to another user."""
        if member is None or amount is None:
            return await ctx.reply(embed=self._err("Usage: `pay <@user> <amount>`"), mention_author=False)
        if member.bot or member.id == ctx.author.id:
            return await ctx.reply(embed=self._err("Invalid target."), mention_author=False)
        if amount <= 0:
            return await ctx.reply(embed=self._err("Amount must be positive."), mention_author=False)

        ok = await transfer(ctx.author.id, member.id, amount)
        if not ok:
            wallet = await get_wallet(ctx.author.id)
            return await ctx.reply(
                embed=self._err(f"You only have **{_fmt(wallet)}** coins in your wallet."),
                mention_author=False,
            )

        new_wallet = await get_wallet(ctx.author.id)
        embed = discord.Embed(
            description=(
                f"{E_OK} Sent **{_fmt(amount)}** coins to {member.mention}\n"
                f"> Your wallet: **{_fmt(new_wallet)}** coins"
            ),
            color=EMBED_COLOR, timestamp=discord.utils.utcnow(),
        )
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
        embed.set_footer(text="Synapse - Economy")
        await ctx.reply(embed=embed, mention_author=False)


    @commands.command(name="rob")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    async def rob(self, ctx, member: discord.Member = None):
        """Attempt to rob someone's wallet. 40% success. (1h cooldown)"""
        if member is None or member.bot or member.id == ctx.author.id:
            return await ctx.reply(embed=self._err("Usage: `rob <@user>`"), mention_author=False)

        await ensure_user(ctx.author.id)
        await ensure_user(member.id)

        rem = await remaining_cooldown(ctx.author.id, "rob", 3600)
        if rem > 0:
            h, r = divmod(int(rem), 3600)
            m, s = divmod(r, 60)
            return await ctx.reply(
                embed=discord.Embed(
                    description=f"{E_ERR} You're laying low.\n> Try again in **{h}h {m}m {s}s**",
                    color=EMBED_COLOR,
                ),
                mention_author=False,
            )

        victim_wallet = await get_wallet(member.id)
        if victim_wallet < 50:
            return await ctx.reply(
                embed=self._err(f"{member.display_name} is too broke to rob (< 50 coins)."),
                mention_author=False,
            )

        await set_cooldown(ctx.author.id, "rob")
        success = random.random() < 0.40

        if success:
            stolen     = random.randint(int(victim_wallet * 0.10), int(victim_wallet * 0.35))
            stolen     = max(1, stolen)
            new_wallet = await add_wallet(ctx.author.id,  stolen)
            await add_wallet(member.id, -stolen)
            line = (
                f"{E_OK} You robbed {member.mention}!\n"
                f"> Stole **{_fmt(stolen)}** coins from their wallet."
            )
        else:
            your_wallet = await get_wallet(ctx.author.id)
            fine        = min(random.randint(50, 200), your_wallet)
            new_wallet  = await add_wallet(ctx.author.id, -fine)
            line = (
                f"{E_ERR} You got caught!\n"
                f"> Paid a fine of **{_fmt(fine)}** coins."
            )

        embed = discord.Embed(description=line, color=EMBED_COLOR, timestamp=discord.utils.utcnow())
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
        embed.set_footer(text=f"Wallet: {_fmt(new_wallet)} coins • Synapse - Economy")
        await ctx.reply(embed=embed, mention_author=False)


    _CRIMES = [
        ("You hacked a corporate server 💻",             300, 800, True),
        ("You pickpocketed a tourist 👜",                 80, 250,  True),
        ("You sold used AirPods as new 📦",              100, 400,  True),
        ("You ran a shell company 🏢",                   200, 600,  True),
        ("You got caught red-handed 🚔",                 100, 300, False),
        ("The police recognised you 👮",                  50, 200, False),
        ("Your scheme collapsed 💸",                     150, 350, False),
    ]

    @commands.command(name="crime")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    async def crime(self, ctx):
        """High-risk high-reward crime. (45m cooldown)"""
        await ensure_user(ctx.author.id)
        rem = await remaining_cooldown(ctx.author.id, "crime", 2700)
        if rem > 0:
            m, s = divmod(int(rem), 60)
            return await ctx.reply(
                embed=discord.Embed(
                    description=f"{E_ERR} Lay low for a bit.\n> Try again in **{m}m {s}s**",
                    color=EMBED_COLOR,
                ),
                mention_author=False,
            )

        await set_cooldown(ctx.author.id, "crime")
        desc, low, high, is_win = random.choice(self._CRIMES)
        amount = random.randint(low, high)

        if is_win:
            new_wallet = await add_wallet(ctx.author.id, amount)
            result = f"{E_OK} **Crime Successful!**\n> {desc}\n> **+{_fmt(amount)}** coins!"
        else:
            wallet = await get_wallet(ctx.author.id)
            amount = min(amount, wallet)
            new_wallet = await add_wallet(ctx.author.id, -amount)
            result = f"{E_ERR} **Crime Failed!**\n> {desc}\n> **-{_fmt(amount)}** coins."

        embed = discord.Embed(description=result, color=EMBED_COLOR, timestamp=discord.utils.utcnow())
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
        embed.set_footer(text=f"Wallet: {_fmt(new_wallet)} coins • Synapse - Economy")
        await ctx.reply(embed=embed, mention_author=False)


    @commands.command(name="addbal")
    @commands.is_owner()
    async def addbal(self, ctx, member: discord.Member = None, amount: int = None, where: str = "wallet"):
        """Add balance to a user. [wallet/bank]"""
        if not member or not amount:
            return await ctx.reply("Usage: `addbal <@user> <amount> [wallet/bank]`")
        where = where.lower()
        if where not in ("wallet", "bank"):
            return await ctx.reply("Use `wallet` or `bank`.")
        await ensure_user(member.id)
        if where == "wallet":
            await add_wallet(member.id, amount)
        else:
            await add_bank(member.id, amount)
        await ctx.reply(embed=discord.Embed(
            description=f"{E_OK} Added **{_fmt(amount)}** coins to `{member.display_name}`'s **{where}**.",
            color=EMBED_COLOR,
        ))

    @commands.command(name="removebal")
    @commands.is_owner()
    async def removebal(self, ctx, member: discord.Member = None, amount: int = None, where: str = "wallet"):
        """Remove balance from a user. [wallet/bank]"""
        if not member or not amount:
            return await ctx.reply("Usage: `removebal <@user> <amount> [wallet/bank]`")
        where = where.lower()
        if where not in ("wallet", "bank"):
            return await ctx.reply("Use `wallet` or `bank`.")
        await ensure_user(member.id)
        if where == "wallet":
            current = await get_wallet(member.id)
        else:
            current = await get_bank(member.id)
        if amount > current:
            return await ctx.reply(f"{E_ERR} `{member.display_name}` doesn't have that much in {where}.")
        if where == "wallet":
            await add_wallet(member.id, -amount)
        else:
            await add_bank(member.id, -amount)
        await ctx.reply(embed=discord.Embed(
            description=f"{E_OK} Removed **{_fmt(amount)}** coins from `{member.display_name}`'s **{where}**.",
            color=EMBED_COLOR,
        ))

    @commands.command(name="setbal")
    @commands.is_owner()
    async def setbal(self, ctx, member: discord.Member = None, amount: int = None, where: str = "wallet"):
        """Set a user's balance. [wallet/bank]"""
        if not member or amount is None:
            return await ctx.reply("Usage: `setbal <@user> <amount> [wallet/bank]`")
        if amount < 0:
            return await ctx.reply("Balance can't be negative.")
        where = where.lower()
        if where not in ("wallet", "bank"):
            return await ctx.reply("Use `wallet` or `bank`.")
        await ensure_user(member.id)
        if where == "wallet":
            await set_wallet(member.id, amount)
        else:
            await set_bank(member.id, amount)
        await ctx.reply(embed=discord.Embed(
            description=f"{E_OK} Set `{member.display_name}`'s **{where}** to **{_fmt(amount)}** coins.",
            color=EMBED_COLOR,
        ))


async def setup(client):
    await init_db()
    await client.add_cog(EconomyCog(client))