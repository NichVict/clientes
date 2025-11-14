import streamlit as st
import pandas as pd
import os
from supabase import create_client, Client

last_update_id = 0

# ==========================
# CONFIG SUPABASE
# ==========================
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

# ==========================
# UI
# ==========================
st.set_page_config(page_title="Telegram Manager", layout="wide")
st.title("🤖 Gerenciador do Bot do Telegram")
st.caption("Controle, sincronização e administração dos acessos ao Telegram.")

st.markdown("---")



st.markdown("---")

st.subheader("👤 Clientes e Status Telegram")

# Carrega tabela de clientes
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

# Normaliza campos
if "data_fim" in df.columns:
    df["data_fim"] = pd.to_datetime(df["data_fim"], errors="coerce").dt.date

# Preenche campos Telegram se ainda não existem
for col in ["telegram_id","telegram_username","telegram_connected","telegram_last_sync"]:
    if col not in df.columns:
        df[col] = None

st.dataframe(
    df[[
        "id","nome","email","carteiras","data_fim",
        "telegram_id","telegram_username","telegram_connected","telegram_last_sync"
    ]],
    use_container_width=True
)

st.markdown("---")

import time
import threading
import telebot

# ==========================
# CONFIG BOT DO TELEGRAM
# ==========================
TELEGRAM_TOKEN = get_secret("TELEGRAM_BOT_TOKEN")

if not TELEGRAM_TOKEN:
    st.error("❌ TELEGRAM_BOT_TOKEN não foi configurado em Secrets.")
    st.stop()

bot = telebot.TeleBot(TELEGRAM_TOKEN, parse_mode="HTML")

# ==========================
# FUNÇÕES AUXILIARES
# ==========================
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


# Grupo por carteira (config no secrets)
CARTEIRA_GRUPOS = {
    "Curto Prazo": st.secrets.get("TG_CURTO_LINK", ""),
    "Curtíssimo Prazo": st.secrets.get("TG_CURTISSIMO_LINK", ""),
    "Opções": st.secrets.get("TG_OPCOES_LINK", ""),
    "Criptomoedas": st.secrets.get("TG_CRIPTO_LINK", ""),
    "Clube": st.secrets.get("TG_CLUBE_LINK", ""),
}

# ==========================
# PROCESSADOR DO /start
# ==========================
def processar_start(message):
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "Para validar seu acesso, use o link enviado no e-mail.")
        return

    cliente_id = parts[1]

    # Busca cliente no Supabase
    resp = supabase.table("clientes").select("*").eq("id", cliente_id).execute()
    if not resp.data:
        bot.reply_to(message, "❌ Cadastro não encontrado. Fale com o suporte.")
        return

    cli = resp.data[0]

    nome = cli.get("nome") or "investidor"
    carteiras = carteiras_to_list(cli.get("carteiras", []))
    data_fim = parse_date(cli.get("data_fim"))
    hoje = pd.Timestamp.now().date()

    # Atualiza Telegram no Supabase
    try:
        supabase.table("clientes").update({
            "telegram_id": message.from_user.id,
            "telegram_username": message.from_user.username,
            "telegram_first_name": message.from_user.first_name,
            "telegram_connected": True,
            "telegram_last_sync": pd.Timestamp.utcnow().isoformat()
        }).eq("id", cliente_id).execute()
    except:
        pass

    # Verifica vigência
    if not data_fim or data_fim < hoje:
        bot.reply_to(
            message,
            f"⚠️ Olá {nome}! Sua assinatura está vencida (até {data_fim})."
        )
        return

    # Monta resposta com links
    linhas = [
        f"🎉 Olá <b>{nome}</b>! Seu acesso foi validado.\n\nAqui estão seus grupos:"
    ]

    for c in carteiras:
        link = CARTEIRA_GRUPOS.get(c, "")
        if link:
            linhas.append(f"• <b>{c}</b>: {link}")
        else:
            linhas.append(f"• <b>{c}</b>: (link não configurado)")

    bot.reply_to(message, "\n".join(linhas))


# ==========================
# POLLING (busca mensagens)
# ==========================
def rodar_bot():
    global last_update_id

    try:
        updates = bot.get_updates(offset=last_update_id + 1, timeout=1)
    except Exception as e:
        st.error(f"Erro ao buscar updates: {e}")
        return

    for update in updates:
        last_update_id = update.update_id

        if update.message:
            msg = update.message
            texto = msg.text or ""

            if texto.startswith("/start"):
                try:
                    processar_start(msg)
                except Exception as e:
                    st.error(f"Erro no processar_start: {e}")



# ==========================
# TIMER AUTOMÁTICO
# ==========================
def loop_automatico():
    while st.session_state.get("auto_bot", False):
        rodar_bot()
        time.sleep(3)  # roda a cada 3 segundos


# ==========================
# CONTROLES DO BOT NA TELA
# ==========================
st.markdown("---")
st.subheader("📡 Status & Ações do Bot")

# garante estado inicial
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


