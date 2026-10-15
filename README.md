# 🗽 Ivy Discord Economy Bot

Bot de Discord temático inspirado en **Ivy de Deadlock**, diseñado para gestionar un sistema integral de **economía, apuestas, duelos y eventos aleatorios periódicos** en tu servidor con persistencia atómica en JSON, cero números mágicos y total personalización mediante variables de entorno.

---

## ✨ Características Principales

### 🪙 Sistema de Economía Completo
- **Billetera y Banco (Cornisa):** Gestión segura de almas en mano y resguardadas.
- **Trabajo Callejero (`%work`):** Genera almas periódicamente con recompensas aleatorias.
- **Robo con Riesgo (`%rob`):** Sistema de dados (d20). Si fallas, la policía te cobra fianza o te envía al calabozo.
- **Transferencias (`%pay`):** Envía almas a cualquier vecino del servidor.
- **Leaderboard Dinámico (`%rank`):** Ranking del Top 10 más rico con medallas y seguimiento personal de posición.
- **👑 Rol Dinámico "El Más Millonario":** Se otorga automáticamente al líder de la economía (#1) y se le retira en tiempo real si es superado.

### 🎲 Apuestas y Minijuegos (Timba)
- **Cara o Cruz (`%coin`):** Apuestas rápidas de doble o nada.
- **Ruleta Callejera (`%ruleta`):** Apuesta a rojo, negro o al verde pleno (pago x14).
- **Sistema de Duelos y Apuestas de Espectadores (`%duelo` / `%apostar`):**
  - Desafía a otro miembro a un combate 1v1.
  - El servidor dispone de una ventana de tiempo para apostar por su combatiente preferido.
  - Pozo compartido y recompensas garantizadas incluso sin contra-apostantes.

### ⚡ Eventos Aleatorios Periódicos (Ivy's Street Events)
El bot ejecuta un ciclo en segundo plano con probabilidad configurable que activa eventos interactivos exclusivos en el canal de economía:
1. **Drop de Almas:** Botón interactivo para el vecino con los mejores reflejos.
2. **Trivia de Ivy:** Preguntas y acertijos de Deadlock y Spanish Harlem.
3. **Raid / Emboscada Cooperativa:** Un enemigo con barra de vida que requiere el ataque coordinado de múltiples usuarios distintos para repartir el botín.
4. **Desafío de Ruleta Rusa:** 70% de ganar un premio gordo o 30% de ir directo a prisión.
5. **Lluvia de Almas:** Multiplicador temporal de ganancias para el comando `%work`.
6. **Robin Hood (Impuesto a la Gárgola Millonaria):** Le cobra un porcentaje al líder más rico y suelta el botín en las calles para que lo recolecte cualquiera.

### 🎭 Personalidad y Lore
- Diálogos, embeds y respuestas ambientados con la voz leal, pícara y protectora de **Ivy de Deadlock**.
- Comandos interactivos adicionales: `%deadlock`, `%kiss`, `%gif` (Giphy API), `%hablar` (puente de mensajería para administradores), entre otros.

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
| `%apostar <@combatiente> <monto>` | `%bet` | Apuesta en un duelo activo durante el tiempo de apuestas. |
| `%deadlock` | - | Lanza la señal de Deadlock con GIFs aleatorios. |
| `%gif <búsqueda>` | - | Busca y envía un GIF animado mediante la API de Giphy. |

---

## 🔒 Seguridad y Privacidad

- **Protección de Credenciales:** El archivo `.gitignore` viene configurado para nunca subir `.env`, bases de datos locales (`stats.json`) ni archivos temporales.
- **Cero Hardcoding:** Ningún ID de canal, usuario o rol está incrustado rígidamente en el código.
- **Persistencia Concurrente:** `stats.json` utiliza cierres asíncronos (`asyncio.Lock`) y escritura temporal atómica para evitar corrupción de datos por condiciones de carrera.

---

## 📄 Licencia

Este proyecto se distribuye bajo la licencia MIT. Consulta el archivo [LICENSE](LICENSE) para más detalles.
