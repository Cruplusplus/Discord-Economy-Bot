"""
Sistema de eventos aleatorios y automaticos de Ivy en el canal de economia.
Incluye el loop periodico con dynamic anti-abuse Robin Hood escalation,
los triggers para cada tipo de evento barrial y el comando owner '%eventtest'.
"""

import time
import random
import asyncio
from typing import Optional
import discord
from discord.ext import commands, tasks

from .views import SoulDropView, RaidBossView, RiskRouletteView, RobinHoodView
from .lore import IVY_TRIVIA_QUESTIONS
from .config import (
    EVENT_MIN_INTERVAL_MINUTES,
    EVENT_MAX_INTERVAL_MINUTES,
    EVENT_TRIGGER_CHANCE,
    ECONOMY_CHANNEL_ID,
    EVENT_WEIGHT_DROP,
    EVENT_WEIGHT_TRIVIA,
    EVENT_WEIGHT_RAID,
    EVENT_WEIGHT_ROULETTE,
    EVENT_WEIGHT_BOOST,
    EVENT_WEIGHT_ROBIN_HOOD,
    INACTIVITY_STAGE_1_HOURS,
    INACTIVITY_STAGE_2_HOURS,
    INACTIVITY_STAGE_3_HOURS,
    EVENT_WEIGHT_ROBIN_HOOD_STAGE_1,
    EVENT_WEIGHT_ROBIN_HOOD_STAGE_2,
    EVENT_WEIGHT_ROBIN_HOOD_STAGE_3,
    DROP_MIN_SOULS,
    DROP_MAX_SOULS,
    DROP_TIMEOUT_SECONDS,
    TRIVIA_TIMEOUT_SECONDS,
    TRIVIA_REWARD_MIN,
    TRIVIA_REWARD_MAX,
    RAID_HP,
    RAID_TIMEOUT_SECONDS,
    RAID_TOTAL_POOL,
    ROULETTE_WIN_AMOUNT,
    ROULETTE_RISK_WIN_CHANCE,
    ROULETTE_PRISON_DURATION,
    BOOST_DURATION_MINUTES,
    BOOST_MULTIPLIER,
    ROBIN_HOOD_STEAL_PERCENTAGE,
    ROBIN_HOOD_MIN_WALLET,
    CURRENCY_NAME,
    CURRENCY_SYMBOL,
)


class EconomyEventsMixin:
    """Mixin que contiene el bucle de eventos aleatorios de Ivy y sus disparadores."""

    # --------------------------------------------------------------------------
    #                     SISTEMA DE EVENTOS ALEATORIOS (LOOP)
    # --------------------------------------------------------------------------

    async def cog_load(self):
        """Inicia el loop de eventos periódicos al cargar el Cog."""
        if not self.random_events_loop.is_running():
            self.random_events_loop.start()
        try:
            await super().cog_load()
        except AttributeError:
            pass

    async def cog_unload(self):
        """Cancela el loop de eventos al descargar el Cog."""
        self.random_events_loop.cancel()
        try:
            await super().cog_unload()
        except AttributeError:
            pass

    @tasks.loop(minutes=EVENT_MIN_INTERVAL_MINUTES)
    async def random_events_loop(self):
        """Loop periódico que evalúa y dispara eventos aleatorios en el canal configurado."""
        if not ECONOMY_CHANNEL_ID:
            return

        # 1. Recalcular un nuevo intervalo aleatorio e impredecible para el próximo ciclo
        try:
            min_m = max(1, min(EVENT_MIN_INTERVAL_MINUTES, EVENT_MAX_INTERVAL_MINUTES))
            max_m = max(min_m, max(EVENT_MIN_INTERVAL_MINUTES, EVENT_MAX_INTERVAL_MINUTES))
            nuevo_intervalo = random.randint(min_m, max_m)
            self.random_events_loop.change_interval(minutes=nuevo_intervalo)
        except Exception as e:
            print(f"[IVY ECONOMY] Error al recalcular intervalo de eventos: {e}")

        # 2. Evaluación de probabilidad de disparo para este ciclo
        if EVENT_TRIGGER_CHANCE < 1.0 and random.random() > EVENT_TRIGGER_CHANCE:
            return

        if self.active_event:
            return

        channel = self.bot.get_channel(ECONOMY_CHANNEL_ID)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(ECONOMY_CHANNEL_ID)
            except Exception:
                return

        # 3. Calcular peso dinámico de Robin Hood según la inactividad del Más Millonario
        guild = getattr(channel, "guild", None)
        robin_weight = EVENT_WEIGHT_ROBIN_HOOD
        if guild:
            richest_member, richest_total = await self._get_top_wealthy_member(guild)
            if richest_member and richest_total >= ROBIN_HOOD_MIN_WALLET:
                async with self.db.lock:
                    user_data = self.db.get_user_data(richest_member.id)
                    last_gamble = user_data.get("last_gamble", time.time())

                idle_hours = max(0.0, (time.time() - last_gamble) / 3600.0)

                if idle_hours >= INACTIVITY_STAGE_3_HOURS:
                    robin_weight = EVENT_WEIGHT_ROBIN_HOOD_STAGE_3
                elif idle_hours >= INACTIVITY_STAGE_2_HOURS:
                    robin_weight = EVENT_WEIGHT_ROBIN_HOOD_STAGE_2
                elif idle_hours >= INACTIVITY_STAGE_1_HOURS:
                    robin_weight = EVENT_WEIGHT_ROBIN_HOOD_STAGE_1
                else:
                    robin_weight = EVENT_WEIGHT_ROBIN_HOOD

        # Distribuir el restante equitativamente entre los otros 4 eventos manteniendo Boost en su peso
        boost_weight = EVENT_WEIGHT_BOOST
        remaining_pool = max(0.0, 100.0 - robin_weight - boost_weight)
        other_event_weight = remaining_pool / 4.0

        eventos = [
            self._trigger_soul_drop,
            self._trigger_trivia,
            self._trigger_raid,
            self._trigger_roulette,
            self._trigger_boost,
            self._trigger_robin_hood,
        ]

        pesos = [
            other_event_weight,
            other_event_weight,
            other_event_weight,
            other_event_weight,
            boost_weight,
            robin_weight,
        ]

        evento_seleccionado = random.choices(eventos, weights=pesos, k=1)[0]
        try:
            self.active_event = True
            await evento_seleccionado(channel)
        except Exception as e:
            print(f"[IVY ECONOMY] Error al ejecutar evento aleatorio {evento_seleccionado.__name__}: {e}")
        finally:
            self.active_event = False

    @random_events_loop.before_loop
    async def before_random_events_loop(self):
        await self.bot.wait_until_ready()

    # --- Métodos disparadores de eventos ---

    async def _trigger_soul_drop(self, channel: discord.abc.Messageable):
        """1. Drop de almas (Reflejos con botón UI)."""
        amount = random.randint(DROP_MIN_SOULS, DROP_MAX_SOULS)
        view = SoulDropView(self, amount)
        deadline = int(time.time() + DROP_TIMEOUT_SECONDS)

        embed = discord.Embed(
            title="💎 ¡ALIJO DE ALMAS EN EL CALLEJÓN!",
            description=(
                f"¡Una fuerte corriente de aire tiró un alijo de almas desde lo alto de la catedral de Spanish Harlem!\n\n"
                f"💰 **Contenido del alijo:** **{amount:,} {CURRENCY_NAME} {CURRENCY_SYMBOL}**\n"
                f"⏳ **Tiempo para agarrarlo:** <t:{deadline}:R>\n\n"
                f"¡El vecino más rápido en cliquear el botón se queda con todo!"
            ),
            color=discord.Color.blue()
        )
        embed.set_footer(text="Being a gargoyle means spotting the shinies before anyone else!")
        msg = await channel.send(
            content="@everyone 💎 ¡Cayó un alijo de almas en el callejón de Spanish Harlem!",
            embed=embed,
            view=view,
            allowed_mentions=discord.AllowedMentions(everyone=True)
        )
        view.message = msg

    async def _trigger_trivia(self, channel: discord.abc.Messageable):
        """2. Trivia callejera de Ivy."""
        trivia_item = random.choice(IVY_TRIVIA_QUESTIONS)
        pregunta = trivia_item["pregunta"]
        respuestas_validas = [r.lower().strip() for r in trivia_item["respuestas"]]
        pista = trivia_item.get("pista", "")
        recompensa = random.randint(TRIVIA_REWARD_MIN, TRIVIA_REWARD_MAX)
        deadline = int(time.time() + TRIVIA_TIMEOUT_SECONDS)

        embed = discord.Embed(
            title="🧠 ¡TRIVIA CALLEJERA DE IVY!",
            description=(
                f"Ivy se acomodó en la cornisa y les lanza un acertijo al barrio:\n\n"
                f"**❓ Pregunta:**\n>>> *\"{pregunta}\"*\n\n"
                f"💰 **Premio para el más despierto:** **+{recompensa:,} {CURRENCY_NAME} {CURRENCY_SYMBOL}**\n"
                f"⏳ **Tiempo límite:** <t:{deadline}:R>\n"
                f"📝 *Escribe tu respuesta directamente en este canal.*"
            ),
            color=discord.Color.purple()
        )
        if pista:
            embed.set_footer(text=f"Pista de Ivy: {pista}")
        else:
            embed.set_footer(text="¡El primero en responder correctamente se lleva las almas!")

        await channel.send(
            content="@everyone 🧠 ¡Trivia callejera de Ivy en marcha! ¡El primero en acertar se lleva las almas!",
            embed=embed,
            allowed_mentions=discord.AllowedMentions(everyone=True)
        )

        def check(m: discord.Message) -> bool:
            return m.channel.id == channel.id and not m.author.bot

        start_time = time.time()
        winner_msg: Optional[discord.Message] = None

        while time.time() - start_time < TRIVIA_TIMEOUT_SECONDS:
            remaining = max(1, int(TRIVIA_TIMEOUT_SECONDS - (time.time() - start_time)))
            try:
                msg = await self.bot.wait_for("message", timeout=remaining, check=check)
            except asyncio.TimeoutError:
                break

            clean_content = msg.content.lower().strip()
            if any(ans == clean_content or (len(ans) > 3 and ans in clean_content) for ans in respuestas_validas):
                winner_msg = msg
                break

        if winner_msg is not None:
            async with self.db.lock:
                u_data = self.db.get_user_data(winner_msg.author.id)
                u_data["wallet"] += recompensa
                await self.db.save()

            embed_win = discord.Embed(
                title="🎉 ¡CLAVASTE LA RESPUESTA, CHACHO!",
                description=(
                    f"¡Exacto! **{winner_msg.author.mention}** fue el más rápido de mente y acertó con:\n"
                    f"> **\"{winner_msg.content}\"**\n\n"
                    f"Ivy le arroja **+{recompensa:,} {CURRENCY_NAME} {CURRENCY_SYMBOL}** desde la cornisa.\n"
                    f"Billetera: **{u_data['wallet']:,} {CURRENCY_SYMBOL}**"
                ),
                color=discord.Color.green()
            )
            embed_win.set_thumbnail(url=winner_msg.author.display_avatar.url)
            embed_win.set_footer(text="Being quick on your feet is good, but being quick in the head is better!")
            await winner_msg.reply(embed=embed_win)

            if winner_msg.guild:
                await self.actualizar_rol_millonario(winner_msg.guild, announce_channel=channel)
        else:
            correct_display = respuestas_validas[0].capitalize()
            embed_timeout = discord.Embed(
                title="⌛ ¡Se Congelaron las Neuronas!",
                description=(
                    f"Nadie acertó a tiempo, che... Parece que hoy todos tienen cerebro de piedra.\n\n"
                    f"💡 **La respuesta correcta era:** **{correct_display}**"
                ),
                color=discord.Color.dark_grey()
            )
            embed_timeout.set_footer(text="Carlos always says: think first, speak second.")
            await channel.send(embed=embed_timeout)

    async def _trigger_raid(self, channel: discord.abc.Messageable):
        """3. Emboscada / Raid cooperativo."""
        view = RaidBossView(self)
        deadline = int(time.time() + RAID_TIMEOUT_SECONDS)

        embed = discord.Embed(
            title="🚨 ¡EMBOSCADA DEL SINDICATO MENDOZA!",
            description=(
                f"¡Una patrulla de matones del Sindicato Mendoza apareció en Spanish Harlem buscando problemas!\n\n"
                f"❤️ **Vida del matón:** {view._generate_hp_bar()}\n"
                f"💰 **Pozo cooperativo:** **{RAID_TOTAL_POOL:,} {CURRENCY_SYMBOL}** (se reparte entre todos los combatientes)\n"
                f"⏳ **Tiempo para derrotarlos:** <t:{deadline}:R>\n\n"
                f"⚠️ *¡Se necesitan **{RAID_HP} vecinos distintos** golpeando juntos para rodearlos y bajarlos!*"
            ),
            color=discord.Color.red()
        )
        embed.set_footer(text="Carlos always says: strength in numbers, especially against Mendoza.")
        msg = await channel.send(
            content="@everyone 🚨 ¡Emboscada del Sindicato Mendoza! ¡A defender el barrio entre todos!",
            embed=embed,
            view=view,
            allowed_mentions=discord.AllowedMentions(everyone=True)
        )
        view.message = msg

    async def _trigger_roulette(self, channel: discord.abc.Messageable):
        """4. El desafío riesgoso de Ivy (Riesgo vs. Recompensa)."""
        view = RiskRouletteView(self)
        deadline = int(time.time() + DROP_TIMEOUT_SECONDS)

        embed = discord.Embed(
            title="🔥 ¡EL DESAFÍO RIESGOSO DE IVY!",
            description=(
                f"Ivy aterriza con un fajo de almas en una mano y unas esposas policiales en la otra:\n\n"
                f"*«Oigan, chachos... Tengo **{ROULETTE_WIN_AMOUNT:,} {CURRENCY_SYMBOL}** para quien tenga agallas. "
                f"Tiras los dados conmigo: un **{int(ROULETTE_RISK_WIN_CHANCE * 100)}%** de llevarte el premio, "
                f"o un **{int((1 - ROULETTE_RISK_WIN_CHANCE) * 100)}%** de pasar {ROULETTE_PRISON_DURATION // 60} minutos en el calabozo policial.»*\n\n"
                f"🏆 **Premio si ganas:** **+{ROULETTE_WIN_AMOUNT:,} {CURRENCY_SYMBOL}**\n"
                f"⛓️ **Castigo si pierdes:** **{ROULETTE_PRISON_DURATION // 60} min** en prisión sin chambear\n"
                f"⏳ **Tiempo para aceptar:** <t:{deadline}:R>\n\n"
                f"¿Quién es el primero en arriesgar el pellejo?"
            ),
            color=discord.Color.dark_purple()
        )
        embed.set_footer(text="Fortune favors the bold, but the cells are cold!")
        msg = await channel.send(
            content="@everyone 🔥 ¡Ivy lanzó un desafío riesgoso! ¿Quién es el primero en arriesgar el pellejo?",
            embed=embed,
            view=view,
            allowed_mentions=discord.AllowedMentions(everyone=True)
        )
        view.message = msg

    async def _boost_end_task(self, channel: discord.abc.Messageable, duration_seconds: int):
        """Tarea en segundo plano que avisa cuando finaliza la bonificación de trabajo."""
        await asyncio.sleep(duration_seconds)
        self.work_boost_active = False

        embed_end = discord.Embed(
            title="🍂 La Lluvia de Almas ha Terminado",
            description=(
                f"El cielo de El Barrio vuelve a despejarse y las rondas de `%work` regresan a su paga habitual.\n"
                f"¡Buen laburo a todos los que salieron a ganarse el pan hoy!"
            ),
            color=discord.Color.light_grey()
        )
        embed_end.set_footer(text="Carlos always says: rest is just as important as the hustle.")
        try:
            await channel.send(embed=embed_end)
        except Exception:
            pass

    async def _trigger_boost(self, channel: discord.abc.Messageable):
        """5. Lluvia de almas (Multiplicador temporal de trabajo)."""
        self.work_boost_active = True
        self.work_boost_until = time.time() + (BOOST_DURATION_MINUTES * 60)
        end_ts = int(self.work_boost_until)

        embed = discord.Embed(
            title="🌧️✨ ¡LLUVIA DE ALMAS EN SPANISH HARLEM!",
            description=(
                f"¡Las campanas de la catedral repican y las calles están que hierven de laburo extra!\n\n"
                f"⚡ **Efecto Activo:** Durante los próximos **{BOOST_DURATION_MINUTES} minutos**, "
                f"el comando `%work` paga **x{BOOST_MULTIPLIER:.1f} DE ALMAS**.\n\n"
                f"⏳ **Termina:** <t:{end_ts}:R> (a las <t:{end_ts}:T>)\n\n"
                f"¡Salgan a patrullar las cornisas y a cuidar el barrio antes de que pare la lluvia!"
            ),
            color=discord.Color.gold()
        )
        embed.set_footer(text="¡Aprovechen la bonificación antes de que se enfríe el asfalto!")
        await channel.send(
            content=f"@everyone 🌧️✨ ¡Lluvia de almas activa! ¡El comando %work paga x{BOOST_MULTIPLIER:.1f} durante {BOOST_DURATION_MINUTES} minutos!",
            embed=embed,
            allowed_mentions=discord.AllowedMentions(everyone=True)
        )

        asyncio.create_task(self._boost_end_task(channel, BOOST_DURATION_MINUTES * 60))

    async def _trigger_robin_hood(self, channel: discord.abc.Messageable):
        """6. Robin Hood (Impuesto a la gárgola millonaria)."""
        guild = getattr(channel, "guild", None)
        if guild is None:
            return

        richest_member = await self.actualizar_rol_millonario(guild)
        if richest_member is None:
            await self._trigger_soul_drop(channel)
            return

        async with self.db.lock:
            richest_data = self.db.get_user_data(richest_member.id)
            current_wallet = richest_data.get("wallet", 0)
            current_bank = richest_data.get("bank", 0)
            total_wealth = current_wallet + current_bank

            if total_wealth < ROBIN_HOOD_MIN_WALLET:
                embed_safe = discord.Embed(
                    title="🏹 Robin Hood Pasó de Largo...",
                    description=(
                        f"Ivy fue a inspeccionar la fortuna de **{richest_member.display_name}** para redistribuir un poco, "
                        f"pero vio que tiene menos de **{ROBIN_HOOD_MIN_WALLET:,} {CURRENCY_SYMBOL}** de patrimonio total.\n\n"
                        f"¡Esta vez el magnate zafó del impuesto barrial!"
                    ),
                    color=discord.Color.blue()
                )
                embed_safe.set_footer(text="Ivy solo cobra impuestos a quienes realmente les sobra.")
                await channel.send(embed=embed_safe)
                return

            stolen_amount = int(round(total_wealth * ROBIN_HOOD_STEAL_PERCENTAGE))
            if stolen_amount <= 0:
                return

            # Deducir de la billetera primero; si no alcanza, abrir la caja fuerte del banco
            if current_wallet >= stolen_amount:
                richest_data["wallet"] -= stolen_amount
                origen_robo = "de su billetera"
            else:
                from_wallet = current_wallet
                from_bank = stolen_amount - from_wallet
                richest_data["wallet"] = 0
                richest_data["bank"] = max(0, current_bank - from_bank)
                if from_wallet > 0:
                    origen_robo = f"({from_wallet:,} {CURRENCY_SYMBOL} de su mano y {from_bank:,} {CURRENCY_SYMBOL} de su caja fuerte del banco)"
                else:
                    origen_robo = "directamente de su caja fuerte en el banco"

            await self.db.save()

        idle_hours = max(0.0, (time.time() - richest_data.get("last_gamble", time.time())) / 3600.0)
        motivo_inactividad = ""
        if idle_hours >= INACTIVITY_STAGE_1_HOURS:
            motivo_inactividad = (
                f"\n⚠️ **Causa del ataque:** ¡El magnate lleva **{int(idle_hours)} horas** sin arriesgar almas en la calle!\n"
                f"*«Carlos always says: las almas estancadas crían moho y atraen a los amigos de lo ajeno.»*\n"
            )

        deadline = int(time.time() + DROP_TIMEOUT_SECONDS)
        view = RobinHoodView(self, richest_member, stolen_amount)
        embed = discord.Embed(
            title="🏹 ¡IMPUESTO A LA OPULENCIA: ROBIN HOOD CALLEJERO!",
            description=(
                f"Ivy se coló silenciosa como gárgola en las propiedades de **{richest_member.mention}** y le sustrajo un **{int(ROBIN_HOOD_STEAL_PERCENTAGE * 100)}%** "
                f"de su fortuna {origen_robo} por andar acaparando almas.\n"
                f"{motivo_inactividad}\n"
                f"💰 **Bolsa redistribuida:** **{stolen_amount:,} {CURRENCY_NAME} {CURRENCY_SYMBOL}**\n"
                f"🚫 **Restricción:** {richest_member.mention} no puede recoger su propia bolsa.\n"
                f"⏳ **Tiempo para agarrarla:** <t:{deadline}:R>\n\n"
                f"¡El primer vecino que cliquee el botón se queda con el botín!"
            ),
            color=discord.Color.dark_green()
        )
        embed.set_footer(text="Being wealthy is fine, but in El Barrio, everyone eats. ¡Ni la caja del banco se salva!")
        msg = await channel.send(
            content=f"@everyone 🏹 ¡Robin Hood callejero! ¡Ivy le cobró impuestos a {richest_member.mention} y soltó la bolsa de almas!",
            embed=embed,
            view=view,
            allowed_mentions=discord.AllowedMentions(everyone=True, users=True)
        )
        view.message = msg

    # --- Comando de prueba para Owners ---

    @commands.command(name="eventtest", hidden=True)
    @commands.is_owner()
    async def eventtest(self, ctx: commands.Context, tipo: Optional[str] = None):
        """[Owner] Dispara inmediatamente un evento aleatorio o específico para pruebas."""
        tipos = {
            "drop": self._trigger_soul_drop,
            "trivia": self._trigger_trivia,
            "raid": self._trigger_raid,
            "desafio": self._trigger_roulette,
            "ruleta": self._trigger_roulette,
            "lluvia": self._trigger_boost,
            "robin": self._trigger_robin_hood,
        }

        if tipo:
            tipo_clean = tipo.lower().strip()
            handler = tipos.get(tipo_clean)
            if not handler:
                validos = ", ".join(tipos.keys())
                await ctx.reply(f"❌ Tipo no válido. Opciones: `{validos}`")
                return
            await ctx.reply(f"🚀 Disparando evento `{tipo_clean}`...")
            await handler(ctx.channel)
        else:
            eventos_test = [
                self._trigger_soul_drop,
                self._trigger_trivia,
                self._trigger_raid,
                self._trigger_roulette,
                self._trigger_boost,
                self._trigger_robin_hood,
            ]
            pesos_test = [
                EVENT_WEIGHT_DROP,
                EVENT_WEIGHT_TRIVIA,
                EVENT_WEIGHT_RAID,
                EVENT_WEIGHT_ROULETTE,
                EVENT_WEIGHT_BOOST,
                EVENT_WEIGHT_ROBIN_HOOD,
            ]
            handler = random.choices(eventos_test, weights=pesos_test, k=1)[0]
            await ctx.reply("🎲 Disparando un evento al azar para pruebas...")
            await handler(ctx.channel)
