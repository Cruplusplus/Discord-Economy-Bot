"""
Cog principal de Economia para Discord.
Personificado con la voz, lore y personalidad de Ivy (Deadlock).
Hereda de EconomyEventsMixin y EconomyDuelsMixin para conformar el sistema completo.
"""

import time
import random
import aiohttp
from typing import Optional, Tuple, Dict, Any
import discord
from discord.ext import commands

from .config import (
    DATA_FILE_PATH,
    CURRENCY_NAME,
    CURRENCY_SYMBOL,
    WORK_COOLDOWN,
    WORK_MIN_REWARD,
    WORK_MAX_REWARD,
    BOOST_MULTIPLIER,
    COIN_MULTIPLIER,
    COIN_FACES,
    RULETA_WEIGHT_ROJO,
    RULETA_WEIGHT_NEGRO,
    RULETA_WEIGHT_VERDE,
    RULETA_PAYOUT_ROJO,
    RULETA_PAYOUT_NEGRO,
    RULETA_PAYOUT_VERDE,
    RULETA_COLOR_MAP,
    ROB_COOLDOWN,
    ROB_VICTIM_MIN_WALLET,
    ROB_DICE_MIN,
    ROB_DICE_MAX,
    ROB_FAIL_THRESHOLD,
    ROB_FAIL_FINE,
    PRISON_DURATION,
    RICHEST_ROLE_ID,
    RICHEST_ROLE_NAME,
    RICHEST_ANNOUNCE_CHANNEL_ID,
    GIPHY_API_KEY,
    MIN_RISK_BET_PERCENT,
    MIN_RISK_BET_FLOOR,
    ROBIN_HOOD_MIN_WALLET,
    INACTIVITY_STAGE_1_HOURS,
)
from .lore import (
    IVY_WORK_ACTIVITIES,
    IVY_WORK_COOLDOWN_QUOTES,
    IVY_PRISON_WARNING_QUOTES,
    IVY_COIN_WIN_QUOTES,
    IVY_COIN_LOSS_QUOTES,
    IVY_RULETA_WIN_NORMAL_QUOTES,
    IVY_RULETA_WIN_VERDE_QUOTES,
    IVY_RULETA_LOSS_QUOTES,
    IVY_ROB_FAIL_QUOTES,
    IVY_ROB_SUCCESS_QUOTES,
)
from .database import DataManager
from .events import EconomyEventsMixin
from .duels import EconomyDuelsMixin


class Economy(EconomyEventsMixin, EconomyDuelsMixin, commands.Cog):
    """Modulo de economia y timba personificado por Ivy de Deadlock."""

    def __init__(self, bot: commands.Bot):
        super().__init__()
        self.bot = bot
        self.db = DataManager(DATA_FILE_PATH)
        self.active_duels: Dict[int, Dict[str, Any]] = {}
        self.pending_challenges: set[int] = set()
        self.work_boost_active: bool = False
        self.work_boost_until: float = 0.0
        self.active_event: bool = False
        self._top_leader_cache: Dict[int, Tuple[int, int]] = {}
        self._not_in_guild_cache: Dict[int, set[int]] = {}

    # --------------------------------------------------------------------------
    #                         METODOS AUXILIARES
    # --------------------------------------------------------------------------

    async def _obtener_gif(self, tags=None) -> Optional[str]:
        """Busca un GIF temático en Giphy para los duelos."""
        if isinstance(tags, list):
            q = " ".join(tags)
        elif isinstance(tags, str):
            q = tags
        else:
            q = "fight"

        random_offset = random.randint(0, 25)
        url = "https://api.giphy.com/v1/gifs/search"
        params = {
            "api_key": GIPHY_API_KEY,
            "q": q,
            "limit": 10,
            "offset": random_offset,
            "rating": "r"
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        resultados = data.get("data", [])
                        if resultados:
                            elegido = random.choice(resultados)
                            return elegido["images"]["original"]["url"]
        except Exception as e:
            print(f"[IVY ECONOMY] Error al conectar con Giphy para duelo: {e}")

        return None

    def _is_in_prison(self, user_data: Dict[str, Any]) -> Tuple[bool, int]:
        """Determina si el usuario está preso y cuántos segundos le restan."""
        prison_until = user_data.get("prison_until", 0.0)
        now = time.time()
        if prison_until > now:
            return True, int(prison_until - now)
        return False, 0

    def _format_time(self, seconds: int) -> str:
        """Formatea segundos a un formato amigable 'Xm Ys'."""
        minutes, secs = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours > 0:
            return f"{hours}h {minutes}m {secs}s"
        elif minutes > 0:
            return f"{minutes}m {secs}s"
        return f"{secs}s"

    def _parse_amount(self, amount_str: str, current_balance: int) -> Optional[int]:
        """Parsea el monto ingresado admitiendo 'all' o 'todo' para mover el total como entero."""
        amount_str = amount_str.strip().lower()
        if amount_str in ("all", "todo", "max"):
            return int(round(current_balance))

        try:
            val = int(amount_str)
            if val <= 0:
                return None
            return val
        except ValueError:
            return None

    # --------------------------------------------------------------------------
    #              SISTEMA DINAMICO: ROL DEL MAS MILLONARIO (TOP 1)
    # --------------------------------------------------------------------------

    def _get_richest_role(self, guild: discord.Guild) -> Optional[discord.Role]:
        """Obtiene el rol configurado para el Más Millonario por ID o por Nombre."""
        if guild is None:
            return None
        if RICHEST_ROLE_ID > 0:
            role = guild.get_role(RICHEST_ROLE_ID)
            if role:
                return role
        if RICHEST_ROLE_NAME:
            return discord.utils.get(guild.roles, name=RICHEST_ROLE_NAME)
        return None

    @staticmethod
    def _safe_remove_cached_role(member: Optional[discord.Member], role_id: int):
        if member is None:
            return
        roles_attr = getattr(member, "_roles", None)
        if roles_attr is not None:
            try:
                if hasattr(roles_attr, "remove"):
                    try:
                        roles_attr.remove(role_id)
                    except (ValueError, KeyError):
                        pass
                elif hasattr(roles_attr, "discard"):
                    roles_attr.discard(role_id)
            except Exception:
                pass

    @staticmethod
    def _safe_add_cached_role(member: Optional[discord.Member], role_id: int):
        if member is None:
            return
        roles_attr = getattr(member, "_roles", None)
        if roles_attr is not None:
            try:
                if hasattr(roles_attr, "has") and hasattr(roles_attr, "add"):
                    if not roles_attr.has(role_id):
                        roles_attr.add(role_id)
                elif hasattr(roles_attr, "add"):
                    roles_attr.add(role_id)
                elif hasattr(roles_attr, "append"):
                    if role_id not in roles_attr:
                        roles_attr.append(role_id)
            except Exception:
                pass

    async def _get_top_wealthy_member(self, guild: Optional[discord.Guild]) -> Tuple[Optional[discord.Member], int]:
        """Encuentra al miembro no-bot con mayor fortuna total (wallet + bank) dentro del servidor de forma optimizada."""
        if guild is None:
            return None, 0

        async with self.db.lock:
            all_users = self.db.get_all_users()

        # Filtrar y ordenar candidatos por patrimonio total descendente
        candidates = []
        for uid_str, data in all_users.items():
            try:
                user_id = int(uid_str)
            except ValueError:
                continue

            total = data.get("wallet", 0) + data.get("bank", 0)
            if total > 0:
                candidates.append((user_id, total))

        candidates.sort(key=lambda x: x[1], reverse=True)

        not_in_guild = self._not_in_guild_cache.setdefault(guild.id, set())

        for user_id, total in candidates:
            if user_id in not_in_guild:
                continue

            member = guild.get_member(user_id)
            if member is None:
                try:
                    member = await guild.fetch_member(user_id)
                except discord.NotFound:
                    not_in_guild.add(user_id)
                    member = None
                except discord.HTTPException:
                    member = None

            if member is not None and not member.bot:
                # Early Exit O(1): al estar ordenados descendente, el primero valido es indiscutiblemente el lider
                self._top_leader_cache[guild.id] = (member.id, total)
                return member, total

        self._top_leader_cache[guild.id] = (0, 0)
        return None, 0

    def _evaluar_riesgo_apostador(
        self,
        user_id: int,
        bet_amount: int,
        user_total: int,
        guild: Optional[discord.Guild]
    ) -> Tuple[bool, bool, int]:
        """
        Evalua en memoria (0 llamadas de red) si una apuesta resetea el reloj de inactividad
        del apostador, aplicando la regla de riesgo para el Mas Millonario.
        Retorna:
            (es_el_millonario, apuesta_valida_para_resetear, apuesta_minima_requerida)
        """
        if guild is None:
            return False, True, 0

        cached_leader_id, cached_wealth = self._top_leader_cache.get(guild.id, (0, 0))
        is_richest = (cached_leader_id == user_id and user_total > 0)

        if not is_richest:
            return False, True, 0

        required_bet = max(MIN_RISK_BET_FLOOR, int(round(user_total * MIN_RISK_BET_PERCENT)))
        is_valid = (bet_amount >= required_bet)
        return True, is_valid, required_bet

    async def _registrar_actividad_riesgo(
        self,
        user_id: int,
        bet_amount: int,
        guild: Optional[discord.Guild]
    ) -> Tuple[bool, bool, int]:
        """
        Registra la actividad de apuesta para el usuario.
        Aprovecha la cache en memoria y solo guarda en disco si hubo cambio.
        """
        if guild is None:
            return False, True, 0

        if guild.id not in self._top_leader_cache:
            await self._get_top_wealthy_member(guild)

        async with self.db.lock:
            user_data = self.db.get_user_data(user_id)
            user_total = user_data.get("wallet", 0) + user_data.get("bank", 0)

            cached_leader_id, cached_wealth = self._top_leader_cache.get(guild.id, (0, 0))
            if cached_leader_id != user_id and user_total > cached_wealth and user_total > 0:
                top_member, top_total = await self._get_top_wealthy_member(guild)
                is_richest = (top_member is not None and top_member.id == user_id and top_total > 0)
            else:
                is_richest = (cached_leader_id == user_id and user_total > 0)

            if not is_richest:
                user_data["last_gamble"] = time.time()
                await self.db.save()
                return False, True, 0

            # Es el Mas Millonario: calcular la apuesta minima requerida (Skin in the game)
            required_bet = max(MIN_RISK_BET_FLOOR, int(round(user_total * MIN_RISK_BET_PERCENT)))

            if bet_amount >= required_bet:
                user_data["last_gamble"] = time.time()
                await self.db.save()
                return True, True, required_bet
            else:
                return True, False, required_bet

    async def actualizar_rol_millonario(
        self,
        guild: Optional[discord.Guild],
        announce_channel: Optional[discord.abc.Messageable] = None
    ) -> Optional[discord.Member]:
        """
        Determina automáticamente quién es el usuario con más patrimonio total (mano + banco)
        en el servidor y le transfiere el rol exclusivo de Millonario/Magnate si hubo un cambio.
        """
        if guild is None:
            return None

        # 1. Obtener el rol configurado
        role = self._get_richest_role(guild)
        if role is None:
            return None

        # 2. Determinar quién es el usuario con mayor fortuna en stats.json dentro del servidor
        best_member, max_wealth = await self._get_top_wealthy_member(guild)

        if best_member is None:
            return None

        # Asegurar actualización de la caché del líder
        self._top_leader_cache[guild.id] = (best_member.id, max_wealth)

        # 3. Verificar los portadores actuales del rol
        current_holders = [m for m in role.members]

        # Si el líder actual ya tiene el rol y es el único, no realizamos llamadas innecesarias a la API
        if len(current_holders) == 1 and current_holders[0].id == best_member.id:
            return best_member

        # 4. Remover el rol de cualquier portador anterior
        previous_leader = None
        for old_member in current_holders:
            if old_member.id != best_member.id:
                previous_leader = old_member
                try:
                    await old_member.remove_roles(
                        role,
                        reason="Perdió el puesto del Más Millonario de Spanish Harlem."
                    )
                    cached_old = guild.get_member(old_member.id)
                    self._safe_remove_cached_role(cached_old, role.id)
                    self._safe_remove_cached_role(old_member, role.id)
                except discord.Forbidden:
                    print(f"[IVY ECONOMY] Sin permisos para remover el rol '{role.name}' a {old_member.display_name}. Verifica la jerarquía de roles.")
                except discord.HTTPException as e:
                    print(f"[IVY ECONOMY] Error de Discord al remover rol: {e}")

        # 5. Asignar el rol al nuevo líder si aún no lo tiene
        if role not in best_member.roles:
            try:
                await best_member.add_roles(
                    role,
                    reason="Nuevo Top 1 de la economía (El Más Millonario)."
                )
                cached_best = guild.get_member(best_member.id)
                self._safe_add_cached_role(cached_best, role.id)
                self._safe_add_cached_role(best_member, role.id)

                # Otorgar gracia de 24 horas al nuevo líder para que no herede inactividad previa
                async with self.db.lock:
                    new_leader_data = self.db.get_user_data(best_member.id)
                    new_leader_data["last_gamble"] = time.time()
                    await self.db.save()
            except discord.Forbidden:
                print(f"[IVY ECONOMY] Sin permisos de jerarquía para asignar el rol '{role.name}' a {best_member.display_name}. Coloca el rol del bot por encima de '{role.name}'.")
                return best_member
            except discord.HTTPException as e:
                print(f"[IVY ECONOMY] Error de Discord al asignar rol: {e}")
                return best_member

        return best_member


    @commands.Cog.listener()
    async def on_ready(self):
        """Sincroniza el rol del más millonario al iniciar o reconectar el bot."""
        for guild in self.bot.guilds:
            try:
                await self.actualizar_rol_millonario(guild)
            except Exception as e:
                print(f"[IVY ECONOMY] Error sincronizando rol de millonario en {guild.name}: {e}")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Si un miembro abandona el servidor, agregarlo a no-miembros e invalidar líder si lo era."""
        guild = member.guild
        self._not_in_guild_cache.setdefault(guild.id, set()).add(member.id)
        cached_id, _ = self._top_leader_cache.get(guild.id, (0, 0))
        if cached_id == member.id:
            self._top_leader_cache.pop(guild.id, None)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Si un miembro se une al servidor, quitarlo del conjunto de no-miembros."""
        self._not_in_guild_cache.setdefault(member.guild.id, set()).discard(member.id)

    # --------------------------------------------------------------------------
    #                       COMANDO: WORK / TRABAJAR
    # --------------------------------------------------------------------------

    @commands.command(name="work", aliases=["w", "W", "trabajar", "chambear"])
    async def work(self, ctx: commands.Context):
        """Patrullas Spanish Harlem y haces trabajitos para ganar almas legales."""
        user_id = ctx.author.id

        async with self.db.lock:
            user = self.db.get_user_data(user_id)
            now = time.time()

            # 1. Validación de Cárcel
            in_prison, remaining_prison = self._is_in_prison(user)
            if in_prison:
                time_str = self._format_time(remaining_prison)
                quote = random.choice(IVY_PRISON_WARNING_QUOTES).format(time=time_str)
                embed = discord.Embed(
                    title="🚨 ¡Estás en Cana, Chacho!",
                    description=quote,
                    color=discord.Color.red()
                )
                embed.set_footer(text="Ivy no deja salir a los rateros hasta que cumplan la condena.")
                await ctx.reply(embed=embed)
                return

            # 2. Validación de Cooldown
            last_work = user.get("last_work", 0.0)
            elapsed = now - last_work
            if elapsed < WORK_COOLDOWN:
                remaining_cd = int(WORK_COOLDOWN - elapsed)
                time_str = self._format_time(remaining_cd)
                quote = random.choice(IVY_WORK_COOLDOWN_QUOTES).format(time=time_str)
                embed = discord.Embed(
                    title="🪨 Modo Estatua / Stone Form Activo",
                    description=quote,
                    color=discord.Color.light_grey()
                )
                embed.set_footer(text="Being a statue isn't riveting, but it beats being exhausted!")
                await ctx.reply(embed=embed)
                return

            # 3. Asignación de Recompensa
            base_reward = random.randint(WORK_MIN_REWARD, WORK_MAX_REWARD)
            is_boosted = self.work_boost_active and (now < self.work_boost_until)
            reward = int(round(base_reward * BOOST_MULTIPLIER)) if is_boosted else base_reward

            user["wallet"] += reward
            user["last_work"] = now
            user["stats"]["times_worked"] = user["stats"].get("times_worked", 0) + 1
            await self.db.save()

        action = random.choice(IVY_WORK_ACTIVITIES)
        desc = (
            f"*{action}*\n\n"
            f"Recolectaste **+{reward:,} {CURRENCY_NAME} {CURRENCY_SYMBOL}** por el esfuerzo.\n"
        )
        if is_boosted:
            desc += f"⚡ **¡Bonificación de Lluvia de Almas activa! (x{BOOST_MULTIPLIER:.1f})**\n"
        desc += f"En tus bolsillos ahora tenés: **{user['wallet']:,} {CURRENCY_SYMBOL}**"

        embed = discord.Embed(
            title="✨ ¡Ronda Completada por Spanish Harlem!",
            description=desc,
            color=discord.Color.green()
        )
        embed.set_footer(text=f"Ivy te espera para la próxima ronda en {WORK_COOLDOWN // 60} minutos.")
        await ctx.reply(embed=embed)

        if ctx.guild:
            leader_id, leader_wealth = self._top_leader_cache.get(ctx.guild.id, (0, 0))
            user_total = user["wallet"] + user["bank"]
            if user_id == leader_id or user_total >= leader_wealth:
                await self.actualizar_rol_millonario(ctx.guild, announce_channel=ctx.channel)

    # --------------------------------------------------------------------------
    #                    COMANDO: COIN / CARA O CRUZ
    # --------------------------------------------------------------------------

    @commands.command(name="coin", aliases=["c", "moneda", "flip"])
    async def coin(self, ctx: commands.Context, eleccion: str, monto: str):
        """Tiras una moneda al aire desde lo alto de la cornisa (cara o cruz)."""
        eleccion_clean = eleccion.lower().strip()
        alias_map = {
            "cara": "cara", "c": "cara", "heads": "cara", "h": "cara",
            "cruz": "cruz", "x": "cruz", "tails": "cruz", "t": "cruz"
        }

        if eleccion_clean not in alias_map:
            await ctx.reply(
                f"❌ ¡Ey, chacho! Tienes que elegir **cara** o **cruz**.\n"
                f"*Ejemplo:* `{ctx.prefix}coin cara 50`"
            )
            return

        lado_elegido = alias_map[eleccion_clean]
        user_id = ctx.author.id

        async with self.db.lock:
            user = self.db.get_user_data(user_id)
            wallet = user["wallet"]

            parsed_amount = self._parse_amount(monto, wallet)
            if parsed_amount is None:
                await ctx.reply("❌ Pon un monto válido en números positivos o usa `all` si tienes agallas de gárgola.")
                return

            if parsed_amount > wallet or parsed_amount == 0:
                await ctx.reply(
                    f"❌ ¡Te falta plata en los bolsillos, chacho! Solo tienes **{wallet:,} {CURRENCY_SYMBOL}** en mano."
                )
                return

            # Tirada 50/50
            resultado = random.choice(COIN_FACES)

            if resultado == lado_elegido:
                ganancia = int(parsed_amount * (COIN_MULTIPLIER - 1.0))
                user["wallet"] += ganancia
                user["stats"]["gambles_won"] = user["stats"].get("gambles_won", 0) + 1

                quote = random.choice(IVY_COIN_WIN_QUOTES).format(face=resultado.upper())
                embed = discord.Embed(
                    title=f"🪙 ¡Moneda al Aire: Salió {resultado.upper()}!",
                    description=f"{quote}\n\n"
                                f"🎉 **Ganancia neta:** +{ganancia:,} {CURRENCY_SYMBOL}\n"
                                f"💵 **Billetera actual:** {user['wallet']:,} {CURRENCY_SYMBOL}",
                    color=discord.Color.green()
                )
                embed.set_footer(text="Who says vigilante work doesn't pay the bills?")
            else:
                user["wallet"] -= parsed_amount
                user["stats"]["gambles_lost"] = user["stats"].get("gambles_lost", 0) + 1

                quote = random.choice(IVY_COIN_LOSS_QUOTES).format(face=resultado.upper())
                embed = discord.Embed(
                    title=f"🪙 Moneda al Aire: Salió {resultado.upper()}",
                    description=f"{quote}\n\n"
                                f"💸 **Pérdida:** -{parsed_amount:,} {CURRENCY_SYMBOL}\n"
                                f"💵 **Te quedaron:** {user['wallet']:,} {CURRENCY_SYMBOL}",
                    color=discord.Color.red()
                )
                embed.set_footer(text="I always get a little nervous before taking big risks...")

            # Evaluar y registrar actividad de riesgo en la misma transaccion atomica
            user_total = user["wallet"] + user["bank"]
            is_richest, is_valid_reset, req_bet = self._evaluar_riesgo_apostador(
                user_id, parsed_amount, user_total, ctx.guild
            )
            if not is_richest or is_valid_reset:
                user["last_gamble"] = time.time()

            await self.db.save()

        if is_richest and not is_valid_reset:
            embed.set_footer(
                text=f"⚠️ [Magnate] Apuesta insuficiente para resetear inactividad. Mínimo: {req_bet:,} {CURRENCY_SYMBOL} ({int(MIN_RISK_BET_PERCENT * 100)}% de tu fortuna)."
            )

        await ctx.reply(embed=embed)

        if ctx.guild:
            leader_id, leader_wealth = self._top_leader_cache.get(ctx.guild.id, (0, 0))
            if user_id == leader_id or user_total >= leader_wealth:
                await self.actualizar_rol_millonario(ctx.guild, announce_channel=ctx.channel)

    # --------------------------------------------------------------------------
    #                       COMANDO: RULETA (ROULETTE)
    # --------------------------------------------------------------------------

    @commands.command(name="ruleta", aliases=["r", "roulette"])
    async def ruleta(self, ctx: commands.Context, color: str, monto: str):
        """Apuestas en la ruleta callejera: Rojo (r), Negro (b) o Verde (g)."""
        color_clean = color.lower().strip()
        if color_clean not in RULETA_COLOR_MAP:
            await ctx.reply(
                f"❌ Ese color no juega en esta mesa, amigo. Elige bien:\n"
                f"🔴 **Rojo** (`r` o `rojo`) - Paga x{RULETA_PAYOUT_ROJO}\n"
                f"⚫ **Negro** (`b` o `negro`) - Paga x{RULETA_PAYOUT_NEGRO}\n"
                f"🟢 **Verde** (`g` o `verde`) - Paga x{RULETA_PAYOUT_VERDE} *(¡Alto riesgo!)*\n"
                f"*Ejemplo:* `{ctx.prefix}ruleta r 100`"
            )
            return

        color_elegido = RULETA_COLOR_MAP[color_clean]
        user_id = ctx.author.id

        async with self.db.lock:
            user = self.db.get_user_data(user_id)
            wallet = user["wallet"]

            parsed_amount = self._parse_amount(monto, wallet)
            if parsed_amount is None:
                await ctx.reply("❌ Ingresa una cantidad válida o escribe `all`.")
                return

            if parsed_amount > wallet:
                await ctx.reply(
                    f"❌ No tienes tantas almas en la mano. Tu saldo es de **{wallet:,} {CURRENCY_SYMBOL}**."
                )
                return

            colores_posibles = ["rojo", "negro", "verde"]
            pesos = [RULETA_WEIGHT_ROJO, RULETA_WEIGHT_NEGRO, RULETA_WEIGHT_VERDE]
            resultado = random.choices(colores_posibles, weights=pesos, k=1)[0]

            if resultado == "rojo":
                color_emoji = "🔴"
                multiplicador = RULETA_PAYOUT_ROJO
            elif resultado == "negro":
                color_emoji = "⚫"
                multiplicador = RULETA_PAYOUT_NEGRO
            else:
                color_emoji = "🟢"
                multiplicador = RULETA_PAYOUT_VERDE

            if resultado == color_elegido:
                ganancia = int(parsed_amount * (multiplicador - 1.0))
                user["wallet"] += ganancia
                user["stats"]["gambles_won"] = user["stats"].get("gambles_won", 0) + 1

                if resultado == "verde":
                    quote = random.choice(IVY_RULETA_WIN_VERDE_QUOTES).format(multiplicador=multiplicador)
                else:
                    quote = random.choice(IVY_RULETA_WIN_NORMAL_QUOTES).format(
                        emoji=color_emoji, color=resultado.upper()
                    )

                embed = discord.Embed(
                    title=f"🎰 ¡La bolilla descansó en {color_emoji} {resultado.upper()}!",
                    description=f"{quote}\n\n"
                                f"💰 **Ganancia:** +{ganancia:,} {CURRENCY_SYMBOL}\n"
                                f"💵 **En mano:** {user['wallet']:,} {CURRENCY_SYMBOL}",
                    color=discord.Color.green()
                )
                embed.set_footer(text="¡Now that's what I call a lucky bounce!")
            else:
                user["wallet"] -= parsed_amount
                user["stats"]["gambles_lost"] = user["stats"].get("gambles_lost", 0) + 1

                quote = random.choice(IVY_RULETA_LOSS_QUOTES).format(
                    emoji=color_emoji, color=resultado.upper()
                )
                embed = discord.Embed(
                    title=f"🎰 La bolilla frenó en {color_emoji} {resultado.upper()}",
                    description=f"{quote}\n\n"
                                f"💸 **Pérdida:** -{parsed_amount:,} {CURRENCY_SYMBOL}\n"
                                f"💵 **Billetera restante:** {user['wallet']:,} {CURRENCY_SYMBOL}",
                    color=discord.Color.red()
                )
                embed.set_footer(text="Sometimes you have to make your own opportunities...")

            # Evaluar y registrar actividad de riesgo en la misma transaccion atomica
            user_total = user["wallet"] + user["bank"]
            is_richest, is_valid_reset, req_bet = self._evaluar_riesgo_apostador(
                user_id, parsed_amount, user_total, ctx.guild
            )
            if not is_richest or is_valid_reset:
                user["last_gamble"] = time.time()

            await self.db.save()

        if is_richest and not is_valid_reset:
            embed.set_footer(
                text=f"⚠️ [Magnate] Apuesta insuficiente para resetear inactividad. Mínimo: {req_bet:,} {CURRENCY_SYMBOL} ({int(MIN_RISK_BET_PERCENT * 100)}% de tu fortuna)."
            )

        await ctx.reply(embed=embed)

        if ctx.guild:
            leader_id, leader_wealth = self._top_leader_cache.get(ctx.guild.id, (0, 0))
            if user_id == leader_id or user_total >= leader_wealth:
                await self.actualizar_rol_millonario(ctx.guild, announce_channel=ctx.channel)

    # --------------------------------------------------------------------------
    #                   COMANDOS DE BANCO: DEPOSIT Y WITHDRAW
    # --------------------------------------------------------------------------

    @commands.group(name="bank", aliases=["banco", "cornisa"], invoke_without_command=True)
    async def bank(self, ctx: commands.Context):
        """Muestra el estado financiero entre tus bolsillos y el escondite en la cornisa."""
        user_id = ctx.author.id
        async with self.db.lock:
            user = self.db.get_user_data(user_id)
            wallet = user["wallet"]
            bank_bal = user["bank"]
            total = wallet + bank_bal

        embed = discord.Embed(
            title=f"🏛️ El Escondite de {ctx.author.display_name} en los Tejados",
            description="Las gárgolas sabemos que dejar la plata en el suelo es una invitación a que te la afanen.",
            color=discord.Color.gold()
        )
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        embed.add_field(
            name="💵 En Mano",
            value=f"**{wallet:,}** {CURRENCY_SYMBOL}",
            inline=True
        )
        embed.add_field(
            name="🪨 En la Cornisa",
            value=f"**{bank_bal:,}** {CURRENCY_SYMBOL}",
            inline=True
        )
        embed.add_field(
            name="💰 Patrimonio Total Acumulado",
            value=f"**{total:,}** {CURRENCY_NAME} {CURRENCY_SYMBOL}",
            inline=False
        )
        embed.set_footer(text=f"Usa '{ctx.prefix}deposit <monto>' para subir plata al tejado o '{ctx.prefix}withdraw <monto>' para bajarla.")
        await ctx.reply(embed=embed)

    @bank.command(name="deposit", aliases=["dep", "d"])
    async def bank_deposit_sub(self, ctx: commands.Context, monto: str):
        """Sube almas a la cornisa protegida."""
        await self.deposit(ctx, monto=monto)

    @bank.command(name="withdraw", aliases=["with", "w", "retirar"])
    async def bank_withdraw_sub(self, ctx: commands.Context, monto: str):
        """Baja almas de la cornisa a tus bolsillos."""
        await self.withdraw(ctx, monto=monto)

    @commands.command(name="deposit", aliases=["dep", "depositar"])
    async def deposit(self, ctx: commands.Context, monto: str):
        """Guarda almas en lo alto de la cornisa de Ivy para que ningún carterista las toque."""
        user_id = ctx.author.id

        async with self.db.lock:
            user = self.db.get_user_data(user_id)
            wallet = user["wallet"]

            amount = self._parse_amount(monto, wallet)
            if amount is None or amount <= 0:
                await ctx.reply("❌ Pon un número válido de almas a resguardar o escribe `all`.")
                return

            if amount > wallet:
                await ctx.reply(
                    f"❌ ¡No tenés esa cantidad en mano, amigo! Solo tienes **{wallet:,} {CURRENCY_SYMBOL}** en los bolsillos."
                )
                return

            user["wallet"] -= amount
            user["bank"] += amount
            await self.db.save()

            embed = discord.Embed(
                title="🪨 ¡Almas Aseguradas en las Alturas!",
                description=f"Subí volando a la cornisa más alta y guardé **{amount:,} {CURRENCY_SYMBOL}** en el nido de piedra.\n"
                            f"Ni el ladrón más ágil del sindicato se anima a trepar hasta acá arriba.",
                color=discord.Color.blue()
            )
            embed.add_field(name="💵 En Mano", value=f"{user['wallet']:,} {CURRENCY_SYMBOL}")
            embed.add_field(name="🪨 En la Cornisa", value=f"{user['bank']:,} {CURRENCY_SYMBOL}")
            embed.set_footer(text="Safety first! I'll watch over your stash.")

        await ctx.reply(embed=embed)

    @commands.command(name="withdraw", aliases=["with", "retirar"])
    async def withdraw(self, ctx: commands.Context, monto: str):
        """Bajas almas de la cornisa para tenerlas a mano."""
        user_id = ctx.author.id

        async with self.db.lock:
            user = self.db.get_user_data(user_id)
            bank_bal = user["bank"]

            amount = self._parse_amount(monto, bank_bal)
            if amount is None or amount <= 0:
                await ctx.reply("❌ Ingresa un monto válido o usa `all`.")
                return

            if amount > bank_bal:
                await ctx.reply(
                    f"❌ No tienes tantas almas guardadas en la cornisa. Tu depósito es de **{bank_bal:,} {CURRENCY_SYMBOL}**."
                )
                return

            user["bank"] -= amount
            user["wallet"] += amount
            await self.db.save()

            embed = discord.Embed(
                title="💸 Almas Bajadas a la Calle",
                description=f"Te traje **{amount:,} {CURRENCY_SYMBOL}** desde la cornisa.\n"
                            f"⚠️ **Aviso de gárgola:** Ahora que las llevas encima, cualquiera con `{ctx.prefix}rob` te las puede manotear si andas distraído.",
                color=discord.Color.gold()
            )
            embed.add_field(name="💵 En Mano", value=f"{user['wallet']:,} {CURRENCY_SYMBOL}")
            embed.add_field(name="🪨 En la Cornisa", value=f"{user['bank']:,} {CURRENCY_SYMBOL}")
            embed.set_footer(text="Cuida tu espalda en los callejones oscuros.")

        await ctx.reply(embed=embed)

    # --------------------------------------------------------------------------
    #                         COMANDO: ROB / AFANAR
    # --------------------------------------------------------------------------

    @commands.command(name="rob", aliases=["robar", "afanar"])
    async def rob(self, ctx: commands.Context, victim: discord.Member):
        """Intentas robarle almas del bolsillo a otro usuario."""
        robber_id = ctx.author.id
        victim_id = victim.id

        # Validaciones de interacción directa
        if victim_id == robber_id:
            await ctx.reply("❌ ¿Te vas a robar a ti mismo, chacho? Ni Bebop haría semejante tontería. ¡Buscate algo útil que hacer!")
            return

        if victim.bot:
            if victim_id == self.bot.user.id:
                async with self.db.lock:
                    robber = self.db.get_user_data(robber_id)
                    attempts = robber["stats"].get("ivy_rob_attempts", 0) + 1
                    robber["stats"]["ivy_rob_attempts"] = attempts

                    if attempts >= 3:
                        robber["stats"]["ivy_rob_attempts"] = 0
                        robber["prison_until"] = time.time() + PRISON_DURATION
                        multa_cobrada = min(robber["wallet"], ROB_FAIL_FINE)
                        robber["wallet"] -= multa_cobrada
                        await self.db.save()

                        await ctx.reply(
                            f"🚨 **¡TE PASASTE DE LISTO, CHACHO!**\n"
                            f"Intentaste robarle a Ivy por tercera vez y la policía te dejó sin salida.\n\n"
                            f"⛓️ **Condena:** {PRISON_DURATION // 60} minutos tras las rejas\n"
                            f"💸 **Multa:** -{multa_cobrada:,} {CURRENCY_SYMBOL}"
                        )
                        return

                    await self.db.save()

                remaining = 3 - attempts
                await ctx.reply(
                    f"❌ ¡Oye! ¿Estás intentando meterle la mano en el bolsillo a una gárgola de piedra maciza? "
                    f"¡Te vas a romper los dedos! Además, yo protejo este barrio, no me afanes a mí.\n\n"
                    f"⚠️ **Intento {attempts}/3**. Si vuelves a probar, la patrulla te mete preso."
                )
                return

            await ctx.reply(
                "❌ ¡Oye! ¿Estás intentando meterle la mano en el bolsillo a una gárgola de piedra maciza? "
                "¡Te vas a romper los dedos! Además, yo protejo este barrio, no me afanes a mí."
            )
            return

        async with self.db.lock:
            robber = self.db.get_user_data(robber_id)
            victim_data = self.db.get_user_data(victim_id)
            now = time.time()

            # 1. ¿El ladrón está preso?
            in_prison, remaining_prison = self._is_in_prison(robber)
            if in_prison:
                time_str = self._format_time(remaining_prison)
                quote = random.choice(IVY_PRISON_WARNING_QUOTES).format(time=time_str)
                embed = discord.Embed(
                    title="🚨 ¡Estás Tras las Rejas!",
                    description=quote,
                    color=discord.Color.red()
                )
                await ctx.reply(embed=embed)
                return

            # 2. Cooldown de robo
            last_rob = robber.get("last_rob", 0.0)
            elapsed = now - last_rob
            if elapsed < ROB_COOLDOWN:
                remaining_cd = int(ROB_COOLDOWN - elapsed)
                time_str = self._format_time(remaining_cd)
                embed = discord.Embed(
                    title="🤫 Calma los impulsos, chacho",
                    description=f"La policía y los vecinos están alertas. Esperá **{time_str}** a que se enfríe la calle antes del próximo golpe.",
                    color=discord.Color.orange()
                )
                embed.set_footer(text="Don't got time to walk into another patrol.")
                await ctx.reply(embed=embed)
                return

            # 3. Fondos mínimos de la víctima en mano
            if victim_data["wallet"] < ROB_VICTIM_MIN_WALLET:
                await ctx.reply(
                    f"🦴 ¡Dejá tranquilo a {victim.mention}! Apenas tiene `{victim_data['wallet']}` {CURRENCY_SYMBOL} en los bolsillos. "
                    f"En Spanish Harlem nos cuidamos entre vecinos, no le robamos a los secos."
                )
                return

            robber["last_rob"] = now
            robber["stats"]["times_robbed"] = robber["stats"].get("times_robbed", 0) + 1

            # Tirada de D20
            dado = random.randint(ROB_DICE_MIN, ROB_DICE_MAX)

            if dado < ROB_FAIL_THRESHOLD:
                # --- ROBO FALLIDO: CÁRCEL Y MULTA ---
                robber["prison_until"] = now + PRISON_DURATION
                multa_cobrada = min(robber["wallet"], ROB_FAIL_FINE)
                robber["wallet"] -= multa_cobrada
                await self.db.save()

                quote = random.choice(IVY_ROB_FAIL_QUOTES).format(
                    dice=dado,
                    thresh=ROB_FAIL_THRESHOLD,
                    victim=victim.mention,
                    duration=PRISON_DURATION // 60,
                    fine=multa_cobrada,
                    currency=CURRENCY_SYMBOL
                )

                embed = discord.Embed(
                    title="🚔 ¡CANAZO DIRECTO! ¡LA POLICÍA TE ATRAPÓ!",
                    description=quote,
                    color=discord.Color.dark_red()
                )
                embed.set_footer(text="You tried to steal under a gargoyle's watch? Really?!")
            else:
                # --- ROBO EXITOSO ---
                rob_prc = random.randint(1, 50)
                botin = int((victim_data["wallet"] * rob_prc) / 100)

                victim_data["wallet"] -= botin
                robber["wallet"] += botin
                robber["stats"]["successful_robs"] = robber["stats"].get("successful_robs", 0) + 1
                await self.db.save()

                quote = random.choice(IVY_ROB_SUCCESS_QUOTES).format(
                    dice=dado,
                    thresh=ROB_FAIL_THRESHOLD,
                    loot=botin,
                    currency=CURRENCY_SYMBOL,
                    victim=victim.mention
                )

                embed = discord.Embed(
                    title="🥷 ¡GOLPE CALLEJERO CONSUMADO!",
                    description=f"{quote}\n\n"
                                f"💵 **Bolsillo de {ctx.author.mention}:** {robber['wallet']:,} {CURRENCY_SYMBOL}\n"
                                f"🥀 **Bolsillo de {victim.mention}:** {victim_data['wallet']:,} {CURRENCY_SYMBOL}",
                    color=discord.Color.green()
                )
                embed.set_footer(text=f"💡 Consejo para la víctima: ¡Resguárdate en la cornisa con '{ctx.prefix}deposit'!")

        await ctx.reply(embed=embed)
        if ctx.guild:
            leader_id, leader_wealth = self._top_leader_cache.get(ctx.guild.id, (0, 0))
            robber_total = robber["wallet"] + robber["bank"]
            if user_id == leader_id or victim.id == leader_id or robber_total >= leader_wealth:
                await self.actualizar_rol_millonario(ctx.guild, announce_channel=ctx.channel)

    # --------------------------------------------------------------------------
    #                         COMANDO: PAY / PAGAR
    # --------------------------------------------------------------------------

    @commands.command(name="pay", aliases=["pagar", "transferir", "transfer"])
    async def pay(self, ctx: commands.Context, receiver: discord.Member, monto: str):
        """Compartes almas con un aliado de tu equipo o vecino del barrio."""
        sender_id = ctx.author.id
        receiver_id = receiver.id

        if receiver_id == sender_id:
            await ctx.reply("❌ ¿Pasarte plata de un bolsillo al otro? No inventes cosas raras, chacho.")
            return

        if receiver.bot:
            await ctx.reply(
                "Aprecio el gesto de corazón, amigo, pero yo no cobro por cuidar el barrio. "
                "Ayudar a la gente es lo mío. ¡Guárdate esas almas para equiparte mejor!"
            )
            return

        async with self.db.lock:
            sender = self.db.get_user_data(sender_id)
            wallet = sender["wallet"]

            amount = self._parse_amount(monto, wallet)
            if amount is None or amount <= 0:
                await ctx.reply("❌ Pon un número válido de almas para transferir o usa `all`.")
                return

            if amount > wallet:
                await ctx.reply(
                    f"❌ No tienes suficientes almas en mano. En tus bolsillos solo hay **{wallet:,} {CURRENCY_SYMBOL}**."
                )
                return

            receiver_data = self.db.get_user_data(receiver_id)

            sender["wallet"] -= amount
            receiver_data["wallet"] += amount
            await self.db.save()

        embed = discord.Embed(
            title="🌿 ¡Kudzu Connection Financiero!",
            description=f"**{ctx.author.display_name}** compartió un lazo de almas con **{receiver.display_name}** entregándole **{amount:,} {CURRENCY_SYMBOL}**.\n\n"
                        f"*«¡Eso es jugar en equipo! Como siempre le digo al grupo: si nos apoyamos entre nosotros, nadie nos puede bajar.»*",
            color=discord.Color.teal()
        )
        embed.add_field(name=f"Bolsillo de {ctx.author.display_name}", value=f"{sender['wallet']:,} {CURRENCY_SYMBOL}", inline=True)
        embed.add_field(name=f"Bolsillo de {receiver.display_name}", value=f"{receiver_data['wallet']:,} {CURRENCY_SYMBOL}", inline=True)
        embed.set_footer(text="Now that's what I call teamwork!")
        await ctx.reply(embed=embed)
        if ctx.guild:
            leader_id, leader_wealth = self._top_leader_cache.get(ctx.guild.id, (0, 0))
            sender_total = sender["wallet"] + sender["bank"]
            receiver_total = receiver_data["wallet"] + receiver_data["bank"]
            if sender_id == leader_id or receiver_total >= leader_wealth:
                await self.actualizar_rol_millonario(ctx.guild, announce_channel=ctx.channel)

    # --------------------------------------------------------------------------
    #                     COMANDOS EXTRA: BALANCE, JAIL, TOP
    # --------------------------------------------------------------------------

    @commands.command(name="bal", aliases=["balance", "cartera", "plata", "billetera"])
    async def balance(self, ctx: commands.Context, target: Optional[discord.Member] = None):
        """Consulta el estado financiero y penal de un vecino del barrio."""
        member = target or ctx.author
        async with self.db.lock:
            user = self.db.get_user_data(member.id)
            wallet = user["wallet"]
            bank_bal = user["bank"]
            total = wallet + bank_bal
            in_prison, rem = self._is_in_prison(user)

        embed = discord.Embed(
            title=f"💳 Balance de {member.display_name}",
            description="Revisando el registro de almas en los archivos de Spanish Harlem.",
            color=discord.Color.blue()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="💵 En Mano (Bolsillos)", value=f"**{wallet:,}** {CURRENCY_SYMBOL}", inline=True)
        embed.add_field(name="🪨 En la Cornisa (Banco)", value=f"**{bank_bal:,}** {CURRENCY_SYMBOL}", inline=True)
        embed.add_field(name="💰 Patrimonio Neto", value=f"**{total:,}** {CURRENCY_NAME} {CURRENCY_SYMBOL}", inline=False)

        if in_prison:
            embed.add_field(
                name="🚨 Estado Penal",
                value=f"⛓️ **EN EL CALABOZO** (le restan {self._format_time(rem)} de condena)",
                inline=False
            )
        else:
            embed.add_field(name="🕊️ Estado Legal", value="Ciudadano libre y sin causas pendientes.", inline=False)

        embed.set_footer(text="Helping people's what I do.")
        await ctx.reply(embed=embed)

    @commands.command(name="unjail", hidden=True)
    @commands.is_owner()
    async def unjail(self, ctx: commands.Context, target: Optional[discord.Member] = None):
        member = target or ctx.author
        async with self.db.lock:
            user = self.db.get_user_data(member.id)
            user["prison_until"] = 0
            await self.db.save()

        await ctx.reply(f"🔓 {member.mention} quedó libre. Su condena fue anulada por ivy.")

    @commands.command(name="jail", aliases=["cana", "carcel", "calabozo"])
    async def jail(self, ctx: commands.Context, target: Optional[discord.Member] = None):
        """Verifica la situación penal de un usuario en el calabozo municipal."""
        member = target or ctx.author
        async with self.db.lock:
            user = self.db.get_user_data(member.id)
            in_prison, rem = self._is_in_prison(user)

        if in_prison:
            embed = discord.Embed(
                title=f"🔒 {member.display_name} está en CANA",
                description=f"Le restan **{self._format_time(rem)}** de condena tras las rejas por intentar hacer fechorías.\n"
                            f"No puede usar `{ctx.prefix}work` ni `{ctx.prefix}rob` hasta que cumpla su tiempo.",
                color=discord.Color.red()
            )
            embed.set_footer(text="You do the crime, you do the time, chacho.")
        else:
            embed = discord.Embed(
                title=f"🕊️ {member.display_name} es un ciudadano limpio",
                description="Camina tranquilo por Spanish Harlem sin deberle nada a la ley ni al sindicato.",
                color=discord.Color.green()
            )
            embed.set_footer(text="Keep it up, ally!")

        await ctx.reply(embed=embed)

    @commands.command(name="rank", aliases=["ranking", "leaderboard", "lb", "top", "ricos", "baltop"])
    async def rank(self, ctx: commands.Context):
        """Muestra el ranking de los vecinos con más almas en Spanish Harlem."""
        # Sincronizar y obtener el rol del más millonario
        await self.actualizar_rol_millonario(ctx.guild)
        role = self._get_richest_role(ctx.guild) if ctx.guild else None

        async with self.db.lock:
            all_users = self.db.get_all_users()

            # Ordenar usuarios por patrimonio total (mano + banco)
            sorted_users = sorted(
                all_users.items(),
                key=lambda item: item[1].get("wallet", 0) + item[1].get("bank", 0),
                reverse=True
            )

            # Buscar la posición del autor en el ranking
            author_id_str = str(ctx.author.id)
            author_rank = None
            author_total = 0
            for idx, (uid_str, data) in enumerate(sorted_users, start=1):
                if uid_str == author_id_str:
                    author_rank = idx
                    author_total = data.get("wallet", 0) + data.get("bank", 0)
                    break

        embed = discord.Embed(
            title="🏆 Ranking de Almas de Spanish Harlem",
            description="Desde las cornisas más altas las gárgolas vemos todo, y sabemos muy bien quiénes son los más forrados de almas en el barrio.",
            color=discord.Color.gold()
        )

        lines = []
        rank_num = 1
        for uid_str, data in sorted_users:
            if rank_num > 10:
                break
            user_id = int(uid_str)
            user_obj = ctx.guild.get_member(user_id) if ctx.guild else None

            # Si no estaba en caché, intentamos obtenerlo de la API de Discord para este servidor
            if user_obj is None and ctx.guild:
                try:
                    user_obj = await ctx.guild.fetch_member(user_id)
                except (discord.NotFound, discord.HTTPException):
                    user_obj = None

            # Si se encuentra en el servidor usamos su display_name; si se fue, buscamos su nombre global
            if user_obj:
                name = user_obj.display_name
            else:
                try:
                    global_user = await self.bot.fetch_user(user_id)
                    name = f"{global_user.display_name} (Fuera del server)"
                except Exception:
                    name = f"Vecino ({uid_str})"

            total = data.get("wallet", 0) + data.get("bank", 0)
            is_richest = (rank_num == 1 and total > 0)

            crown = " 👑" if is_richest else ""
            tag = f" `[{role.name}]`" if (is_richest and role) else ""
            inactivity_tag = ""
            if is_richest and total >= ROBIN_HOOD_MIN_WALLET:
                last_g = data.get("last_gamble", time.time())
                idle_h = max(0.0, (time.time() - last_g) / 3600.0)
                if idle_h >= INACTIVITY_STAGE_1_HOURS:
                    inactivity_tag = f" *(⚠️ Inactivo {int(idle_h)}h)*"

            medal = "🥇" if rank_num == 1 else "🥈" if rank_num == 2 else "🥉" if rank_num == 3 else f"**#{rank_num}**"
            lines.append(f"{medal}{crown} **{name}**{tag}{inactivity_tag}: {total:,} {CURRENCY_SYMBOL} *(Mano: {data.get('wallet', 0):,} | Cornisa: {data.get('bank', 0):,})*")
            rank_num += 1

        embed.description = (
            "Desde las cornisas más altas las gárgolas vemos todo, y sabemos muy bien quiénes son los más forrados de almas en el barrio:\n\n"
            + ("\n".join(lines) if lines else "Aún no hay registros de almas en el barrio.")
        )

        if author_rank is not None:
            embed.add_field(
                name="📍 Tu Lugar en la Tabla",
                value=f"Estás en el puesto **#{author_rank}** con un total de **{author_total:,} {CURRENCY_NAME} {CURRENCY_SYMBOL}**.",
                inline=False
            )

        embed.set_footer(text="Carlos always says: don't let wealth get to your head.")
        await ctx.reply(embed=embed)

    # --------------------------------------------------------------------------
    #                       MANEJO GLOBAL DE ERRORES DEL COG
    # --------------------------------------------------------------------------

    async def cog_command_error(self, ctx: commands.Context, error: Exception):
        """Captura y traduce excepciones comunes al tono característico de Ivy."""
        if isinstance(error, commands.MissingRequiredArgument):
            param = error.param.name
            await ctx.reply(
                f"⚠️ ¡Ey, chacho! Te faltó un dato clave: `{param}`.\n"
                f"Usa `{ctx.prefix}help {ctx.command.name}` si no te acuerdas de cómo va la jugada."
            )
        elif isinstance(error, commands.MemberNotFound):
            await ctx.reply("🔍 Mmm... no pude ubicar a ese vecino en el barrio. Asegúrate de mencionarlo con `@` o usar su ID correcto.")
        elif isinstance(error, commands.BadArgument):
            await ctx.reply("❌ Esos datos no me cuadran nada, amigo. Revisa bien los números o las opciones que pusiste.")
        else:
            print(f"[IVY ECONOMY ERROR] Excepción no controlada en {ctx.command}: {error}")
            raise error
