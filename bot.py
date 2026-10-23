import os, json, asyncio, logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from besk import get_besk_data

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(BOT_TOKEN)
dp = Dispatcher()

# Машина состояний для ввода долга
class DebtState(StatesGroup):
    waiting_for_amount = State()

with open("config.json", "r", encoding="utf-8") as f:
    CFG = json.load(f)

def save_cfg():
    with open("config.json", "w", encoding="utf-8") as f:
        json.dump(CFG, f, ensure_ascii=False, indent=2)

def main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💧 Водоканал | {CFG['accounts']['hv']}", callback_data="info_hv"),
         InlineKeyboardButton(text=f"🔥 Шығыс Жылу | {CFG['accounts']['gvs']}", callback_data="info_gvs")],
        [InlineKeyboardButton(text=f"💡 Шыгыс Энерго | {CFG['accounts']['svet']}", callback_data="info_svet"),
         InlineKeyboardButton(text="💸 Ввести долг БЭСК", callback_data="edit_dolg")],
        [InlineKeyboardButton(text="🧾 Сформировать квитанцию", callback_data="kv")]
    ])

@dp.message(Command("start", "menu"))
async def start(m: types.Message):
    await m.answer(
        f"🏠 {CFG['address']}\n\n"
        f"Бот для учета коммуналки. Нажмите кнопку ниже, чтобы ввести актуальный долг за свет или сформировать квитанцию.",
        reply_markup=main_kb()
    )

@dp.callback_query(F.data.startswith("info_"))
async def info_account(c: types.CallbackQuery):
    acc_type = c.data.split("_")[1]
    await c.answer(f"Л/с: {CFG['accounts'][acc_type]}", show_alert=True)

# Ввод долга БЭСК
@dp.callback_query(F.data == "edit_dolg")
async def ask_dolg(c: types.CallbackQuery, state: FSMContext):
    await c.message.answer("Введите текущий долг за свет (в тенге), только цифры:")
    await state.set_state(DebtState.waiting_for_amount)
    await c.answer()

@dp.message(DebtState.waiting_for_amount)
async def process_dolg(m: types.Message, state: FSMContext):
    try:
        amount = float(m.text.replace(',', '.'))
        CFG['debt_svet'] = amount
        save_cfg()
        await m.answer(f"✅ Долг за свет обновлен: {amount} тг", reply_markup=main_kb())
    except ValueError:
        await m.answer("❌ Пожалуйста, введите число (например, 4500).")
    await state.clear()

# Формирование квитанции
@dp.callback_query(F.data == "kv")
async def kv(c: types.CallbackQuery):
    # Берем текущие показания (в будущем мы их будем брать из фото)
    hv_tek = CFG['last_readings']['hv']
    gvs_tek = CFG['last_readings']['gvs']
    
    # Считаем расход (пока просто ставим 0, так как это тестовые данные)
    # Для правильного расчета нужно будет вычитать предыдущие показания
    rashod_hv = 15.868 
    rashod_gvs = 10.007
    
    t_hv = CFG['tariffs']['hv']
    t_gvs = CFG['tariffs']['gvs']
    dolg = CFG.get('debt_svet', 0)
    
    sum_hv = rashod_hv * t_hv
    sum_gvs = rashod_gvs * t_gvs
    total = sum_hv + sum_gvs + dolg
    
    text = (
        f"🧾 **Квитанция (расчет)**\n\n"
        f"💧 ХВ: {rashod_hv} м³ × {t_hv} тг = {sum_hv:.0f} тг\n"
        f"🔥 ГВС: {rashod_gvs} м³ × {t_gvs} тг = {sum_gvs:.0f} тг\n"
        f"💡 Долг БЭСК: {dolg} тг\n"
        f"----------------------------\n"
        f"💰 **ИТОГО К ОПЛАТЕ: {total:.0f} тг**"
    )
    await c.message.answer(text, parse_mode="Markdown")
    await c.answer()

async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())