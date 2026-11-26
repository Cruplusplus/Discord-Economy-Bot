"""
Esquema de base de datos SQLite para Discord Economy Bot.
Define tablas, índices y migraciones versionadas.
"""

import aiosqlite
from typing import List, Tuple

# Version actual del esquema (incrementar en cada migración)
SCHEMA_VERSION = 2

# Definición de tablas: (nombre_tabla, sql_create)
TABLES: List[Tuple[str, str]] = [
    (
        "schema_version",
        """
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    ),
    (
        "users",
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            wallet INTEGER NOT NULL DEFAULT 100,
            bank INTEGER NOT NULL DEFAULT 0,
            last_work REAL NOT NULL DEFAULT 0,
            last_rob REAL NOT NULL DEFAULT 0,
            prison_until REAL NOT NULL DEFAULT 0,
            last_gamble REAL NOT NULL DEFAULT 0,
            last_paradox_rewind REAL NOT NULL DEFAULT 0,
            last_loss TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    ),
    (
        "inventory",
        """
        CREATE TABLE IF NOT EXISTS inventory (
            user_id INTEGER NOT NULL,
            item_id TEXT NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (user_id, item_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        )
        """
    ),
    (
        "buffs",
        """
        CREATE TABLE IF NOT EXISTS buffs (
            user_id INTEGER NOT NULL,
            buff_id TEXT NOT NULL,
            expires_at REAL NOT NULL,
            PRIMARY KEY (user_id, buff_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        )
        """
    ),
    (
        "stats",
        """
        CREATE TABLE IF NOT EXISTS stats (
            user_id INTEGER PRIMARY KEY,
            times_worked INTEGER NOT NULL DEFAULT 0,
            times_robbed INTEGER NOT NULL DEFAULT 0,
            successful_robs INTEGER NOT NULL DEFAULT 0,
            gambles_won INTEGER NOT NULL DEFAULT 0,
            gambles_lost INTEGER NOT NULL DEFAULT 0,
            ivy_rob_attempts INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        )
        """
    ),
    (
        "lottery",
        """
        CREATE TABLE IF NOT EXISTS lottery (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            jackpot INTEGER NOT NULL DEFAULT 50000,
            last_winner_id INTEGER,
            last_winner_amount INTEGER,
            last_winner_timestamp REAL,
            last_winner_total_tickets INTEGER,
            last_draw TIMESTAMP,
            total_drawn INTEGER NOT NULL DEFAULT 0
        )
        """
    ),
    (
        "lottery_tickets",
        """
        CREATE TABLE IF NOT EXISTS lottery_tickets (
            user_id INTEGER NOT NULL,
            ticket_count INTEGER NOT NULL DEFAULT 0,
            draw_id INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY (user_id, draw_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        )
        """
    ),
    (
        "transactions",
        """
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            tx_type TEXT NOT NULL,           -- 'work', 'coin', 'ruleta', 'blackjack', 'rob', 'deposit', 'withdraw', 'pay', 'duel', 'bet', 'shop_buy', 'shop_use', 'lottery_buy', 'lottery_win', 'event_drop', 'event_trivia', 'event_raid', 'event_roulette', 'event_robin_hood', 'admin_add', 'admin_set', 'paradox_rewind'
            amount INTEGER NOT NULL,         -- positivo = entrada, negativo = salida
            balance_before INTEGER NOT NULL,
            balance_after INTEGER NOT NULL,
            bank_before INTEGER NOT NULL,
            bank_after INTEGER NOT NULL,
            context TEXT,                    -- JSON con detalles extra (game, target, item, etc.)
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        )
        """
    ),
    (
        "cooldowns",
        """
        CREATE TABLE IF NOT EXISTS cooldowns (
            user_id INTEGER NOT NULL,
            command TEXT NOT NULL,
            expires_at REAL NOT NULL,
            PRIMARY KEY (user_id, command),
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        )
        """
    ),
]

# Índices para consultas frecuentes
INDEXES: List[str] = [
    "CREATE INDEX IF NOT EXISTS idx_users_wallet_bank ON users(wallet + bank DESC)",
    "CREATE INDEX IF NOT EXISTS idx_transactions_user_created ON transactions(user_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_transactions_type_created ON transactions(tx_type, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_lottery_tickets_draw ON lottery_tickets(draw_id, ticket_count DESC)",
    "CREATE INDEX IF NOT EXISTS idx_buffs_expires ON buffs(expires_at)",
    "CREATE INDEX IF NOT EXISTS idx_cooldowns_expires ON cooldowns(expires_at)",
]

# Trigger para actualizar updated_at en users
TRIGGERS: List[str] = [
    """
    CREATE TRIGGER IF NOT EXISTS update_users_timestamp
    AFTER UPDATE ON users
    BEGIN
        UPDATE users SET updated_at = CURRENT_TIMESTAMP WHERE user_id = NEW.user_id;
    END
    """
]


async def init_database(db_path: str) -> None:
    """
    Inicializa la base de datos: crea tablas, índices, triggers y registra versión.
    """
    async with aiosqlite.connect(db_path) as db:
        # Activar WAL mode para mejor concurrencia
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA synchronous=NORMAL")
        await db.execute("PRAGMA foreign_keys=ON")
        
        # Crear tablas
        for table_name, sql in TABLES:
            await db.execute(sql)
        
        # Crear índices
        for sql in INDEXES:
            await db.execute(sql)
        
        # Crear triggers
        for sql in TRIGGERS:
            await db.execute(sql)
        
        # Inicializar versión de esquema
        await db.execute(
            "INSERT OR IGNORE INTO schema_version (version) VALUES (?)",
            (SCHEMA_VERSION,)
        )
        
        # Inicializar registro único de lotería
        await db.execute(
            "INSERT OR IGNORE INTO lottery (id, jackpot) VALUES (1, 50000)"
        )
        
        await db.commit()


async def get_schema_version(db_path: str) -> int:
    """Obtiene la versión actual del esquema aplicada."""
    async with aiosqlite.connect(db_path) as db:
        async with db.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1") as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


async def run_migrations(db_path: str) -> None:
    """
    Ejecuta migraciones pendientes según la versión actual.
    Cada migración debe ser idempotente y transaccional.
    """
    current_version = await get_schema_version(db_path)
    
    migrations = {
        1: _migration_v1_initial,
        2: _migration_v2_add_last_loss,
    }
    
    for version in range(current_version + 1, SCHEMA_VERSION + 1):
        if version in migrations:
            print(f"[DB] Ejecutando migración v{version}...")
            await migrations[version](db_path)
            async with aiosqlite.connect(db_path) as db:
                await db.execute(
                    "UPDATE schema_version SET version = ? WHERE version = ?",
                    (version, current_version)
                )
                await db.commit()
            print(f"[DB] Migración v{version} completada.")


async def _migration_v1_initial(db_path: str) -> None:
    """Migración inicial: ya cubierta por init_database()."""
    pass


async def _migration_v2_add_last_loss(db_path: str) -> None:
    """Agrega columna last_loss a la tabla users para guardar la última pérdida rebobinable."""
    async with aiosqlite.connect(db_path) as db:
        # Verificar si la columna ya existe
        async with db.execute("PRAGMA table_info(users)") as cursor:
            columns = [row[1] async for row in cursor]
        
        if "last_loss" not in columns:
            await db.execute("ALTER TABLE users ADD COLUMN last_loss TEXT")
            await db.commit()
            print("[DB] Columna last_loss agregada a la tabla users.")


# --- Utilidades para migración desde JSON ---

async def migrate_from_json(db_path: str, json_path: str) -> None:
    """
    Migra datos desde stats.json (formato legacy) a SQLite.
    Ejecutar una sola vez al migrar por primera vez.
    """
    import json
    import os
    
    if not os.path.exists(json_path):
        print(f"[DB] No existe {json_path}, saltando migración JSON.")
        return
    
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    async with aiosqlite.connect(db_path) as db:
        await db.execute("PRAGMA foreign_keys=ON")
        
        for uid_str, udata in data.items():
            if not uid_str.isdigit() or not isinstance(udata, dict):
                continue
            
            user_id = int(uid_str)
            
            # users
            wallet = int(round(udata.get("wallet", 100)))
            bank = int(round(udata.get("bank", 0)))
            last_work = float(udata.get("last_work", 0))
            last_rob = float(udata.get("last_rob", 0))
            prison_until = float(udata.get("prison_until", 0))
            last_gamble = float(udata.get("last_gamble", 0))
            last_paradox_rewind = float(udata.get("last_paradox_rewind", 0))
            
            await db.execute(
                """
                INSERT OR REPLACE INTO users 
                (user_id, wallet, bank, last_work, last_rob, prison_until, last_gamble, last_paradox_rewind)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, wallet, bank, last_work, last_rob, prison_until, last_gamble, last_paradox_rewind)
            )
            
            # inventory
            inv = udata.get("inventory", {})
            for item_id, qty in inv.items():
                if qty > 0:
                    await db.execute(
                        "INSERT OR REPLACE INTO inventory (user_id, item_id, quantity) VALUES (?, ?, ?)",
                        (user_id, item_id, int(qty))
                    )
            
            # buffs
            buffs = udata.get("buffs", {})
            for buff_id, expires_at in buffs.items():
                if expires_at > 0:
                    await db.execute(
                        "INSERT OR REPLACE INTO buffs (user_id, buff_id, expires_at) VALUES (?, ?, ?)",
                        (user_id, buff_id, float(expires_at))
                    )
            
            # stats
            stats = udata.get("stats", {})
            await db.execute(
                """
                INSERT OR REPLACE INTO stats 
                (user_id, times_worked, times_robbed, successful_robs, gambles_won, gambles_lost, ivy_rob_attempts)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    stats.get("times_worked", 0),
                    stats.get("times_robbed", 0),
                    stats.get("successful_robs", 0),
                    stats.get("gambles_won", 0),
                    stats.get("gambles_lost", 0),
                    stats.get("ivy_rob_attempts", 0),
                )
            )
        
        # lottery data
        lottery_data = data.get("_lottery", {})
        if lottery_data:
            await db.execute(
                """
                UPDATE lottery SET
                    jackpot = ?,
                    last_winner_id = ?,
                    last_winner_amount = ?,
                    last_winner_timestamp = ?,
                    last_winner_total_tickets = ?,
                    last_draw = ?,
                    total_drawn = ?
                WHERE id = 1
                """,
                (
                    int(lottery_data.get("jackpot", 50000)),
                    lottery_data.get("last_winner", {}).get("user_id") if lottery_data.get("last_winner") else None,
                    lottery_data.get("last_winner", {}).get("amount") if lottery_data.get("last_winner") else None,
                    lottery_data.get("last_winner", {}).get("timestamp") if lottery_data.get("last_winner") else None,
                    lottery_data.get("last_winner", {}).get("total_tickets") if lottery_data.get("last_winner") else None,
                    lottery_data.get("last_draw") if lottery_data.get("last_draw") else None,
                    int(lottery_data.get("total_drawn", 0)),
                )
            )
            
            tickets = lottery_data.get("tickets", {})
            for uid_str, count in tickets.items():
                if uid_str.isdigit() and count > 0:
                    await db.execute(
                        "INSERT OR REPLACE INTO lottery_tickets (user_id, ticket_count, draw_id) VALUES (?, ?, 1)",
                        (int(uid_str), int(count))
                    )
        
        await db.commit()
    
    print(f"[DB] Migración desde {json_path} completada: {len([k for k in data.keys() if k.isdigit()])} usuarios.")