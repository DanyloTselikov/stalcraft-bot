# Деплой бота на Raspberry Pi

Инструкция рассчитана на Raspberry Pi OS (стандартная система Pi). Везде, где написано
`pi` и `IP_МАЛИНКИ`, подставь своего пользователя и IP-адрес своей Raspberry Pi.

## 1. Скопировать файлы на Pi

С компьютера (Windows, из папки проекта) — PowerShell или Git Bash:

```bash
scp -r main.py .env requirements.txt stalcraft-bot.service y3nmw.png pi@IP_МАЛИНКИ:/home/pi/stalcraft-bot/
```

Если папки ещё нет, сначала создай её на Pi:

```bash
ssh pi@IP_МАЛИНКИ "mkdir -p /home/pi/stalcraft-bot"
```

> Если бот уже какое-то время работал на компьютере и набрал подписчиков —
> скопируй также `subscribers.json`, чтобы не потерять список.

## 2. Установить зависимости на Pi

Заходим на Pi по SSH:

```bash
ssh pi@IP_МАЛИНКИ
```

Дальше на самой Pi — создаём виртуальное окружение и ставим зависимости
(в новых Raspberry Pi OS ставить pip-пакеты в систему напрямую запрещено,
поэтому venv обязателен):

```bash
cd /home/pi/stalcraft-bot
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

## 3. Проверить, что бот запускается

```bash
venv/bin/python main.py
```

Должно появиться «Бот запущен. Начинаю мониторинг...» и количество подписчиков.
Останавливаем по `Ctrl+C` и идём настраивать автозапуск.

## 4. Настроить автозапуск (systemd)

```bash
sudo cp stalcraft-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable stalcraft-bot   # автозапуск при включении Pi
sudo systemctl start stalcraft-bot    # запустить прямо сейчас
```

> Если пользователь на Pi не `pi` — перед копированием поправь в
> `stalcraft-bot.service` строку `User=` и пути `/home/pi/...`.

## 5. Полезные команды

```bash
sudo systemctl status stalcraft-bot        # работает ли бот
journalctl -u stalcraft-bot -f             # смотреть логи вживую
journalctl -u stalcraft-bot --since today  # логи за сегодня
sudo systemctl restart stalcraft-bot       # перезапустить (после обновления main.py)
sudo systemctl stop stalcraft-bot          # остановить
```

## 6. Как обновлять бота

Поменял `main.py` на компьютере — копируешь и перезапускаешь:

```bash
scp main.py pi@IP_МАЛИНКИ:/home/pi/stalcraft-bot/
ssh pi@IP_МАЛИНКИ "sudo systemctl restart stalcraft-bot"
```

Для нового предмета не забудь скопировать и его картинку `{id}.png`.

## Что уже учтено в боте

- Бот сам перезапускается при падении (`Restart=always` в сервисе).
- На всех сетевых запросах стоят таймауты — зависший запрос не заморозит бота.
- Список подписчиков хранится в `subscribers.json` и переживает перезапуски.
- Логи видны через `journalctl` (буферизация вывода отключена в сервисе).

## Важно про безопасность

Все секреты (токен бота, Client-Secret) лежат в `.env`, который добавлен в
`.gitignore` — на git он не попадёт. На Pi файл `.env` копируется вручную через
`scp` (шаг 1). Если токен всё-таки утёк — перевыпусти его у @BotFather
(«Revoke current token») и обнови в `.env`.
