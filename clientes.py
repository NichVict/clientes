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
import re
from supabase import create_client, Client

st.markdown("""
<style>
.card {
    background: #121212; /* fundo dark */
    border: 1px solid rgba(0,255,180,0.25); /* borda verde aqua leve */
    padding: 22px;
    border-radius: 14px;
    text-align: center;
    transition: 0.25s ease;
    box-shadow: 0 0 8px rgba(0,255,180,0.12);
}

.card:hover {
    transform: translateY(-4px);
    box-shadow: 0 0 18px rgba(0,255,200,0.25);
    border-color: rgba(0,255,200,0.45);
}

.card h3 {
    font-size: 34px;
    margin: 0;
    color: #00E6A8; /* verde neon */
    font-weight: 700;
}

.card p {
    margin: 4px 0 0;
    font-size: 15px;
    color: #e0e0e0;
}
</style>
""", unsafe_allow_html=True)



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

CARTEIRAS_OPCOES = ["Curto Prazo", "Curtíssimo Prazo", "Opções", "Criptomoedas", "Clube", "Leads"]
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
LINK_CRIPTO = "https://t.me/+f9Ck6W_Bb00zZDI0"

# Links Google Groups (um por carteira)
LINK_GG_CURTO         = "https://groups.google.com/g/listasemanal"
LINK_GG_CURTISSIMO    = "https://groups.google.com/g/listacurtissimo"
LINK_GG_OPCOES        = "https://groups.google.com/g/lisopcoes"
LINK_GG_CRIPTO        = "https://groups.google.com/g/carteiracriptos"
LINK_GG_CLUBE         = "https://groups.google.com/g/clubenecton"

# Botão sólido (estilo Google) – azul
def BOTAO_GOOGLE(texto: str, link: str) -> str:
    return f'''
<p style="text-align:left;margin:10px 0 18px;">
  <a href="{link}" target="_blank" style="
    border:2px solid #25D366;
    color:#25D366;
    padding:12px 20px;
    border-radius:8px;
    text-decoration:none;
    font-weight:700;
    display:inline-block;">
    {texto}
  </a>
</p>
'''

def BOTAO_TELEGRAM(texto: str, link: str) -> str:
    return f'''
<p style="text-align:left;margin:10px 0 18px;">
  <a href="{link}" target="_blank" style="
    border:2px solid #7D3C98;
    color:#7D3C98;
    padding:12px 20px;
    border-radius:8px;
    text-decoration:none;
    font-weight:700;
    display:inline-block;">
    {texto}
  </a>
</p>
'''


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
<p style="text-align:left;margin:16px 0;">
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

WHATSAPP_BTN = """
<p style="text-align:left;margin-top:18px;">
  <a href="https://wa.me/5511940266027" target="_blank" style="
    background-color:#25D366;
    color:white;
    padding:12px 20px;
    border-radius:8px;
    text-decoration:none;
    font-weight:600;
    display:inline-block;
  ">
    💬 Falar com Suporte
  </a>
</p>
"""


# Textos por carteira (com placeholders {nome}, {inicio}, {fim}) — AGORA SEM BOTÃO ANTIGO DE TELEGRAM
EMAIL_CORPOS = {
    "Curto Prazo": f"""
<h2>👋 Olá {{nome}}!</h2>
<p>Que bom ter você conosco na <b>Carteira Recomendada de Curto Prazo</b>. 🧠📈</p>
<p><b>Vigência do contrato:</b> {{inicio}} a {{fim}}</p>

<h3>✅ Passos iniciais</h3>
<ol>
  <li>Leia o documento em anexo e responda este e-mail com <b>ACEITE</b></li>
  <li>A seguir, valide seu acesso ao grupo do Google e ao grupo do Telegram:</li>
</ol>

{BOTAO_GOOGLE("Entrar no Grupo Google", LINK_GG_CURTO)}

<hr>
<h3>📬 Você receberá toda semana</h3>
<ul>
  <li>Até 5 recomendações de <b>compra</b></li>
  <li>Até 5 recomendações de <b>venda descoberta</b></li>
  <li>Entrada, alvos e stop</li>
  <li>Atualizações diárias das operações abertas</li>
  <li>Alertas automatizados de início e fim de cada operação</li>  
</ul>

{AULAS_TXT_HTML}

<p>Bem-vindo(a) ao próximo nível!<br>Equipe 1 Milhão Invest</p>
{WHATSAPP_BTN}
""",

    "Curtíssimo Prazo": f"""
<h2>⚡ Olá {{nome}}!</h2>
<p>Bem-vindo(a) à <b>Carteira Recomendada de Curtíssimo Prazo</b>.</p>
<p><b>Vigência do contrato:</b> {{inicio}} a {{fim}}</p>

<h3>✅ Passos iniciais</h3>
<ol>
  <li>Leia o documento em anexo e responda este e-mail com <b>ACEITE</b></li>
  <li>A seguir, valide seu acesso ao grupo do Google e ao grupo do Telegram:</li>
</ol>

{BOTAO_GOOGLE("Entrar no Grupo Google", LINK_GG_CURTISSIMO)}

<hr>
<h3>📬 Você receberá toda semana</h3>
<ul>
  <li>Até 5 compras e 5 vendas descoberta</li>
  <li>Estratégias com entrada, alvos e stop</li>
  <li>Alertas automatizados de início e fim de cada operação</li>  
</ul>

{AULAS_TXT_HTML}

<p>Bora buscar performance com agilidade!<br>Equipe 1 Milhão Invest</p>
{WHATSAPP_BTN}
""",

    "Opções": f"""
<h2>🔥 Olá {{nome}}!</h2>
<p>Seja bem-vindo(a) à <b>Carteira Recomendada de Opções</b>.</p>
<p><b>Vigência do contrato:</b> {{inicio}} a {{fim}}</p>

<h3>✅ Passos iniciais</h3>
<ol>
  <li>Leia o documento em anexo e responda este e-mail com <b>ACEITE</b></li>
  <li>A seguir, valide seu acesso ao grupo do Google e ao grupo do Telegram:</li>
</ol>

{BOTAO_GOOGLE("Entrar no Grupo Google", LINK_GG_OPCOES)}

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
{WHATSAPP_BTN}
""",

    "Criptomoedas": f"""
<h2>👋 Olá {{nome}}!</h2>
<p>Bem-vindo(a) à <b>Carteira de Criptomoedas</b>. 🚀</p>
<p><b>Vigência do contrato:</b> {{inicio}} a {{fim}}</p>

<h3>✅ Passos iniciais</h3>
<ol>
  <li>Leia o documento em anexo e responda este e-mail com <b>ACEITE</b></li>
  <li>A seguir, valide seu acesso ao grupo do Google e ao grupo do Telegram:</li>
</ol>

{BOTAO_GOOGLE("Entrar no Grupo Google", LINK_GG_CRIPTO)}

<hr>

{AULAS_TXT_HTML}

<p>Bem-vindo(a) ao universo cripto com inteligência e gestão!<br>Equipe 1 Milhão Invest</p>
{WHATSAPP_BTN}
""",

    "Clube": f"""
<h2>🏆 Olá {{nome}}!</h2>
<p>Bem-vindo(a) ao <b>Clube 1 Milhão Invest</b>.</p>
<p>Nosso contato será personalizado e direto com nossa equipe.</p>

<p>Estamos muito felizes em ter você conosco!</p>
<br><br>

{BOTAO_GOOGLE("Entrar no Grupo Google", LINK_GG_CLUBE)}

<p>Equipe 1 Milhão Invest</p>
{WHATSAPP_BTN}
"""
}



# ---------------------- TEMPLATES DE RENOVAÇÃO ----------------------
# ---------------------- TEMPLATES DE RENOVAÇÃO ----------------------



EMAIL_RENOVACAO_30 = f"""
<h2>⚠️ Sua assinatura está quase vencendo, {{nome}}</h2>

<p>Falta cerca de <b>30 dias</b> para o fim da sua assinatura da carteira <b>{{carteira}}</b>.</p>

<p><b>Período atual:</b> {{inicio}} até {{fim}}</p>

<p>Quer continuar recebendo nossas análises exclusivas e recomendações semanais?</p>

<p>➡️ Responda este e-mail com <b>RENOVAR</b> ou clique abaixo:</p>

{WHATSAPP_BTN}

<p>Equipe 1 Milhão Invest 💚</p>
"""

EMAIL_RENOVACAO_15 = f"""
<h2>📈 Renovação da sua assinatura — {{carteira}}</h2>

<p>Olá {{nome}}, sua assinatura vence em aproximadamente <b>15 dias</b>.</p>

<p>Para manter seu acesso sem interrupções, responda este e-mail com:</p>

<p><b>Quero renovar</b></p>

<p><b>Período atual:</b> {{inicio}} até {{fim}}</p>

{WHATSAPP_BTN}

<p>Estamos juntos 🚀</p>
"""

EMAIL_RENOVACAO_7 = f"""
<h2>⏳ Atenção — sua assinatura expira em breve</h2>

<p>{{nome}}, faltam menos de <b>7 dias</b> para o fim da sua assinatura da carteira <b>{{carteira}}</b>.</p>

<p>Para não perder as operações e análises exclusivas, responda:</p>

<p><b>RENOVAR</b></p>

<p><b>Período atual:</b> {{inicio}} até {{fim}}</p>

{WHATSAPP_BTN}

<p>Obrigado por confiar no nosso trabalho 💪</p>
"""




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
    Mantém o botão original do Google Groups
    e adiciona o botão ESTILIZADO de validação no Telegram logo abaixo.
    """
    resultados = []
    inicio_br = _format_date_br(inicio)
    fim_br = _format_date_br(fim)

    for c in carteiras:
        corpo = EMAIL_CORPOS.get(c, "")
        if not corpo:
            resultados.append((c, False, "Sem template configurado"))
            continue

        # ------------------------------------------
        # 1) Preenche texto do template
        # ------------------------------------------
        corpo = corpo.format(nome=nome, inicio=inicio_br, fim=fim_br)

        # ------------------------------------------
        # 2) Gera link dinâmico do Telegram usando o ID salvo
        # ------------------------------------------
        link_telegram = None
        if st.session_state.get("last_cadastro") and st.session_state.last_cadastro.get("id"):
            cliente_id = st.session_state.last_cadastro["id"]
            link_telegram = f"https://t.me/milhao_crm_bot?start={cliente_id}"

        # ------------------------------------------
        # 3) Monta botão do Telegram estilizado (se houver link)
        # ------------------------------------------
        botao_telegram = ""
        if link_telegram:
            botao_telegram = BOTAO_TELEGRAM("Entrar no Telegram", link_telegram)

        # ------------------------------------------
        # 4) Insere o botão do Telegram LOGO ABAIXO
        #    do botão “Entrar no Grupo Google”
        # ------------------------------------------
        # Inserir o botão do Telegram logo ANTES do <hr>
        anchor = "<hr>"
        if anchor in corpo:
            partes = corpo.split(anchor)
            corpo = partes[0] + botao_telegram + anchor + partes[1]
        else:
            # fallback (caso raro)
            corpo = corpo + botao_telegram


        # ------------------------------------------
        # 5) Envia e-mail
        # ------------------------------------------
        anexar_pdf = (c != "Clube")
        assunto = f"Bem-vindo(a) — {c}"

        ok, msg = _enviar_email(nome, email_destino, assunto, corpo, anexar_pdf)
        resultados.append((c, ok, msg))

    return resultados





def enviar_email_renovacao(nome, email_destino, carteira, inicio, fim, dias):
    inicio_br = _format_date_br(inicio)
    fim_br = _format_date_br(fim)

    # Escolhe qual template usar
    templates = {
        30: EMAIL_RENOVACAO_30,
        15: EMAIL_RENOVACAO_15,
        7: EMAIL_RENOVACAO_7
    }

    corpo = templates[dias].format(
        nome=nome,
        carteira=carteira,
        inicio=inicio_br,
        fim=fim_br
    )

    assunto = f"Renovação — {carteira} ({dias} dias restantes)"

    ok, msg = _enviar_email(
        nome,
        email_destino,
        assunto,
        corpo,
        anexar_pdf=False  # PDF não precisa na renovação
    )

    return ok, msg




# ---------------------- UI: CABEÇALHO ----------------------
st.title("🌀 CRM 1Milhao Invest")
st.markdown("<div style='height:1px;background:linear-gradient(90deg,transparent,rgba(0,255,180,0.35),transparent);'></div>", unsafe_allow_html=True)

st.caption("Customer Relationship Management")

with st.expander("ℹ️ Como funciona este CRM", expanded=False):

    st.markdown("""
    Este CRM foi desenvolvido para facilitar **todo o fluxo de gestão de clientes, leads, assinaturas e comunicação** da 1Milhao Invest.  
    Abaixo está um resumo simples e direto de como tudo funciona:

    ### 🧑‍💻 **1. Cadastro de Leads e Clientes**
    - Você pode cadastrar tanto **Leads** (não compraram ainda) quanto **Clientes** (com carteira ativa).
    - Leads ficam com status **⚪ Lead** e não entram nos KPIs financeiros nem nas métricas de vigência.
    - Clientes possuem vigência, pagamento, valor e uma ou mais carteiras (Curto Prazo, Curtíssimo, Opções, Criptos, Clube).

    ---

    ### ✏️ **2. Edição Completa**
    - Qualquer cliente ou lead pode ser editado a qualquer momento.
    - Após salvar uma edição, você pode **reenviar os e-mails das carteiras** usando o botão de Pack.
    - Conversão de Lead → Cliente é feita **somente alterando a carteira**.

    ---

    ### ✉️ **3. Envio Automático e Manual de E-mails**
    **Envio manual (sempre disponível):**
    - Após criar **ou editar** um cliente, aparece a opção de enviar o **Pack de Boas-Vindas**, contendo:
        - Instruções da carteira  
        - Links do Telegram  
        - Links do Google Groups  
        - Materiais extras (curso, e-book)  
        - Contrato em PDF (exceto Clube)  

    **Envio automático:**
    - O CRM envia avisos automáticos de **renovação** quando faltam:
        - **30 dias**
        - **15 dias**
        - **7 dias**
    - Isso funciona apenas para clientes com vigência ativa.

    ---

    ### 📊 **4. Dashboard / KPIs**
    Os cards mostram automaticamente:
    - **🟢 Clientes Ativos**
    - **🟡 Clientes que vencem em até 30 dias**
    - **🔴 Clientes Vencidos**
    - Leads não entram nessas métricas.

    ---

    ### 🧩 **5. Tabela Completa e Inteligente**
    - Você pode filtrar por:
        - Nome, email, telefone  
        - Carteira  
        - Status de vigência  
    - Cada linha tem status visual:
        - **🟢 > 30 dias**  
        - **🟡 < 30 dias**  
        - **🔴 Vencida**  
        - **⚪ Lead**
    - De cada cliente você pode:
        - Editar  
        - Excluir  
        - Abrir WhatsApp direto por link gerado automaticamente  

    ---

    ### 💰 **6. Relatório de Faturamento**
    - Escolha um período e veja:
        - Todos os clientes vendidos nesse intervalo  
        - Valores individuais  
        - Total do período  
    - Apenas clientes entram no relatório (Leads são ignorados).

    ---

    ### 🤝 **Resumo Geral**
    O CRM cuida de tudo:
    - Cadastro  
    - Edição  
    - Comunicação  
    - Renovação automática  
    - Gestão de carteiras  
    - WhatsApp integrado  
    - Relatório financeiro  

    É sua central completa para gestão de toda a operação comercial e recorrência.
    """)

# ---------------------- DASHBOARD / KPIs ----------------------
try:
    query = supabase.table("clientes").select("*").execute()
    dados_kpi = query.data or []
    df_kpi = pd.DataFrame(dados_kpi)

    if not df_kpi.empty:
        df_kpi["data_fim"] = pd.to_datetime(df_kpi["data_fim"], errors="coerce").dt.date

        today = date.today()
        ativos = df_kpi[df_kpi["data_fim"] >= today]
        vencendo = df_kpi[(df_kpi["data_fim"] >= today) & (df_kpi["data_fim"] <= today + timedelta(days=30))]
        vencidos = df_kpi[df_kpi["data_fim"] < today]

        c1, c2, c3 = st.columns(3)
        
        with c1:
            st.markdown(f"<div class='card'><h3>🟢 {len(ativos)}</h3><p>Clientes Ativos</p></div>", unsafe_allow_html=True)
        
        with c2:
            st.markdown(f"<div class='card'><h3>🟡 {len(vencendo)}</h3><p>≤ 30 dias para vencer</p></div>", unsafe_allow_html=True)
        
        with c3:
            st.markdown(f"<div class='card'><h3>🔴 {len(vencidos)}</h3><p>Vencidos</p></div>", unsafe_allow_html=True)
 

     


except Exception as e:
    st.error(f"Erro ao carregar KPIs: {e}")

st.markdown("<br><br>", unsafe_allow_html=True)

st.markdown("<div style='height:1px;background:linear-gradient(90deg,transparent,rgba(0,255,180,0.35),transparent);'></div>", unsafe_allow_html=True)


# ---------------------- FORMULÁRIO DE CADASTRO ----------------------
# ---------------------- FORMULÁRIO DE CADASTRO ----------------------
st.markdown("<br><br>", unsafe_allow_html=True)
st.subheader("🆕 Cadastro e Edição de Clientes")
st.markdown("<br>", unsafe_allow_html=True)

is_edit = st.session_state.get("edit_mode", False)
edit_data = st.session_state.get("edit_data") or {}

with st.expander("Formulário", expanded=is_edit):
    with st.form("form_cadastro", clear_on_submit=not is_edit):

        c1, c2 = st.columns([2, 2])
        with c1:
            nome = st.text_input("Nome Completo", value=edit_data.get("nome", ""), placeholder="Ex.: Maria Silva")
        with c2:
            email = st.text_input("Email", value=edit_data.get("email", ""), placeholder="exemplo@dominio.com")

        c3, c4, c5 = st.columns([1.2, 1.2, 1.6])
        with c3:
            pais_label = st.selectbox("País (bandeira + código)", options=list(PAISES.keys()), index=0)
        with c4:
            numero = st.text_input("Telefone", value=edit_data.get("telefone", ""), placeholder="(00) 00000-0000")
        with c5:                       
            # tratar carteiras para o multiselect
            # --- trata carteiras para o multiselect ---
            raw_carteiras = edit_data.get("carteiras", [])
            
            if isinstance(raw_carteiras, list):
                carteiras_val = raw_carteiras
            
            elif isinstance(raw_carteiras, str):
                if raw_carteiras.strip() == "":
                    carteiras_val = []
                else:
                    parts = [p.strip() for p in raw_carteiras.replace("[","").replace("]","").replace("'","").split(",")]
                    carteiras_val = [p for p in parts if p != ""]
            
            elif raw_carteiras is None:
                carteiras_val = []
            
            else:
                carteiras_val = [str(raw_carteiras)]
            
            # garante que só valores válidos entrem
            carteiras_val = [c for c in carteiras_val if c in CARTEIRAS_OPCOES]
            
            carteiras = st.multiselect("Carteiras", CARTEIRAS_OPCOES, default=carteiras_val)






        c6, c7, c8 = st.columns([1, 1, 1])
        with c6:
            inicio = st.date_input("Início da Vigência", value=edit_data.get("data_inicio", date.today()), format="DD/MM/YYYY")
        with c7:
            fim = st.date_input("Final da Vigência", value=edit_data.get("data_fim", date.today() + timedelta(days=180)), format="DD/MM/YYYY")
        with c8:
            pagamento = st.selectbox(
                "Forma de Pagamento",
                PAGAMENTOS,
                index=(PAGAMENTOS.index(edit_data["pagamento"]) if is_edit else 0)
            )

        c9, c10 = st.columns([1, 2])
        with c9:
            valor = st.number_input("Valor líquido", min_value=0.0, value=float(edit_data.get("valor", 0)), step=100.0, format="%.2f")
        with c10:
            observacao = st.text_area("Observação (opcional)", value=edit_data.get("observacao", ""), placeholder="Notas internas...")

        salvar = st.form_submit_button("Salvar", use_container_width=True)

    if salvar:
        telefone = montar_telefone(PAISES.get(pais_label, ""), numero)
        if not nome or not email:
            st.error("Preencha ao menos **Nome Completo** e **Email**.")
        else:
            payload = {
                "nome": nome,
                "telefone": telefone,
                "email": email,
                "carteiras": list(carteiras) if carteiras else [],
                "data_inicio": str(inicio),
                "data_fim": str(fim),
                "pagamento": pagamento,
                "valor": float(valor),
                "observacao": observacao or None,
            }

            # Se estiver editando → UPDATE
            if is_edit:
                try:
                    edit_id = str(st.session_state.get("selected_client_id"))
            
                    # 🔄 Atualiza cliente no Supabase
                    response = (
                        supabase.table("clientes")
                        .update(payload)
                        .eq("id", edit_id)
                        .execute()
                    )
                    
                    telegram_link = f"https://t.me/milhao_crm_bot?start={edit_id}"
                    
                    st.session_state.last_cadastro = {
                        "id": edit_id,
                        "nome": nome,
                        "email": email,
                        "carteiras": payload.get("carteiras", []),
                        "inicio": inicio,
                        "fim": fim,
                        "telegram_link": telegram_link
                    }
                    
                    st.success("✅ Cliente atualizado com sucesso!")
                    st.session_state["edit_mode"] = False
                    st.session_state["edit_id"] = None
                    st.session_state["edit_data"] = None
                    st.session_state["selected_client_id"] = None
                    
                    st.rerun()

            
                except Exception as e:
                    st.error(f"Erro ao atualizar: {e}")          
                    
            



            # Se for novo → INSERT
            else:
                try:
                    # 🔄 Salva no Supabase
                    res = supabase.table("clientes").insert(payload).execute()
                    
                    # 📌 Captura o ID recém inserido
                    cliente_id = res.data[0]["id"]
                    
                    # 🔗 Gera link do bot
                    telegram_link = f"https://t.me/milhao_crm_bot?start={cliente_id}"
                    
                    st.success("✅ Cliente cadastrado com sucesso!")
                    
                    # Guarda no estado para enviar email depois
                    st.session_state.last_cadastro = {
                        "id": cliente_id,
                        "nome": nome,
                        "email": email,
                        "carteiras": list(carteiras) if carteiras else [],
                        "inicio": inicio,
                        "fim": fim,
                        "telegram_link": telegram_link
                    }



                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao salvar no Supabase: {e}")


# ---------------------- AÇÃO: ENVIAR E-MAIL APÓS CADASTRO (DOIS BOTÕES) ----------------------
if "last_cadastro" in st.session_state and st.session_state.last_cadastro:
    lc = st.session_state.last_cadastro
    lista = ", ".join(lc.get("carteiras", [])) if lc.get("carteiras") else "Nenhuma carteira selecionada"
    st.info(f"Enviar e-mail de boas-vindas para **{lc['email']}** — carteiras: **{lista}**?")
    c1, c2 = st.columns([1, 1])
    with c1:
        if st.button("✉️ Enviar e-mails com Pack boas vindas", use_container_width=True):
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
        if st.button("❌ Não enviar e-mails", use_container_width=True):
            st.session_state.last_cadastro = None
            st.toast("Cadastro concluído sem envio de e-mails.", icon="✅")




# ---------------------- LISTAGEM / TABELA ----------------------
# ---------------------- LISTAGEM / TABELA ----------------------
st.markdown("<br><br>", unsafe_allow_html=True)

st.markdown("<div style='height:1px;background:linear-gradient(90deg,transparent,rgba(0,255,180,0.35),transparent);'></div>", unsafe_allow_html=True)

st.markdown("<br><br>", unsafe_allow_html=True)
st.subheader("🧑‍🤝‍🧑 Clientes Cadastrados")
st.markdown("<br>", unsafe_allow_html=True)

# 1️⃣ Buscar dados
try:
    query = (
        supabase
        .table("clientes")
        .select("*")
        .order("created_at", desc=True)
        .execute()
    )
    dados = query.data or []
except Exception as e:
    st.error(f"Erro ao buscar dados no Supabase: {e}")
    dados = []

# 2️⃣ Disparador automático de avisos de renovação
from datetime import date

# Disparador automático de avisos de renovação
for cli in dados:
    try:
        fim = pd.to_datetime(cli["data_fim"]).date()
    except:
        continue

    today = date.today()
    dias = (fim - today).days

    avisos = {30: "aviso_30", 15: "aviso_15", 7: "aviso_7"}

    if dias in avisos:
        campo = avisos[dias]

        if not cli.get(campo, False):
            carteiras = cli.get("carteiras", [])
            if isinstance(carteiras, str):
                carteiras = [x.strip() for x in carteiras.split(",")]

            for cart in carteiras:
                enviar_email_renovacao(
                    nome=cli["nome"],
                    email_destino=cli["email"],
                    carteira=cart,
                    inicio=cli["data_inicio"],
                    fim=cli["data_fim"],
                    dias=dias
                )

            supabase.table("clientes").update({campo: True}).eq("id", cli["id"]).execute()

            st.toast(f"📬 E-mail de renovação enviado ({dias} dias) — {cli['nome']}", icon="✅")




# ---------------------- FILTROS AVANÇADOS ----------------------
# ---------------------- FILTROS AVANÇADOS ----------------------
# ---------------------- FILTROS AVANÇADOS ----------------------

# 4️⃣ Renderização da tabela
if dados:
    df = pd.DataFrame(dados)
    df["id"] = df["id"].astype(str)

    # 🔧 Ajusta campos obrigatórios
    for col in ["nome","telefone","email","carteiras","data_inicio","data_fim","pagamento","valor","observacao","id"]:
        if col not in df.columns:
            df[col] = None
    
    # Converte datas antes dos filtros
    df["data_inicio"] = pd.to_datetime(df["data_inicio"], errors="coerce").dt.date
    df["data_fim"] = pd.to_datetime(df["data_fim"], errors="coerce").dt.date
    
    # ---------------------- FILTROS AVANÇADOS ----------------------
    with st.expander("⚙️ Filtros Avançados"):
    
        search = st.text_input("Buscar cliente por nome, email ou telefone:")
    
        filtro_carteira = st.multiselect(
            "Carteiras",
            CARTEIRAS_OPCOES,
            default=[]
        )
    
        status_opcoes = ["🟢 Ativos", "🟡 Vencendo (≤ 30 dias)", "🔴 Vencidos"]
        filtro_status = st.multiselect(
            "Status da Vigência",
            status_opcoes,
            default=[]
        )
    
    # 🔎 Busca texto
    if search:
        df = df[
            df["nome"].fillna("").str.contains(search, case=False, na=False) |
            df["email"].fillna("").str.contains(search, case=False, na=False) |
            df["telefone"].fillna("").str.contains(search, case=False, na=False)
        ]
    
    # 📂 Filtro carteira
    if filtro_carteira:
        df = df[df["carteiras"].apply(
            lambda x: any(c in x for c in filtro_carteira) if isinstance(x, list) else False
        )]
    
    # 🟢🟡🔴 Filtro vigência
    if filtro_status:
        hoje = date.today()
        def status_calc(d):
            if d < hoje: 
                return "🔴 Vencidos"
            dias = (d - hoje).days
            return "🟡 Vencendo (≤ 30 dias)" if dias <= 30 else "🟢 Ativos"
    
        df = df[df["data_fim"].apply(status_calc).isin(filtro_status)]
    
    # Ordenação final por data fim
    df = df.sort_values(by="data_fim", ascending=True)
    
    # Formata carteiras p/ tabela
    df["carteiras"] = df["carteiras"].apply(
        lambda v: ", ".join(v) if isinstance(v, list) else (v or "")
    )



    def carteiras_to_str(v):
        return ", ".join(v) if isinstance(v, list) else (v or "")

    df["carteiras"] = df["carteiras"].apply(carteiras_to_str)

    # Criar DataFrame da tabela
    df_view = pd.DataFrame({
        "ID": df["id"],
        "Nome": df["nome"],
        "Email": df["email"],
        "Telefone": df["telefone"],
        "Carteiras": df["carteiras"],
        "Início": df["data_inicio"],
        "Fim": df["data_fim"],
        "Pagamento": df["pagamento"],
        "Valor (R$)": df["valor"],
        "Observação": df["observacao"],
    })
    
    # Status Vigência
    def status_vigencia(data_fim, carteiras=None):        
        # Leads sempre ficam com bolinha branca
        if carteiras and "Leads" in carteiras:
            return "⚪ Lead"
    
        hoje = date.today()
    
        if isinstance(data_fim, date):
            if data_fim < hoje:
                return "🔴 Vencida"
            dias = (data_fim - hoje).days
            return "🟡 < 30 dias" if dias <= 30 else "🟢 > 30 dias"
    
        return ""

    
    df_view["Status Vigência"] = df_view.apply(
        lambda r: status_vigencia(
            r["Fim"],
            r["Carteiras"].split(", ") if isinstance(r["Carteiras"], str) else []
        ),
        axis=1
    )


    
    # Adiciona coluna Selecionar primeiro
    df_view.insert(0, "Selecionar", False)
    
    # Move "Status Vigência" para ser segunda coluna
    status_col = df_view.pop("Status Vigência")
    df_view.insert(1, "Status Vigência", status_col)


    edited = st.data_editor(
        df_view,
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        column_config={
            "Selecionar": st.column_config.CheckboxColumn("Selecionar", default=False),
            "ID": st.column_config.TextColumn("ID", disabled=True, width=1),
            "Início": st.column_config.DateColumn("Início", disabled=True),
            "Fim": st.column_config.DateColumn("Fim", disabled=True),
            "Valor (R$)": st.column_config.NumberColumn("Valor (R$)", format="%.2f", disabled=True),
            "Status Vigência": st.column_config.TextColumn("Status Vigência", disabled=True),
        },
        disabled=["ID","Nome","Email","Telefone","Carteiras","Início","Fim","Pagamento","Valor (R$)","Observação","Status Vigência"],
    )

    selected_rows = edited[edited["Selecionar"]]
    if len(selected_rows) > 0:
        sel = selected_rows.iloc[0]
        selected_id = str(sel["ID"])
        st.session_state["selected_client_id"] = selected_id

        colE, colM, colD = st.columns(3)
        
        with colE:
            if st.button("📝 Editar cliente"):
                df["id"] = df["id"].astype(str)
                cliente = df[df["id"] == selected_id].iloc[0]
        
                st.session_state["edit_mode"] = True
                st.session_state["edit_data"] = cliente.to_dict()
                st.rerun()
        
        with colM:            
            telefone = sel["Telefone"]
        
            if telefone:
                # Mantém apenas + e dígitos
                telefone_clean = "".join([c for c in str(telefone) if c.isdigit() or c == "+"])
        
                # Se não tiver +, adiciona um (pois banco já tem prefixo do país)
                if not telefone_clean.startswith("+"):
                    telefone_clean = "+" + telefone_clean
        
                # Remove qualquer símbolo extra
                telefone_clean = telefone_clean.replace(" ", "").replace("-", "")
        
                msg = f"Olá {sel['Nome']}, tudo bem? 😊"
                msg_encoded = msg.replace(" ", "%20")
        
                link = f"https://api.whatsapp.com/send?phone={telefone_clean}&text={msg_encoded}"
        
                st.link_button("💬 Conversar por WhatsApp", link)
            else:
                st.info("📱 Sem telefone cadastrado")


        
        with colD:
            if st.button("🗑 Excluir cliente"):
                st.session_state["confirm_delete"] = True
                st.session_state["delete_id"] = selected_id
                st.rerun()


    if st.session_state.get("confirm_delete", False):
        st.warning("⚠️ Tem certeza que deseja excluir este cliente? Esta ação não pode ser desfeita.")

        c1, c2 = st.columns(2)

        with c1:
            if st.button("✅ Confirmar exclusão"):
                supabase.table("clientes").delete().eq("id", st.session_state["delete_id"]).execute()
                st.toast("✅ Cliente excluído", icon="🗑")
                st.session_state["confirm_delete"] = False
                st.session_state["selected_client_id"] = None
                st.rerun()

        with c2:
            if st.button("❌ Cancelar"):
                st.session_state["confirm_delete"] = False
                st.session_state["delete_id"] = None
                st.rerun()


    # ===================== RELATÓRIO DE VENDAS NO PERÍODO =====================
    with st.expander("📊 Relatório de Vendas / Assinaturas no Período"):
        c1, c2 = st.columns(2)
        dt_inicio = c1.date_input("Data inicial", value=date.today().replace(day=1))
        dt_fim = c2.date_input("Data final", value=date.today())

        df_rel = df[
            (df["data_inicio"] >= dt_inicio) &
            (df["data_inicio"] <= dt_fim)
        ].copy()

        st.write(f"🔎 Registros encontrados: **{len(df_rel)}**")

        df_rel["valor"] = pd.to_numeric(df_rel["valor"], errors="coerce").fillna(0)
        total = df_rel["valor"].sum()

        st.dataframe(df_rel[["nome","email","carteiras","data_inicio","data_fim","valor"]], use_container_width=True)

        st.markdown(f"### 💰 Total no período: **R$ {total:,.2f}**")






