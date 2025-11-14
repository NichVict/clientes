import streamlit as st
import pandas as pd
import os
import time
import threading

import telebot
from telebot import types
from supabase import create_client, Client

# =========================================
# CONFIG - LINKS DOS GRUPOS TELEGRAM (ENTRADA)
# =========================================
LINKS_TELEGRAM = {
    "Curto Prazo": "https://t.me/+3BTqTX--W6gyNTE0",
    "Curtíssimo Prazo": "https://t.me/+BiTfqYUSiWpjN2U0",
    "Opções": "https://t.me/+1si_16NC5E8xNDhk",
    "Criptomoedas": "https://t.me/+-08kGaN0ZMsyNjJk",
    # "Leads": ""  # Leads não tem grupo
}

# =========================================
# CONFIG - CHAT_ID DOS GRUPOS (PARA EXPULSAR)
# =========================================
GROUP_CHAT_IDS = {
    "Curto Prazo": -1002046197953,
    "Curtíssimo Prazo": -1002074291817,
    "Opções": -1002001152534,
    "Criptomoedas": -1002947159530,
    # "Leads": None  # não é grupo
}

# =========================================
# SUPABASE
# =========================================
def get_secret(name: str, default=None):
    if name in st.secrets:
        return st.secrets[name]
    return os.getenv(name, default)

SUPABASE_URL = get_secret("SUPABASE_URL")
SUPABASE_KEY = get_secret("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("❌ SUPABASE_URL ou SUPABASE_KEY ausentes.")
    st.stop()

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# =========================================
# UI PRINCIPAL
# =========================================
st.set_page_config(page_title="Telegram Manager", layout="wide")
st.title("🤖 Gerenciador do Bot do Telegram")
st.caption("Controle, sincronização e administração dos acessos ao Telegram.")
st.markdown("---")

st.subheader("👤 Clientes e Status Telegram")

# Carrega clientes
try:
    resp = supabase.table("clientes").select("*").execute()
    dados = resp.data or []
except Exception as e:
    st.error(f"Erro ao carregar dados: {e}")
    st.stop()

if not dados:
    st.info("Nenhum cliente encontrado.")
    st.stop()

df = pd.DataFrame(dados)

# Normalizar datas
if "data_fim" in df.columns:
    df["data_fim"] = pd.to_datetime(df["data_fim"], errors="coerce").dt.date

# Garantir colunas de Telegram / controle
for col in ["telegram_id", "telegram_username", "telegram_connected",
            "telegram_last_sync", "telegram_removed_at"]:
    if col not in df.columns:
        df[col] = None

st.dataframe(
    df[[
        "id", "nome", "email", "carteiras", "data_fim",
        "telegram_id", "telegram_username",
        "telegram_connected", "telegram_last_sync", "telegram_removed_at"
    ]],
    use_container_width=True
)

st.markdown("---")

# =========================================
# BOT TELEGRAM
# =========================================
TELEGRAM_TOKEN = get_secret("TELEGRAM_BOT_TOKEN")

if not TELEGRAM_TOKEN:
    st.error("❌ TELEGRAM_BOT_TOKEN não foi configurado em Secrets.")
    st.stop()

bot = telebot.TeleBot(TELEGRAM_TOKEN, parse_mode="HTML")

# =========================================
# FUNÇÕES AUXILIARES
# =========================================
def carteiras_to_list(raw):
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        raw = raw.replace("[", "").replace("]", "").replace("'", "")
        return [x.strip() for x in raw.split(",") if x.strip()]
    return []


def parse_date(d):
    try:
        return pd.to_datetime(d).date()
    except Exception:
        return None


# =========================================
# /start COM ID -> mensagem com BOTÃO VALIDAR
# link no email: https://t.me/milhao_crm_bot?start=97
# =========================================
@bot.message_handler(commands=['start'])
def boas_vindas(message):
    parts = message.text.split()

    # precisa vir com ID na segunda parte
    if len(parts) < 2:
        bot.send_message(
            message.chat.id,
            "Olá! Este link de acesso não é válido. Fale com o suporte."
        )
        return

    cliente_id = parts[1]

    # Busca cliente no Supabase
    try:
        resp = supabase.table("clientes").select("*").eq("id", cliente_id).execute()
    except Exception:
        bot.send_message(message.chat.id, "❌ Erro ao consultar cadastro. Tente novamente.")
        return

    if not resp.data:
        bot.send_message(message.chat.id, "❌ Cadastro não encontrado.")
        return

    cli = resp.data[0]
    nome = cli.get("nome", "cliente")

    # botão VALIDAR ACESSO com callback_data contendo o id
    markup = types.InlineKeyboardMarkup()
    botao = types.InlineKeyboardButton(
        "VALIDAR ACESSO",
        callback_data=f"validar_{cliente_id}"
    )
    markup.add(botao)

    texto = (
        f"👋 Olá <b>{nome}</b>!\n\n"
        f"Clique no botão abaixo para validar sua entrada no grupo exclusivo."
    )

    bot.send_message(
        message.chat.id,
        texto,
        reply_markup=markup,
        parse_mode="HTML"
    )


# =========================================
# CALLBACK DO BOTÃO VALIDAR ACESSO
# =========================================
@bot.callback_query_handler(func=lambda call: call.data.startswith("validar_"))
def processar_validacao(call):
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        # Só pra garantir que não estoura se já tiver sido respondido
        pass

    cliente_id = call.data.split("_", 1)[1]

    # Busca cliente novamente
    try:
        resp = supabase.table("clientes").select("*").eq("id", cliente_id).execute()
    except Exception:
        bot.send_message(call.message.chat.id, "❌ Erro ao consultar cadastro. Tente novamente.")
        return

    if not resp.data:
        bot.send_message(call.message.chat.id, "❌ Cadastro não encontrado.")
        return

    cli = resp.data[0]
    nome = cli.get("nome", "cliente")
    carteiras = carteiras_to_list(cli.get("carteiras", []))
    data_fim = parse_date(cli.get("data_fim"))
    hoje = pd.Timestamp.now().date()

    # Verifica vigência
    if not data_fim or data_fim < hoje:
        bot.send_message(
            call.message.chat.id,
            f"⚠️ Olá {nome}! Sua assinatura está vencida (até {data_fim}).",
            parse_mode="HTML"
        )
        return

    # Atualiza dados do Telegram no Supabase
    try:
        supabase.table("clientes").update({
            "telegram_id": call.from_user.id,
            "telegram_username": call.from_user.username,
            "telegram_first_name": call.from_user.first_name,
            "telegram_connected": True,
            "telegram_last_sync": pd.Timestamp.utcnow().isoformat()
        }).eq("id", cliente_id).execute()
    except Exception:
        # se falhar o update, pelo menos segue com a mensagem
        pass

    # Monta mensagem com links
    linhas = [
        f"🎉 Acesso validado, <b>{nome}</b>!\n\nAqui estão seus grupos:"
    ]

    for c in carteiras:
        link = LINKS_TELEGRAM.get(c, "")
        if link:
            linhas.append(f"• <b>{c}</b>: {link}")
        else:
            linhas.append(f"• <b>{c}</b>: (sem grupo configurado)")

    bot.send_message(
        call.message.chat.id,
        "\n".join(linhas),
        parse_mode="HTML"
    )


# =========================================
# REMOÇÃO AUTOMÁTICA DE VENCIDOS + VIRAR LEAD
# =========================================
def remover_cliente_dos_grupos_e_virar_lead(cli) -> bool:
    """
    Expulsa o cliente de todos os grupos das carteiras dele,
    envia mensagem de aviso no privado e converte carteiras para ['Leads'].
    Retorna True se conseguiu processar.
    """
    cliente_id = cli.get("id")
    nome = cli.get("nome", "cliente")
    telegram_id = cli.get("telegram_id")

    if not telegram_id:
        return False

    carteiras_orig = carteiras_to_list(cli.get("carteiras", []))
    carteiras_texto = ", ".join(carteiras_orig) if carteiras_orig else "sua carteira"

    # 1) Expulsar de cada grupo
    for c in carteiras_orig:
        chat_id = GROUP_CHAT_IDS.get(c)
        if not chat_id:
            continue
        try:
            # Expulsa e em seguida desbloqueia (remove sem banir permanentemente)
            bot.ban_chat_member(chat_id, telegram_id)
            bot.unban_chat_member(chat_id, telegram_id)
        except Exception:
            # Se der erro em um grupo, seguimos para os demais
            pass

    # 2) Atualizar registro para virar Lead e marcar desconexão
    try:
        supabase.table("clientes").update({
            "carteiras": ["Leads"],
            "telegram_connected": False,
            "telegram_removed_at": pd.Timestamp.utcnow().isoformat()
        }).eq("id", cliente_id).execute()
    except Exception:
        # mesmo que falhe o update, tentamos enviar mensagem
        pass

    # 3) Avisar o cliente no privado
    try:
        bot.send_message(
            telegram_id,
            (
                f"⚠️ Olá {nome}! Sua assinatura da(s) carteira(s) {carteiras_texto} "
                f"venceu e seu acesso ao(s) grupo(s) exclusivo(s) foi removido.\n\n"
                f"Se quiser renovar, fale com a equipe ou responda esta mensagem."
            )
        )
    except Exception:
        # se não conseguir mandar mensagem privada, vida que segue
        pass

    return True


def verificar_e_excluir_vencidos() -> int:
    """
    Busca clientes vencidos com telegram_connected = True,
    expulsa dos grupos e converte para Leads.
    Retorna quantos foram processados.
    """
    hoje = pd.Timestamp.now().date()
    processados = 0

    try:
        resp = (
            supabase
            .table("clientes")
            .select("*")
            .lt("data_fim", str(hoje))
            .eq("telegram_connected", True)
            .execute()
        )
    except Exception:
        return 0

    clientes = resp.data or []

    for cli in clientes:
        carteiras = carteiras_to_list(cli.get("carteiras", []))
        # Se já é Lead ou não tem carteiras, pula
        if not carteiras or (len(carteiras) == 1 and carteiras[0] == "Leads"):
            continue

        ok = remover_cliente_dos_grupos_e_virar_lead(cli)
        if ok:
            processados += 1

    return processados


# =========================================
# THREAD DO BOT (infinity_polling)
# =========================================
def iniciar_bot():
    """
    Loop infinito do Telegram rodando em thread separada.
    Não depende do Streamlit para responder.
    """
    bot.infinity_polling(timeout=10, long_polling_timeout=5)


# =========================================
# THREAD DA ROTINA DIÁRIA DE VENCIDOS (24h)
# =========================================
def rotina_remocao_vencidos():
    while True:
        try:
            verificar_e_excluir_vencidos()
        except Exception:
            pass
        # 24 horas (em segundos)
        time.sleep(24 * 60 * 60)


# =========================================
# INICIALIZAÇÃO DAS THREADS (BOT + LIMPEZA)
# =========================================
if "bot_started" not in st.session_state:
    st.session_state["bot_started"] = False

if "cleanup_started" not in st.session_state:
    st.session_state["cleanup_started"] = False

# Inicia o bot uma única vez
if not st.session_state["bot_started"]:
    thread_bot = threading.Thread(target=iniciar_bot, daemon=True)
    thread_bot.start()
    st.session_state["bot_started"] = True

# Inicia rotina diária de remoção de vencidos
if not st.session_state["cleanup_started"]:
    thread_clean = threading.Thread(target=rotina_remocao_vencidos, daemon=True)
    thread_clean.start()
    st.session_state["cleanup_started"] = True


# =========================================
# CONTROLES VISUAIS (STATUS)
# =========================================
st.subheader("📡 Status & Ações do Bot")

col1, col2 = st.columns(2)

with col1:
    st.success("🤖 Bot em execução automática em background (infinity_polling).")

with col2:
    st.info("🕒 Rotina diária de remoção de assinaturas vencidas ativa (intervalo: 24h).")

st.markdown("---")

st.subheader("🧪 Testes manuais")

if st.button("🚨 Rodar verificação de vencidos agora"):
    qnt = verificar_e_excluir_vencidos()
    if qnt > 0:
        st.success(f"Remoção executada. Clientes processados: {qnt}.")
    else:
        st.warning("Nenhum cliente vencido com Telegram conectado foi encontrado.")
