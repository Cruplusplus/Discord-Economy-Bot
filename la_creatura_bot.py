import os
import re
import asyncio
import aiohttp
import random
import signal
from dotenv import load_dotenv

# Cargar variables de entorno desde el archivo .env
load_dotenv()

import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True

def parse_int_env(key: str, default: int = 0) -> int:
    val = os.getenv(key)
    if val:
        try:
            return int(val.strip())
        except ValueError:
            pass
    return default

prefijo = os.getenv("BOT_PREFIX", "%")

bot = commands.Bot(command_prefix=prefijo, intents=intents)

# Administrador de consola interactiva CLI
from console import ConsoleManager
console_manager = ConsoleManager(bot)

# CONST
discord_api_key = os.getenv("DISCORD_TOKEN")
giphy_api_key = os.getenv("GIPHY_API_KEY", "")
deadlock_senal_id = parse_int_env("DEADLOCK_SIGNAL_ROLE_ID", 0)
ivy_online_channel = parse_int_env("IVY_ONLINE_CHANNEL_ID", 0)
self_discord_id = parse_int_env("OWNER_DISCORD_ID", 0)

# Constantes multimedia y listas de recursos estáticos
from constants import (
    LISTA_GIFS,
    HOP_ON_DEADLOCK_LIST,
    LEPOARD_PAW_LIST,
    ivy_tags,
)

#code

deadlock_counter = int(0)
shutdown_started = False



# ===============fx====================

async def obtener_gif(tags=None) -> str | None:
    """Busca un GIF en Giphy.
    
    'tags' puede ser:
      - None (usa una búsqueda por defecto o trending)
      - Un string: "gato durmiendo"
      - Una lista de strings: ["cat", "cute"] -> los une en "cat cute"
    Retorna la URL del GIF si encuentra uno, o None si no hay resultados/error.
    """
    if isinstance(tags, list):
        q = " ".join(tags)
    elif isinstance(tags, str):
        q = tags.replace(",", " ").strip()
    else:
        q = "happy"

    url = "https://api.giphy.com/v1/gifs/search"
    params = {
        "api_key": giphy_api_key,
        "q": q,
        "limit": 25,
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
        print(f"Error al conectar con Giphy: {e}")

    return None

_media_url_cache = {}

async def resolver_direct_gif_url(url: str) -> str | None:
    """Resuelve URLs de Tenor u otros hosts a enlaces directos de imagen/gif para discord.Embed."""
    if not url:
        return None
    url = url.rstrip(",").strip()
    if url in _media_url_cache:
        return _media_url_cache[url]

    # Si es una página web de Tenor (no un CDN directo), extraer el enlace directo de og:image
    if "tenor.com" in url and not any(k in url for k in ["media.tenor.com", "media1.tenor.com", "c.tenor.com"]):
        try:
            headers = {"User-Agent": "Mozilla/5.0 (compatible; Discordbot/2.0; +https://discordapp.com)"}
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=4)) as resp:
                    if resp.status == 200:
                        html = await resp.text()
                        og_img = re.findall(r"""<meta[^>]+property=["']og:image["'][^>]+content=["']([^"']+)["']""", html)
                        if not og_img:
                            og_img = re.findall(r"""<meta[^>]+content=["']([^"']+)["'][^>]+property=["']og:image["']""", html)
                        if og_img:
                            direct = og_img[0]
                            _media_url_cache[url] = direct
                            return direct
        except Exception as e:
            print(f"[PAW] Error resolviendo URL de Tenor: {e}")

    # Si ya es un recurso multimedia directo válido
    clean_path = url.lower().split("?")[0]
    if any(clean_path.endswith(ext) for ext in [".gif", ".png", ".jpg", ".jpeg", ".webp"]):
        if "cdn.discordapp.com" not in url and "imgs.search.brave.com" not in url:
            _media_url_cache[url] = url
            return url

    return None


def request_shutdown():
    global shutdown_started
    if shutdown_started:
        return

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return

    loop.create_task(shutdown_bot())


def handle_signal(signum, frame):
    print(f"Signal: {signum}. Killing bot")
    request_shutdown()

# cogs
async def setup_hook():
    await bot.load_extension("economy")
    print("Módulos cargados con éxito")

bot.setup_hook = setup_hook

# ===============EVENTS====================

@bot.event
async def on_ready():
    print(f"Bot conectado como {bot.user} (ID: {bot.user.id})")
    if not console_manager.is_running:
        console_manager.start()

    if ivy_online_channel > 0:
        canal = bot.get_channel(ivy_online_channel)
        if canal is not None:
            try:
                await canal.send("🟢 Looks like I'm missing that job interview...")
            except Exception as e:
                print(f"No se pudo enviar aviso de inicio al canal {ivy_online_channel}: {e}")
        else:
            print(f"Canal de inicio ({ivy_online_channel}) no encontrado en caché")

    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.playing,
        name="Deadlock",
        details="Wishing the Arroyos were In console.py",
        state="Wishing the Arroyos were In console.py"
    ))   


async def shutdown_bot():
    global shutdown_started
    if shutdown_started:
        return

    shutdown_started = True
    console_manager.stop()
    if ivy_online_channel > 0:
        canal = bot.get_channel(ivy_online_channel)
        if canal is not None:
            try:
                await canal.send("🔴 I really need a job.")
            except Exception:
                pass
    await bot.change_presence(status=discord.Status.invisible)
    await bot.close()


@bot.event
async def on_disconnect():
    print("⚠️ Desconectado temporalmente de Discord. discord.py intentará reconectar automáticamente...")

@bot.event
async def on_resumed():
    print("🟢 Conexión con Discord reanudada exitosamente.")


for sig in (signal.SIGINT, signal.SIGTERM):
    try:
        signal.signal(sig, handle_signal)
    except (AttributeError, ValueError):
        pass

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    content = message.content.lower()

    if f"{prefijo}" in content:
        await bot.process_commands(message)
        return
    
    if "for ixia" in content:
        await message.reply("https://tenor.com/view/apollo-deadlock-for-ixia-gif-449243688111567927")
        await bot.process_commands(message)
        return
    
    if "ivy" in content:

        randNum = random.randint(1, 8)
        if(randNum < 3):
            gif_url = await obtener_gif(ivy_tags)
            if gif_url:
                await message.reply(gif_url) 
        else:
            randGif = random.choice(LISTA_GIFS)
            await message.reply(f"{randGif}")

    
    # Si defines on_message, DEBES incluir esta línea al final.
    await bot.process_commands(message)

# ===============COMMAND====================

@bot.command(name="hablar", hidden=True)
async def hablar(ctx, canal_o_id: str, *, texto: str):
    # 1. Solo ejecutable por mensaje directo (MD)
    if not isinstance(ctx.channel, discord.DMChannel):
        return

    # 2. Solo el dueño del bot (detección automática de discord.py o por self_discord_id)
    es_dueno = await bot.is_owner(ctx.author) or (self_discord_id and ctx.author.id == self_discord_id)
    if not es_dueno:
        await ctx.send("❌ No tienes permisos para usar este comando.")
        return

    # 3. Obtener el ID del canal (soporta ID directo o mención <#ID>)
    channel_id = None
    if canal_o_id.startswith("<#") and canal_o_id.endswith(">"):
        cleaned = canal_o_id[2:-1]
        if cleaned.isdigit():
            channel_id = int(cleaned)
    elif canal_o_id.isdigit():
        channel_id = int(canal_o_id)

    # 4. Buscar el canal en la caché o en la API de Discord
    canal = None
    if channel_id:
        canal = bot.get_channel(channel_id)
        if canal is None:
            try:
                canal = await bot.fetch_channel(channel_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                canal = None
    else:
        # Búsqueda por nombre de canal en los servidores donde está el bot
        for g in bot.guilds:
            canal = discord.utils.get(g.text_channels, name=canal_o_id)
            if canal:
                break

    if canal is None or not hasattr(canal, "send"):
        await ctx.send(f"❌ No pude encontrar el canal `{canal_o_id}`. Pasa el ID numérico del canal.")
        return

    # 5. Enviar el mensaje al canal
    try:
        await canal.send(texto)
        guild_name = canal.guild.name if hasattr(canal, "guild") and canal.guild else "Servidor"
        await ctx.send(f"✅ Mensaje enviado en #{canal.name} ({guild_name})")
    except discord.Forbidden:
        await ctx.send(f"❌ No tengo permisos suficientes para enviar mensajes en #{canal.name}.")
    except Exception as e:
        await ctx.send(f"❌ Error al enviar el mensaje: {e}")

@hablar.error
async def hablar_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"⚠️ Uso correcto: `{prefijo}hablar <id_canal_o_nombre> <mensaje>`")

@bot.command()
async def ping(ctx):
    await ctx.send("Pong!")

ping.help = "responde Pong!"

@bot.command()
async def son(ctx):
    """son"""
    await ctx.reply("https://tenor.com/view/deadlock-deadlock-sinclair-gif-7336193010982328669")


@bot.command(name="repeat", aliases=["repetir"], hidden=True)
async def repeat(ctx, *, texto: str):
    await ctx.message.delete()
    await ctx.send(f"{texto}")

repeat.help = "repite tu mensaje"

@bot.command()
async def senton(ctx):
    randNum = random.randint(1, 20)
    if(randNum == 20):
        await ctx.send("https://tenor.com/drJeVkoSzP2.gif")
    else:
        await ctx.send("https://klipy.com/gifs/ivy-deadlock-10")

senton.help = "👀"

@bot.command()
async def deadlock(ctx):
    global deadlock_counter
    deadlock_counter = deadlock_counter + 1

    ping_text = f"<@&{deadlock_senal_id}> \n " if deadlock_senal_id > 0 else ""

    if(deadlock_counter == 5):
        await ctx.send(f"{ping_text}https://tenor.com/bN9ff66l0TL.gif")
    elif(deadlock_counter == 6):
        deadlock_counter = 0
        await ctx.send(f"{ping_text}https://tenor.com/jC6vgrbusJc.gif")
    else:
        randGif = random.choice(HOP_ON_DEADLOCK_LIST)
        await ctx.send(f"{ping_text}{randGif}")

deadlock.help = "hace la deadlock señal"


@bot.command()
@commands.is_owner()
async def morite(ctx):
    randNum = random.randint(1, 20)
    if randNum != 20:
        await ctx.send("https://tenor.com/eVXTx0HR8u.gif")
        await shutdown_bot()
    else:
        await ctx.send("Necesitas mucho mas que eso para matarme \n https://tenor.com/drJeVkoSzP2.gif")
        

morite.help = "no churri no lo hagas :("

@bot.command(name="explotar", aliases=["explosion", "boom"])
async def explotar(ctx):
    await ctx.send("https://tenor.com/view/ambs---euthyami-deadlock-deadlock-valve-valve-deadlock-ivy-gif-5811381007726499181%22%3EAmbs")

explotar.help = "explota a ivy"

@bot.command(name="feet", aliases=["pies", "patas"])
async def feet(ctx):
    randNum = random.randint(1, 20)
    if(randNum == 20):
        await ctx.send("https://pbs.twimg.com/media/HHnQgiqW4AAxXK0?format=jpg&name=4096x4096")
    elif (randNum > 1):
        await ctx.message.add_reaction("🤢")
    else:
        await ctx.send("ew :nauseated_face: \n https://tenor.com/view/mo-and-krill-mo-krill-deadlock-ivy-gif-18413066452038964095")

feet.help = "🦶?"

@bot.command()
async def gif(ctx, *, tags: str = None) -> str | None:
    """
    muestra un gif

    gif {tag1} {tag2} ...
    """
    gif = await obtener_gif(tags)
    if gif:
        await ctx.send(gif)
    else:
        await ctx.reply("No pude encontrar un gif con esos tags :(")

@bot.command(name="kiss", aliases=["besar", "beso"])
async def kiss(ctx, miembro: discord.Member | None = None):
        if miembro is None:
            randNum = random.randint(1, 20)
            if randNum == 20:
                await ctx.message.add_reaction("😘")
            elif randNum > 1:
                await ctx.send("https://tenor.com/e59gZz1Lj1f.gif")
            else:
                await ctx.send("hola, no")
            return

        if(miembro.id == ctx.author.id):
            await ctx.send("Vas a... besarte a ti mismo?")
            return
        
        if(miembro == bot.user):
            randNum = random.randint(1, 20)
            if(randNum == 20):
                await ctx.message.add_reaction("😘")
            elif(randNum > 1):
                await ctx.send("https://tenor.com/e59gZz1Lj1f.gif")
            else:
                await ctx.send("hola, no")
            return

        emisor = ctx.author.mention
        mentioned = miembro.mention
        gif_beso = await obtener_gif(["kiss", "anime"])
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass

        if gif_beso:
            embed = discord.Embed(
                description=f"### {emisor} le dio un foking beso a {mentioned}!",
                color=discord.Color.from_rgb(255, 105, 180)
            )
            embed.set_image(url=gif_beso)
            await ctx.send(content=mentioned, embed=embed)
        else:
            await ctx.send(f"{emisor} le dio un foking beso a {mentioned}!")

kiss.help = "le das un beso a alguien"

@kiss.error
async def kiss_error(ctx, error):
    if isinstance(error, commands.MemberNotFound):
        await ctx.send("No pude encontrar a ese usuario en el servidor.")


@bot.command(name="paw")
async def paw(ctx, miembro: discord.Member | None = None):
    randNum = random.randint(1, 10)
    if randNum > 3:
        paw_gif = random.choice(LEPOARD_PAW_LIST)
    else:
        paw_gif = await obtener_gif(["snow", "leopard", "paw"])

    if not paw_gif:
        paw_gif = random.choice(LEPOARD_PAW_LIST)

    # Si se invoca sin miembro, o mencionándose a sí mismo / al bot
    if (miembro is None) or (miembro == bot.user) or (miembro.id == ctx.author.id):
        await ctx.send(paw_gif)
        return

    emisor = ctx.author.mention
    mentioned = miembro.mention
    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass

    direct_url = await resolver_direct_gif_url(paw_gif)
    if not direct_url:
        direct_url = await obtener_gif(["snow", "leopard", "paw"])

    if direct_url:
        embed = discord.Embed(
            description=f"### {emisor} paws at {mentioned}",
            color=discord.Color.from_rgb(255, 105, 180)
        )
        embed.set_image(url=direct_url)
        await ctx.send(content=mentioned, embed=embed)
    else:
        await ctx.send(f"### {emisor} paws at {mentioned}\n{paw_gif}")

paw.help = "paws at you"

@paw.error
async def paw_error(ctx, error):
    if isinstance(error, commands.MemberNotFound):
        await ctx.send("No pude encontrar a ese usuario en el servidor.")

if __name__ == "__main__":
    if not discord_api_key:
        print("❌ ERROR: No se encontró la variable DISCORD_TOKEN en el entorno ni en el archivo .env.")
        print("Crea un archivo .env a partir de .env.example y coloca tu token de Discord.")
        exit(1)

    bot.run(discord_api_key)