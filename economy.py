"""
Módulo de Economía y Timba para Discord Bot (discord.py v2+)
Personificado con la voz, lore y personalidad de Ivy (Deadlock)
- Gárgola de piedra/mármol, protectora de Spanish Harlem (El Barrio, Nueva York).
- Callejera, leal, amistosa, pícara y protectora de su gente.
- Persistencia atómica segura en stats.json y CERO números mágicos.
"""

import os
import json
import time
import random
import asyncio
import aiohttp
from typing import Optional, Tuple, Dict, Any, List

import discord
from discord.ext import commands, tasks

from dotenv import load_dotenv

# Asegurar carga de variables de entorno
load_dotenv()

# ==============================================================================
#                      CONFIGURACIÓN Y BALANCEO (CERO NÚMEROS MÁGICOS)
# ==============================================================================

def _parse_int_env(var_name: str, default: int) -> int:
    val = os.getenv(var_name)
    if val:
        try:
            return int(val.strip())
        except ValueError:
            pass
    return default

def _parse_float_env(var_name: str, default: float) -> float:
    val = os.getenv(var_name)
    if val:
        try:
            return float(val.strip())
        except ValueError:
            pass
    return default

def _parse_optional_int_env(var_name: str, default: Optional[int] = None) -> Optional[int]:
    val = os.getenv(var_name)
    if val:
        try:
            parsed = int(val.strip())
            return parsed if parsed != 0 else None
        except ValueError:
            pass
    return default

# --- Moneda y Valores Iniciales ---
CURRENCY_SYMBOL: str = os.getenv("CURRENCY_SYMBOL", "🪙")
CURRENCY_NAME: str = os.getenv("CURRENCY_NAME", "almas")
INITIAL_WALLET: int = _parse_int_env("INITIAL_WALLET", 100)
INITIAL_BANK: int = _parse_int_env("INITIAL_BANK", 0)

# --- Trabajo y Patrulla (Work) ---
WORK_COOLDOWN: int = _parse_int_env("WORK_COOLDOWN", 60)
WORK_MIN_REWARD: int = _parse_int_env("WORK_MIN_REWARD", 50)
WORK_MAX_REWARD: int = _parse_int_env("WORK_MAX_REWARD", 150)

# --- Apuesta: Cara o Cruz (Coin) ---
COIN_MULTIPLIER: float = _parse_float_env("COIN_MULTIPLIER", 2.0)
COIN_FACES: Tuple[str, str] = ("cara", "cruz")

# --- Apuesta: Ruleta de la Calle (Ruleta) ---
RULETA_WEIGHT_ROJO: int = 18       # 18 casillas rojas
RULETA_WEIGHT_NEGRO: int = 18      # 18 casillas negras
RULETA_WEIGHT_VERDE: int = 1       # 1 casilla verde (pleno especial)

# Multiplicadores de pago
RULETA_PAYOUT_ROJO: float = 2.0    # x2
RULETA_PAYOUT_NEGRO: float = 2.0   # x2
RULETA_PAYOUT_VERDE: float = 14.0  # x14 (alto riesgo, premio gordo)

RULETA_COLOR_MAP = {
    "r": "rojo", "rojo": "rojo", "red": "rojo",
    "b": "negro", "black": "negro", "negro": "negro", "n": "negro",
    "g": "verde", "green": "verde", "verde": "verde", "v": "verde"
}

# --- Robo Callejero (Rob) ---
ROB_COOLDOWN: int = _parse_int_env("ROB_COOLDOWN", 120)
ROB_VICTIM_MIN_WALLET: int = _parse_int_env("ROB_VICTIM_MIN_WALLET", 20)
ROB_DICE_MIN: int = 1              # Tirada mínima de dado
ROB_DICE_MAX: int = 20             # Tirada máxima (d20)
ROB_FAIL_THRESHOLD: int = 12       # Si la tirada es MENOR (< 12), el robo fracasa
ROB_FAIL_FINE: int = 30            # Fianza/multa cobrada al ladrón por la policía
PRISON_DURATION: int = _parse_int_env("PRISON_DURATION", 900)

# --- Rol del Más Millonario (Top 1 de la Economía) ---
RICHEST_ROLE_ID: int = _parse_int_env("RICHEST_ROLE_ID", 0)
RICHEST_ROLE_NAME: str = os.getenv("RICHEST_ROLE_NAME", "El Más Millonario")
RICHEST_ANNOUNCE_CHANNEL_ID: Optional[int] = _parse_optional_int_env("RICHEST_ANNOUNCE_CHANNEL_ID", None)

# --- Duelos y Apuestas (Duelo) ---
DUEL_CHANNEL_ID: Optional[int] = _parse_optional_int_env("DUEL_CHANNEL_ID", None)
DUEL_BET_TIME_SECONDS: int = _parse_int_env("DUEL_BET_TIME_SECONDS", 180)
DUEL_INVITE_TIMEOUT: int = _parse_int_env("DUEL_INVITE_TIMEOUT", 60)
DUEL_UNOPPOSED_PROFIT_PERCENT: float = _parse_float_env("DUEL_UNOPPOSED_PROFIT_PERCENT", 0.5)
GIPHY_API_KEY: str = os.getenv("GIPHY_API_KEY", "")

# --- Archivo de Persistencia ---
DATA_FILE_PATH: str = os.getenv("DATA_FILE_PATH", "stats.json")

# --- Eventos Aleatorios y Automáticos de Ivy ---
EVENT_MIN_INTERVAL_MINUTES: int = _parse_int_env("EVENT_MIN_INTERVAL_MINUTES", 15)
EVENT_MAX_INTERVAL_MINUTES: int = _parse_int_env("EVENT_MAX_INTERVAL_MINUTES", 30)
EVENT_TRIGGER_CHANCE: float = _parse_float_env("EVENT_TRIGGER_CHANCE", 0.5)
ECONOMY_CHANNEL_ID: int = _parse_int_env("ECONOMY_CHANNEL_ID", 0)

# Probabilidades / Pesos de selección entre eventos
# Robin Hood (5%) y Lluvia de Almas (5%); el 90% restante repartido en partes iguales (22.5% c/u)
EVENT_WEIGHT_DROP: float = _parse_float_env("EVENT_WEIGHT_DROP", 22.5)
EVENT_WEIGHT_TRIVIA: float = _parse_float_env("EVENT_WEIGHT_TRIVIA", 22.5)
EVENT_WEIGHT_RAID: float = _parse_float_env("EVENT_WEIGHT_RAID", 22.5)
EVENT_WEIGHT_ROULETTE: float = _parse_float_env("EVENT_WEIGHT_ROULETTE", 22.5)
EVENT_WEIGHT_BOOST: float = _parse_float_env("EVENT_WEIGHT_BOOST", 5.0)
EVENT_WEIGHT_ROBIN_HOOD: float = _parse_float_env("EVENT_WEIGHT_ROBIN_HOOD", 5.0)

# Parámetros de eventos específicos
DROP_MIN_SOULS: int = _parse_int_env("DROP_MIN_SOULS", 3000)
DROP_MAX_SOULS: int = _parse_int_env("DROP_MAX_SOULS", 10000)
DROP_TIMEOUT_SECONDS: int = _parse_int_env("DROP_TIMEOUT_SECONDS", 120)

TRIVIA_TIMEOUT_SECONDS: int = _parse_int_env("TRIVIA_TIMEOUT_SECONDS", 60)
TRIVIA_REWARD_MIN: int = _parse_int_env("TRIVIA_REWARD_MIN", 2000)
TRIVIA_REWARD_MAX: int = _parse_int_env("TRIVIA_REWARD_MAX", 5000)

RAID_HP: int = _parse_int_env("RAID_HP", 5)
RAID_TIMEOUT_SECONDS: int = _parse_int_env("RAID_TIMEOUT_SECONDS", 60)
RAID_TOTAL_POOL: int = _parse_int_env("RAID_TOTAL_POOL", 15000)

ROULETTE_RISK_WIN_CHANCE: float = _parse_float_env("ROULETTE_RISK_WIN_CHANCE", 0.70)
ROULETTE_WIN_AMOUNT: int = _parse_int_env("ROULETTE_WIN_AMOUNT", 8000)
ROULETTE_PRISON_DURATION: int = _parse_int_env("ROULETTE_PRISON_DURATION", 900)

BOOST_DURATION_MINUTES: int = _parse_int_env("BOOST_DURATION_MINUTES", 20)
BOOST_MULTIPLIER: float = _parse_float_env("BOOST_MULTIPLIER", 10.0)

ROBIN_HOOD_STEAL_PERCENTAGE: float = _parse_float_env("ROBIN_HOOD_STEAL_PERCENTAGE", 0.03)
ROBIN_HOOD_MIN_WALLET: int = _parse_int_env("ROBIN_HOOD_MIN_WALLET", 10000)

IVY_TRIVIA_QUESTIONS: List[Dict[str, Any]] = [
    {
        "pregunta": "¿Qué criatura mística de piedra es Ivy, la protectora de Spanish Harlem?",
        "respuestas": ["gargola", "una gargola", "gargoyle"],
        "pista": "Alas de piedra y garras de mármol tallado."
    },
    {
        "pregunta": "¿En qué emblemático barrio de Nueva York patrulla y tiene su hogar Ivy en Deadlock?",
        "respuestas": ["spanish harlem", "el barrio", "harlem"],
        "pista": "El famoso vecindario latino del este de Manhattan."
    },
    {
        "pregunta": "¿Cómo se llama la habilidad definitiva de Ivy donde vuela cargando a un aliado o una bomba?",
        "respuestas": ["air drop", "airdrop"],
        "pista": "Dos palabras en inglés: entrega express desde los cielos."
    },
    {
        "pregunta": "¿Cómo se llama el sabio amigo y compañero de Ivy en el diner que siempre le da consejos?",
        "respuestas": ["carlos"],
        "pista": "Ivy siempre dice: 'Carlos always says...'"
    },
    {
        "pregunta": "¿Cómo se llama la habilidad de Ivy que la transforma en una estatua indestructible curando su salud?",
        "respuestas": ["stone form", "forma de piedra", "stoneform"],
        "pista": "Se convierte en piedra pura para descansar las alas."
    },
    {
        "pregunta": "¿Cuál es la moneda o recurso místico que juntamos en las calles de Deadlock?",
        "respuestas": ["almas", "souls", "alma"],
        "pista": "Flotan en orbes brillantes cuando caen los combatientes."
    },
    {
        "pregunta": "¿Qué plato tradicional caribeño se prepara en el diner de Carlos los viernes a la noche?",
        "respuestas": ["mofongo"],
        "pista": "Plátano verde frito y machacado con ajo y chicharrón."
    },
    {
        "pregunta": "¿Cómo se llama el sindicato mafioso enemigo que intenta apoderarse de Spanish Harlem?",
        "respuestas": ["sindicato mendoza", "mendoza"],
        "pista": "Lleva el apellido de la peligrosa familia criminal."
    },
    {
        "pregunta": "¿Cuál es la habilidad de Ivy que arroja un enramado de espinas para enredar y ralentizar enemigos?",
        "respuestas": ["kudzu vine", "kudzu", "enredadera", "espinas"],
        "pista": "Una planta trepadora japonesa que brota del asfalto."
    },
    {
        "pregunta": "¿Qué tipo de arma empuña Ivy en Deadlock para disparar ráfagas de energía mágica?",
        "respuestas": ["subfusil", "smg", "metralleta"],
        "pista": "Dispara ráfagas veloces a corta y media distancia."
    }
]


# ==============================================================================
#                  BANCO DE DIÁLOGOS Y FRASES DE IVY (DEADLOCK)
# ==============================================================================

IVY_WORK_ACTIVITIES: List[str] = [
    "Patrullaste las cornisas de Spanish Harlem vigilando que el Sindicato Mendoza no asome las narices.",
    "Hiciste un turno extra de mozo en el diner del barrio para darle una mano a Sophie y Carlos.",
    "Te subiste a lo alto de la catedral con Ivy a otear callejones y juntar almas sueltas que cayeron del cielo.",
    "Le diste una paliza a un par de matones de poca monta que intentaban extorsionar a un quiosquero.",
    "Hiciste una entrega express por los cielos con Air Drop esquivando cables y chimeneas.",
    "Ayudaste a una doña del barrio a subir las bolsas de la compra hasta el quinto piso volando bajito.",
    "Hiciste guardia nocturna sobrevolando El Barrio antes de que empiece la noche de mofongo.",
    "Esparciste unas enredaderas de espinas para frenar a unos carteristas en plena avenida."
]

IVY_WORK_COOLDOWN_QUOTES: List[str] = [
    "Oye, chacho, hasta las gárgolas nos cansamos. Me estoy poniendo en Stone Form para descansar las alas. Esperá **{time}**.",
    "Calma las plumas, amigo. Carlos siempre dice que apresurarse solo trae líos. Date una vuelta y vuelve en **{time}**.",
    "¡Uff! Mis alas de piedra necesitan un respiro antes de la próxima ronda aérea. Bancame **{time}**.",
    "Todo a su tiempo, chiquito. El barrio está tranquilo por ahora. Podrás patrullar de nuevo en **{time}**."
]

IVY_PRISON_WARNING_QUOTES: List[str] = [
    "🚨 ¡Pero si estás en el calabozo, chacho! Te advertí que no te hicieras el vivo con la guardia. Te quedan **{time}** de condena tras las rejas.",
    "⛓️ ¿Pretendes patrullar esposado a la pared? ¡Quédate ahí! La policía te tiene guardado por **{time}** más. Nada de mofongo para los presos.",
    "🚔 ¡Ni hablar! Estás pagando condena por andar de manos largas. Te restan **{time}** en cana. Tómate el tiempo para pensar en lo que hiciste.",
    "🔒 Lo siento, amigo, pero las reglas son las reglas. Te quedan **{time}** a la sombra. Hasta que no cumplas tu condena, no sales a la calle."
]

IVY_COIN_WIN_QUOTES: List[str] = [
    "¡Ja! ¡Viste eso! ¡Cayó **{face}**! La suerte de las alturas nunca me falla.",
    "¡Bien hecho, chacho! Sabía que teníamos buena mano. ¡Duplicaste la apuesta!",
    "¡Woooo! ¡Le pegaste justo al **{face}**! ¡Más almas para la alcancía del equipo!",
    "¡Eso es! Como dice Carlos: las oportunidades hay que agarrarlas en el aire. ¡Ganaste!"
]

IVY_COIN_LOSS_QUOTES: List[str] = [
    "Ay, no... Salió **{face}**. Lo siento, chacho, la moneda cayó del lado equivocado esta vez.",
    "Mala pata, amigo... Salió **{face}**. Pero ey, ¡de peores caídas de piedra me he levantado!",
    "Uff, dolió en la billetera... Salió **{face}**. ¡No te me achiques, que la próxima la clavamos!",
    "¡Ay Dios! La gravedad jugó en contra. Perdiste esas fichas... Hay que saber cuándo replegarse."
]

IVY_RULETA_WIN_NORMAL_QUOTES: List[str] = [
    "¡Esa es! La bolilla frenó en {emoji} **{color}**. ¡Victoria limpia para la banda!",
    "¡Lo conseguimos! ¡Viste que hacer equipo rinde frutos! Te llevas un buen fajo a la bolsa.",
    "¡Wooo! ¡Cayó en {emoji} **{color}**! ¡Quién dice que vigilar los tejados no da para divertirse un rato!"
]

IVY_RULETA_WIN_VERDE_QUOTES: List[str] = [
    "¡¿PERO QUÉ VEN MIS OJOS?! 🟢 ¡¡EL CERO VERDE!! ¡Le diste al pleno imposible, chacho! ¡Te llenaste de almas hasta el cogote! (x{multiplicador})",
    "¡¡SANTO CIELO!! 🟢 ¡Cayo en el verde! ¡Esto va directo a las leyendas de Spanish Harlem! ¡Te forraste de almas con multiplicador x{multiplicador}!"
]

IVY_RULETA_LOSS_QUOTES: List[str] = [
    "La bolilla rodó y se clavó en {emoji} **{color}**. La casa no perdona, amigo. Toca afilar la puntería.",
    "¡Ay, qué mala leche! Se fue al {emoji} **{color}**. Como siempre le digo a Abrams: a veces el destino te esquiva.",
    "Ronda perdida: cayó en {emoji} **{color}**. ¡Tranqui, que las gárgolas no nos rendimos por una mala tirada!"
]

IVY_ROB_FAIL_QUOTES: List[str] = [
    "🚔 **¡¡ALTO AHÍ!! ¡SONÓ LA ALARMA!**\n🎲 Sacaste un mísero **{dice}** en el dado (necesitabas ≥ {thresh}).\n¡Te vieron venir a tres cuadras, chacho! Te interceptó la patrulla vecinal con las manos en la billetera de {victim}.\n\n⛓️ **A la sombra:** Vas al calabozo por **{duration} minutos** (olvídate de laburar o moverte).\n💸 **Fianza:** Tuviste que soltar **-{fine:,} {currency}** para no empeorar las cosas.",
    "🚨 **¡TE AGARRARON CON LAS MANOS EN LA MASA!**\n🎲 Tiraste un pobre **{dice}** (umbral: ≥ {thresh}).\n¡Elegiste la víctima equivocada! Unos guardias te placaron contra el asfalto frente a {victim}.\n\n⛓️ **Condena:** **{duration} minutos en cana** sin derecho a fianza fácil.\n💸 **Multa:** La policía te confiscó **-{fine:,} {currency}**.",
    "🛑 **¡MALA IDEA, CHACHO!**\n🎲 Tu tirada fue de **{dice}** (necesitabas ≥ {thresh}).\nTropezaste con una teja suelta y caíste justo enfrente de la comisaría.\n\n⛓️ **Preso:** Te comés **{duration} minutos** tras las rejas.\n💸 **Gastos legales:** Perdiste **-{fine:,} {currency}**."
]

IVY_ROB_SUCCESS_QUOTES: List[str] = [
    "🥷 **¡QUÉ ESCURRIDIZO! ¡GOLPE LIMPIO!**\n🎲 Clavaste un hermoso **{dice}** en el dado (≥ {thresh}).\nTe moviste entre las sombras como gárgola en noche cerrada y le manoteaste **+{loot:,} {currency}** de los bolsillos a {victim}.",
    "🤫 **¡AFANO SILENCIOSO!**\n🎲 Tirada maestra de **{dice}** (≥ {thresh}).\nNi cuenta se dio {victim} mientras le sacabas **+{loot:,} {currency}** de la campera. ¡Andá a esconderlo a la cornisa con `%deposit` antes de que se avive!",
    "🦅 **¡ZARPAZO DESDE EL TEJADO!**\n🎲 Tiraste un sólido **{dice}** (≥ {thresh}).\nBajaste en picada, le afanaste **+{loot:,} {currency}** a {victim} y remontaste el vuelo antes de que pudiera parpadear."
]


# ==============================================================================
#                 GESTOR DE DATOS Y PERSISTENCIA ATÓMICA SEGURA
# ==============================================================================

class DataManager:
    """
    Administra la persistencia de datos en stats.json con operaciones atómicas
    y un Lock asíncrono para evitar condiciones de carrera (race conditions).
    """

    def __init__(self, file_path: str = DATA_FILE_PATH):
        self.file_path = file_path
        self._lock = asyncio.Lock()
        self._data: Dict[str, Any] = {}
        self._load_sync()

    def _load_sync(self) -> None:
        """Carga sincrónica inicial de los datos desde el archivo JSON."""
        if not os.path.exists(self.file_path):
            self._data = {}
            self._save_sync()
            return

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                self._data = json.load(f)
            # Asegurar conversión estricta de todos los valores monetarios a enteros
            for udata in self._data.values():
                if isinstance(udata, dict):
                    if "wallet" in udata and udata["wallet"] is not None:
                        udata["wallet"] = int(round(udata["wallet"]))
                    if "bank" in udata and udata["bank"] is not None:
                        udata["bank"] = int(round(udata["bank"]))
        except (json.JSONDecodeError, IOError) as e:
            print(f"[IVY ECONOMY] No se pudo leer {self.file_path}: {e}. Creando nuevo registro.")
            self._data = {}

    def _save_sync(self) -> None:
        """
        Escritura atómica segura: escribe primero en un archivo temporal (.tmp)
        y luego lo reemplaza atómicamente con os.replace para evitar corrupción.
        """
        # Asegurar antes de guardar que wallet y bank sean siempre int
        for udata in self._data.values():
            if isinstance(udata, dict):
                if "wallet" in udata and udata["wallet"] is not None:
                    udata["wallet"] = int(round(udata["wallet"]))
                if "bank" in udata and udata["bank"] is not None:
                    udata["bank"] = int(round(udata["bank"]))

        temp_path = f"{self.file_path}.tmp"
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=4, ensure_ascii=False)
            os.replace(temp_path, self.file_path)
        except Exception as e:
            print(f"[IVY ECONOMY] Error crítico guardando en {self.file_path}: {e}")
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

    async def save(self) -> None:
        """Guarda los datos en un hilo asíncrono para no trabar el bucle de eventos."""
        await asyncio.to_thread(self._save_sync)

    def get_user_data(self, user_id: int) -> Dict[str, Any]:
        """
        Obtiene el diccionario del usuario asegurando la inicialización segura
        de todas sus claves por defecto y garantizando enteros en la economía.
        """
        uid = str(user_id)
        defaults = {
            "wallet": int(INITIAL_WALLET),
            "bank": int(INITIAL_BANK),
            "last_work": 0.0,
            "last_rob": 0.0,
            "prison_until": 0.0,
            "stats": {
                "times_worked": 0,
                "times_robbed": 0,
                "successful_robs": 0,
                "gambles_won": 0,
                "gambles_lost": 0,
                "ivy_rob_attempts": 0
            }
        }

        if uid not in self._data:
            self._data[uid] = defaults
        else:
            for k, v in defaults.items():
                if k not in self._data[uid]:
                    self._data[uid][k] = v

        # Garantizar que wallet y bank sean siempre enteros
        user = self._data[uid]
        if "wallet" in user and user["wallet"] is not None:
            user["wallet"] = int(round(user["wallet"]))
        if "bank" in user and user["bank"] is not None:
            user["bank"] = int(round(user["bank"]))

        return user

    def get_all_users(self) -> Dict[str, Any]:
        """Devuelve todos los registros de usuarios asegurando enteros."""
        for udata in self._data.values():
            if isinstance(udata, dict):
                if "wallet" in udata and udata["wallet"] is not None:
                    udata["wallet"] = int(round(udata["wallet"]))
                if "bank" in udata and udata["bank"] is not None:
                    udata["bank"] = int(round(udata["bank"]))
        return self._data

    @property
    def lock(self) -> asyncio.Lock:
        return self._lock


# ==============================================================================
#                  CLASES DE INTERFAZ GRÁFICA (DISCORD.UI.VIEW)
# ==============================================================================

class SoulDropView(discord.ui.View):
    """Botón de reflejos para recoger un alijo de almas."""
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
            user_data["wallet"] += self.amount
            await self.cog.db.save()

        embed = discord.Embed(
            title="⚡ ¡ALIJO RECLAMADO A TODA VELOCIDAD!",
            description=(
                f"¡Rápido como una gárgola en picada! **{interaction.user.mention}** se abalanzó sobre el alijo "
                f"y se embolsó **+{self.amount:,} {CURRENCY_NAME} {CURRENCY_SYMBOL}**.\n\n"
                f"En sus bolsillos ahora carga con: **{user_data['wallet']:,} {CURRENCY_SYMBOL}**"
            ),
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
        self.attacker_ids: set[int] = set()
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
    """El desafío riesgoso de Ivy: 70% premio gordo vs 30% cárcel."""
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
    """Impuesto a la opulencia: bolsa cobrada al más rico disponible para los demás."""
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


# ==============================================================================
#                          COG PRINCIPAL DE ECONOMÍA
# ==============================================================================

class Economy(commands.Cog):
    """Módulo de economía y timba personificado por Ivy de Deadlock."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = DataManager(DATA_FILE_PATH)
        self.active_duels: Dict[int, Dict[str, Any]] = {}
        self.pending_challenges: set[int] = set()
        self.work_boost_active: bool = False
        self.work_boost_until: float = 0.0
        self.active_event: bool = False

    # --------------------------------------------------------------------------
    #                         MÉTODOS AUXILIARES
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
    #              SISTEMA DINÁMICO: ROL DEL MÁS MILLONARIO (TOP 1)
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
        async with self.db.lock:
            all_users = self.db.get_all_users()

        best_member: Optional[discord.Member] = None
        max_wealth: int = -1

        for uid_str, data in all_users.items():
            try:
                user_id = int(uid_str)
            except ValueError:
                continue

            total = data.get("wallet", 0) + data.get("bank", 0)
            if total <= 0:
                continue

            member = guild.get_member(user_id)
            if member is None:
                try:
                    member = await guild.fetch_member(user_id)
                except (discord.NotFound, discord.HTTPException):
                    member = None

            if member is None or member.bot:
                continue

            if total > max_wealth:
                max_wealth = total
                best_member = member

        if best_member is None:
            return None

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
            except discord.Forbidden:
                print(f"[IVY ECONOMY] Sin permisos de jerarquía para asignar el rol '{role.name}' a {best_member.display_name}. Coloca el rol del bot por encima de '{role.name}'.")
                return best_member
            except discord.HTTPException as e:
                print(f"[IVY ECONOMY] Error de Discord al asignar rol: {e}")
                return best_member

            # 6. Anuncio dinámico con la voz de Ivy
            target_channel = None
            if RICHEST_ANNOUNCE_CHANNEL_ID:
                target_channel = guild.get_channel(RICHEST_ANNOUNCE_CHANNEL_ID)
            if target_channel is None:
                target_channel = announce_channel

            if target_channel:
                desc = (
                    f"¡Atención a todos los vecinos de Spanish Harlem! **{best_member.mention}** acaba de coronarse "
                    f"como el nuevo portador de **{role.name}** con un patrimonio de **{max_wealth:,} {CURRENCY_NAME} {CURRENCY_SYMBOL}**.\n"
                    f"https://www.youtube.com/watch?v=0UvtvJlkdes \n\n"
                )
                if previous_leader:
                    desc += f"🥀 {previous_leader.mention} no pudo aguantar la presión y tuvo que ceder la corona de los tejados.\n\n"

                desc += "*«Desde las cornisas veo brillar ese fajo de almas. ¡A ver cuánto tiempo aguantas en la cima antes de que te afanen, chacho!»*"

                embed = discord.Embed(
                    title=f"👑 ¡NUEVO MAGNATE DEL BARRIO: {role.name.upper()}!",
                    description=desc,
                    color=discord.Color.gold()
                )
                embed.set_thumbnail(url=best_member.display_avatar.url)
                embed.set_footer(text="Carlos always says: the higher you climb, the harder the fall.")
                try:
                    await target_channel.send(embed=embed)
                except (discord.Forbidden, discord.HTTPException):
                    pass

        return best_member

    @commands.Cog.listener()
    async def on_ready(self):
        """Sincroniza el rol del más millonario al iniciar o reconectar el bot."""
        for guild in self.bot.guilds:
            try:
                await self.actualizar_rol_millonario(guild)
            except Exception as e:
                print(f"[IVY ECONOMY] Error sincronizando rol de millonario en {guild.name}: {e}")

    # --------------------------------------------------------------------------
    #                       COMANDO: WORK / TRABAJAR
    # --------------------------------------------------------------------------

    @commands.command(name="work", aliases=["w", "W","trabajar", "chambear"])
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
                await self.db.save()

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
                await self.db.save()

                quote = random.choice(IVY_COIN_LOSS_QUOTES).format(face=resultado.upper())
                embed = discord.Embed(
                    title=f"🪙 Moneda al Aire: Salió {resultado.upper()}",
                    description=f"{quote}\n\n"
                                f"💸 **Pérdida:** -{parsed_amount:,} {CURRENCY_SYMBOL}\n"
                                f"💵 **Te quedaron:** {user['wallet']:,} {CURRENCY_SYMBOL}",
                    color=discord.Color.red()
                )
                embed.set_footer(text="I always get a little nervous before taking big risks...")

        await ctx.reply(embed=embed)
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
                await self.db.save()

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
                await self.db.save()

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

        await ctx.reply(embed=embed)
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
                botin = int((victim_data["wallet"]*rob_prc)/100)

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
            medal = "🥇" if rank_num == 1 else "🥈" if rank_num == 2 else "🥉" if rank_num == 3 else f"**#{rank_num}**"
            lines.append(f"{medal}{crown} **{name}**{tag}: {total:,} {CURRENCY_SYMBOL} *(Mano: {data.get('wallet', 0):,} | Cornisa: {data.get('bank', 0):,})*")
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
    #                   SISTEMA DE COMBATE Y APUESTAS: DUELO
    # --------------------------------------------------------------------------

    @commands.command(name="duelo", aliases=["duel"])
    async def duelo(self, ctx: commands.Context, member: discord.Member, monto: str):
        """Reta a un miembro a un combate callejero con apuestas de la comunidad."""
        if ctx.guild is None:
            await ctx.reply("❌ Los duelos solo se pueden celebrar en las calles de un servidor.")
            return

        # Restricción de canal si DUEL_CHANNEL_ID está configurado
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

        # Registrar desafío pendiente para evitar desafíos solapados
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

            # Si aceptó, verificamos que ambos tengan el dinero en mano (wallet)
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
                # Si nadie le apostó al ganador, el ganador del duelo se queda con el pozo perdedor
                winner_data["wallet"] += losing_pool

            for bet in losing_bets:
                payouts_info.append({
                    "user": bet["user"],
                    "won": False,
                    "bet": bet["amount"],
                    "profit": -bet["amount"],
                    "total": 0
                })

            await self.db.save()

        # Sincronizar el rol del más millonario tras el cambio de riquezas
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

        # Notificación con @everyone y mención a los apostadores
        notification_text = f"@everyone 📢 ¡El duelo ha terminado! Ganador: {winner.mention}"
        if payouts_info:
            resumen_pings = " | " + " ".join(
                f"{p['user'].mention} ({'Ganaste' if p['won'] else 'Perdiste'})" for p in payouts_info
            )
            # Evitar exceder el límite de 2000 caracteres de Discord
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

        # Restricción de canal si DUEL_CHANNEL_ID está configurado
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
        embed_bet.set_footer(text="Spanish Harlem nunca olvida a los que arriesgan.")
        await ctx.reply(embed=embed_bet)

    # --------------------------------------------------------------------------
    #                     SISTEMA DE EVENTOS ALEATORIOS (LOOP)
    # --------------------------------------------------------------------------

    async def cog_load(self):
        """Inicia el loop de eventos periódicos al cargar el Cog."""
        if not self.random_events_loop.is_running():
            self.random_events_loop.start()

    async def cog_unload(self):
        """Cancela el loop de eventos al descargar el Cog."""
        self.random_events_loop.cancel()

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

        eventos = [
            self._trigger_soul_drop,
            self._trigger_trivia,
            self._trigger_raid,
            self._trigger_roulette,
            self._trigger_boost,
            self._trigger_robin_hood,
        ]

        pesos = [
            EVENT_WEIGHT_DROP,
            EVENT_WEIGHT_TRIVIA,
            EVENT_WEIGHT_RAID,
            EVENT_WEIGHT_ROULETTE,
            EVENT_WEIGHT_BOOST,
            EVENT_WEIGHT_ROBIN_HOOD,
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

        deadline = int(time.time() + DROP_TIMEOUT_SECONDS)
        view = RobinHoodView(self, richest_member, stolen_amount)
        embed = discord.Embed(
            title="🏹 ¡IMPUESTO A LA OPULENCIA: ROBIN HOOD CALLEJERO!",
            description=(
                f"Ivy se coló silenciosa como gárgola en las propiedades de **{richest_member.mention}** y le sustrajo un **{int(ROBIN_HOOD_STEAL_PERCENTAGE * 100)}%** "
                f"de su fortuna {origen_robo} por andar acaparando almas.\n\n"
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


# ==============================================================================
#                      FUNCIÓN DE REGISTRO DEL COG
# ==============================================================================

async def setup(bot: commands.Bot):
    """Función de entrada estándar de discord.py para cargar la extensión."""
    await bot.add_cog(Economy(bot))
