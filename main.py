import json
import os
import sys
import requests
import time
from dotenv import load_dotenv

# Чтобы print с русским текстом и эмодзи не падал в консоли Windows
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ================= НАСТРОЙКИ =================
# Все секреты лежат в файле .env рядом со скриптом (см. .env.example)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

# Токен твоего Телеграм-бота (получать у @BotFather)
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
# Твой ID в Телеграме (получать у @userinfobot) — стартовый подписчик рассылки
TG_CHAT_ID = os.getenv("TG_CHAT_ID")

# Данные твоего приложения EXBO
SC_CLIENT_ID = os.getenv("SC_CLIENT_ID")
SC_CLIENT_SECRET = os.getenv("SC_CLIENT_SECRET")
REGION = os.getenv("REGION", "eu")  # Регион игры (ru, eu, na, sea)

# Порог цены: слать уведомление, если цена ЗА ШТУКУ <= этого значения
PRICE_LIMIT = int(os.getenv("PRICE_LIMIT", "50000"))

if not all([TG_BOT_TOKEN, TG_CHAT_ID, SC_CLIENT_ID, SC_CLIENT_SECRET]):
    print("Ошибка: не заполнен .env! Скопируй .env.example в .env и впиши свои ключи.")
    sys.exit(1)

# =============================================

# Лоты, о которых уже отправляли сообщение (чтобы не спамить каждую минуту)
already_sent = set()

# Файл со списком подписчиков бота
SUBSCRIBERS_FILE = os.path.join(BASE_DIR, "subscribers.json")


def load_subscribers():
    """Читает список подписчиков из файла. Если файла нет — начинаем с твоего ID."""
    try:
        with open(SUBSCRIBERS_FILE, encoding="utf-8") as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return {TG_CHAT_ID}


def save_subscribers():
    with open(SUBSCRIBERS_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(subscribers), f)


subscribers = load_subscribers()
last_update_id = 0


def check_new_subscribers():
    """Проверяет новые сообщения боту: кто написал (/start или что угодно) — подписывается."""
    global last_update_id
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/getUpdates"
    try:
        response = requests.get(url, params={"offset": last_update_id + 1}, timeout=30)
        updates = response.json().get("result", [])
    except Exception as e:
        print(f"Ошибка получения обновлений ТГ: {e}")
        return

    for upd in updates:
        last_update_id = max(last_update_id, upd.get("update_id", 0))
        chat = (upd.get("message") or {}).get("chat") or {}
        chat_id = str(chat.get("id", ""))
        if not chat_id or chat_id in subscribers:
            continue
        subscribers.add(chat_id)
        save_subscribers()
        name = chat.get("first_name") or chat.get("title") or chat_id
        print(f"Новый подписчик: {name} ({chat_id}). Всего: {len(subscribers)}")
        send_message_to(chat_id, "Вы подписаны на уведомления о дешёвых лотах! 🔔")


def send_message_to(chat_id, text):
    """Отправка одного сообщения конкретному чату."""
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    try:
        response = requests.post(url, data={"chat_id": chat_id, "text": text}, timeout=30)
        # 403 = пользователь заблокировал бота, убираем его из рассылки
        if response.status_code == 403 and chat_id in subscribers:
            subscribers.discard(chat_id)
            save_subscribers()
            print(f"Подписчик {chat_id} заблокировал бота, удалён из рассылки.")
    except Exception as e:
        print(f"Ошибка отправки в ТГ ({chat_id}): {e}")

def send_telegram_alert(message):
    """Рассылка сообщения всем подписчикам бота"""
    # У Telegram лимит 4096 символов на сообщение — режем по строкам на части
    lines = message.split("\n")
    chunk = ""
    chunks = []
    for line in lines:
        if len(chunk) + len(line) + 1 > 4000:
            chunks.append(chunk)
            chunk = ""
        chunk += line + "\n"
    if chunk:
        chunks.append(chunk)

    for chat_id in list(subscribers):
        for part in chunks:
            send_message_to(chat_id, part)

def send_telegram_photo(item_id, caption):
    """Отправляет картинку предмета ({item_id}.png рядом со скриптом) с подписью.
    Если картинки нет — шлёт обычное текстовое сообщение."""
    image_path = os.path.join(BASE_DIR, f"{item_id}.png")

    if not os.path.exists(image_path):
        print(f"Картинка {image_path} не найдена, отправляю просто текст.")
        send_telegram_alert(caption)
        return

    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendPhoto"
    # У подписи к фото лимит 1024 символа — если список длиннее,
    # шлём фото с коротким заголовком, а список отдельным сообщением
    if len(caption) <= 1024:
        photo_caption, extra_text = caption, None
    else:
        first_line = caption.split("\n", 1)[0]
        photo_caption, extra_text = first_line, caption

    # Читаем картинку один раз и шлём всем подписчикам
    with open(image_path, "rb") as f:
        image_bytes = f.read()

    photo_failed = False
    for chat_id in list(subscribers):
        try:
            response = requests.post(url, data={"chat_id": chat_id, "caption": photo_caption},
                                     files={"photo": (f"{item_id}.png", image_bytes)}, timeout=60)
            if response.status_code == 403 and chat_id in subscribers:
                subscribers.discard(chat_id)
                save_subscribers()
                print(f"Подписчик {chat_id} заблокировал бота, удалён из рассылки.")
        except Exception as e:
            print(f"Ошибка отправки фото в ТГ ({chat_id}): {e}")
            photo_failed = True

    if photo_failed:
        extra_text = caption  # фото не ушло — отправим хотя бы текст

    if extra_text:
        send_telegram_alert(extra_text)


def check_auction():
    """Основная логика проверки лотов на аукционе"""
    print("Проверяю аукцион...")
    
    # ID предмета, который мы ищем (Продвинутые запчасти)
    target_item_id = "y3nmw" 
    
    # URL актуального (Production) API Сталкрафта
    url = f"https://eapi.stalcraft.net/{REGION}/auction/{target_item_id}/lots"

    # Вся суть метода: ключи кладутся прямо в headers
    headers = {
        "Client-Id": SC_CLIENT_ID,
        "Client-Secret": SC_CLIENT_SECRET

    }

    # Запрашиваем до 200 лотов, отсортированных по цене выкупа (от дешёвых к дорогим)
    params = {
        "limit": 200,
        "sort": "buyout_price",
        "order": "asc"
    }

    try:
        # Отправляем GET-запрос
        response = requests.get(url, headers=headers, params=params, timeout=30)

        # Проверяем, что сервер ответил успешно (HTTP 200)
        if response.status_code == 200:
            data = response.json()
            lots = data.get("lots", [])
            print(f"Успешно! Получено лотов: {len(lots)} (всего активных: {data.get('total', 0)})")

            cheap_lots = []
            for lot in lots:
                amount = lot.get("amount", 1) or 1
                buyout = lot.get("buyoutPrice", 0)

                # Пропускаем лоты без выкупа (только ставки)
                if not buyout:
                    continue

                price_per_unit = buyout / amount

                if price_per_unit <= PRICE_LIMIT:
                    # Уникальный "отпечаток" лота, чтобы не слать его повторно
                    lot_key = (amount, buyout, lot.get("startTime"), lot.get("endTime"))
                    if lot_key in already_sent:
                        continue
                    already_sent.add(lot_key)

                    cheap_lots.append(f"{amount}шт : {buyout} : {price_per_unit:.0f}/шт")

            if cheap_lots:
                message = (f"🔥 Найдены лоты <= {PRICE_LIMIT} за штуку ({len(cheap_lots)} шт.):\n"
                           + "\n".join(cheap_lots))
                print(message)
                send_telegram_photo(target_item_id, message)
            else:
                print(f"Новых лотов дешевле {PRICE_LIMIT} за штуку нет.")

            # Чистим память, если разрослась (старые лоты всё равно уже проданы/истекли)
            if len(already_sent) > 5000:
                already_sent.clear()

            return data
        else:
            # Если сервер недоволен ключами или предмета не существует
            print(f"Ошибка {response.status_code}: {response.text}")
            return None

    except requests.exceptions.RequestException as e:
        print(f"Ошибка подключения к API: {e}")
        return None
    

# ================= ЗАПУСК =================
if __name__ == "__main__":
    print("Бот запущен. Начинаю мониторинг...")
    
    print(f"Подписчиков в рассылке: {len(subscribers)}")

    # Бесконечный цикл проверки
    while True:
        try:
            check_new_subscribers()  # кто написал боту — добавляем в рассылку
            check_auction()
        except Exception as e:
            print(f"Произошла ошибка при парсинге: {e}")
            
        # ОБЯЗАТЕЛЬНАЯ ПАУЗА (Rate Limit)
        # Если спамить запросами без перерыва, EXBO заблокирует твой IP
        time.sleep(10) # Ждем 60 секунд до следующей проверки
