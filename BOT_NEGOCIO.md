# Chatbot conversacional de negocio

El bot usa la API de Groq para mantener una conversación en lenguaje natural.
El historial se conserva localmente por chat y se envía mediante Chat Completions,
sin depender de `previous_response_id`.
Cuando una pregunta requiere cifras, la IA genera una consulta SQL de solo
lectura sobre `data/stock-y-ventas/Ventas_3.db`. El resultado vuelve a la IA,
que lo interpreta y responde por Telegram.

Cada chat de Telegram conserva su propio contexto. El comando `/nuevo` permite
comenzar otra conversación.

## Requisitos

- Token de Telegram creado con `@BotFather`.
- Clave de la API de Groq creada en https://console.groq.com/keys
- Un modelo habilitado en el proyecto de Groq.

## Instalar dependencias

```powershell
cd C:\Users\usuario\Documents\Codex\chatbot\python-telegram-bot
.\.venv\Scripts\python.exe -m pip install -r .\requirements-business-bot.txt
```

## Iniciar en PowerShell

```powershell
cd C:\Users\usuario\Documents\Codex\chatbot\python-telegram-bot
$env:TELEGRAM_BOT_TOKEN = Read-Host "Token nuevo de BotFather"
$env:GROQ_API_KEY = Read-Host "Clave de la API de Groq"
.\.venv\Scripts\python.exe .\bot_prueba.py
```

Las claves permanecen solo en esa ventana de PowerShell y no se escriben en el
código. Para detener el bot, presiona `Ctrl+C`.

## Gráficas

La IA puede crear y enviar imágenes PNG directamente por Telegram. Admite:

- Barras horizontales para comparar productos o categorías.
- Líneas para tendencias por fecha.
- Gráficas circulares para participaciones con 12 categorías o menos.

Ejemplos:

```text
Genera una gráfica de participación de ingresos para todos los productos.
Muéstrame la evolución mensual de las ventas durante 2024.
Grafica los diez productos con más unidades vendidas.
Compara en una gráfica los ingresos de 2023 y 2024.
```

De manera predeterminada se usa `llama-3.3-70b-versatile`. Se puede elegir otro modelo
antes de iniciar:

```powershell
$env:GROQ_MODEL = "llama-3.3-70b-versatile"
```

## Ejemplo de conversación

```text
Usuario: ¿Cómo evolucionaron los ingresos durante 2024?
Bot: [consulta el dataset y explica la tendencia]

Usuario: ¿Qué productos explican principalmente ese resultado?
Bot: [recuerda que se refiere a 2024 y compara los productos]

Usuario: ¿Alguno de ellos tiene un nivel de stock preocupante?
Bot: [relaciona los productos anteriores con el último stock disponible]
```

## Seguridad y límites

- SQLite se abre en modo de solo lectura.
- Únicamente se aceptan consultas `SELECT` o `WITH`.
- Se bloquean instrucciones que puedan modificar la base.
- Cada consulta devuelve como máximo 200 filas y se interrumpe después de cinco segundos.
- El dataset cubre del 1 de enero de 2015 al 31 de diciembre de 2024.
- El dataset no identifica la moneda de sus precios.
