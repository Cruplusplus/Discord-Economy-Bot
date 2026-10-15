"""
Banco de dialogos, frases tematicas y preguntas de trivia de Ivy (Deadlock).
Mantiene viva la personalidad callejera y leal de la gargola de Spanish Harlem.
"""

from typing import List, Dict, Any

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
