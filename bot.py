import os
from aiogram import Bot, Dispatcher, executor, types

# ---------------------------------------------------
# CARREGA O TOKEN DO TELEGRAM (que você vai colocar no Render)
# ---------------------------------------------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher(bot)

# ---------------------------------------------------
# /start + ID do cliente vindo do link do email
# ---------------------------------------------------
@dp.message_handler(commands=['start'])
async def start_cmd(message: types.Message):

    args = message.get_args()  # pega o ID enviado no link
    if not args or not args.isdigit():
        await message.answer("❌ Link inválido. Peça ao suporte um link atualizado.")
        return

    cliente_id = int(args)

    # Mensagem inicial
    await message.answer(
        "👋 Olá! Clique abaixo para validar seu acesso ao grupo:",
        reply_markup=types.InlineKeyboardMarkup().add(
            types.InlineKeyboardButton(
                "VALIDAR ACESSO", callback_data=f"validar:{cliente_id}"
            )
        )
    )

# ---------------------------------------------------
# Callback quando clicar no botão VALIDAR
# ---------------------------------------------------
@dp.callback_query_handler(lambda c: c.data.startswith("validar:"))
async def validar(callback: types.CallbackQuery):

    cliente_id = callback.data.split(":")[1]

    # Aqui você coloca depois a lógica REAL.
    # Por enquanto vamos colocar um link fixo apenas para rodar.
    link_grupo = "https://t.me/+SeuGrupoAqui"

    await callback.message.edit_text(
        f"🎉 Acesso validado!\n\nEntre no grupo pelo link abaixo:\n{link_grupo}"
    )

    await callback.answer()

# ---------------------------------------------------
# Mantém o bot vivo (Render vai rodar isso 24h)
# ---------------------------------------------------
if __name__ == "__main__":
    print("Bot rodando no Render…")
    executor.start_polling(dp, skip_updates=True)
