#!/usr/bin/env python3
import logging
import asyncio
import requests
from datetime import datetime, timezone, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes, filters

# ─── КОНФИГУРАЦИЯ ───────────────────────────────────────────
BOT_TOKEN    = '8453964932:AAESkzNlRCD4T2rt7aPBqui0oEFzzv5LZeg'
CHAT_ID      = -1003865772640
MINI_APP_URL = 'https://nurankerim3332-cpu.github.io/dashordboed/'
SHEET_ID     = '1Yok6bv-VyNRZh8o-q2uEbFqupdULZz04kavOY8eYyiA'
API_KEY      = 'AIzaSyDl76JFeNHkKcZFW92BxuicnqGS_d9I-vg'
SHEET_NAME   = 'Sales'
DAILY_HOUR   = 20
TZ           = timezone(timedelta(hours=6))
# ────────────────────────────────────────────────────────────

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)


def get_sales():
    url = (f'https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}'
           f'/values/{SHEET_NAME}!A2:E5000?key={API_KEY}')
    try:
        data = requests.get(url, timeout=10).json()
        result = []
        for r in data.get('values', []):
            if len(r) >= 3 and r[0] and r[1]:
                result.append({
                    'date':     r[0].strip(),
                    'employee': r[1].strip(),
                    'amount':   float(r[2]) if r[2] else 0,
                    'salary':   float(r[3]) if len(r) > 3 and r[3] else 0,
                })
        return result
    except Exception as e:
        logger.error(f'Ошибка загрузки: {e}')
        return []


def norm_date(s):
    if not s: return ''
    if '.' in s:
        p = s.split('.')
        if len(p) == 3:
            return f'{p[2]}-{p[1].zfill(2)}-{p[0].zfill(2)}'
    return s[:10]


def fmt_money(n):
    if n >= 1_000_000: return f'{n/1_000_000:.1f}M'
    if n >= 1_000: return f'{round(n/1_000)}K'
    return str(round(n))


def build_report():
    now       = datetime.now(TZ)
    today     = now.strftime('%Y-%m-%d')
    today_ru  = now.strftime('%d.%m.%Y')
    day_sales = [s for s in get_sales() if norm_date(s['date']) == today]

    if not day_sales:
        return f'📊 *Статистика за {today_ru}*\n\nСегодня продаж не зафиксировано.'

    by_emp = {}
    for s in day_sales:
        n = s['employee']
        if n not in by_emp:
            by_emp[n] = {'earned': 0, 'salary': 0, 'count': 0}
        by_emp[n]['earned'] += s['amount']
        if s['salary'] > 0:
            by_emp[n]['salary'] = s['salary']
        by_emp[n]['count'] += 1

    total      = sum(v['earned'] for v in by_emp.values())
    sorted_emp = sorted(by_emp.items(), key=lambda x: x[1]['earned'], reverse=True)
    medals     = ['🥇', '🥈', '🥉']
    lines      = [f'📊 *Статистика за {today_ru}*\n']

    for i, (name, d) in enumerate(sorted_emp):
        medal = medals[i] if i < 3 else f'{i+1}.'
        if d['salary'] > 0:
            pct  = (d['earned'] / d['salary'] * 100) - 100
            ps   = f'+{pct:.0f}%' if pct > 0 else f'{pct:.0f}%'
            icon = '📈' if pct > 0 else '📉'
            lines.append(f"{medal} *{name}*\n   💰 {fmt_money(d['earned'])} сом  {icon} {ps}\n")
        else:
            lines.append(f"{medal} *{name}*\n   💰 {fmt_money(d['earned'])} сом\n")

    lines.append(f'\n💼 *Итого: {fmt_money(total)} сом*')
    lines.append(f'👥 Сотрудников: {len(by_emp)} | Записей: {len(day_sales)}')
    return '\n'.join(lines)


def build_top():
    """Топ сотрудников за всё время по сумме продаж."""
    all_sales = get_sales()
    if not all_sales:
        return '🏆 *Топ сотрудников*\n\nДанных пока нет.'

    by_emp = {}
    for s in all_sales:
        n = s['employee']
        if n not in by_emp:
            by_emp[n] = {'earned': 0, 'count': 0}
        by_emp[n]['earned'] += s['amount']
        by_emp[n]['count']  += 1

    sorted_emp = sorted(by_emp.items(), key=lambda x: x[1]['earned'], reverse=True)
    medals = ['🥇', '🥈', '🥉']
    lines  = ['🏆 *Топ сотрудников за всё время*\n']

    for i, (name, d) in enumerate(sorted_emp):
        medal = medals[i] if i < 3 else f'{i+1}.'
        lines.append(
            f"{medal} *{name}*\n"
            f"   💰 {fmt_money(d['earned'])} сом  |  📋 {d['count']} продаж\n"
        )

    total_all = sum(v['earned'] for v in by_emp.values())
    lines.append(f'\n💼 *Общий оборот: {fmt_money(total_all)} сом*')
    lines.append(f'👥 Всего сотрудников: {len(by_emp)}')
    return '\n'.join(lines)


def build_employees():
    """Список всех сотрудников с кратким резюме."""
    all_sales = get_sales()
    if not all_sales:
        return '📋 *Список сотрудников*\n\nДанных пока нет.'

    by_emp = {}
    for s in all_sales:
        n = s['employee']
        nd = norm_date(s['date'])
        if n not in by_emp:
            by_emp[n] = {'earned': 0, 'count': 0, 'last_date': nd, 'salary': 0}
        by_emp[n]['earned'] += s['amount']
        by_emp[n]['count']  += 1
        if s['salary'] > 0:
            by_emp[n]['salary'] = s['salary']
        if nd > by_emp[n]['last_date']:
            by_emp[n]['last_date'] = nd

    sorted_emp = sorted(by_emp.items(), key=lambda x: x[0])  # по алфавиту
    lines = [f'📋 *Список сотрудников ({len(by_emp)} чел.)*\n']

    for name, d in sorted_emp:
        try:
            ld = datetime.strptime(d['last_date'], '%Y-%m-%d').strftime('%d.%m.%Y')
        except Exception:
            ld = d['last_date']

        salary_line = f"  📌 План: {fmt_money(d['salary'])} сом\n" if d['salary'] > 0 else ''
        lines.append(
            f"👤 *{name}*\n"
            f"  💰 Заработано: {fmt_money(d['earned'])} сом\n"
            f"  📋 Продаж: {d['count']}\n"
            f"{salary_line}"
            f"  🕐 Последняя продажа: {ld}\n"
        )

    return '\n'.join(lines)


def open_btn(in_group=False):
    if in_group:
        return InlineKeyboardMarkup([[
            InlineKeyboardButton('📊 Открыть Dashboard', url=MINI_APP_URL)
        ]])
    else:
        return InlineKeyboardMarkup([[
            InlineKeyboardButton('📊 Открыть Dashboard', web_app=WebAppInfo(url=MINI_APP_URL))
        ]])


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    in_group = update.message.chat.type in ('group', 'supergroup')
    name = update.effective_user.first_name or 'друг'
    await update.message.reply_text(
        f'Привет, *{name}*! 👋\n\n'
        f'Я бот для отслеживания продаж команды.\n\n'
        f'📌 *Доступные команды:*\n'
        f'🔹 /stats — статистика за сегодня\n'
        f'🔹 /top — топ сотрудников за всё время\n'
        f'🔹 /employees — список всех сотрудников\n\n'
        f'Каждый день в *{DAILY_HOUR}:00* получай автосводку 👇',
        parse_mode='Markdown',
        reply_markup=open_btn(in_group)
    )


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    in_group = update.message.chat.type in ('group', 'supergroup')
    await update.message.reply_text('⏳ Загружаю данные...')
    await update.message.reply_text(
        build_report(),
        parse_mode='Markdown',
        reply_markup=open_btn(in_group)
    )


async def cmd_top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    in_group = update.message.chat.type in ('group', 'supergroup')
    await update.message.reply_text('⏳ Загружаю данные...')
    await update.message.reply_text(
        build_top(),
        parse_mode='Markdown',
        reply_markup=open_btn(in_group)
    )


async def cmd_employees(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    in_group = update.message.chat.type in ('group', 'supergroup')
    await update.message.reply_text('⏳ Загружаю данные...')
    await update.message.reply_text(
        build_employees(),
        parse_mode='Markdown',
        reply_markup=open_btn(in_group)
    )


async def daily_scheduler(bot):
    while True:
        now    = datetime.now(TZ)
        target = now.replace(hour=DAILY_HOUR, minute=0, second=0, microsecond=0)
        if now >= target:
            target += timedelta(days=1)
        secs = (target - now).total_seconds()
        logger.info(f'Следующая рассылка через {secs/3600:.1f} ч ({target.strftime("%d.%m %H:%M")})')
        await asyncio.sleep(secs)
        try:
            await bot.send_message(
                chat_id=CHAT_ID,
                text=build_report(),
                parse_mode='Markdown',
                reply_markup=open_btn(in_group=True)
            )
            logger.info('Статистика отправлена!')
        except Exception as e:
            logger.error(f'Ошибка отправки: {e}')


async def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler('start',     cmd_start,     filters=filters.ALL))
    app.add_handler(CommandHandler('stats',     cmd_stats,     filters=filters.ALL))
    app.add_handler(CommandHandler('top',       cmd_top,       filters=filters.ALL))
    app.add_handler(CommandHandler('employees', cmd_employees, filters=filters.ALL))

    async with app:
        await app.start()
        await app.updater.start_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )
        logger.info('Бот запущен!')
        await daily_scheduler(app.bot)


if __name__ == '__main__':
    asyncio.run(main())
