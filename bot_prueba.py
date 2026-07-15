#!/usr/bin/env python
"""Bot conversacional de Telegram conectado al dataset de ventas."""

import logging
import os
import re

from openai import APIConnectionError, APIStatusError, RateLimitError
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from ai_business_assistant import AIBusinessAssistant


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

assistant: AIBusinessAssistant
TELEGRAM_MESSAGE_LIMIT = 4000


def is_allowed(update: Update) -> bool:
    """Restringe el bot cuando ALLOWED_TELEGRAM_USER_IDS está configurado."""
    configured = os.environ.get("ALLOWED_TELEGRAM_USER_IDS", "").strip()
    if not configured:
        return True
    allowed = {item.strip() for item in configured.split(",") if item.strip()}
    return str(update.effective_user.id) in allowed


async def reject_unauthorized(update: Update) -> bool:
    if is_allowed(update):
        return False
    logger.warning("Acceso rechazado para telegram_user_id=%s", update.effective_user.id)
    await update.message.reply_text("Este bot es privado y tu usuario no está autorizado.")
    return True

HELP_TEXT = """Soy un analista de negocio con IA conectado al dataset de ventas.

Puedes conversar libremente conmigo, por ejemplo:
• ¿Cómo evolucionaron las ventas durante 2024?
• Compara los tres productos con mayores ingresos.
• ¿Cuál de ellos tiene menos stock actualmente?
• ¿Qué recomendaciones darías basándote en esos resultados?
• Genera una gráfica de participación de ingresos por producto.

/nuevo borra el contexto de la conversación.
/id muestra tu identificador para configurar el acceso privado.
/ayuda muestra este mensaje."""


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_unauthorized(update):
        return
    await update.message.reply_text(HELP_TEXT)


async def new_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_unauthorized(update):
        return
    assistant.reset(update.effective_chat.id)
    await update.message.reply_text("He iniciado una conversación nueva.")


async def user_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(f"Tu Telegram user ID es: {update.effective_user.id}")


async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_unauthorized(update):
        return
    await update.effective_chat.send_action(ChatAction.TYPING)
    try:
        response = await assistant.answer(update.effective_chat.id, update.message.text)
        for chart in response.charts:
            try:
                with chart.open("rb") as image:
                    await update.message.reply_photo(photo=image)
            finally:
                chart.unlink(missing_ok=True)
        for start in range(0, len(response.text), TELEGRAM_MESSAGE_LIMIT):
            await update.message.reply_text(
                response.text[start : start + TELEGRAM_MESSAGE_LIMIT]
            )
    except RateLimitError:
        await update.message.reply_text(
            "La API de IA alcanzó temporalmente su límite de uso. Intenta de nuevo más tarde."
        )
    except APIConnectionError:
        await update.message.reply_text("No pude conectarme con la API de IA.")
    except APIStatusError as exc:
        logger.exception("Error de la API de Groq")
        await update.message.reply_text(f"La API de IA devolvió un error ({exc.status_code}).")
    except Exception:
        logger.exception("Error procesando el mensaje")
        await update.message.reply_text("Ocurrió un error al analizar el dataset.")


def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Define TELEGRAM_BOT_TOKEN antes de iniciar el bot.")

    global assistant
    assistant = AIBusinessAssistant()

    application = Application.builder().token(token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", start))
    application.add_handler(CommandHandler("ayuda", start))
    application.add_handler(CommandHandler("nuevo", new_conversation))
    application.add_handler(CommandHandler("id", user_id))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    render_url = os.environ.get("RENDER_EXTERNAL_URL")
    if render_url:
        port = int(os.environ.get("PORT", "10000"))
        raw_secret = os.environ.get("WEBHOOK_SECRET", token)
        webhook_secret = re.sub(r"[^A-Za-z0-9_-]", "_", raw_secret)[:256]
        webhook_path = "telegram-webhook"
        logger.info("Iniciando webhook en %s/%s", render_url, webhook_path)
        application.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path=webhook_path,
            webhook_url=f"{render_url.rstrip('/')}/{webhook_path}",
            secret_token=webhook_secret,
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=False,
        )
    else:
        logger.info("Iniciando polling local")
        application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
