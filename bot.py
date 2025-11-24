import os
import time
import requests
from datetime import datetime

# ============================================================
# CONFIGURAÇÕES
# ============================================================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
SUPABASE_URL   = os.getenv("SUPABASE_URL")
SUPABASE_KEY   = os.getenv("SUPABASE_KEY")

# ============================================================
# NOVO: TODOS OS GRUPOS USAM O MESMO LINK DE CONVITE
# ============================================================
LINK_CONVITE = "https://t.me/+Rkvw9CfJBkowMTg0"

GRUPOS = {
    "Curto Prazo": LINK_CONVITE,
    "Curtíssimo Prazo": LINK_CONVITE,
    "Opções": LINK_CONVITE,
    "Criptomoedas": LINK_CONVITE,
    "Estratégias Phoenix": LINK_CONVITE
}

BASE_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"


# ============================================================
# FUNÇÕES DE SUPABASE
# ============================================================
def supabase_get_client(cliente_id):
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
# TELEGRAM API
# ============================================================
def tg_get_updates(offset=None):
    url = BASE_API + "/getUpdates"
    if offset:
        url += f"?offset={offset}"
    return requests.get(url).json()


def tg_send_message(chat_id, text, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    requests.post(BASE_API + "/sendMessage", json=payload)


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
        tg_send_message(chat_id, "❌ Cliente não encontrado.")
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
# PROCESSAMENTO DO CALLBACK
# ============================================================
def process_callback(callback):
    data = callback["data"]             # validar:123
    chat_id = callback["message"]["chat"]["id"]
    _, cliente_id = data.split(":")

    cliente = supabase_get_client(cliente_id)
    if not cliente:
        tg_send_message(chat_id, "❌ Cliente não encontrado.")
        return

    nome = cliente["nome"]
    carteiras = cliente["carteiras"]

    resposta = [f"🎉 <b>Acesso Validado, {nome}!</b>\n"]

    for c in carteiras:
        link = GRUPOS.get(c)
        if link:
            resposta.append(f"➡️ <b>{c}</b>: {link}")
        else:
            resposta.append(f"⚠️ Carteira sem link configurado: {c}")

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

                    if "message" in u and "text" in u["message"]:
                        texto = u["message"]["text"]
                        if texto.startswith("/start"):
                            process_start(u["message"])

                    if "callback_query" in u:
                        process_callback(u["callback_query"])

        except Exception as e:
            print("Erro no bot:", e)

        time.sleep(1)


if __name__ == "__main__":
    main()
