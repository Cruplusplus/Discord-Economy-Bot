"""
Sistema de Blackjack Callejero (21) para Discord Economy Bot.
Personificado con la voz y lore de Ivy (Deadlock).
Maneja baraja, calculo dinamico de manos (Ases suaves y duros),
interfaz interactiva discord.ui.View y resolucion de apuestas.
"""

import random
import time
from typing import List, Optional, Tuple, TYPE_CHECKING
import discord

from .config import (
    CURRENCY_NAME,
    CURRENCY_SYMBOL,
    BLACKJACK_PAYOUT_NORMAL,
    BLACKJACK_PAYOUT_NATURAL,
    BLACKJACK_TIMEOUT_SECONDS,
    BLACKJACK_DEALER_STAND,
    MIN_RISK_BET_PERCENT,
)
from .lore import (
    IVY_BLACKJACK_WIN_QUOTES,
    IVY_BLACKJACK_NATURAL_QUOTES,
    IVY_BLACKJACK_LOSS_QUOTES,
    IVY_BLACKJACK_BUST_QUOTES,
    IVY_BLACKJACK_DEALER_BUST_QUOTES,
    IVY_BLACKJACK_PUSH_QUOTES,
)

if TYPE_CHECKING:
    from .cog import Economy


SUITS = ["♠️", "♥️", "♦️", "♣️"]
RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]


class Card:
    """Representa una carta individual de la baraja francesa."""

    def __init__(self, rank: str, suit: str):
        self.rank = rank
        self.suit = suit

    @property
    def value(self) -> int:
        if self.rank in ("J", "Q", "K"):
            return 10
        elif self.rank == "A":
            return 11
        return int(self.rank)

    def display(self) -> str:
        return f"`[{self.rank}{self.suit}]`"

    def __repr__(self) -> str:
        return f"{self.rank}{self.suit}"


class Deck:
    """Baraja de 52 cartas con barajado y reparto aleatorio."""

    def __init__(self):
        self.cards: List[Card] = [Card(r, s) for s in SUITS for r in RANKS]
        self.shuffle()

    def shuffle(self) -> None:
        random.shuffle(self.cards)

    def draw(self) -> Card:
        if not self.cards:
            self.cards = [Card(r, s) for s in SUITS for r in RANKS]
            self.shuffle()
        return self.cards.pop()


def calculate_hand(cards: List[Card]) -> int:
    """Calcula el puntaje de una mano manejando Ases dinamicamente (11 o 1)."""
    total = sum(c.value for c in cards)
    aces = sum(1 for c in cards if c.rank == "A")

    while total > 21 and aces > 0:
        total -= 10
        aces -= 1

    return total


def is_natural_blackjack(cards: List[Card]) -> bool:
    """Determina si la mano es un Blackjack Natural (21 con exactamente 2 cartas)."""
    return len(cards) == 2 and calculate_hand(cards) == 21


def format_hand(cards: List[Card], hide_second: bool = False) -> str:
    """Formatea las cartas de la mano para mostrar en el Embed de Discord."""
    if not cards:
        return "`[ Vacio ]`"
    if hide_second and len(cards) >= 2:
        return f"{cards[0].display()} `[ 🂠 ? ]`"
    return " ".join(c.display() for c in cards)


class BlackjackView(discord.ui.View):
    """Vista interactiva con botones para Pedir, Plantarse y Doblar en Blackjack."""

    def __init__(
        self,
        cog: "Economy",
        user: discord.Member | discord.User,
        guild: Optional[discord.Guild],
        channel: discord.abc.Messageable,
        bet: int,
        deck: Deck,
        player_hand: List[Card],
        dealer_hand: List[Card],
    ):
        super().__init__(timeout=BLACKJACK_TIMEOUT_SECONDS)
        self.cog = cog
        self.user = user
        self.user_id = user.id
        self.guild = guild
        self.channel = channel
        self.bet = bet
        self.initial_bet = bet
        self.deck = deck
        self.player_hand = player_hand
        self.dealer_hand = dealer_hand
        self.doubled = False
        self.game_over = False
        self.message: Optional[discord.Message] = None

        # Deshabilitar Doblar si el usuario no tiene saldo suficiente en mano
        user_wallet = self._get_user_wallet()
        if user_wallet < self.bet:
            self.double_button.disabled = True

    def _get_user_wallet(self) -> int:
        user_data = self.cog.db.get_user_data(self.user_id)
        return user_data.get("wallet", 0)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ ¡Ey, chacho! Esta mesa de Blackjack pertenece a otro vecino. ¡Tirá tus propias cartas con `%blackjack`!",
                ephemeral=True
            )
            return False
        return True

    def disable_all_buttons(self) -> None:
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True

    def build_embed(
        self,
        title: str,
        description: str,
        color: discord.Color,
        hide_dealer: bool = True,
        footer_text: Optional[str] = None
    ) -> discord.Embed:
        embed = discord.Embed(
            title=title,
            description=description,
            color=color
        )

        player_score = calculate_hand(self.player_hand)
        dealer_score = calculate_hand(self.dealer_hand)

        player_status = f"{player_score}"
        if player_score == 21:
            player_status += " ⚡ *(¡Veintiuno!)*"
        elif player_score > 21:
            player_status += " 💥 *(¡Bust!)*"

        dealer_status = f"{self.dealer_hand[0].value} + ?" if hide_dealer else f"{dealer_score}"
        if not hide_dealer and dealer_score > 21:
            dealer_status += " 💥 *(¡Bust!)*"

        embed.add_field(
            name=f"👤 Mano de {self.user.display_name} ({player_status})",
            value=format_hand(self.player_hand),
            inline=False
        )
        embed.add_field(
            name=f"🪨 Mano de Ivy - Crupier ({dealer_status})",
            value=format_hand(self.dealer_hand, hide_second=hide_dealer),
            inline=False
        )

        apuesta_str = f"{self.bet:,} {CURRENCY_SYMBOL}"
        if self.doubled:
            apuesta_str += f" *(Doblada: {self.initial_bet:,} x2)*"
        embed.add_field(name="💰 Apuesta en Mesa", value=apuesta_str, inline=True)

        user_data = self.cog.db.get_user_data(self.user_id)
        embed.add_field(name="💵 Tu Billetera Restante", value=f"{user_data.get('wallet', 0):,} {CURRENCY_SYMBOL}", inline=True)

        footer = footer_text or "Usa los botones para Pedir (Hit), Plantarte (Stand) o Doblar (Double Down)."
        embed.set_footer(text=footer)
        return embed

    @discord.ui.button(label="Pedir Carta", style=discord.ButtonStyle.primary, emoji="🃏")
    async def hit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.game_over:
            return

        self.player_hand.append(self.deck.draw())
        player_score = calculate_hand(self.player_hand)

        # Ya no se puede doblar tras pedir carta
        self.double_button.disabled = True

        if player_score > 21:
            await self._finish_game(interaction, result_type="player_bust")
        elif player_score == 21:
            # Con 21 exactos, se planta automaticamente para jugar contra Ivy
            await self._finish_game(interaction, result_type="stand")
        else:
            embed = self.build_embed(
                title="🃏 Blackjack Callejero - Mano en Juego",
                description="Robaste una carta. ¿Te plantas o buscas acercarte más a 21?",
                color=discord.Color.blue(),
                hide_dealer=True
            )
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Plantarse", style=discord.ButtonStyle.secondary, emoji="🛑")
    async def stand_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.game_over:
            return
        await self._finish_game(interaction, result_type="stand")

    @discord.ui.button(label="Doblar Apuesta", style=discord.ButtonStyle.success, emoji="⚡")
    async def double_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.game_over:
            return

        async with self.cog.db.lock:
            user_data = self.cog.db.get_user_data(self.user_id)
            wallet = user_data.get("wallet", 0)

            if wallet < self.initial_bet:
                await interaction.response.send_message(
                    f"❌ ¡No tienes suficientes almas en mano para doblar! Necesitas **{self.initial_bet:,} {CURRENCY_SYMBOL}** más.",
                    ephemeral=True
                )
                return

            # Descontar la segunda mitad de la apuesta
            user_data["wallet"] -= self.initial_bet
            self.bet = self.initial_bet * 2
            self.doubled = True
            await self.cog.db.save()

        # Doblar otorga exactamente 1 carta mas y se planta automaticamente
        self.player_hand.append(self.deck.draw())
        player_score = calculate_hand(self.player_hand)

        if player_score > 21:
            await self._finish_game(interaction, result_type="player_bust")
        else:
            await self._finish_game(interaction, result_type="stand")

    async def _finish_game(
        self,
        interaction: Optional[discord.Interaction] = None,
        result_type: str = "stand"
    ) -> None:
        """Resuelve el final de la partida de Blackjack, actualiza balances y BD de forma atomica."""
        self.game_over = True
        self.disable_all_buttons()
        self.stop()

        player_score = calculate_hand(self.player_hand)
        dealer_score = calculate_hand(self.dealer_hand)

        # 1. Turno de Ivy (Crupier) si el jugador no se paso
        if result_type == "stand":
            while calculate_hand(self.dealer_hand) < BLACKJACK_DEALER_STAND:
                self.dealer_hand.append(self.deck.draw())
            dealer_score = calculate_hand(self.dealer_hand)

        # 2. Determinar resultado y pagos
        ganancia_neta = 0
        devolucion = 0
        outcome = ""  # "win", "loss", "push", "dealer_bust", "player_bust"

        if result_type == "player_bust":
            outcome = "player_bust"
            # La apuesta ya fue descontada al iniciar/doblar
        elif dealer_score > 21:
            outcome = "dealer_bust"
            ganancia_neta = self.bet
            devolucion = self.bet * 2
        elif player_score > dealer_score:
            outcome = "win"
            ganancia_neta = self.bet
            devolucion = self.bet * 2
        elif player_score < dealer_score:
            outcome = "loss"
        else:
            outcome = "push"
            devolucion = self.bet  # Se devuelve la apuesta integra

        # 3. Transaccion atomica en base de datos
        async with self.cog.db.lock:
            user_data = self.cog.db.get_user_data(self.user_id)

            if devolucion > 0:
                user_data["wallet"] += devolucion

            if outcome in ("win", "dealer_bust"):
                user_data["stats"]["gambles_won"] = user_data["stats"].get("gambles_won", 0) + 1
            elif outcome in ("loss", "player_bust"):
                user_data["stats"]["gambles_lost"] = user_data["stats"].get("gambles_lost", 0) + 1

            # Evaluacion en memoria del temporizador de Robin Hood ("Skin in the game")
            user_total = user_data.get("wallet", 0) + user_data.get("bank", 0)
            is_richest, is_valid_reset, req_bet = self.cog._evaluar_riesgo_apostador(
                self.user_id, self.bet, user_total, self.guild
            )
            if not is_richest or is_valid_reset:
                user_data["last_gamble"] = time.time()

            await self.cog.db.save()

        # Limpiar de la lista de partidas activas
        self.cog.active_blackjacks.discard(self.user_id)

        # 4. Formatear Embed final y citas
        if outcome == "player_bust":
            quote = random.choice(IVY_BLACKJACK_BUST_QUOTES).format(
                player_total=player_score
            )
            title = f"💥 ¡Te Pasaste de 21! (Bust con {player_score})"
            desc = (
                f"{quote}\n\n"
                f"💸 **Pérdida:** -{self.bet:,} {CURRENCY_SYMBOL}\n"
                f"💵 **Billetera restante:** {user_data['wallet']:,} {CURRENCY_SYMBOL}"
            )
            color = discord.Color.red()
        elif outcome == "dealer_bust":
            quote = random.choice(IVY_BLACKJACK_DEALER_BUST_QUOTES).format(
                dealer_total=dealer_score
            )
            title = f"🎉 ¡Ivy Quebró con {dealer_score}! ¡Victoria!"
            desc = (
                f"{quote}\n\n"
                f"💰 **Ganancia neta:** +{ganancia_neta:,} {CURRENCY_SYMBOL}\n"
                f"💵 **Billetera actual:** {user_data['wallet']:,} {CURRENCY_SYMBOL}"
            )
            color = discord.Color.green()
        elif outcome == "win":
            quote = random.choice(IVY_BLACKJACK_WIN_QUOTES).format(
                player_total=player_score,
                dealer_total=dealer_score,
                profit=ganancia_neta,
                symbol=CURRENCY_SYMBOL
            )
            title = f"🎉 ¡Victoria en la Mesa! ({player_score} a {dealer_score})"
            desc = (
                f"{quote}\n\n"
                f"💰 **Ganancia neta:** +{ganancia_neta:,} {CURRENCY_SYMBOL}\n"
                f"💵 **Billetera actual:** {user_data['wallet']:,} {CURRENCY_SYMBOL}"
            )
            color = discord.Color.green()
        elif outcome == "loss":
            quote = random.choice(IVY_BLACKJACK_LOSS_QUOTES).format(
                player_total=player_score,
                dealer_total=dealer_score
            )
            title = f"💸 La Casa Gana ({dealer_score} a {player_score})"
            desc = (
                f"{quote}\n\n"
                f"💸 **Pérdida:** -{self.bet:,} {CURRENCY_SYMBOL}\n"
                f"💵 **Billetera restante:** {user_data['wallet']:,} {CURRENCY_SYMBOL}"
            )
            color = discord.Color.red()
        else:  # push
            quote = random.choice(IVY_BLACKJACK_PUSH_QUOTES).format(
                total=player_score
            )
            title = f"⚖️ ¡Empate Técnico! ({player_score} a {dealer_score})"
            desc = (
                f"{quote}\n\n"
                f"🔄 **Apuesta recuperada:** {self.bet:,} {CURRENCY_SYMBOL}\n"
                f"💵 **Billetera:** {user_data['wallet']:,} {CURRENCY_SYMBOL}"
            )
            color = discord.Color.light_grey()

        footer_text = None
        if is_richest and not is_valid_reset:
            footer_text = f"⚠️ [Magnate] Apuesta insuficiente para resetear inactividad. Mínimo: {req_bet:,} {CURRENCY_SYMBOL} ({int(MIN_RISK_BET_PERCENT * 100)}% de tu fortuna)."

        final_embed = self.build_embed(
            title=title,
            description=desc,
            color=color,
            hide_dealer=False,
            footer_text=footer_text
        )

        if interaction and not interaction.response.is_done():
            await interaction.response.edit_message(embed=final_embed, view=self)
        elif self.message:
            try:
                await self.message.edit(embed=final_embed, view=self)
            except discord.HTTPException:
                pass

        # 5. Sincronizacion reactiva de rol de lider si aplica
        if self.guild:
            leader_id, leader_wealth = self.cog._top_leader_cache.get(self.guild.id, (0, 0))
            if self.user_id == leader_id or user_total >= leader_wealth:
                await self.cog.actualizar_rol_millonario(self.guild, announce_channel=self.channel)

    async def on_timeout(self) -> None:
        """Si el usuario se queda inactivo 60 segundos, se planta automaticamente."""
        if not self.game_over:
            await self._finish_game(interaction=None, result_type="stand")
