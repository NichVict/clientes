import streamlit as st
import pandas as pd
import os
from supabase import create_client, Client

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

st.subheader("📡 Status & Ações do Bot")

col1, col2 = st.columns(2)

with col1:
    if st.button("🔄 Rodar sincronização manual agora"):
        st.info("A sincronização será executada quando o bot for integrado.")
        
with col2:
    auto = st.checkbox("⏱ Rodar automaticamente enquanto esta página estiver aberta")

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

st.info("⚙️ O bot será integrado nos próximos passos.")
