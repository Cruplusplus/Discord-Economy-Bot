"""
Modulo de Tienda Callejera, Mercado Negro e Inventario para Discord Economy Bot.
Permite adquirir artefactos y consumibles tematicos de Spanish Harlem (Deadlock).
"""

import time
from typing import Dict, Any, Optional, List, Tuple, TYPE_CHECKING
import discord

from .config import (
    CURRENCY_NAME,
    CURRENCY_SYMBOL,
    ITEM_PRICE_COFFEE,
    ITEM_PRICE_BAIL_BOND,
    ITEM_PRICE_KUDZU_SEEDS,
    ITEM_PRICE_LOCKPICK,
    ITEM_PRICE_STONE_CHARM,
    ITEM_PRICE_MEGAPHONE,
    COFFEE_DURATION_SECONDS,
    KUDZU_DURATION_SECONDS,
)

if TYPE_CHECKING:
    from .cog import Economy


class ShopItem:
    """Representa un articulo en venta en el mercado de Ivy."""

    def __init__(
        self,
        item_id: str,
        name: str,
        emoji: str,
        price: int,
        category: str,
        description: str,
        usable: bool = False,
        max_stack: int = 10,
    ):
        self.item_id = item_id
        self.name = name
        self.emoji = emoji
        self.price = price
        self.category = category
        self.description = description
        self.usable = usable
        self.max_stack = max_stack


# Catalogo Oficial de la Tienda de Spanish Harlem
CATALOG: Dict[str, ShopItem] = {
    "carlos_coffee": ShopItem(
        item_id="carlos_coffee",
        name="Café del Diner de Carlos",
        emoji="☕",
        price=ITEM_PRICE_COFFEE,
        category="Utilidad",
        description="Reduce el cooldown de `%work` a solo 15 segundos durante 30 minutos.",
        usable=True,
        max_stack=10,
    ),
    "bail_bond": ShopItem(
        item_id="bail_bond",
        name="Fianza Policial",
        emoji="🚔",
        price=ITEM_PRICE_BAIL_BOND,
        category="Defensa",
        description="Pasivo: Te libera automáticamente de prisión al instante si un robo o ruleta sale mal.",
        usable=False,
        max_stack=5,
    ),
    "kudzu_seeds": ShopItem(
        item_id="kudzu_seeds",
        name="Semillas de Kudzu",
        emoji="🌿",
        price=ITEM_PRICE_KUDZU_SEEDS,
        category="Utilidad",
        description="Otorga +50% de almas bonus al recoger cualquier Soul Drop durante 24 horas.",
        usable=True,
        max_stack=5,
    ),
    "lockpick": ShopItem(
        item_id="lockpick",
        name="Guante de Cerrajero",
        emoji="🧤",
        price=ITEM_PRICE_LOCKPICK,
        category="Especial",
        description="Pasivo: Reduce el umbral de fallo de tu próximo `%rob` (de 12 a 8 en el d20), aumentando tu éxito al 65%.",
        usable=False,
        max_stack=5,
    ),
    "stone_charm": ShopItem(
        item_id="stone_charm",
        name="Amuleto de Piedra",
        emoji="🪨",
        price=ITEM_PRICE_STONE_CHARM,
        category="Defensa",
        description="Pasivo: Si intentan robarte con `%rob`, el robo fracasa 100% y el ladrón va preso. También absorbe 50% de Robin Hood.",
        usable=False,
        max_stack=5,
    ),
    "megaphone": ShopItem(
        item_id="megaphone",
        name="Megáfono de Harlem",
        emoji="📢",
        price=ITEM_PRICE_MEGAPHONE,
        category="Especial",
        description="Transmite un boletín o anuncio destacado con la voz de Ivy en el canal de economía (`%usar megaphone <mensaje>`).",
        usable=True,
        max_stack=3,
    ),
}

# Alias para facilitar compras y busquedas
ITEM_ALIASES: Dict[str, str] = {
    "cafe": "carlos_coffee",
    "coffee": "carlos_coffee",
    "carlos_coffee": "carlos_coffee",
    "espresso": "carlos_coffee",
    "fianza": "bail_bond",
    "bail": "bail_bond",
    "bail_bond": "bail_bond",
    "abogado": "bail_bond",
    "kudzu": "kudzu_seeds",
    "semillas": "kudzu_seeds",
    "seeds": "kudzu_seeds",
    "kudzu_seeds": "kudzu_seeds",
    "guante": "lockpick",
    "lockpick": "lockpick",
    "cerrajero": "lockpick",
    "ganzua": "lockpick",
    "amuleto": "stone_charm",
    "charm": "stone_charm",
    "piedra": "stone_charm",
    "stone_charm": "stone_charm",
    "escudo": "stone_charm",
    "megafono": "megaphone",
    "megaphone": "megaphone",
    "anuncio": "megaphone",
}


def get_item(query: str) -> Optional[ShopItem]:
    """Obtiene un articulo del catalogo a partir de su ID o alias."""
    clean = query.strip().lower()
    item_id = ITEM_ALIASES.get(clean, clean)
    return CATALOG.get(item_id)


def get_user_inventory(user_data: Dict[str, Any]) -> Dict[str, int]:
    """Retorna el inventario del usuario asegurando un diccionario limpio."""
    inv = user_data.setdefault("inventory", {})
    if not isinstance(inv, dict):
        user_data["inventory"] = {}
        return user_data["inventory"]
    return inv


def get_user_buffs(user_data: Dict[str, Any]) -> Dict[str, float]:
    """Retorna los efectos temporales activos del usuario."""
    buffs = user_data.setdefault("buffs", {})
    if not isinstance(buffs, dict):
        user_data["buffs"] = {}
        return user_data["buffs"]
    return buffs


def format_remaining_time(seconds: int) -> str:
    """Formatea segundos restantes a minutos y segundos."""
    if seconds <= 0:
        return "0s"
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}h {m}m"
    if m > 0:
        return f"{m}m {s}s"
    return f"{s}s"


class ShopSelect(discord.ui.Select):
    """Menu desplegable para comprar directamente desde la vista interactiva."""

    def __init__(self, shop_view: "ShopView"):
        self.shop_view = shop_view
        options = [
            discord.SelectOption(
                label=f"{item.name} ({item.price:,} {CURRENCY_SYMBOL})",
                value=item.item_id,
                description=item.description[:95],
                emoji=item.emoji,
            )
            for item in CATALOG.values()
        ]
        super().__init__(
            placeholder="🛒 Selecciona un artículo para comprar 1 unidad...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        item_id = self.values[0]
        item = CATALOG.get(item_id)
        if not item:
            await interaction.response.send_message("❌ Artículo no encontrado.", ephemeral=True)
            return

        user_id = interaction.user.id
        async with self.shop_view.cog.db.lock:
            user_data = self.shop_view.cog.db.get_user_data(user_id)
            wallet = user_data.get("wallet", 0)

            if wallet < item.price:
                await interaction.response.send_message(
                    f"❌ ¡Te faltan almas en la mano, chacho! El **{item.name}** cuesta **{item.price:,} {CURRENCY_SYMBOL}** y solo tienes **{wallet:,} {CURRENCY_SYMBOL}**.",
                    ephemeral=True,
                )
                return

            inv = get_user_inventory(user_data)
            current_count = inv.get(item.item_id, 0)
            if current_count >= item.max_stack:
                await interaction.response.send_message(
                    f"❌ Ya tienes el máximo permitido de este artículo ({item.max_stack} unidades). ¡Usa los que tienes antes de comprar más!",
                    ephemeral=True,
                )
                return

            # Efectuar la compra
            user_data["wallet"] -= item.price
            inv[item.item_id] = current_count + 1
            await self.shop_view.cog.db.save()

        embed = self.shop_view.build_embed(user_data)
        await interaction.response.edit_message(embed=embed, view=self.shop_view)
        await interaction.followup.send(
            f"✅ ¡Compraste **{item.emoji} {item.name}** por **{item.price:,} {CURRENCY_SYMBOL}**! Guardado en tu `%inv`.",
            ephemeral=True,
        )


class ShopView(discord.ui.View):
    """Vista interactiva con catalogo y menu desplegable de compra."""

    def __init__(self, cog: "Economy", user: discord.Member | discord.User):
        super().__init__(timeout=90)
        self.cog = cog
        self.user = user
        self.add_item(ShopSelect(self))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(
                "❌ Esta vitrina la abrió otro vecino. Usa `%tienda` para abrir la tuya.",
                ephemeral=True,
            )
            return False
        return True

    def build_embed(self, user_data: Dict[str, Any]) -> discord.Embed:
        wallet = user_data.get("wallet", 0)
        inv = get_user_inventory(user_data)

        embed = discord.Embed(
            title="🏬 La Tienda Callejera y Mercado Negro de Ivy",
            description=(
                "¡Bienvenido al rincón de las cornisas de Spanish Harlem! Acá podés canjear tus almas por "
                "artilugios defensivos, café caliente y herramientas tácticas.\n\n"
                f"💵 **Tus almas en mano:** **{wallet:,} {CURRENCY_SYMBOL}**\n"
                f"💡 *Usa el menú desplegable abajo o escribe `%comprar <nombre>`.*"
            ),
            color=discord.Color.teal(),
        )

        # Categorizar artículos
        categorias = {}
        for item in CATALOG.values():
            categorias.setdefault(item.category, []).append(item)

        for cat_name, items in categorias.items():
            lineas = []
            for item in items:
                owned = inv.get(item.item_id, 0)
                owned_str = f" `(Llevas: {owned}/{item.max_stack})`" if owned > 0 else ""
                tipo_str = "*(Usable)*" if item.usable else "*(Efecto Pasivo)*"
                lineas.append(
                    f"{item.emoji} **{item.name}** — **{item.price:,} {CURRENCY_SYMBOL}** {tipo_str}{owned_str}\n"
                    f"↳ *{item.description}*"
                )
            embed.add_field(name=f"📦 Categoría: {cat_name}", value="\n\n".join(lineas), inline=False)

        embed.set_footer(text="Carlos always says: un buen artilugio a tiempo vale más que cien mil almas.")
        return embed


class InventoryView(discord.ui.View):
    """Vista del inventario del usuario mostrando objetos y buffs activos."""

    def __init__(self, cog: "Economy", user: discord.Member | discord.User):
        super().__init__(timeout=60)
        self.cog = cog
        self.user = user

    def build_embed(self, user_data: Dict[str, Any]) -> discord.Embed:
        inv = get_user_inventory(user_data)
        buffs = get_user_buffs(user_data)
        now = time.time()

        embed = discord.Embed(
            title=f"🎒 Mochila Callejera de {self.user.display_name}",
            description="Todos tus artilugios resguardados y efectos mágicos activos.",
            color=discord.Color.dark_teal(),
        )

        # 1. Buffs activos
        buff_lines = []
        coffee_until = buffs.get("coffee_until", 0.0)
        if coffee_until > now:
            rem = int(coffee_until - now)
            buff_lines.append(f"☕ **Café de Carlos Activo:** Cooldown de `%work` a 15s (Resta: **{format_remaining_time(rem)}**)")

        kudzu_until = buffs.get("kudzu_until", 0.0)
        if kudzu_until > now:
            rem = int(kudzu_until - now)
            buff_lines.append(f"🌿 **Bendición de Kudzu Activa:** +50% almas en Soul Drops (Resta: **{format_remaining_time(rem)}**)")

        if buff_lines:
            embed.add_field(name="⚡ Efectos Temporales Activos", value="\n".join(buff_lines), inline=False)

        # 2. Ítems en inventario
        item_lines = []
        for item_id, count in inv.items():
            if count <= 0:
                continue
            item = CATALOG.get(item_id)
            if item:
                usar_hint = " — *(Escribe `%usar " + item.item_id + "`)*" if item.usable else " — *(Se activa solo cuando haga falta)*"
                item_lines.append(f"{item.emoji} **{item.name}** x{count}{usar_hint}\n↳ *{item.description}*")

        if item_lines:
            embed.add_field(name="📦 Artículos en tu Posesión", value="\n\n".join(item_lines), inline=False)
        else:
            embed.add_field(
                name="📦 Artículos en tu Posesión",
                value="*No tienes ningún artilugio en la mochila. Date una vuelta por la `%tienda`.*",
                inline=False,
            )

        wallet = user_data.get("wallet", 0)
        bank = user_data.get("bank", 0)
        embed.set_footer(text=f"Bolsillo: {wallet:,} {CURRENCY_SYMBOL} | Cornisa: {bank:,} {CURRENCY_SYMBOL} • Ivy te cuida la espalda.")
        return embed
