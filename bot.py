#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════
#  Telegram Bot — Sales Dashboard
#  - /start → приветствие + кнопка открыть Mini App
#  - Ежедневная статистика в 20:00 (по Бишкеку, UTC+6)
# ═══════════════════════════════════════════════════════════

import logging
import requests
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes

# ─── КОНФИГУРАЦИЯ ───────────────────────────────────────────
BOT_TOKEN     = '8453964932:AAESkzNlRCD4T2rt7aPBqui0oEFzzv5LZeg'
CHAT_ID       = 1935081717
MINI_APP_URL  = 'https://nurankerim3332-cpu.github.io/dashordboed/'
SHEET_ID      = '1Yok6bv-VyNRZh8o-q2uEbFqupdULZz04kavOY8eYyiA'
API_KEY       = 'AIzaSyDl76JFeNHkKcZFW92BxuicnqGS_d9I-vg'
SHEET_NAME    = 'Sales'
TIMEZONE      = timezone(timedelta(hours=6))  # Бишкек UTC+6
DAILY_HOUR    = 20  # время отправки статистики (20:00)
# ────────────────────────────────────────────────────────────

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def get_sales_data():
    """Получить данные из Google Sheets."""
    url = (
        f'https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}'
        f'/values/{SHEET_NAME}!A2:E5000?key={API_KEY}'
    )
    try:
        res = requests.get(url, timeout=10)
        data = res.json()
        rows = data.get('values', [])
        sales = []
        for r in rows:
            if len(r) >= 3 and r[0] and r[1]:
                sales.append({
                    'date':     r[0].strip(),
                    'employee': r[1].strip(),
                    'amount':   float(r[2]) if r[2] else 0,
                    'salary':   float(r[3]) if len(r) > 3 and r[3] else 0,
                    'comment':  r[4] if len(r) > 4 else ''
                })
        return sales
    except Exception as e:
        logger.error(f'Ошибка загрузки данных: {e}')
        return []


def norm_date(s):
    """Нормализовать дату к формату YYYY-MM-DD."""
    if not s:
        return ''
    if '.' in s:
        parts = s.split('.')
        if len(parts) == 3:
            d, m, y = parts
            return f'{y}-{m.zfill(2)}-{d.zfill(2)}'
    return s[:10]


def fmt_money(n):
    """Форматировать число как деньги."""
    if n >= 1_000_000:
        return f'{n/1_000_000:.1f}M'
    if n >= 1_000:
        return f'{round(n/1_000)}K'
    return str(round(n))


def build_daily_report():
    """Собрать текст ежедневного отчёта."""
    now = datetime.now(TIMEZONE)
    today = now.strftime('%Y-%m-%d')
    today_ru = now.strftime('%d.%m.%Y')

    sales = get_sales_data()
    day_sales = [s for s in sales if norm_date(s['date']) == today]

    if not day_sales:
        return f'📊 *Статистика за {today_ru}*\n\nСегодня продаж не зафиксировано.'

    # Агрегируем по сотруднику
    by_emp = {}
    for s in day_sales:
        name = s['employee']
        if name not in by_emp:
            by_emp[name] = {'earned': 0, 'salary': 0, 'count': 0}
        by_emp[name]['earned'] += s['amount']
        if s['salary'] > 0:
            by_emp[name]['salary'] = s['salary']
        by_emp[name]['count'] += 1

    total = sum(v['earned'] for v in by_emp.values())
    sorted_emp = sorted(by_emp.items(), key=lambda x: x[1]['earned'], reverse=True)

    medals = ['🥇', '🥈', '🥉']
    lines = [f'📊 *Статистика за {today_ru}*\n']

    for i, (name, d) in enumerate(sorted_emp):
        medal = medals[i] if i < 3 else f'{i+1}.'
        earned = d['earned']
        salary = d['salary']

        if salary > 0:
            pct = (earned / salary * 100) - 100
            pct_str = f'+{pct:.0f}%' if pct > 0 else f'{pct:.0f}%'
            pct_icon = '📈' if pct > 0 else '📉'
            lines.append(
                f'{medal} *{name}*\n'
                f'   💰 {fmt_money(earned)} сом  {pct_icon} {pct_str}\n'
            )
        else:
            lines.append(
                f'{medal} *{name}*\n'
                f'   💰 {fmt_money(earned)} сом\n'
            )

    lines.append(f'\n💼 *Итого за день: {fmt_money(total)} сом*')
    lines.append(f'👥 Сотрудников: {len(by_emp)} | Записей: {len(day_sales)}')

    return '\n'.join(lines)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start."""
    user = update.effective_user
    name = user.first_name or 'друг'

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(
            text='📊 Открыть Dashboard',
            web_app=WebAppInfo(url=MINI_APP_URL)
        )
    ]])

    text = (
        f'Привет, *{name}*! 👋\n\n'
        f'Я бот для отслеживания продаж команды.\n\n'
        f'🔹 Открывай дашборд — смотри статистику\n'
        f'🔹 Добавляй продажи прямо из приложения\n'
        f'🔹 Каждый день в *{DAILY_HOUR}:00* получай сводку\n\n'
        f'Нажми кнопку ниже 👇'
    )

    await update.message.reply_text(
        text,
        parse_mode='Markdown',
        reply_markup=keyboard
    )


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /stats — статистика прямо сейчас."""
    await update.message.reply_text('⏳ Загружаю данные...')
    report = build_daily_report()
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton('📊 Открыть Dashboard', web_app=WebAppInfo(url=MINI_APP_URL))
    ]])
    await update.message.reply_text(report, parse_mode='Markdown', reply_markup=keyboard)


def send_daily_stats(app):
    """Отправить ежедневную статистику (вызывается планировщиком)."""
    import asyncio
    report = build_daily_report()
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton('📊 Открыть Dashboard', web_app=WebAppInfo(url=MINI_APP_URL))
    ]])
    asyncio.run_coroutine_threadsafe(
        app.bot.send_message(
            chat_id=CHAT_ID,
            text=report,
            parse_mode='Markdown',
            reply_markup=keyboard
        ),
        app.bot.loop if hasattr(app.bot, 'loop') else asyncio.get_event_loop()
    )


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Команды
    app.add_handler(CommandHandler('start', cmd_start))
    app.add_handler(CommandHandler('stats', cmd_stats))

    # Планировщик ежедневной статистики
    scheduler = BackgroundScheduler(timezone=str(TIMEZONE))
    scheduler.add_job(
        lambda: send_daily_stats(app),
        trigger='cron',
        hour=DAILY_HOUR,
        minute=0
    )
    scheduler.start()
    logger.info(f'Планировщик запущен. Статистика каждый день в {DAILY_HOUR}:00 (Бишкек)')

    logger.info('Бот запущен...')
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
