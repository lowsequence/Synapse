from typing import Union
import discord
from discord.ext import commands
from database import ColorDatabase

def get_embed_color(user_id: str, ctx: Union[discord.Interaction, commands.Context]) -> discord.Color:
    db = ColorDatabase()
    color_value = db.get_color(user_id)

    if color_value is None:
        return discord.Color(0x2b2d31) 
    elif isinstance(color_value, int):
        return discord.Color(color_value)  
    elif color_value == "random":
        return discord.Color.random()
    elif color_value == "top":
        if isinstance(ctx, commands.Context):
            return ctx.author.top_role.color
        elif isinstance(ctx, discord.Interaction):
            user = ctx.user
            if ctx.guild:
                member = ctx.guild.get_member(user.id)
                if member and member.top_role:
                    return member.top_role.color

    return discord.Color(0x2b2d31)  