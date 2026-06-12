import discord
from discord.ext import commands
import aiosqlite
import json
import os

DB_PATH = os.path.join("database", "boost.db")


class VariableReplacer:
    """Replace placeholders in boost messages with real data."""

    def __init__(self, member: discord.Member):
        self.member = member
        self.guild = member.guild

    def replace(self, text: str) -> str:
        if not text:
            return text

        g = self.guild
        m = self.member
        owner = g.owner

        replacements = {
            "{user}":               str(m),
            "{user_id}":            str(m.id),
            "{user_name}":          m.name,
            "{user_tag}":           str(m),
            "{user_avatar}":        m.display_avatar.url,
            "{user_avatar_png}":    m.display_avatar.with_format("png").url if m.avatar else m.default_avatar.url,
            "{user_mention}":       m.mention,
            "{server}":             g.name,
            "{server_id}":          str(g.id),
            "{server_membercount}": str(g.member_count),
            "{server_icon}":        g.icon.url if g.icon else "",
            "{server_icon_png}":    g.icon.with_format("png").url if g.icon else "",
            "{server_banner}":      g.banner.url if g.banner else "",
            "{server_banner_png}":  g.banner.with_format("png").url if g.banner else "",
            "{boost_count}":        str(g.premium_subscription_count),
            "{boost_tier}":         str(g.premium_tier),
            "{guild_owner}":        str(owner) if owner else "Unknown",
            "{guild_owner_id}":     str(owner.id) if owner else "0",
            "{guild_owner_mention}": owner.mention if owner else "",
        }

        for key, val in replacements.items():
            text = text.replace(key, val)
        return text


class BoostEvents(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def send_boost_message(self, member: discord.Member, cfg: dict, test_channel=None):
        """Build and send the boost announcement. Used by both the event and `boost test`."""
        config = json.loads(cfg["config_json"]) if isinstance(cfg["config_json"], str) else cfg["config_json"]
        mode = cfg["mode"]
        replacer = VariableReplacer(member)

        del_kwargs = {"delete_after": cfg["delete_after"]} if cfg.get("delete_after") and cfg["delete_after"] > 0 else {}

        if test_channel:
            channel = test_channel
        else:
            channel = member.guild.get_channel(cfg.get("channel_id", 0))
            if not channel:
                return

        try:
            if mode == "message":
                msg = replacer.replace(config.get("message", ""))
                await channel.send(content=msg, **del_kwargs)

            elif mode == "embed":
                content = replacer.replace(config.get("message", "")) or None
                embed = discord.Embed(
                    title=replacer.replace(config.get("title")),
                    description=replacer.replace(config.get("description")),
                    color=config.get("color", 0xf47fff),
                )
                if config.get("author_name"):
                    embed.set_author(
                        name=replacer.replace(config["author_name"]),
                        icon_url=replacer.replace(config.get("author_icon", "")) or None,
                    )
                if config.get("footer_text"):
                    embed.set_footer(
                        text=replacer.replace(config["footer_text"]),
                        icon_url=replacer.replace(config.get("footer_icon", "")) or None,
                    )
                if config.get("image"):
                    embed.set_image(url=replacer.replace(config["image"]))
                if config.get("thumbnail"):
                    embed.set_thumbnail(url=replacer.replace(config["thumbnail"]))
                for field in config.get("fields", []):
                    embed.add_field(
                        name=replacer.replace(field.get("name", "")),
                        value=replacer.replace(field.get("value", "")),
                        inline=field.get("inline", False),
                    )

                await channel.send(content=content, embed=embed, **del_kwargs)
        except discord.Forbidden:
            pass
        except Exception as e:
            print(f"[BoostEvents] Error sending boost message in {member.guild.id}: {e}")

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.premium_since is not None or after.premium_since is None:
            return

        guild = after.guild

        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM boost_config WHERE guild_id = ?", (guild.id,)) as cur:
                row = await cur.fetchone()

        if not row:
            return
        cfg = dict(row)

        if not cfg["is_enabled"]:
            return

        if cfg["mode"] and cfg["channel_id"]:
            await self.send_boost_message(after, cfg)

        if cfg["role_id"]:
            role = guild.get_role(cfg["role_id"])
            if role and role not in after.roles:
                try:
                    await after.add_roles(role, reason="Synapse Boost Reward")
                except discord.Forbidden:
                    pass
                except discord.HTTPException:
                    pass


async def setup(bot):
    await bot.add_cog(BoostEvents(bot))
