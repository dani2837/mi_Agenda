import html
import os
import re
import asyncio
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from app_settings import get_setting, is_reminder_enabled, set_setting
from database import get_connection, init_db
from weather_service import format_weather_for_bot, get_weather


load_dotenv()


def get_madrid_timezone():
    """Return Spain timezone, with a Windows-friendly fallback if tzdata is missing."""
    try:
        return ZoneInfo("Europe/Madrid")
    except ZoneInfoNotFoundError:
        return datetime.now().astimezone().tzinfo or timezone(timedelta(hours=1))


def add_task(
    title: str,
    priority: str = "normal",
    description: Optional[str] = None,
    due_date: Optional[str] = None,
) -> None:
    """Add a task to the same SQLite database used by the FastAPI app."""
    init_db()
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO tasks (
                title, description, priority, due_date, due_time, status,
                created_at, completed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                title.strip(),
                description,
                priority,
                due_date,
                None,
                "pending",
                datetime.now().isoformat(timespec="seconds"),
                None,
            ),
        )


def get_pending_tasks(due_date: Optional[str] = None):
    init_db()
    query = """
        SELECT * FROM tasks
        WHERE status = ?
    """
    params = ["pending"]

    if due_date:
        query += " AND due_date = ?"
        params.append(due_date)

    query += """
        ORDER BY
            CASE priority WHEN 'urgente' THEN 0 ELSE 1 END,
            CASE WHEN due_date IS NULL THEN 1 ELSE 0 END,
            due_date ASC,
            due_time ASC,
            created_at DESC
    """

    with get_connection() as connection:
        return connection.execute(query, params).fetchall()


def add_idea(title: str) -> None:
    init_db()
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO ideas (title, status, created_at, completed_at)
            VALUES (?, ?, ?, ?)
            """,
            (title.strip(), "pending", datetime.now().isoformat(timespec="seconds"), None),
        )


def get_pending_ideas():
    init_db()
    with get_connection() as connection:
        return connection.execute(
            """
            SELECT * FROM ideas
            WHERE status = ?
            ORDER BY created_at DESC
            """,
            ("pending",),
        ).fetchall()


def add_book(name: str, author: Optional[str] = None, description: Optional[str] = None) -> None:
    init_db()
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO books (name, author, description, status, created_at, completed_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                name.strip(),
                normalize_empty(author or ""),
                normalize_empty(description or ""),
                "pending",
                datetime.now().isoformat(timespec="seconds"),
                None,
            ),
        )


def add_series(name: str, season: Optional[str] = None, comment: Optional[str] = None) -> None:
    init_db()
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO series (name, season, comment, status, created_at, completed_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                name.strip(),
                normalize_empty(season or ""),
                normalize_empty(comment or ""),
                "pending",
                datetime.now().isoformat(timespec="seconds"),
                None,
            ),
        )


def add_movie(name: str, comment: Optional[str] = None) -> None:
    init_db()
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO movies (name, comment, status, created_at, completed_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                name.strip(),
                normalize_empty(comment or ""),
                "pending",
                datetime.now().isoformat(timespec="seconds"),
                None,
            ),
        )


def get_books():
    init_db()
    with get_connection() as connection:
        return connection.execute(
            """
            SELECT * FROM books
            ORDER BY
                CASE status WHEN 'pending' THEN 0 ELSE 1 END,
                created_at DESC
            """
        ).fetchall()


def get_series():
    init_db()
    with get_connection() as connection:
        return connection.execute(
            """
            SELECT * FROM series
            ORDER BY
                CASE status WHEN 'pending' THEN 0 ELSE 1 END,
                created_at DESC
            """
        ).fetchall()


def get_movies():
    init_db()
    with get_connection() as connection:
        return connection.execute(
            """
            SELECT * FROM movies
            ORDER BY
                CASE status WHEN 'pending' THEN 0 ELSE 1 END,
                created_at DESC
            """
        ).fetchall()


def add_shopping_item(title: str) -> None:
    init_db()
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO shopping_items (title, status, created_at, completed_at)
            VALUES (?, ?, ?, ?)
            """,
            (title.strip(), "pending", datetime.now().isoformat(timespec="seconds"), None),
        )


def get_shopping_items():
    init_db()
    with get_connection() as connection:
        return connection.execute(
            """
            SELECT * FROM shopping_items
            ORDER BY
                CASE status WHEN 'pending' THEN 0 ELSE 1 END,
                created_at DESC
            """
        ).fetchall()


def command_text(context: ContextTypes.DEFAULT_TYPE) -> str:
    return " ".join(context.args).strip()


def help_message() -> str:
    return (
        "Hola. Soy tu bot local de tareas.\n\n"
        "Comandos disponibles:\n"
        "/tarea titulo + descripcion + dd/mm/aaaa - crea una tarea normal\n"
        "/urgente titulo + descripcion + dd/mm/aaaa - crea una tarea urgente\n"
        "/idea texto - guarda una idea pendiente\n"
        "/ideas - muestra tus ideas pendientes\n"
        "/libro nombre + autor + descripcion - guarda un libro pendiente\n"
        "/serie nombre + temporada + comentario - guarda una serie pendiente\n"
        "/pelicula nombre + comentario - guarda una pelicula pendiente\n"
        "/libros - muestra tus libros guardados\n"
        "/series - muestra tus series guardadas\n"
        "/peliculas - muestra tus peliculas guardadas\n"
        "/hoy - muestra tareas pendientes de hoy\n"
        "/pendientes - muestra todas las tareas pendientes\n"
        "/comprar producto1, producto2 - anade productos a la lista de compra\n"
        "/listacompra - muestra la lista de compra\n"
        "/tiempo - muestra el tiempo de hoy en tu ciudad\n"
        "/info - muestra esta ayuda\n\n"
        "La descripcion y la fecha son opcionales.\n"
        "Si no indicas fecha, la tarea se guarda para manana.\n"
        "Ejemplo tarea: /tarea llamar a pepe, recuerdale la cita 17/06/2026\n"
        "Ejemplo idea: /idea preparar una plantilla semanal\n"
        "Ejemplo libro: /libro Dune + Frank Herbert + ciencia ficcion\n"
        "Ejemplo serie: /serie The Bear + temporada 2 + verla con calma\n"
        "Ejemplo pelicula: /pelicula Matrix + revision pendiente\n"
        "Ejemplo compra: /comprar leche, huevos, aceite"
    )


def normalize_empty(value: str) -> Optional[str]:
    value = value.strip()
    return value or None


def parse_spanish_date(value: str) -> str:
    try:
        return datetime.strptime(value.strip(), "%d/%m/%Y").date().isoformat()
    except ValueError as error:
        raise ValueError("La fecha debe tener formato dd/mm/aaaa. Ejemplo: 20/06/2026") from error


def looks_like_spanish_date(value: str) -> bool:
    return bool(re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", value.strip()))


def parse_task_input(text: str) -> tuple[str, Optional[str], Optional[str]]:
    text = text.strip()
    if text.startswith("-"):
        text = text[1:].strip()

    due_date = None
    trailing_date = re.search(r"(\d{1,2}/\d{1,2}/\d{4})$", text)
    if trailing_date:
        due_date = parse_spanish_date(trailing_date.group(1))
        text = text[: trailing_date.start()].rstrip(" ,+")

    # Allow both "+" and "," as separators for title, description and date.
    parts = [part.strip() for part in re.split(r"[+,]", text)]
    parts = [part for part in parts if part]

    if not parts:
        raise ValueError("Escribe el titulo de la tarea.")

    title = parts[0]
    description = None
    detail_parts = parts[1:]

    if due_date is None and detail_parts and looks_like_spanish_date(detail_parts[-1]):
        due_date = parse_spanish_date(detail_parts[-1])
        detail_parts = detail_parts[:-1]
    elif due_date is None and detail_parts and "/" in detail_parts[-1]:
        raise ValueError("La fecha debe tener formato dd/mm/aaaa. Ejemplo: 20/06/2026")

    if detail_parts:
        description = ", ".join(detail_parts)

    if due_date is None:
        due_date = (date.today() + timedelta(days=1)).isoformat()

    return title, normalize_empty(description or ""), due_date


def parse_shopping_items(text: str) -> list[str]:
    text = text.strip()
    if text.startswith("+"):
        text = text[1:].strip()

    return [item.strip() for item in text.split(",") if item.strip()]


def parse_plus_parts(text: str, max_parts: int) -> list[str]:
    text = text.strip()
    if text.startswith("+"):
        text = text[1:].strip()

    parts = [part.strip() for part in text.split("+")]
    parts = [part for part in parts if part]

    if len(parts) > max_parts:
        parts = parts[: max_parts - 1] + [" + ".join(parts[max_parts - 1 :])]

    return parts


def escape_text(value) -> str:
    return html.escape(str(value)) if value is not None else ""


def section_header(title: str) -> str:
    return f"<b>{escape_text(title)}</b>\n----------"


def trim_long_message(message: str) -> str:
    if len(message) > 3500:
        return message[:3500] + "\n\n<i>La lista es larga; abre la app web para ver el resto.</i>"
    return message


def format_task(task, index: int) -> str:
    date_text = task["due_date"] or "sin fecha"
    time_text = f" {task['due_time']}" if task["due_time"] else ""
    lines = [
        f"<b>{index}. {escape_text(task['title'])}</b>",
        f"<b>Prioridad:</b> {escape_text(task['priority'].upper())}",
        f"<b>Fecha:</b> {escape_text(date_text + time_text)}",
    ]
    if task["description"]:
        lines.append(f"<b>Descripcion:</b> {escape_text(task['description'])}")
    return "\n".join(lines)


def format_task_list(tasks, empty_message: str) -> str:
    if not tasks:
        return f"<i>{escape_text(empty_message)}</i>"

    blocks = [format_task(task, index) for index, task in enumerate(tasks, start=1)]
    return trim_long_message("\n\n".join(blocks))


def format_idea_list(ideas, empty_message: str) -> str:
    if not ideas:
        return f"<i>{escape_text(empty_message)}</i>"

    blocks = [
        "\n".join(
            [
                f"<b>{index}. {escape_text(idea['title'])}</b>",
                "<b>Estado:</b> PENDIENTE",
            ]
        )
        for index, idea in enumerate(ideas, start=1)
    ]
    return trim_long_message("\n\n".join(blocks))


def format_shopping_list(items) -> str:
    if not items:
        return "<i>La lista de compra esta vacia.</i>"

    lines = []
    for index, item in enumerate(items, start=1):
        marker = "OK" if item["status"] == "done" else "PENDIENTE"
        lines.append(f"<b>{index}. {escape_text(item['title'])}</b>\n<b>Estado:</b> {marker}")

    return trim_long_message("\n\n".join(lines))


def format_books_list(items) -> str:
    if not items:
        return "<i>No tienes libros guardados.</i>"

    lines = []
    for index, item in enumerate(items, start=1):
        if item["status"] == "read":
            marker = "LEIDO"
        elif item["status"] == "downloaded":
            marker = "DESCARGADO"
        else:
            marker = "PENDIENTE"
        block = [
            f"<b>{index}. {escape_text(item['name'])}</b>",
            f"<b>Estado:</b> {marker}",
        ]
        if item["author"]:
            block.append(f"<b>Autor:</b> {escape_text(item['author'])}")
        if item["description"]:
            block.append(f"<b>Descripcion:</b> {escape_text(item['description'])}")
        lines.append("\n".join(block))

    return trim_long_message("\n\n".join(lines))


def format_series_list(items) -> str:
    if not items:
        return "<i>No tienes series guardadas.</i>"

    lines = []
    for index, item in enumerate(items, start=1):
        marker = "VISTA" if item["status"] == "watched" else "PENDIENTE"
        block = [
            f"<b>{index}. {escape_text(item['name'])}</b>",
            f"<b>Estado:</b> {marker}",
        ]
        if item["season"]:
            block.append(f"<b>Temporada:</b> {escape_text(item['season'])}")
        if item["comment"]:
            block.append(f"<b>Comentario:</b> {escape_text(item['comment'])}")
        lines.append("\n".join(block))

    return trim_long_message("\n\n".join(lines))


def format_movies_list(items) -> str:
    if not items:
        return "<i>No tienes peliculas guardadas.</i>"

    lines = []
    for index, item in enumerate(items, start=1):
        marker = "VISTA" if item["status"] == "watched" else "PENDIENTE"
        block = [
            f"<b>{index}. {escape_text(item['name'])}</b>",
            f"<b>Estado:</b> {marker}",
        ]
        if item["comment"]:
            block.append(f"<b>Comentario:</b> {escape_text(item['comment'])}")
        lines.append("\n".join(block))

    return trim_long_message("\n\n".join(lines))


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat:
        set_setting("telegram_chat_id", str(update.effective_chat.id))
    await update.message.reply_text(help_message())


async def info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(help_message())


async def create_task_from_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    priority: str,
    label: str,
    example: str,
) -> None:
    text = command_text(context)
    if not text:
        await update.message.reply_text(f"Escribe una tarea. Ejemplo: {example}")
        return

    try:
        title, description, due_date = parse_task_input(text)
    except ValueError as error:
        await update.message.reply_text(str(error))
        return

    add_task(title, priority, description, due_date)

    details = [f"<u>{html.escape(label)} creada:</u> {html.escape(title)}"]
    if description:
        details.append(f"<u>Descripcion:</u> {html.escape(description)}")
    if due_date:
        details.append(f"<u>Fecha:</u> {html.escape(due_date)}")
    await update.message.reply_text("\n".join(details), parse_mode="HTML")


async def create_normal_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await create_task_from_command(
        update,
        context,
        "normal",
        "Tarea",
        "/tarea llamar al banco, preguntar por recibo, 20/06/2026",
    )


async def create_urgent_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await create_task_from_command(
        update,
        context,
        "urgente",
        "Tarea urgente",
        "/urgente pagar factura luz, vence pronto, 20/06/2026",
    )


async def create_idea(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = command_text(context)
    if not text:
        await update.message.reply_text("Escribe una idea. Ejemplo: /idea preparar una plantilla semanal")
        return

    add_idea(text)
    await update.message.reply_text(
        f"<u>Idea creada:</u> {html.escape(text)}",
        parse_mode="HTML",
    )


async def create_shopping_item(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = command_text(context)
    items = parse_shopping_items(text)

    if not items:
        await update.message.reply_text("Escribe que quieres comprar. Ejemplo: /comprar leche, huevos, aceite")
        return

    for item in items:
        add_shopping_item(item)

    if len(items) == 1:
        await update.message.reply_text(f"Producto anadido a la lista de compra: {items[0]}")
    else:
        await update.message.reply_text(
            "Productos anadidos a la lista de compra:\n" + "\n".join(f"- {item}" for item in items)
        )


async def create_book(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    parts = parse_plus_parts(command_text(context), 3)
    if not parts:
        await update.message.reply_text("Escribe un libro. Ejemplo: /libro Dune + Frank Herbert + ciencia ficcion")
        return

    name = parts[0]
    author = parts[1] if len(parts) > 1 else None
    description = parts[2] if len(parts) > 2 else None
    add_book(name, author, description)

    details = [f"<u>Libro creado:</u> {html.escape(name)}"]
    if author:
        details.append(f"<u>Autor:</u> {html.escape(author)}")
    if description:
        details.append(f"<u>Descripcion:</u> {html.escape(description)}")
    await update.message.reply_text("\n".join(details), parse_mode="HTML")


async def create_series(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    parts = parse_plus_parts(command_text(context), 3)
    if not parts:
        await update.message.reply_text("Escribe una serie. Ejemplo: /serie The Bear + temporada 2 + verla con calma")
        return

    name = parts[0]
    season = parts[1] if len(parts) > 1 else None
    comment = parts[2] if len(parts) > 2 else None
    add_series(name, season, comment)

    details = [f"<u>Serie creada:</u> {html.escape(name)}"]
    if season:
        details.append(f"<u>Temporada:</u> {html.escape(season)}")
    if comment:
        details.append(f"<u>Comentario:</u> {html.escape(comment)}")
    await update.message.reply_text("\n".join(details), parse_mode="HTML")


async def create_movie(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    parts = parse_plus_parts(command_text(context), 2)
    if not parts:
        await update.message.reply_text("Escribe una pelicula. Ejemplo: /pelicula Matrix + revision pendiente")
        return

    name = parts[0]
    comment = parts[1] if len(parts) > 1 else None
    add_movie(name, comment)

    details = [f"<u>Pelicula creada:</u> {html.escape(name)}"]
    if comment:
        details.append(f"<u>Comentario:</u> {html.escape(comment)}")
    await update.message.reply_text("\n".join(details), parse_mode="HTML")


async def shopping_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    items = get_shopping_items()
    message = f"{section_header('Lista de compra')}\n{format_shopping_list(items)}"
    await update.message.reply_text(message, parse_mode="HTML")


async def books_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = f"{section_header('Libros')}\n{format_books_list(get_books())}"
    await update.message.reply_text(message, parse_mode="HTML")


async def series_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = f"{section_header('Series')}\n{format_series_list(get_series())}"
    await update.message.reply_text(message, parse_mode="HTML")


async def movies_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = f"{section_header('Peliculas')}\n{format_movies_list(get_movies())}"
    await update.message.reply_text(message, parse_mode="HTML")


async def ideas_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = f"{section_header('Ideas pendientes')}\n{format_idea_list(get_pending_ideas(), 'No tienes ideas pendientes.')}"
    await update.message.reply_text(message, parse_mode="HTML")


async def today_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tasks = get_pending_tasks(date.today().isoformat())
    message = f"{section_header('Tareas de hoy')}\n{format_task_list(tasks, 'No tienes tareas pendientes para hoy.')}"
    await update.message.reply_text(message, parse_mode="HTML")


async def pending_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tasks = get_pending_tasks()
    message = f"{section_header('Tareas pendientes')}\n{format_task_list(tasks, 'No tienes tareas pendientes.')}"
    await update.message.reply_text(message, parse_mode="HTML")


async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = f"{section_header('Tiempo')}\n{escape_text(format_weather_for_bot(get_weather()))}"
    await update.message.reply_text(message, parse_mode="HTML")


def build_daily_reminder_message() -> str:
    today = date.today().isoformat()
    tasks = get_pending_tasks(today)
    task_text = format_task_list(tasks, "No tienes tareas pendientes para hoy.")
    weather_text = format_weather_for_bot(get_weather())

    return (
        "<b>Buenos dias.</b>\n\n"
        f"{section_header('Tiempo de hoy')}\n"
        f"{escape_text(weather_text)}\n\n"
        f"{section_header('Tareas de hoy')}\n"
        f"{task_text}"
    )


async def daily_reminder_loop(application: Application) -> None:
    madrid_timezone = get_madrid_timezone()

    while True:
        now = datetime.now(madrid_timezone)
        next_run = now.replace(hour=9, minute=0, second=0, microsecond=0)
        if now >= next_run:
            next_run += timedelta(days=1)

        wait_seconds = max(1, (next_run - now).total_seconds())
        print(f"Recordatorio diario programado para {next_run.isoformat()}")
        await asyncio.sleep(wait_seconds)

        run_day = next_run.date().isoformat()
        last_sent = get_setting("daily_reminder_last_sent", "")
        chat_id = get_setting("telegram_chat_id", "")

        if is_reminder_enabled() and chat_id and last_sent != run_day:
            try:
                await application.bot.send_message(
                    chat_id=int(chat_id),
                    text=build_daily_reminder_message(),
                    parse_mode="HTML",
                )
                set_setting("daily_reminder_last_sent", run_day)
                print(f"Recordatorio diario enviado para {run_day}")
            except Exception as error:
                print(f"No se pudo enviar el recordatorio: {error}")
        else:
            print("Recordatorio diario omitido: desactivado, sin chat o ya enviado.")


async def start_background_jobs(application: Application) -> None:
    asyncio.create_task(daily_reminder_loop(application))


def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token or token == "mi_token_aqui":
        raise RuntimeError("Configura TELEGRAM_BOT_TOKEN en el archivo .env")

    init_db()

    application = Application.builder().token(token).post_init(start_background_jobs).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("info", info))
    application.add_handler(CommandHandler("tarea", create_normal_task))
    application.add_handler(CommandHandler("urgente", create_urgent_task))
    application.add_handler(CommandHandler("idea", create_idea))
    application.add_handler(CommandHandler("ideas", ideas_list))
    application.add_handler(CommandHandler("libro", create_book))
    application.add_handler(CommandHandler("serie", create_series))
    application.add_handler(CommandHandler("pelicula", create_movie))
    application.add_handler(CommandHandler("libros", books_list))
    application.add_handler(CommandHandler("series", series_list))
    application.add_handler(CommandHandler("peliculas", movies_list))
    application.add_handler(CommandHandler("comprar", create_shopping_item))
    application.add_handler(CommandHandler("listacompra", shopping_list))
    application.add_handler(CommandHandler("tiempo", weather_command))
    application.add_handler(CommandHandler("hoy", today_tasks))
    application.add_handler(CommandHandler("pendientes", pending_tasks))

    print("Bot de tareas iniciado. Pulsa Ctrl+C para detenerlo.")
    application.run_polling()


if __name__ == "__main__":
    main()
