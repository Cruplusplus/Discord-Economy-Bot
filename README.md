# 🗽 Ivy Discord Economy Bot

Bot de Discord temático inspirado en **Ivy de Deadlock**, diseñado para gestionar un sistema integral de **economía, apuestas, duelos y eventos aleatorios periódicos** en tu servidor con persistencia atómica en JSON, cero números mágicos y total personalización mediante variables de entorno.

---

## ✨ Características Principales

### 🪙 Sistema de Economía Completo
- **Billetera y Banco (Cornisa):** Gestión segura de almas en mano y resguardadas.
- **Trabajo Callejero (`%work`):** Genera almas periódicamente con recompensas aleatorias.
- **Robo con Riesgo (`%rob`):** Sistema de dados (d20). Si fallas, la policía te cobra fianza o te envía al calabozo.
- **Transferencias (`%pay`):** Envía almas a cualquier vecino del servidor.
- **Leaderboard Dinámico (`%rank`):** Ranking del Top 10 más rico con medallas, etiqueta de inactividad y seguimiento personal de posición.
- **👑 Rol Dinámico "El Más Millonario":** Se otorga automáticamente al líder de la economía (#1) y se le retira en tiempo real si es superado.

### 🎲 Apuestas y Minijuegos (Timba)
- **Cara o Cruz (`%coin`):** Apuestas rápidas de doble o nada.
- **Ruleta Callejera (`%ruleta`):** Apuesta a rojo, negro o al verde pleno (pago x14).
- **Sistema de Duelos y Apuestas de Espectadores (`%duelo` / `%bet`):**
  - Desafía a otro miembro a un combate 1v1.
  - El servidor dispone de una ventana de tiempo para apostar por su combatiente preferido.
  - Pozo compartido y recompensas garantizadas incluso sin contra-apostantes.

### ⚡ Eventos Aleatorios Periódicos (Ivy's Street Events)
El bot ejecuta un ciclo en segundo plano con intervalo dinámico e impredecible que activa eventos interactivos exclusivos en el canal de economía:
1. **Drop de Almas:** Botón interactivo para el vecino con los mejores reflejos.
2. **Trivia de Ivy:** Preguntas y acertijos de Deadlock y Spanish Harlem.
3. **Raid / Emboscada Cooperativa:** Un enemigo con barra de vida que requiere el ataque coordinado de múltiples usuarios distintos para repartir el botín.
4. **Desafío de Ruleta Rusa:** 70% de ganar un premio gordo o 30% de ir directo a prisión.
5. **Lluvia de Almas:** Multiplicador temporal de ganancias para el comando `%work`.
6. **Robin Hood (Impuesto a la Gárgola Millonaria):** Si el líder más rico acumula almas sin arriesgarlas en la calle, la probabilidad del evento escala progresivamente (24h -> 15%, 48h -> 30%, 72h -> 50%). Cuenta con protección anti-abuso (*Skin in the Game*): requiere apostar al menos el 2% de su patrimonio total (con piso mínimo de 500 almas) para reiniciar su reloj de inactividad.

---

## 🏛️ Arquitectura Modular del Código

El módulo de economía está estructurado como un paquete modular en Python bajo patrones de alta cohesión, separación de responsabilidades y herencia cooperativa mediante **Mixins**:

```text
Discord Economy Bot/
├── la_creatura_bot.py       # Entrada principal, ciclo de vida del bot y comandos utilitarios
├── console.py               # Consola interactiva CLI en segundo plano (daemon thread)
├── stats.json               # Persistencia local de balances y estadísticas (ignorado en git)
├── requirements.txt         # Dependencias del proyecto
└── economy/                 # Paquete modular de economía
    ├── __init__.py          # Exporta la clase Economy y setup(bot) para load_extension
    ├── config.py            # Cero números mágicos: constantes de balance y parseo de .env
    ├── lore.py              # Banco inmersivo de diálogos, citas de Ivy y preguntas de trivia
    ├── database.py          # DataManager con escrituras atómicas (.tmp -> os.replace) y asyncio.Lock
    ├── views.py             # Interfaces interactivas (discord.ui.View) desacopladas
    ├── duels.py             # EconomyDuelsMixin: combate 1v1, apuestas externas y liquidación
    ├── events.py            # EconomyEventsMixin: loop periódico @tasks.loop y eventos aleatorios
    └── cog.py               # Cog principal Economy (hereda mixins y expone comandos base)
```

---

## 🚀 Requisitos Previos

- Python 3.10 o superior (compatible con Python 3.11, 3.12, 3.13 y 3.14).
- Una aplicación y bot creados en el [Discord Developer Portal](https://discord.com/developers/applications).
- **Privileged Gateway Intents habilitados:**
  - En la pestaña **Bot** del Developer Portal, activa:
    - ✅ **Message Content Intent** (Obligatorio para leer comandos con prefijo).

---

## 🛠️ Instalación y Configuración

1. **Clona el repositorio:**
   ```bash
   git clone https://github.com/tu-usuario/Discord-Economy-Bot.git
   cd Discord-Economy-Bot
   ```

2. **Crea y activa un entorno virtual (recomendado):**
   ```bash
   # Windows
   python -m venv venv
   .\venv\Scripts\activate

   # Linux / macOS
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Instala las dependencias requeridas:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configura tus variables de entorno:**
   Copia el archivo de ejemplo `.env.example` y renómbralo a `.env`:
   ```bash
   cp .env.example .env   # En Linux/macOS
   copy .env.example .env # En Windows (PowerShell / CMD)
   ```

5. **Edita el archivo `.env` con tus configuraciones:**
   ```env
   # Token de tu bot (OBLIGATORIO)
   DISCORD_TOKEN=tu_token_aqui

   # Prefijo de comandos (por defecto: %)
   BOT_PREFIX=%

   # Tu ID de Discord (para comandos exclusivos de dueño)
   OWNER_DISCORD_ID=123456789012345678

   # ID del canal exclusivo para eventos aleatorios
   ECONOMY_CHANNEL_ID=123456789012345678

   # ID del rol a otorgar al Más Millonario
   RICHEST_ROLE_ID=123456789012345678
   RICHEST_ROLE_NAME=El Más Millonario

   # ID del canal para el boletín diario y hora de publicación (HH:MM)
   RICHEST_ANNOUNCE_CHANNEL_ID=123456789012345678
   RICHEST_DAILY_ANNOUNCE_TIME=20:00
   ```

---

## ▶️ Ejecución

Inicia el bot ejecutando el script principal:
```bash
python la_creatura_bot.py
```
*(En Windows también puedes utilizar el acceso directo `rundiscord.bat`).*

---

## 📖 Lista de Comandos

| Comando | Alias | Descripción |
| :--- | :--- | :--- |
| `%balance` | `%bal`, `%saldo`, `%dinero` | Consulta tus almas en mano y en la cornisa (banco). |
| `%work` | `%trabajar`, `%chamba`, `%laburar` | Trabaja en el barrio para recolectar almas. |
| `%dep <cantidad\|all>` | `%depositar`, `%guardar` | Guarda almas en el banco a salvo de robos. |
| `%with <cantidad\|all>` | `%retirar`, `%sacar` | Retira almas del banco hacia tu mano. |
| `%pay <@usuario> <cantidad>` | `%pagar`, `%transferir` | Transfiere almas a otro miembro del servidor. |
| `%rob <@usuario>` | `%robar`, `%afanar` | Intenta robarle almas en mano a un vecino. |
| `%rank` | `%lb`, `%top`, `%ricos` | Muestra la tabla de líderes de la economía. |
| `%coin <cara\|cruz> <apuesta>` | `%moneda`, `%flip` | Apuesta al lanzamiento de una moneda. |
| `%ruleta <color> <apuesta>` | `%roulette` | Apuesta en la ruleta callejera (rojo, negro o verde). |
| `%duelo <@usuario> <apuesta>` | `%duel` | Desafía a un usuario a un duelo a muerte por almas. |
| `%bet <@combatiente> <monto>` | `%apostar` | Apuesta en un duelo activo durante el tiempo de apuestas. |
| `%deadlock` | - | Lanza la señal de Deadlock con GIFs aleatorios. |
| `%gif <búsqueda>` | - | Busca y envía un GIF animado mediante la API de Giphy. |

---

## 💻 Consola Interactiva en Terminal (CLI)

El bot incluye una consola interactiva en tiempo real que se ejecuta en segundo plano sin congelar ni interferir con la conexión de Discord. Puedes escribir comandos directamente en la terminal mientras el bot está en línea:

| Comando CLI | Descripción |
| :--- | :--- |
| `hablar <canal_id\|nombre> <mensaje>` | Envía un mensaje como Ivy directamente al canal especificado. |
| `add <user_id> <monto> [w\|b]` | Suma o resta almas (valores negativos) a la billetera o banco. |
| `set <user_id> <wallet> [bank]` | Establece el saldo exacto de un usuario. |
| `bal <user_id>` | Muestra en terminal el balance y estado penal de un miembro. |
| `unjail <user_id>` / `jail <user_id> [min]` | Libera o encarcela a un usuario inmediatamente. |
| `event <drop\|trivia\|raid\|ruleta...>` | Dispara un evento en el canal oficial de economía. |
| `servers` | Lista los servidores donde está conectado el bot. |
| `channels [guild_id]` | Muestra los canales de texto disponibles y sus IDs. |
| `help` | Despliega la ayuda de comandos de consola. |
| `exit` / `quit` | Apaga el bot de forma limpia y ordenada. |

---

## 🔒 Seguridad y Privacidad

- **Protección de Credenciales:** El archivo `.gitignore` viene configurado para nunca subir `.env`, bases de datos locales (`stats.json`) ni archivos temporales.
- **Cero Hardcoding:** Ningún ID de canal, usuario o rol está incrustado rígidamente en el código.
- **Persistencia Concurrente:** `stats.json` utiliza cierres asíncronos (`asyncio.Lock`) y escritura temporal atómica para evitar corrupción de datos por condiciones de carrera.

---

## 📄 Licencia

Este proyecto se distribuye bajo la licencia MIT. Consulta el archivo [LICENSE](LICENSE) para más detalles.
