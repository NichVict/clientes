# clientes.py
# ------------------------------------------------------------
# App Streamlit para cadastro de clientes com Supabase
# - Login simples (usuario/senha fixos)
# - Formulário de cadastro
# - Gravação e leitura no Supabase
# - Tabela com destaque de cor pela data de fim da vigência
# - Opção de enviar e-mail de boas-vindas após cadastro (com dois botões)
#
# Requer no Streamlit Cloud (Settings -> Secrets):
#   SUPABASE_URL
#   SUPABASE_KEY
#   EMAIL_HOST
#   EMAIL_PORT
#   EMAIL_USER
#   EMAIL_PASS
#
# requirements.txt:
#   streamlit
#   supabase
#   python-dotenv
#   pandas
# ------------------------------------------------------------

import os
import smtplib
from email.mime.text import MIMEText
from datetime import date, timedelta, datetime

import pandas as pd
import streamlit as st
from supabase import create_client, Client


# ---------------------- CONFIG STREAMLIT ----------------------
st.set_page_config(page_title="Clientes - CRM", layout="wide")


# ---------------------- SECRETS / CONFIG ----------------------
def get_secret(name: str, default=None):
    # Prioriza st.secrets (Cloud). Em dev local, pode cair para variável de ambiente.
    if name in st.secrets:
        return st.secrets[name]
    return os.getenv(name, default)

SUPABASE_URL = get_secret("SUPABASE_URL")
SUPABASE_KEY = get_secret("SUPABASE_KEY")

EMAIL_USER = get_secret("email_sender")
EMAIL_PASS = get_secret("gmail_app_password")

EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587


if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("Configuração do Supabase ausente. Defina SUPABASE_URL e SUPABASE_KEY em Secrets.")
    st.stop()

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"Falha ao inicializar Supabase: {e}")
    st.stop()


# ---------------------- AUTENTICAÇÃO SIMPLES ----------------------
def check_login(user: str, pwd: str) -> bool:
    # Ajuste aqui se quiser trocar credenciais
    return user == "admin" and pwd == "123"


if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    st.title("🔐 Login")
    col1, col2 = st.columns([1, 1])
    with col1:
        user = st.text_input("Usuário")
    with col2:
        pwd = st.text_input("Senha", type="password")
    if st.button("Entrar", use_container_width=True):
        if check_login(user, pwd):
            st.session_state.auth = True
            st.rerun()
        else:
            st.error("Credenciais inválidas.")
    st.stop()


# ---------------------- FUNÇÕES AUXILIARES ----------------------
PAISES = {
    "🇧🇷 Brasil (+55)": "+55",
    "🇵🇹 Portugal (+351)": "+351",
    "🇺🇸 EUA (+1)": "+1",
    "🇪🇸 Espanha (+34)": "+34",
    "🌍 Outro": ""
}

CARTEIRAS_OPCOES = ["Curto Prazo", "Curtíssimo Prazo", "Opções", "Criptomoedas", "Clube"]
PAGAMENTOS = ["PIX", "PAYPAL", "Infinite"]  # se precisar "Infinitie", troque aqui


def montar_telefone(cod: str, numero: str) -> str:
    numero = numero.strip()
    cod = cod.strip()
    if cod and not numero.startswith(cod):
        return f"{cod} {numero}"
    return numero


from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.mime.text import MIMEText

def enviar_email_boas_vindas(nome: str, email_destino: str) -> tuple[bool, str]:
    if not (EMAIL_USER and EMAIL_PASS and EMAIL_HOST and EMAIL_PORT):
        return False, "Parâmetros de e-mail ausentes. Configure email_sender e gmail_app_password em Secrets."

    corpo = f"""
Olá {nome},

Seja muito bem-vindo(a) à **1 Milhão Invest**! 🎯🚀

Seu cadastro foi realizado com sucesso.

📎 No anexo deste e-mail está o **Contrato de Prestação de Serviços**.

Por favor:

1) Leia com atenção o documento
2) Assine digitalmente ou manualmente
3) Envie a via assinada de volta para este e-mail

Caso tenha dúvidas, nossa equipe está à disposição para ajudar.

Bem-vindo(a) ao próximo nível!

Atenciosamente,  
**Equipe 1 Milhão Invest**
"""

    try:
        # Mensagem com suporte a anexo
        msg = MIMEMultipart()
        msg["Subject"] = "📄 Seu Contrato — 1 Milhão Invest"
        msg["From"] = EMAIL_USER
        msg["To"] = email_destino

        # Corpo do email
        msg.attach(MIMEText(corpo, "plain", "utf-8"))

        # 📎 Anexar PDF
        with open("1milhaoinvest.pdf", "rb") as f:
            part = MIMEApplication(f.read(), _subtype="pdf")
            part.add_header(
                "Content-Disposition",
                "attachment",
                filename="Contrato_1MilhaoInvest.pdf"
            )
            msg.attach(part)

        # SMTP Gmail
        server = smtplib.SMTP(EMAIL_HOST, EMAIL_PORT)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.sendmail(EMAIL_USER, email_destino, msg.as_string())
        server.quit()

        return True, "✅ E-mail com contrato enviado com sucesso!"

    except Exception as e:
        return False, f"❌ Erro ao enviar e-mail: {e}"



def status_cor_data_fim(data_fim: date) -> str:
    """Retorna cor de fundo conforme regra:
       - vermelho: data atual > data_fim
       - amarelo: faltam <= 30 dias para data_fim
       - verde: faltam > 30 dias
    """
    hoje = date.today()
    if data_fim < hoje:
        return "background-color: red"
    dias = (data_fim - hoje).days
    if dias <= 30:
        return "background-color: yellow"
    return "background-color: lightgreen"


# ---------------------- UI: CABEÇALHO ----------------------
st.title("📋 Cadastro de Clientes")
st.caption("CRM simples com Supabase + Streamlit")


# ---------------------- FORMULÁRIO DE CADASTRO ----------------------
with st.expander("➕ Novo cadastro", expanded=True):
    with st.form("form_cadastro", clear_on_submit=True):
        c1, c2 = st.columns([2, 2])
        with c1:
            nome = st.text_input("Nome Completo", placeholder="Ex.: Maria Silva")
        with c2:
            email = st.text_input("Email", placeholder="exemplo@dominio.com")

        c3, c4, c5 = st.columns([1.2, 1.2, 1.6])
        with c3:
            pais_label = st.selectbox("País (bandeira + código)", options=list(PAISES.keys()), index=0)
        with c4:
            numero = st.text_input("Telefone", placeholder="(00) 00000-0000")
        with c5:
            carteiras = st.multiselect("Carteiras", CARTEIRAS_OPCOES, default=[])

        c6, c7, c8 = st.columns([1, 1, 1])
        with c6:
            inicio = st.date_input("Início da Vigência", value=date.today(), format="DD/MM/YYYY")
        with c7:
            fim = st.date_input("Final da Vigência", value=date.today() + timedelta(days=90), format="DD/MM/YYYY")
        with c8:
            pagamento = st.selectbox("Forma de Pagamento", PAGAMENTOS, index=0)

        c9, c10 = st.columns([1, 2])
        with c9:
            valor = st.number_input("Valor líquido", min_value=0.0, step=100.0, format="%.2f")
        with c10:
            observacao = st.text_area("Observação (opcional)", placeholder="Notas internas...")

        salvar = st.form_submit_button("Salvar cadastro", use_container_width=True)

    if salvar:
        telefone = montar_telefone(PAISES.get(pais_label, ""), numero)
        if not nome or not email:
            st.error("Preencha ao menos **Nome Completo** e **Email**.")
        else:
            payload = {
                "nome": nome,
                "telefone": telefone,
                "email": email,
                "carteiras": carteiras,                # text[] no Supabase
                "data_inicio": str(inicio),
                "data_fim": str(fim),
                "pagamento": pagamento,
                "valor": float(valor),
                "observacao": observacao or None,
            }
            try:
                res = supabase.table("clientes").insert(payload).execute()
                st.success("✅ Cliente cadastrado com sucesso!")

                # Guarda último cadastro na sessão para permitir envio de e-mail logo após
                st.session_state.last_cadastro = {"nome": nome, "email": email}
            except Exception as e:
                st.error(f"Erro ao salvar no Supabase: {e}")


# ---------------------- AÇÃO: ENVIAR E-MAIL APÓS CADASTRO (DOIS BOTÕES) ----------------------
if "last_cadastro" in st.session_state and st.session_state.last_cadastro:
    st.info(f"Deseja enviar e-mail de boas-vindas para **{st.session_state.last_cadastro['email']}**?")
    c1, c2 = st.columns([1, 1])
    with c1:
        if st.button("✉️ Enviar e-mail agora", use_container_width=True):
            ok, msg = enviar_email_boas_vindas(
                st.session_state.last_cadastro["nome"],
                st.session_state.last_cadastro["email"],
            )
            if ok:
                st.success(msg)
                st.session_state.last_cadastro = None
            else:
                st.error(msg)
    with c2:
        if st.button("❌ Não enviar", use_container_width=True):
            st.session_state.last_cadastro = None
            st.toast("Cadastro concluído sem envio de e-mail.", icon="✅")


# ---------------------- LISTAGEM / TABELA ----------------------
st.subheader("📊 Clientes cadastrados")

try:
    query = supabase.table("clientes").select("*").order("created_at", desc=True).execute()
    dados = query.data or []
except Exception as e:
    st.error(f"Erro ao buscar dados no Supabase: {e}")
    dados = []

if dados:
    df = pd.DataFrame(dados)

    # Normalizações de colunas esperadas
    # Garante colunas mesmo se a tabela tiver variações
    for col in ["nome", "telefone", "email", "carteiras", "data_inicio", "data_fim", "pagamento", "valor", "observacao"]:
        if col not in df.columns:
            df[col] = None

    # Converte datas
    def parse_data(x):
        if pd.isna(x) or x is None:
            return None
        try:
            # Tenta YYYY-MM-DD
            return pd.to_datetime(x).date()
        except Exception:
            try:
                # Tenta DD/MM/YYYY
                return datetime.strptime(str(x), "%d/%m/%Y").date()
            except Exception:
                return None

    df["data_inicio"] = df["data_inicio"].apply(parse_data)
    df["data_fim"] = df["data_fim"].apply(parse_data)

    # Ordena por data_fim crescente (próximas vigências no topo)
    df = df.sort_values(by=["data_fim"], ascending=[True], na_position="last")

    # Exibe carteiras como string legível
    def carteiras_to_str(v):
        if isinstance(v, list):
            return ", ".join(v)
        return v or ""

    df["carteiras"] = df["carteiras"].apply(carteiras_to_str)

    # Seleção e renome de colunas para visualização
    view_cols = [
        "nome", "email", "telefone", "carteiras",
        "data_inicio", "data_fim", "pagamento", "valor", "observacao"
    ]
    df_view = df[view_cols].copy()
    df_view = df_view.rename(columns={
        "nome": "Nome",
        "email": "Email",
        "telefone": "Telefone",
        "carteiras": "Carteiras",
        "data_inicio": "Início",
        "data_fim": "Fim",
        "pagamento": "Pagamento",
        "valor": "Valor (R$)",
        "observacao": "Observação",
    })

    # Estilo condicional na coluna Fim
    def style_fim(col):
        styles = []
        for v in col:
            if isinstance(v, date):
                styles.append(status_cor_data_fim(v))
            else:
                styles.append("")
        return styles

    styled = df_view.style.apply(style_fim, subset=["Fim"])

    st.dataframe(styled, use_container_width=True)

else:
    st.info("Nenhum cliente cadastrado ainda.")


# ---------------------- RODAPÉ / DICAS ----------------------
with st.expander("ℹ️ Dicas & Próximos passos"):
    st.markdown(
        """
- Para autenticação robusta, podemos migrar para **Supabase Auth**.
- Podemos adicionar **editar/excluir** registros diretamente na tabela.
- Relatórios: exportar para **Excel/PDF** e **gráficos** de vigências.
- Automação: e-mail de **renovação** quando faltar 30, 15 e 7 dias.
- Tema: posso aplicar um **dark theme** igual ao seu dashboard.
        """
    )
