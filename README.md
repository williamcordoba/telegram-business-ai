# Asistente de negocio con IA para Telegram

Chatbot conversacional en español que responde preguntas de negocio utilizando un
dataset de ventas e inventario. El bot funciona en Telegram, utiliza modelos de IA
servidos por Groq y consulta una base SQLite de solo lectura para respaldar sus
respuestas con datos reales.

## Funcionalidades

- Conversación libre en español.
- Memoria contextual independiente para cada chat.
- Análisis de ingresos, unidades, facturas, clientes, productos y stock.
- Consultas SQL generadas por la IA y ejecutadas con restricciones de seguridad.
- Gráficas de barras, líneas y participación porcentual enviadas por Telegram.
- Acceso privado mediante una lista de usuarios autorizados.
- Ejecución local con polling.
- Despliegue en Render mediante webhook HTTPS.
- Contenedor Docker ejecutado con un usuario sin privilegios.

## Ejemplos de preguntas

```text
¿Cuál fue el año con mayores ingresos?
¿Qué productos explican principalmente ese resultado?
Compara esos productos con el año anterior.
¿Alguno tiene un nivel de stock preocupante?
Genera una gráfica de participación de ingresos por producto.
¿Qué decisiones comerciales recomendarías?
```

## Arquitectura

```text
Usuario de Telegram
        │
        ▼
Bot python-telegram-bot
        │
        ▼
Modelo de IA en Groq
        │ solicita una herramienta
        ▼
Consultas SQLite de solo lectura ──► Ventas_3.db
        │
        ├── Resultado tabular ──► Respuesta en español
        └── Matplotlib ─────────► Gráfica PNG en Telegram
```

## Dataset

El proyecto utiliza el dataset
[Stock y ventas (para practicar)](https://www.kaggle.com/datasets/acm-ud/stock-y-ventas-para-prcticar).

La base utilizada por la aplicación es:

```text
data/stock-y-ventas/Ventas_3.db
```

Contiene datos desde el 1 de enero de 2015 hasta el 31 de diciembre de 2024:

- `FACTURA`: facturas y compradores anonimizados.
- `FACT_PROD`: productos y cantidades de cada factura.
- `PRECIO`: precio mensual por producto.
- `PRODUCTOS`: catálogo y descripción de productos.
- `STOCK`: evolución del inventario.

El dataset no especifica la moneda de los precios. Por esa razón, el bot presenta
los importes como valores monetarios sin atribuirles una divisa.

## Requisitos

- Python 3.10 o superior.
- Token de un bot creado con `@BotFather`.
- API key de [Groq](https://console.groq.com/keys).

## Instalación local

Desde PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m pip install -r .\requirements-business-bot.txt
```

Configura las credenciales en la terminal actual:

```powershell
$env:TELEGRAM_BOT_TOKEN = Read-Host "Token de Telegram"
$env:GROQ_API_KEY = Read-Host "API key de Groq"
```

No escribas las credenciales directamente en el código ni las publiques en GitHub.

Inicia el bot:

```powershell
.\.venv\Scripts\python.exe .\bot_prueba.py
```

Para detenerlo, presiona `Ctrl+C`.

## Comandos de Telegram

- `/start`: muestra la presentación y ejemplos.
- `/ayuda`: muestra la ayuda.
- `/nuevo`: elimina el contexto en memoria e inicia otra conversación.
- `/id`: muestra el identificador del usuario para configurar acceso privado.

## Variables de entorno

| Variable | Obligatoria | Descripción |
|---|---:|---|
| `TELEGRAM_BOT_TOKEN` | Sí | Token creado con BotFather. |
| `GROQ_API_KEY` | Sí | API key del proyecto Groq. |
| `GROQ_MODEL` | No | Modelo; por defecto `llama-3.3-70b-versatile`. |
| `ALLOWED_TELEGRAM_USER_IDS` | No | IDs autorizados separados por comas. |
| `WEBHOOK_SECRET` | En Render | Secreto para validar solicitudes del webhook. |

## Seguridad de las consultas

- La base se abre con `mode=ro` y `PRAGMA query_only`.
- Solo se admiten consultas que comienzan con `SELECT` o `WITH`.
- Se bloquean operaciones de escritura y administración.
- Cada consulta se limita a 200 filas y cinco segundos.
- Las gráficas admiten un máximo de 30 categorías.
- Los archivos PNG temporales se eliminan después de enviarlos.

## Despliegue gratuito en Render

El repositorio incluye:

- `Dockerfile` validado localmente.
- `render.yaml` para crear el Web Service.
- Webhook automático usando `RENDER_EXTERNAL_URL` y `PORT`.

Consulta la guía detallada:

**[Despliegue paso a paso en Render](PRODUCCION_RENDER.md)**

El plan Free de Render suspende el servicio después de un periodo sin tráfico. El
primer mensaje posterior puede tardar mientras el contenedor vuelve a iniciar. El
historial conversacional se almacena en memoria y se pierde durante reinicios.

## Documentación adicional

- [Uso del chatbot de negocio](BOT_NEGOCIO.md)
- [Producción en Render](PRODUCCION_RENDER.md)
- [Variables de entorno de ejemplo](.env.example)

## Créditos y licencias

Este repositorio se basa en la biblioteca de código abierto
[python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot).
Los archivos originales de esa biblioteca conservan sus licencias y avisos.

El dataset pertenece a su autor y está sujeto a las condiciones publicadas en Kaggle.
Verifica dichas condiciones antes de utilizarlo con fines comerciales.
