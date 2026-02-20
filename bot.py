"""
Bot de Telegram para agendamento — Studio Dandara Britto 💅🌸
Desenvolvido com python-telegram-bot e Supabase
"""

import os
import re
import logging
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
from supabase import create_client, Client

# ─── Configuração de logs ──────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ─── Carrega variáveis de ambiente ────────────────────────────────────
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
SUPABASE_URL   = os.getenv("SUPABASE_URL")
SUPABASE_KEY   = os.getenv("SUPABASE_KEY")

# ─── Cliente Supabase ─────────────────────────────────────────────────
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ─── Estados da conversa (ConversationHandler) ────────────────────────
MENU, NOME, SERVICO, DATA, HORARIO = range(5)

# ─── Serviços disponíveis ─────────────────────────────────────────────
SERVICOS = ["Manicure", "Pedicure", "Alongamento", "Blindagem", "Nail Art"]

# ─── Horários disponíveis ─────────────────────────────────────────────
HORARIOS = ["09:00", "10:00", "11:00", "13:00", "14:00", "15:00", "16:00", "17:00"]


# ══════════════════════════════════════════════════════════════════════
#  FUNÇÕES AUXILIARES
# ══════════════════════════════════════════════════════════════════════

def validar_data(data_str: str) -> bool:
    """Valida se a data está no formato DD/MM/AAAA e não é uma data passada."""
    try:
        data = datetime.strptime(data_str, "%d/%m/%Y")
        return data.date() >= datetime.now().date()
    except ValueError:
        return False


def validar_horario(horario_str: str) -> bool:
    """Valida se o horário está na lista de horários disponíveis."""
    return horario_str in HORARIOS


async def salvar_agendamento(nome: str, servico: str, data: str, horario: str) -> bool:
    """Salva o agendamento no Supabase. Retorna True se sucesso."""
    try:
        resultado = supabase.table("agendamentos").insert({
            "nome":    nome,
            "servico": servico,
            "data":    data,
            "horario": horario,
        }).execute()
        logger.info(f"Agendamento salvo: {resultado.data}")
        return True
    except Exception as e:
        logger.error(f"Erro ao salvar no Supabase: {e}")
        return False


# ══════════════════════════════════════════════════════════════════════
#  HANDLERS
# ══════════════════════════════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Exibe o menu principal ao usuário."""
    keyboard = [
        [InlineKeyboardButton("📅 Agendar horário", callback_data="agendar")],
        [InlineKeyboardButton("🕐 Ver horários disponíveis", callback_data="horarios")],
    ]
    markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "🌸 Olá! Bem-vinda ao *Studio Dandara Britto*! 💅\n\n"
        "Fico feliz em te receber por aqui. ✨\n"
        "Como posso te ajudar hoje?",
        reply_markup=markup,
        parse_mode="Markdown",
    )
    return MENU


async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processa a escolha do menu principal."""
    query = update.callback_query
    await query.answer()

    if query.data == "horarios":
        horarios_texto = "\n".join(f"🕐 {h}" for h in HORARIOS)
        await query.edit_message_text(
            f"⏰ *Horários disponíveis no Studio Dandara Britto:*\n\n{horarios_texto}\n\n"
            "Para agendar, use /start e escolha *Agendar horário*. 🌸",
            parse_mode="Markdown",
        )
        return ConversationHandler.END

    # Fluxo de agendamento
    await query.edit_message_text(
        "Ótimo! Vamos fazer seu agendamento no *Studio Dandara Britto*. 📋🌸\n\n"
        "Por favor, me diga seu *nome completo*:",
        parse_mode="Markdown",
    )
    return NOME


async def receber_nome(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Coleta o nome e pergunta o serviço."""
    nome = update.message.text.strip()

    if len(nome) < 2:
        await update.message.reply_text("❌ Nome muito curto. Por favor, informe seu nome completo:")
        return NOME

    context.user_data["nome"] = nome

    # Teclado com os serviços disponíveis
    keyboard = [[s] for s in SERVICOS]
    markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

    await update.message.reply_text(
        f"Prazer, *{nome}*! 😊\n\nQual serviço você deseja?",
        reply_markup=markup,
        parse_mode="Markdown",
    )
    return SERVICO


async def receber_servico(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Coleta o serviço e pergunta a data."""
    servico = update.message.text.strip()

    if servico not in SERVICOS:
        keyboard = [[s] for s in SERVICOS]
        markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text(
            "❌ Serviço inválido. Por favor, escolha uma das opções:",
            reply_markup=markup,
        )
        return SERVICO

    context.user_data["servico"] = servico

    await update.message.reply_text(
        f"*{servico}* selecionado! ✅\n\n"
        "Agora, me informe a *data* desejada no formato *DD/MM/AAAA*:",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown",
    )
    return DATA


async def receber_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Coleta a data e pergunta o horário."""
    data_str = update.message.text.strip()

    if not validar_data(data_str):
        await update.message.reply_text(
            "❌ Data inválida ou passada.\n"
            "Informe uma data futura no formato *DD/MM/AAAA* (ex: 25/12/2025):",
            parse_mode="Markdown",
        )
        return DATA

    context.user_data["data"] = data_str

    # Teclado com horários
    keyboard = [HORARIOS[i:i+2] for i in range(0, len(HORARIOS), 2)]
    markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

    await update.message.reply_text(
        f"📅 Data: *{data_str}*\n\nEscolha o *horário* desejado:",
        reply_markup=markup,
        parse_mode="Markdown",
    )
    return HORARIO


async def receber_horario(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Coleta o horário, salva no Supabase e finaliza."""
    horario = update.message.text.strip()

    if not validar_horario(horario):
        keyboard = [HORARIOS[i:i+2] for i in range(0, len(HORARIOS), 2)]
        markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text(
            "❌ Horário inválido. Escolha um dos horários disponíveis:",
            reply_markup=markup,
        )
        return HORARIO

    context.user_data["horario"] = horario

    # Recupera dados coletados
    nome    = context.user_data["nome"]
    servico = context.user_data["servico"]
    data    = context.user_data["data"]

    # Salva no Supabase
    await update.message.reply_text("⏳ Salvando seu agendamento...", reply_markup=ReplyKeyboardRemove())

    sucesso = await salvar_agendamento(nome, servico, data, horario)

    if sucesso:
        await update.message.reply_text(
            "✅ *Agendamento confirmado!*\n\n"
            f"👤 *Nome:* {nome}\n"
            f"💅 *Serviço:* {servico}\n"
            f"📅 *Data:* {data}\n"
            f"🕐 *Horário:* {horario}\n\n"
            "🌸 Te esperamos no *Studio Dandara Britto*!\n"
            "Qualquer dúvida, é só chamar. Até lá! 💖",
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(
            "❌ Ops! Ocorreu um erro ao salvar seu agendamento.\n"
            "Por favor, tente novamente com /start ou entre em contato conosco.",
        )

    # Limpa dados do usuário
    context.user_data.clear()
    return ConversationHandler.END


async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancela o agendamento em qualquer etapa."""
    context.user_data.clear()
    await update.message.reply_text(
        "❌ Agendamento cancelado. Use /start para recomeçar.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


async def erro_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Loga erros inesperados."""
    logger.error("Erro inesperado:", exc_info=context.error)


# ══════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════

def main() -> None:
    """Inicia o bot."""
    if not TELEGRAM_TOKEN:
        raise ValueError("TELEGRAM_TOKEN não encontrado no .env")
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("SUPABASE_URL ou SUPABASE_KEY não encontrados no .env")

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # ConversationHandler gerencia o fluxo de agendamento
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            MENU:    [CallbackQueryHandler(menu_callback)],
            NOME:    [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_nome)],
            SERVICO: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_servico)],
            DATA:    [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_data)],
            HORARIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_horario)],
        },
        fallbacks=[CommandHandler("cancelar", cancelar)],
        allow_reentry=True,
    )

    app.add_handler(conv_handler)
    app.add_error_handler(erro_handler)

    logger.info("Bot iniciado! Pressione Ctrl+C para parar.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
