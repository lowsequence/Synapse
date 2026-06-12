import discord, aiosqlite, asyncio, os
from discord.ext import commands
from discord import ui
from utils.Tools import blacklist_check, ignore_check

DB     = "database/automod.db"
JAILDB = "database/jail.db"
CLR    = 0x2b2d31
CHK    = "<:emoji_1769867605256:1467155817726873650>"
ERR    = "<:emoji_1769867589372:1467155751456735326>"
ICN    = "<:synapse_automod:1471871079256424550>"
LDG    = "<a:Loadixd:1469568214169288890>"
BAR    = "<:syanapse_bar:1471870923241029753>"

def _sep(v=True):
    return discord.ui.Separator(visible=v, spacing=discord.SeparatorSpacing.small)

MODULES = [
    ("anticaps",     "Anti-Caps",      "config_anticaps"),
    ("antiinvite",   "Anti-Invite",    "config_antiinvite"),
    ("antilink",     "Anti-Link",      "config_antilink"),
    ("antinsfw",     "Anti-NSFW",      "config_antinsfw"),
    ("antiswear",    "Anti-Swear",     "config_antiswear"),
    ("antispam",     "Anti-Spam",      "config_antispam"),
    ("antiemoji",    "Anti-Emoji",     "config_antiemoji"),
    ("antimassline", "Anti-MassLine",  "config_antimassline"),
]
MOD_MAP = {k: (l, t) for k, l, t in MODULES}

FINETUNE = {
    "english": ["fuck","fucker","fucking","motherfucker","bitch","shit","ass","asshole","cunt","dick",
                "pussy","whore","slut","bastard","nigger","nigga","faggot","retard","twat","wanker",
                "cock","prick","dumbass","dipshit","jackass","douche","rape","rapist","tits","blowjob"],
    "hindi":   ["madarchod","bhenchod","chutiya","gandu","randi","mc","bc","bsdk","loda","lund",
                "gaand","haramzada","kaminey","bhosda","chut","lawde","behenchod","bhadwa","suar"],
    "spanish": ["puta","puto","mierda","cabron","pendejo","cono","joder","gilipollas","zorra",
                "perra","pinche","culero","verga","marica","cojon"],
    "french":  ["merde","putain","salope","connard","bite","encule","foutre","pede","batard",
                "pute","nique","fdp","ntm","bordel"],
    "german":  ["scheisse","arschloch","schlampe","hure","wichser","fotze","verdammt","fick",
                "ficken","hurensohn","drecksack","pisser"],
    "russian": ["suka","blyat","pizdec","huy","ebat","mudak","pidor","shlukha","zalupa","eban"],
}

# ── DB Helpers ─────────────────────────────────────────────────────────────────
async def _row(table, guild_id):
    async with aiosqlite.connect(DB) as db:
        c = await db.execute(f"SELECT * FROM {table} WHERE guild_id=?", (guild_id,))
        row = await c.fetchone()
        if not row:
            await db.execute(f"INSERT OR IGNORE INTO {table} (guild_id) VALUES (?)", (guild_id,))
            await db.commit()
            c = await db.execute(f"SELECT * FROM {table} WHERE guild_id=?", (guild_id,))
            row = await c.fetchone()
        return row

async def _set(table, field, val, guild_id):
    async with aiosqlite.connect(DB) as db:
        await db.execute(f"UPDATE {table} SET {field}=? WHERE guild_id=?", (val, guild_id))
        await db.commit()

async def _jail_ok(guild_id):
    if not os.path.exists(JAILDB): return False
    async with aiosqlite.connect(JAILDB) as db:
        try:
            c = await db.execute("SELECT role_id FROM jail_config WHERE guild_id=?", (guild_id,))
            r = await c.fetchone()
            return r is not None and r[0] is not None
        except: return False

# ── Modals ─────────────────────────────────────────────────────────────────────
class TimeoutModal(ui.Modal, title="Set Timeout Duration"):
    duration = ui.TextInput(label="Timeout (seconds)", placeholder="e.g. 300 for 5 minutes", min_length=1, max_length=6)
    def __init__(self, cog, ctx, key):
        super().__init__(); self.cog = cog; self.ctx = ctx; self.key = key
    async def on_submit(self, i):
        try: s = int(self.duration.value); assert s >= 0
        except: return await i.response.send_message("Enter a valid positive integer.", ephemeral=True)
        await _set(MOD_MAP[self.key][1], "timeout", s, i.guild.id)
        v = await ModuleView.build(self.cog, self.ctx, self.key)
        await i.response.edit_message(view=v); v.message = i.message

class CapsModal(ui.Modal, title="Anti-Caps Settings"):
    minlen = ui.TextInput(label="Min message length to check", placeholder="10", default="10")
    thresh = ui.TextInput(label="Caps threshold % (1–100)", placeholder="70", default="70")
    def __init__(self, cog, ctx, key):
        super().__init__(); self.cog = cog; self.ctx = ctx; self.key = key
    async def on_submit(self, i):
        try: ml, th = int(self.minlen.value), int(self.thresh.value); assert 1 <= th <= 100
        except: return await i.response.send_message("Threshold must be 1–100.", ephemeral=True)
        async with aiosqlite.connect(DB) as db:
            await db.execute("UPDATE config_anticaps SET minlength=?,threshold=? WHERE guild_id=?", (ml, th, i.guild.id))
            await db.commit()
        v = await ModuleView.build(self.cog, self.ctx, self.key)
        await i.response.edit_message(view=v); v.message = i.message

class SpamModal(ui.Modal, title="Anti-Spam Settings"):
    limit   = ui.TextInput(label="Message limit per 5 seconds", placeholder="5", default="5")
    strikes = ui.TextInput(label="Strikes before punishment", placeholder="3", default="3")
    def __init__(self, cog, ctx, key):
        super().__init__(); self.cog = cog; self.ctx = ctx; self.key = key
    async def on_submit(self, i):
        try: lim, st = int(self.limit.value), int(self.strikes.value); assert lim > 0 and st > 0
        except: return await i.response.send_message("Enter positive integers.", ephemeral=True)
        async with aiosqlite.connect(DB) as db:
            await db.execute("UPDATE config_antispam SET msg_limit=?,strikes=? WHERE guild_id=?", (lim, st, i.guild.id))
            await db.commit()
        v = await ModuleView.build(self.cog, self.ctx, self.key)
        await i.response.edit_message(view=v); v.message = i.message

class EmojiModal(ui.Modal, title="Anti-Emoji Settings"):
    val = ui.TextInput(label="Max emojis per message", placeholder="10", default="10")
    def __init__(self, cog, ctx, key):
        super().__init__(); self.cog = cog; self.ctx = ctx; self.key = key
    async def on_submit(self, i):
        try: n = int(self.val.value); assert n >= 1
        except: return await i.response.send_message("Enter a positive integer.", ephemeral=True)
        await _set("config_antiemoji", "max_emojis", n, i.guild.id)
        v = await ModuleView.build(self.cog, self.ctx, self.key)
        await i.response.edit_message(view=v); v.message = i.message

class MasslineModal(ui.Modal, title="Anti-MassLine Settings"):
    val = ui.TextInput(label="Max lines per message", placeholder="10", default="10")
    def __init__(self, cog, ctx, key):
        super().__init__(); self.cog = cog; self.ctx = ctx; self.key = key
    async def on_submit(self, i):
        try: n = int(self.val.value); assert n >= 1
        except: return await i.response.send_message("Enter a positive integer.", ephemeral=True)
        await _set("config_antimassline", "max_lines", n, i.guild.id)
        v = await ModuleView.build(self.cog, self.ctx, self.key)
        await i.response.edit_message(view=v); v.message = i.message

class SwearAddModal(ui.Modal, title="Add Swear Words"):
    words = ui.TextInput(label="Words (comma-separated)", placeholder="word1, word2, word3",
                         style=discord.TextStyle.paragraph, max_length=500)
    def __init__(self, cog, ctx):
        super().__init__(); self.cog = cog; self.ctx = ctx
    async def on_submit(self, i):
        ws = [w.strip().lower() for w in self.words.value.split(",") if w.strip()]
        added = 0
        async with aiosqlite.connect(DB) as db:
            c = await db.execute("SELECT word FROM swear_words WHERE guild_id=?", (i.guild.id,))
            existing = {r[0] for r in await c.fetchall()}
            for w in ws:
                if w and w not in existing:
                    await db.execute("INSERT INTO swear_words VALUES (?,?)", (i.guild.id, w)); added += 1
            await db.commit()
        v = await SwearView.build(self.cog, self.ctx, notice=f"{CHK} Added **{added}** word(s).")
        await i.response.edit_message(view=v); v.message = i.message

class SwearRemoveModal(ui.Modal, title="Remove Swear Word"):
    word = ui.TextInput(label="Word to remove", min_length=1, max_length=50)
    def __init__(self, cog, ctx):
        super().__init__(); self.cog = cog; self.ctx = ctx
    async def on_submit(self, i):
        async with aiosqlite.connect(DB) as db:
            await db.execute("DELETE FROM swear_words WHERE guild_id=? AND word=?", (i.guild.id, self.word.value.lower()))
            await db.commit()
        v = await SwearView.build(self.cog, self.ctx, notice=f"{CHK} Removed `{self.word.value.lower()}`.")
        await i.response.edit_message(view=v); v.message = i.message

class AllowedAddModal(ui.Modal):
    val = ui.TextInput(label="Enter value", min_length=1, max_length=100)
    def __init__(self, cog, ctx, key):
        lbl = "Invite Code" if key == "antiinvite" else "Link Pattern"
        super().__init__(title=f"Add Allowed {lbl}")
        self.val.label = "Code / Pattern"
        self.cog = cog; self.ctx = ctx; self.key = key
    async def on_submit(self, i):
        tbl = "allowed_invites" if self.key == "antiinvite" else "allowed_links"
        fld = "code" if self.key == "antiinvite" else "pattern"
        async with aiosqlite.connect(DB) as db:
            await db.execute(f"INSERT INTO {tbl} (guild_id,{fld}) VALUES (?,?)", (i.guild.id, self.val.value.strip()))
            await db.commit()
        v = await AllowedView.build(self.cog, self.ctx, self.key)
        await i.response.edit_message(view=v); v.message = i.message

class AllowedRemoveModal(ui.Modal):
    val = ui.TextInput(label="Value to remove", min_length=1, max_length=100)
    def __init__(self, cog, ctx, key):
        super().__init__(title=f"Remove Allowed {'Code' if key == 'antiinvite' else 'Pattern'}")
        self.cog = cog; self.ctx = ctx; self.key = key
    async def on_submit(self, i):
        tbl = "allowed_invites" if self.key == "antiinvite" else "allowed_links"
        fld = "code" if self.key == "antiinvite" else "pattern"
        async with aiosqlite.connect(DB) as db:
            await db.execute(f"DELETE FROM {tbl} WHERE guild_id=? AND {fld}=?", (i.guild.id, self.val.value.strip()))
            await db.commit()
        v = await AllowedView.build(self.cog, self.ctx, self.key)
        await i.response.edit_message(view=v); v.message = i.message

class WLRemoveModal(ui.Modal, title="Remove from Whitelist"):
    entry = ui.TextInput(label="ID to remove", placeholder="e.g. 123456789012345678", min_length=15, max_length=20)
    def __init__(self, cog, ctx, type_str):
        super().__init__(); self.cog = cog; self.ctx = ctx; self.type_str = type_str
    async def on_submit(self, i):
        try: tid = int(self.entry.value)
        except: return await i.response.send_message("Invalid ID.", ephemeral=True)
        async with aiosqlite.connect(DB) as db:
            await db.execute("DELETE FROM whitelist WHERE guild_id=? AND target_id=? AND type=?", (i.guild.id, tid, self.type_str))
            await db.commit()
        v = await WLTypeView.build(self.cog, self.ctx, self.type_str)
        await i.response.edit_message(view=v); v.message = i.message

# ── Selects ────────────────────────────────────────────────────────────────────
class ModuleSelect(ui.Select):
    def __init__(self, cog, ctx):
        self.cog = cog; self.ctx = ctx
        opts = [discord.SelectOption(label=l, value=k, description=f"Configure the {l} filter") for k, l, _ in MODULES]
        super().__init__(placeholder="Select a module to configure...", options=opts)
    async def callback(self, i):
        v = await ModuleView.build(self.cog, self.ctx, self.values[0])
        await i.response.edit_message(view=v); v.message = i.message

class PunishmentSelect(ui.Select):
    def __init__(self, cog, ctx, key):
        self.cog = cog; self.ctx = ctx; self.key = key
        opts = [
            discord.SelectOption(label="None",    value="none",    description="Only delete the message", emoji="<:synone:1490340133361291478>"),
            discord.SelectOption(label="Timeout", value="timeout", description="Temporarily mute",        emoji="<:symute:1490340241708683275>"),
            discord.SelectOption(label="Kick",    value="kick",    description="Kick from the server",    emoji="<:sykick:1490340186188546059>"),
            discord.SelectOption(label="Ban",     value="ban",     description="Permanently ban",         emoji="<:syban:1490340143142277221>"),
            discord.SelectOption(label="Jail",    value="jail",    description="Move to jail role",       emoji="<:syjail:1490340287099306014>"),
        ]
        super().__init__(placeholder="Set punishment...", options=opts)
    async def callback(self, i):
        ptype = self.values[0]
        if ptype == "jail" and not await _jail_ok(i.guild.id):
            return await i.response.send_message("Jail is not configured. Use `jail setup` first.", ephemeral=True)
        await _set(MOD_MAP[self.key][1], "punishment", ptype, i.guild.id)
        v = await ModuleView.build(self.cog, self.ctx, self.key)
        await i.response.edit_message(view=v); v.message = i.message

class FineTuneSelect(ui.Select):
    def __init__(self, cog, ctx):
        self.cog = cog; self.ctx = ctx
        opts = [discord.SelectOption(label=lang.title(), value=lang, description=f"Add preset {lang} words") for lang in FINETUNE]
        super().__init__(placeholder="Add preset word list by language...", options=opts)
    async def callback(self, i):
        lang = self.values[0]
        added = 0
        async with aiosqlite.connect(DB) as db:
            c = await db.execute("SELECT word FROM swear_words WHERE guild_id=?", (i.guild.id,))
            existing = {r[0] for r in await c.fetchall()}
            for w in FINETUNE[lang]:
                if w not in existing:
                    await db.execute("INSERT INTO swear_words VALUES (?,?)", (i.guild.id, w)); added += 1
            await db.commit()
        v = await SwearView.build(self.cog, self.ctx, notice=f"{CHK} Added **{added}** preset `{lang}` words.")
        await i.response.edit_message(view=v); v.message = i.message

class WLTypeSelect(ui.Select):
    def __init__(self, cog, ctx):
        self.cog = cog; self.ctx = ctx
        opts = [
            discord.SelectOption(label="Users",    value="user",    description="Whitelist specific users",    emoji="<:icons_user:1490341664848478270>"),
            discord.SelectOption(label="Roles",    value="role",    description="Whitelist specific roles",    emoji="<:icons_roles:1490341868381143165>"),
            discord.SelectOption(label="Channels", value="channel", description="Whitelist specific channels", emoji="<:icons_channel:1490341836496310272>"),
        ]
        super().__init__(placeholder="Choose whitelist type...", options=opts)
    async def callback(self, i):
        v = await WLTypeView.build(self.cog, self.ctx, self.values[0])
        await i.response.edit_message(view=v); v.message = i.message

# ── View base ──────────────────────────────────────────────────────────────────
class _BaseView(discord.ui.LayoutView):
    def __init__(self, ctx, timeout=120):
        super().__init__(timeout=timeout)
        self.ctx = ctx
        self.message = None

    async def interaction_check(self, i: discord.Interaction) -> bool:
        if i.user.id != self.ctx.author.id:
            err_view = discord.ui.LayoutView(timeout=10)
            err_view.add_item(discord.ui.Container(
                discord.ui.TextDisplay(
                    f"{ERR} **Not your panel!**\n"
                    f"-# Only <@{self.ctx.author.id}> can interact with this."
                ),
                accent_color=0xe74c3c,
            ))
            await i.response.send_message(view=err_view, ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        # Disable every button/select in every ActionRow (top-level or inside Container)
        for item in self.children:
            if hasattr(item, "disabled"):
                item.disabled = True
            if hasattr(item, "children"):
                for child in item.children:
                    if hasattr(child, "disabled"):
                        child.disabled = True
        try:
            if self.message:
                await self.message.edit(view=self)
        except Exception:
            pass

# ── MainView ───────────────────────────────────────────────────────────────────
class MainView(_BaseView):
    def __init__(self, cog, ctx, lines, avatar):
        super().__init__(ctx)
        self.cog = cog

        status_block = "\n".join(lines)
        container = discord.ui.Container(
            discord.ui.Section(
                discord.ui.TextDisplay(f"## {ICN} AutoMod Control Panel"),
                discord.ui.TextDisplay("-# Select a module from the dropdown to configure it."),
                accessory=discord.ui.Thumbnail(discord.UnfurledMediaItem(url=avatar)),
            ),
            _sep(),
            discord.ui.TextDisplay(status_block),
            _sep(False),
            accent_color=CLR,
        )
        self.add_item(container)
        self.add_item(discord.ui.ActionRow(ModuleSelect(cog, ctx)))

        rst_btn = discord.ui.Button(label="Reset All", style=discord.ButtonStyle.danger, custom_id="main_rst")
        rst_btn.callback = self._confirm_reset
        self.add_item(discord.ui.ActionRow(rst_btn))

    @classmethod
    async def build(cls, cog, ctx):
        lines = []
        async with aiosqlite.connect(DB) as db:
            for key, label, table in MODULES:
                c = await db.execute(f"SELECT enabled, punishment FROM {table} WHERE guild_id=?", (ctx.guild.id,))
                row = await c.fetchone()
                icon = CHK if (row and row[0]) else ERR
                pun  = (row[1] if row else None) or "none"
                lines.append(f"{BAR} {icon} **{label}** — `{pun}`")
        return cls(cog, ctx, lines, cog.bot.user.display_avatar.url)

    async def _confirm_reset(self, i):
        v = ResetConfirmView(self.cog, self.ctx)
        container = discord.ui.Container(
            discord.ui.TextDisplay(f"## Reset AutoMod"),
            _sep(),
            discord.ui.TextDisplay(
                f"> This will wipe **all** module configurations, swear words, allowed invites and links.\n"
                f"> Whitelist and logging data will be **preserved**.\n\n"
                f"Are you sure?"
            ),
            _sep(False),
            accent_color=0xe74c3c,
        )
        v.add_item(container)
        confirm = discord.ui.Button(label="Confirm Reset", style=discord.ButtonStyle.danger, custom_id="rst_yes")
        confirm.callback = v._do_reset
        cancel = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.secondary, custom_id="rst_no")
        cancel.callback = v._cancel
        v.add_item(discord.ui.ActionRow(confirm, cancel))
        await i.response.send_message(view=v, ephemeral=True)

# ── ResetConfirmView ───────────────────────────────────────────────────────────
class ResetConfirmView(_BaseView):
    def __init__(self, cog, ctx, original_message=None):
        super().__init__(ctx); self.cog = cog
        self.original_message = original_message

    async def _do_reset(self, i):
        tables = ["config_anticaps","config_antispam","config_antinsfw","config_antiswear",
                  "config_antilink","config_antiinvite","config_antiemoji","config_antimassline"]
        async with aiosqlite.connect(DB) as db:
            for t in tables: await db.execute(f"DELETE FROM {t} WHERE guild_id=?", (i.guild.id,))
            for t in ["swear_words","allowed_invites","allowed_links"]:
                await db.execute(f"DELETE FROM {t} WHERE guild_id=?", (i.guild.id,))
            await db.commit()

        # Update ephemeral message
        v = discord.ui.LayoutView(timeout=10)
        done = discord.ui.Container(
            discord.ui.TextDisplay(f"## {CHK} AutoMod Reset"),
            _sep(),
            discord.ui.TextDisplay("> All module configurations have been cleared.\n> Whitelist and logging preserved."),
            accent_color=CLR,
        )
        v.add_item(done)
        await i.response.edit_message(view=v)

        # Update the original main panel
        if self.original_message:
            try:
                main_v = await MainView.build(self.cog, self.ctx)
                await self.original_message.edit(view=main_v)
                main_v.message = self.original_message
            except Exception: pass

    async def _cancel(self, i):
        v = discord.ui.LayoutView(timeout=10)
        cancel_ctr = discord.ui.Container(
            discord.ui.TextDisplay(f"## ❌ Reset Cancelled"),
            accent_color=0xe74c3c,
        )
        v.add_item(cancel_ctr)
        await i.response.edit_message(view=v)

# ── ModuleView ─────────────────────────────────────────────────────────────────
class ModuleView(_BaseView):
    def __init__(self, cog, ctx, key, row, avatar):
        super().__init__(ctx); self.cog = cog; self.key = key
        label, table = MOD_MAP[key]

        enabled = bool(row[1]) if row else False
        pun     = (row[3] if row else None) or "none"
        tmo     = row[4] if row else 0
        status  = f"{CHK} Enabled" if enabled else f"{ERR} Disabled"
        toggle_label = "Disable" if enabled else "Enable"
        toggle_style = discord.ButtonStyle.danger if enabled else discord.ButtonStyle.success

        extra = ""
        if key == "anticaps"     and row and len(row) > 5: extra = f"\n{BAR} **Min Length:** `{row[5]}` chars\n{BAR} **Threshold:** `{row[6]}%`"
        elif key == "antispam"   and row and len(row) > 5: extra = f"\n{BAR} **Msg Limit:** `{row[5]}` per 5s\n{BAR} **Strikes:** `{row[6]}`"
        elif key == "antiemoji"  and row and len(row) > 5: extra = f"\n{BAR} **Max Emojis:** `{row[5]}`"
        elif key == "antimassline" and row and len(row) > 5: extra = f"\n{BAR} **Max Lines:** `{row[5]}`"

        has_list  = key in ("antiinvite", "antilink")
        has_words = key == "antiswear"

        body = (
            f"{BAR} **Status:** {status}\n"
            f"{BAR} **Punishment:** `{pun}`\n"
            f"{BAR} **Timeout:** `{tmo}s`"
            f"{extra}"
        )

        container = discord.ui.Container(
            discord.ui.Section(
                discord.ui.TextDisplay(f"## {label}"),
                discord.ui.TextDisplay("-# Configure this AutoMod module."),
                accessory=discord.ui.Thumbnail(discord.UnfurledMediaItem(url=avatar)),
            ),
            _sep(),
            discord.ui.TextDisplay(body),
            _sep(False),
            accent_color=CLR,
        )
        self.add_item(container)
        self.add_item(discord.ui.ActionRow(PunishmentSelect(cog, ctx, key)))

        tog = discord.ui.Button(label=toggle_label, style=toggle_style, custom_id="mod_tog")
        tog.callback = self._toggle
        tmo_btn = discord.ui.Button(label="Set Timeout", emoji="<:timeout:1470401370782695536>", style=discord.ButtonStyle.secondary, custom_id="mod_tmo")
        tmo_btn.callback = self._set_timeout
        row2 = [tog, tmo_btn]

        if key in ("anticaps","antispam","antiemoji","antimassline"):
            sett = discord.ui.Button(label="Settings", emoji="<:sygear:1490345728776736778>", style=discord.ButtonStyle.secondary, custom_id="mod_sett")
            sett.callback = self._settings
            row2.append(sett)

        if has_words:
            wb = discord.ui.Button(label="Manage Words", emoji="<:text2:1490345769532784733>", style=discord.ButtonStyle.secondary, custom_id="mod_words")
            wb.callback = self._open_swear
            row2.append(wb)

        if has_list:
            lb = discord.ui.Button(label="Allowed List", emoji="<:icons_linkadd:1490345689736151080>", style=discord.ButtonStyle.secondary, custom_id="mod_allowed")
            lb.callback = self._open_allowed
            row2.append(lb)

        back = discord.ui.Button(label="Back", emoji="<:icons_back:1490343437071814758>", style=discord.ButtonStyle.secondary, custom_id="mod_back")
        back.callback = self._back
        self.add_item(discord.ui.ActionRow(*row2))
        self.add_item(discord.ui.ActionRow(back))

    @classmethod
    async def build(cls, cog, ctx, key):
        _, table = MOD_MAP[key]
        row = await _row(table, ctx.guild.id)
        return cls(cog, ctx, key, row, cog.bot.user.display_avatar.url)

    async def _toggle(self, i):
        _, table = MOD_MAP[self.key]
        row = await _row(table, i.guild.id)
        await _set(table, "enabled", 0 if row[1] else 1, i.guild.id)
        v = await ModuleView.build(self.cog, self.ctx, self.key)
        await i.response.edit_message(view=v); v.message = i.message

    async def _set_timeout(self, i):
        await i.response.send_modal(TimeoutModal(self.cog, self.ctx, self.key))

    async def _settings(self, i):
        modal_map = {"anticaps": CapsModal, "antispam": SpamModal, "antiemoji": EmojiModal, "antimassline": MasslineModal}
        await i.response.send_modal(modal_map[self.key](self.cog, self.ctx, self.key))

    async def _open_swear(self, i):
        v = await SwearView.build(self.cog, self.ctx)
        await i.response.edit_message(view=v); v.message = i.message

    async def _open_allowed(self, i):
        v = await AllowedView.build(self.cog, self.ctx, self.key)
        await i.response.edit_message(view=v); v.message = i.message

    async def _back(self, i):
        v = await MainView.build(self.cog, self.ctx)
        await i.response.edit_message(view=v); v.message = i.message

# ── SwearView ──────────────────────────────────────────────────────────────────
PER_PAGE = 25

class SwearView(_BaseView):
    def __init__(self, cog, ctx, words, page=0, notice=""):
        super().__init__(ctx); self.cog = cog; self.words = words; self.page = page

        total = len(words)
        total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
        page = max(0, min(page, total_pages - 1))  # clamp
        self.page = page
        page_words = words[page * PER_PAGE:(page + 1) * PER_PAGE]

        if page_words:
            word_block = " ".join(f"`{w}`" for w in page_words)
        else:
            word_block = "*No words added yet. Use **Add Words** to get started.*"

        body = f"{BAR} **Total:** `{total}` words — Page `{page + 1}/{total_pages}`\n\n{word_block}"
        if notice: body = f"{notice}\n\n" + body

        container = discord.ui.Container(
            discord.ui.Section(
                discord.ui.TextDisplay("## <:text2:1490345769532784733> Anti-Swear — Word List"),
                discord.ui.TextDisplay("-# Manage your server's blacklisted words."),
                accessory=discord.ui.Thumbnail(discord.UnfurledMediaItem(url=cog.bot.user.display_avatar.url)),
            ),
            _sep(),
            discord.ui.TextDisplay(body),
            _sep(False),
            accent_color=CLR,
        )
        self.add_item(container)
        self.add_item(discord.ui.ActionRow(FineTuneSelect(cog, ctx)))

        add_b  = discord.ui.Button(label="Add Words",   emoji="<:icons_add:1490343943177506948>",     style=discord.ButtonStyle.success,   custom_id="sw_add")
        add_b.callback = self._add
        rem_b  = discord.ui.Button(label="Remove Word", emoji="<:icons_removed:1490343967152406569>", style=discord.ButtonStyle.danger,    custom_id="sw_rem")
        rem_b.callback = self._remove
        clr_b  = discord.ui.Button(label="Clear All",  emoji="<:Trash:1462771196885074002>",         style=discord.ButtonStyle.danger,    custom_id="sw_clr")
        clr_b.callback = self._clear
        back_b = discord.ui.Button(label="Back",        emoji="<:icons_back:1490343437071814758>",    style=discord.ButtonStyle.secondary, custom_id="sw_back")
        back_b.callback = self._back
        self.add_item(discord.ui.ActionRow(add_b, rem_b, clr_b, back_b))

        if total_pages > 1:
            prev_b = discord.ui.Button(label="Previous", style=discord.ButtonStyle.secondary,
                                       custom_id="sw_prev", disabled=(page == 0))
            prev_b.callback = self._prev
            next_b = discord.ui.Button(label="Next", style=discord.ButtonStyle.secondary,
                                       custom_id="sw_next", disabled=(page >= total_pages - 1))
            next_b.callback = self._next
            self.add_item(discord.ui.ActionRow(prev_b, next_b))

    @classmethod
    async def build(cls, cog, ctx, page=0, notice=""):
        async with aiosqlite.connect(DB) as db:
            c = await db.execute("SELECT word FROM swear_words WHERE guild_id=? ORDER BY word", (ctx.guild.id,))
            words = [r[0] for r in await c.fetchall()]
        return cls(cog, ctx, words, page, notice)

    async def _add(self, i):    await i.response.send_modal(SwearAddModal(self.cog, self.ctx))
    async def _remove(self, i): await i.response.send_modal(SwearRemoveModal(self.cog, self.ctx))
    async def _clear(self, i):
        async with aiosqlite.connect(DB) as db:
            await db.execute("DELETE FROM swear_words WHERE guild_id=?", (i.guild.id,))
            await db.commit()
        v = await SwearView.build(self.cog, self.ctx, notice=f"{CHK} All words cleared.")
        await i.response.edit_message(view=v); v.message = i.message
    async def _prev(self, i):
        v = await SwearView.build(self.cog, self.ctx, page=self.page - 1)
        await i.response.edit_message(view=v); v.message = i.message
    async def _next(self, i):
        v = await SwearView.build(self.cog, self.ctx, page=self.page + 1)
        await i.response.edit_message(view=v); v.message = i.message
    async def _back(self, i):
        v = await ModuleView.build(self.cog, self.ctx, "antiswear")
        await i.response.edit_message(view=v); v.message = i.message

# ── AllowedView ────────────────────────────────────────────────────────────────
class AllowedView(_BaseView):
    def __init__(self, cog, ctx, key, items, notice=""):
        super().__init__(ctx); self.cog = cog; self.key = key
        label, _ = MOD_MAP[key]
        kind = "Invite Codes" if key == "antiinvite" else "Link Patterns"
        preview = ", ".join(f"`{it}`" for it in items[:10]) + ("..." if len(items) > 10 else "") or "`—`"
        body = f"{BAR} **Total:** `{len(items)}`\n{BAR} **List:** {preview}"
        if notice: body = f"{notice}\n\n" + body

        container = discord.ui.Container(
            discord.ui.TextDisplay(f"## <:icons_linkadd:1490345689736151080> {label} — Allowed {kind}"),
            _sep(),
            discord.ui.TextDisplay(body),
            _sep(False),
            accent_color=CLR,
        )
        self.add_item(container)
        add_b  = discord.ui.Button(label="Add",    emoji="<:icons_add:1490343943177506948>", style=discord.ButtonStyle.success,   custom_id="al_add")
        add_b.callback = self._add
        rem_b  = discord.ui.Button(label="Remove", emoji="<:icons_removed:1490343967152406569>", style=discord.ButtonStyle.danger,    custom_id="al_rem")
        rem_b.callback = self._remove
        clr_b  = discord.ui.Button(label="Clear",  emoji="<:Trash:1462771196885074002>", style=discord.ButtonStyle.danger,    custom_id="al_clr")
        clr_b.callback = self._clear
        back_b = discord.ui.Button(label="Back",   emoji="<:icons_back:1490343437071814758>", style=discord.ButtonStyle.secondary, custom_id="al_back")
        back_b.callback = self._back
        self.add_item(discord.ui.ActionRow(add_b, rem_b, clr_b, back_b))

    @classmethod
    async def build(cls, cog, ctx, key, notice=""):
        tbl = "allowed_invites" if key == "antiinvite" else "allowed_links"
        fld = "code" if key == "antiinvite" else "pattern"
        async with aiosqlite.connect(DB) as db:
            c = await db.execute(f"SELECT {fld} FROM {tbl} WHERE guild_id=?", (ctx.guild.id,))
            items = [r[0] for r in await c.fetchall()]
        return cls(cog, ctx, key, items, notice)

    async def _add(self, i):    await i.response.send_modal(AllowedAddModal(self.cog, self.ctx, self.key))
    async def _remove(self, i): await i.response.send_modal(AllowedRemoveModal(self.cog, self.ctx, self.key))
    async def _clear(self, i):
        tbl = "allowed_invites" if self.key == "antiinvite" else "allowed_links"
        async with aiosqlite.connect(DB) as db:
            await db.execute(f"DELETE FROM {tbl} WHERE guild_id=?", (i.guild.id,))
            await db.commit()
        v = await AllowedView.build(self.cog, self.ctx, self.key, notice=f"{CHK} Cleared.")
        await i.response.edit_message(view=v); v.message = i.message
    async def _back(self, i):
        v = await ModuleView.build(self.cog, self.ctx, self.key)
        await i.response.edit_message(view=v); v.message = i.message

# ── WhitelistView ──────────────────────────────────────────────────────────────
class WhitelistView(_BaseView):
    def __init__(self, cog, ctx, counts, avatar):
        super().__init__(ctx); self.cog = cog
        body = (
            f"{BAR} <:icons_user:1490341664848478270> **Users:** `{counts['user']}`\n"
            f"{BAR} <:icons_roles:1490341868381143165> **Roles:** `{counts['role']}`\n"
            f"{BAR} <:icons_channel:1490341836496310272> **Channels:** `{counts['channel']}`"
        )
        container = discord.ui.Container(
            discord.ui.Section(
                discord.ui.TextDisplay("## <:WhitelistUser:1490346707244941364> Whitelist Manager"),
                discord.ui.TextDisplay("-# Select a type to view and manage entries."),
                accessory=discord.ui.Thumbnail(discord.UnfurledMediaItem(url=avatar)),
            ),
            _sep(),
            discord.ui.TextDisplay(body),
            _sep(False),
            accent_color=CLR,
        )
        self.add_item(container)
        self.add_item(discord.ui.ActionRow(WLTypeSelect(cog, ctx)))
        back_b = discord.ui.Button(label="Back", emoji="<:icons_back:1490343437071814758>", style=discord.ButtonStyle.secondary, custom_id="wl_back")
        back_b.callback = self._back
        self.add_item(discord.ui.ActionRow(back_b))

    @classmethod
    async def build(cls, cog, ctx):
        counts = {}
        async with aiosqlite.connect(DB) as db:
            for t in ("user","role","channel"):
                c = await db.execute("SELECT COUNT(*) FROM whitelist WHERE guild_id=? AND type=?", (ctx.guild.id, t))
                counts[t] = (await c.fetchone())[0]
        return cls(cog, ctx, counts, cog.bot.user.display_avatar.url)

    async def _back(self, i):
        v = await MainView.build(self.cog, self.ctx)
        await i.response.edit_message(view=v); v.message = i.message

# ── WLTypeView ─────────────────────────────────────────────────────────────────
class WLTypeView(_BaseView):
    def __init__(self, cog, ctx, type_str, entries):
        super().__init__(ctx); self.cog = cog; self.type_str = type_str
        label = {"user":"<:icons_user:1490341664848478270> Users","role":"<:icons_roles:1490341868381143165> Roles","channel":"<:icons_channel:1490341836496310272> Channels"}[type_str]
        fmt   = {"user": lambda x: f"<@{x}>", "role": lambda x: f"<@&{x}>", "channel": lambda x: f"<#{x}>"}[type_str]
        listed = "\n".join(f"{BAR} {fmt(e)} (`{e}`)" for e in entries[:15]) or f"{BAR} *No entries yet.*"
        if len(entries) > 15: listed += f"\n{BAR} *... and {len(entries)-15} more.*"

        container = discord.ui.Container(
            discord.ui.TextDisplay(f"## <:WhitelistUser:1490346707244941364> Whitelist — {label}"),
            _sep(),
            discord.ui.TextDisplay(listed),
            _sep(False),
            accent_color=CLR,
        )
        self.add_item(container)
        add_b  = discord.ui.Button(label="Add by ID",  emoji="<:icons_add:1490343943177506948>", style=discord.ButtonStyle.success,   custom_id="wlt_add")
        add_b.callback = self._add
        rem_b  = discord.ui.Button(label="Remove by ID",emoji="<:icons_removed:1490343967152406569>", style=discord.ButtonStyle.danger,    custom_id="wlt_rem")
        rem_b.callback = self._remove
        clr_b  = discord.ui.Button(label="Clear All",  emoji="<:Trash:1462771196885074002>", style=discord.ButtonStyle.danger,    custom_id="wlt_clr")
        clr_b.callback = self._clear
        back_b = discord.ui.Button(label="Back",       emoji="<:icons_back:1490343437071814758>", style=discord.ButtonStyle.secondary, custom_id="wlt_back")
        back_b.callback = self._back
        self.add_item(discord.ui.ActionRow(add_b, rem_b, clr_b, back_b))

    @classmethod
    async def build(cls, cog, ctx, type_str):
        async with aiosqlite.connect(DB) as db:
            c = await db.execute("SELECT target_id FROM whitelist WHERE guild_id=? AND type=?", (ctx.guild.id, type_str))
            entries = [r[0] for r in await c.fetchall()]
        return cls(cog, ctx, type_str, entries)

    async def _add(self, i):    await i.response.send_modal(WLAddModal(self.cog, self.ctx, self.type_str))
    async def _remove(self, i): await i.response.send_modal(WLRemoveModal(self.cog, self.ctx, self.type_str))
    async def _clear(self, i):
        async with aiosqlite.connect(DB) as db:
            await db.execute("DELETE FROM whitelist WHERE guild_id=? AND type=?", (i.guild.id, self.type_str))
            await db.commit()
        v = await WLTypeView.build(self.cog, self.ctx, self.type_str)
        await i.response.edit_message(view=v); v.message = i.message
    async def _back(self, i):
        v = await WhitelistView.build(self.cog, self.ctx)
        await i.response.edit_message(view=v); v.message = i.message

class WLAddModal(ui.Modal, title="Add to Whitelist"):
    entry = ui.TextInput(label="ID to add", placeholder="e.g. 123456789012345678", min_length=15, max_length=20)
    def __init__(self, cog, ctx, type_str):
        super().__init__(); self.cog = cog; self.ctx = ctx; self.type_str = type_str
    async def on_submit(self, i):
        try: tid = int(self.entry.value)
        except: return await i.response.send_message("Invalid ID.", ephemeral=True)
        async with aiosqlite.connect(DB) as db:
            await db.execute("INSERT INTO whitelist (guild_id, target_id, type) VALUES (?,?,?)", (i.guild.id, tid, self.type_str))
            await db.commit()
        v = await WLTypeView.build(self.cog, self.ctx, self.type_str)
        await i.response.edit_message(view=v); v.message = i.message

# ── LoggingView ────────────────────────────────────────────────────────────────
class LoggingView(_BaseView):
    def __init__(self, cog, ctx, webhook_url, avatar):
        super().__init__(ctx); self.cog = cog
        status  = f"{CHK} **Active**\n{BAR} Webhook configured." if webhook_url else f"{ERR} **Not set up.**\n{BAR} Select a channel below to enable logging."
        container = discord.ui.Container(
            discord.ui.Section(
                discord.ui.TextDisplay("## <:icons_richpresence:1490347038376988776> AutoMod Logging"),
                discord.ui.TextDisplay("-# Log all violations to a channel via webhook."),
                accessory=discord.ui.Thumbnail(discord.UnfurledMediaItem(url=avatar)),
            ),
            _sep(),
            discord.ui.TextDisplay(f"{BAR} **Status:** {status}"),
            _sep(False),
            accent_color=CLR,
        )
        self.add_item(container)

        ch_sel = discord.ui.ChannelSelect(placeholder="Select channel to setup / change logging...",
                                          channel_types=[discord.ChannelType.text])
        ch_sel.callback = self._setup
        self.add_item(discord.ui.ActionRow(ch_sel))

        rst_b  = discord.ui.Button(label="Reset Logging", emoji="<:Trash:1462771196885074002>", style=discord.ButtonStyle.danger,    custom_id="log_rst")
        rst_b.callback = self._reset
        back_b = discord.ui.Button(label="Back",          emoji="<:icons_back:1490343437071814758>", style=discord.ButtonStyle.secondary, custom_id="log_back")
        back_b.callback = self._back
        self.add_item(discord.ui.ActionRow(rst_b, back_b))

    @classmethod
    async def build(cls, cog, ctx):
        async with aiosqlite.connect(DB) as db:
            c = await db.execute("SELECT webhook_url FROM logging WHERE guild_id=?", (ctx.guild.id,))
            row = await c.fetchone()
        return cls(cog, ctx, row[0] if row else None, cog.bot.user.display_avatar.url)

    async def _setup(self, i):
        channel = self.children[-2].values[0]  
        async with aiosqlite.connect(DB) as db:
            c = await db.execute("SELECT webhook_url FROM logging WHERE guild_id=?", (i.guild.id,))
            existing = await c.fetchone()
        try:
            if existing:
                try:
                    import discord as _d
                    wh = _d.SyncWebhook.from_url(existing[0])
                    wh.delete()
                except: pass
                async with aiosqlite.connect(DB) as db:
                    await db.execute("DELETE FROM logging WHERE guild_id=?", (i.guild.id,))
                    await db.commit()
            wh = await channel.create_webhook(name="Synapse AutoMod")
            async with aiosqlite.connect(DB) as db:
                await db.execute("INSERT OR REPLACE INTO logging VALUES (?,?)", (i.guild.id, wh.url))
                await db.commit()
        except discord.Forbidden:
            return await i.response.send_message("I need `Manage Webhooks` permission in that channel.", ephemeral=True)
        v = await LoggingView.build(self.cog, self.ctx)
        await i.response.edit_message(view=v); v.message = i.message

    async def _reset(self, i):
        async with aiosqlite.connect(DB) as db:
            await db.execute("DELETE FROM logging WHERE guild_id=?", (i.guild.id,))
            await db.commit()
        v = await LoggingView.build(self.cog, self.ctx)
        await i.response.edit_message(view=v); v.message = i.message

    async def _back(self, i):
        v = await MainView.build(self.cog, self.ctx)
        await i.response.edit_message(view=v); v.message = i.message


class AutoMod(commands.Cog):
    """AutoMod — Interactive panel-based chat filter system."""
    def __init__(self, bot):
        self.bot = bot
        os.makedirs("database", exist_ok=True)

    def get_db(self): return aiosqlite.connect(DB)

    async def cog_load(self):
        async with self.get_db() as db:
            await db.execute("CREATE TABLE IF NOT EXISTS whitelist (guild_id INTEGER, target_id INTEGER, type TEXT)")
            for mod in ["anticaps","antispam","antinsfw","antiswear","antilink","antiinvite"]:
                schema = (f"CREATE TABLE IF NOT EXISTS config_{mod} "
                          f"(guild_id INTEGER PRIMARY KEY, enabled INTEGER DEFAULT 0, "
                          f"delete_msg INTEGER DEFAULT 1, punishment TEXT DEFAULT 'none', timeout INTEGER DEFAULT 0")
                if mod == "anticaps":  schema += ", minlength INTEGER DEFAULT 10, threshold INTEGER DEFAULT 70"
                elif mod == "antispam": schema += ", msg_limit INTEGER DEFAULT 5, strikes INTEGER DEFAULT 3"
                schema += ")"
                await db.execute(schema)
            await db.execute("CREATE TABLE IF NOT EXISTS config_antiemoji (guild_id INTEGER PRIMARY KEY, enabled INTEGER DEFAULT 0, delete_msg INTEGER DEFAULT 1, punishment TEXT DEFAULT 'none', timeout INTEGER DEFAULT 0, max_emojis INTEGER DEFAULT 10)")
            await db.execute("CREATE TABLE IF NOT EXISTS config_antimassline (guild_id INTEGER PRIMARY KEY, enabled INTEGER DEFAULT 0, delete_msg INTEGER DEFAULT 1, punishment TEXT DEFAULT 'none', timeout INTEGER DEFAULT 0, max_lines INTEGER DEFAULT 10)")
            await db.execute("CREATE TABLE IF NOT EXISTS swear_words (guild_id INTEGER, word TEXT)")
            await db.execute("CREATE TABLE IF NOT EXISTS allowed_invites (guild_id INTEGER, code TEXT)")
            await db.execute("CREATE TABLE IF NOT EXISTS allowed_links (guild_id INTEGER, pattern TEXT)")
            await db.execute("CREATE TABLE IF NOT EXISTS logging (guild_id INTEGER PRIMARY KEY, webhook_url TEXT)")
            await db.commit()

    @commands.group(name="chatfilter", aliases=["automod"], invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    async def chatfilter(self, ctx):
        """Open the AutoMod control panel."""
        v = await MainView.build(self, ctx)
        msg = await ctx.send(view=v)
        v.message = msg

    @chatfilter.command(name="whitelist", aliases=["wl"])
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    async def cf_whitelist(self, ctx):
        """Open the whitelist management panel."""
        v = await WhitelistView.build(self, ctx)
        msg = await ctx.send(view=v)
        v.message = msg

    @chatfilter.command(name="logging", aliases=["log"])
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    async def cf_logging(self, ctx):
        """Open the logging setup panel."""
        v = await LoggingView.build(self, ctx)
        msg = await ctx.send(view=v)
        v.message = msg

    @chatfilter.command(name="reset")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    async def cf_reset(self, ctx):
        """Reset all AutoMod configuration."""
        await ctx.invoke(self.chatfilter)

    @chatfilter.command(name="rules")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    async def cf_rules(self, ctx):
        """Show an overview of all active AutoMod rules."""
        lines = []
        async with self.get_db() as db:
            for key, label, table in MODULES:
                c = await db.execute(f"SELECT * FROM {table} WHERE guild_id=?", (ctx.guild.id,))
                row = await c.fetchone()
                if not row:
                    lines.append(f"{ERR} **{label}** — `not configured`"); continue
                icon = CHK if row[1] else ERR
                pun  = row[3] or "none"
                tmo  = row[4] or 0
                info = f"{icon} **{label}** — `{pun}` | timeout `{tmo}s`"
                if key == "anticaps"     and len(row) > 5: info += f" | min `{row[5]}` | threshold `{row[6]}%`"
                elif key == "antispam"   and len(row) > 5: info += f" | limit `{row[5]}` | strikes `{row[6]}`"
                elif key == "antiemoji"  and len(row) > 5: info += f" | max emojis `{row[5]}`"
                elif key == "antimassline" and len(row) > 5: info += f" | max lines `{row[5]}`"
                lines.append(info)
        view = discord.ui.LayoutView(timeout=60)
        view.add_item(discord.ui.Container(
            discord.ui.TextDisplay(f"## {ICN} AutoMod Rules Overview"),
            _sep(),
            discord.ui.TextDisplay("\n".join(lines)),
            accent_color=CLR,
        ))
        msg = await ctx.send(view=view)

    @chatfilter.command(name="wizard")
    @commands.has_permissions(administrator=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 300, commands.BucketType.guild)
    async def cf_wizard(self, ctx):
        """One-click setup: enable all modules with sensible defaults."""
        guild_id = ctx.guild.id
        tables = [t for _, _, t in MODULES]

        async def _step(text: str, done: list[str] = []):
            lines = [f"{CHK} {d}" for d in done] + [f"{LDG} **{text}**"]
            v = discord.ui.LayoutView(timeout=60)
            v.add_item(discord.ui.Container(
                discord.ui.Section(
                    discord.ui.TextDisplay(f"## {ICN} AutoMod Setup Wizard"),
                    discord.ui.TextDisplay("-# Please wait while we configure everything..."),
                    accessory=discord.ui.Thumbnail(discord.UnfurledMediaItem(url=self.bot.user.display_avatar.url)),
                ),
                _sep(),
                discord.ui.TextDisplay("\n".join(lines)),
                accent_color=CLR,
            ))
            await msg.edit(view=v)

        completed = []

        # Phase 1 — Setting up modules (send first step as initial message)
        def _build_step_view(text: str, done: list[str]) -> discord.ui.LayoutView:
            lines = [f"{CHK} {d}" for d in done] + [f"{LDG} **{text}**"]
            v = discord.ui.LayoutView(timeout=60)
            v.add_item(discord.ui.Container(
                discord.ui.Section(
                    discord.ui.TextDisplay(f"## {ICN} AutoMod Setup Wizard"),
                    discord.ui.TextDisplay("-# Please wait while we configure everything..."),
                    accessory=discord.ui.Thumbnail(discord.UnfurledMediaItem(url=self.bot.user.display_avatar.url)),
                ),
                _sep(),
                discord.ui.TextDisplay("\n".join(lines)),
                accent_color=CLR,
            ))
            return v

        msg = await ctx.send(view=_build_step_view("Setting up modules...", completed))
        await asyncio.sleep(1.2)
        async with self.get_db() as db:
            for _, _, table in MODULES:
                await db.execute(f"INSERT OR IGNORE INTO {table} (guild_id) VALUES (?)", (guild_id,))
                await db.execute(f"UPDATE {table} SET enabled=1, punishment='timeout', timeout=300 WHERE guild_id=?", (guild_id,))
            await db.commit()

        # Phase 2 — Configuring punishments
        completed.append("Modules set up")
        await msg.edit(view=_build_step_view("Configuring punishments...", completed))
        await asyncio.sleep(1.2)
        async with self.get_db() as db:
            await db.execute("UPDATE config_antiswear    SET punishment='none',    timeout=0   WHERE guild_id=?", (guild_id,))
            await db.execute("UPDATE config_anticaps     SET minlength=5,          threshold=70 WHERE guild_id=?", (guild_id,))
            await db.execute("UPDATE config_antispam     SET msg_limit=4,          strikes=3   WHERE guild_id=?", (guild_id,))
            await db.execute("UPDATE config_antiemoji    SET max_emojis=5                       WHERE guild_id=?", (guild_id,))
            await db.execute("UPDATE config_antimassline SET max_lines=6                        WHERE guild_id=?", (guild_id,))
            await db.commit()

        # Phase 3 — Fine-tuning swear words
        completed.append("Punishments configured")
        await msg.edit(view=_build_step_view("Fine-tuning swear words...", completed))
        await asyncio.sleep(1.4)
        async with self.get_db() as db:
            c = await db.execute("SELECT word FROM swear_words WHERE guild_id=?", (guild_id,))
            existing = {r[0] for r in await c.fetchall()}
            all_words = [w for words in FINETUNE.values() for w in words]
            for word in all_words:
                if word not in existing:
                    await db.execute("INSERT INTO swear_words VALUES (?,?)", (guild_id, word))
            await db.commit()

        # Phase 4 — Creating logging
        completed.append("Swear words fine-tuned")
        await msg.edit(view=_build_step_view("Creating logging...", completed))
        await asyncio.sleep(1.2)
        async with self.get_db() as db:
            c = await db.execute("SELECT webhook_url FROM logging WHERE guild_id=?", (guild_id,))
            has_logging = await c.fetchone()

        if not has_logging:
            try:
                # Private channel — only admins + bot can see it
                overwrites = {
                    ctx.guild.default_role: discord.PermissionOverwrite(view_channel=False),
                    ctx.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_webhooks=True),
                }
                # Also grant access to any roles with administrator permission
                for role in ctx.guild.roles:
                    if role.permissions.administrator:
                        overwrites[role] = discord.PermissionOverwrite(view_channel=True, read_message_history=True)

                log_channel = await ctx.guild.create_text_channel(
                    name="synapse-automod",
                    topic="AutoMod violation logs — managed by Synapse.",
                    overwrites=overwrites,
                )
                webhook = await log_channel.create_webhook(name="Synapse AutoMod")
                async with self.get_db() as db:
                    await db.execute("INSERT OR REPLACE INTO logging VALUES (?,?)", (guild_id, webhook.url))
                    await db.commit()
            except discord.Forbidden:
                pass  # Missing permissions — skip logging setup

        # Done — show setup complete info panel (no auto-transition)
        completed.append("Logging ready")
        await msg.edit(view=_build_step_view("Finalizing...", completed))
        await asyncio.sleep(0.8)

        prefix = ctx.clean_prefix
        done_view = discord.ui.LayoutView(timeout=30)
        done_view.add_item(discord.ui.Container(
            discord.ui.Section(
                discord.ui.TextDisplay(f"## {CHK} AutoMod is Ready!"),
                discord.ui.TextDisplay("-# Your server is now protected by Synapse AutoMod."),
                accessory=discord.ui.Thumbnail(discord.UnfurledMediaItem(url=self.bot.user.display_avatar.url)),
            ),
            _sep(),
            discord.ui.TextDisplay(
                f"**What was set up:**\n"
                f"{BAR} All **8 modules** enabled with smart defaults\n"
                f"{BAR} Punishments set to `timeout` (300s), except swear → `none`\n"
                f"{BAR} Swear word list pre-loaded with **6 language presets**\n"
                f"{BAR} Private logging channel `#synapse-automod` created\n"
            ),
            _sep(),
            discord.ui.TextDisplay(
                f"**How to configure AutoMod:**\n"
                f"{BAR} `{prefix}chatfilter` — Open the interactive control panel\n"
                f"{BAR} `{prefix}chatfilter whitelist` — Whitelist users, roles or channels\n"
                f"{BAR} `{prefix}chatfilter logging` — Change or reset the logging channel\n"
                f"{BAR} `{prefix}chatfilter rules` — View a summary of all active rules\n"
                f"{BAR} `{prefix}chatfilter reset` — Wipe all AutoMod configuration\n"
            ),
            _sep(),
            discord.ui.TextDisplay(
                f"**Tips:**\n"
                f"{BAR} Click any module in the panel dropdown to toggle it on/off, change its punishment, or adjust its threshold.\n"
                f"{BAR} Anti-Swear is set to `none` punishment — it will silently delete messages without punishing the user. Change it in the panel if you want stricter enforcement.\n"
                f"{BAR} All violating messages are **always deleted**, regardless of punishment setting.\n"
                f"{BAR} Use `{prefix}chatfilter whitelist` to exempt your staff roles from all filters."
            ),
            _sep(False),
            accent_color=0x2ecc71,
        ))
        await msg.edit(view=done_view)

async def setup(bot):
    await bot.add_cog(AutoMod(bot))
