import random
import datetime
import discord
from discord.ext import commands
from typing import Dict, List

from utils.Tools import blacklist_check, ignore_check
from utils.eco_db import (
    init_db, ensure_user, get_wallet, add_wallet,
    get_user_jobs, add_user_job, remove_user_job,
    remaining_cooldown, set_cooldown,
)

EMBED_COLOR = 0x2b2d31
E_OK  = "<:emoji_1769867605256:1467155817726873650>"
E_ERR = "<:emoji_1769867589372:1467155751456735326>"


def _fmt(n: int) -> str:
    return f"{n:,}"



class JobMarketView(discord.ui.View):
    PER_PAGE = 3

    def __init__(self, cog, ctx, user_jobs: list, page: int = 0):
        super().__init__(timeout=60)
        self.cog       = cog
        self.ctx       = ctx
        self.user_jobs = user_jobs
        self.page      = page
        self.pages     = max(1, -(-len(cog.JOBS) // self.PER_PAGE))
        self.message   = None
        self._sync_buttons()

    def _sync_buttons(self):
        self.prev_btn.disabled = self.page == 0
        self.next_btn.disabled = self.page >= self.pages - 1

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("Not yours!", ephemeral=True)
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
        jobs_list = list(self.cog.JOBS.items())
        start     = self.page * self.PER_PAGE
        chunk     = jobs_list[start: start + self.PER_PAGE]

        embed = discord.Embed(
            description=f"Browse all available jobs and unlock them with `buyjob`.",
            color=EMBED_COLOR,
            timestamp=discord.utils.utcnow(),
        )
        embed.set_author(name="Job Market")
        LOCK   = "<:rlock:1459852279506010234>"
        UNLOCK = "<:gunlock:1459851897040273632>"

        for name, info in chunk:
            owned = name in self.user_jobs
            status = f"{UNLOCK} Owned" if owned else f"{LOCK} {_fmt(info['cost'])} coins to unlock"
            val = (
                f"Base Pay: **{_fmt(info['base_pay'])}** coins\n"
                f"Bonus: **{info['bonus_chance']*100:.0f}%** chance of +**{_fmt(info['bonus_amount'])}**\n"
                f"{status}"
            )
            embed.add_field(name=name, value=val, inline=False)

        embed.set_footer(text=f"Page {self.page + 1}/{self.pages} • Synapse - Economy")
        return embed

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def prev_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.page -= 1
        self._sync_buttons()
        await interaction.response.edit_message(embed=self._build_embed(), view=self)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def next_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.page += 1
        self._sync_buttons()
        await interaction.response.edit_message(embed=self._build_embed(), view=self)



class JobMarketCog(commands.Cog):

    JOBS: Dict[str, Dict] = {
        "McDonalds-Employee":  {"base_pay": 75,   "bonus_chance": 0.20, "bonus_amount": 50,  "cost": 0},
        "Delivery-Driver":     {"base_pay": 150,  "bonus_chance": 0.25, "bonus_amount": 50,  "cost": 0},
        "Artist":              {"base_pay": 300,  "bonus_chance": 0.25, "bonus_amount": 250, "cost": 1000},
        "Streamer":            {"base_pay": 250,  "bonus_chance": 0.55, "bonus_amount": 400, "cost": 4000},
        "Stripper":            {"base_pay": 150,  "bonus_chance": 0.50, "bonus_amount": 150, "cost": 1000},
        "Teacher":             {"base_pay": 350,  "bonus_chance": 0.10, "bonus_amount": 100, "cost": 2000},
        "Farmer":              {"base_pay": 220,  "bonus_chance": 0.20, "bonus_amount": 80,  "cost": 2000},
        "Flight-Attendant":    {"base_pay": 250,  "bonus_chance": 0.20, "bonus_amount": 100, "cost": 3000},
        "Youtuber":            {"base_pay": 300,  "bonus_chance": 0.60, "bonus_amount": 500, "cost": 5000},
        "Plumber":             {"base_pay": 300,  "bonus_chance": 0.20, "bonus_amount": 100, "cost": 4000},
        "Real-Estate-Agent":   {"base_pay": 400,  "bonus_chance": 0.40, "bonus_amount": 300, "cost": 10000},
        "Software-Developer":  {"base_pay": 500,  "bonus_chance": 0.20, "bonus_amount": 200, "cost": 5000},
        "Esportler":           {"base_pay": 400,  "bonus_chance": 0.45, "bonus_amount": 300, "cost": 8000},
        "Police-Officer":      {"base_pay": 450,  "bonus_chance": 0.15, "bonus_amount": 150, "cost": 7500},
        "Life-Coach":          {"base_pay": 350,  "bonus_chance": 0.30, "bonus_amount": 150, "cost": 6000},
        "Engineer":            {"base_pay": 550,  "bonus_chance": 0.20, "bonus_amount": 250, "cost": 10000},
        "Lawyer":              {"base_pay": 650,  "bonus_chance": 0.30, "bonus_amount": 250, "cost": 18000},
        "Doctor":              {"base_pay": 600,  "bonus_chance": 0.10, "bonus_amount": 300, "cost": 15000},
        "Stock-Trader":        {"base_pay": 600,  "bonus_chance": 0.50, "bonus_amount": 400, "cost": 20000},
        "Scientist":           {"base_pay": 700,  "bonus_chance": 0.25, "bonus_amount": 300, "cost": 20000},
        "Politician":          {"base_pay": 750,  "bonus_chance": 0.30, "bonus_amount": 350, "cost": 25000},
        "Pilot":               {"base_pay": 800,  "bonus_chance": 0.15, "bonus_amount": 400, "cost": 30000},
        "Astronaut":           {"base_pay": 1000, "bonus_chance": 0.20, "bonus_amount": 500, "cost": 50000},
    }

    def __init__(self, client):
        self.client = client


    @commands.command(name="jobs")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    async def jobs(self, ctx, page: int = 1):
        """Browse the job market."""
        await ensure_user(ctx.author.id)
        user_jobs = await get_user_jobs(ctx.author.id)
        view = JobMarketView(self, ctx, user_jobs, page=max(0, page - 1))
        view.message = await ctx.reply(embed=view._build_embed(), view=view, mention_author=False)


    @commands.command(name="buyjob")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def buyjob(self, ctx, *, job_name: str = None):
        """Purchase a job to unlock it. Max 3 jobs."""
        await ensure_user(ctx.author.id)

        if not job_name:
            return await ctx.reply(
                embed=discord.Embed(
                    description=f"{E_ERR} Usage: `buyjob <job name>` — use `jobs` to browse.",
                    color=EMBED_COLOR,
                ),
                mention_author=False,
            )

        job_name = job_name.strip().title()
        if job_name not in self.JOBS:
            return await ctx.reply(
                embed=discord.Embed(
                    description=f"{E_ERR} `{job_name}` is not a valid job. Use `jobs` to see the market.",
                    color=EMBED_COLOR,
                ),
                mention_author=False,
            )

        user_jobs = await get_user_jobs(ctx.author.id)

        if job_name in user_jobs:
            return await ctx.reply(
                embed=discord.Embed(
                    description=f"{E_ERR} You already own **{job_name}**.", color=EMBED_COLOR,
                ),
                mention_author=False,
            )

        if len(user_jobs) >= 3:
            return await ctx.reply(
                embed=discord.Embed(
                    description=f"{E_ERR} You can only hold **3 jobs** at a time. Use `removejob` first.",
                    color=EMBED_COLOR,
                ),
                mention_author=False,
            )

        info   = self.JOBS[job_name]
        wallet = await get_wallet(ctx.author.id)

        if wallet < info["cost"]:
            return await ctx.reply(
                embed=discord.Embed(
                    description=(
                        f"{E_ERR} You need **{_fmt(info['cost'])}** coins but only have **{_fmt(wallet)}**."
                    ),
                    color=EMBED_COLOR,
                ),
                mention_author=False,
            )

        new_wallet = await add_wallet(ctx.author.id, -info["cost"])
        await add_user_job(ctx.author.id, job_name)
        user_jobs.append(job_name)

        embed = discord.Embed(
            description=(
                f"{E_OK} You unlocked **{job_name}**!\n"
                f"> Cost: **{_fmt(info['cost'])}** coins\n"
                f"> Your jobs: {', '.join(f'`{j}`' for j in user_jobs)}"
            ),
            color=EMBED_COLOR,
            timestamp=discord.utils.utcnow(),
        )
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
        embed.set_footer(text=f"Wallet: {_fmt(new_wallet)} coins • Synapse - Economy")
        await ctx.reply(embed=embed, mention_author=False)


    @commands.command(name="removejob")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    async def removejob(self, ctx, *, job_name: str = None):
        """Remove one of your jobs."""
        if not job_name:
            return await ctx.reply(
                embed=discord.Embed(
                    description=f"{E_ERR} Usage: `removejob <job name>`", color=EMBED_COLOR,
                ),
                mention_author=False,
            )

        job_name  = job_name.strip().title()
        user_jobs = await get_user_jobs(ctx.author.id)

        if job_name not in user_jobs:
            return await ctx.reply(
                embed=discord.Embed(
                    description=f"{E_ERR} You don't own **{job_name}**.", color=EMBED_COLOR,
                ),
                mention_author=False,
            )

        await remove_user_job(ctx.author.id, job_name)
        user_jobs.remove(job_name)

        embed = discord.Embed(
            description=(
                f"{E_OK} Removed **{job_name}** from your jobs.\n"
                f"> Remaining: {', '.join(f'`{j}`' for j in user_jobs) or 'None'}"
            ),
            color=EMBED_COLOR,
            timestamp=discord.utils.utcnow(),
        )
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
        embed.set_footer(text="Synapse - Economy")
        await ctx.reply(embed=embed, mention_author=False)


    @commands.command(name="work")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    async def work(self, ctx):
        """Work all your jobs. (24h cooldown, DB-persisted)"""
        await ensure_user(ctx.author.id)
        rem = await remaining_cooldown(ctx.author.id, "work", 86400)
        if rem > 0:
            h, r = divmod(int(rem), 3600)
            m, s = divmod(r, 60)
            return await ctx.reply(
                embed=discord.Embed(
                    description=f"{E_ERR} You already worked today!\n> Come back in **{h}h {m}m {s}s**",
                    color=EMBED_COLOR,
                ),
                mention_author=False,
            )

        user_jobs = await get_user_jobs(ctx.author.id)
        if not user_jobs:
            return await ctx.reply(
                embed=discord.Embed(
                    description=f"{E_ERR} You don't have any jobs! Use `jobs` to browse and `buyjob` to unlock one.",
                    color=EMBED_COLOR,
                ),
                mention_author=False,
            )

        await set_cooldown(ctx.author.id, "work")

        total     = 0
        breakdown = []
        for job_name in user_jobs:
            info   = self.JOBS.get(job_name)
            if not info:
                continue
            earn   = info["base_pay"]
            bonus  = 0
            if random.random() < info["bonus_chance"]:
                bonus = info["bonus_amount"]
                earn += bonus
                breakdown.append(f"**{job_name}**: {_fmt(info['base_pay'])} + {_fmt(bonus)} bonus")
            else:
                breakdown.append(f"**{job_name}**: {_fmt(earn)}")
            total += earn

        new_wallet = await add_wallet(ctx.author.id, total)

        embed = discord.Embed(
            description=f"{E_OK} You worked and earned **{_fmt(total)}** coins!\n\n" + "\n".join(breakdown),
            color=EMBED_COLOR,
            timestamp=discord.utils.utcnow(),
        )
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
        embed.set_footer(text=f"Wallet: {_fmt(new_wallet)} coins • Synapse - Economy")
        await ctx.reply(embed=embed, mention_author=False)


    @commands.command(name="myjobs")
    @blacklist_check()
    @ignore_check()
    @commands.guild_only()
    async def myjobs(self, ctx):
        """View your owned jobs."""
        await ensure_user(ctx.author.id)
        user_jobs = await get_user_jobs(ctx.author.id)

        if not user_jobs:
            return await ctx.reply(
                embed=discord.Embed(
                    description=(
                        f"{E_ERR} You have no jobs yet!\n"
                        f"> Use `jobs` to browse and `buyjob <name>` to unlock one."
                    ),
                    color=EMBED_COLOR,
                ),
                mention_author=False,
            )

        embed = discord.Embed(
            description=f"You own **{len(user_jobs)}/3** job(s).",
            color=EMBED_COLOR,
            timestamp=discord.utils.utcnow(),
        )
        embed.set_author(name=f"{ctx.author.display_name}'s Jobs", icon_url=ctx.author.display_avatar.url)

        for name in user_jobs:
            info = self.JOBS.get(name, {})
            embed.add_field(
                name=f"✅ {name}",
                value=(
                    f"Base Pay: **{_fmt(info.get('base_pay', 0))}** coins\n"
                    f"Bonus: **{info.get('bonus_chance', 0)*100:.0f}%** — **{_fmt(info.get('bonus_amount', 0))}**"
                ),
                inline=False,
            )

        embed.set_footer(text="Synapse - Economy • work once a day to collect earnings")
        await ctx.reply(embed=embed, mention_author=False)


async def setup(client):
    await init_db()
    await client.add_cog(JobMarketCog(client))