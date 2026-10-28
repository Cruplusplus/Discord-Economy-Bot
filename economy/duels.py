"""
Modulo de combates callejeros y apuestas entre usuarios (Duelos).
Contiene EconomyDuelsMixin con los comandos '%duelo', '%bet' y la resolucion automatica.
"""

import time
import random
import asyncio
from typing import Optional
import discord
from discord.ext import commands

from .config import (
    DUEL_CHANNEL_ID,
    DUEL_BET_TIME_SECONDS,
    DUEL_INVITE_TIMEOUT,
    DUEL_UNOPPOSED_PROFIT_PERCENT,
    CURRENCY_SYMBOL,
    MIN_RISK_BET_PERCENT,
)


class EconomyDuelsMixin:
    """Mixin que encapsula el sistema de duelos PvP y apuestas comunitarias de tribuna."""

    # --------------------------------------------------------------------------
    #                   SISTEMA DE COMBATE Y APUESTAS: DUELO
    # --------------------------------------------------------------------------

    @commands.command(name="duelo", aliases=["duel"])
    async def duelo(self, ctx: commands.Context, member: discord.Member, monto: str):
        """Reta a un miembro a un combate callejero con apuestas de la comunidad."""
        if ctx.guild is None:
            await ctx.reply("❌ Los duelos solo se pueden celebrar en las calles de un servidor.")
            return

        # Restriccion de canal si DUEL_CHANNEL_ID esta configurado
        if DUEL_CHANNEL_ID and ctx.channel.id != DUEL_CHANNEL_ID:
            await ctx.reply(f"❌ Los duelos solo se pueden celebrar en el callejón asignado: <#{DUEL_CHANNEL_ID}>.")
            return

        guild_id = ctx.guild.id

        # 1. Un solo duelo a la vez por servidor
        if guild_id in self.active_duels or guild_id in self.pending_challenges:
            await ctx.reply("❌ Ya hay un duelo en curso o un desafío pendiente en este barrio. ¡Un combate a la vez, chacho!")
            return

        if member.id == ctx.author.id:
            await ctx.reply("❌ No puedes retarte a ti mismo, chacho. Busca a alguien con quien medir fuerzas.")
            return
        if member.bot:
            await ctx.reply("❌ Las gárgolas no apostamos contra bots, no tienen almas que perder.")
            return

        async with self.db.lock:
            attacker_data = self.db.get_user_data(ctx.author.id)
            enemy_data = self.db.get_user_data(member.id)

            attacker_total = attacker_data.get("wallet", 0) + attacker_data.get("bank", 0)
            enemy_total = enemy_data.get("wallet", 0) + enemy_data.get("bank", 0)

            stake = self._parse_amount(monto, attacker_total)
            if stake is None or stake <= 0:
                await ctx.reply("❌ La apuesta debe ser un número entero positivo.")
                return

            if stake > attacker_total:
                await ctx.reply(
                    f"❌ No tienes suficientes almas en tu fortuna total (billetera + cornisa). "
                    f"Tu patrimonio total es de **{attacker_total:,} {CURRENCY_SYMBOL}**."
                )
                return

            if stake > enemy_total:
                await ctx.reply(
                    f"❌ {member.display_name} no tiene suficientes almas en su fortuna total para igualar esa apuesta "
                    f"(su patrimonio total es de **{enemy_total:,} {CURRENCY_SYMBOL}**)."
                )
                return

        # Registrar desafio pendiente para evitar desafios solapados
        self.pending_challenges.add(guild_id)

        invite_deadline = int(time.time() + DUEL_INVITE_TIMEOUT)
        embed_desafio = discord.Embed(
            title="⚔️ ¡DESAFÍO A DUELO EN SPANISH HARLEM!",
            description=(
                f"**{ctx.author.mention}** ha desafiado a **{member.mention}** a un combate en el callejón.\n\n"
                f"💰 **Apuesta individual:** **{stake:,} {CURRENCY_SYMBOL}**\n"
                f"🏆 **Pozo inicial del ganador:** **{stake * 2:,} {CURRENCY_SYMBOL}**\n\n"
                f"⚠️ *¡Atención! Ambos duelistas deben tener las almas **en mano (billetera)** para poder pelear. "
                f"Si las tienen en el banco, retírenlas con `{ctx.prefix}withdraw {stake}` antes de aceptar.*\n\n"
                f"⏳ {member.mention}, tienes hasta <t:{invite_deadline}:R> (<t:{invite_deadline}:T>) para decidir:\n"
                f"• Reacciona con ✅ para **Aceptar el duelo**\n"
                f"• Reacciona con ❌ para **Rechazar y huir**"
            ),
            color=discord.Color.red()
        )
        embed_desafio.set_thumbnail(url=ctx.author.display_avatar.url)
        embed_desafio.set_footer(text="Carlos always says: choose your fights wisely.")

        try:
            request = await ctx.send(content=f"{member.mention} ¡Te han desafiado a un combate!", embed=embed_desafio)
            await request.add_reaction("✅")
            await request.add_reaction("❌")

            def reaction_check(reaction: discord.Reaction, user: discord.User) -> bool:
                return (
                    reaction.message.id == request.id
                    and user.id == member.id
                    and str(reaction.emoji) in ("✅", "❌")
                )

            try:
                reaction, _ = await self.bot.wait_for("reaction_add", timeout=DUEL_INVITE_TIMEOUT, check=reaction_check)
            except asyncio.TimeoutError:
                self.pending_challenges.discard(guild_id)
                await ctx.send(f"⌛ El reto expiró: {member.mention} no respondió a tiempo. Los callejones siguen en silencio.")
                return

            if str(reaction.emoji) == "❌":
                self.pending_challenges.discard(guild_id)
                await ctx.send(f"💨 {member.mention} rechazó el duelo y se marchó silbando bajo.")
                return

            # Si acepto, verificamos que ambos tengan el dinero en mano (wallet)
            async with self.db.lock:
                attacker_data = self.db.get_user_data(ctx.author.id)
                enemy_data = self.db.get_user_data(member.id)

                faltantes = []
                if attacker_data["wallet"] < stake:
                    faltantes.append(f"{ctx.author.mention} (tiene **{attacker_data['wallet']:,} {CURRENCY_SYMBOL}** en mano)")
                if enemy_data["wallet"] < stake:
                    faltantes.append(f"{member.mention} (tiene **{enemy_data['wallet']:,} {CURRENCY_SYMBOL}** en mano)")

                if faltantes:
                    self.pending_challenges.discard(guild_id)
                    faltantes_str = " y ".join(faltantes)
                    await ctx.send(
                        f"❌ El duelo no pudo comenzar: Para pelear hay que poner las almas en mano sobre la mesa.\n"
                        f"Fondos insuficientes en mano de: {faltantes_str}.\n"
                        f"💡 Si tienen las almas guardadas en la cornisa, usen `{ctx.prefix}withdraw {stake}` para retirarlas a la mano antes de aceptar."
                    )
                    return

                attacker_data["wallet"] -= stake
                enemy_data["wallet"] -= stake
                await self.db.save()

            # Registrar actividad de riesgo para ambos combatientes
            await self._registrar_actividad_riesgo(ctx.author.id, stake, ctx.guild)
            await self._registrar_actividad_riesgo(member.id, stake, ctx.guild)

            self.pending_challenges.discard(guild_id)

            # Buscar GIF de pelea en Giphy
            gif_pelea = await self._obtener_gif(["anime fight", "fight", "street brawl"])

            duel = {
                "channel": ctx.channel,
                "guild_id": guild_id,
                "attacker": ctx.author,
                "enemy": member,
                "stake": stake,
                "bets": {},
                "ends_at": time.time() + DUEL_BET_TIME_SECONDS,
            }
            self.active_duels[guild_id] = duel

            ends_at_ts = int(duel["ends_at"])
            embed_duelo = discord.Embed(
                title=f"🔥 ¡DUELO EN MARCHA: {ctx.author.display_name.upper()} VS {member.display_name.upper()}!",
                description=(
                    f"💥 ¡La campana sonó! Ambos gladiadores pusieron **{stake:,} {CURRENCY_SYMBOL}** cada uno.\n\n"
                    f"🏆 **Bolsa del vencedor:** **{stake * 2:,} {CURRENCY_SYMBOL}**\n"
                    f"⏳ **Tiempo para apostar:** Termina <t:{ends_at_ts}:R> (a las <t:{ends_at_ts}:T>)\n\n"
                    f"🎲 **¿A quién le vas?**\n"
                    f"Cualquier vecino del servidor puede apostar simplemente con:\n"
                    f"`{ctx.prefix}bet {ctx.author.display_name} <monto>` o `{ctx.prefix}bet {member.display_name} <monto>`\n"
                    f"*(¡Un solo duelo a la vez, no necesitas ningún ID!)*"
                ),
                color=discord.Color.gold()
            )
            if gif_pelea:
                embed_duelo.set_image(url=gif_pelea)
            embed_duelo.set_footer(text="Todo Spanish Harlem se acerca a mirar. ¡Hagan sus apuestas!")

            await ctx.send(
                content=f"@everyone ⚔️ ¡Comenzó el duelo entre {ctx.author.mention} y {member.mention}! ¡Apuestas abiertas: terminan <t:{ends_at_ts}:R>!",
                embed=embed_duelo,
                allowed_mentions=discord.AllowedMentions(everyone=True, users=True)
            )

            asyncio.create_task(self._resolve_duel(guild_id))

        except Exception as e:
            self.pending_challenges.discard(guild_id)
            raise e

    async def _resolve_duel(self, guild_id: int) -> None:
        """Resuelve el combate al finalizar el tiempo de apuestas y liquida premios."""
        duel = self.active_duels.get(guild_id)
        if duel is None:
            return

        # Esperar a que culmine el tiempo estipulado de apuestas
        await asyncio.sleep(max(0, duel["ends_at"] - time.time()))
        duel = self.active_duels.pop(guild_id, None)
        if duel is None:
            return

        channel = duel["channel"]
        attacker = duel["attacker"]
        enemy = duel["enemy"]
        stake = duel["stake"]

        winner = random.choice([attacker, enemy])
        loser = enemy if winner.id == attacker.id else attacker
        loser_id = loser.id
        duel_pool = stake * 2

        winning_bets = [bet for bet in duel["bets"].values() if bet["side_id"] == winner.id]
        losing_bets = [bet for bet in duel["bets"].values() if bet["side_id"] == loser_id]
        losing_pool = sum(bet["amount"] for bet in losing_bets)
        winning_total = sum(bet["amount"] for bet in winning_bets)

        payouts_info = []

        async with self.db.lock:
            winner_data = self.db.get_user_data(winner.id)
            winner_data["wallet"] += duel_pool

            loser_data = self.db.get_user_data(loser_id)
            loser_data["last_loss"] = {
                "amount": stake,
                "game": f"duelo contra {winner.display_name}",
                "timestamp": time.time(),
                "reverted": False,
            }

            if winning_bets:
                for bet in winning_bets:
                    bettor_data = self.db.get_user_data(bet["user"].id)
                    if losing_pool > 0:
                        ganancia_extra = int(losing_pool * bet["amount"] / winning_total) if winning_total > 0 else 0
                    else:
                        # Si no hubo contra-apostantes, recibe un porcentaje de ganancia sobre su apuesta
                        ganancia_extra = max(1, int(bet["amount"] * DUEL_UNOPPOSED_PROFIT_PERCENT))

                    retorno_total = bet["amount"] + ganancia_extra
                    bettor_data["wallet"] += retorno_total
                    payouts_info.append({
                        "user": bet["user"],
                        "won": True,
                        "bet": bet["amount"],
                        "profit": ganancia_extra,
                        "total": retorno_total
                    })
            else:
                # Si nadie le aposto al ganador, el ganador del duelo se queda con el pozo perdedor
                winner_data["wallet"] += losing_pool

            for bet in losing_bets:
                bettor_data = self.db.get_user_data(bet["user"].id)
                bettor_data["last_loss"] = {
                    "amount": bet["amount"],
                    "game": f"apuesta en duelo ({loser.display_name})",
                    "timestamp": time.time(),
                    "reverted": False,
                }
                payouts_info.append({
                    "user": bet["user"],
                    "won": False,
                    "bet": bet["amount"],
                    "profit": -bet["amount"],
                    "total": 0
                })

            await self.db.save()

        # Sincronizar el rol del mas millonario tras el cambio de riquezas
        if channel.guild:
            await self.actualizar_rol_millonario(channel.guild, announce_channel=channel)

        # Buscar GIF de KO o victoria en Giphy
        gif_victoria = await self._obtener_gif(["anime ko", "knockout punch", "winner fight"])

        embed_res = discord.Embed(
            title=f"🏆 ¡VICTORIA DE {winner.display_name.upper()} EN EL COMBATE!",
            description=(
                f"💥 ¡Tremendo derechazo de piedra! **{winner.mention}** mandó a dormir a **{loser.mention}**.\n\n"
                f"👑 **Premio del campeón:** **+{duel_pool:,} {CURRENCY_SYMBOL}**\n"
            ),
            color=discord.Color.green()
        )
        if not winning_bets and losing_pool > 0:
            embed_res.description += f"🎁 *(Nadie apostó por {winner.display_name}, ¡así que también se llevó el pozo de apuestas de **+{losing_pool:,} {CURRENCY_SYMBOL}**!)*\n"
        elif winning_bets and losing_pool == 0:
            embed_res.description += f"🎁 *(Como no hubo contra-apostantes, la banca otorgó un bono del {int(DUEL_UNOPPOSED_PROFIT_PERCENT * 100)}% de ganancia a quienes acertaron al ganador.)*\n"

        # Listado detallado de apostadores
        if payouts_info:
            ganadores_str = [
                f"• {p['user'].mention}: **+{p['profit']:,} {CURRENCY_SYMBOL}** *(Devuelto: {p['total']:,})*"
                for p in payouts_info if p["won"]
            ]
            perdedores_str = [
                f"• {p['user'].mention}: **-{p['bet']:,} {CURRENCY_SYMBOL}**"
                for p in payouts_info if not p["won"]
            ]

            if ganadores_str:
                embed_res.add_field(name="🎉 Apostadores Ganadores", value="\n".join(ganadores_str), inline=False)
            if perdedores_str:
                embed_res.add_field(name="💀 Apostadores Perdedores", value="\n".join(perdedores_str), inline=False)
        else:
            embed_res.add_field(name="🎲 Apuestas Externas", value="Nadie de la tribuna se animó a poner fichas en este combate.", inline=False)

        if gif_victoria:
            embed_res.set_image(url=gif_victoria)

        embed_res.set_footer(text="Carlos always says: the street always picks a winner.")

        # Notificacion con @everyone y mencion a los apostadores
        notification_text = f"@everyone 📢 ¡El duelo ha terminado! Ganador: {winner.mention}"
        if payouts_info:
            resumen_pings = " | " + " ".join(
                f"{p['user'].mention} ({'Ganaste' if p['won'] else 'Perdiste'})" for p in payouts_info
            )
            # Evitar exceder el limite de 2000 caracteres de Discord
            if len(notification_text + resumen_pings) < 1950:
                notification_text += resumen_pings

        await channel.send(
            content=notification_text,
            embed=embed_res,
            allowed_mentions=discord.AllowedMentions(everyone=True, users=True)
        )

    @commands.command(name="bet", aliases=["apostar"])
    async def bet(self, ctx: commands.Context, arg1: str, arg2: str):
        """Apuesta por uno de los dos participantes del duelo activo (sin necesidad de ID)."""
        if ctx.guild is None:
            return

        # Restriccion de canal si DUEL_CHANNEL_ID esta configurado
        if DUEL_CHANNEL_ID and ctx.channel.id != DUEL_CHANNEL_ID:
            await ctx.reply(f"❌ Las apuestas de combate solo se pueden realizar en el callejón asignado: <#{DUEL_CHANNEL_ID}>.")
            return

        guild_id = ctx.guild.id
        duel = self.active_duels.get(guild_id)

        if duel is None:
            await ctx.reply("❌ No hay ningún duelo activo en este momento en el barrio.")
            return

        if duel["ends_at"] <= time.time():
            await ctx.reply("❌ Las apuestas para este combate ya cerraron. ¡La pelea está en su clímax!")
            return

        # Flexibilidad en el orden de argumentos: '%bet @jugador 100' o '%bet 100 @jugador'
        member = None
        monto_str = None
        try:
            member = await commands.MemberConverter().convert(ctx, arg1)
            monto_str = arg2
        except commands.BadArgument:
            try:
                member = await commands.MemberConverter().convert(ctx, arg2)
                monto_str = arg1
            except commands.BadArgument:
                await ctx.reply(f"❌ Uso correcto: `{ctx.prefix}bet @jugador <monto>`")
                return

        if member.id not in (duel["attacker"].id, duel["enemy"].id):
            await ctx.reply(
                f"❌ Solo puedes apostar por uno de los combatientes actuales: "
                f"**{duel['attacker'].display_name}** o **{duel['enemy'].display_name}**."
            )
            return

        if ctx.author.id in (duel["attacker"].id, duel["enemy"].id):
            await ctx.reply("❌ Los duelistas no pueden apostar por fuera, ya tienen su bolsa y su honra en juego.")
            return

        if ctx.author.id in duel["bets"]:
            await ctx.reply("❌ Ya tienes una apuesta registrada en este combate. ¡No se puede cambiar de bando!")
            return

        async with self.db.lock:
            bettor_data = self.db.get_user_data(ctx.author.id)
            amount = self._parse_amount(monto_str, bettor_data["wallet"])
            if amount is None or amount <= 0 or amount > bettor_data["wallet"]:
                await ctx.reply(f"❌ Fondos insuficientes en mano. Solo tienes **{bettor_data['wallet']:,} {CURRENCY_SYMBOL}**.")
                return

            bettor_data["wallet"] -= amount
            await self.db.save()

        duel["bets"][ctx.author.id] = {
            "user": ctx.author,
            "side_id": member.id,
            "amount": amount,
        }

        ends_at_ts = int(duel["ends_at"])
        embed_bet = discord.Embed(
            title="🎯 ¡Apuesta Registrada!",
            description=(
                f"{ctx.author.mention} apostó **{amount:,} {CURRENCY_SYMBOL}** por la victoria de **{member.mention}**.\n\n"
                f"💰 **Billetera restante:** **{bettor_data['wallet']:,} {CURRENCY_SYMBOL}**\n"
                f"⏳ **Tiempo restante para apostar:** <t:{ends_at_ts}:R>"
            ),
            color=discord.Color.teal()
        )
        # Registrar actividad de riesgo para el apostador
        is_richest, is_valid_reset, req_bet = await self._registrar_actividad_riesgo(ctx.author.id, amount, ctx.guild)
        if is_richest and not is_valid_reset:
            embed_bet.set_footer(
                text=f"⚠️ [Magnate] Apuesta insuficiente para resetear inactividad. Mínimo: {req_bet:,} {CURRENCY_SYMBOL} ({int(MIN_RISK_BET_PERCENT * 100)}% de tu fortuna)."
            )

        await ctx.reply(embed=embed_bet)
