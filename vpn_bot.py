import logging
import subprocess
import codecs
import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from telegraph import Telegraph

# Установите уровень логирования
logging.basicConfig(level=logging.INFO)

# Токен вашего бота
TOKEN = '7478333898:AAHhLVf9YFpgABd-jcoUbViLdWMeR-51VeA'

# Список разрешенных Telegram ID
ALLOWED_TELEGRAM_IDS = [5979595107]

# Создайте экземпляры бота и диспетчера
bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

telegraph = Telegraph()
telegraph.create_account(short_name='vpn_bot')

# Определение состояний для FSM
class Form(StatesGroup):
    waiting_for_username = State()
    waiting_for_password = State()
    waiting_for_confirm_password = State()
    waiting_for_block_time = State()  # Новое состояние для времени блокировки
    waiting_for_delete_number = State()
    waiting_for_block_number = State()
    waiting_for_unblock_number = State()
    waiting_for_unblock_time = State()  # Новое состояние для времени до повторной блокировки
    waiting_for_update_number = State()
    waiting_for_new_password = State()
    waiting_for_confirm_new_password = State()

# Функция проверки разрешенного Telegram ID
def is_allowed(user_id):
    return user_id in ALLOWED_TELEGRAM_IDS

# Команда /start
@dp.message_handler(commands=['start'], state='*')
async def start_command(message: types.Message, state: FSMContext):
    if not is_allowed(message.from_user.id):
        return
    await state.finish()
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton(text="Кто онлайн", callback_data='1'),
                 types.InlineKeyboardButton(text="Рестарт", callback_data='2'))
    keyboard.add(types.InlineKeyboardButton(text="Добавить пользователя", callback_data='3'))
    keyboard.add(types.InlineKeyboardButton(text="Все пользователи", callback_data='4'),
                 types.InlineKeyboardButton(text="Удалить пользователя", callback_data='5'))
    keyboard.add(types.InlineKeyboardButton(text="Блокировать пользователя", callback_data='6'),
                 types.InlineKeyboardButton(text="Разблокировать пользователя", callback_data='7'))
    keyboard.add(types.InlineKeyboardButton(text="Изменить пароль пользователя", callback_data='8'),
                 types.InlineKeyboardButton(text="Обновить время", callback_data='9'))

    await message.answer(f"Привет {message.from_user.first_name}", reply_markup=keyboard)

# Обработчик нажатий на кнопки
@dp.callback_query_handler(lambda c: c.data)
async def process_callback(callback_query: types.CallbackQuery, state: FSMContext):
    if not is_allowed(callback_query.from_user.id):
        return

    code = callback_query.data
    if code == '1':
        await send_online_users(callback_query.from_user.id)
    elif code == '2':
        command = ['systemctl', 'restart', 'ocserv']
        try:
            subprocess.run(command, check=True)
            await bot.send_message(callback_query.from_user.id, "Сервис ocserv успешно перезапущен.")
        except subprocess.CalledProcessError as e:
            await bot.send_message(callback_query.from_user.id, f"Ошибка при перезапуске сервиса: {e}")
    elif code == '3':
        await bot.send_message(callback_query.from_user.id, "Введите имя нового клиента:")
        await Form.waiting_for_username.set()
    elif code in ['4', '5', '6', '7', '8']:
        await send_users_list(callback_query.from_user.id, code)

# Функция для отправки списка онлайн пользователей
async def send_online_users(user_id):
    try:
        command = ['occtl', 'show', 'users']
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        output, error = process.communicate(timeout=10)
        if error:
            await bot.send_message(user_id, error)
        elif not output.strip():
            await bot.send_message(user_id, "Нет подключенных пользователей.")
        else:
            users = output.strip().split('\n')
            limited_users = '\n'.join([f"{i+1}. {user}" for i, user in enumerate(users[:50])])
            user_list = '\n'.join([f"{i+1}. {user}" for i, user in enumerate(users)])
            telegraph_response = telegraph.create_page(
                title='Список подключенных пользователей',
                html_content=f"<p>Список подключенных пользователей</p><pre>{output.strip()}</pre>"
            )
            telegraph_url = telegraph_response['url']
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton(text="ПОСМОТРЕТЬ", url=telegraph_url))
            await bot.send_message(user_id, f"Ваши ключи\n{limited_users}", reply_markup=keyboard)
    except subprocess.TimeoutExpired:
        await bot.send_message(user_id, f"Команда {command} превысила время ожидания.")
    except Exception as e:
        await bot.send_message(user_id, str(e))

# Функция для отправки списка пользователей
async def send_users_list(user_id, action_code=None):
    try:
        with codecs.open('/etc/ocserv/ocpasswd', 'r', encoding='utf-8') as f:
            users = [line.split(':')[0] for line in f if line.strip()]
        if users:
            limited_users = '\n'.join([f"{i+1}. {user}" for i, user in enumerate(users[:50])])  # Ограничение на 50 пользователей в предварительном просмотре
            user_list = '\n'.join([f"{i+1}. {user}" for i, user in enumerate(users)])
            telegraph_response = telegraph.create_page(
                title='Список подключенных ключей',
                html_content=f"<p>Список подключенных ключей</p><pre>{user_list}</pre>"
            )
            telegraph_url = telegraph_response['url']
            keyboard = InlineKeyboardMarkup()
            if action_code:
                keyboard.add(InlineKeyboardButton(text="ПОСМОТРЕТЬ", url=telegraph_url))
                await bot.send_message(user_id, f"Ваши ключи\n{limited_users}", reply_markup=keyboard)
                if action_code == '5':
                    await bot.send_message(user_id, "Введите номер пользователя для удаления:")
                    await Form.waiting_for_delete_number.set()
                elif action_code == '6':
                    await bot.send_message(user_id, "Введите номер пользователя для блокировки:")
                    await Form.waiting_for_block_number.set()
                elif action_code == '7':
                    await bot.send_message(user_id, "Введите номер пользователя для разблокировки:")
                    await Form.waiting_for_unblock_number.set()
                elif action_code == '8':
                    await bot.send_message(user_id, "Введите номер пользователя для изменения пароля:")
                    await Form.waiting_for_update_number.set()
            else:
                await bot.send_message(user_id, f"Ваши ключи\n{limited_users}")
        else:
            await bot.send_message(user_id, "Нет пользователей.")
    except Exception as e:
        await bot.send_message(user_id, str(e))

# Обработчик ввода имени пользователя
@dp.message_handler(state=Form.waiting_for_username)
async def process_username(message: types.Message, state: FSMContext):
    await state.update_data(username=message.text.strip())
    await message.answer("Введите пароль:")
    await Form.waiting_for_password.set()

# Обработчик ввода пароля
@dp.message_handler(state=Form.waiting_for_password)
async def process_password(message: types.Message, state: FSMContext):
    await state.update_data(password=message.text.strip())
    await message.answer("Подтвердите пароль:")
    await Form.waiting_for_confirm_password.set()

# Обработчик подтверждения пароля
@dp.message_handler(state=Form.waiting_for_confirm_password)
async def process_confirm_password(message: types.Message, state: FSMContext):
    data = await state.get_data()
    if message.text.strip() == data['password']:
        await message.answer("Введите количество дней до блокировки:")
        await Form.waiting_for_block_time.set()
    else:
        await message.answer("Пароли не совпадают. Попробуйте снова. Введите пароль:")
        await Form.waiting_for_password.set()

# Обработчик ввода времени до блокировки
@dp.message_handler(state=Form.waiting_for_block_time)
async def process_block_time(message: types.Message, state: FSMContext):
    try:
        block_time = int(message.text.strip())
        data = await state.get_data()
        username = data['username']
        password = data['password']
        command = ['ocpasswd', '-c', '/etc/ocserv/ocpasswd', username]
        try:
            process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            output, error = process.communicate(input=password + '\n' + password + '\n', timeout=10)
            if error:
                await message.answer(error)
            else:
                await message.answer(f"Пользователь {username} успешно добавлен.")
                
                # Вычисляем дату блокировки
                today = datetime.date.today()
                block_date = today + datetime.timedelta(days=block_time)
                cron_command = f'(crontab -l ; echo "0 0 {block_date.day} {block_date.month} * ocpasswd -c /etc/ocserv/ocpasswd -l {username}") | crontab -'
                
                subprocess.run(cron_command, shell=True)
                await message.answer(f"Пользователь {username} будет заблокирован через {block_time} дней.")
        except subprocess.TimeoutExpired:
            await message.answer(f"Команда {command} превысила время ожидания.")
        except Exception as e:
            await message.answer(str(e))
        await state.finish()
    except ValueError:
        await message.answer("Введите корректное количество дней.")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
