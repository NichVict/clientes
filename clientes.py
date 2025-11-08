# clientes.py
# ------------------------------------------------------------
# App Streamlit para cadastro de clientes com Supabase
# - Login simples (usuario/senha fixos)
# - Formulário de cadastro
# - Gravação e leitura no Supabase
# - Tabela com destaque de cor pela data de fim da vigência
# - Envio de e-mails por carteira (texto e links personalizados)
# - PDF anexo para todas as carteiras EXCETO Clube
#
# Requer no Streamlit Cloud (Settings -> Secrets):
#   SUPABASE_URL
#   SUPABASE_KEY
#   email_sender
#   gmail_app_password
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

# Seu padrão de e-mail (iguais aos outros apps)
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

# ---------------------- LINKS E TEMPLATES DE E-MAIL ----------------------
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.mime.text import MIMEText

# Links Telegram
LINK_CURTO = "https://t.me/+3BTqTX--W6gyNTE0"
LINK_CURTISSIMO = "https://t.me/+BiTfqYUSiWpjN2U0"
LINK_OPCOES = "https://t.me/+1si_16NC5E8xNDhk"
LINK_CRIPTO = LINK_CURTO  # por enquanto, mesmo do Curto

# Aulas bônus (links limpos e clicáveis)
AULAS_TXT_HTML = (
    '<h3>📚 Bônus — Curso Completo (5 aulas)</h3>'
    '<p>'
    '<a href="https://youtu.be/usGS5KpBPcA">Aula 1</a><br>'
    '<a href="https://youtu.be/mtY0qY1zZN4">Aula 2</a><br>'
    '<a href="https://youtu.be/2aHj8LSGrV8">Aula 3</a><br>'
    '<a href="https://youtu.be/0QOtVHX1n-4">Aula 4</a><br>'
    '<a href="https://youtu.be/pzK8dnK6jsk">Aula 5</a>'
    '</p>'
)

# Botão estilo B (outline)
def BOTAO_OUTLINE(texto: str, link: str) -> str:
    return f'''
<p style="text-align:center;margin:16px 0;">
  <a href="{link}" target="_blank" style="
    border:2px solid #0169FF;
    color:#0169FF;
    padding:12px 20px;
    border-radius:8px;
    text-decoration:none;
    font-weight:700;
    display:inline-block;">
    {texto}
  </a>
</p>
'''

# E-book Opções
EBOOK_OPCOES_HTML = (
    '<h3>📘 Material Exclusivo</h3>'
    '<p><a href="https://drive.google.com/file/d/1U3DBmTbbjiq34tTQdvHcxi2MnZnd8owN/view">Baixar E-book de Opções</a></p>'
)

# Textos por carteira (com placeholders {nome}, {inicio}, {fim}) — agora em HTML com botões
EMAIL_CORPOS = {
    "Curto Prazo": f"""
<h2>👋 Olá {{nome}}!</h2>
<p>Que bom ter você conosco na <b>Carteira Recomendada de Curto Prazo</b>. 🧠📈</p>
<p><b>Vigência do contrato:</b> {{inicio}} a {{fim}}</p>

<h3>✅ Passos iniciais</h3>
<ol>
  <li>Leia o documento em anexo e responda este e-mail com <b>ACEITE</b></li>
  <li>Entre no grupo exclusivo do Telegram:</li>
</ol>
{BOTAO_OUTLINE("Entrar no Grupo do Telegram", LINK_CURTO)}
<p>3) Libere o e-mail: <b>avisoscanal1milhao@gmail.com</b></p>

<hr>
<h3>📬 Você receberá toda semana</h3>
<ul>
  <li>Até 5 recomendações de <b>compra</b></li>
  <li>Até 5 recomendações de <b>venda descoberta</b></li>
  <li>Entrada, alvos e stop</li>
  <li>Atualizações diárias das operações abertas</li>
  <li>Avisos automáticos de início e fim</li>
  <li>Vídeo semanal explicando o racional</li>
</ul>

{AULAS_TXT_HTML}

<p>Bem-vindo(a) ao próximo nível!<br>Equipe 1 Milhão Invest</p>
""",

    "Curtíssimo Prazo": f"""
<h2>⚡ Olá {{nome}}!</h2>
<p>Bem-vindo(a) à <b>Carteira Recomendada de Curtíssimo Prazo</b>.</p>
<p><b>Vigência do contrato:</b> {{inicio}} a {{fim}}</p>

<h3>✅ Passos iniciais</h3>
<ol>
  <li>Leia o documento em anexo e responda este e-mail com <b>ACEITE</b></li>
  <li>Entre no grupo exclusivo do Telegram:</li>
</ol>
{BOTAO_OUTLINE("Entrar no Grupo do Telegram", LINK_CURTISSIMO)}
<p>3) Libere o e-mail: <b>avisoscanal1milhao@gmail.com</b></p>

<hr>
<h3>📬 Você receberá toda semana</h3>
<ul>
  <li>Até 5 compras e 5 vendas descoberta</li>
  <li>Estratégias com entrada, alvos e stop</li>
  <li>Alertas automatizados</li>
  <li>Relatórios com racional</li>
</ul>

{AULAS_TXT_HTML}

<p>Bora buscar performance com agilidade!<br>Equipe 1 Milhão Invest</p>
""",

    "Opções": f"""
<h2>🔥 Olá {{nome}}!</h2>
<p>Seja bem-vindo(a) à <b>Carteira Recomendada de Opções</b>.</p>
<p><b>Vigência do contrato:</b> {{inicio}} a {{fim}}</p>

<h3>✅ Passos iniciais</h3>
<ol>
  <li>Leia o documento em anexo e responda este e-mail com <b>ACEITE</b></li>
  <li>Entre no grupo exclusivo do Telegram:</li>
</ol>
{BOTAO_OUTLINE("Entrar no Grupo do Telegram", LINK_OPCOES)}
<p>3) Libere o e-mail: <b>opcoes.1milhao.invest@gmail.com</b></p>

<hr>
<h3>📈 Você terá</h3>
<ul>
  <li>Mínimo de 8 operações por mês (média 2/semana)</li>
  <li>Alertas com ticker, strike, vencimento e preço</li>
  <li>Atualizações semanais das operações</li>
  <li>Relatório de rentabilidade</li>
</ul>
<p><i>Por ser um mercado mais volátil, acompanhe os avisos para não perder o timing.</i></p>

{AULAS_TXT_HTML}
{EBOOK_OPCOES_HTML}

<p>Vamos operar com estratégia e controle!<br>Equipe 1 Milhão Invest</p>
""",

    # Criptomoedas usa o mesmo corpo do Curto Prazo (links e tudo)
    "Criptomoedas": "<<USE_CURTO>>",

    # Clube: sem PDF, sem link
    "Clube": """
<h2>🏆 Olá {nome}!</h2>
<p>Bem-vindo(a) ao <b>Clube 1 Milhão Invest</b>.</p>
<p>Nossa equipe fará contato exclusivo com você para os próximos passos.</p>
<p>Conte conosco!<br>Equipe 1 Milhão Invest</p>
"""
}

def _format_date_br(d: date) -> str:
    try:
        return d.strftime("%d/%m/%Y")
    except Exception:
        # caso venha string
        try:
            return pd.to_datetime(d).strftime("%d/%m/%Y")
        except Exception:
            return str(d)

def _enviar_email(nome: str, email_destino: str, assunto: str, corpo: str, anexar_pdf: bool) -> tuple[bool, str]:
    try:
        msg = MIMEMultipart()
        msg["Subject"] = assunto
        msg["From"] = EMAIL_USER
        msg["To"] = email_destino

        # HTML no corpo do e-mail
        msg.attach(MIMEText(corpo, "html", "utf-8"))

        if anexar_pdf:
            # anexa contrato padrão
            with open("1milhaoinvest.pdf", "rb") as f:
                part = MIMEApplication(f.read(), _subtype="pdf")
                part.add_header("Content-Disposition", "attachment", filename="Contrato_1MilhaoInvest.pdf")
                msg.attach(part)

        server = smtplib.SMTP(EMAIL_HOST, EMAIL_PORT)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.sendmail(EMAIL_USER, [email_destino], msg.as_string())
        server.quit()
        return True, "OK"
    except Exception as e:
        return False, f"{e}"

def enviar_emails_por_carteira(nome: str, email_destino: str, carteiras: list, inicio: date, fim: date) -> list[tuple[str, bool, str]]:
    """
    Envia 1 e-mail por carteira.
    Retorna lista de (carteira, sucesso, mensagem)
    """
    resultados = []
    inicio_br = _format_date_br(inicio)
    fim_br = _format_date_br(fim)

    for c in carteiras:
        corpo = EMAIL_CORPOS.get(c, "")
        if c == "Criptomoedas":
            # Usa corpo do Curto Prazo
            corpo = EMAIL_CORPOS["Curto Prazo"]
        if not corpo:
            resultados.append((c, False, "Sem template configurado"))
            continue

        corpo = corpo.format(nome=nome, inicio=inicio_br, fim=fim_br)

        anexar_pdf = (c != "Clube")
        assunto = f"Bem-vindo(a) — {c}"

        ok, msg = _enviar_email(nome, email_destino, assunto, corpo, anexar_pdf)
        resultados.append((c, ok, msg))
    return resultados

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
                supabase.table("clientes").insert(payload).execute()
                st.success("✅ Cliente cadastrado com sucesso!")

                # Guarda dados do cadastro para envio de e-mails por carteira
                st.session_state.last_cadastro = {
                    "nome": nome,
                    "email": email,
                    "carteiras": carteiras,
                    "inicio": inicio,
                    "fim": fim
                }
            except Exception as e:
                st.error(f"Erro ao salvar no Supabase: {e}")

# ---------------------- AÇÃO: ENVIAR E-MAIL APÓS CADASTRO (DOIS BOTÕES) ----------------------
if "last_cadastro" in st.session_state and st.session_state.last_cadastro:
    lc = st.session_state.last_cadastro
    lista = ", ".join(lc.get("carteiras", [])) if lc.get("carteiras") else "Nenhuma carteira selecionada"
    st.info(f"Enviar e-mail de boas-vindas para **{lc['email']}** — carteiras: **{lista}**?")
    c1, c2 = st.columns([1, 1])
    with c1:
        if st.button("✉️ Enviar e-mails agora", use_container_width=True):
            if not lc.get("carteiras"):
                st.warning("Nenhuma carteira selecionada. Nada foi enviado.")
            else:
                resultados = enviar_emails_por_carteira(
                    nome=lc["nome"],
                    email_destino=lc["email"],
                    carteiras=lc["carteiras"],
                    inicio=lc["inicio"],
                    fim=lc["fim"]
                )
                # Feedback por carteira
                ok_all = True
                for carteira, ok, msg in resultados:
                    if ok:
                        st.success(f"✅ {carteira}: enviado")
                    else:
                        ok_all = False
                        st.error(f"❌ {carteira}: falhou — {msg}")
                if ok_all:
                    st.toast("Todos os e-mails foram enviados com sucesso.", icon="✅")
            st.session_state.last_cadastro = None
    with c2:
        if st.button("❌ Não enviar", use_container_width=True):
            st.session_state.last_cadastro = None
            st.toast("Cadastro concluído sem envio de e-mails.", icon="✅")


# ---------------------- CAMPO DE BUSCA ----------------------
search = st.text_input("🔎 Buscar cliente por nome, email ou telefone:")


# ---------------------- LISTAGEM / TABELA ----------------------
st.subheader("📊 Clientes cadastrados")

try:
    query = supabase.table("clientes").select("*").order("created_at", desc=True).execute()
    dados = query.data or []
except Exception as e:
    st.error(f"Erro ao buscar dados no Supabase: {e}")
    dados = []
# ---------------------- CAMPO DE BUSCA ----------------------
if dados:
    df = pd.DataFrame(dados)

    # Normalizações de colunas esperadas
    for col in ["nome", "telefone", "email", "carteiras", "data_inicio", "data_fim", "pagamento", "valor", "observacao"]:
        if col not in df.columns:
            df[col] = None

        # --- Filtro de busca (após normalizar colunas) ---
    if search:
        # garante as colunas para o filtro
        for col in ["nome", "email", "telefone"]:
            if col not in df.columns:
                df[col] = ""
        mask = (
            df["nome"].fillna("").str.contains(search, case=False, na=False) |
            df["email"].fillna("").str.contains(search, case=False, na=False) |
            df["telefone"].fillna("").str.contains(search, case=False, na=False)
        )
        df = df[mask].copy()


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
