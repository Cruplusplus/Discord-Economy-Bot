"""
Paquete modular de economia y timba para el bot de Discord.
Exporta la clase Economy y la funcion setup(bot) para bot.load_extension("economy").
"""

from discord.ext import commands
from .cog import Economy


async def setup(bot: commands.Bot) -> None:
    """Funcion de entrada estandar de discord.py para cargar la extension."""
    await bot.add_cog(Economy(bot))


__all__ = ["Economy", "setup"]
