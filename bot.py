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

# ─── Configuração de logs ─────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ─── Variáveis de ambiente ────────────────────────────────────────────
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
SUPABASE_URL   = os.getenv("SUPABASE_URL")
SUPABASE_KEY   = os.getenv("SUPABASE_KEY")

# ─── Cliente Supabase ─────────────────────────────────────────────────
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ─── IDs especiais ────────────────────────────────────────────────────
ADMIN_ID = 7539142683   # 👑 Administradora — Studio Dandara Britto
TI_ID    = 8367937028   # 🛠 Desenvolvedor TI do bot

# ─── Estados da conversa ──────────────────────────────────────────────
(
    MENU, NOME, SERVICO, DATA, HORARIO,
    AGUARD_MSG_USUARIO,
    TI_AGUARD_ADD_SERVICO,
    TI_AGUARD_ADD_HORARIO,
    TI_AGUARD_DEL_AGENDAMENTO,
    TI_AGUARD_EDITAR_ID,
    TI_AGUARD_EDITAR_CAMPO,
    TI_AGUARD_EDITAR_VALOR,
) = range(12)

# ─── Listas dinâmicas (alteráveis pelo TI em tempo real) ─────────────
SERVICOS = ["Manicure", "Pedicure", "Alongamento", "Blindagem", "Nail Art"]
HORARIOS = ["09:00", "10:00", "11:00", "13:00", "14:00", "15:00", "16:00", "17:00"]


# ══════════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════════

def validar_data(data_str: str) -> bool:
    try:
        data = datetime.strptime(data_str, "%d/%m/%Y")
        return data.date() >= datetime.now().date()
    except ValueError:
        return False

def validar_horario(h: str) -> bool:
    return h in HORARIOS

async def safe_edit(query, text: str, markup=None, parse_mode: str = "Markdown") -> None:
    """Edita mensagem com segurança — ignora erro de conteúdo idêntico."""
    try:
        await query.edit_message_text(text, parse_mode=parse_mode, reply_markup=markup)
    except Exception as e:
        if "Message is not modified" in str(e):
            pass  # usuário clicou duas vezes — sem problema
        else:
            # fallback: envia nova mensagem
            try:
                await query.message.reply_text(text, parse_mode=parse_mode, reply_markup=markup)
            except Exception:
                logger.warning(f"safe_edit fallback também falhou: {e}")

def formatar_agendamento(ag: dict) -> str:
    status = ag.get("status", "pendente")
    emoji  = {"pendente": "⏳", "confirmado": "✅", "cancelado": "❌"}.get(status, "⏳")
    return (
        f"{emoji} *ID:* `{str(ag['id'])[:8]}...`\n"
        f"   👤 {ag['nome']} | 💅 {ag['servico']}\n"
        f"   📅 {ag['data']} às 🕐 {ag['horario']}\n"
        f"   Status: *{status.upper()}*\n"
    )

def menu_admin_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Agendamentos de hoje",   callback_data="adm_hoje")],
        [InlineKeyboardButton("📅 Todos os agendamentos",  callback_data="adm_todos")],
        [InlineKeyboardButton("✅ Confirmar agendamento",   callback_data="adm_confirmar")],
        [InlineKeyboardButton("❌ Cancelar agendamento",    callback_data="adm_cancelar_ag")],
        [InlineKeyboardButton("💬 Enviar msg a cliente",   callback_data="adm_msg")],
    ])

def menu_ti_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Ver todos agendamentos", callback_data="ti_todos")],
        [InlineKeyboardButton("🗑 Deletar agendamento",    callback_data="ti_deletar")],
        [InlineKeyboardButton("✏️ Editar agendamento",     callback_data="ti_editar")],
        [InlineKeyboardButton("➕ Adicionar serviço",      callback_data="ti_add_servico")],
        [InlineKeyboardButton("➖ Remover serviço",        callback_data="ti_del_servico")],
        [InlineKeyboardButton("⏰ Adicionar horário",      callback_data="ti_add_horario")],
        [InlineKeyboardButton("🕐 Remover horário",        callback_data="ti_del_horario")],
        [InlineKeyboardButton("📊 Estatísticas do banco",  callback_data="ti_stats")],
        [InlineKeyboardButton("🔄 Listar serviços/horários", callback_data="ti_listar")],
    ])


# ══════════════════════════════════════════════════════════════════════
#  FLUXO CLIENTE
# ══════════════════════════════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = [
        [InlineKeyboardButton("📅 Agendar horário",          callback_data="agendar")],
        [InlineKeyboardButton("🕐 Ver horários disponíveis", callback_data="horarios")],
    ]
    await update.message.reply_text(
        "🌸 *Querida e distinta visitante,*\n\n"
        "Seja muito bem-vinda ao *Studio Dandara Britto* — "
        "o salão mais refinado e encantador desta temporada. 👑\n\n"
        "A sociedade toda já sabe: quem cuida das unhas aqui, "
        "jamais passa despercebida nos salões da alta sociedade. 💅✨\n\n"
        "Como posso lhe ser útil hoje?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )
    return MENU


async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "horarios":
        texto = "\n".join(f"🕐 {h}" for h in HORARIOS)
        await query.edit_message_text(
            f"🕐 *Os horários disponíveis nesta temporada são:*\n\n{texto}\n\n"
            "_A agenda da Dandara é bastante disputada, querida. "
            "Não deixe para amanhã o que pode ser agendado hoje._ 🌸\n\n"
            "Use /start para realizar o seu agendamento.",
            parse_mode="Markdown",
        )
        return ConversationHandler.END

    await query.edit_message_text(
        "✨ *Esplêndido! Uma escolha verdadeiramente sábia.*\n\n"
        "Permita-me colher algumas informações para garantir "
        "um momento à altura de sua distinção. 📋\n\n"
        "Primeiramente, qual é o seu *nome completo*, minha cara?",
        parse_mode="Markdown",
    )
    return NOME


async def receber_nome(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    nome = update.message.text.strip()
    if len(nome) < 2:
        await update.message.reply_text(
            "🌸 Peço-lhe a gentileza de informar seu *nome completo*, minha cara.",
            parse_mode="Markdown",
        )
        return NOME

    context.user_data["nome"]        = nome
    context.user_data["telegram_id"] = update.effective_user.id

    markup = ReplyKeyboardMarkup([[s] for s in SERVICOS], one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(
        f"_Que nome encantador,_ *{nome}*! 👑\n\n"
        "Agora, diga-me — qual serviço a senhora deseja desfrutar "
        "em nossa mais refinada casa de beleza?",
        reply_markup=markup,
        parse_mode="Markdown",
    )
    return SERVICO


async def receber_servico(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    servico = update.message.text.strip()
    if servico not in SERVICOS:
        markup = ReplyKeyboardMarkup([[s] for s in SERVICOS], one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text(
            "🌸 Perdoe-me, mas não reconheço tal serviço em nosso cardápio. "
            "Permita-me apresentar nossas opções novamente:",
            reply_markup=markup,
        )
        return SERVICO

    context.user_data["servico"] = servico
    await update.message.reply_text(
        f"*{servico}* — uma escolha impecável! ✨\n\n"
        "_A senhora tem um gosto verdadeiramente refinado._\n\n"
        "Agora, informe-me a *data* de sua preferência no formato *DD/MM/AAAA*:",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown",
    )
    return DATA


async def receber_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    data_str = update.message.text.strip()
    if not validar_data(data_str):
        await update.message.reply_text(
            "🌸 Peço perdão, mas essa data não me parece válida — "
            "ou já pertence ao passado, e o passado, minha cara, não se agenda. 😊\n\n"
            "Por favor, informe uma data futura no formato *DD/MM/AAAA*:",
            parse_mode="Markdown",
        )
        return DATA

    context.user_data["data"] = data_str
    markup = ReplyKeyboardMarkup(
        [HORARIOS[i:i+2] for i in range(0, len(HORARIOS), 2)],
        one_time_keyboard=True, resize_keyboard=True,
    )
    await update.message.reply_text(
        f"📅 *{data_str}* — anotado com toda a elegância que merece. 🌸\n\n"
        "E em qual *horário* a senhora deseja ser recebida?",
        reply_markup=markup,
        parse_mode="Markdown",
    )
    return HORARIO


async def receber_horario(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    horario = update.message.text.strip()
    if not validar_horario(horario):
        markup = ReplyKeyboardMarkup(
            [HORARIOS[i:i+2] for i in range(0, len(HORARIOS), 2)],
            one_time_keyboard=True, resize_keyboard=True,
        )
        await update.message.reply_text(
            "🌸 Este horário não consta em nossa agenda, minha cara. "
            "Permita-me apresentar as opções disponíveis:",
            reply_markup=markup,
        )
        return HORARIO

    nome    = context.user_data["nome"]
    servico = context.user_data["servico"]
    data    = context.user_data["data"]
    tg_id   = context.user_data.get("telegram_id")

    await update.message.reply_text(
        "✨ Um momento, por favor. Estamos registrando sua visita nos livros da temporada...",
        reply_markup=ReplyKeyboardRemove(),
    )

    try:
        res = supabase.table("agendamentos").insert({
            "nome": nome, "servico": servico, "data": data,
            "horario": horario, "telegram_id": str(tg_id), "status": "pendente",
        }).execute()
        ag_id   = res.data[0]["id"] if res.data else "?"
        sucesso = True
    except Exception as e:
        logger.error(f"Erro Supabase: {e}")
        sucesso = False
        ag_id   = "?"

    if sucesso:
        await update.message.reply_text(
            "👑 *Que notícia esplêndida!*\n\n"
            "Seu agendamento foi registrado com toda a pompa e circunstância "
            "que a senhora merece. Os fofoqueiros da sociedade certamente "
            "já estão comentando sobre sua próxima visita! 🌸\n\n"
            f"👤 *Nome:* {nome}\n"
            f"💅 *Serviço:* {servico}\n"
            f"📅 *Data:* {data}\n"
            f"🕐 *Horário:* {horario}\n\n"
            "_Aguarde a confirmação da nossa equipe. Até breve, querida!_ 💖",
            parse_mode="Markdown",
        )
        # Notifica admin sobre novo agendamento
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    "🔔 *Novo agendamento recebido!*\n\n"
                    f"👤 *Nome:* {nome}\n"
                    f"💅 *Serviço:* {servico}\n"
                    f"📅 *Data:* {data}\n"
                    f"🕐 *Horário:* {horario}\n"
                    f"🆔 *ID:* `{ag_id}`\n\n"
                    "Use /admin para confirmar ou cancelar. 👑"
                ),
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.warning(f"Não foi possível notificar admin: {e}")
    else:
        await update.message.reply_text(
            "😔 *Minhas mais sinceras desculpas, minha cara.*\n\n"
            "Um imprevisto nos impediu de registrar seu agendamento.\n\n"
            "Por gentileza, tente novamente com /start. 🌸",
        )

    context.user_data.clear()
    return ConversationHandler.END


async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text(
        "🌸 *Como a senhora desejar.*\n\n"
        "_É uma pena, mas respeito sua decisão com toda a elegância que me cabe._\n\n"
        "Quando estiver pronta, basta usar /start. 👑",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown",
    )
    return ConversationHandler.END


# ══════════════════════════════════════════════════════════════════════
#  PAINEL ADMIN 👑 E TI 🛠
# ══════════════════════════════════════════════════════════════════════

async def painel_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id

    if user_id == ADMIN_ID:
        await update.message.reply_text(
            "👑 *Bem-vinda, Administradora!*\n\n"
            "_O que deseja gerenciar hoje no Studio Dandara Britto?_",
            reply_markup=menu_admin_kb(),
            parse_mode="Markdown",
        )
        return MENU

    elif user_id == TI_ID:
        await update.message.reply_text(
            "🛠 *Bem-vindo, TI!*\n\n"
            "_Painel técnico completo à sua disposição._",
            reply_markup=menu_ti_kb(),
            parse_mode="Markdown",
        )
        return MENU

    else:
        await update.message.reply_text(
            "🌸 *Minha cara, esta ala é restrita à alta sociedade.*\n\n"
            "_Apenas membros autorizados podem adentrar este recinto._ 👑",
            parse_mode="Markdown",
        )
        return ConversationHandler.END


# ── Callbacks unificados Admin + TI ───────────────────────────────────

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query   = update.callback_query
    user_id = query.from_user.id
    data    = query.data

    if user_id not in {ADMIN_ID, TI_ID}:
        await query.answer("Acesso negado.", show_alert=True)
        return ConversationHandler.END

    await query.answer()

    # ════════════ ADMIN ════════════

    if data == "adm_hoje":
        hoje = datetime.now().strftime("%d/%m/%Y")
        res  = supabase.table("agendamentos").select("*").eq("data", hoje).order("horario").execute()
        ags  = res.data
        if not ags:
            texto = f"📋 *Agendamentos de hoje ({hoje}):*\n\n_Nenhum agendamento para hoje._ 🌸"
        else:
            linhas = [f"📋 *Agendamentos de hoje ({hoje}):*\n"]
            for ag in ags:
                linhas.append(formatar_agendamento(ag))
            texto = "\n".join(linhas)
        await safe_edit(query, texto, menu_admin_kb())
        return MENU

    elif data == "adm_todos":
        res = supabase.table("agendamentos").select("*").order("data").order("horario").execute()
        ags = res.data
        if not ags:
            texto = "📅 *Todos os agendamentos:*\n\n_Nenhum agendamento encontrado._ 🌸"
        else:
            linhas = [f"📅 *Todos os agendamentos ({len(ags)} total):*\n"]
            for ag in ags:
                linhas.append(formatar_agendamento(ag))
            texto = "\n".join(linhas)
            if len(texto) > 4000:
                texto = texto[:4000] + "\n\n_...lista truncada._"
        await safe_edit(query, texto, menu_admin_kb())
        return MENU

    elif data == "adm_confirmar":
        res = supabase.table("agendamentos").select("*").eq("status", "pendente").order("data").execute()
        ags = res.data
        if not ags:
            await safe_edit(query, "✅ *Confirmar agendamento:*\n\n_Nenhum agendamento pendente._ 🌸", menu_admin_kb())
            return MENU
        botoes = [[InlineKeyboardButton(
            f"{ag['nome']} — {ag['data']} {ag['horario']}",
            callback_data=f"confirmar_{ag['id']}"
        )] for ag in ags]
        botoes.append([InlineKeyboardButton("🔙 Voltar", callback_data="adm_voltar")])
        await safe_edit(query, "✅ *Escolha o agendamento para confirmar:*", InlineKeyboardMarkup(botoes))
        return MENU

    elif data.startswith("confirmar_"):
        ag_id = data.replace("confirmar_", "")
        res   = supabase.table("agendamentos").update({"status": "confirmado"}).eq("id", ag_id).execute()
        ag    = res.data[0] if res.data else None
        if ag:
            await safe_edit(query,
                f"✅ *Agendamento de {ag['nome']} confirmado!*\n\n📅 {ag['data']} às 🕐 {ag['horario']}",
                menu_admin_kb())
            tg_id = ag.get("telegram_id")
            if tg_id:
                try:
                    await context.bot.send_message(
                        chat_id=int(tg_id),
                        text=(
                            "✅ *Seu agendamento foi confirmado!* 👑\n\n"
                            f"💅 *Serviço:* {ag['servico']}\n"
                            f"📅 *Data:* {ag['data']}\n"
                            f"🕐 *Horário:* {ag['horario']}\n\n"
                            "_Te esperamos com toda a elegância que merece. Até lá, querida!_ 🌸"
                        ),
                        parse_mode="Markdown",
                    )
                except Exception as e:
                    logger.warning(f"Erro ao notificar cliente: {e}")
        return MENU

    elif data == "adm_cancelar_ag":
        res = supabase.table("agendamentos").select("*").in_("status", ["pendente", "confirmado"]).order("data").execute()
        ags = res.data
        if not ags:
            await safe_edit(query, "❌ *Cancelar agendamento:*\n\n_Nenhum agendamento ativo._ 🌸", menu_admin_kb())
            return MENU
        botoes = [[InlineKeyboardButton(
            f"{ag['nome']} — {ag['data']} {ag['horario']}",
            callback_data=f"cancela_{ag['id']}"
        )] for ag in ags]
        botoes.append([InlineKeyboardButton("🔙 Voltar", callback_data="adm_voltar")])
        await safe_edit(query, "❌ *Escolha o agendamento para cancelar:*", InlineKeyboardMarkup(botoes))
        return MENU

    elif data.startswith("cancela_"):
        ag_id = data.replace("cancela_", "")
        res   = supabase.table("agendamentos").update({"status": "cancelado"}).eq("id", ag_id).execute()
        ag    = res.data[0] if res.data else None
        if ag:
            await safe_edit(query,
                f"❌ *Agendamento de {ag['nome']} cancelado.*\n\n📅 {ag['data']} às {ag['horario']}",
                menu_admin_kb())
            tg_id = ag.get("telegram_id")
            if tg_id:
                try:
                    await context.bot.send_message(
                        chat_id=int(tg_id),
                        text=(
                            "😔 *Infelizmente, seu agendamento foi cancelado.*\n\n"
                            f"📅 {ag['data']} às 🕐 {ag['horario']}\n\n"
                            "_Entre em contato para reagendar. Pedimos desculpas._ 🌸"
                        ),
                        parse_mode="Markdown",
                    )
                except Exception as e:
                    logger.warning(f"Erro ao notificar cliente: {e}")
        return MENU

    elif data == "adm_msg":
        res = supabase.table("agendamentos").select("*").not_.is_("telegram_id", "null")\
            .order("criado_em", desc=True).limit(30).execute()
        ags = res.data
        vistos, botoes = set(), []
        for ag in ags:
            tid = ag.get("telegram_id")
            if tid and tid not in vistos:
                vistos.add(tid)
                botoes.append([InlineKeyboardButton(
                    ag["nome"], callback_data=f"msg_{tid}_{ag['nome'][:15]}"
                )])
        botoes.append([InlineKeyboardButton("🔙 Voltar", callback_data="adm_voltar")])
        if len(botoes) == 1:
            await safe_edit(query, "💬 _Nenhum cliente com ID registrado ainda._ 🌸", menu_admin_kb())
            return MENU
        await safe_edit(query, "💬 *Para qual cliente deseja enviar uma mensagem?*", InlineKeyboardMarkup(botoes))
        return MENU

    elif data.startswith("msg_"):
        partes = data[4:].split("_", 1)
        tid    = partes[0]
        nome   = partes[1] if len(partes) > 1 else "Cliente"
        context.user_data["msg_destino_id"]   = tid
        context.user_data["msg_destino_nome"] = nome
        await safe_edit(query, f"💬 *Digite a mensagem para {nome}:*\n\n_Ou /cancelar para voltar._")
        return AGUARD_MSG_USUARIO

    elif data == "adm_voltar":
        await safe_edit(query, "👑 *Painel Admin — Studio Dandara Britto*\n\n_O que deseja gerenciar?_", menu_admin_kb())
        return MENU

    # ════════════ TI ════════════

    elif data == "ti_todos":
        res = supabase.table("agendamentos").select("*").order("criado_em", desc=True).execute()
        ags = res.data
        if not ags:
            texto = "📋 *Agendamentos:*\n\n_Nenhum agendamento encontrado._"
        else:
            linhas = [f"📋 *Todos os agendamentos ({len(ags)}):*\n"]
            for ag in ags:
                linhas.append(formatar_agendamento(ag))
            texto = "\n".join(linhas)
            if len(texto) > 4000:
                texto = texto[:4000] + "\n_...truncado._"
        await safe_edit(query, texto, menu_ti_kb())
        return MENU

    elif data == "ti_deletar":
        await safe_edit(query,
            "🗑 *Digite o ID (ou os primeiros caracteres) do agendamento a deletar:*\n\n"
            "_Use 'Ver todos' para ver os IDs. Envie /cancelar para voltar._")
        return TI_AGUARD_DEL_AGENDAMENTO

    elif data == "ti_editar":
        await safe_edit(query,
            "✏️ *Digite o ID (ou os primeiros caracteres) do agendamento a editar:*\n\n"
            "_Envie /cancelar para voltar._")
        return TI_AGUARD_EDITAR_ID

    elif data == "ti_add_servico":
        await safe_edit(query,
            f"➕ *Serviços atuais:*\n{', '.join(SERVICOS)}\n\n*Digite o nome do novo serviço:*")
        return TI_AGUARD_ADD_SERVICO

    elif data == "ti_del_servico":
        botoes = [[InlineKeyboardButton(s, callback_data=f"delserv_{s}")] for s in SERVICOS]
        botoes.append([InlineKeyboardButton("🔙 Voltar", callback_data="ti_voltar")])
        await safe_edit(query, "➖ *Qual serviço deseja remover?*", InlineKeyboardMarkup(botoes))
        return MENU

    elif data.startswith("delserv_"):
        servico = data.replace("delserv_", "")
        if servico in SERVICOS:
            SERVICOS.remove(servico)
        await safe_edit(query,
            f"✅ Serviço *{servico}* removido!\n\nServiços atuais: {', '.join(SERVICOS)}",
            menu_ti_kb())
        return MENU

    elif data == "ti_add_horario":
        await safe_edit(query,
            f"⏰ *Horários atuais:*\n{', '.join(HORARIOS)}\n\n*Digite o novo horário (HH:MM):*")
        return TI_AGUARD_ADD_HORARIO

    elif data == "ti_del_horario":
        botoes = [[InlineKeyboardButton(h, callback_data=f"delhor_{h}")] for h in HORARIOS]
        botoes.append([InlineKeyboardButton("🔙 Voltar", callback_data="ti_voltar")])
        await safe_edit(query, "🕐 *Qual horário deseja remover?*", InlineKeyboardMarkup(botoes))
        return MENU

    elif data.startswith("delhor_"):
        horario = data.replace("delhor_", "")
        if horario in HORARIOS:
            HORARIOS.remove(horario)
        await safe_edit(query,
            f"✅ Horário *{horario}* removido!\n\nHorários atuais: {', '.join(HORARIOS)}",
            menu_ti_kb())
        return MENU

    elif data == "ti_stats":
        try:
            hoje     = datetime.now().strftime("%d/%m/%Y")
            total    = supabase.table("agendamentos").select("*", count="exact").execute()
            pend     = supabase.table("agendamentos").select("*", count="exact").eq("status", "pendente").execute()
            conf     = supabase.table("agendamentos").select("*", count="exact").eq("status", "confirmado").execute()
            canc     = supabase.table("agendamentos").select("*", count="exact").eq("status", "cancelado").execute()
            hoje_res = supabase.table("agendamentos").select("*", count="exact").eq("data", hoje).execute()
            await safe_edit(query,
                "📊 *Estatísticas do banco de dados:*\n\n"
                f"📋 Total: *{total.count}*\n"
                f"⏳ Pendentes: *{pend.count}*\n"
                f"✅ Confirmados: *{conf.count}*\n"
                f"❌ Cancelados: *{canc.count}*\n"
                f"📅 Hoje: *{hoje_res.count}*\n\n"
                f"💅 Serviços cadastrados: *{len(SERVICOS)}*\n"
                f"⏰ Horários disponíveis: *{len(HORARIOS)}*",
                menu_ti_kb())
        except Exception as e:
            await safe_edit(query, f"❌ Erro nas estatísticas: {e}", menu_ti_kb())
        return MENU

    elif data == "ti_listar":
        await safe_edit(query,
            "💅 *Serviços disponíveis:*\n" + "\n".join(f"  • {s}" for s in SERVICOS) +
            "\n\n⏰ *Horários disponíveis:*\n" + "\n".join(f"  • {h}" for h in HORARIOS),
            menu_ti_kb())
        return MENU

    elif data == "ti_voltar":
        await safe_edit(query,
            "🛠 *Painel TI — Studio Dandara Britto*\n\n_O que deseja gerenciar?_",
            menu_ti_kb())
        return MENU

    elif data.startswith("edit_campo_"):
        campo_map = {
            "edit_campo_nome":    ("nome",    "novo nome"),
            "edit_campo_servico": ("servico", "novo serviço"),
            "edit_campo_data":    ("data",    "nova data (DD/MM/AAAA)"),
            "edit_campo_horario": ("horario", "novo horário (HH:MM)"),
        }
        if data in campo_map:
            campo, descricao = campo_map[data]
            context.user_data["editar_campo"] = campo
            await safe_edit(query, f"✏️ *Digite o {descricao}:*")
            return TI_AGUARD_EDITAR_VALOR
        return MENU

    return MENU


# ══════════════════════════════════════════════════════════════════════
#  HANDLERS DE TEXTO — ADMIN E TI
# ══════════════════════════════════════════════════════════════════════

async def receber_msg_usuario(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Admin envia mensagem personalizada para uma cliente."""
    texto = update.message.text.strip()
    tid   = context.user_data.get("msg_destino_id")
    nome  = context.user_data.get("msg_destino_nome", "Cliente")
    try:
        await context.bot.send_message(
            chat_id=int(tid),
            text=f"💬 *Mensagem do Studio Dandara Britto:*\n\n{texto}",
            parse_mode="Markdown",
        )
        await update.message.reply_text(
            f"✅ Mensagem enviada com sucesso para *{nome}*! 🌸",
            reply_markup=menu_admin_kb(), parse_mode="Markdown",
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Erro ao enviar: {e}", reply_markup=menu_admin_kb())
    context.user_data.clear()
    return MENU


async def ti_add_servico(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """TI adiciona novo serviço."""
    novo = update.message.text.strip().title()
    if novo in SERVICOS:
        await update.message.reply_text(f"⚠️ O serviço *{novo}* já existe!",
            parse_mode="Markdown", reply_markup=menu_ti_kb())
    else:
        SERVICOS.append(novo)
        await update.message.reply_text(
            f"✅ Serviço *{novo}* adicionado!\n\nServiços: {', '.join(SERVICOS)}",
            parse_mode="Markdown", reply_markup=menu_ti_kb(),
        )
    return MENU


async def ti_add_horario(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """TI adiciona novo horário."""
    novo = update.message.text.strip()
    if not re.match(r"^\d{2}:\d{2}$", novo):
        await update.message.reply_text(
            "❌ Formato inválido. Use *HH:MM* (ex: 08:30):", parse_mode="Markdown"
        )
        return TI_AGUARD_ADD_HORARIO
    if novo in HORARIOS:
        await update.message.reply_text(f"⚠️ O horário *{novo}* já existe!",
            parse_mode="Markdown", reply_markup=menu_ti_kb())
    else:
        HORARIOS.append(novo)
        HORARIOS.sort()
        await update.message.reply_text(
            f"✅ Horário *{novo}* adicionado!\n\nHorários: {', '.join(HORARIOS)}",
            parse_mode="Markdown", reply_markup=menu_ti_kb(),
        )
    return MENU


async def ti_deletar_agendamento(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """TI deleta agendamento pelo ID."""
    ag_id = update.message.text.strip()
    try:
        res = supabase.table("agendamentos").select("*").ilike("id", f"{ag_id}%").execute()
        if not res.data:
            await update.message.reply_text("❌ Agendamento não encontrado.", reply_markup=menu_ti_kb())
            return MENU
        ag = res.data[0]
        supabase.table("agendamentos").delete().eq("id", ag["id"]).execute()
        await update.message.reply_text(
            f"🗑 *Deletado!*\n\n👤 {ag['nome']} | 📅 {ag['data']} às {ag['horario']}",
            parse_mode="Markdown", reply_markup=menu_ti_kb(),
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Erro: {e}", reply_markup=menu_ti_kb())
    return MENU


async def ti_editar_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """TI informa ID do agendamento a editar."""
    ag_id = update.message.text.strip()
    try:
        res = supabase.table("agendamentos").select("*").ilike("id", f"{ag_id}%").execute()
        if not res.data:
            await update.message.reply_text("❌ Agendamento não encontrado.", reply_markup=menu_ti_kb())
            return MENU
        ag = res.data[0]
        context.user_data["editar_id"] = ag["id"]
        botoes = InlineKeyboardMarkup([
            [InlineKeyboardButton("👤 Nome",    callback_data="edit_campo_nome")],
            [InlineKeyboardButton("💅 Serviço", callback_data="edit_campo_servico")],
            [InlineKeyboardButton("📅 Data",    callback_data="edit_campo_data")],
            [InlineKeyboardButton("🕐 Horário", callback_data="edit_campo_horario")],
            [InlineKeyboardButton("🔙 Voltar",  callback_data="ti_voltar")],
        ])
        await update.message.reply_text(
            f"✏️ *Editando agendamento de {ag['nome']}*\n\n"
            f"💅 {ag['servico']} | 📅 {ag['data']} às {ag['horario']}\n\n"
            "*Qual campo deseja alterar?*",
            parse_mode="Markdown", reply_markup=botoes,
        )
        return TI_AGUARD_EDITAR_CAMPO
    except Exception as e:
        await update.message.reply_text(f"❌ Erro: {e}", reply_markup=menu_ti_kb())
        return MENU


async def ti_editar_valor(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """TI informa novo valor do campo."""
    novo_valor = update.message.text.strip()
    ag_id = context.user_data.get("editar_id")
    campo = context.user_data.get("editar_campo")
    try:
        supabase.table("agendamentos").update({campo: novo_valor}).eq("id", ag_id).execute()
        await update.message.reply_text(
            f"✅ Campo *{campo}* atualizado para *{novo_valor}*!",
            parse_mode="Markdown", reply_markup=menu_ti_kb(),
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Erro: {e}", reply_markup=menu_ti_kb())
    context.user_data.clear()
    return MENU


# ══════════════════════════════════════════════════════════════════════
#  ERRO
# ══════════════════════════════════════════════════════════════════════

async def erro_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Erro inesperado:", exc_info=context.error)


# ══════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════

def main() -> None:
    if not TELEGRAM_TOKEN:
        raise ValueError("TELEGRAM_TOKEN não encontrado no .env")
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("SUPABASE_URL ou SUPABASE_KEY não encontrados no .env")

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # ── Fluxo cliente ─────────────────────────────────────────────────
    cliente_conv = ConversationHandler(
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

    # ── Painel Admin / TI ─────────────────────────────────────────────
    admin_conv = ConversationHandler(
        entry_points=[CommandHandler("admin", painel_admin)],
        states={
            MENU: [CallbackQueryHandler(admin_callback)],
            AGUARD_MSG_USUARIO:      [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_msg_usuario)],
            TI_AGUARD_ADD_SERVICO:   [MessageHandler(filters.TEXT & ~filters.COMMAND, ti_add_servico)],
            TI_AGUARD_ADD_HORARIO:   [MessageHandler(filters.TEXT & ~filters.COMMAND, ti_add_horario)],
            TI_AGUARD_DEL_AGENDAMENTO: [MessageHandler(filters.TEXT & ~filters.COMMAND, ti_deletar_agendamento)],
            TI_AGUARD_EDITAR_ID:     [MessageHandler(filters.TEXT & ~filters.COMMAND, ti_editar_id)],
            TI_AGUARD_EDITAR_CAMPO:  [CallbackQueryHandler(admin_callback, pattern="^edit_campo_")],
            TI_AGUARD_EDITAR_VALOR:  [MessageHandler(filters.TEXT & ~filters.COMMAND, ti_editar_valor)],
        },
        fallbacks=[CommandHandler("cancelar", cancelar)],
        allow_reentry=True,
    )

    app.add_handler(cliente_conv)
    app.add_handler(admin_conv)
    app.add_error_handler(erro_handler)

    logger.info("🌸 Studio Dandara Britto Bot iniciado!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
