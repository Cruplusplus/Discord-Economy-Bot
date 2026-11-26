# Changelog

Todos los cambios relevantes del proyecto se documentan en este archivo.

## [1.1.0] - 2026-11-26

### Añadido

- Migración de persistencia JSON a SQLite con `aiosqlite` y modo WAL.
- Esquema normalizado con migraciones versionadas, índices, transacciones y cooldowns.
- Migración automática desde `stats.json` y comando CLI `migrate` para importación manual.
- Logging estructurado JSON con rotación configurable.
- Pipeline GitHub Actions con Ruff, MyPy, pytest, compilación, verificación SQLite y Bandit.
- Registro de comandos slash mediante `discord.app_commands` en paralelo con los comandos de prefijo.
- Variable `SLASH_COMMAND_GUILD_ID` para sincronización inmediata en servidores de desarrollo.

### Corregido

- Prevención de condiciones de carrera mediante lock reentrante y persistencia atómica.
- Verificación CI desacoplada de Discord: ya no usa tokens falsos ni falla con HTTP 401.
- Compatibilidad de caché de roles con `SnowflakeList` de discord.py.
- Referencias indefinidas y errores de lint detectados durante la preparación del release.

### Compatibilidad

- Los comandos con prefijo (`%`) se mantienen como fallback.
- Los datos existentes en `stats.json` se conservan y pueden migrarse a `stats.db`.

## [1.0.0]

Primera release oficial del bot de economía de Ivy.
