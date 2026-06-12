import discord
from discord.ext import commands
import random
from games.tictactoe import Tictactoe
from games.wordle import Wordle
from games.typeracer import TypeRacer
from games.connect_four import ConnectFour
from games.battleship import BattleShip
from games.country_guess import CountryGuesser
from games.twenty_48 import Twenty48
from games.reaction_test import ReactionGame

E_TICK  = "<:emoji_1769867605256:1467155817726873650>"
E_CROSS = "<:emoji_1769867589372:1467155751456735326>"
E_EXCL  = "<:SynapseExcl:1477234549552320634>"
EMBED_COLOR = 0x2b2d31

class Games(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="dice", aliases=["roll", "diceroll"])
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def dice(self, ctx):
        roll = random.randint(1, 6)
        embed = discord.Embed(
            title="🎲 Dice Roll",
            description=f"You rolled a **{roll}**!",
            color=EMBED_COLOR
        )
        embed.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar.url)
        await ctx.reply(embed=embed)

    @commands.command(name="iq", aliases=["iqtest", "smartness"])
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def iq(self, ctx, user: discord.Member = None):
        user = user or ctx.author
        iq_num = random.randint(1, 250)
        embed = discord.Embed(
            title="🧠 IQ Test",
            description=f"{user.mention}'s IQ is **{iq_num}**.",
            color=EMBED_COLOR
        )
        embed.set_author(name=user.name, icon_url=user.display_avatar.url)
        await ctx.reply(embed=embed)

    @commands.command(name="gayrate", aliases=["gay", "howgay"])
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def gayrate(self, ctx, user: discord.Member = None):
        user = user or ctx.author
        rate = random.randint(0, 100)
        embed = discord.Embed(
            title="🏳️‍🌈 Gay Rate",
            description=f"{user.mention} is **{rate}%** gay.",
            color=EMBED_COLOR
        )
        embed.set_author(name=user.name, icon_url=user.display_avatar.url)
        await ctx.reply(embed=embed)

    @commands.command(name="simprate", aliases=["simp", "howsimp"])
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def simprate(self, ctx, user: discord.Member = None):
        user = user or ctx.author
        rate = random.randint(0, 100)
        embed = discord.Embed(
            title="🥺 Simp Rate",
            description=f"{user.mention} is **{rate}%** simp.",
            color=EMBED_COLOR
        )
        embed.set_author(name=user.name, icon_url=user.display_avatar.url)
        await ctx.reply(embed=embed)




async def setup(bot):
    await bot.add_cog(Games(bot))
