"""
Modulo de configuracion y balanceo para el sistema de economia.
Centraliza la carga de variables de entorno y define constantes sin numeros magicos.
"""

import os
from typing import Optional, Tuple
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()


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
ROB_DICE_MIN: int = 1              # Tirada minima de dado
ROB_DICE_MAX: int = 20             # Tirada maxima (d20)
ROB_FAIL_THRESHOLD: int = 12       # Si la tirada es MENOR (< 12), el robo fracasa
ROB_FAIL_FINE: int = 30            # Fianza/multa cobrada al ladron por la policia
PRISON_DURATION: int = _parse_int_env("PRISON_DURATION", 900)

# --- Rol del Mas Millonario (Top 1 de la Economia) ---
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

# --- Eventos Aleatorios y Automaticos de Ivy ---
EVENT_MIN_INTERVAL_MINUTES: int = _parse_int_env("EVENT_MIN_INTERVAL_MINUTES", 15)
EVENT_MAX_INTERVAL_MINUTES: int = _parse_int_env("EVENT_MAX_INTERVAL_MINUTES", 30)
EVENT_TRIGGER_CHANCE: float = _parse_float_env("EVENT_TRIGGER_CHANCE", 0.5)
ECONOMY_CHANNEL_ID: int = _parse_int_env("ECONOMY_CHANNEL_ID", 0)

# Probabilidades / Pesos de seleccion entre eventos
EVENT_WEIGHT_DROP: float = _parse_float_env("EVENT_WEIGHT_DROP", 22.5)
EVENT_WEIGHT_TRIVIA: float = _parse_float_env("EVENT_WEIGHT_TRIVIA", 22.5)
EVENT_WEIGHT_RAID: float = _parse_float_env("EVENT_WEIGHT_RAID", 22.5)
EVENT_WEIGHT_ROULETTE: float = _parse_float_env("EVENT_WEIGHT_ROULETTE", 22.5)
EVENT_WEIGHT_BOOST: float = _parse_float_env("EVENT_WEIGHT_BOOST", 5.0)
EVENT_WEIGHT_ROBIN_HOOD: float = _parse_float_env("EVENT_WEIGHT_ROBIN_HOOD", 5.0)

# --- Sistema Anti-Abuso y Escalamiento por Inactividad del Lider ---
MIN_RISK_BET_PERCENT: float = _parse_float_env("MIN_RISK_BET_PERCENT", 0.02)  # 2% de la fortuna total del lider
MIN_RISK_BET_FLOOR: int = _parse_int_env("MIN_RISK_BET_FLOOR", 500)          # Piso minimo de almas para validar riesgo

# Escalamiento progresivo de probabilidad para Robin Hood segun horas sin apostar
INACTIVITY_STAGE_1_HOURS: int = _parse_int_env("INACTIVITY_STAGE_1_HOURS", 24)
EVENT_WEIGHT_ROBIN_HOOD_STAGE_1: float = _parse_float_env("EVENT_WEIGHT_ROBIN_HOOD_STAGE_1", 15.0)

INACTIVITY_STAGE_2_HOURS: int = _parse_int_env("INACTIVITY_STAGE_2_HOURS", 48)
EVENT_WEIGHT_ROBIN_HOOD_STAGE_2: float = _parse_float_env("EVENT_WEIGHT_ROBIN_HOOD_STAGE_2", 30.0)

INACTIVITY_STAGE_3_HOURS: int = _parse_int_env("INACTIVITY_STAGE_3_HOURS", 72)
EVENT_WEIGHT_ROBIN_HOOD_STAGE_3: float = _parse_float_env("EVENT_WEIGHT_ROBIN_HOOD_STAGE_3", 50.0)

# Parametros de eventos especificos
DROP_MIN_SOULS: int = _parse_int_env("DROP_MIN_SOULS", 10000)
DROP_MAX_SOULS: int = _parse_int_env("DROP_MAX_SOULS", 20000)
DROP_TIMEOUT_SECONDS: int = _parse_int_env("DROP_TIMEOUT_SECONDS", 120)

TRIVIA_TIMEOUT_SECONDS: int = _parse_int_env("TRIVIA_TIMEOUT_SECONDS", 60)
TRIVIA_REWARD_MIN: int = _parse_int_env("TRIVIA_REWARD_MIN", 9000)
TRIVIA_REWARD_MAX: int = _parse_int_env("TRIVIA_REWARD_MAX", 15000)

RAID_HP: int = _parse_int_env("RAID_HP", 5)
RAID_TIMEOUT_SECONDS: int = _parse_int_env("RAID_TIMEOUT_SECONDS", 60)
RAID_TOTAL_POOL: int = _parse_int_env("RAID_TOTAL_POOL", 40000)

ROULETTE_RISK_WIN_CHANCE: float = _parse_float_env("ROULETTE_RISK_WIN_CHANCE", 0.70)
ROULETTE_WIN_AMOUNT: int = _parse_int_env("ROULETTE_WIN_AMOUNT", 15000)
ROULETTE_PRISON_DURATION: int = _parse_int_env("ROULETTE_PRISON_DURATION", 900)

BOOST_DURATION_MINUTES: int = _parse_int_env("BOOST_DURATION_MINUTES", 20)
BOOST_MULTIPLIER: float = _parse_float_env("BOOST_MULTIPLIER", 12.0)

ROBIN_HOOD_STEAL_PERCENTAGE: float = _parse_float_env("ROBIN_HOOD_STEAL_PERCENTAGE", 0.03)
ROBIN_HOOD_MIN_WALLET: int = _parse_int_env("ROBIN_HOOD_MIN_WALLET", 10000)
