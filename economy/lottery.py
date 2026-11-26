"""
Modulo de Loteria y Gran Pozo Comunitario de Spanish Harlem.
Gestiona la acumulacion del pozo (jackpot), compra de boletos con limite anti-monopolio,
calculo ponderado de probabilidades y sorteo automatico con anuncios de Ivy.
"""

import logging
import random
import time
from typing import TYPE_CHECKING, Any

import discord

from .config import (
    CURRENCY_NAME,
    CURRENCY_SYMBOL,
    LOTTERY_BASE_JACKPOT,
    LOTTERY_DRAW_TIME,
    LOTTERY_MAX_TICKETS_PER_USER,
    LOTTERY_TICKET_PRICE,
)
from .lore import (
    IVY_LOTTERY_BUY_QUOTES,
)

if TYPE_CHECKING:
    from .cog import Economy


class LotteryManager:
    """Administra las reglas y sorteos del pozo comunitario."""

    def __init__(self, cog: "Economy"):
        self.cog = cog
        self._log = logging.getLogger("economy.lottery")

    async def get_lottery_data(self) -> dict[str, Any]:
        return await self.cog.db.get_lottery_data()

    async def add_to_jackpot(self, amount: int) -> int:
        """Suma un importe al pozo acumulado (comisiones de timba, multas, etc.)."""
        if amount <= 0:
            return 0
        
        async with self.cog.db.lock:
            lottery = await self.get_lottery_data()
            new_jackpot = lottery.get("jackpot", LOTTERY_BASE_JACKPOT) + amount
            
            async with aiosqlite.connect(self.cog.db.file_path) as db:
                await db.execute("PRAGMA foreign_keys=ON")
                await db.execute(
                    "UPDATE lottery SET jackpot = ? WHERE id = 1",
                    (new_jackpot,)
                )
                await db.commit()
            
            self._log.info("Pozo de lotería incrementado", extra={"amount": amount, "new_jackpot": new_jackpot})
            return new_jackpot

    async def buy_tickets(self, user_id: int, count: int) -> tuple[bool, str, int, int]:
        """
        Compra boletos de lotería para el usuario asegurando el límite anti-monopolio.
        Retorna: (exito, mensaje, total_tickets_usuario, pozo_actual)
        """
        if count <= 0:
            return False, "❌ Tienes que comprar al menos 1 boleto, chacho.", 0, 0

        async with self.cog.db.lock:
            async with aiosqlite.connect(self.cog.db.file_path) as db:
                await db.execute("PRAGMA foreign_keys=ON")
                db.row_factory = aiosqlite.Row
                
                # Obtener wallet del usuario
                async with db.execute("SELECT wallet FROM users WHERE user_id = ?", (user_id,)) as cursor:
                    row = await cursor.fetchone()
                wallet = row["wallet"] if row else 0
                
                # Obtener jackpot y tickets actuales
                async with db.execute("SELECT jackpot FROM lottery WHERE id = 1") as cursor:
                    row = await cursor.fetchone()
                jackpot = row["jackpot"] if row else LOTTERY_BASE_JACKPOT
                
                tickets_dict = {}
                async with db.execute(
                    "SELECT user_id, ticket_count FROM lottery_tickets WHERE draw_id = 1 AND ticket_count > 0"
                ) as cursor:
                    async for trow in cursor:
                        tickets_dict[str(trow["user_id"])] = trow["ticket_count"]
                
                user_key = str(user_id)
                current_user_tickets = tickets_dict.get(user_key, 0)
                
                if current_user_tickets + count > LOTTERY_MAX_TICKETS_PER_USER:
                    disponibles = max(0, LOTTERY_MAX_TICKETS_PER_USER - current_user_tickets)
                    return (
                        False,
                        f"❌ ¡Límite anti-monopolio alcanzado! Cada vecino puede tener un máximo de **{LOTTERY_MAX_TICKETS_PER_USER} tickets** por sorteo.\n"
                        f"Actualmente tienes **{current_user_tickets}** boletos (solo puedes comprar **{disponibles}** más).",
                        current_user_tickets,
                        jackpot,
                    )

                total_cost = count * LOTTERY_TICKET_PRICE
                if wallet < total_cost:
                    return (
                        False,
                        f"❌ Te faltan almas en mano. Comprar **{count} ticket(s)** cuesta **{total_cost:,} {CURRENCY_SYMBOL}** "
                        f"y solo tienes **{wallet:,} {CURRENCY_SYMBOL}**.",
                        current_user_tickets,
                        jackpot,
                    )

                # Cobrar y acreditar al pozo - todo en una transacción
                # Descontar wallet
                await db.execute(
                    "UPDATE users SET wallet = wallet - ? WHERE user_id = ?",
                    (total_cost, user_id)
                )
                
                # Actualizar/insertar ticket
                new_ticket_count = current_user_tickets + count
                await db.execute(
                    """
                    INSERT OR REPLACE INTO lottery_tickets (user_id, ticket_count, draw_id)
                    VALUES (?, ?, 1)
                    """,
                    (user_id, new_ticket_count)
                )
                
                # Actualizar jackpot
                new_jackpot = jackpot + total_cost
                await db.execute(
                    "UPDATE lottery SET jackpot = ? WHERE id = 1",
                    (new_jackpot,)
                )
                
                await db.commit()

            self._log.info("Boletos de lotería comprados", extra={"user_id": user_id, "count": count, "total_cost": total_cost, "new_ticket_count": new_ticket_count, "new_jackpot": new_jackpot})

            return (
                True,
                random.choice(IVY_LOTTERY_BUY_QUOTES).format(
                    count=count,
                    cost=total_cost,
                    currency=CURRENCY_SYMBOL
                ),
                new_ticket_count,
                new_jackpot,
            )

    async def draw_lottery(self, guild: discord.Guild | None) -> tuple[bool, discord.Member | None, int, int]:
        """
        Realiza el sorteo del pozo ponderado entre los boletos emitidos.
        Retorna: (hubo_ganador, member_ganador, premio_otorgado, total_boletos_participantes)
        """
        async with self.cog.db.lock:
            async with aiosqlite.connect(self.cog.db.file_path) as db:
                await db.execute("PRAGMA foreign_keys=ON")
                db.row_factory = aiosqlite.Row
                
                # Obtener jackpot actual y tickets
                async with db.execute("SELECT jackpot FROM lottery WHERE id = 1") as cursor:
                    row = await cursor.fetchone()
                jackpot = row["jackpot"] if row else LOTTERY_BASE_JACKPOT
                
                # Obtener tickets
                tickets_dict = {}
                bolillero: list[int] = []
                async with db.execute(
                    "SELECT user_id, ticket_count FROM lottery_tickets WHERE draw_id = 1 AND ticket_count > 0"
                ) as cursor:
                    async for trow in cursor:
                        uid = trow["user_id"]
                        qty = trow["ticket_count"]
                        tickets_dict[str(uid)] = qty
                        bolillero.extend([uid] * qty)
                
                if not bolillero:
                    self._log.info("Sorteo de lotería sin participantes")
                    return False, None, jackpot, 0
                
                total_tickets = len(bolillero)
                winner_id = random.choice(bolillero)
                now = time.time()
                
                self._log.info("Sorteo de lotería realizado", extra={"winner_id": winner_id, "jackpot": jackpot, "total_tickets": total_tickets, "participants": len(tickets_dict)})
                
                # Sumar premio al ganador
                await db.execute(
                    "UPDATE users SET wallet = wallet + ? WHERE user_id = ?",
                    (jackpot, winner_id)
                )
                
                # Guardar histórico y resetear lotería
                await db.execute(
                    """
                    UPDATE lottery SET
                        last_winner_id = ?,
                        last_winner_amount = ?,
                        last_winner_timestamp = ?,
                        last_winner_total_tickets = ?,
                        last_draw = ?,
                        jackpot = ?,
                        total_drawn = total_drawn + 1
                    WHERE id = 1
                    """,
                    (winner_id, jackpot, now, total_tickets, now, LOTTERY_BASE_JACKPOT)
                )
                
                # Limpiar tickets
                await db.execute("DELETE FROM lottery_tickets WHERE draw_id = 1")
                
                await db.commit()

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
        guild: discord.Guild | None,
    ) -> discord.Embed:
        """Crea el panel visual del Pozo Comunitario (versión síncrona para compatibilidad)."""
        # Nota: Este método se llama desde comandos que ya están en contexto async
        # Para simplificar, usamos una versión que requiere lottery data ya cargada
        # o hacemos la llamada async desde el comando.
        raise NotImplementedError("Usa build_embed_async desde comandos async")

    async def build_embed_async(
        self,
        user_id: int,
        guild: discord.Guild | None,
    ) -> discord.Embed:
        """Crea el panel visual del Pozo Comunitario (versión async)."""
        lottery = await self.get_lottery_data()
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


# Importación local para evitar ciclo
import aiosqlite