"""
Gestor de datos y persistencia atomica segura para la economia.
Utiliza escrituras atomicas temporales (.tmp -> os.replace) y un Lock asincrono
para evitar condiciones de carrera (race conditions) y corrupcion de datos.
"""

import os
import json
import time
import asyncio
from typing import Dict, Any

from .config import DATA_FILE_PATH, INITIAL_WALLET, INITIAL_BANK


class DataManager:
    """
    Administra la persistencia de datos en stats.json con operaciones atomicas
    y un Lock asincrono para evitar condiciones de carrera.
    """

    def __init__(self, file_path: str = DATA_FILE_PATH):
        self.file_path = file_path
        self._lock = asyncio.Lock()
        self._data: Dict[str, Any] = {}
        self._load_sync()

    def _load_sync(self) -> None:
        """Carga sincronica inicial de los datos desde el archivo JSON."""
        if not os.path.exists(self.file_path):
            self._data = {}
            self._save_sync()
            return

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                self._data = json.load(f)
            # Asegurar conversion estricta de todos los valores monetarios a enteros
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
        Escritura atomica segura: escribe primero en un archivo temporal (.tmp)
        y luego lo reemplaza atomicamente con os.replace para evitar corrupcion.
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
            print(f"[IVY ECONOMY] Error critico guardando en {self.file_path}: {e}")
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

    async def save(self) -> None:
        """Guarda los datos en un hilo asincrono para no trabar el bucle de eventos."""
        await asyncio.to_thread(self._save_sync)

    def get_user_data(self, user_id: int) -> Dict[str, Any]:
        """
        Obtiene el diccionario del usuario asegurando la inicializacion segura
        de todas sus claves por defecto y garantizando enteros en la economia.
        """
        uid = str(user_id)
        defaults = {
            "wallet": int(INITIAL_WALLET),
            "bank": int(INITIAL_BANK),
            "last_work": 0.0,
            "last_rob": 0.0,
            "prison_until": 0.0,
            "last_gamble": time.time(),
            "last_paradox_rewind": 0.0,
            "inventory": {},
            "buffs": {},
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

    def get_lottery_data(self) -> Dict[str, Any]:
        """Obtiene o inicializa el registro del pozo y tickets de la loteria."""
        from .config import LOTTERY_BASE_JACKPOT
        lottery_defaults = {
            "jackpot": int(LOTTERY_BASE_JACKPOT),
            "tickets": {},
            "last_winner": None,
            "last_draw": 0.0,
            "total_drawn": 0,
        }
        if "_lottery" not in self._data:
            self._data["_lottery"] = lottery_defaults
        else:
            for k, v in lottery_defaults.items():
                if k not in self._data["_lottery"]:
                    self._data["_lottery"][k] = v
        return self._data["_lottery"]

    def reset_lottery(self) -> Dict[str, Any]:
        """Reinicia los tickets y repone el pozo base tras un sorteo."""
        from .config import LOTTERY_BASE_JACKPOT
        lottery = self.get_lottery_data()
        lottery["tickets"] = {}
        lottery["jackpot"] = int(LOTTERY_BASE_JACKPOT)
        lottery["last_draw"] = time.time()
        lottery["total_drawn"] = lottery.get("total_drawn", 0) + 1
        return lottery

    def get_all_users(self) -> Dict[str, Any]:
        """Devuelve todos los registros de usuarios reales asegurando enteros y filtrando metadatos."""
        user_dict = {}
        for uid_str, udata in self._data.items():
            if not uid_str.isdigit() or not isinstance(udata, dict):
                continue
            if "wallet" in udata and udata["wallet"] is not None:
                udata["wallet"] = int(round(udata["wallet"]))
            if "bank" in udata and udata["bank"] is not None:
                udata["bank"] = int(round(udata["bank"]))
            user_dict[uid_str] = udata
        return user_dict

    @property
    def lock(self) -> asyncio.Lock:
        return self._lock
