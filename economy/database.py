"""
Gestor de datos y persistencia atómica segura para la economía.
Usa SQLite (aiosqlite) con WAL mode, transacciones ACID y Lock asincrónico
para evitar condiciones de carrera y corrupción de datos.
"""

import asyncio
import json
import logging
import time
from collections.abc import MutableMapping
from contextlib import asynccontextmanager
from typing import Any

import aiosqlite


class _ReentrantLock:
    """Lock reentrante para asyncio que permite al mismo task adquirirlo múltiples veces."""
    
    def __init__(self):
        self._lock = asyncio.Lock()
        self._owner = None
        self._count = 0
    
    async def __aenter__(self):
        current_task = asyncio.current_task()
        if self._owner is current_task:
            self._count += 1
            return self
        await self._lock.__aenter__()
        self._owner = current_task
        self._count = 1
        return self
    
    async def __aexit__(self, *args):
        if self._owner is asyncio.current_task():
            self._count -= 1
            if self._count == 0:
                self._owner = None
                await self._lock.__aexit__(*args)
        return False
    
    def locked(self) -> bool:
        return self._lock.locked()


from .config import (
    DATA_FILE_PATH,
    INITIAL_BANK,
    INITIAL_WALLET,
    LOTTERY_BASE_JACKPOT,
)
from .schema import init_database, migrate_from_json, run_migrations


class _DirtyTrackingDict(dict):
    """Dict que notifica a su dueño cuando se modifica."""
    
    def __init__(self, owner: 'UserDataProxy', initial: dict[str, Any], field_name: str):
        self._owner = owner
        self._field_name = field_name
        super().__init__(initial)
    
    def _mark_dirty(self):
        self._owner._mark_field_dirty(self._field_name)
    
    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self._mark_dirty()
    
    def __delitem__(self, key):
        super().__delitem__(key)
        self._mark_dirty()
    
    def setdefault(self, key, default=None):
        if key not in self:
            self[key] = default
        return self[key]
    
    def update(self, *args, **kwargs):
        super().update(*args, **kwargs)
        self._mark_dirty()
    
    def pop(self, key, *args):
        result = super().pop(key, *args)
        self._mark_dirty()
        return result
    
    def clear(self):
        super().clear()
        self._mark_dirty()


class UserDataProxy(MutableMapping):
    """
    Proxy mutable para datos de usuario que rastrea cambios y los persiste en flush().
    Compatible con el patrón: user["wallet"] += 10; user["inventory"]["item"] = 1; await db.save()
    """
    
    def __init__(self, db: 'DataManager', user_id: int, initial: dict[str, Any]):
        self._db = db
        self._user_id = user_id
        self._data = dict(initial)
        self._dirty_fields: set[str] = set()
        self._nested_proxies: dict[str, _DirtyTrackingDict] = {}
        
        # Envolver dicts anidados para rastrear mutaciones internas
        for key in ("inventory", "buffs", "stats", "last_loss"):
            if key in self._data and isinstance(self._data[key], dict):
                self._nested_proxies[key] = _DirtyTrackingDict(self, self._data[key], key)
                self._data[key] = self._nested_proxies[key]
    
    def _mark_field_dirty(self, field: str):
        self._dirty_fields.add(field)
        self._db._register_dirty(self)
    
    def _get_raw(self, key: str) -> Any:
        """Obtiene valor sin proxy (para serialización)."""
        val = self._data.get(key)
        if isinstance(val, _DirtyTrackingDict):
            return val.copy()
        return val
    
    async def flush(self) -> None:
        """Persiste todos los campos sucios en la base de datos."""
        if not self._dirty_fields:
            return
        
        async with aiosqlite.connect(self._db.file_path) as db:
            await db.execute("PRAGMA foreign_keys=ON")
            
            # users table fields
            user_fields = ["wallet", "bank", "last_work", "last_rob", "prison_until", 
                          "last_gamble", "last_paradox_rewind", "last_loss"]
            user_updates = {}
            for k in user_fields:
                if k in self._dirty_fields:
                    val = self._get_raw(k)
                    # Serializar last_loss a JSON
                    if k == "last_loss" and val is not None:
                        val = json.dumps(val, ensure_ascii=False)
                    user_updates[k] = val
            
            if user_updates:
                set_clause = ", ".join(f"{k} = ?" for k in user_updates)
                values = list(user_updates.values()) + [self._user_id]
                await db.execute(f"UPDATE users SET {set_clause} WHERE user_id = ?", values)
            
            # inventory
            if "inventory" in self._dirty_fields:
                await db.execute("DELETE FROM inventory WHERE user_id = ? AND quantity <= 0", (self._user_id,))
                inv = self._get_raw("inventory")
                for item_id, qty in inv.items():
                    if qty > 0:
                        await db.execute(
                            "INSERT OR REPLACE INTO inventory (user_id, item_id, quantity) VALUES (?, ?, ?)",
                            (self._user_id, item_id, qty)
                        )
                    else:
                        await db.execute(
                            "DELETE FROM inventory WHERE user_id = ? AND item_id = ?",
                            (self._user_id, item_id)
                        )
            
            # buffs
            if "buffs" in self._dirty_fields:
                now = time.time()
                await db.execute("DELETE FROM buffs WHERE user_id = ? AND expires_at <= ?", (self._user_id, now))
                buffs = self._get_raw("buffs")
                for buff_id, expires_at in buffs.items():
                    if expires_at > now:
                        await db.execute(
                            "INSERT OR REPLACE INTO buffs (user_id, buff_id, expires_at) VALUES (?, ?, ?)",
                            (self._user_id, buff_id, expires_at)
                        )
                    else:
                        await db.execute(
                            "DELETE FROM buffs WHERE user_id = ? AND buff_id = ?",
                            (self._user_id, buff_id)
                        )
            
            # stats
            if "stats" in self._dirty_fields:
                stats = self._get_raw("stats")
                await db.execute(
                    """
                    INSERT OR REPLACE INTO stats 
                    (user_id, times_worked, times_robbed, successful_robs, gambles_won, gambles_lost, ivy_rob_attempts)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        self._user_id,
                        stats.get("times_worked", 0),
                        stats.get("times_robbed", 0),
                        stats.get("successful_robs", 0),
                        stats.get("gambles_won", 0),
                        stats.get("gambles_lost", 0),
                        stats.get("ivy_rob_attempts", 0),
                    )
                )
            
            await db.commit()
        
        self._dirty_fields.clear()
    
    # --- MutableMapping interface ---
    
    def __getitem__(self, key):
        return self._data[key]
    
    def __setitem__(self, key, value):
        # Envolver dicts anidados para rastrear mutaciones internas
        if key in ("inventory", "buffs", "stats", "last_loss") and isinstance(value, dict) and not isinstance(value, _DirtyTrackingDict):
            self._nested_proxies[key] = _DirtyTrackingDict(self, value, key)
            value = self._nested_proxies[key]
        self._data[key] = value
        self._mark_field_dirty(key)
    
    def __delitem__(self, key):
        del self._data[key]
        self._mark_field_dirty(key)
    
    def __iter__(self):
        return iter(self._data)
    
    def __len__(self):
        return len(self._data)
    
    def __repr__(self):
        return f"UserDataProxy({self._user_id}, {dict(self._data)})"
    
    def __hash__(self):
        return hash(self._user_id)
    
    def __eq__(self, other):
        if isinstance(other, UserDataProxy):
            return self._user_id == other._user_id
        return NotImplemented
    
    def get(self, key, default=None):
        return self._data.get(key, default)
    
    def setdefault(self, key, default=None):
        if key not in self._data:
            self._data[key] = default
            self._mark_field_dirty(key)
        return self._data[key]
    
    def update(self, *args, **kwargs):
        self._data.update(*args, **kwargs)
        for k in (args[0] if args else {}).keys() | kwargs.keys():
            self._mark_field_dirty(k)
    
    def pop(self, key, *args):
        result = self._data.pop(key, *args)
        self._mark_field_dirty(key)
        return result


class DataManager:
    """
    Administra la persistencia de datos en SQLite con operaciones atómicas
    y un Lock asincrónico para evitar condiciones de carrera.
    API compatible con la versión JSON anterior.
    """

    def __init__(self, file_path: str = DATA_FILE_PATH):
        self.file_path = file_path
        self._lock = _ReentrantLock()
        self._initialized = False
        # Para migración inicial: usar el archivo .json correspondiente si existe
        if file_path.endswith('.db'):
            self._json_path = file_path[:-3] + '.json'
        elif file_path.endswith('.json'):
            self._json_path = file_path
        else:
            self._json_path = file_path + '.json'
        self._dirty_proxies: set[UserDataProxy] = set()
        self._log = logging.getLogger("economy.database")

    def _register_dirty(self, proxy: UserDataProxy):
        self._dirty_proxies.add(proxy)

    async def initialize(self) -> None:
        """Inicializa la BD, ejecuta migraciones y migra desde JSON si es primera vez."""
        if self._initialized:
            return
        
        async with self._lock:
            if self._initialized:
                return
            
            # 1. Inicializar esquema
            await init_database(self.file_path)
            
            # 2. Ejecutar migraciones de esquema pendientes
            await run_migrations(self.file_path)
            
            # 3. Migrar desde JSON legacy si existe y la BD está vacía
            await self._maybe_migrate_from_json()
            
            self._initialized = True

    async def _maybe_migrate_from_json(self) -> None:
        """Migra desde stats.json solo si la BD no tiene usuarios aún."""
        async with aiosqlite.connect(self.file_path) as db:
            async with db.execute("SELECT COUNT(*) FROM users") as cursor:
                row = await cursor.fetchone()
                user_count = row[0] if row else 0
        
        if user_count == 0:
            self._log.info("Base de datos vacía, migrando desde JSON legacy", extra={"json_path": self._json_path})
            await migrate_from_json(self.file_path, self._json_path)
        else:
            self._log.info("BD ya tiene usuarios, saltando migración JSON", extra={"user_count": user_count})

    @asynccontextmanager
    async def transaction(self):
        """
        Context manager para transacciones explícitas.
        Uso:
            async with self.transaction() as db:
                await db.execute(...)
        """
        async with self._lock, aiosqlite.connect(self.file_path) as db:
            await db.execute("PRAGMA foreign_keys=ON")
            try:
                yield db
                await db.commit()
            except Exception:
                await db.rollback()
                raise

    # --------------------------------------------------------------------------
    #                           USERS
    # --------------------------------------------------------------------------

    async def get_user_data(self, user_id: int) -> UserDataProxy:
        """
        Obtiene el proxy mutable del usuario, inicializando con valores por defecto si no existe.
        """
        await self.initialize()
        
        async with self._lock:
            async with aiosqlite.connect(self.file_path) as db:
                await db.execute("PRAGMA foreign_keys=ON")
                db.row_factory = aiosqlite.Row
                
                # Obtener o crear usuario
                async with db.execute(
                    "SELECT * FROM users WHERE user_id = ?", (user_id,)
                ) as cursor:
                    row = await cursor.fetchone()
                
                if row is None:
                    # Insertar usuario nuevo con defaults
                    now = time.time()
                    await db.execute(
                        """
                        INSERT INTO users 
                        (user_id, wallet, bank, last_work, last_rob, prison_until, last_gamble, last_paradox_rewind)
                        VALUES (?, ?, ?, 0, 0, 0, ?, 0)
                        """,
                        (user_id, INITIAL_WALLET, INITIAL_BANK, now)
                    )
                    await db.commit()
                    
                    initial = await self._build_user_dict(db, user_id, INITIAL_WALLET, INITIAL_BANK, 0, 0, 0, now, 0)
                    return UserDataProxy(self, user_id, initial)
                
                initial = await self._build_user_dict_from_row(db, row)
                return UserDataProxy(self, user_id, initial)

    async def _build_user_dict(self, db: aiosqlite.Connection, user_id: int, wallet: int, bank: int,
                                last_work: float, last_rob: float, prison_until: float,
                                last_gamble: float, last_paradox_rewind: float) -> dict[str, Any]:
        """Construye el diccionario completo del usuario consultando tablas relacionadas."""
        inv = await self._get_inventory(db, user_id)
        buffs = await self._get_buffs(db, user_id)
        stats = await self._get_stats(db, user_id)
        
        return {
            "wallet": wallet,
            "bank": bank,
            "last_work": last_work,
            "last_rob": last_rob,
            "prison_until": prison_until,
            "last_gamble": last_gamble,
            "last_paradox_rewind": last_paradox_rewind,
            "inventory": inv,
            "buffs": buffs,
            "stats": stats,
        }

    async def _build_user_dict_from_row(self, db: aiosqlite.Connection, row: aiosqlite.Row) -> dict[str, Any]:
        user_id = row["user_id"]
        inv = await self._get_inventory(db, user_id)
        buffs = await self._get_buffs(db, user_id)
        stats = await self._get_stats(db, user_id)
        
        # Deserializar last_loss si existe
        last_loss = row["last_loss"]
        if last_loss:
            try:
                last_loss = json.loads(last_loss)
            except (json.JSONDecodeError, TypeError):
                last_loss = None
        
        return {
            "wallet": row["wallet"],
            "bank": row["bank"],
            "last_work": row["last_work"],
            "last_rob": row["last_rob"],
            "prison_until": row["prison_until"],
            "last_gamble": row["last_gamble"],
            "last_paradox_rewind": row["last_paradox_rewind"],
            "last_loss": last_loss,
            "inventory": inv,
            "buffs": buffs,
            "stats": stats,
        }

    async def _get_inventory(self, db: aiosqlite.Connection, user_id: int) -> dict[str, int]:
        inv = {}
        async with db.execute(
            "SELECT item_id, quantity FROM inventory WHERE user_id = ? AND quantity > 0",
            (user_id,)
        ) as cursor:
            async for row in cursor:
                inv[row["item_id"]] = row["quantity"]
        return inv

    async def _get_buffs(self, db: aiosqlite.Connection, user_id: int) -> dict[str, float]:
        now = time.time()
        buffs = {}
        async with db.execute(
            "SELECT buff_id, expires_at FROM buffs WHERE user_id = ? AND expires_at > ?",
            (user_id, now)
        ) as cursor:
            async for row in cursor:
                buffs[row["buff_id"]] = row["expires_at"]
        return buffs

    async def _get_stats(self, db: aiosqlite.Connection, user_id: int) -> dict[str, int]:
        async with db.execute(
            "SELECT * FROM stats WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
        
        if row is None:
            await db.execute("INSERT INTO stats (user_id) VALUES (?)", (user_id,))
            await db.commit()
            return {
                "times_worked": 0,
                "times_robbed": 0,
                "successful_robs": 0,
                "gambles_won": 0,
                "gambles_lost": 0,
                "ivy_rob_attempts": 0,
            }
        
        return {
            "times_worked": row["times_worked"],
            "times_robbed": row["times_robbed"],
            "successful_robs": row["successful_robs"],
            "gambles_won": row["gambles_won"],
            "gambles_lost": row["gambles_lost"],
            "ivy_rob_attempts": row["ivy_rob_attempts"],
        }

    # --------------------------------------------------------------------------
    #                           LOTTERY
    # --------------------------------------------------------------------------

    async def get_lottery_data(self) -> dict[str, Any]:
        """Obtiene o inicializa el registro del pozo y tickets de la lotería."""
        await self.initialize()
        
        async with self._lock:
            async with aiosqlite.connect(self.file_path) as db:
                await db.execute("PRAGMA foreign_keys=ON")
                db.row_factory = aiosqlite.Row
                
                async with db.execute("SELECT * FROM lottery WHERE id = 1") as cursor:
                    row = await cursor.fetchone()
                
                if row is None:
                    await db.execute("INSERT INTO lottery (id, jackpot) VALUES (1, ?)", (LOTTERY_BASE_JACKPOT,))
                    await db.commit()
                    return {
                        "jackpot": LOTTERY_BASE_JACKPOT,
                        "tickets": {},
                        "last_winner": None,
                        "last_draw": 0.0,
                        "total_drawn": 0,
                    }
                
                # Obtener tickets
                tickets = {}
                async with db.execute(
                    "SELECT user_id, ticket_count FROM lottery_tickets WHERE draw_id = 1 AND ticket_count > 0"
                ) as cursor:
                    async for trow in cursor:
                        tickets[str(trow["user_id"])] = trow["ticket_count"]
                
                last_winner = None
                if row["last_winner_id"] is not None:
                    last_winner = {
                        "user_id": row["last_winner_id"],
                        "amount": row["last_winner_amount"],
                        "timestamp": row["last_winner_timestamp"],
                        "total_tickets": row["last_winner_total_tickets"],
                    }
                
                return {
                    "jackpot": row["jackpot"],
                    "tickets": tickets,
                    "last_winner": last_winner,
                    "last_draw": row["last_draw"] if row["last_draw"] else 0.0,
                    "total_drawn": row["total_drawn"],
                }

    async def reset_lottery(self) -> dict[str, Any]:
        """Reinicia los tickets y repone el pozo base tras un sorteo."""
        await self.initialize()
        
        async with self._lock, aiosqlite.connect(self.file_path) as db:
            await db.execute("PRAGMA foreign_keys=ON")
            now = time.time()
            
            await db.execute(
                """
                    UPDATE lottery SET
                        jackpot = ?,
                        last_draw = ?,
                        total_drawn = total_drawn + 1
                    WHERE id = 1
                    """,
                (LOTTERY_BASE_JACKPOT, now)
            )
            await db.execute("DELETE FROM lottery_tickets WHERE draw_id = 1")
            await db.commit()
            
            return {
                "jackpot": LOTTERY_BASE_JACKPOT,
                "tickets": {},
                "last_draw": now,
                "total_drawn": 1,
            }

    # --------------------------------------------------------------------------
    #                           LEADERBOARD / ALL USERS
    # --------------------------------------------------------------------------

    async def get_all_users(self) -> dict[str, dict[str, Any]]:
        """
        Devuelve todos los registros de usuarios reales para leaderboard.
        Retorna dict {uid_str: user_data_dict} compatible con versión JSON.
        """
        await self.initialize()
        
        async with self._lock:
            async with aiosqlite.connect(self.file_path) as db:
                await db.execute("PRAGMA foreign_keys=ON")
                db.row_factory = aiosqlite.Row
                
                users = {}
                async with db.execute(
                    "SELECT user_id, wallet, bank, last_work, last_rob, prison_until, last_gamble, last_paradox_rewind, last_loss FROM users WHERE wallet + bank > 0 ORDER BY (wallet + bank) DESC"
                ) as cursor:
                    async for row in cursor:
                        uid = str(row["user_id"])
                        user_data = await self._build_user_dict_from_row(db, row)
                        users[uid] = user_data
                
                return users

    async def get_top_wealthy(self, limit: int = 10) -> list[tuple[int, int, int, int]]:
        """
        Retorna top usuarios por riqueza total: [(user_id, total, wallet, bank), ...]
        Optimizado para leaderboard sin cargar inventario/buffs/stats.
        """
        await self.initialize()
        
        async with self._lock:
            async with aiosqlite.connect(self.file_path) as db:
                await db.execute("PRAGMA foreign_keys=ON")
                async with db.execute(
                    "SELECT user_id, wallet, bank, (wallet + bank) as total FROM users WHERE wallet + bank > 0 ORDER BY total DESC LIMIT ?",
                    (limit,)
                ) as cursor:
                    return [(row["user_id"], row["total"], row["wallet"], row["bank"]) async for row in cursor]

    # --------------------------------------------------------------------------
    #                           TRANSACTIONS / AUDIT
    # --------------------------------------------------------------------------

    async def record_transaction(
        self,
        user_id: int,
        tx_type: str,
        amount: int,
        balance_before: int,
        balance_after: int,
        bank_before: int,
        bank_after: int,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Registra una transacción inmutable en la tabla de auditoría."""
        await self.initialize()
        
        self._log.debug(
            "Registrando transacción",
            extra={
                "user_id": user_id,
                "tx_type": tx_type,
                "amount": amount,
                "balance_before": balance_before,
                "balance_after": balance_after,
            },
        )
        
        async with self._lock:
            async with aiosqlite.connect(self.file_path) as db:
                await db.execute("PRAGMA foreign_keys=ON")
                await db.execute(
                    """
                    INSERT INTO transactions 
                    (user_id, tx_type, amount, balance_before, balance_after, bank_before, bank_after, context)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        tx_type,
                        amount,
                        balance_before,
                        balance_after,
                        bank_before,
                        bank_after,
                        json.dumps(context, ensure_ascii=False) if context else None,
                    )
                )
                await db.commit()

    # --------------------------------------------------------------------------
    #                           SAVE / LOCK (Compatibilidad)
    # --------------------------------------------------------------------------

    async def save(self) -> None:
        """
        Persiste todos los proxies sucios registrados.
        Mantiene compatibilidad con el patrón: async with db.lock: ...; await db.save()
        """
        if not self._dirty_proxies:
            return
        
        self._log.debug("Guardando proxies sucios", extra={"count": len(self._dirty_proxies)})
        
        # Flush all dirty proxies in a single transaction for efficiency
        # But we need to be careful - each proxy's flush() does its own transaction.
        # For now, flush sequentially; could optimize with a batch flush later.
        for proxy in list(self._dirty_proxies):
            try:
                await proxy.flush()
            except Exception as e:
                self._log.error("Error flushing proxy", extra={"user_id": proxy._user_id, "error": str(e)})
        
        self._dirty_proxies.clear()

    @property
    def lock(self) -> asyncio.Lock:
        return self._lock