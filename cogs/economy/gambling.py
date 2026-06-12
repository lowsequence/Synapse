import random
import discord
from discord.ext import commands

from utils.Tools import blacklist_check, ignore_check
from utils.eco_db import (
    init_db, ensure_user, get_wallet, add_wallet, set_cooldown
)

EMBED_COLOR = 0x2b2d31
E_OK  = "<:emoji_1769867605256:1467155817726873650>"
E_ERR = "<:emoji_1769867589372:1467155751456735326>"


def _fmt(n: int) -> str:
    return f"{n:,}"



SUITS = ["♠", "♥", "♦", "♣"]
RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]


def _new_deck() -> list:
    d = [f"{r}{s}" for s in SUITS for r in RANKS]
    random.shuffle(d)
    return d


def _hand_value(hand: list) -> int:
    value, aces = 0, 0
    for card in hand:
        r = card[:-1]
        if r in ("J", "Q", "K"):
            value += 10
        elif r == "A":
            aces += 1
            value += 11
        else:
            value += int(r)
    while value > 21 and aces:
        value -= 10
        aces -= 1
    return value


def _fmt_hand(hand: list) -> str:
    return "  ".join(f"`{c}`" for c in hand)



class BlackjackView(discord.ui.View):
    def __init__(self, ctx, bet: int, player: list, dealer: list, deck: list):
        super().__init__(timeout=60)
        self.ctx    = ctx
        self.bet    = bet
        self.player = player
        self.dealer = dealer
        self.deck   = deck
        self.message = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("Not your game!", ephemeral=True)
            return False
        return True

    def _build_embed(self, result_line: str = "", reveal: bool = False) -> discord.Embed:
        pv = _hand_value(self.player)
        dv = _hand_value(self.dealer)
        dealer_str = _fmt_hand(self.dealer) if reveal else f"`{self.dealer[0]}`  `??`"
        dealer_val = str(dv) if reveal else "?"
        desc = (
            f"**Your hand** — {pv}\n{_fmt_hand(self.player)}\n\n"
            f"**Dealer's hand** — {dealer_val}\n{dealer_str}"
        )
        if result_line:
            desc += f"\n\n{result_line}"
        return discord.Embed(description=desc, color=EMBED_COLOR, timestamp=discord.utils.utcnow())

    async def _resolve(self, interaction: discord.Interaction) -> None:
        while _hand_value(self.dealer) < 17:
            self.dealer.append(self.deck.pop())
        pv = _hand_value(self.player)
        dv = _hand_value(self.dealer)

        if dv > 21 or pv > dv:
            new_wallet = await add_wallet(self.ctx.author.id, self.bet)
            line = f"{E_OK} You win! ({pv} vs {dv}) **+{_fmt(self.bet)}** coins."
        elif pv < dv:
            new_wallet = await add_wallet(self.ctx.author.id, -self.bet)
            line = f"{E_ERR} Dealer wins. ({pv} vs {dv}) **-{_fmt(self.bet)}** coins."
        else:
            new_wallet = await get_wallet(self.ctx.author.id)
            line = "🤝 **Push** — bet returned."

        embed = self._build_embed(result_line=line, reveal=True)
        embed.set_author(
            name=f"{self.ctx.author.display_name} — Blackjack",
            icon_url=self.ctx.author.display_avatar.url,
        )
        embed.set_footer(text=f"Wallet: {_fmt(new_wallet)} coins • Synapse - Economy")
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()

    async def _bust(self, interaction: discord.Interaction) -> None:
        new_wallet = await add_wallet(self.ctx.author.id, -self.bet)
        pv   = _hand_value(self.player)
        line = f"{E_ERR} **Bust!** ({pv}) Lost **{_fmt(self.bet)}** coins."
        embed = self._build_embed(result_line=line, reveal=True)
        embed.set_author(
            name=f"{self.ctx.author.display_name} — Blackjack",
            icon_url=self.ctx.author.display_avatar.url,
        )
        embed.set_footer(text=f"Wallet: {_fmt(new_wallet)} coins • Synapse - Economy")
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.primary, emoji="🃏")
    async def hit_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.player.append(self.deck.pop())
        pv = _hand_value(self.player)
        if pv > 21:
            await self._bust(interaction)
        elif pv == 21:
            await self._resolve(interaction)
        else:
            embed = self._build_embed()
            embed.set_author(
                name=f"{self.ctx.author.display_name} — Blackjack (Bet: {_fmt(self.bet)})",
                icon_url=self.ctx.author.display_avatar.url,
            )
            embed.set_footer(text="Synapse - Economy • Hit or Stand")
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.secondary, emoji="🛑")
    async def stand_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self._resolve(interaction)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        try:
            await self.message.edit(view=self)
        except Exception:
            pass



SLOT_SYMBOLS = ["🍒", "🍋", "🍊", "🍇", "⭐", "💎", "7️⃣"]
SLOT_WEIGHTS = [30,   25,   20,   15,   5,    3,    2  ]
SLOT_PAYOUTS = {"7️⃣": 10, "💎": 5, "⭐": 4, "🍇": 3, "🍊": 2.5, "🍋": 2, "🍒": 1.5}



class GamblingCog(commands.Cog):
    def __init__(self, client):
        self.client = client

    @staticmethod
    def _parse(s: str, wallet: int):
        s = str(s).lower().strip()
        if s == "all":
            return wallet
        if "%" in s:
            try:
                pct = int(s.replace("%", ""))
                return max(1, int(wallet * pct / 100)) if 1 <= pct <= 100 else None
            except ValueError:
                return None
        try:
            return int(s)
        except ValueError:
            return None

    @staticmethod
    def _err(text: str) -> discord.Embed:
        return discord.Embed(description=f"{E_ERR} {text}", color=EMBED_COLOR)


    @commands.command(name="coinflip", aliases=["cf", "flip"])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def coinflip(self, ctx, amount: str = None, choice: str = None):
        """Flip a coin. Pick heads or tails and bet."""
        await ensure_user(ctx.author.id)
        if amount is None:
            return await ctx.reply(embed=self._err("Usage: `coinflip <amount> [heads/tails]`"), mention_author=False)

        wallet = await get_wallet(ctx.author.id)
        bet    = self._parse(amount, wallet)
        if not bet or bet <= 0:
            return await ctx.reply(embed=self._err("Enter a valid positive amount."), mention_author=False)
        if bet > wallet:
            return await ctx.reply(embed=self._err("Not enough coins in your wallet."), mention_author=False)

        pick   = ("heads" if choice and choice.lower() in ("heads", "h") else
                  "tails" if choice and choice.lower() in ("tails", "t") else
                  random.choice(["heads", "tails"]))
        result = random.choice(["heads", "tails"])
        won    = result == pick
        embed = discord.Embed(description="<a:CoinSpinning:1477297903297888336> The Coin is Spinning Let's see what you get....", color=EMBED_COLOR, timestamp=discord.utils.utcnow())
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
        msg = await ctx.reply(embed=embed, mention_author=False)

        await asyncio.sleep(1)

        if won:
            new_wallet = await add_wallet(ctx.author.id,  bet)
            desc = f"🪙 Landed on **{result}**!\n\n{E_OK} You picked **{pick}** — won **{_fmt(bet)}** coins!"
        else:
            new_wallet = await add_wallet(ctx.author.id, -bet)
            desc = f"🪙 Landed on **{result}**!\n\n{E_ERR} You picked **{pick}** — lost **{_fmt(bet)}** coins."

        embed = discord.Embed(description=desc, color=EMBED_COLOR, timestamp=discord.utils.utcnow())
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
        embed.set_footer(text=f"Wallet: {_fmt(new_wallet)} coins • Synapse - Economy")
        await msg.edit(embed=embed, mention_author=False)


    @commands.command(name="slots")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def slots(self, ctx, amount: str = None):
        """Spin the slot machine!"""
        await ensure_user(ctx.author.id)
        if amount is None:
            return await ctx.reply(embed=self._err("Usage: `slots <amount>`"), mention_author=False)

        wallet = await get_wallet(ctx.author.id)
        bet    = self._parse(amount, wallet)
        if not bet or bet <= 0:
            return await ctx.reply(embed=self._err("Enter a valid positive amount."), mention_author=False)
        if bet > wallet:
            return await ctx.reply(embed=self._err("Not enough coins in your wallet."), mention_author=False)

        reels = random.choices(SLOT_SYMBOLS, weights=SLOT_WEIGHTS, k=3)

        if reels[0] == reels[1] == reels[2]:
            mult       = SLOT_PAYOUTS.get(reels[0], 2)
            payout     = int(bet * mult)
            new_wallet = await add_wallet(ctx.author.id, payout)
            result = f"{E_OK} **JACKPOT!** Three {reels[0]} — **+{_fmt(payout)}** coins! (`{mult}x`)"
        elif len(set(reels)) < 3:
            payout     = int(bet * 0.5)
            new_wallet = await add_wallet(ctx.author.id, payout)
            result = f"{E_OK} Two of a kind! **+{_fmt(payout)}** coins."
        else:
            new_wallet = await add_wallet(ctx.author.id, -bet)
            result = f"{E_ERR} No match. **-{_fmt(bet)}** coins."

        embed = discord.Embed(
            description=f"**[ {'  '.join(reels)} ]**\n\n{result}",
            color=EMBED_COLOR, timestamp=discord.utils.utcnow(),
        )
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
        embed.set_footer(text=f"Wallet: {_fmt(new_wallet)} coins • Synapse - Economy")
        await ctx.reply(embed=embed, mention_author=False)


    @commands.command(name="blackjack", aliases=["bj"])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def blackjack(self, ctx, amount: str = None):
        """Play blackjack — beat the dealer to 21."""
        await ensure_user(ctx.author.id)
        if amount is None:
            return await ctx.reply(embed=self._err("Usage: `blackjack <amount>`"), mention_author=False)

        wallet = await get_wallet(ctx.author.id)
        bet    = self._parse(amount, wallet)
        if not bet or bet <= 0:
            return await ctx.reply(embed=self._err("Enter a valid positive amount."), mention_author=False)
        if bet > wallet:
            return await ctx.reply(embed=self._err("Not enough coins in your wallet."), mention_author=False)

        deck   = _new_deck()
        player = [deck.pop(), deck.pop()]
        dealer = [deck.pop(), deck.pop()]

        if _hand_value(player) == 21:
            win        = int(bet * 1.5)
            new_wallet = await add_wallet(ctx.author.id, win)
            embed = discord.Embed(
                description=(
                    f"**Your hand** — 21\n{_fmt_hand(player)}\n\n"
                    f"**Dealer's hand** — {_hand_value(dealer)}\n{_fmt_hand(dealer)}\n\n"
                    f"{E_OK} **Blackjack!** Won **{_fmt(win)}** coins!"
                ),
                color=EMBED_COLOR, timestamp=discord.utils.utcnow(),
            )
            embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
            embed.set_footer(text=f"Wallet: {_fmt(new_wallet)} coins • Synapse - Economy")
            return await ctx.reply(embed=embed, mention_author=False)

        view  = BlackjackView(ctx, bet, player, dealer, deck)
        embed = view._build_embed()
        embed.set_author(
            name=f"{ctx.author.display_name} — Blackjack (Bet: {_fmt(bet)})",
            icon_url=ctx.author.display_avatar.url,
        )
        embed.set_footer(text="Synapse - Economy • Hit or Stand")
        view.message = await ctx.reply(embed=embed, view=view, mention_author=False)


    @commands.command(name="gamble")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def gamble(self, ctx, amount: str = None):
        """Legacy alias → coinflip."""
        await ctx.invoke(self.coinflip, amount=amount)


async def setup(client):
    await init_db()
    await client.add_cog(GamblingCog(client))