# 07_Telegram_Bot_Manager.py

import streamlit as st
import pandas as pd
import os
import time
import threading
import telebot
from telebot import types
from supabase import create_client, Client

###############################################
# CONFIG & CONSTANTES
###############################################

LINKS_TELEGRAM = {
    "Curto Prazo": "https://t.me/+3BTqTX--W6gyNTE0",
    "Curtíssimo Prazo": "https://t.me/+BiTfqYUSiWpjN2U0",
    "Opções": "https://t.me/+1si_16NC5E8xNDhk",
    "Criptomoedas": "https://t.me/+-08kGaN0ZMsyNjJk"
}

# Controle de update_id persistente
if "last_update_id" not in st.session_state:
    st.session_state["last_update_id"] = 0

###############################################
# SUPABASE
###############################################

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

###############################################
# UI PRINCIPAL
###############################################

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
    df[["id", "nome", "email", "carteiras", "data_fim",
        "telegram_id", "telegram_username", "telegram_connected", "telegram_last_sync"]],
    use_container_width=True
)

st.markdown("---")

###############################################
# BOT TELEGRAM
###############################################

TELEGRAM_TOKEN = get_secret("TELEGRAM_BOT_TOKEN")

if not TELEGRAM_TOKEN:
    st.error("❌ TELEGRAM_BOT_TOKEN não foi configurado em Secrets.")
    st.stop()

bot = telebot.TeleBot(TELEGRAM_TOKEN, parse_mode="HTML")

###############################################
# FUNÇÕES AUXILIARES
###############################################

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
    except:
        return None

###############################################
# PROCESSAR /start — envia BOTÃO VALIDAR
###############################################

@bot.message_handler(commands=['start'])
def boas_vindas(message):
    parts = message.text.split()

    if len(parts) < 2:
        bot.send_message(message.chat.id, "Olá! Este link de acesso não é válido. Fale com o suporte.")
        return

    cliente_id = parts[1]

    resp = supabase.table("clientes").select("*").eq("id", cliente_id).execute()
    if not resp.data:
        bot.send_message(message.chat.id, "❌ Cadastro não encontrado.")
        return

    cli = resp.data[0]
    nome = cli.get("nome", "cliente")

    markup = types.InlineKeyboardMarkup()
    botao = types.InlineKeyboardButton(
        "VALIDAR ACESSO", callback_data=f"validar_{cliente_id}"
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

###############################################
# CALLBACK — botão VALIDAR ACESSO
###############################################

@bot.callback_query_handler(func=lambda call: call.data.startswith("validar_"))
def processar_validacao(call):
    bot.answer_callback_query(call.id)

    cliente_id = call.data.split("_")[1]

    resp = supabase.table("clientes").select("*").eq("id", cliente_id).execute()
    if not resp.data:
        bot.send_message(call.message.chat.id, "❌ Cadastro não encontrado.")
        return

    cli = resp.data[0]

    nome = cli.get("nome", "cliente")
    carteiras = carteiras_to_list(cli.get("carteiras", []))

    # Atualiza dados Telegram
    supabase.table("clientes").update({
        "telegram_id": call.from_user.id,
        "telegram_username": call.from_user.username,
        "telegram_first_name": call.from_user.first_name,
        "telegram_connected": True,
        "telegram_last_sync": pd.Timestamp.utcnow().isoformat()
    }).eq("id", cliente_id).execute()

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

###############################################
# POLLING — SEM FLOOD
###############################################

def rodar_bot():
    try:
        updates = bot.get_updates(
            offset=st.session_state["last_update_id"] + 1,
            timeout=1
        )
    except Exception as e:
        st.error(f"Erro ao buscar updates: {e}")
        return

    for update in updates:
        st.session_state["last_update_id"] = update.update_id

        if update.message:
            message = update.message
            texto = message.text or ""

            if texto.startswith("/start"):
                try:
                    boas_vindas(message)
                except Exception as e:
                    st.error(f"Erro no boas_vindas: {e}")

        if update.callback_query:
            call = update.callback_query

            if call.data.startswith("validar_"):
                try:
                    processar_validacao(call)
                except Exception as e:
                    st.error(f"Erro no processar_validacao: {e}")

###############################################
# LOOP AUTOMÁTICO
###############################################

def loop_automatico():
    while st.session_state.get("auto_bot", False):
        rodar_bot()
        time.sleep(1)

###############################################
# CONTROLES NA TELA
###############################################

st.markdown("---")
st.subheader("📡 Status & Ações do Bot")

if "auto_bot" not in st.session_state:
    st.session_state["auto_bot"] = False

col1, col2 = st.columns(2)

with col1:
    if st.button("🔄 Rodar sincronização manual agora"):
        rodar_bot()
        st.success("Bot sincronizado com sucesso.")

with col2:
    auto = st.checkbox(
        "⏱ Rodar automaticamente enquanto esta página estiver aberta",
        value=st.session_state["auto_bot"]
    )

if auto:
    st.session_state["auto_bot"] = True
    thread = threading.Thread(target=loop_automatico, daemon=True)
    thread.start()
else:
    st.session_state["auto_bot"] = False
