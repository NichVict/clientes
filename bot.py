
import os
import time
import requests
from datetime import datetime

# ============================================================
# CONFIGURAÇÕES
# ============================================================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")          # coloque no Render
SUPABASE_URL   = os.getenv("SUPABASE_URL")            # coloque no Render
SUPABASE_KEY   = os.getenv("SUPABASE_KEY")            # coloque no Render

# IDs dos grupos — você já me passou# -*- coding: utf-8 -*-
"""
Bot Oficial CRM — Projeto Phoenix (milhao_crm_bot)

Funções principais:
- /start <cliente_id> → mostra botão VALIDAR ACESSO
- Callback VALIDAR → valida cliente, salva dados do Telegram e envia links de carteiras
- Rotina periódica → remove assinaturas vencidas dos grupos (quando configurados)
"""

import os
import time
import requests
from datetime import datetime, date

# ============================================================
# CONFIGURAÇÕES GERAIS
# ============================================================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")          # token do milhao_crm_bot
SUPABASE_URL   = os.getenv("SUPABASE_URL")            # URL Supabase
SUPABASE_KEY   = os.getenv("SUPABASE_KEY")            # KEY Supabase

if not TELEGRAM_TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN não definido no ambiente.")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL ou SUPABASE_KEY não definidos.")

BASE_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# Grupos oficiais Phoenix v2 (links de convite)
GRUPOS = {
    "Carteira de Ações IBOV": "https://t.me/+Rkvw9CfJBkowMTg0",
    "Carteira de BDRs": "https://t.me/+-Io0aAFaGJ0yN2Rk",
    "Carteira de Opções": "https://t.me/+3YzTJqBi-xYxNjNk",
    "Carteira Small Caps": "https://t.me/+2UD3b1xLWvU0NDFk",
}

# CHAT_ID dos grupos (para expulsar usuários vencidos)
# ⚠️ PREENCHA COM OS IDs REAIS DOS GRUPOS ANTES DE SUBIR EM PRODUÇÃO.
GROUP_CHAT_IDS = {
    "Carteira de Ações IBOV": None,   # ex: -1001234567890
    "Carteira de BDRs": None,
    "Carteira de Opções": None,
    "Carteira Small Caps": None,
}

# ============================================================
# FUNÇÕES DE SUPABASE (REST)
# ============================================================

def supabase_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


def supabase_get_client(cliente_id):
    """Busca cliente no Supabase pelo ID."""
    url = f"{SUPABASE_URL}/rest/v1/clientes?id=eq.{cliente_id}"
    r = requests.get(url, headers=supabase_headers(), timeout=15)
    try:
        data = r.json()
        if isinstance(data, list) and data:
            return data[0]
        return None
    except Exception:
        return None


def supabase_update_client(cliente_id, payload: dict):
    """Atualiza campos de um cliente no Supabase."""
    url = f"{SUPABASE_URL}/rest/v1/clientes?id=eq.{cliente_id}"
    r = requests.patch(url, headers=supabase_headers(), json=payload, timeout=15)
    try:
        r.raise_for_status()
        return True
    except Exception:
        print("Erro ao atualizar cliente:", r.text)
        return False


def supabase_list_clients_for_cleanup():
    """
    Busca todos clientes que podem entrar na rotina de remoção.
    Filtra depois em Python.
    """
    url = f"{SUPABASE_URL}/rest/v1/clientes"
    params = {
        "select": "id,nome,carteiras,data_fim,telegram_id,telegram_username,telegram_connected,telegram_removed_at"
    }
    r = requests.get(url, headers=supabase_headers(), params=params, timeout=20)
    try:
        data = r.json()
        if isinstance(data, list):
            return data
        return []
    except Exception:
        return []


# ============================================================
# FUNÇÕES TELEGRAM
# ============================================================

def tg_get_updates(offset=None):
    """Busca mensagens novas do Telegram."""
    url = BASE_API + "/getUpdates"
    if offset:
        url += f"?offset={offset}"
    try:
        return requests.get(url, timeout=30).json()
    except Exception as e:
        print("Erro em getUpdates:", e)
        return {"result": []}


def tg_send_message(chat_id, text, reply_markup=None):
    """Envia mensagem simples com parse_mode HTML."""
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        requests.post(BASE_API + "/sendMessage", json=payload, timeout=15)
    except Exception as e:
        print("Erro sendMessage:", e)


def tg_kick_user(group_id, user_id):
    """Expulsa usuário do grupo (remoção de vencidos)."""
    if group_id is None:
        return False
    url = BASE_API + "/kickChatMember"  # ou banChatMember em bots mais novos
    payload = {"chat_id": group_id, "user_id": user_id}
    try:
        resp = requests.post(url, json=payload, timeout=15)
        ok = resp.json().get("ok", False)
        if not ok:
            print("Erro kickChatMember:", resp.text)
        return ok
    except Exception as e:
        print("Erro kickChatMember:", e)
        return False


# ============================================================
# PROCESSAMENTO DO /start
# ============================================================

def process_start(message):
    chat_id = message["chat"]["id"]
    text = message.get("text", "")

    parts = text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        tg_send_message(
            chat_id,
            "❌ Link inválido ou expirado.\n"
            "Peça um novo link de acesso ao suporte."
        )
        return

    cliente_id = parts[1]
    cliente = supabase_get_client(cliente_id)
    if not cliente:
        tg_send_message(chat_id, "❌ Cliente não encontrado.\nPeça um novo link ao suporte.")
        return

    nome = cliente.get("nome", "Cliente")

    teclado = {
        "inline_keyboard": [
            [
                {
                    "text": "🔓 VALIDAR ACESSO",
                    "callback_data": f"validar:{cliente_id}"
                }
            ]
        ]
    }

    tg_send_message(
        chat_id,
        f"👋 Olá <b>{nome}</b>!\n\n"
        "Clique no botão abaixo para <b>validar seu acesso</b> às carteiras do Projeto Phoenix.",
        reply_markup=teclado
    )


# ============================================================
# PROCESSAMENTO DE CALLBACK (VALIDAR ACESSO)
# ============================================================

def process_callback(callback):
    data = callback.get("data", "")
    if not data.startswith("validar:"):
        return

    _, cliente_id = data.split(":", 1)

    user = callback.get("from", {})
    user_id = user.get("id")
    username = user.get("username", "")

    msg = callback.get("message", {})
    chat_id = msg.get("chat", {}).get("id")

    cliente = supabase_get_client(cliente_id)
    if not cliente:
        tg_send_message(chat_id, "❌ Cliente não encontrado no cadastro.")
        return

    nome = cliente.get("nome", "Cliente")
    carteiras = cliente.get("carteiras", [])
    if isinstance(carteiras, str):
        try:
            # tentativa de normalizar string para lista
            import json
            carteiras = json.loads(carteiras)
        except Exception:
            carteiras = []

    # Confere vigência
    data_fim_str = cliente.get("data_fim")
    try:
        data_fim = datetime.fromisoformat(data_fim_str).date()
    except Exception:
        try:
            data_fim = datetime.strptime(data_fim_str, "%Y-%m-%d").date()
        except Exception:
            data_fim = None

    hoje = date.today()
    if data_fim and data_fim < hoje:
        fim_txt = data_fim.strftime("%d/%m/%Y")
        tg_send_message(
            chat_id,
            f"⚠️ Olá <b>{nome}</b>.\n\n"
            f"Sua assinatura do Projeto Phoenix venceu em <b>{fim_txt}</b>.\n"
            "Entre em contato com o suporte para renovar seu acesso."
        )
        # Garante que não fique marcado como conectado
        supabase_update_client(cliente_id, {
            "telegram_connected": False
        })
        return

    # Atualiza dados de Telegram do cliente
    supabase_update_client(cliente_id, {
        "telegram_id": user_id,
        "telegram_username": username,
        "telegram_connected": True,
        "telegram_last_sync": datetime.utcnow().isoformat(),
        "telegram_removed_at": None,
    })

    resposta = [f"🎉 <b>Acesso Validado, {nome}!</b>\n"]
    resposta.append("Você tem acesso às seguintes carteiras:\n")

    tem_carteira_valida = False
    for c in carteiras:
        if c in GRUPOS:
            link = GRUPOS[c]
            resposta.append(f"➡️ <b>{c}</b>: {link}")
            tem_carteira_valida = True
        else:
            resposta.append(f"⚠️ Nenhum grupo configurado para: <b>{c}</b>")

    if not tem_carteira_valida:
        resposta.append(
            "\n⚠️ Seu cadastro não possui nenhuma carteira Phoenix com grupo configurado.\n"
            "Fale com o suporte para ajustar seu acesso."
        )
    else:
        resposta.append(
            "\n✅ Entre nos grupos acima para receber:\n"
            "• Alertas automáticos\n"
            "• Relatórios\n"
            "• Atualizações do Projeto Phoenix\n"
        )

    tg_send_message(chat_id, "\n".join(resposta))


# ============================================================
# ROTINA DE REMOÇÃO AUTOMÁTICA DE VENCIDOS
# ============================================================

def process_auto_cleanup():
    """
    Procura clientes com data_fim vencida e telegram conectado,
    remove dos grupos (quando GROUP_CHAT_IDS estiver configurado)
    e atualiza campos no Supabase.
    """
    print("🔍 Rodando rotina de remoção automática de vencidos...")
    clientes = supabase_list_clients_for_cleanup()
    if not clientes:
        return

    hoje = date.today()
    removidos = 0

    for cli in clientes:
        try:
            data_fim_str = cli.get("data_fim")
            if not data_fim_str:
                continue
            try:
                dfim = datetime.fromisoformat(data_fim_str).date()
            except Exception:
                dfim = datetime.strptime(data_fim_str, "%Y-%m-%d").date()
        except Exception:
            continue

        telegram_id = cli.get("telegram_id")
        telegram_connected = cli.get("telegram_connected", False)
        telegram_removed_at = cli.get("telegram_removed_at")
        carteiras = cli.get("carteiras", [])
        if isinstance(carteiras, str):
            try:
                import json
                carteiras = json.loads(carteiras)
            except Exception:
                carteiras = []

        # Não remove se não está conectado ou já foi removido
        if not telegram_id or not telegram_connected or telegram_removed_at:
            continue

        # Se ainda não venceu, ignora
        if dfim >= hoje:
            continue

        # Tenta expulsar dos grupos conectados
        for cart in carteiras:
            chat_id = GROUP_CHAT_IDS.get(cart)
            if chat_id is None:
                # se ainda não configurou chat_id, apenas ignora
                continue
            ok = tg_kick_user(chat_id, telegram_id)
            if ok:
                print(f"Removido {cli.get('nome')} ({telegram_id}) do grupo {cart}")

        # Atualiza Supabase: marca como desconectado / removido
        supabase_update_client(cli["id"], {
            "telegram_connected": False,
            "telegram_removed_at": datetime.utcnow().isoformat()
        })
        removidos += 1

    print(f"✅ Rotina de remoção concluída. Clientes processados: {removidos}")


# ============================================================
# LOOP PRINCIPAL
# ============================================================

def main():
    print("🤖 Bot CRM Phoenix rodando...")
    last_update = None
    last_cleanup_ts = 0
    CLEANUP_INTERVAL = 60 * 60  # 1 hora

    while True:
        try:
            updates = tg_get_updates(last_update)
            if "result" in updates:
                for u in updates["result"]:
                    last_update = u["update_id"] + 1

                    # Mensagem normal
                    if "message" in u and "text" in u["message"]:
                        texto = u["message"]["text"]
                        if texto.startswith("/start"):
                            process_start(u["message"])

                    # Callback (VALIDAR ACESSO)
                    if "callback_query" in u:
                        process_callback(u["callback_query"])

            # Rotina periódica de remoção de vencidos
            now = time.time()
            if now - last_cleanup_ts > CLEANUP_INTERVAL:
                process_auto_cleanup()
                last_cleanup_ts = now

        except Exception as e:
            print("Erro no loop principal:", e)

        time.sleep(1)


if __name__ == "__main__":
    main()

# NOVOS GRUPOS PHOENIX — links de convite oficiais
GRUPOS = {
    "Carteira de Ações IBOV": "https://t.me/+Rkvw9CfJBkowMTg0",
    "Carteira de BDRs": "https://t.me/+-Io0aAFaGJ0yN2Rk",
    "Carteira de Opções": "https://t.me/+3YzTJqBi-xYxNjNk",
}




BASE_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"


# ============================================================
# FUNÇÕES DE SUPABASE
# ============================================================
def supabase_get_client(cliente_id):
    """Busca cliente no Supabase pelo ID"""
    url = f"{SUPABASE_URL}/rest/v1/clientes?id=eq.{cliente_id}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }
    r = requests.get(url, headers=headers)
    try:
        return r.json()[0]
    except:
        return None


# ============================================================
# FUNÇÕES TELEGRAM
# ============================================================
def tg_get_updates(offset=None):
    """Pega mensagens novas do Telegram"""
    url = BASE_API + "/getUpdates"
    if offset:
        url += f"?offset={offset}"
    return requests.get(url).json()


def tg_send_message(chat_id, text, reply_markup=None):
    """Envia mensagem simples"""
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    requests.post(BASE_API + "/sendMessage", json=payload)


def tg_kick_user(group_id, user_id):
    """Expulsa usuário do grupo - usado mais tarde"""
    url = BASE_API + "/kickChatMember"
    payload = {"chat_id": group_id, "user_id": user_id}
    requests.post(url, json=payload)


# ============================================================
# PROCESSAMENTO DO /start
# ============================================================
def process_start(message):
    chat_id = message["chat"]["id"]
    text = message["text"]

    parts = text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        tg_send_message(chat_id, "❌ Link inválido ou expirado. Peça um novo ao suporte.")
        return

    cliente_id = parts[1]

    cliente = supabase_get_client(cliente_id)
    if not cliente:
        tg_send_message(chat_id, "❌ Cliente não encontrado. Peça um novo link ao suporte.")
        return

    nome = cliente["nome"]

    teclado = {
        "inline_keyboard": [
            [
                {
                    "text": "🔓 VALIDAR ACESSO",
                    "callback_data": f"validar:{cliente_id}"
                }
            ]
        ]
    }

    tg_send_message(
        chat_id,
        f"👋 Olá <b>{nome}</b>!\n\nClique abaixo para validar seu acesso.",
        reply_markup=teclado
    )



# ============================================================
# PROCESSAMENTO DE CALLBACK (quando clica VALIDAR ACESSO)
# ============================================================
def process_callback(callback):
    data = callback["data"]            # ex: validar:939
    user_id = callback["from"]["id"]
    chat_id = callback["message"]["chat"]["id"]

    _, cliente_id = data.split(":")

    cliente = supabase_get_client(cliente_id)
    if not cliente:
        tg_send_message(chat_id, "❌ Cliente não encontrado.")
        return

    nome = cliente["nome"]
    carteiras = cliente["carteiras"]

    resposta = [f"🎉 <b>Acesso Validado, {nome}!</b>\n"]

    # percorre as carteiras novas
    for c in carteiras:
        if c in GRUPOS:
            link = GRUPOS[c]
            resposta.append(f"➡️ <b>{c}</b>: {link}")
        else:
            resposta.append(f"⚠️ Nenhum grupo configurado para: {c}")

    tg_send_message(chat_id, "\n".join(resposta))



# ============================================================
# LOOP PRINCIPAL
# ============================================================
def main():
    print("🤖 Bot do Telegram rodando no Render…")
    last_update = None

    while True:
        try:
            updates = tg_get_updates(last_update)
            if "result" in updates:
                for u in updates["result"]:
                    last_update = u["update_id"] + 1

                    # mensagem normal
                    if "message" in u and "text" in u["message"]:
                        texto = u["message"]["text"]
                        if texto.startswith("/start"):
                            process_start(u["message"])

                    # callback
                    if "callback_query" in u:
                        process_callback(u["callback_query"])

        except Exception as e:
            print("Erro no bot:", e)

        time.sleep(1)


if __name__ == "__main__":
    main()
