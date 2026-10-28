"""
Vistas interactivas de interfaz grafica (discord.ui.View) para eventos aleatorios:
- SoulDropView: Reflejos y velocidad al reclamar un alijo.
- RaidBossView: Combate cooperativo barrial contra el Sindicato Mendoza.
- RiskRouletteView: Desafio de alto riesgo (70% premio gordo vs 30% carcel).
- RobinHoodView: Impuesto a la opulencia y redistribucion comunitaria.
"""

import random
import time
from typing import Optional, List, Set, TYPE_CHECKING
import discord

from .config import (
    DROP_TIMEOUT_SECONDS,
    CURRENCY_NAME,
    CURRENCY_SYMBOL,
    RAID_HP,
    RAID_TIMEOUT_SECONDS,
    RAID_TOTAL_POOL,
    ROULETTE_RISK_WIN_CHANCE,
    ROULETTE_WIN_AMOUNT,
    ROULETTE_PRISON_DURATION,
    KUDZU_DROP_BONUS_PERCENT,
)

if TYPE_CHECKING:
    from .cog import Economy


class SoulDropView(discord.ui.View):
    """Boton de reflejos para recoger un alijo de almas."""

    def __init__(self, cog: "Economy", amount: int):
        super().__init__(timeout=DROP_TIMEOUT_SECONDS)
        self.cog = cog
        self.amount = amount
        self.claimed = False
        self.message: Optional[discord.Message] = None

    @discord.ui.button(label="💎 ¡Reclamar Alijo!", style=discord.ButtonStyle.success, emoji="🪙")
    async def claim_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.claimed:
            await interaction.response.send_message("❌ ¡Demasiado tarde, chacho! Ya se llevaron estas almas.", ephemeral=True)
            return

        async with self.cog.db.lock:
            if self.claimed:
                await interaction.response.send_message("❌ ¡Demasiado tarde, chacho! Ya se llevaron estas almas.", ephemeral=True)
                return
            self.claimed = True
            button.disabled = True
            self.stop()

            user_data = self.cog.db.get_user_data(interaction.user.id)
            buffs = user_data.setdefault("buffs", {})
            kudzu_until = buffs.get("kudzu_until", 0.0)
            kudzu_bonus = 0
            if kudzu_until > time.time():
                kudzu_bonus = int(round(self.amount * KUDZU_DROP_BONUS_PERCENT))

            total_reward = self.amount + kudzu_bonus
            user_data["wallet"] += total_reward
            await self.cog.db.save()

        desc = (
            f"¡Rápido como una gárgola en picada! **{interaction.user.mention}** se abalanzó sobre el alijo "
            f"y se embolsó **+{self.amount:,} {CURRENCY_NAME} {CURRENCY_SYMBOL}**.\n"
        )
        if kudzu_bonus > 0:
            desc += f"🌿 **¡Bendición de Semillas de Kudzu!** (+{kudzu_bonus:,} {CURRENCY_SYMBOL} de bonus extra)\n"
        desc += f"\nEn sus bolsillos ahora carga con: **{user_data['wallet']:,} {CURRENCY_SYMBOL}**"

        embed = discord.Embed(
            title="⚡ ¡ALIJO RECLAMADO A TODA VELOCIDAD!",
            description=desc,
            color=discord.Color.green()
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.set_footer(text="Carlos always says: the fastest hands get the warmest mofongo.")
        await interaction.response.edit_message(embed=embed, view=self)

        if interaction.guild:
            await self.cog.actualizar_rol_millonario(interaction.guild, announce_channel=interaction.channel)

    async def on_timeout(self):
        if not self.claimed:
            for item in self.children:
                item.disabled = True
            if self.message:
                embed = discord.Embed(
                    title="💨 Alijo de Almas Desvanecido",
                    description="El viento de Spanish Harlem sopló fuerte y las almas sueltas se dispersaron entre los callejones. ¡Nadie fue lo bastante rápido!",
                    color=discord.Color.dark_grey()
                )
                embed.set_footer(text="Las gárgolas no esperan a los dormilones.")
                try:
                    await self.message.edit(embed=embed, view=self)
                except Exception:
                    pass


class RaidBossView(discord.ui.View):
    """Raid cooperativo contra una patrulla del Sindicato Mendoza."""

    def __init__(self, cog: "Economy"):
        super().__init__(timeout=RAID_TIMEOUT_SECONDS)
        self.cog = cog
        self.max_hp = RAID_HP
        self.current_hp = RAID_HP
        self.attackers: List[discord.Member] = []
        self.attacker_ids: Set[int] = set()
        self.defeated = False
        self.message: Optional[discord.Message] = None

    def _generate_hp_bar(self) -> str:
        filled = "🟩" * self.current_hp
        empty = "⬜" * (self.max_hp - self.current_hp)
        return f"{filled}{empty} ({self.current_hp}/{self.max_hp} HP)"

    @discord.ui.button(label="⚔️ ¡Golpear!", style=discord.ButtonStyle.danger, emoji="💥")
    async def attack_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.defeated:
            await interaction.response.send_message("❌ ¡El matón ya fue noqueado contra el pavimento!", ephemeral=True)
            return

        async with self.cog.db.lock:
            if self.defeated:
                await interaction.response.send_message("❌ ¡El matón ya fue noqueado contra el pavimento!", ephemeral=True)
                return

            if interaction.user.id in self.attacker_ids:
                await interaction.response.send_message(
                    "❌ ¡Ey, chacho, ya diste tu golpe! Deja que otro vecino del barrio le dé una tunda para rematarlo.",
                    ephemeral=True
                )
                return

            self.attacker_ids.add(interaction.user.id)
            self.attackers.append(interaction.user)
            self.current_hp -= 1

            if self.current_hp <= 0:
                self.defeated = True
                button.disabled = True
                self.stop()
                payout = RAID_TOTAL_POOL // len(self.attackers)
                for member in self.attackers:
                    u_data = self.cog.db.get_user_data(member.id)
                    u_data["wallet"] += payout
                await self.cog.db.save()

        if self.defeated:
            heroes_str = "\n".join(f"• {u.mention}: **+{payout:,} {CURRENCY_SYMBOL}**" for u in self.attackers)
            embed = discord.Embed(
                title="🏆 ¡PATRULLA DERROTADA! ¡EL BARRIO SE RESPETA!",
                description=(
                    f"💥 ¡Con el impacto final de **{interaction.user.mention}**, los matones salieron huyendo despavoridos!\n\n"
                    f"💰 **Botín repartido equitativamente:** **{RAID_TOTAL_POOL:,} {CURRENCY_SYMBOL}**\n\n"
                    f"**🛡️ Vecinos justicieros:**\n{heroes_str}"
                ),
                color=discord.Color.green()
            )
            embed.set_footer(text="Ivy dice: ¡Nadie se mete con Spanish Harlem mientras estemos unidos!")
            await interaction.response.edit_message(embed=embed, view=self)

            if interaction.guild:
                await self.cog.actualizar_rol_millonario(interaction.guild, announce_channel=interaction.channel)
        else:
            embed = discord.Embed(
                title="🚨 ¡EMBOSCADA DEL SINDICATO MENDOZA!",
                description=(
                    f"¡Unos matones del Sindicato Mendoza intentan cobrar peaje ilegal en Spanish Harlem!\n\n"
                    f"❤️ **Vida del matón:** {self._generate_hp_bar()}\n"
                    f"💰 **Recompensa total:** **{RAID_TOTAL_POOL:,} {CURRENCY_SYMBOL}** (a repartir entre todos los que ataquen)\n\n"
                    f"👊 **Último impacto:** {interaction.user.mention} le encajó un derechazo de piedra.\n"
                    f"👥 **Vecinos al ataque ({len(self.attackers)}/{self.max_hp}):** "
                    f"{', '.join(u.display_name for u in self.attackers)}"
                ),
                color=discord.Color.orange()
            )
            embed.set_footer(text="¡Se necesitan vecinos distintos para rodearlos y acabarlos!")
            await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self):
        if not self.defeated:
            for item in self.children:
                item.disabled = True
            if self.message:
                embed = discord.Embed(
                    title="💨 La Patrulla Mendoza Escapó",
                    description=(
                        f"Los matones se rieron en sus caras y se perdieron en las sombras con el botín. "
                        f"Les faltó coordinación barrial para bajarlos a tiempo."
                    ),
                    color=discord.Color.dark_grey()
                )
                embed.set_footer(text="Carlos always says: if you don't stick together, you lose together.")
                try:
                    await self.message.edit(embed=embed, view=self)
                except Exception:
                    pass


class RiskRouletteView(discord.ui.View):
    """El desafio riesgoso de Ivy: 70% premio gordo vs 30% carcel."""

    def __init__(self, cog: "Economy"):
        super().__init__(timeout=DROP_TIMEOUT_SECONDS)
        self.cog = cog
        self.claimed = False
        self.message: Optional[discord.Message] = None

    @discord.ui.button(label="🎲 ¡Aceptar el Desafío!", style=discord.ButtonStyle.primary, emoji="🔥")
    async def risk_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.claimed:
            await interaction.response.send_message("❌ ¡Alguien ya tomó este riesgo antes que tú!", ephemeral=True)
            return

        async with self.cog.db.lock:
            if self.claimed:
                await interaction.response.send_message("❌ ¡Alguien ya tomó este riesgo antes que tú!", ephemeral=True)
                return
            self.claimed = True
            button.disabled = True
            self.stop()

            user_data = self.cog.db.get_user_data(interaction.user.id)
            now = time.time()

            won = random.random() < ROULETTE_RISK_WIN_CHANCE
            if won:
                user_data["wallet"] += ROULETTE_WIN_AMOUNT
                await self.cog.db.save()

                embed = discord.Embed(
                    title="💎 ¡QUÉ AGALLAS! ¡VICTORIA TOTAL!",
                    description=(
                        f"**{interaction.user.mention}** se puso la diez, dio el salto de fe sin mirar abajo y cayó de pie.\n\n"
                        f"🎁 **Premio de las alturas:** **+{ROULETTE_WIN_AMOUNT:,} {CURRENCY_NAME} {CURRENCY_SYMBOL}**\n"
                        f"Billetera actual: **{user_data['wallet']:,} {CURRENCY_SYMBOL}**"
                    ),
                    color=discord.Color.gold()
                )
                embed.set_thumbnail(url=interaction.user.display_avatar.url)
                embed.set_footer(text="Ivy dice: ¡A los valientes la suerte les sonríe desde las cornisas!")
            else:
                user_data["prison_until"] = max(user_data.get("prison_until", 0.0), now + ROULETTE_PRISON_DURATION)
                await self.cog.db.save()

                minutos = ROULETTE_PRISON_DURATION // 60
                embed = discord.Embed(
                    title="🚨 ¡LA POLICÍA TE CAYÓ ENCIMA!",
                    description=(
                        f"Ay, chacho... **{interaction.user.mention}** se hizo el vivo y lo agarró la patrulla en plena movida.\n\n"
                        f"⛓️ **Condena:** Al calabozo por **{minutos} minutos** tras las rejas sin poder patrullar ni chambear."
                    ),
                    color=discord.Color.red()
                )
                embed.set_thumbnail(url=interaction.user.display_avatar.url)
                embed.set_footer(text="Ivy no rescata rateros atrapados in fraganti.")

        await interaction.response.edit_message(embed=embed, view=self)

        if won and interaction.guild:
            await self.cog.actualizar_rol_millonario(interaction.guild, announce_channel=interaction.channel)

    async def on_timeout(self):
        if not self.claimed:
            for item in self.children:
                item.disabled = True
            if self.message:
                embed = discord.Embed(
                    title="🐔 Desafío Expirado: Nadie se Animó",
                    description="Ivy se quedó esperando en la cornisa con una sonrisa burlona... Parece que a todo el barrio le temblaron las piernas hoy.",
                    color=discord.Color.dark_grey()
                )
                embed.set_footer(text="Mucho ruido y pocas nueces en Spanish Harlem.")
                try:
                    await self.message.edit(embed=embed, view=self)
                except Exception:
                    pass


class RobinHoodView(discord.ui.View):
    """Impuesto a la opulencia: bolsa cobrada al mas rico disponible para los demas."""

    def __init__(self, cog: "Economy", target_member: discord.Member, amount: int):
        super().__init__(timeout=DROP_TIMEOUT_SECONDS)
        self.cog = cog
        self.target_member = target_member
        self.amount = amount
        self.claimed = False
        self.message: Optional[discord.Message] = None

    @discord.ui.button(label="💰 ¡Agarrar Bolsa Redistribuida!", style=discord.ButtonStyle.success, emoji="🏹")
    async def claim_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id == self.target_member.id:
            await interaction.response.send_message(
                "❌ ¡Oye, chacho descarado! Este es el impuesto a la opulencia que te cobramos. ¡No puedes autorecuperártelo!",
                ephemeral=True
            )
            return

        if self.claimed:
            await interaction.response.send_message("❌ ¡Otro vecino ya se llevó esta bolsa de almas!", ephemeral=True)
            return

        async with self.cog.db.lock:
            if self.claimed:
                await interaction.response.send_message("❌ ¡Otro vecino ya se llevó esta bolsa de almas!", ephemeral=True)
                return
            self.claimed = True
            button.disabled = True
            self.stop()

            user_data = self.cog.db.get_user_data(interaction.user.id)
            user_data["wallet"] += self.amount
            await self.cog.db.save()

        embed = discord.Embed(
            title="🏹 ¡JUSTICIA CALLEJERA AL ESTILO IVY!",
            description=(
                f"**{interaction.user.mention}** fue el más despierto del barrio y se quedó con la bolsa de "
                f"**+{self.amount:,} {CURRENCY_NAME} {CURRENCY_SYMBOL}** que Ivy le 'redistribuyó' a **{self.target_member.display_name}**.\n\n"
                f"Billetera actual: **{user_data['wallet']:,} {CURRENCY_SYMBOL}**"
            ),
            color=discord.Color.green()
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.set_footer(text="Ivy dice: En Spanish Harlem la riqueza circula, no se estanca.")
        await interaction.response.edit_message(embed=embed, view=self)

        if interaction.guild:
            await self.cog.actualizar_rol_millonario(interaction.guild, announce_channel=interaction.channel)

    async def on_timeout(self):
        if not self.claimed:
            for item in self.children:
                item.disabled = True
            if self.message:
                embed = discord.Embed(
                    title="💨 Almas Redistribuidas Perdidas",
                    description=(
                        f"Nadie recogió la bolsa con {self.amount:,} {CURRENCY_SYMBOL} que se le cobraron a "
                        f"{self.target_member.display_name}. Ivy se las llevó para alimentar a las palomas de la catedral."
                    ),
                    color=discord.Color.dark_grey()
                )
                try:
                    await self.message.edit(embed=embed, view=self)
                except Exception:
                    pass
