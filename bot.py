# -*- coding: utf-8 -*-
"""
BOT OFICIAL CRM — PROJETO PHOENIX (milhao_crm_bot)
Autor: Phoenix v2
Versão: 2025-02

Funções:
- /start <cliente_id> → exibe botão VALIDAR ACESSO
- VALIDAR ACESSO → salva telegram_id, username, registra log, libera grupos
- Rotina automática → remove vencidos dos grupos + registra log
"""

import os
import time
import json
import requests
from datetime import datetime, date

# ============================================================
# CONFIGURAÇÕES GERAIS
# ============================================================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
SUPABASE_URL   = os.getenv("SUPABASE_URL")
SUPABASE_KEY   = os.getenv("SUPABASE_KEY")

if not TELEGRAM_TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN não definido")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL ou SUPABASE_KEY não definidos")

BASE_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# ============================================================
# GRUPOS OFICIAIS (links + chat_ids)
# ============================================================

GRUPOS = {
    "Carteira de Ações IBOV": "https://t.me/+Rkvw9CfJBkowMTg0",
    "Carteira de BDRs":       "https://t.me/+-Io0aAFaGJ0yN2Rk",
    "Carteira de Opções":     "https://t.me/+3YzTJqBi-xYxNjNk",
    "Carteira de Small Caps": "https://t.me/+2UD3b1xLWvU0NDFk",
}

GROUP_CHAT_IDS = {
    "Carteira de Ações IBOV": -1002198655576,
    "Carteira de Small Caps": -1003251673981,
    "Carteira de BDRs":       -1002171530332,
    "Carteira de Opções":     -1003274356400,
}

# ============================================================
# LOGS (Phoenix)
# ============================================================

def registrar_log(evento, descricao, cliente_id=None, extra=None):
    """
    Versão independente para rodar no Render (sem Streamlit).
    Grava logs diretamente na tabelas logs do Supabase.
    """
    try:
        payload = {
            "evento": evento,
            "descricao": descricao,
            "cliente_id": cliente_id,
            "extra": extra or {},
        }
        url = f"{SUPABASE_URL}/rest/v1/logs"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        requests.post(url, json=payload, headers=headers, timeout=10)
    except Exception as e:
        print("Erro registrar_log:", e)

# ============================================================
# SUPABASE HELPERS
# ============================================================

def supabase_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

def supabase_get_client(cliente_id):
    """Busca cliente por ID"""
    url = f"{SUPABASE_URL}/rest/v1/clientes"
    params = {"id": f"eq.{cliente_id}"}
    try:
        r = requests.get(url, headers=supabase_headers(), params=params, timeout=10).json()
        return r[0] if isinstance(r, list) and r else None
    except:
        return None

def supabase_update_client(cliente_id, payload):
    url = f"{SUPABASE_URL}/rest/v1/clientes?id=eq.{cliente_id}"
    try:
        requests.patch(url, json=payload, headers=supabase_headers(), timeout=10)
    except Exception as e:
        print("Erro atualizar cliente:", e)

def supabase_list_clients_for_cleanup():
    url = f"{SUPABASE_URL}/rest/v1/clientes"
    params = {
        "select": "id,nome,carteiras,data_fim,telegram_id,telegram_username,telegram_connected,telegram_removed_at"
    }
    try:
        r = requests.get(url, headers=supabase_headers(), params=params, timeout=20).json()
        return r if isinstance(r, list) else []
    except:
        return []

# ============================================================
# TELEGRAM HELPERS
# ============================================================

def tg_send_message(chat_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        requests.post(BASE_API + "/sendMessage", json=payload, timeout=10)
    except:
        pass

def tg_get_updates(offset=None):
    url = BASE_API + "/getUpdates"
    if offset:
        url += f"?offset={offset}"
    try:
        return requests.get(url, timeout=30).json()
    except:
        return {"result": []}

def tg_kick_user(chat_id, user_id):
    try:
        payload = {"chat_id": chat_id, "user_id": user_id}
        resp = requests.post(BASE_API + "/kickChatMember", json=payload, timeout=10).json()
        return resp.get("ok", False)
    except:
        return False

# ============================================================
# PROCESSAMENTO DO /start
# ============================================================

def process_start(message):
    chat_id = message["chat"]["id"]
    text = message.get("text", "")

    registrar_log("telegram_start", "/start recebido", extra={"chat_id": chat_id, "texto": text})

    parts = text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        registrar_log("telegram_start_invalido", "Start sem ID", extra={"chat_id": chat_id})
        tg_send_message(chat_id, "❌ Link inválido. Peça outro ao suporte.")
        return

    cliente_id = parts[1]
    cliente = supabase_get_client(cliente_id)

    if not cliente:
        registrar_log("telegram_cliente_inexistente", "Cliente ID não encontrado", extra={"cliente_id": cliente_id})
        tg_send_message(chat_id, "❌ Cliente não encontrado.")
        return

    nome = cliente.get("nome", "Cliente")

    teclado = {
        "inline_keyboard": [
            [{"text": "🔓 VALIDAR ACESSO", "callback_data": f"validar:{cliente_id}"}]
        ]
    }

    tg_send_message(
        chat_id,
        f"👋 Olá <b>{nome}</b>!\n\nClique no botão abaixo para validar seu acesso.",
        reply_markup=teclado
    )

# ============================================================
# PROCESSAMENTO DO VALIDAR ACESSO
# ============================================================

def process_callback(callback):
    data = callback.get("data", "")
    if not data.startswith("validar:"):
        return

    _, cliente_id = data.split(":")
    user     = callback.get("from", {})
    user_id  = user.get("id")
    username = user.get("username", "")

    msg      = callback.get("message", {})
    chat_id  = msg.get("chat", {}).get("id")

    cliente = supabase_get_client(cliente_id)
    if not cliente:
        tg_send_message(chat_id, "❌ Cliente não encontrado.")
        return

    nome      = cliente.get("nome", "Cliente")
    carteiras = cliente.get("carteiras", [])
    if isinstance(carteiras, str):
        try: carteiras = json.loads(carteiras)
        except: carteiras = []

    # Validar vigência
    try:
        data_fim = datetime.fromisoformat(cliente["data_fim"]).date()
    except:
        data_fim = None

    hoje = date.today()
    if data_fim and data_fim < hoje:
        registrar_log("telegram_vencido", f"Acesso vencido ({nome})", cliente_id)
        tg_send_message(chat_id, f"⚠️ Sua assinatura venceu em <b>{data_fim.strftime('%d/%m/%Y')}</b>.")
        supabase_update_client(cliente_id, {"telegram_connected": False})
        return

    # Atualizar Supabase com dados do Telegram
    supabase_update_client(cliente_id, {
        "telegram_id": user_id,
        "telegram_username": username,
        "telegram_connected": True,
        "telegram_last_sync": datetime.utcnow().isoformat(),
        "telegram_removed_at": None
    })

    registrar_log("telegram_validado", f"Acesso validado para {nome}", cliente_id,
        extra={"telegram_id": user_id, "username": username, "carteiras": carteiras}
    )

    # Montar resposta com os links dos grupos
    resposta = [f"🎉 <b>Acesso Validado, {nome}!</b>\n", "Você tem acesso às seguintes carteiras:\n"]

    for c in carteiras:
        if c in GRUPOS:
            resposta.append(f"➡️ <b>{c}</b>: {GRUPOS[c]}")
        else:
            resposta.append(f"⚠️ Carteira sem grupo: {c}")

    tg_send_message(chat_id, "\n".join(resposta))

# ============================================================
# ROTINA AUTOMÁTICA DE LIMPEZA / REMOÇÃO DE VENCIDOS
# ============================================================

def process_auto_cleanup():
    clientes = supabase_list_clients_for_cleanup()
    hoje = date.today()
    removidos = 0

    for cli in clientes:
        telegram_id = cli.get("telegram_id")
        if not telegram_id:
            continue

        if not cli.get("telegram_connected"):
            continue

        if cli.get("telegram_removed_at"):
            continue

        # Data fim
        try:
            dfim = datetime.fromisoformat(cli["data_fim"]).date()
        except:
            continue

        if dfim >= hoje:
            continue

        carteiras = cli.get("carteiras", [])
        if isinstance(carteiras, str):
            try: carteiras = json.loads(carteiras)
            except: carteiras = []

        # Expulsar dos grupos
        for c in carteiras:
            chatid = GROUP_CHAT_IDS.get(c)
            if chatid:
                tg_kick_user(chatid, telegram_id)

        # Atualizar Supabase
        supabase_update_client(cli["id"], {
            "telegram_connected": False,
            "telegram_removed_at": datetime.utcnow().isoformat()
        })

        registrar_log("telegram_remocao_automatica",
            "Cliente removido automaticamente",
            cli["id"],
            extra={"carteiras": carteiras}
        )

        removidos += 1

    registrar_log("telegram_rotina_cleanup",
        f"Rotina auto cleanup executada ({removidos} removidos)",
        extra={"quantidade": removidos}
    )

# ============================================================
# LOOP PRINCIPAL
# ============================================================

def main():
    print("🤖 Bot CRM Phoenix rodando...")
    last_update = None
    last_cleanup_ts = 0
    CLEANUP_INTERVAL = 60 * 60  # 1h

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

                    # Callback
                    if "callback_query" in u:
                        process_callback(u["callback_query"])

            # Executar limpeza periódica
            now = time.time()
            if now - last_cleanup_ts > CLEANUP_INTERVAL:
                process_auto_cleanup()
                last_cleanup_ts = now

        except Exception as e:
            print("Erro no loop principal:", e)

        time.sleep(1)

# ============================================================

if __name__ == "__main__":
    main()
