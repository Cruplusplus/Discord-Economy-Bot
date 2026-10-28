"""
Modulo de Loteria y Gran Pozo Comunitario de Spanish Harlem.
Gestiona la acumulacion del pozo (jackpot), compra de boletos con limite anti-monopolio,
calculo ponderado de probabilidades y sorteo automatico con anuncios de Ivy.
"""

import random
import time
from typing import Dict, Any, Optional, List, Tuple, TYPE_CHECKING
import discord

from .config import (
    CURRENCY_NAME,
    CURRENCY_SYMBOL,
    LOTTERY_TICKET_PRICE,
    LOTTERY_MAX_TICKETS_PER_USER,
    LOTTERY_BASE_JACKPOT,
    LOTTERY_DRAW_TIME,
    LOTTERY_DRAW_DAY,
)
from .lore import (
    IVY_LOTTERY_BUY_QUOTES,
    IVY_LOTTERY_WIN_QUOTES,
)

if TYPE_CHECKING:
    from .cog import Economy


class LotteryManager:
    """Administra las reglas y sorteos del pozo comunitario."""

    def __init__(self, cog: "Economy"):
        self.cog = cog

    def get_lottery_data(self) -> Dict[str, Any]:
        return self.cog.db.get_lottery_data()

    async def add_to_jackpot(self, amount: int, acquire_lock: bool = True) -> int:
        """Suma un importe al pozo acumulado (comisiones de timba, multas, etc.)."""
        if amount <= 0:
            return 0
        if acquire_lock:
            async with self.cog.db.lock:
                data = self.get_lottery_data()
                data["jackpot"] = data.get("jackpot", LOTTERY_BASE_JACKPOT) + amount
                await self.cog.db.save()
                return data["jackpot"]
        else:
            data = self.get_lottery_data()
            data["jackpot"] = data.get("jackpot", LOTTERY_BASE_JACKPOT) + amount
            return data["jackpot"]

    async def buy_tickets(self, user_id: int, count: int) -> Tuple[bool, str, int, int]:
        """
        Compra boletos de lotería para el usuario asegurando el límite anti-monopolio.
        Retorna: (exito, mensaje, total_tickets_usuario, pozo_actual)
        """
        if count <= 0:
            return False, "❌ Tienes que comprar al menos 1 boleto, chacho.", 0, 0

        async with self.cog.db.lock:
            user_data = self.cog.db.get_user_data(user_id)
            wallet = user_data.get("wallet", 0)
            lottery = self.get_lottery_data()
            tickets_dict = lottery.setdefault("tickets", {})
            user_key = str(user_id)

            current_user_tickets = tickets_dict.get(user_key, 0)
            if current_user_tickets + count > LOTTERY_MAX_TICKETS_PER_USER:
                disponibles = max(0, LOTTERY_MAX_TICKETS_PER_USER - current_user_tickets)
                return (
                    False,
                    f"❌ ¡Límite anti-monopolio alcanzado! Cada vecino puede tener un máximo de **{LOTTERY_MAX_TICKETS_PER_USER} tickets** por sorteo.\n"
                    f"Actualmente tienes **{current_user_tickets}** boletos (solo puedes comprar **{disponibles}** más).",
                    current_user_tickets,
                    lottery.get("jackpot", LOTTERY_BASE_JACKPOT),
                )

            total_cost = count * LOTTERY_TICKET_PRICE
            if wallet < total_cost:
                return (
                    False,
                    f"❌ Te faltan almas en mano. Comprar **{count} ticket(s)** cuesta **{total_cost:,} {CURRENCY_SYMBOL}** "
                    f"y solo tienes **{wallet:,} {CURRENCY_SYMBOL}**.",
                    current_user_tickets,
                    lottery.get("jackpot", LOTTERY_BASE_JACKPOT),
                )

            # Cobrar y acreditar al pozo
            user_data["wallet"] -= total_cost
            tickets_dict[user_key] = current_user_tickets + count
            lottery["jackpot"] = lottery.get("jackpot", LOTTERY_BASE_JACKPOT) + total_cost

            await self.cog.db.save()

            return (
                True,
                random.choice(IVY_LOTTERY_BUY_QUOTES).format(
                    count=count,
                    cost=total_cost,
                    currency=CURRENCY_SYMBOL
                ),
                tickets_dict[user_key],
                lottery["jackpot"],
            )

    async def draw_lottery(self, guild: Optional[discord.Guild]) -> Tuple[bool, Optional[discord.Member], int, int]:
        """
        Realiza el sorteo del pozo ponderado entre los boletos emitidos.
        Retorna: (hubo_ganador, member_ganador, premio_otorgado, total_boletos_participantes)
        """
        async with self.cog.db.lock:
            lottery = self.get_lottery_data()
            tickets_dict = lottery.get("tickets", {})
            jackpot = lottery.get("jackpot", LOTTERY_BASE_JACKPOT)

            if not tickets_dict:
                # Nadie compro tickets: el pozo se acumula para la proxima
                return False, None, jackpot, 0

            # Construir bolillero ponderado
            bolillero: List[int] = []
            for uid_str, qty in tickets_dict.items():
                try:
                    uid = int(uid_str)
                    bolillero.extend([uid] * qty)
                except ValueError:
                    continue

            if not bolillero:
                return False, None, jackpot, 0

            total_tickets = len(bolillero)
            winner_id = random.choice(bolillero)

            # Acreditar premio al ganador
            winner_data = self.cog.db.get_user_data(winner_id)
            winner_data["wallet"] += jackpot

            # Guardar historico y resetear loteria
            lottery["last_winner"] = {
                "user_id": winner_id,
                "amount": jackpot,
                "timestamp": time.time(),
                "total_tickets": total_tickets,
            }
            self.cog.db.reset_lottery()
            await self.cog.db.save()

        # Obtener objeto Member del ganador
        winner_member = None
        if guild:
            winner_member = guild.get_member(winner_id)
            if winner_member is None:
                try:
                    winner_member = await guild.fetch_member(winner_id)
                except Exception:
                    winner_member = None

        return True, winner_member, jackpot, total_tickets

    def build_embed(
        self,
        user_id: int,
        guild: Optional[discord.Guild],
    ) -> discord.Embed:
        """Crea el panel visual del Pozo Comunitario."""
        lottery = self.get_lottery_data()
        jackpot = lottery.get("jackpot", LOTTERY_BASE_JACKPOT)
        tickets_dict = lottery.get("tickets", {})

        total_tickets = sum(tickets_dict.values())
        user_tickets = tickets_dict.get(str(user_id), 0)

        user_prob = (user_tickets / total_tickets * 100) if total_tickets > 0 else 0.0

        embed = discord.Embed(
            title="🎰 El Gran Pozo y Lotería de Spanish Harlem",
            description=(
                f"Cada semana las gárgolas juntamos un fondo comunal con la recaudación del barrio.\n"
                f"¡Comprá tus tickets y participá por llevarte la fortuna entera!\n\n"
                f"💰 **Pozo Acumulado Actual:** **{jackpot:,} {CURRENCY_NAME.upper()} {CURRENCY_SYMBOL}**\n"
                f"🎟️ **Precio por Ticket:** **{LOTTERY_TICKET_PRICE:,} {CURRENCY_SYMBOL}** *(Máximo: {LOTTERY_MAX_TICKETS_PER_USER} por vecino)*"
            ),
            color=discord.Color.gold(),
        )

        embed.add_field(
            name="📊 Estado de tus Boletos",
            value=(
                f"• Boletos comprados: **{user_tickets} / {LOTTERY_MAX_TICKETS_PER_USER}**\n"
                f"• Probabilidad de ganar: **{user_prob:.1f}%**\n"
                f"• Inversión acumulada: **{user_tickets * LOTTERY_TICKET_PRICE:,} {CURRENCY_SYMBOL}**"
            ),
            inline=True,
        )

        embed.add_field(
            name="📈 Estadísticas del Sorteo",
            value=(
                f"• Total de tickets en juego: **{total_tickets}**\n"
                f"• Vecinos participando: **{len(tickets_dict)}**\n"
                f"• Pozo base garantizado: **{LOTTERY_BASE_JACKPOT:,} {CURRENCY_SYMBOL}**"
            ),
            inline=True,
        )

        # Participantes destacados (Top compradores)
        if tickets_dict:
            sorted_buyers = sorted(tickets_dict.items(), key=lambda x: x[1], reverse=True)[:5]
            buyer_lines = []
            for uid_str, count in sorted_buyers:
                member_name = f"<@{uid_str}>"
                if guild and uid_str.isdigit():
                    try:
                        m = guild.get_member(int(uid_str))
                        if m:
                            member_name = m.display_name
                    except ValueError:
                        pass
                buyer_lines.append(f"• **{member_name}**: {count} ticket(s) ({(count / total_tickets * 100):.1f}%)")
            embed.add_field(name="👥 Principales Apostadores", value="\n".join(buyer_lines), inline=False)
        else:
            embed.add_field(name="👥 Principales Apostadores", value="*¡Sé el primero en comprar tickets con `%ticket`!*", inline=False)

        # Ultimo ganador
        last_win = lottery.get("last_winner")
        if last_win:
            last_mention = f"<@{last_win['user_id']}>"
            embed.add_field(
                name="🏆 Último Ganador del Pozo",
                value=f"**{last_mention}** se llevó **{last_win['amount']:,} {CURRENCY_SYMBOL}** con {last_win.get('total_tickets', 0)} tickets en juego.",
                inline=False,
            )

        embed.set_footer(text=f"Usa '%ticket <cantidad>' para comprar • Sorteo todos los domingos a las {LOTTERY_DRAW_TIME.strftime('%H:%M')} hs.")
        return embed
