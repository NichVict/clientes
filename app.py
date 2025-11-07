import streamlit as st
from supabase import create_client
from datetime import date, timedelta
import smtplib
from email.mime.text import MIMEText
import os

# ------- CONFIG -------
from dotenv import load_dotenv
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Login simples
def check_login(user, pwd):
    return user == "admin" and pwd == "123"

if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    st.title("Login")
    u = st.text_input("Usuário")
    p = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        if check_login(u,p):
            st.session_state.auth = True
            st.rerun()
        else:
            st.error("Credenciais inválidas")
    st.stop()

st.title("📋 Cadastro de Clientes")

# Form
with st.form("cadastro"):
    nome = st.text_input("Nome Completo")
    telefone = st.text_input("Telefone", value="+55 ")
    email = st.text_input("Email")
    carteiras = st.multiselect("Carteiras", ["Curto Prazo", "Curtíssimo Prazo", "Opções", "Criptomoedas", "Clube"])
    inicio = st.date_input("Início da Vigência", value=date.today())
    fim = st.date_input("Final da Vigência", value=date.today()+timedelta(days=90))
    pagamento = st.selectbox("Forma de Pagamento", ["PIX", "PAYPAL", "Infinite"])
    valor = st.number_input("Valor líquido", min_value=0.0)
    obs = st.text_area("Observação (Opcional)")
    submit = st.form_submit_button("Salvar")

    if submit:
        data = {
            "nome": nome,
            "telefone": telefone,
            "email": email,
            "carteiras": carteiras,
            "data_inicio": str(inicio),
            "data_fim": str(fim),
            "pagamento": pagamento,
            "valor": valor,
            "observacao": obs
        }
        supabase.table("clientes").insert(data).execute()
        st.success("Cliente cadastrado com sucesso!")

        if st.radio("Enviar e-mail de boas-vindas?", ["Não", "Sim"]) == "Sim":
            try:
                msg = MIMEText(f"Olá {nome}, seja bem-vindo! Estamos felizes em tê-lo conosco.")
                msg["Subject"] = "Bem-vindo!"
                msg["From"] = os.getenv("EMAIL_USER")
                msg["To"] = email

                server = smtplib.SMTP(os.getenv("EMAIL_HOST"), os.getenv("EMAIL_PORT"))
                server.starttls()
                server.login(os.getenv("EMAIL_USER"), os.getenv("EMAIL_PASS"))
                server.sendmail(msg["From"], [msg["To"]], msg.as_string())
                server.quit()

                st.success("E-mail enviado com sucesso!")
            except Exception as e:
                st.error(f"Erro ao enviar e-mail: {e}")

# -------- LISTAGEM CLIENTES --------
st.subheader("📊 Clientes Cadastrados")

clientes = supabase.table("clientes").select("*").execute().data

import pandas as pd
df = pd.DataFrame(clientes)

if not df.empty:
    today = date.today()
    def color(v):
        data = pd.to_datetime(v).date()
        if data < today:
            return "background-color: red"
        elif (data - today).days <= 30:
            return "background-color: yellow"
        else:
            return "background-color: lightgreen"

    st.dataframe(
        df.style.applymap(color, subset=["data_fim"])
    )
else:
    st.info("Nenhum cliente cadastrado ainda.")
