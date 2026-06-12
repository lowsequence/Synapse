import discord
from discord.ext import commands
import aiosqlite
import platform
import datetime
import time
import os

try:
    import psutil
except ImportError:
    psutil = None

ACCENT_COLOR = 0x2b2d31



def format_dt(dt: datetime.datetime, style: str = "f") -> str:
    """Formats a datetime object for Discord timestamp."""
    if dt is None:
        return "N/A"
    return f"<t:{int(dt.timestamp())}:{style}>"


async def is_guild_premium(guild_id: int) -> bool:
    """Checks if the guild has an active premium subscription."""
    db_path = "database/premium_codes.db"
    if not os.path.exists(db_path):
        return False
    try:
        async with aiosqlite.connect(db_path) as db:
            async with db.execute(
                "SELECT expires_at FROM premium_guilds WHERE guild_id = ?",
                (guild_id,)
            ) as cursor:
                row = await cursor.fetchone()
        if not row:
            return False
        expires_at = datetime.datetime.fromisoformat(row[0])
        if expires_at < datetime.datetime.utcnow():
            return False
        return True
    except Exception:
        return False


def _ephem_embed(text: str, color: int = ACCENT_COLOR) -> discord.Embed:
    """Creates a minimal ephemeral Embed."""
    return discord.Embed(description=text, color=color)



class RoleInfoDropdown(discord.ui.Select):
    def __init__(self, view_obj: "RoleInfoView"):
        options = [
            discord.SelectOption(label="General Information", description="View basic role details", emoji="<:SynapseIGeneral:1477289401938608138>", value="general"),
            discord.SelectOption(label="Role Properties", description="View role specific properties", emoji="<:SynapseProperties:1477289753979392131>", value="properties"),
            discord.SelectOption(label="Permissions", description="View role permissions", emoji="<:SynapseShield:1477548906848981225>", value="permissions"),
            discord.SelectOption(label="Members", description="View members with this role", emoji="<:MekoUser:1477291982110986470>", value="members"),
        ]
        super().__init__(placeholder="Select a category to view...", min_values=1, max_values=1, options=options)
        self.view_obj = view_obj

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.view_obj.author_id:
            return await interaction.response.send_message("You cannot use this interaction.", ephemeral=True)

        choice = self.values[0]

        if choice == "permissions":
            perms = [perm[0].replace("_", " ").title() for perm in self.view_obj.role.permissions if perm[1]]
            desc = ", ".join(perms) if perms else "No permissions."
            embed = _ephem_embed(
                f"**Permissions for {self.view_obj.role.name}**\n\n{desc}",
                color=self.view_obj.role.color.value or ACCENT_COLOR,
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        if choice == "members":
            members = self.view_obj.role.members
            if not members:
                text = f"**Members with {self.view_obj.role.name}**\n\nNo members have this role."
            else:
                count = len(members)
                lines = "\n".join(m.mention for m in members[:20])
                text = f"**Members with {self.view_obj.role.name} ({count})**\n\n{lines}"
                if count > 20:
                    text += f"\n*...and {count - 20} more.*"
            embed = _ephem_embed(text, color=self.view_obj.role.color.value or ACCENT_COLOR)
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        self.view_obj.current_tab = choice
        embed = self.view_obj.get_embed()
        await interaction.response.edit_message(embed=embed, view=self.view_obj)

class RoleInfoView(discord.ui.View):
    def __init__(self, role: discord.Role, author_id: int, guild_icon_url: str | None = None):
        super().__init__(timeout=180)
        self.author_id = author_id
        self.role = role
        self.guild_icon_url = guild_icon_url
        self.current_tab = "general"

        self.dropdown = RoleInfoDropdown(self)
        self.add_item(self.dropdown)

    def get_embed(self) -> discord.Embed:
        role = self.role
        created = format_dt(role.created_at, "d")
        color = role.color.value if role.color.value else ACCENT_COLOR

        embed = discord.Embed(color=color)

        if self.guild_icon_url:
            embed.set_author(name=f"Role Information: {role.name}", icon_url=self.guild_icon_url)
        else:
            embed.set_author(name=f"Role Information: {role.name}")

        if self.current_tab == "general":
            text = (
                f"> **ID** : {role.id}\n"
                f"> **Name** : {role.name}\n"
                f"> **Mention** : {role.mention}\n"
                f"> **Created** : {created}\n"
                f"> **Position** : {role.position}\n"
                f"> **Color** : {role.color}\n"
                f"> **Hoisted** : {'Yes' if role.hoist else 'No'}\n"
                f"> **Managed** : {'Yes' if role.managed else 'No'}"
            )
            embed.add_field(name="<:SynapseIGeneral:1477289401938608138> General Information", value=text, inline=False)
        else:
            text = (
                f"> **Mentionable** : {'Yes' if role.mentionable else 'No'}\n"
                f"> **Members with Role** : {len(role.members)}\n"
                f"> **Integration Role** : {'Yes' if role.is_integration() else 'No'}\n"
                f"> **Default Role** : {'Yes' if role.is_default() else 'No'}"
            )
            embed.add_field(name="<:SynapseProperties:1477289753979392131> Role Properties", value=text, inline=False)

        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "You cannot use this interaction.", ephemeral=True
            )
            return False
        return True



class ServerInfoView(discord.ui.View):
    def __init__(self, guild: discord.Guild, author_id: int, is_premium: bool):
        super().__init__(timeout=180)
        self.author_id = author_id
        self.guild = guild
        self.is_premium = is_premium

    def get_embed(self) -> discord.Embed:
        guild = self.guild
        embed = discord.Embed(color=ACCENT_COLOR)

        if guild.icon:
            embed.set_author(name=f"{guild.name}", icon_url=guild.icon.url)
            embed.set_thumbnail(url=guild.icon.url)
        else:
            embed.set_author(name=f"{guild.name}")

        owner = str(guild.owner) if guild.owner else "Unknown"
        created = format_dt(guild.created_at, "D")
        gen_text = (
            f"> **Name** : {guild.name}\n"
            f"> **ID** : {guild.id}\n"
            f"> **Owner** : {owner}\n"
            f"> **Created** : {created}\n"
            f"> **Verification** : {str(guild.verification_level).title()}\n"
            f"> **Vanity URL** : {guild.vanity_url_code or 'None'}"
        )
        embed.add_field(name="<:SynapseIGeneral:1477289401938608138> General", value=gen_text, inline=True)

        humans = sum(1 for m in guild.members if not m.bot)
        bots = sum(1 for m in guild.members if m.bot)
        online = sum(1 for m in guild.members if m.status == discord.Status.online)
        idle = sum(1 for m in guild.members if m.status == discord.Status.idle)
        dnd = sum(1 for m in guild.members if m.status == discord.Status.dnd)
        offline = sum(1 for m in guild.members if m.status == discord.Status.offline)
        stats_text = (
            f"> **Members** : {guild.member_count} ({humans}H | {bots}B)\n"
            f"> **Online** : {online} | **Idle** : {idle}\n"
            f"> **DND** : {dnd} | **Offline** : {offline}"
        )
        embed.add_field(name="<:MekoIstats:1477290724679745576> Statistics", value=stats_text, inline=True)

        chan_text = (
            f"> **Text** : {len(guild.text_channels)} | **Voice** : {len(guild.voice_channels)}\n"
            f"> **Categories** : {len(guild.categories)}\n"
            f"> **Roles** : {len(guild.roles)} | **Highest** : {guild.roles[-1].mention}"
        )
        embed.add_field(name="<:SynapseChannel:1477291334363648302> Channels & Roles", value=chan_text, inline=False)

        sec_text = (
            f"> **Level** : {guild.premium_tier} | **Boosts** : {guild.premium_subscription_count}\n"
            f"> **MFA** : {guild.mfa_level} | **Filter** : {guild.explicit_content_filter}\n"
            f"> **Premium System** : {'Yes' if self.is_premium else 'No'}"
        )
        embed.add_field(name="<:SynapseShield:1477548906848981225> Boost & Security", value=sec_text, inline=False)

        embed.set_footer(text=f"ID: {guild.id} | Synapse")
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("You cannot use this interaction.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Icon", style=discord.ButtonStyle.secondary)
    async def icon_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not self.guild.icon:
            return await interaction.response.send_message(embed=_ephem_embed("No icon set."), ephemeral=True)
        embed = discord.Embed(title="Server Icon", color=ACCENT_COLOR)
        embed.set_image(url=self.guild.icon.url)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Banner", style=discord.ButtonStyle.secondary)
    async def banner_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not self.guild.banner:
            return await interaction.response.send_message(embed=_ephem_embed("No banner set."), ephemeral=True)
        embed = discord.Embed(title="Server Banner", color=ACCENT_COLOR)
        embed.set_image(url=self.guild.banner.url)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Features", style=discord.ButtonStyle.secondary)
    async def features_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        features_list = [
            "ANIMATED_ICON", "BANNER", "COMMUNITY", "DISCOVERABLE", "INVITE_SPLASH",
            "MEMBER_VERIFICATION_GATE_ENABLED", "NEWS", "PARTNERED", "PREVIEW_ENABLED",
            "VANITY_URL", "VERIFIED", "VIP_REGIONS", "WELCOME_SCREEN_ENABLED",
            "TICKETED_EVENTS_ENABLED", "MONETIZATION_ENABLED", "MORE_STICKERS",
            "THREE_DAY_THREAD_ARCHIVE", "SEVEN_DAY_THREAD_ARCHIVE", "PRIVATE_THREADS",
            "ROLE_ICONS",
        ]
        guild_features = set(self.guild.features)

        def get_lines(fs):
            ls = []
            for feature in fs:
                display_name = feature.replace("_", " ").title()
                icon = "<:emoji_1769867605256:1467155817726873650>" if feature in guild_features else "<:emoji_1769867589372:1467155751456735326>"
                ls.append(f"{icon} {display_name}")
            return "\n".join(ls)

        mid = len(features_list) // 2
        embed = discord.Embed(title="Server Features", color=ACCENT_COLOR)
        embed.add_field(name="Part 1", value=get_lines(features_list[:mid]), inline=True)
        embed.add_field(name="Part 2", value=get_lines(features_list[mid:]), inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)



class UserInfoView(discord.ui.View):
    def __init__(self, user: discord.Member, author_id: int):
        super().__init__(timeout=180)
        self.author_id = author_id
        self.user = user

    def get_embed(self) -> discord.Embed:
        user = self.user
        embed = discord.Embed(color=user.color.value if user.color.value else ACCENT_COLOR)
        embed.set_author(name=f"{user.display_name} (@{user.name})", icon_url=user.display_avatar.url)
        embed.set_thumbnail(url=user.display_avatar.url)

        created = format_dt(user.created_at, "D")
        gen_text = (
            f"> **Name** : {user.name}\n"
            f"> **ID** : {user.id}\n"
            f"> **Bot** : {'Yes' if user.bot else 'No'}\n"
            f"> **Created** : {created}\n"
            f"> **Avatar** : {'Animated' if user.display_avatar.is_animated() else 'Static'}"
        )
        embed.add_field(name="<:SynapseIGeneral:1477289401938608138> General", value=gen_text, inline=False)

        joined = format_dt(user.joined_at, "D")
        nick = user.nick if user.nick else "None"
        boosting = format_dt(user.premium_since, "R") if user.premium_since else "No"
        timeout = format_dt(user.timed_out_until, "R") if user.timed_out_until else "None"
        guild_text = (
            f"> **Joined** : {joined}\n"
            f"> **Nickname** : {nick}\n"
            f"> **Top Role** : {user.top_role.mention}\n"
            f"> **Boosting** : {boosting}\n"
            f"> **Timeout** : {timeout}"
        )
        embed.add_field(name="<:SynapseIGuild:1477293210639536254> Guild Information", value=guild_text, inline=False)

        flags = [flag[0].replace("_", " ").title() for flag in user.public_flags if flag[1]]
        if flags:
            embed.add_field(name="<:MekoDev:1477293186543259748> Badges", value=f"> {', '.join(flags)}", inline=False)

        embed.set_footer(text=f"ID: {user.id} | Synapse")
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("You cannot use this interaction.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Avatar", style=discord.ButtonStyle.secondary)
    async def avatar_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        embed = discord.Embed(title=f"{self.user.display_name}'s Avatar", color=ACCENT_COLOR)
        embed.set_image(url=self.user.display_avatar.url)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Banner", style=discord.ButtonStyle.secondary)
    async def banner_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        fetched = await interaction.client.fetch_user(self.user.id)
        if not fetched.banner:
            return await interaction.response.send_message(embed=_ephem_embed("No banner set."), ephemeral=True)
        embed = discord.Embed(title=f"{self.user.display_name}'s Banner", color=ACCENT_COLOR)
        embed.set_image(url=fetched.banner.url)
        await interaction.response.send_message(embed=embed, ephemeral=True)



class StatsView(discord.ui.View):
    def __init__(self, bot: commands.Bot, author_id: int):
        super().__init__(timeout=180)
        self.author_id = author_id
        self.bot = bot

        self.general_btn = discord.ui.Button(
            label="General", style=discord.ButtonStyle.secondary, custom_id="st_general"
        )
        self.system_btn = discord.ui.Button(
            label="System", style=discord.ButtonStyle.secondary, custom_id="st_system"
        )
        self.team_btn = discord.ui.Button(
            label="Team", style=discord.ButtonStyle.secondary, custom_id="st_team"
        )
        self.general_btn.callback = self.general_callback
        self.system_btn.callback = self.system_callback
        self.team_btn.callback = self.team_callback

        self.add_item(self.general_btn)
        self.add_item(self.system_btn)
        self.add_item(self.team_btn)

    def get_embed(self, tab: str = "General", text: str = "") -> discord.Embed:
        bot = self.bot
        total_members = sum(g.member_count or 0 for g in bot.guilds)

        embed = discord.Embed(color=ACCENT_COLOR)
        embed.set_author(name="Bot Statistics", icon_url=bot.user.display_avatar.url)
        embed.set_thumbnail(url=bot.user.display_avatar.url)

        embed.description = (
            f"Latency: **{round(bot.latency * 1000)}ms** · "
            f"**{len(bot.guilds)}** guilds · "
            f"**{total_members}** users"
        )

        if tab == "General":
            embed.add_field(name="<:SynapseGgeneral:1477295060281458739> General", value=text, inline=False)
        elif tab == "System":
            embed.add_field(name="<:SynapseServer:1477295497268953099> System", value=text, inline=False)
        elif tab == "Team":
            embed.description = text

        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "You cannot use this interaction.", ephemeral=True
            )
            return False
        return True

    async def general_callback(self, interaction: discord.Interaction) -> None:
        bot = self.bot
        total_members = sum(g.member_count or 0 for g in bot.guilds)
        total_channels = sum(len(g.channels) for g in bot.guilds)
        fields = [
            ("Bot Name", str(bot.user)),
            ("Bot ID", str(bot.user.id)),
            ("Servers", str(len(bot.guilds))),
            ("Users", str(total_members)),
            ("Channels", str(total_channels)),
            ("Commands Count", len(set(self.bot.walk_commands()))),
            ("Latency", f"{round(bot.latency * 1000)}ms"),
        ]
        gen_val = "\n".join(f"> **{n}** : {v}" for n, v in fields)

        embed = self.get_embed("General", gen_val)
        await interaction.response.edit_message(embed=embed, view=self)

    async def system_callback(self, interaction: discord.Interaction) -> None:
        bot = self.bot
        mem = psutil.virtual_memory() if psutil else None
        cpu = psutil.cpu_percent() if psutil else "N/A"
        mem_usage = f"{mem.percent}%" if mem else "N/A"
        uptime_seconds = int(time.time() - bot.start_time) if hasattr(bot, "start_time") else 0
        uptime_str = str(datetime.timedelta(seconds=uptime_seconds))

        fields = [
            ("Python Version", platform.python_version()),
            ("discord.py Version", discord.__version__),
            ("Memory Usage", mem_usage),
            ("CPU Usage", f"{cpu}%" if cpu != "N/A" else "N/A"),
            ("Uptime", uptime_str),
            ("OS", f"{platform.system()} {platform.release()}"),
            ("Architecture", platform.machine()),
        ]
        sys_val = "\n".join(f"> **{n}** : {v}" for n, v in fields)

        embed = self.get_embed("System", sys_val)
        await interaction.response.edit_message(embed=embed, view=self)

    async def team_callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()

        OWNER_IDS = [
            1287859210436087930,
            190487452949938176,
            1113016552623722497,
        ]
        DEVELOPER_IDS = [
            1368989570816802886,
            1482994688305791088,
        ]

        async def fetch_user_line(uid: int) -> str:
            user = self.bot.get_user(uid)
            if not user:
                try:
                    user = await self.bot.fetch_user(uid)
                except Exception:
                    return f"> [Unknown User](https://discord.com/users/{uid}) — Unknown"
            return f"> [{user.display_name}](https://discord.com/users/{uid}) — {user.name}"

        owner_lines = "\n".join([await fetch_user_line(uid) for uid in OWNER_IDS])
        dev_lines = "\n".join([await fetch_user_line(uid) for uid in DEVELOPER_IDS])

        text = f"**<:MekoDev:1477293186543259748> Developers**\n{dev_lines}\n\n**<:MekoOwner:1477294556176322622> Owner**\n{owner_lines}"

        embed = self.get_embed("Team", text)
        await interaction.edit_original_response(embed=embed, view=self)


class Extra2(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        if not hasattr(self.bot, "start_time"):
            self.bot.start_time = time.time()

    @commands.hybrid_command(name="roleinfo", aliases=["ri"], help="Shows information about a role.")
    async def roleinfo(self, ctx: commands.Context, role: discord.Role):
        guild_icon_url = ctx.guild.icon.url if ctx.guild.icon else None
        view = RoleInfoView(role, ctx.author.id, guild_icon_url)
        embed = view.get_embed()
        await ctx.send(embed=embed, view=view)

    @commands.hybrid_command(name="serverinfo", aliases=["si"], help="Shows detailed server information.")
    async def serverinfo(self, ctx: commands.Context):
        guild = ctx.guild
        is_premium = await is_guild_premium(guild.id)
        view = ServerInfoView(guild, ctx.author.id, is_premium)
        embed = view.get_embed()
        await ctx.send(embed=embed, view=view)

    @commands.hybrid_command(name="userinfo", aliases=["ui"], help="Shows information about a user.")
    async def userinfo(self, ctx: commands.Context, user: discord.Member = None):
        user = user or ctx.author
        view = UserInfoView(user, ctx.author.id)
        embed = view.get_embed()
        await ctx.send(embed=embed, view=view)

    @commands.hybrid_command(name="stats", aliases=["botinfo", "bi", "statistics"], help="Shows bot statistics.")
    async def stats(self, ctx: commands.Context):
        view = StatsView(self.bot, ctx.author.id)

        total_members = sum(g.member_count or 0 for g in self.bot.guilds)
        total_channels = sum(len(g.channels) for g in self.bot.guilds)
        gen_text = (
            f"> **Bot Name** : {self.bot.user}\n"
            f"> **Bot ID** : {self.bot.user.id}\n"
            f"> **Servers** : {len(self.bot.guilds)}\n"
            f"> **Users** : {total_members}\n"
            f"> **Channels** : {total_channels}\n"
            f"> **Commands Count** : {len(self.bot.commands)}\n"
            f"> **Latency** : {round(self.bot.latency * 1000)}ms"
        )
        embed = view.get_embed("General", gen_text)
        await ctx.send(embed=embed, view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(Extra2(bot))
