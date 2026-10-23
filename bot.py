import os, json, asyncio, logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from besk import get_besk_data
from aiohttp import web

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(BOT_TOKEN)
dp = Dispatcher()

class UserState(StatesGroup):
    waiting_for_dolg = State()
    waiting_for_hv = State()
    waiting_for_gvs = State()
    waiting_for_svet = State()

with open("config.json", "r", encoding="utf-8") as f:
    CFG = json.load(f)

def save_cfg():
    with open("config.json", "w", encoding="utf-8") as f:
        json.dump(CFG, f, ensure_ascii=False, indent=2)

def main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💧 Водоканал (ХВ)", callback_data="edit_hv"),
         InlineKeyboardButton(text=f"🔥 Шығыс Жылу (ГВС)", callback_data="edit_gvs")],
        [InlineKeyboardButton(text=f"💡 Шыгыс Энерго (Свет)", callback_data="edit_svet"),
         InlineKeyboardButton(text="💸 Ввести долг БЭСК", callback_data="edit_dolg")],
        [InlineKeyboardButton(text="🧾 Сформировать квитанцию", callback_data="kv")]
    ])

def cancel_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Отмена", callback_data="main")]
    ])

@dp.message(Command("start", "menu"))
async def start(m: types.Message, state: FSMContext):
    await state.clear()
    await m.answer(f"🏠 {CFG['address']}\n\nВыберите действие:", reply_markup=main_kb())

@dp.callback_query(F.data == "main")
async def back_to_main(c: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await c.message.edit_text(f"🏠 {CFG['address']}\n\nВыберите действие:", reply_markup=main_kb())
    await c.answer()

# --- ВВОД ДАННЫХ ---
@dp.callback_query(F.data == "edit_dolg")
async def ask_dolg(c: types.CallbackQuery, state: FSMContext):
    await c.message.edit_text("💸 Введите текущий долг за свет (в тенге):", reply_markup=cancel_kb())
    await state.set_state(UserState.waiting_for_dolg)

@dp.callback_query(F.data == "edit_hv")
async def ask_hv(c: types.CallbackQuery, state: FSMContext):
    prev = CFG['readings']['hv']['prev']
    await c.message.edit_text(f"💧 Введите новые показания ХВ.\nПрошлые: {prev}", reply_markup=cancel_kb())
    await state.set_state(UserState.waiting_for_hv)

@dp.callback_query(F.data == "edit_gvs")
async def ask_gvs(c: types.CallbackQuery, state: FSMContext):
    prev = CFG['readings']['gvs']['prev']
    await c.message.edit_text(f"🔥 Введите новые показания ГВС.\nПрошлые: {prev}", reply_markup=cancel_kb())
    await state.set_state(UserState.waiting_for_gvs)

@dp.callback_query(F.data == "edit_svet")
async def ask_svet(c: types.CallbackQuery, state: FSMContext):
    prev = CFG['readings']['svet']['prev']
    await c.message.edit_text(f"💡 Введите новые показания Света.\nПрошлые: {prev}", reply_markup=cancel_kb())
    await state.set_state(UserState.waiting_for_svet)

# --- ОБРАБОТКА ВВОДА ---
@dp.message(UserState.waiting_for_dolg)
async def process_dolg(m: types.Message, state: FSMContext):
    try:
        CFG['debt_svet'] = float(m.text.replace(',', '.'))
        save_cfg()
        await m.answer("✅ Долг обновлен!", reply_markup=main_kb())
        await state.clear()
    except ValueError:
        await m.answer("❌ Введите число.", reply_markup=cancel_kb())

@dp.message(UserState.waiting_for_hv)
async def process_hv(m: types.Message, state: FSMContext):
    try:
        CFG['readings']['hv']['curr'] = float(m.text.replace(',', '.'))
        save_cfg()
        await m.answer("✅ Показания ХВ сохранены!", reply_markup=main_kb())
        await state.clear()
    except ValueError:
        await m.answer("❌ Введите число.", reply_markup=cancel_kb())

@dp.message(UserState.waiting_for_gvs)
async def process_gvs(m: types.Message, state: FSMContext):
    try:
        CFG['readings']['gvs']['curr'] = float(m.text.replace(',', '.'))
        save_cfg()
        await m.answer("✅ Показания ГВС сохранены!", reply_markup=main_kb())
        await state.clear()
    except ValueError:
        await m.answer("❌ Введите число.", reply_markup=cancel_kb())

@dp.message(UserState.waiting_for_svet)
async def process_svet(m: types.Message, state: FSMContext):
    try:
        CFG['readings']['svet']['curr'] = float(m.text.replace(',', '.'))
        save_cfg()
        await m.answer("✅ Показания Света сохранены!", reply_markup=main_kb())
        await state.clear()
    except ValueError:
        await m.answer("❌ Введите число.", reply_markup=cancel_kb())

# --- КВИТАНЦИЯ ---
@dp.callback_query(F.data == "kv")
async def kv(c: types.CallbackQuery):
    t = CFG['tariffs']
    r = CFG['readings']
    area = CFG['area']
    
    # Расходы
    rash_hv = r['hv']['curr'] - r['hv']['prev']
    rash_gvs = r['gvs']['curr'] - r['gvs']['prev']
    rash_svet = r['svet']['curr'] - r['svet']['prev']
    rash_kanaliz = rash_hv + rash_gvs
    
    # Суммы
    sum_hv = rash_hv * t['hv']
    sum_kanaliz = rash_kanaliz * t['kanaliz']
    sum_gvs = rash_gvs * t['gvs']
    sum_otopl = area * t['otopl']
    sum_svet = rash_svet * t['svet']
    
    # Фиксы
    sum_fixed = sum(item['sum'] for item in CFG['fixed'])
    
    # Итог
    total = sum_hv + sum_kanaliz + sum_gvs + sum_otopl + sum_svet + sum_fixed
    
    # Формируем красивую таблицу (тег <pre> сохраняет пробелы)
    text = f"<b>Коммуналка | {CFG['address']} | {area} м²</b>\n\n"
    text += "<pre>\n"
    text += "№  Услуга         Сумма\n"
    text += "-------------------------\n"
    text += f"1  Водоканал ХВ   {sum_hv:7.2f}\n"
    text += f"2  Канализ.       {sum_kanaliz:7.2f}\n"
    text += f"3  ГВС            {sum_gvs:7.2f}\n"
    text += f"4  Отопл.         {sum_otopl:7.2f}\n"
    text += f"5  Свет БЭСК      {sum_svet:7.2f}\n"
    
    for i, item in enumerate(CFG['fixed'], start=6):
        name = item['name'][:12].ljust(12)
        text += f"{i:<2} {name} {item['sum']:7.2f}\n"
        
    text += "-------------------------\n"
    text += f"   ИТОГО:         {total:7.2f}\n"
    text += "</pre>\n"
    
    text += f"\n<i>Расход: ХВ {rash_hv:.3f} | ГВС {rash_gvs:.3f} | Свет {rash_svet:.2f}</i>"

    await c.message.answer(text, parse_mode="HTML", reply_markup=main_kb())
    await c.answer()

# --- ВЕБ-СЕРВЕР ---
async def handle(request):
    return web.Response(text="Bot is running")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

async def main():
    logging.basicConfig(level=logging.INFO)
    asyncio.create_task(start_web_server())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
