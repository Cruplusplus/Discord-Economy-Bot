"""
Consola interactiva por terminal para administracion y depuracion en tiempo real.
Ejecuta comandos CLI en un hilo secundario daemon conectado de forma asincrona
al bucle de eventos principal (asyncio) sin bloquear el Gateway de Discord.
"""

import sys
import time
import shlex
import asyncio
import threading
from typing import Optional, List
import discord
from discord.ext import commands


class ConsoleManager:
    """Administrador de consola interactiva CLI para el bot."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.is_running = False
        self._queue: Optional[asyncio.Queue] = None
        self._thread: Optional[threading.Thread] = None
        self._task: Optional[asyncio.Task] = None

    def start(self) -> None:
        """Inicia el hilo lector de terminal y la tarea asincrona de procesamiento."""
        if self.is_running:
            return

        self.is_running = True
        self._queue = asyncio.Queue()
        loop = asyncio.get_running_loop()

        self._thread = threading.Thread(
            target=self._stdin_worker,
            args=(self._queue, loop),
            name="IvyConsoleReader",
            daemon=True
        )
        self._thread.start()
        self._task = asyncio.create_task(self._process_commands_loop())
        print("\n[IVY CONSOLE] Consola interactiva iniciada. Escribe 'help' para ver los comandos.")

    def stop(self) -> None:
        """Detiene el bucle de procesamiento de la consola."""
        self.is_running = False
        if self._task and not self._task.done():
            self._task.cancel()

    def _stdin_worker(self, queue: asyncio.Queue, loop: asyncio.AbstractEventLoop) -> None:
        """Hilo en segundo plano que lee lineas de terminal sin bloquear asyncio."""
        while self.is_running:
            try:
                line = sys.stdin.readline()
                if not line:
                    break
                clean_line = line.strip()
                if clean_line:
                    loop.call_soon_threadsafe(queue.put_nowait, clean_line)
            except Exception:
                break

    async def _process_commands_loop(self) -> None:
        """Bucle asincrono en el hilo principal que consume y ejecuta comandos de la consola."""
        while self.is_running:
            try:
                line = await self._queue.get()
                await self._execute_line(line)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[CONSOLA ERROR] Excepcion no controlada: {e}")

    async def _execute_line(self, line: str) -> None:
        """Parsea y deriva la linea ingresada al comando correspondiente."""
        try:
            parts = shlex.split(line)
        except ValueError as e:
            print(f"[CONSOLA ERROR] Error al parsear argumentos: {e}")
            return

        if not parts:
            return

        cmd = parts[0].lower()
        args = parts[1:]

        handlers = {
            "help": self._cmd_help,
            "ayuda": self._cmd_help,
            "hablar": self._cmd_hablar,
            "say": self._cmd_hablar,
            "add": self._cmd_addmoney,
            "addmoney": self._cmd_addmoney,
            "set": self._cmd_setmoney,
            "setmoney": self._cmd_setmoney,
            "bal": self._cmd_balance,
            "balance": self._cmd_balance,
            "money": self._cmd_balance,
            "unjail": self._cmd_unjail,
            "jail": self._cmd_jail,
            "event": self._cmd_event,
            "eventtest": self._cmd_event,
            "lottery": self._cmd_lottery,
            "pozo": self._cmd_lottery,
            "servers": self._cmd_servers,
            "guilds": self._cmd_servers,
            "channels": self._cmd_channels,
            "canales": self._cmd_channels,
            "exit": self._cmd_exit,
            "quit": self._cmd_exit,
        }

        handler = handlers.get(cmd)
        if handler:
            try:
                await handler(args)
            except Exception as e:
                print(f"[CONSOLA ERROR] Error al ejecutar '{cmd}': {e}")
        else:
            print(f"[CONSOLA] Comando desconocido: '{cmd}'. Escribe 'help' para ver la lista de comandos.")

    # --------------------------------------------------------------------------
    #                       IMPLEMENTACION DE COMANDOS CLI
    # --------------------------------------------------------------------------

    async def _cmd_help(self, args: List[str]) -> None:
        print("""
========================================================================
                 IVY DISCORD BOT - CONSOLA DE COMANDOS
========================================================================
- hablar <canal_id|nombre> <mensaje> : Envia un mensaje como Ivy a un canal
- add <user_id> <monto> [w|b]        : Suma o resta almas (w: wallet, b: bank)
- set <user_id> <wallet> [bank]      : Fija el balance exacto de un usuario
- bal <user_id>                      : Consulta el saldo y estado penal
- unjail <user_id>                   : Libera a un usuario de prision
- jail <user_id> [minutos]           : Envia a prision a un usuario
- lottery [info|draw]                : Consulta estado del pozo o ejecuta el sorteo
- event <drop|trivia|raid|etc>       : Dispara un evento en el canal oficial
- servers                            : Lista los servidores donde esta el bot
- channels [guild_id]                : Lista los canales de texto disponibles
- help                               : Muestra este menu de ayuda
- exit / quit                        : Apaga el bot de forma limpia y segura
========================================================================
""")

    async def _cmd_hablar(self, args: List[str]) -> None:
        """Envia un mensaje al canal especificado por ID o por nombre."""
        if len(args) < 2:
            print("[CONSOLA] Uso: hablar <id_canal_o_nombre> <mensaje>")
            return

        target_str = args[0]
        mensaje = " ".join(args[1:])

        canal = None
        # Buscar por ID numerico
        if target_str.isdigit():
            c_id = int(target_str)
            canal = self.bot.get_channel(c_id)
            if canal is None:
                try:
                    canal = await self.bot.fetch_channel(c_id)
                except Exception:
                    canal = None
        else:
            # Buscar por nombre en los servidores disponibles
            for g in self.bot.guilds:
                canal = discord.utils.get(g.text_channels, name=target_str)
                if canal:
                    break

        if canal is None or not hasattr(canal, "send"):
            print(f"[CONSOLA] No se encontro el canal '{target_str}'. Revisa el ID o nombre.")
            return

        try:
            await canal.send(mensaje)
            guild_name = canal.guild.name if hasattr(canal, "guild") and canal.guild else "Servidor"
            print(f"[CONSOLA] Mensaje enviado a #{canal.name} ({guild_name}): {mensaje}")
        except discord.Forbidden:
            print(f"[CONSOLA] Error: Sin permisos para escribir en #{canal.name}.")
        except Exception as e:
            print(f"[CONSOLA] Error al enviar mensaje: {e}")

    async def _cmd_addmoney(self, args: List[str]) -> None:
        """Suma o resta almas a la billetera o banco de un usuario."""
        if len(args) < 2:
            print("[CONSOLA] Uso: add <user_id> <cantidad> [w|b] (ejemplo: add 123456789 500 w)")
            return

        try:
            user_id = int(args[0])
            amount = int(args[1])
        except ValueError:
            print("[CONSOLA] user_id y cantidad deben ser numeros enteros.")
            return

        target_type = "wallet"
        if len(args) >= 3 and args[2].lower() in ("b", "bank", "banco", "cornisa"):
            target_type = "bank"

        economy_cog = self.bot.get_cog("Economy")
        if not economy_cog:
            print("[CONSOLA] Modulo de economia no disponible.")
            return

        async with economy_cog.db.lock:
            user_data = economy_cog.db.get_user_data(user_id)
            current_val = user_data.get(target_type, 0)
            new_val = max(0, current_val + amount)
            user_data[target_type] = new_val
            await economy_cog.db.save()

        # Sincronizar rol de millonario en los servidores del usuario
        for g in self.bot.guilds:
            if g.get_member(user_id):
                await economy_cog.actualizar_rol_millonario(g)

        sign = "+" if amount >= 0 else ""
        print(f"[CONSOLA] Balance actualizado para {user_id}: {sign}{amount:,} en {target_type}. Saldo actual: {new_val:,}")

    async def _cmd_setmoney(self, args: List[str]) -> None:
        """Fija la cantidad exacta en mano y/o banco para un usuario."""
        if len(args) < 2:
            print("[CONSOLA] Uso: set <user_id> <wallet> [bank] (ejemplo: set 123456789 1000 5000)")
            return

        try:
            user_id = int(args[0])
            new_wallet = int(args[1])
            new_bank = int(args[2]) if len(args) >= 3 else None
        except ValueError:
            print("[CONSOLA] Los valores deben ser numeros enteros.")
            return

        economy_cog = self.bot.get_cog("Economy")
        if not economy_cog:
            print("[CONSOLA] Modulo de economia no disponible.")
            return

        async with economy_cog.db.lock:
            user_data = economy_cog.db.get_user_data(user_id)
            user_data["wallet"] = max(0, new_wallet)
            if new_bank is not None:
                user_data["bank"] = max(0, new_bank)
            await economy_cog.db.save()

        for g in self.bot.guilds:
            if g.get_member(user_id):
                await economy_cog.actualizar_rol_millonario(g)

        print(f"[CONSOLA] Valores fijados para {user_id}: Wallet: {user_data['wallet']:,} | Bank: {user_data['bank']:,}")

    async def _cmd_balance(self, args: List[str]) -> None:
        """Muestra el saldo y situacion penal de un usuario."""
        if len(args) < 1:
            print("[CONSOLA] Uso: bal <user_id>")
            return

        try:
            user_id = int(args[0])
        except ValueError:
            print("[CONSOLA] user_id debe ser un numero.")
            return

        economy_cog = self.bot.get_cog("Economy")
        if not economy_cog:
            print("[CONSOLA] Modulo de economia no disponible.")
            return

        async with economy_cog.db.lock:
            user_data = economy_cog.db.get_user_data(user_id)
            wallet = user_data.get("wallet", 0)
            bank = user_data.get("bank", 0)
            in_prison, rem = economy_cog._is_in_prison(user_data)

        # Buscar nombre de usuario en cache
        user_obj = self.bot.get_user(user_id)
        name_str = f"{user_obj.display_name} ({user_obj})" if user_obj else f"ID: {user_id}"

        print(f"""
--------------------------------------------------
[BALANCE] {name_str}
- En mano (Wallet) : {wallet:,}
- En cornisa (Bank): {bank:,}
- Total acumulado  : {wallet + bank:,}
- Estado penal     : {'EN PRISION (' + economy_cog._format_time(rem) + ')' if in_prison else 'Libre'}
--------------------------------------------------""")

    async def _cmd_unjail(self, args: List[str]) -> None:
        """Libera a un usuario encarcelado."""
        if len(args) < 1:
            print("[CONSOLA] Uso: unjail <user_id>")
            return

        try:
            user_id = int(args[0])
        except ValueError:
            print("[CONSOLA] user_id debe ser un numero.")
            return

        economy_cog = self.bot.get_cog("Economy")
        if not economy_cog:
            print("[CONSOLA] Modulo de economia no disponible.")
            return

        async with economy_cog.db.lock:
            user_data = economy_cog.db.get_user_data(user_id)
            user_data["prison_until"] = 0
            await economy_cog.db.save()

        print(f"[CONSOLA] Usuario {user_id} liberado de prision exitosamente.")

    async def _cmd_jail(self, args: List[str]) -> None:
        """Envia a prision a un usuario por una cantidad determinada de minutos."""
        if len(args) < 1:
            print("[CONSOLA] Uso: jail <user_id> [minutos]")
            return

        try:
            user_id = int(args[0])
            minutos = int(args[1]) if len(args) >= 2 else 15
        except ValueError:
            print("[CONSOLA] Los argumentos deben ser numericos.")
            return

        economy_cog = self.bot.get_cog("Economy")
        if not economy_cog:
            print("[CONSOLA] Modulo de economia no disponible.")
            return

        async with economy_cog.db.lock:
            user_data = economy_cog.db.get_user_data(user_id)
            user_data["prison_until"] = time.time() + (minutos * 60)
            await economy_cog.db.save()

        print(f"[CONSOLA] Usuario {user_id} encarcelado por {minutos} minutos.")

    async def _cmd_event(self, args: List[str]) -> None:
        """Dispara un evento aleatorio o especifico en el canal oficial de economia."""
        economy_cog = self.bot.get_cog("Economy")
        if not economy_cog:
            print("[CONSOLA] Modulo de economia no disponible.")
            return

        from economy.config import ECONOMY_CHANNEL_ID
        if not ECONOMY_CHANNEL_ID:
            print("[CONSOLA] ECONOMY_CHANNEL_ID no esta configurado en el .env.")
            return

        channel = self.bot.get_channel(ECONOMY_CHANNEL_ID)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(ECONOMY_CHANNEL_ID)
            except Exception as e:
                print(f"[CONSOLA] No se pudo obtener el canal de economia: {e}")
                return

        tipos = {
            "drop": economy_cog._trigger_soul_drop,
            "trivia": economy_cog._trigger_trivia,
            "raid": economy_cog._trigger_raid,
            "ruleta": economy_cog._trigger_roulette,
            "desafio": economy_cog._trigger_roulette,
            "lluvia": economy_cog._trigger_boost,
            "robin": economy_cog._trigger_robin_hood,
            "millonario": economy_cog._trigger_daily_richest_announcement,
            "magnate": economy_cog._trigger_daily_richest_announcement,
            "loteria": economy_cog._trigger_lottery_draw,
            "pozo": economy_cog._trigger_lottery_draw,
        }

        tipo = args[0].lower() if args else None
        if tipo:
            handler = tipos.get(tipo)
            if not handler:
                validos = ", ".join(tipos.keys())
                print(f"[CONSOLA] Tipo no valido. Opciones: {validos}")
                return
            print(f"[CONSOLA] Disparando evento '{tipo}' en #{channel.name}...")
            await handler(channel)
        else:
            print(f"[CONSOLA] Disparando un evento aleatorio en #{channel.name}...")
            import random
            from economy.config import (
                EVENT_WEIGHT_DROP, EVENT_WEIGHT_TRIVIA, EVENT_WEIGHT_RAID,
                EVENT_WEIGHT_ROULETTE, EVENT_WEIGHT_BOOST, EVENT_WEIGHT_ROBIN_HOOD
            )
            eventos_test = [
                economy_cog._trigger_soul_drop,
                economy_cog._trigger_trivia,
                economy_cog._trigger_raid,
                economy_cog._trigger_roulette,
                economy_cog._trigger_boost,
                economy_cog._trigger_robin_hood,
            ]
            pesos_test = [
                EVENT_WEIGHT_DROP, EVENT_WEIGHT_TRIVIA, EVENT_WEIGHT_RAID,
                EVENT_WEIGHT_ROULETTE, EVENT_WEIGHT_BOOST, EVENT_WEIGHT_ROBIN_HOOD,
            ]
            handler = random.choices(eventos_test, weights=pesos_test, k=1)[0]
            await handler(channel)

    async def _cmd_lottery(self, args: List[str]) -> None:
        """Gestiona la loteria y el pozo del barrio desde la terminal."""
        economy_cog = self.bot.get_cog("Economy")
        if not economy_cog or not hasattr(economy_cog, "lottery"):
            print("[CONSOLA] Modulo de economia o loteria no disponible.")
            return

        subcmd = args[0].lower() if args else "info"

        if subcmd in ("draw", "sortear", "tirar"):
            print("[CONSOLA] Ejecutando sorteo manual del Gran Pozo...")
            await economy_cog._trigger_lottery_draw()
            print("[CONSOLA] Sorteo finalizado y anunciado.")
        else:
            lottery_data = economy_cog.lottery.get_lottery_data()
            jackpot = lottery_data.get("jackpot", 50000)
            tickets = lottery_data.get("tickets", {})
            total_tickets = sum(tickets.values())
            last_winner = lottery_data.get("last_winner")

            print("\n[ESTADO DEL GRAN POZO Y LOTERIA]")
            print(f"- Pozo Acumulado: {jackpot:,} almas")
            print(f"- Total de Tickets en Juego: {total_tickets}")
            print(f"- Apostadores Participando: {len(tickets)}")
            if tickets:
                for uid, qty in sorted(tickets.items(), key=lambda x: x[1], reverse=True)[:5]:
                    prob = (qty / total_tickets * 100) if total_tickets > 0 else 0
                    print(f"  • Usuario {uid}: {qty} ticket(s) ({prob:.1f}%)")
            if last_winner:
                print(f"- Ultimo Ganador: Usuario {last_winner['user_id']} ({last_winner['amount']:,} almas)")
            print()

    async def _cmd_servers(self, args: List[str]) -> None:
        """Lista los servidores en los que participa el bot."""
        if not self.bot.guilds:
            print("[CONSOLA] El bot no esta conectado a ningun servidor.")
            return

        print(f"\n[SERVIDORES CONECTADOS] (Total: {len(self.bot.guilds)})")
        for g in self.bot.guilds:
            owner_str = f"Dueño: {g.owner} (ID: {g.owner_id})" if g.owner else ""
            print(f"- {g.name} | ID: {g.id} | Miembros: {g.member_count} | {owner_str}")
        print()

    async def _cmd_channels(self, args: List[str]) -> None:
        """Lista los canales de texto de un servidor o de todos los servidores."""
        guild_id = int(args[0]) if args and args[0].isdigit() else None
        guilds = [self.bot.get_guild(guild_id)] if guild_id else self.bot.guilds

        for g in guilds:
            if not g:
                continue
            print(f"\n[CANALES DE TEXTO: {g.name} (ID: {g.id})]")
            for c in g.text_channels:
                print(f"  #{c.name} -> ID: {c.id}")
        print()

    async def _cmd_exit(self, args: List[str]) -> None:
        """Apaga el bot de forma segura y controlada."""
        print("[CONSOLA] Apagando el bot de forma controlada...")
        self.stop()
        # Invocar la rutina de apagado del bot
        from la_creatura_bot import shutdown_bot
        await shutdown_bot()
