import discord
from discord.ext import commands
from typing import Optional
from core.Cog import Cog
from utils.Tools import getConfig
from utils.Tools import *
from utils.v2paginator import V2Paginator
from math import ceil




def _sep(visible=True):
    return discord.ui.Separator(visible=visible, spacing=discord.SeparatorSpacing.small)

def _thumb(url):
    return discord.ui.Thumbnail(discord.UnfurledMediaItem(url=url))

def _parse_cmds(raw_str):
    """Parse '`cmd1`, `cmd2`, ...' into ['cmd1', 'cmd2', ...]."""
    return [p.strip("`").strip() for p in raw_str.split("`, `") if p.strip("`").strip()]




MODULE_CATEGORIES = [
    ("Security", "Antinuke, AutoMod, and server protection modules.", "<:antinuke:1492772279552053370>"),
    ("Moderation", "Manage users, enforce rules, and configure channels.", "<:icons_moderation:1492772336376610819>"),
    ("Automation", "Automate your server and nickname management.", "<:icons_bots:1492772365149536437>"),
    ("General", "Essential utility commands for daily use.", "<:Sygen:1492772508045148202>"),
    ("Embed", "Create, manage, and send custom embeds.", "<:icons_edit:1492772820088918139>"),
    ("Roles", "Custom role, reaction role, and vanity assignments.", "<:Customroles:1492772616153595986>"),
    ("Voice", "Voice channel management and VoiceMaster.", "<:icons_voice:1492467681281048607>"),
    ("Social", "Dating, marriages, and anonymous confessions.", "<:sydate:1492467346298900692>"),
    ("Economy", "Virtual currency, farms, pets, and rewards.", "<:icons_money:1492466449585799180>"),
    ("Gaming", "Chat games, matchmaking, and counting.", "<:Sygame:1492772770134757496>"),
    ("Activity", "User tracking, milestones, and XP leveling.", "<:sycompass:1492467845294981170>"),
    ("Starboard", "Custom starboard and skullboard features.", "<:icons_star:1492772866314473494>"),
    ("Utility", "Media channels, and custom tags.", "<:Icons_utility:1492467904011304981>"),
    ("Greetings", "Welcome, farewell, boosters, and birthdays.", "<:sygreet:1492467791473676408>"),
    ("Community", "Giveaways, suggestions, and YouTube notifications.", "<:Sygift:1492772718259470396>"),
    ("Logging", "Tracks important server events in real time.", "<:icons_richpresence:1490347038376988776>"),
    ("Ticket", "Fully-featured ticket system for your server.", "<:icons_ticket:1492772568015568946>"),
    ("Verification", "Captcha and button verification system.", "<:icons_verify:1495402797883985963>"),
]

CATEGORY_OPTIONS = MODULE_CATEGORIES

COMMANDS_LIST = {
    "Security": {
        "Security": ["`antinuke`, `antinuke setup`, `antinuke disable`, `antinuke config`, `antinuke reset`, `antinuke autorecovery`, `antinuke logging`, `antinuke manage`, `antinuke punishment`, `antinuke limit`, `antinuke limits`, `antibetray`, `whitelist user`, `whitelist role`, `wl violations`, `wl violations list`, `wl violations info`, `wl violations reset`, `wl violations clear`, `panicmode`, `nightmode`, `cynicalmode`, `mainrole`, `mainrole add`, `mainrole remove`, `mainrole list`, `mainrole reset`, `admin`, `admin add`, `admin remove`, `admin list`, `admin reset`"],
        "AutoMod": ["`chatfilter`, `chatfilter whitelist`, `chatfilter logging`, `chatfilter reset`, `chatfilter rules`, `chatfilter wizard`"],
    },
    "Moderation": {
        "Moderation": ["`jail @user`, `jail setup`, `jail reset`, `jail list`, `unjail`, `mute`, `unmute`, `unmuteall`, `kick`, `warn`, `warns`, `clearwarns`, `warnconfig`, `warnconfig add punishment`, `warnconfig add role`, `warnconfig remove`, `warnconfig list`, `warnrole`, `warnrole add`, `warnrole remove`, `warnrole list`, `warnalert`, `warnalert channel`, `warnalert message`, `warnalert enable`, `warnalert disable`, `warnalert reset`, `warnalert show`, `warnalert variables`, `ban`, `unban`, `nick`, `setprefix`, `clear`, `clear all`, `clear bots`, `clear embeds`, `clear files`, `clear mentions`, `clear images`, `clear contains`, `clear reactions`, `clear user`, `clear emoji`, `role`, `role humans`, `role bots`, `nuke`, `lock`, `unlock`, `hide`, `unhide`, `unbanall`, `hideall`, `unhideall`, `rolecolor`, `roleicon`, `steal`, `addsticker`"],
        "ModNotes": ["`note`, `note add`, `note list`, `note delete`, `note clear`, `note search`, `flag`, `unflag`, `flagged`, `flaginfo`"],
        "Channel Config": ["`antibot`, `antibot add`, `antibot config`, `antibot log`, `antibot log remove`, `antibot log set`, `antibot remove`, `chatban`, `chatban add`, `chatban list`, `chatban remove`, `reactban`, `reactban add`, `reactban list`, `reactban remove`, `vcban`, `vcban add`, `vcban list`, `vcban remove`"],
    },
    "Automation": {
        "Automation": ["`autoreact`, `autoreact add`, `autoreact remove`, `autoreact edit`, `autoreact enable`, `autoreact disable`, `autoreact toggle`, `autoreact show`, `autoreact ignore`, `autoreact ignore add`, `autoreact ignore remove`, `autoreact ignore reset`, `autoreact ignore show`, `autoresponder`, `autoresponder add`, `autoresponder remove`, `autoresponder edit`, `autoresponder enable`, `autoresponder disable`, `autoresponder list`, `autoresponder info`, `autorole`, `autorole config`, `autorole humans`, `autorole humans add`, `autorole humans remove`, `autorole humans config`, `autorole bots`, `autorole bots add`, `autorole bots remove`, `autorole bots config`"],
        "AutoNick": ["`autonick`, `autonickjoin`, `autonickjoin view`, `autonickjoin prefix add`, `autonickjoin prefix reset`, `autonickjoin prefix enable`, `autonickjoin prefix disable`, `autonickjoin suffix add`, `autonickjoin suffix reset`, `autonickjoin suffix enable`, `autonickjoin suffix disable`, `autonickjoin resetall`, `autonickrole`, `autonickrole list`, `autonickrole prefix add`, `autonickrole prefix reset`, `autonickrole prefix enable`, `autonickrole prefix disable`, `autonickrole suffix add`, `autonickrole suffix reset`, `autonickrole suffix enable`, `autonickrole suffix disable`, `autonickrole resetall`"],
    },
    "General": {
        "General": ["`afk`, `avatar`, `banner`, `servericon`, `membercount`, `poll`, `hack`, `token`, `users`, `wizz`, `rickroll`, `hash`, `snipe`, `users`, `list boosters`, `list inrole`, `list emojis`, `list bots`, `list admins`, `list invoice`, `list mods`, `list early`, `list activedeveloper`, `list createpos`, `list roles`, `ignore`, `ignore channel add`, `ignore channel remove`, `ignore channel show`, `ignore user add`, `ignore user remove`, `ignore user show`, `ignore bypass add`, `ignore bypass show`, `ignore bypass remove`, `stats`, `steal`, `snipe`, `invite`, `serverinfo`, `userinfo`, `roleinfo`, `boostcount`, `unbanall`, `joined-at`, `ping`, `github`, `vcinfo`, `channelinfo`, `badges`, `banner user`, `banner server`, `permissions`, `timer`, `premium activate`, `prime deactivate`"],
    },
    "Embed": {
        "Embed": ["`embed`, `embed guide`, `embed create`, `embed edit`, `embed show`, `embed delete`, `embed send`, `embed import`, `embed export`"],
    },
    "Roles": {
        "CustomRole": ["`setup`, `setup reqrole`, `setup create`, `setup delete`, `setup list`, `setup config`, `setup reset`, `setup staff`, `setup girl`, `setup friend`, `setup vip`, `setup guest`, `staff`, `girl`, `friend`, `vip`, `guest`"],
        "ReactionRole": ["`reactionrole`, `reactionrole add`, `reactionrole remove`, `reactionrole list`"],
        "RoleModule": ["`vanityroles`, `vanityroles setup`, `vanityroles config`, `vanityroles mode`, `vanityroles toggle`, `tagrole`, `tagrole setup`, `tagrole config`, `tagrole reset`, `tagrole toggle`, `tagrole mode`"],
    },
    "Voice": {
        "Voice": ["`voice`, `voice ban`, `voice kick`, `voice kickall`, `voice mute`, `voice muteall`, `voice unmute`, `voice unmuteall`, `voice deafen`, `voice deafenall`, `voice undeafen`, `voice undeafenall`, `voice pull`, `voice moveall`, `voice invite`, `voice request`, `vcrole`, `vcrole set`, `vcrole show`, `vcrole config`"],
        "VoiceMaster": ["`voicemaster setup`, `voicemaster reset`, `voicemaster config`, `voicemaster default`, `voicemaster default limit`, `voicemaster default bitrate`, `voicemaster default region`"],
    },
    "Social": {
        "Dating": ["`dating`, `dating profile`, `dating setup`, `dating bio`, `dating gender`, `dating age`, `dating lookingfor`, `dating interests`, `dating deleteprofile`, `marry`, `divorce`, `married`, `marriageinfo`, `anniversary`, `vow`, `coupleinfo`, `couplename`, `marriages`, `remarry`, `crush`, `crushreveal`, `crushlist`, `confesslove`, `loveletter`, `loveletters`, `flirt`, `rizz`, `friendzone`, `date`, `datenight`, `datehistory`, `dategift`, `datemood`, `blinddate`, `speeddate`, `dateidea`, `gift`, `gifts`, `gifttop`, `rose`, `chocolate`, `serenade`, `lovebomb`, `breakupsong`, `compatibility`, `lovetest`, `horoscope`, `pickup`, `wouldyourather`, `lovequote`, `love8ball`, `shiplb`, `adopt`, `disown`, `children`, `family`, `dating block`, `dating unblock`, `dating resetall`"],
        "Confessions": ["`confession`, `confessions`, `confess`, `confession reply`, `confession setup`, `confession log`, `confession ban`, `confession unban`, `confession sendpanel`"],
    },
    "Economy": {
        "Economy": ["`ecoguide`, `bal`, `deposit`, `withdraw`, `beg`, `daily`, `weekly`, `pay`, `rob`, `crime`, `baltop`, `addbal`, `removebal`, `setbal`, `jobs`, `buyjob`, `removejob`, `myjobs`, `work`, `gamble`, `coinflip`, `slots`, `blackjack`, `pet`, `pet shop`, `pet buy`, `pet info`, `pet feed`, `pet play`, `pet train`, `pet rename`, `pet clean`, `pet heal`, `pet release`, `pet battle`, `pet leaderboard`, `petlist`, `farm`, `farm shop`, `buyseed`, `plant`, `water`, `harvest`, `fertilize`, `sellcrop`, `farm expand`, `farm inv`, `tractor buy`, `tractor use`, `farm leaderboard`, `inventory`, `shop`, `buy`, `sell`, `use`, `giveitem`, `crafting`, `craft`, `trade`, `iteminfo`, `lootbox`, `business`, `business start`, `business info`, `business collect`, `business upgrade`, `business hire`, `business fire`, `business rename`, `business close`, `stocks`, `stockbuy`, `stocksell`, `crypto`, `cryptobuy`, `cryptosell`"],
    },
    "Gaming": {
        "Entertainment": ["`chess`, `tic-tac-toe`, `rps`, `lights-out`, `wordle`, `2048`, `memory-game`, `number-slider`, `battleship`, `connect-four`, `8ball`, `dice`, `iq`, `gayrate`, `simprate`, `ship`, `hug`, `cuddle`, `kiss`, `slap`, `poke`, `punch`, `kill`, `tease`, `tickle`, `bite`, `pat`, `peck`, `highfive`, `baka`, `stare`, `thumbsup`, `wink`, `wave`, `yeet`, `bonk`, `kick`, `handhold`, `lick`, `dance`, `blush`, `cry`, `happy`, `smug`, `cringe`, `mydog`, `image`, `lesbian`, `chutiya`, `tharki`, `horny`, `cute`, `gif`, `iplookup`, `weather`, `fakeban`, `ngif`, `truth`, `dare`, `translate`"],
        "Counting": ["`counting`, `counting setup`, `counting disable`, `counting channel`, `counting failrole`, `counting passrole`, `counting math`, `counting hardmode`, `counting autodelete`, `counting allowmulti`, `counting reacttick`, `counting reactcross`, `counting resetcount`, `counting restore`, `counting resetstats`, `counting current`, `counting highscore`, `counting personalbest`, `counting leaderboard`, `counting stats`, `counting ruiner`"],
    },
    "Activity": {
        "Tracking": ["`msgtrack enable`, `msgtrack disable`, `msgstats`, `leaderboard messages`, `leaderboard dailymessages`, `leaderboard weeklymessages`, `addmessages`, `removemessages`, `clearmsgs`, `resetmymessages`, `blacklistchannel`, `unblacklistchannel`, `blacklistedchannels`, `blacklistcategory`, `unblacklistcategory`, `blacklistedcategories`, `setmessagerole`, `unsetmessagerole`, `viewmessageroles`, `invitetrack enable`, `invitetrack disable`, `invites`, `inviter`, `invited`, `inviteinfo`, `inviteleaderboard total`, `inviteleaderboard regular`, `inviteleaderboard fake`, `inviteleaderboard left`, `addinvites`, `removeinvites`, `clearinvites`, `resetmyinvites`, `setaltthreshold`, `unsetaltthreshold`, `setinviterole`, `unsetinviterole`, `viewinviteroles`, `voicetrack enable`, `voicetrack disable`, `vcstats`, `voiceleaderboard`, `dailyvoice`, `weeklyvoice`, `addvctime`, `reducevctime`, `clearvoice`, `resetmyvoice`"],
        "Leveling": ["`level`, `level enable`, `level disable`, `level channel`, `level announce`, `level config`, `level reset`, `level role`, `level role add`, `level role remove`, `level role list`, `level ignore`, `level ignore channel`, `level ignore role`, `level unignore`, `level unignore channel`, `level unignore role`, `level boost`, `level boost channel`, `level boost role`, `level unboost`, `level unboost channel`, `level unboost role`, `level stack`, `level rate`, `level maxlevel`, `level noxprole`, `rank`, `xpleaderboard`, `givexp`, `removexp`, `setlevel`, `resetxp`"],
    },
    "Starboard": {
        "Starboard": ["`starboard`, `starboard setup`, `starboard config`, `starboard reset`, `starboard limit`, `starboard emoji`, `starboard selfstar`, `starboard nsfw`, `starboard embed color`, `starboard embed ping`, `starboard embed reply`, `starboard ignore channel add`, `starboard ignore channel remove`, `starboard ignore channel reset`, `starboard ignore channel list`, `starboard ignore role add`, `starboard ignore role remove`, `starboard ignore role reset`, `starboard ignore role list`, `starboard ignore user add`, `starboard ignore user remove`, `starboard lock`, `starboard unlock`, `starboard remove`, `starboard force`, `starboard recount`, `starboard stats`, `starboard top`, `starboard random`"],
        "Skullboard": ["`skullboard`, `skullboard setup`, `skullboard config`, `skullboard reset`, `skullboard limit`, `skullboard selfskull`, `skullboard nsfw`, `skullboard embed color`, `skullboard embed ping`, `skullboard embed reply`, `skullboard ignore channel add`, `skullboard ignore channel remove`, `skullboard ignore channel reset`, `skullboard ignore channel list`, `skullboard ignore role add`, `skullboard ignore role remove`, `skullboard ignore role reset`, `skullboard ignore role list`, `skullboard ignore user add`, `skullboard ignore user remove`, `skullboard lock`, `skullboard unlock`, `skullboard remove`, `skullboard force`, `skullboard recount`, `skullboard stats`, `skullboard top`, `skullboard random`"],
    },
    "Utility": {
        "Tags": ["`tag`, `tag create`, `tag edit`, `tag delete`, `tag list`, `tag info`, `tag alias`, `tag removealias`, `tag search`, `tag top`, `tag claim`, `tag transfer`, `tag raw`, `tag all`, `tag purge`, `tag random`, `tag count`, `sticky`, `sticky add`, `sticky remove`, `sticky edit`, `sticky list`, `sticky clear`, `reminder`, `reminder list`, `reminder delete`, `reminder clear`"],
        "Media": ["`media`, `media add`, `media remove`, `media list`, `media bypass`, `media bypass user add`, `media bypass user remove`, `media bypass user list`, `media bypass role add`, `media bypass role remove`, `media bypass role list`, `mediaa`"],
    },
    "Greetings": {
        "Greetings": ["`greet`, `greet create`, `greet delete`, `greet enable`, `greet disable`, `greet config`, `greet edit`, `greet test`, `greet channel`, `greet channel set`, `greet channel reset`, `greet autodelete`, `greet autodelete enable`, `farewell`, `farewell setup`, `farewell reset`, `farewell config`, `farewell preview`, `farewell variables`, `farewell toggle`, `farewell import`, `farewell export`, `farewell test`, `farewell edit`, `joindm`, `joindm setup`, `joindm edit`, `joindm import`, `joindm export`, `joindm config`, `joindm reset`, `joindm toggle`"],
        "BoostMessage": ["`boost`, `boost setup`, `boost edit`, `boost channel`, `boost channel reset`, `boost role`, `boost role reset`, `boost enable`, `boost disable`, `boost config`, `boost test`, `boost reset`, `boost variables`, `boost delete`, `boost delete reset`"],
        "Birthday": ["`bday`, `birthday`, `bday set`, `bday remove`, `bday view`, `bday upcoming`, `bday channel`, `bday role`, `bday message`, `bday config`"],
    },
    "Community": {
        "Giveaways": ["`gstart`, `gcreate`, `gdrop`, `gend`, `greroll`, `glist`"],
        "Suggestions": ["`suggest`, `suggestion`, `suggestion setup`, `suggestion channel`, `suggestion logchannel`, `suggestion managerrole`, `suggestion anonymous`, `suggestion dmnotify`, `suggestion config`, `suggestion reset`, `suggestion approve`, `suggestion deny`, `suggestion consider`, `suggestion implement`, `suggestion delete`, `suggestion info`"],
        "YouTube": ["`youtube`, `yt add`, `yt remove`, `yt list`, `yt message`, `yt role`"],
    },
    "Logging": {
        "Logging": ["`logging setup`, `logging cleanup`, `logging enable`, `logging channel`, `logging status`, `logging disable`"],
    },
    "Ticket": {
        "Ticket": ["`ticket`, `ticket sendpanel`, `ticket paneldelete`, `ticket add`, `ticket remove`, `ticket close`, `ticket reopen`, `ticket claim`, `ticket transcript`, `ticket delete`, `ticket setup`"],
    },
    "Verification": {
        "Verification": ["`verify`, `verify setup`, `verify mode`, `verify message`, `verify logchannel`, `verify sendpanel`, `verify enable`, `verify disable`, `verify config`, `verify reset`, `verify stats`, `verify user`, `verify unverify`"],
    },
}

COG_DESCRIPTIONS = {
    "Security": "Antinuke, AutoMod, and server protection modules.",
    "Moderation": "Manage users, enforce rules, and configure channels.",
    "Automation": "Automate your server and nickname management.",
    "General": "Essential utility commands for daily use.",
    "Embed": "Create, manage, and send custom embeds.",
    "Roles": "Custom role, reaction role, and vanity assignments.",
    "Voice": "Voice channel management and VoiceMaster.",
    "Social": "Dating, marriages, and anonymous confessions.",
    "Economy": "Virtual currency, farms, pets, and rewards.",
    "Gaming": "Chat games, matchmaking, and counting.",
    "Activity": "User tracking, milestones, and XP leveling.",
    "Starboard": "Custom starboard and skullboard features.",
    "Utility": "Media channels, and custom tags.",
    "Greetings": "Welcome, farewell, boosters, and birthdays.",
    "Community": "Giveaways, suggestions, and YouTube notifications.",
    "Logging": "Tracks important server events in real time.",
    "Ticket": "Fully-featured ticket system for your server.",
    "Verification": "Captcha and button verification system.",
}





class HelpDropdown(discord.ui.Select):
    def __init__(self, help_view, categories, placeholder="Select a module..."):
        self.help_view = help_view
        options = [
            discord.SelectOption(label=label)
            for label, _, _ in categories
        ]
        super().__init__(placeholder=placeholder, min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        cog_name = self.values[0]

        categories_data = COMMANDS_LIST.get(cog_name, {})

        cat_view = CategoryLayoutView(
            self.help_view.ctx, self.help_view.bot, self.help_view.prefix,
            cog_name, categories_data,
        )
        await interaction.response.send_message(view=cat_view, ephemeral=True)


class HelpView(discord.ui.View):

    def __init__(self, ctx, bot, prefix, timeout=120):
        super().__init__(timeout=timeout)
        self.ctx = ctx
        self.bot = bot
        self.prefix = prefix
        self.message = None

        bot_avatar = bot.user.avatar.url if bot.user.avatar else bot.user.default_avatar.url
        bot_id = bot.user.id
        author_avatar = ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url

        self.embed = discord.Embed(
            description=(
                f"> Use the **menu below** to view the commands\n"
                f"> Click [**here**](https://discord.com/api/oauth2/authorize?client_id={bot_id}&permissions=8&scope=bot%20applications.commands) to invite **{bot.user.name}** to your server.\n"
                f"> You can use **{prefix}help [command]** to view a command."
            ),
            color=0x2b2d31,
        )
        self.embed.set_author(name=f"{ctx.author.name} · Synapse Menu", icon_url=author_avatar)
        self.embed.set_thumbnail(url=bot_avatar)
        self.embed.add_field(
            name="Information",
            value=(
                f"> My **prefix** for this **server** is `{prefix}`\n"
                f"> You can use the **dropdown** given **below** to see **various commands**"
            ),
            inline=False,
        )
        self.embed.add_field(
            name="Useful Links",
            value=(
                f"> [Support Server](https://dsc.gg/astrex-dev)\n"
                f"> [Invite Me](https://discord.com/api/oauth2/authorize?client_id={bot_id}&permissions=8&scope=bot%20applications.commands)\n"
                f"> Website? Coming Soon.."
            ),
            inline=False,
        )
        self.embed.set_footer(text="Powered by duracell..!!", icon_url=bot_avatar)

        self.add_item(HelpDropdown(self, MODULE_CATEGORIES, placeholder="Your modules are concealed here"))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(
                "Um, Looks like you are not the author of the command...", ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        for item in self.children:
            if hasattr(item, 'disabled'):
                item.disabled = True
        try:
            if self.message:
                await self.message.edit(view=self)
        except Exception:
            pass



class CategoryLayoutView(discord.ui.LayoutView):
    """Category command list — Components V2 layout."""

    def __init__(self, ctx, bot, prefix, cog_name, categories_data, timeout=120):
        super().__init__(timeout=timeout)
        self.ctx = ctx
        self.bot = bot
        self.prefix = prefix
        self.cog_name = cog_name
        self.message = None

        cog_desc = COG_DESCRIPTIONS.get(cog_name, "No description available.")

        elements = [
            discord.ui.TextDisplay(f"### {cog_name}\n-# {cog_desc}"),
            _sep()
        ]

        if categories_data:
            valid_items = []
            for sub_group, cmds_raw in categories_data.items():
                if cmds_raw and cmds_raw[0]:
                    parsed = _parse_cmds(cmds_raw[0])
                    if parsed:
                        valid_items.append((sub_group, "`" + "`, `".join(parsed) + "`"))

            for i, (sub_group, cmd_text) in enumerate(valid_items):
                text = (
                    f"**__{sub_group} Commands__**\n"
                    f"> {cmd_text}\n"
                )
                elements.append(discord.ui.TextDisplay(text))
                if i < len(valid_items) - 1:
                    elements.append(_sep())
        else:
            elements.append(discord.ui.TextDisplay("> No commands found.\n"))

        elements.append(_sep())
        elements.append(discord.ui.TextDisplay(f"-# Use `{prefix}help <command>` for detailed usage."))

        container = discord.ui.Container(*elements, accent_color=0x2b2d31)
        self.add_item(container)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(
                "Um, Looks like you are not the author of the command...", ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        for item in self.children:
            if hasattr(item, 'disabled'):
                item.disabled = True
            if hasattr(item, 'children'):
                for child in item.children:
                    if hasattr(child, 'disabled'):
                        child.disabled = True
        try:
            if self.message:
                await self.message.edit(view=self)
        except Exception:
            pass



class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.help_menu_cd = commands.CooldownMapping.from_cooldown(1, 5, commands.BucketType.user)
        self.bot.help_cmd_cd = commands.CooldownMapping.from_cooldown(1, 4, commands.BucketType.user)


    async def send_group_help_auto(self, ctx: commands.Context, group: commands.Group):
        subcmds = list(group.commands)
        if not subcmds:
            return await ctx.send("This group has no subcommands.")

        prefix = ctx.clean_prefix
        pages = []
        all_cmd_names = ", ".join([cmd.name for cmd in subcmds])

        chunk_size = 4
        chunks = [subcmds[i:i + chunk_size] for i in range(0, len(subcmds), chunk_size)]

        for i, chunk in enumerate(chunks):
            page = [
                discord.ui.TextDisplay(f"**{group.qualified_name.capitalize()} Commands [{len(subcmds)}]**\n```\n<..> Required | [...] Optional\n```"),
                _sep(),
            ]

            for index, cmd in enumerate(chunk):
                desc = cmd.help or cmd.short_doc or "No description provided."
                usage = f"{prefix}{cmd.qualified_name} {cmd.signature or ''}".strip()

                text = (
                    f"> `{cmd.qualified_name}`\n"
                    f"<:1spacer:1469251392924549294><:rightarrow:1469267754409529394> {desc}\n"
                    f"<:1spacer:1469251392924549294><:rightarrow:1469267754409529394> `{usage}`"
                )
                page.append(discord.ui.TextDisplay(text))
                if index < len(chunk) - 1:
                    page.append(_sep(visible=False))

            page.extend([
                _sep(),
                discord.ui.TextDisplay(f"-# Page {i + 1}/{len(chunks)} • Requested by {ctx.author.name}"),
            ])
            pages.append(page)

        view = V2Paginator(pages, author_id=ctx.author.id)
        msg = await ctx.send(view=view)
        view.message = msg

    @commands.hybrid_command(description="Get Help with the bot's commands or modules", aliases=["h", "commands"])
    @ignore_check()
    @blacklist_check()
    async def help(self, ctx: commands.Context, *, command: Optional[str] = None):
        data = await getConfig(ctx.guild.id)
        prefix = data["prefix"]

        if command is None:
            retry_after = self.bot.help_menu_cd.get_bucket(ctx.message).update_rate_limit()
            if retry_after:
                embed = discord.Embed(
                    description=f"<:timeout:1470401370782695536> Slow down! You can use the help menu again in **{round(retry_after, 1)}s**.",
                    color=0x2b2d31,
                )
                return await ctx.send(embed=embed, delete_after=8)

            view = HelpView(ctx, self.bot, prefix)
            msg = await ctx.send(embed=view.embed, view=view)
            view.message = msg
            return

        retry_after = self.bot.help_cmd_cd.get_bucket(ctx.message).update_rate_limit()
        if retry_after:
            embed = discord.Embed(
                description=f"<:timeout:1470401370782695536> Slow down! You can use command help again in **{round(retry_after, 1)}s**.",
                color=0x2b2d31,
            )
            return await ctx.send(embed=embed, delete_after=8)

        cmd = self.bot.get_command(command)
        if not cmd:
            embed = discord.Embed(
                description=f"<:Lund:1464624797374873611> No command or group named **`{command}`** exists.",
                color=0x2b2d31,
            )
            return await ctx.send(embed=embed)

        if isinstance(cmd, commands.Group):
            help_cog = ctx.bot.get_cog("Help")
            return await help_cog.send_group_help_auto(ctx, cmd)

        signature = f"{prefix}{cmd.qualified_name} {cmd.signature}"
        aliases = ", ".join(cmd.aliases) if cmd.aliases else "None"

        perms = []
        for check in cmd.checks:
            name = getattr(check, '__qualname__', '') or ''
            if 'has_permissions' in name:
                if hasattr(check, '__closure__') and check.__closure__:
                    for cell in check.__closure__:
                        try:
                            val = cell.cell_contents
                            if isinstance(val, dict):
                                perms.extend(
                                    k.replace("_", " ").title() for k, v in val.items() if v
                                )
                        except ValueError:
                            pass
        perms_str = ", ".join(perms) if perms else "No special permissions"

        view = discord.ui.LayoutView(timeout=60)
        container = discord.ui.Container(
            discord.ui.TextDisplay(f"### Command: {cmd.qualified_name}\n-# {cmd.help or 'No description.'}"),
            _sep(),
            discord.ui.TextDisplay(
                f"**<:SynapseUsage:1487700535120363561> Usage**\n<:1spacer:1469251392924549294><:rightarrow:1469267754409529394>`{signature}`\n\n"
                f"**<:SynaspeDesc:1487700565852164217> Aliases**\n<:1spacer:1469251392924549294><:rightarrow:1469267754409529394>{aliases}\n\n"
                f"**<:SynapseAlias:1487700509199568916> Permissions**\n<:1spacer:1469251392924549294><:rightarrow:1469267754409529394>{perms_str}"
            ),
            accent_color=0x2b2d31,
        )
        view.add_item(container)
        return await ctx.send(view=view)


async def setup(client):
    client.remove_command("help")
    await client.add_cog(Help(client))
