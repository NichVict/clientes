import streamlit as st
import pandas as pd
import os
import time
import threading

import telebot
from telebot import types
from supabase import create_client, Client

# =========================================
# CONFIG - LINKS DOS GRUPOS TELEGRAM
# =========================================
LINKS_TELEGRAM = {
    "Curto Prazo": "https://t.me/+3BTqTX--W6gyNTE0",
    "Curtíssimo Prazo": "https://t.me/+BiTfqYUSiWpjN2U0",
    "Opções": "https://t.me/+1si_16NC5E8xNDhk",
    "Criptomoedas": "https://t.me/+-08kGaN0ZMsyNjJk",
    # "Clube": ""  # sem grupo de Telegram
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

# Garantir colunas de Telegram
for col in ["telegram_id", "telegram_username", "telegram_connected", "telegram_last_sync"]:
    if col not in df.columns:
        df[col] = None

st.dataframe(
    df[[
        "id", "nome", "email", "carteiras", "data_fim",
        "telegram_id", "telegram_username", "telegram_connected", "telegram_last_sync"
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
# THREAD DO BOT (infinity_polling)
# =========================================
def iniciar_bot():
    """
    Loop infinito do Telegram rodando em thread separada.
    Não depende do Streamlit para responder.
    """
    # timeout menores para não travar em caso de erro de rede
    bot.infinity_polling(timeout=10, long_polling_timeout=5)


# Garantir que só iniciamos o bot UMA vez
if "bot_started" not in st.session_state:
    st.session_state["bot_started"] = False

if not st.session_state["bot_started"]:
    thread = threading.Thread(target=iniciar_bot, daemon=True)
    thread.start()
    st.session_state["bot_started"] = True


# =========================================
# CONTROLES VISUAIS (STATUS)
# =========================================
st.subheader("📡 Status & Ações do Bot")

col1, col2 = st.columns(2)

with col1:
    st.success("🤖 Bot em execução automática em background.")

with col2:
    st.write("Quando o cliente clicar no link do e-mail, o bot responde na hora com o botão VALIDAR ACESSO.")
