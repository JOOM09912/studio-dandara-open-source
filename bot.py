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

# ─── Logs ─────────────────────────────────────────────────────────────
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── Env ──────────────────────────────────────────────────────────────
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
SUPABASE_URL   = os.getenv("SUPABASE_URL")
SUPABASE_KEY   = os.getenv("SUPABASE_KEY")

# ─── Supabase ─────────────────────────────────────────────────────────
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ─── IDs ──────────────────────────────────────────────────────────────
ADMIN_ID = 7539142683
TI_ID    = 8367937028

# ─── Estados ──────────────────────────────────────────────────────────
(
    MENU, NOME, SERVICO, DATA, HORARIO,
    AGUARD_MSG_USUARIO,
    AGUARD_EXCLUIR,
    TI_AGUARD_ADD_SERVICO,
    TI_AGUARD_ADD_HORARIO,
    TI_AGUARD_EDITAR_ID,
    TI_AGUARD_EDITAR_CAMPO,
    TI_AGUARD_EDITAR_VALOR,
) = range(12)

# ─── Dados dinâmicos ──────────────────────────────────────────────────
SERVICOS = ["Manicure", "Pedicure", "Alongamento", "Blindagem", "Nail Art"]
HORARIOS = ["09:00", "10:00", "11:00", "13:00", "14:00", "15:00", "16:00", "17:00"]


# ══════════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════════

def validar_data(s):
    try:
        return datetime.strptime(s, "%d/%m/%Y").date() >= datetime.now().date()
    except ValueError:
        return False

def validar_horario(h):
    return h in HORARIOS

async def safe_edit(query, text, markup=None, parse_mode="Markdown"):
    """Edita mensagem ignorando erro de conteúdo idêntico."""
    try:
        await query.edit_message_text(text, parse_mode=parse_mode, reply_markup=markup)
    except Exception as e:
        if "Message is not modified" in str(e):
            pass
        else:
            try:
                await query.message.reply_text(text, parse_mode=parse_mode, reply_markup=markup)
            except Exception:
                logger.warning(f"safe_edit falhou: {e}")

def fmt_ag(ag):
    status = ag.get("status", "pendente")
    emoji  = {"pendente": "⏳", "confirmado": "✅", "cancelado": "❌"}.get(status, "⏳")
    return (
        f"{emoji} *{ag['nome']}* — {ag['servico']}\n"
        f"   📅 {ag['data']} às 🕐 {ag['horario']} | {status.upper()}\n"
        f"   🆔 `{str(ag['id'])[:8]}`\n"
    )

# ─── Menus ────────────────────────────────────────────────────────────

def menu_admin_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Agendamentos de hoje",  callback_data="adm_hoje")],
        [InlineKeyboardButton("📅 Todos os agendamentos", callback_data="adm_todos")],
        [InlineKeyboardButton("✅ Confirmar agendamento",  callback_data="adm_confirmar")],
        [InlineKeyboardButton("❌ Cancelar agendamento",   callback_data="adm_cancelar_ag")],
        [InlineKeyboardButton("🗑 Excluir agendamento",   callback_data="excluir_menu")],
        [InlineKeyboardButton("💬 Enviar msg a cliente",  callback_data="adm_msg")],
    ])

def menu_ti_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Ver todos agendamentos",   callback_data="ti_todos")],
        [InlineKeyboardButton("🗑 Excluir agendamento",      callback_data="excluir_menu")],
        [InlineKeyboardButton("✏️ Editar agendamento",       callback_data="ti_editar")],
        [InlineKeyboardButton("➕ Adicionar serviço",        callback_data="ti_add_servico")],
        [InlineKeyboardButton("➖ Remover serviço",          callback_data="ti_del_servico")],
        [InlineKeyboardButton("⏰ Adicionar horário",        callback_data="ti_add_horario")],
        [InlineKeyboardButton("🕐 Remover horário",          callback_data="ti_del_horario")],
        [InlineKeyboardButton("📊 Estatísticas",             callback_data="ti_stats")],
        [InlineKeyboardButton("🔄 Listar serviços/horários", callback_data="ti_listar")],
    ])

def voltar_kb(destino):
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Voltar", callback_data=destino)]])


# ══════════════════════════════════════════════════════════════════════
#  FLUXO CLIENTE
# ══════════════════════════════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Agendar horário",          callback_data="agendar")],
        [InlineKeyboardButton("🕐 Ver horários disponíveis", callback_data="horarios")],
    ])
    await update.message.reply_text(
        "🌸 *Querida e distinta visitante,*\n\n"
        "Seja muito bem-vinda ao *Studio Dandara Britto* — "
        "o salão mais refinado e encantador desta temporada. 👑\n\n"
        "A sociedade toda já sabe: quem cuida das unhas aqui, "
        "jamais passa despercebida nos salões da alta sociedade. 💅✨\n\n"
        "Como posso lhe ser útil hoje?",
        reply_markup=kb, parse_mode="Markdown",
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
            "Use /start para agendar.",
            parse_mode="Markdown",
        )
        return ConversationHandler.END

    await query.edit_message_text(
        "✨ *Esplêndido! Uma escolha verdadeiramente sábia.*\n\n"
        "Permita-me colher algumas informações. 📋\n\n"
        "Primeiramente, qual é o seu *nome completo*, minha cara?",
        parse_mode="Markdown",
    )
    return NOME

async def receber_nome(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    nome = update.message.text.strip()
    if len(nome) < 2:
        await update.message.reply_text("🌸 Informe seu *nome completo*, minha cara.", parse_mode="Markdown")
        return NOME
    context.user_data["nome"]        = nome
    context.user_data["telegram_id"] = update.effective_user.id
    markup = ReplyKeyboardMarkup([[s] for s in SERVICOS], one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(
        f"_Que nome encantador,_ *{nome}*! 👑\n\nQual serviço a senhora deseja?",
        reply_markup=markup, parse_mode="Markdown",
    )
    return SERVICO

async def receber_servico(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    servico = update.message.text.strip()
    if servico not in SERVICOS:
        markup = ReplyKeyboardMarkup([[s] for s in SERVICOS], one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text("🌸 Escolha um serviço da lista:", reply_markup=markup)
        return SERVICO
    context.user_data["servico"] = servico
    await update.message.reply_text(
        f"*{servico}* — uma escolha impecável! ✨\n\nInforme a *data* no formato *DD/MM/AAAA*:",
        reply_markup=ReplyKeyboardRemove(), parse_mode="Markdown",
    )
    return DATA

async def receber_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    data_str = update.message.text.strip()
    if not validar_data(data_str):
        await update.message.reply_text(
            "🌸 Data inválida ou passada. Informe uma data futura no formato *DD/MM/AAAA*:",
            parse_mode="Markdown",
        )
        return DATA
    context.user_data["data"] = data_str
    markup = ReplyKeyboardMarkup([HORARIOS[i:i+2] for i in range(0, len(HORARIOS), 2)], one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(
        f"📅 *{data_str}* anotado! 🌸\n\nEm qual *horário* deseja ser recebida?",
        reply_markup=markup, parse_mode="Markdown",
    )
    return HORARIO

async def receber_horario(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    horario = update.message.text.strip()
    if not validar_horario(horario):
        markup = ReplyKeyboardMarkup([HORARIOS[i:i+2] for i in range(0, len(HORARIOS), 2)], one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text("🌸 Horário inválido. Escolha um da lista:", reply_markup=markup)
        return HORARIO

    nome    = context.user_data["nome"]
    servico = context.user_data["servico"]
    data    = context.user_data["data"]
    tg_id   = context.user_data.get("telegram_id")

    await update.message.reply_text("✨ Registrando seu agendamento...", reply_markup=ReplyKeyboardRemove())

    try:
        res   = supabase.table("agendamentos").insert({
            "nome": nome, "servico": servico, "data": data,
            "horario": horario, "telegram_id": str(tg_id), "status": "pendente",
        }).execute()
        ag_id = res.data[0]["id"] if res.data else "?"
        ok    = True
    except Exception as e:
        logger.error(f"Supabase insert error: {e}")
        ok    = False
        ag_id = "?"

    if ok:
        await update.message.reply_text(
            "👑 *Que notícia esplêndida!*\n\n"
            "Seu agendamento foi registrado! Os fofoqueiros da sociedade "
            "já estão comentando sobre sua próxima visita! 🌸\n\n"
            f"👤 *Nome:* {nome}\n💅 *Serviço:* {servico}\n"
            f"📅 *Data:* {data}\n🕐 *Horário:* {horario}\n\n"
            "_Aguarde a confirmação. Até breve, querida!_ 💖",
            parse_mode="Markdown",
        )
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    "🔔 *Novo agendamento!*\n\n"
                    f"👤 *Nome:* {nome}\n💅 *Serviço:* {servico}\n"
                    f"📅 *Data:* {data}\n🕐 *Horário:* {horario}\n"
                    f"🆔 `{ag_id}`\n\nUse /admin para confirmar. 👑"
                ),
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.warning(f"Erro ao notificar admin: {e}")
    else:
        await update.message.reply_text(
            "😔 *Desculpe, minha cara.* Um imprevisto impediu o registro.\nTente novamente com /start. 🌸"
        )

    context.user_data.clear()
    return ConversationHandler.END

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text(
        "🌸 *Como desejar.*\n\n_Quando estiver pronta, use /start._ 👑",
        reply_markup=ReplyKeyboardRemove(), parse_mode="Markdown",
    )
    return ConversationHandler.END


# ══════════════════════════════════════════════════════════════════════
#  PAINEL ADMIN / TI
# ══════════════════════════════════════════════════════════════════════

async def painel_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    uid = update.effective_user.id
    if uid == ADMIN_ID:
        await update.message.reply_text(
            "👑 *Bem-vinda, Administradora!*\n\n_O que deseja gerenciar?_",
            reply_markup=menu_admin_kb(), parse_mode="Markdown",
        )
        return MENU
    elif uid == TI_ID:
        await update.message.reply_text(
            "🛠 *Bem-vindo, TI!*\n\n_Painel técnico à sua disposição._",
            reply_markup=menu_ti_kb(), parse_mode="Markdown",
        )
        return MENU
    else:
        await update.message.reply_text(
            "🌸 *Esta ala é restrita à alta sociedade.*\n\n_Apenas membros autorizados._ 👑",
            parse_mode="Markdown",
        )
        return ConversationHandler.END

def voltar_menu_kb(uid):
    """Retorna o teclado correto baseado em quem está usando."""
    return menu_admin_kb() if uid == ADMIN_ID else menu_ti_kb()

def voltar_label(uid):
    return "adm_voltar" if uid == ADMIN_ID else "ti_voltar"


# ── Callback principal ────────────────────────────────────────────────

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query   = update.callback_query
    uid     = query.from_user.id
    data    = query.data

    if uid not in {ADMIN_ID, TI_ID}:
        await query.answer("Acesso negado.", show_alert=True)
        return ConversationHandler.END

    await query.answer()
    menu_kb = voltar_menu_kb(uid)

    # ══ EXCLUIR — disponível para AMBOS ══════════════════════════════

    if data == "excluir_menu":
        # Lista todos os agendamentos com botão de exclusão
        res = supabase.table("agendamentos").select("*").order("data").order("horario").execute()
        ags = res.data
        if not ags:
            await safe_edit(query, "🗑 *Excluir agendamento:*\n\n_Nenhum agendamento encontrado._", menu_kb)
            return MENU

        botoes = []
        for ag in ags:
            status_emoji = {"pendente": "⏳", "confirmado": "✅", "cancelado": "❌"}.get(ag.get("status",""), "⏳")
            label = f"{status_emoji} {ag['nome']} — {ag['data']} {ag['horario']}"
            botoes.append([InlineKeyboardButton(label, callback_data=f"excluir_{ag['id']}")])
        botoes.append([InlineKeyboardButton("🔙 Voltar", callback_data=voltar_label(uid))])

        await safe_edit(query, "🗑 *Selecione o agendamento para excluir:*", InlineKeyboardMarkup(botoes))
        return MENU

    elif data.startswith("excluir_"):
        ag_id = data.replace("excluir_", "")
        try:
            res = supabase.table("agendamentos").select("*").eq("id", ag_id).execute()
            ag  = res.data[0] if res.data else None
            supabase.table("agendamentos").delete().eq("id", ag_id).execute()
            nome = ag["nome"] if ag else "?"
            await safe_edit(query,
                f"🗑 *Agendamento de {nome} excluído com sucesso!*",
                menu_kb)
        except Exception as e:
            await safe_edit(query, f"❌ Erro ao excluir: {e}", menu_kb)
        return MENU

    # ══ ADMIN ════════════════════════════════════════════════════════

    elif data == "adm_hoje":
        hoje = datetime.now().strftime("%d/%m/%Y")
        res  = supabase.table("agendamentos").select("*").eq("data", hoje).order("horario").execute()
        ags  = res.data
        if not ags:
            texto = f"📋 *Hoje ({hoje}):*\n\n_Nenhum agendamento para hoje._ 🌸"
        else:
            linhas = [f"📋 *Agendamentos de hoje ({hoje}) — {len(ags)} cliente(s):*\n"]
            for ag in ags:
                linhas.append(fmt_ag(ag))
            texto = "\n".join(linhas)
        await safe_edit(query, texto, menu_admin_kb())
        return MENU

    elif data == "adm_todos":
        res = supabase.table("agendamentos").select("*").order("data").order("horario").execute()
        ags = res.data
        if not ags:
            texto = "📅 *Todos os agendamentos:*\n\n_Nenhum agendamento._ 🌸"
        else:
            linhas = [f"📅 *Todos os agendamentos ({len(ags)}):*\n"]
            for ag in ags:
                linhas.append(fmt_ag(ag))
            texto = "\n".join(linhas)
            if len(texto) > 4000:
                texto = texto[:4000] + "\n\n_...lista truncada._"
        await safe_edit(query, texto, menu_admin_kb())
        return MENU

    elif data == "adm_confirmar":
        res = supabase.table("agendamentos").select("*").eq("status", "pendente").order("data").execute()
        ags = res.data
        if not ags:
            await safe_edit(query, "✅ *Confirmar:*\n\n_Nenhum agendamento pendente._ 🌸", menu_admin_kb())
            return MENU
        botoes = [[InlineKeyboardButton(
            f"{ag['nome']} — {ag['data']} {ag['horario']}",
            callback_data=f"confirmar_{ag['id']}"
        )] for ag in ags]
        botoes.append([InlineKeyboardButton("🔙 Voltar", callback_data="adm_voltar")])
        await safe_edit(query, "✅ *Qual agendamento confirmar?*", InlineKeyboardMarkup(botoes))
        return MENU

    elif data.startswith("confirmar_"):
        ag_id = data.replace("confirmar_", "")
        res   = supabase.table("agendamentos").update({"status": "confirmado"}).eq("id", ag_id).execute()
        ag    = res.data[0] if res.data else None
        if ag:
            await safe_edit(query,
                f"✅ *{ag['nome']} confirmada!*\n\n📅 {ag['data']} às 🕐 {ag['horario']}",
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
                            "_Te esperamos! Até lá, querida!_ 🌸"
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
            await safe_edit(query, "❌ *Cancelar:*\n\n_Nenhum agendamento ativo._ 🌸", menu_admin_kb())
            return MENU
        botoes = [[InlineKeyboardButton(
            f"{ag['nome']} — {ag['data']} {ag['horario']}",
            callback_data=f"cancela_{ag['id']}"
        )] for ag in ags]
        botoes.append([InlineKeyboardButton("🔙 Voltar", callback_data="adm_voltar")])
        await safe_edit(query, "❌ *Qual agendamento cancelar?*", InlineKeyboardMarkup(botoes))
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
                            "😔 *Seu agendamento foi cancelado.*\n\n"
                            f"📅 {ag['data']} às 🕐 {ag['horario']}\n\n"
                            "_Entre em contato para reagendar._ 🌸"
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
                botoes.append([InlineKeyboardButton(ag["nome"], callback_data=f"msg_{tid}_{ag['nome'][:15]}")])
        botoes.append([InlineKeyboardButton("🔙 Voltar", callback_data="adm_voltar")])
        if len(botoes) == 1:
            await safe_edit(query, "💬 _Nenhum cliente com ID registrado ainda._ 🌸", menu_admin_kb())
            return MENU
        await safe_edit(query, "💬 *Para qual cliente enviar mensagem?*", InlineKeyboardMarkup(botoes))
        return MENU

    elif data.startswith("msg_"):
        partes = data[4:].split("_", 1)
        tid    = partes[0]
        nome   = partes[1] if len(partes) > 1 else "Cliente"
        context.user_data["msg_destino_id"]   = tid
        context.user_data["msg_destino_nome"] = nome
        await safe_edit(query, f"💬 *Digite a mensagem para {nome}:*\n\n_/cancelar para voltar._")
        return AGUARD_MSG_USUARIO

    elif data == "adm_voltar":
        await safe_edit(query, "👑 *Painel Admin — Studio Dandara Britto*\n\n_O que deseja?_", menu_admin_kb())
        return MENU

    # ══ TI ═══════════════════════════════════════════════════════════

    elif data == "ti_todos":
        res = supabase.table("agendamentos").select("*").order("criado_em", desc=True).execute()
        ags = res.data
        if not ags:
            texto = "📋 *Agendamentos:*\n\n_Nenhum agendamento encontrado._"
        else:
            linhas = [f"📋 *Todos ({len(ags)}):*\n"]
            for ag in ags:
                linhas.append(fmt_ag(ag))
            texto = "\n".join(linhas)
            if len(texto) > 4000:
                texto = texto[:4000] + "\n_...truncado._"
        await safe_edit(query, texto, menu_ti_kb())
        return MENU

    elif data == "ti_editar":
        await safe_edit(query,
            "✏️ *Digite o ID (ou primeiros caracteres) do agendamento a editar:*\n\n_/cancelar para voltar._")
        return TI_AGUARD_EDITAR_ID

    elif data == "ti_add_servico":
        await safe_edit(query, f"➕ *Serviços atuais:*\n{', '.join(SERVICOS)}\n\n*Digite o novo serviço:*")
        return TI_AGUARD_ADD_SERVICO

    elif data == "ti_del_servico":
        botoes = [[InlineKeyboardButton(s, callback_data=f"delserv_{s}")] for s in SERVICOS]
        botoes.append([InlineKeyboardButton("🔙 Voltar", callback_data="ti_voltar")])
        await safe_edit(query, "➖ *Qual serviço remover?*", InlineKeyboardMarkup(botoes))
        return MENU

    elif data.startswith("delserv_"):
        servico = data.replace("delserv_", "")
        if servico in SERVICOS:
            SERVICOS.remove(servico)
        await safe_edit(query, f"✅ *{servico}* removido!\n\nServiços: {', '.join(SERVICOS)}", menu_ti_kb())
        return MENU

    elif data == "ti_add_horario":
        await safe_edit(query, f"⏰ *Horários atuais:*\n{', '.join(HORARIOS)}\n\n*Digite o novo horário (HH:MM):*")
        return TI_AGUARD_ADD_HORARIO

    elif data == "ti_del_horario":
        botoes = [[InlineKeyboardButton(h, callback_data=f"delhor_{h}")] for h in HORARIOS]
        botoes.append([InlineKeyboardButton("🔙 Voltar", callback_data="ti_voltar")])
        await safe_edit(query, "🕐 *Qual horário remover?*", InlineKeyboardMarkup(botoes))
        return MENU

    elif data.startswith("delhor_"):
        horario = data.replace("delhor_", "")
        if horario in HORARIOS:
            HORARIOS.remove(horario)
        await safe_edit(query, f"✅ *{horario}* removido!\n\nHorários: {', '.join(HORARIOS)}", menu_ti_kb())
        return MENU

    elif data == "ti_stats":
        try:
            hoje     = datetime.now().strftime("%d/%m/%Y")
            total    = supabase.table("agendamentos").select("*", count="exact").execute()
            pend     = supabase.table("agendamentos").select("*", count="exact").eq("status", "pendente").execute()
            conf     = supabase.table("agendamentos").select("*", count="exact").eq("status", "confirmado").execute()
            canc     = supabase.table("agendamentos").select("*", count="exact").eq("status", "cancelado").execute()
            hj       = supabase.table("agendamentos").select("*", count="exact").eq("data", hoje).execute()
            await safe_edit(query,
                "📊 *Estatísticas:*\n\n"
                f"📋 Total: *{total.count}*\n"
                f"⏳ Pendentes: *{pend.count}*\n"
                f"✅ Confirmados: *{conf.count}*\n"
                f"❌ Cancelados: *{canc.count}*\n"
                f"📅 Hoje: *{hj.count}*\n\n"
                f"💅 Serviços: *{len(SERVICOS)}*\n"
                f"⏰ Horários: *{len(HORARIOS)}*",
                menu_ti_kb())
        except Exception as e:
            await safe_edit(query, f"❌ Erro: {e}", menu_ti_kb())
        return MENU

    elif data == "ti_listar":
        await safe_edit(query,
            "💅 *Serviços:*\n" + "\n".join(f"  • {s}" for s in SERVICOS) +
            "\n\n⏰ *Horários:*\n" + "\n".join(f"  • {h}" for h in HORARIOS),
            menu_ti_kb())
        return MENU

    elif data == "ti_voltar":
        await safe_edit(query, "🛠 *Painel TI — Studio Dandara Britto*\n\n_O que deseja?_", menu_ti_kb())
        return MENU

    elif data.startswith("edit_campo_"):
        campo_map = {
            "edit_campo_nome":    ("nome",    "novo nome"),
            "edit_campo_servico": ("servico", "novo serviço"),
            "edit_campo_data":    ("data",    "nova data (DD/MM/AAAA)"),
            "edit_campo_horario": ("horario", "novo horário (HH:MM)"),
        }
        if data in campo_map:
            campo, desc = campo_map[data]
            context.user_data["editar_campo"] = campo
            await safe_edit(query, f"✏️ *Digite o {desc}:*")
            return TI_AGUARD_EDITAR_VALOR
        return MENU

    return MENU


# ══════════════════════════════════════════════════════════════════════
#  HANDLERS DE TEXTO — ADMIN E TI
# ══════════════════════════════════════════════════════════════════════

async def receber_msg_usuario(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    texto = update.message.text.strip()
    tid   = context.user_data.get("msg_destino_id")
    nome  = context.user_data.get("msg_destino_nome", "Cliente")
    try:
        await context.bot.send_message(
            chat_id=int(tid),
            text=f"💬 *Mensagem do Studio Dandara Britto:*\n\n{texto}",
            parse_mode="Markdown",
        )
        await update.message.reply_text(f"✅ Mensagem enviada para *{nome}*! 🌸",
            parse_mode="Markdown", reply_markup=menu_admin_kb())
    except Exception as e:
        await update.message.reply_text(f"❌ Erro: {e}", reply_markup=menu_admin_kb())
    context.user_data.clear()
    return MENU

async def ti_add_servico(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    novo = update.message.text.strip().title()
    if novo in SERVICOS:
        await update.message.reply_text(f"⚠️ *{novo}* já existe!", parse_mode="Markdown", reply_markup=menu_ti_kb())
    else:
        SERVICOS.append(novo)
        await update.message.reply_text(f"✅ *{novo}* adicionado!\n\nServiços: {', '.join(SERVICOS)}",
            parse_mode="Markdown", reply_markup=menu_ti_kb())
    return MENU

async def ti_add_horario(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    novo = update.message.text.strip()
    if not re.match(r"^\d{2}:\d{2}$", novo):
        await update.message.reply_text("❌ Use o formato *HH:MM* (ex: 08:30):", parse_mode="Markdown")
        return TI_AGUARD_ADD_HORARIO
    if novo in HORARIOS:
        await update.message.reply_text(f"⚠️ *{novo}* já existe!", parse_mode="Markdown", reply_markup=menu_ti_kb())
    else:
        HORARIOS.append(novo)
        HORARIOS.sort()
        await update.message.reply_text(f"✅ *{novo}* adicionado!\n\nHorários: {', '.join(HORARIOS)}",
            parse_mode="Markdown", reply_markup=menu_ti_kb())
    return MENU

async def ti_editar_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    ag_id = update.message.text.strip()
    try:
        res = supabase.table("agendamentos").select("*").ilike("id", f"{ag_id}%").execute()
        if not res.data:
            await update.message.reply_text("❌ Agendamento não encontrado.", reply_markup=menu_ti_kb())
            return MENU
        ag = res.data[0]
        context.user_data["editar_id"] = ag["id"]
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("👤 Nome",    callback_data="edit_campo_nome")],
            [InlineKeyboardButton("💅 Serviço", callback_data="edit_campo_servico")],
            [InlineKeyboardButton("📅 Data",    callback_data="edit_campo_data")],
            [InlineKeyboardButton("🕐 Horário", callback_data="edit_campo_horario")],
            [InlineKeyboardButton("🔙 Voltar",  callback_data="ti_voltar")],
        ])
        await update.message.reply_text(
            f"✏️ *Editando: {ag['nome']}*\n\n"
            f"💅 {ag['servico']} | 📅 {ag['data']} às {ag['horario']}\n\n"
            "*Qual campo alterar?*",
            parse_mode="Markdown", reply_markup=kb,
        )
        return TI_AGUARD_EDITAR_CAMPO
    except Exception as e:
        await update.message.reply_text(f"❌ Erro: {e}", reply_markup=menu_ti_kb())
        return MENU

async def ti_editar_valor(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    novo  = update.message.text.strip()
    ag_id = context.user_data.get("editar_id")
    campo = context.user_data.get("editar_campo")
    try:
        supabase.table("agendamentos").update({campo: novo}).eq("id", ag_id).execute()
        await update.message.reply_text(f"✅ *{campo}* atualizado para *{novo}*!",
            parse_mode="Markdown", reply_markup=menu_ti_kb())
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
        raise ValueError("TELEGRAM_TOKEN não encontrado")
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("SUPABASE_URL ou SUPABASE_KEY não encontrados")

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # Fluxo cliente
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

    # Painel Admin / TI
    admin_conv = ConversationHandler(
        entry_points=[CommandHandler("admin", painel_admin)],
        states={
            MENU: [CallbackQueryHandler(admin_callback)],
            AGUARD_MSG_USUARIO:    [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_msg_usuario)],
            TI_AGUARD_ADD_SERVICO: [MessageHandler(filters.TEXT & ~filters.COMMAND, ti_add_servico)],
            TI_AGUARD_ADD_HORARIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, ti_add_horario)],
            TI_AGUARD_EDITAR_ID:   [MessageHandler(filters.TEXT & ~filters.COMMAND, ti_editar_id)],
            TI_AGUARD_EDITAR_CAMPO:[CallbackQueryHandler(admin_callback, pattern="^edit_campo_")],
            TI_AGUARD_EDITAR_VALOR:[MessageHandler(filters.TEXT & ~filters.COMMAND, ti_editar_valor)],
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
