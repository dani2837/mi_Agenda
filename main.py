from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app_settings import get_reminder_status, is_reminder_enabled, set_reminder_enabled
from database import get_connection, init_db
from weather_service import get_weather


app = FastAPI(title="Mi App de Tareas")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


MEDIA_CONFIG = {
    "books": {
        "path": "/libros",
        "table": "books",
        "active_page": "books",
        "title": "Libros",
        "singular": "Libro",
        "name_label": "Nombre",
        "name_placeholder": "Ej. El nombre del viento",
        "pending_label": "Pendientes",
        "done_label": "Leidos",
        "done_status": "read",
        "done_action": "Leido",
        "fields": [
            {"name": "author", "label": "Autor", "placeholder": "Ej. Patrick Rothfuss", "type": "input"},
            {"name": "description", "label": "Descripcion", "placeholder": "Notas o motivo por el que quieres leerlo", "type": "textarea"},
        ],
    },
    "series": {
        "path": "/series",
        "table": "series",
        "active_page": "series",
        "title": "Series",
        "singular": "Serie",
        "name_label": "Nombre",
        "name_placeholder": "Ej. The Bear",
        "pending_label": "Pendientes",
        "done_label": "Vistas",
        "done_status": "watched",
        "done_action": "Vista",
        "fields": [
            {"name": "season", "label": "Temporada", "placeholder": "Ej. Temporada 2", "type": "input"},
            {"name": "comment", "label": "Comentario", "placeholder": "Notas o recomendaciones", "type": "textarea"},
        ],
    },
    "movies": {
        "path": "/peliculas",
        "table": "movies",
        "active_page": "movies",
        "title": "Peliculas",
        "singular": "Pelicula",
        "name_label": "Nombre",
        "name_placeholder": "Ej. Dune",
        "pending_label": "Pendientes",
        "done_label": "Vistas",
        "done_status": "watched",
        "done_action": "Vista",
        "fields": [
            {"name": "comment", "label": "Comentario", "placeholder": "Notas o por que quieres verla", "type": "textarea"},
        ],
    },
}


@app.on_event("startup")
def on_startup():
    init_db()


def normalize_optional(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = value.strip()
    return value or None


def redirect_to_home(filter_name: Optional[str] = None) -> RedirectResponse:
    url = "/"
    if filter_name:
        url = f"/?filter={filter_name}"
    return RedirectResponse(url=url, status_code=303)


def redirect_to_shopping() -> RedirectResponse:
    return RedirectResponse(url="/compra", status_code=303)


def redirect_to_ideas(filter_name: Optional[str] = None) -> RedirectResponse:
    url = "/ideas"
    if filter_name:
        url = f"/ideas?filter={filter_name}"
    return RedirectResponse(url=url, status_code=303)


def redirect_to_media(section: str, filter_name: Optional[str] = None) -> RedirectResponse:
    config = MEDIA_CONFIG.get(section, MEDIA_CONFIG["books"])
    url = config["path"]
    if filter_name:
        url = f"{url}?filter={filter_name}"
    return RedirectResponse(url=url, status_code=303)


def redirect_to_url(url: str) -> RedirectResponse:
    if not url.startswith("/"):
        url = "/"
    return RedirectResponse(url=url, status_code=303)


def build_task_query(filter_name: str) -> tuple[str, list[str]]:
    today = date.today().isoformat()
    base_query = "SELECT * FROM tasks"
    conditions = []
    params = []

    if filter_name == "hechas":
        conditions.append("status = ?")
        params.append("done")
    elif filter_name == "pendientes":
        conditions.append("status = ?")
        params.append("pending")
    elif filter_name == "urgentes":
        conditions.append("priority = ?")
        params.append("urgente")
    elif filter_name == "hoy":
        conditions.append("due_date = ?")
        params.append(today)
    elif filter_name == "vencidas":
        conditions.append("status = ?")
        conditions.append("due_date IS NOT NULL")
        conditions.append("due_date < ?")
        params.extend(["pending", today])

    if conditions:
        base_query += " WHERE " + " AND ".join(conditions)

    base_query += """
        ORDER BY
            CASE status WHEN 'pending' THEN 0 ELSE 1 END,
            CASE priority WHEN 'urgente' THEN 0 ELSE 1 END,
            CASE WHEN due_date IS NULL THEN 1 ELSE 0 END,
            due_date ASC,
            due_time ASC,
            created_at DESC
    """
    return base_query, params


def get_tasks(filter_name: str):
    query, params = build_task_query(filter_name)
    with get_connection() as connection:
        return connection.execute(query, params).fetchall()


def get_ideas(filter_name: str):
    conditions = []
    params = []
    query = "SELECT * FROM ideas"

    if filter_name == "hechas":
        conditions.append("status = ?")
        params.append("done")
    else:
        conditions.append("status = ?")
        params.append("pending")

    query += " WHERE " + " AND ".join(conditions)
    query += """
        ORDER BY
            CASE status WHEN 'pending' THEN 0 ELSE 1 END,
            created_at DESC
    """

    with get_connection() as connection:
        return connection.execute(query, params).fetchall()


def group_pending_tasks(tasks):
    today = date.today().isoformat()
    overdue_tasks = []
    today_tasks = []
    future_groups = {}
    no_date_tasks = []

    for task in tasks:
        due_date = task["due_date"]
        if not due_date:
            no_date_tasks.append(task)
        elif due_date < today:
            overdue_tasks.append(task)
        elif due_date == today:
            today_tasks.append(task)
        else:
            future_groups.setdefault(due_date, []).append(task)

    sections = []
    if overdue_tasks:
        sections.append(
            {
                "label": "VENCIDAS",
                "detail": "Pendientes con fecha anterior a hoy",
                "class": "overdue",
                "tasks": overdue_tasks,
            }
        )
    if today_tasks:
        sections.append(
            {
                "label": "HOY",
                "detail": "Para completar durante el día",
                "class": "today",
                "tasks": today_tasks,
            }
        )

    for due_date in sorted(future_groups):
        sections.append(
            {
                "label": due_date,
                "detail": "Próximas tareas",
                "class": "future",
                "tasks": future_groups[due_date],
            }
        )

    if no_date_tasks:
        sections.append(
            {
                "label": "SIN FECHA",
                "detail": "Pendientes sin día asignado",
                "class": "no-date",
                "tasks": no_date_tasks,
            }
        )

    return sections


def count_today_tasks() -> int:
    today = date.today().isoformat()
    with get_connection() as connection:
        row = connection.execute(
            "SELECT COUNT(*) AS total FROM tasks WHERE due_date = ? AND status = ?",
            (today, "pending"),
        ).fetchone()
    return row["total"]


def count_pending_ideas() -> int:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT COUNT(*) AS total FROM ideas WHERE status = ?",
            ("pending",),
        ).fetchone()
    return row["total"]


def get_shopping_items():
    with get_connection() as connection:
        return connection.execute(
            """
            SELECT * FROM shopping_items
            ORDER BY
                CASE status WHEN 'pending' THEN 0 ELSE 1 END,
                created_at DESC
            """
        ).fetchall()


def get_media_items(section: str, filter_name: str):
    config = MEDIA_CONFIG[section]
    table = config["table"]
    done_status = config["done_status"]

    with get_connection() as connection:
        if section == "books" and filter_name != "hechas":
            return connection.execute(
                """
                SELECT * FROM books
                WHERE status IN (?, ?)
                ORDER BY
                    CASE status WHEN 'pending' THEN 0 WHEN 'downloaded' THEN 1 ELSE 2 END,
                    created_at DESC
                """,
                ("pending", "downloaded"),
            ).fetchall()

        status = done_status if filter_name == "hechas" else "pending"
        return connection.execute(
            f"""
            SELECT * FROM {table}
            WHERE status = ?
            ORDER BY created_at DESC
            """,
            (status,),
        ).fetchall()


@app.get("/")
def index(request: Request, filter: str = "pendientes"):
    allowed_filters = {"pendientes", "hechas", "urgentes", "hoy", "vencidas"}
    active_filter = filter if filter in allowed_filters else "pendientes"
    today = date.today().isoformat()
    tasks = get_tasks(active_filter)

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "tasks": tasks,
            "task_sections": group_pending_tasks(tasks) if active_filter == "pendientes" else [],
            "active_filter": active_filter,
            "active_page": "tasks",
            "today": today,
            "today_count": count_today_tasks(),
            "weather": get_weather(),
            "reminder": get_reminder_status(),
        },
    )


@app.post("/tasks")
def create_task(
    item_type: str = Form("task"),
    title: str = Form(...),
    description: Optional[str] = Form(None),
    priority: str = Form("normal"),
    due_date: Optional[str] = Form(None),
    due_time: Optional[str] = Form(None),
):
    if item_type == "idea":
        clean_title = title.strip()
        if clean_title:
            with get_connection() as connection:
                connection.execute(
                    """
                    INSERT INTO ideas (title, status, created_at, completed_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (clean_title, "pending", datetime.now().isoformat(timespec="seconds"), None),
                )
        return redirect_to_ideas()

    allowed_priorities = {"normal", "urgente"}
    clean_priority = priority if priority in allowed_priorities else "normal"

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
                normalize_optional(description),
                clean_priority,
                normalize_optional(due_date),
                normalize_optional(due_time),
                "pending",
                datetime.now().isoformat(timespec="seconds"),
                None,
            ),
        )

    return redirect_to_home()


@app.get("/ideas")
def ideas(request: Request, filter: str = "pendientes"):
    allowed_filters = {"pendientes", "hechas"}
    active_filter = filter if filter in allowed_filters else "pendientes"

    return templates.TemplateResponse(
        "ideas.html",
        {
            "request": request,
            "ideas": get_ideas(active_filter),
            "active_filter": active_filter,
            "active_page": "ideas",
            "today_count": count_today_tasks(),
            "pending_ideas_count": count_pending_ideas(),
            "weather": get_weather(),
            "reminder": get_reminder_status(),
        },
    )


@app.post("/ideas/{idea_id}/complete")
def complete_idea(idea_id: int, active_filter: Optional[str] = Form(None)):
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE ideas
            SET status = ?, completed_at = ?
            WHERE id = ?
            """,
            ("done", datetime.now().isoformat(timespec="seconds"), idea_id),
        )
    return redirect_to_ideas(active_filter)


@app.post("/ideas/{idea_id}/delete")
def delete_idea(idea_id: int, active_filter: Optional[str] = Form(None)):
    with get_connection() as connection:
        connection.execute("DELETE FROM ideas WHERE id = ?", (idea_id,))
    return redirect_to_ideas(active_filter)


@app.post("/tasks/{task_id}/complete")
def complete_task(task_id: int):
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE tasks
            SET status = ?, completed_at = ?
            WHERE id = ?
            """,
            ("done", datetime.now().isoformat(timespec="seconds"), task_id),
        )
    return redirect_to_home()


@app.post("/tasks/{task_id}/delete")
def delete_task(task_id: int):
    with get_connection() as connection:
        connection.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    return redirect_to_home()


@app.post("/tasks/{task_id}/postpone")
def postpone_task(
    task_id: int,
    due_date: Optional[str] = Form(None),
    due_time: Optional[str] = Form(None),
    active_filter: Optional[str] = Form(None),
):
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE tasks
            SET due_date = ?, due_time = ?
            WHERE id = ?
            """,
            (normalize_optional(due_date), normalize_optional(due_time), task_id),
        )
    return redirect_to_home(active_filter)


@app.post("/tasks/{task_id}/postpone-day")
def postpone_task_one_day(
    task_id: int,
    active_filter: Optional[str] = Form(None),
):
    today = date.today()

    with get_connection() as connection:
        task = connection.execute(
            "SELECT due_date FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()

        base_date = today
        if task and task["due_date"]:
            try:
                base_date = date.fromisoformat(task["due_date"])
            except ValueError:
                base_date = today

        new_date = (base_date + timedelta(days=1)).isoformat()
        connection.execute(
            "UPDATE tasks SET due_date = ? WHERE id = ?",
            (new_date, task_id),
        )

    return redirect_to_home(active_filter)


@app.post("/reminder/toggle")
def toggle_reminder(next_url: str = Form("/")):
    set_reminder_enabled(not is_reminder_enabled())
    return redirect_to_url(next_url)


@app.get("/compra")
def shopping_list(request: Request):
    return templates.TemplateResponse(
        "shopping.html",
        {
            "request": request,
            "items": get_shopping_items(),
            "active_page": "shopping",
            "today_count": count_today_tasks(),
            "weather": get_weather(),
            "reminder": get_reminder_status(),
        },
    )


@app.post("/shopping")
def create_shopping_item(title: str = Form(...)):
    title = title.strip()
    if title:
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO shopping_items (title, status, created_at, completed_at)
                VALUES (?, ?, ?, ?)
                """,
                (title, "pending", datetime.now().isoformat(timespec="seconds"), None),
            )
    return redirect_to_shopping()


@app.post("/shopping/{item_id}/toggle")
def toggle_shopping_item(item_id: int):
    with get_connection() as connection:
        item = connection.execute(
            "SELECT status FROM shopping_items WHERE id = ?",
            (item_id,),
        ).fetchone()
        if item and item["status"] == "done":
            connection.execute(
                "UPDATE shopping_items SET status = ?, completed_at = ? WHERE id = ?",
                ("pending", None, item_id),
            )
        elif item:
            connection.execute(
                "UPDATE shopping_items SET status = ?, completed_at = ? WHERE id = ?",
                ("done", datetime.now().isoformat(timespec="seconds"), item_id),
            )
    return redirect_to_shopping()


@app.post("/shopping/{item_id}/delete")
def delete_shopping_item(item_id: int):
    with get_connection() as connection:
        connection.execute("DELETE FROM shopping_items WHERE id = ?", (item_id,))
    return redirect_to_shopping()


@app.post("/shopping/clear")
def clear_shopping_list():
    with get_connection() as connection:
        connection.execute("DELETE FROM shopping_items")
    return redirect_to_shopping()


@app.get("/libros")
def books(request: Request, filter: str = "pendientes"):
    return media_page(request, "books", filter)


@app.get("/series")
def series_page(request: Request, filter: str = "pendientes"):
    return media_page(request, "series", filter)


@app.get("/peliculas")
def movies(request: Request, filter: str = "pendientes"):
    return media_page(request, "movies", filter)


def media_page(request: Request, section: str, filter_name: str):
    active_filter = filter_name if filter_name in {"pendientes", "hechas"} else "pendientes"
    config = MEDIA_CONFIG[section]

    return templates.TemplateResponse(
        "media.html",
        {
            "request": request,
            "config": config,
            "section": section,
            "items": get_media_items(section, active_filter),
            "active_filter": active_filter,
            "active_page": config["active_page"],
            "today_count": count_today_tasks(),
            "weather": get_weather(),
            "reminder": get_reminder_status(),
        },
    )


@app.post("/media/{section}")
def create_media_item(
    section: str,
    name: str = Form(...),
    author: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    season: Optional[str] = Form(None),
    comment: Optional[str] = Form(None),
):
    if section not in MEDIA_CONFIG:
        return redirect_to_home()

    config = MEDIA_CONFIG[section]
    table = config["table"]
    clean_name = name.strip()
    if not clean_name:
        return redirect_to_media(section)

    now = datetime.now().isoformat(timespec="seconds")
    with get_connection() as connection:
        if section == "books":
            connection.execute(
                """
                INSERT INTO books (name, author, description, status, created_at, completed_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (clean_name, normalize_optional(author), normalize_optional(description), "pending", now, None),
            )
        elif section == "series":
            connection.execute(
                """
                INSERT INTO series (name, season, comment, status, created_at, completed_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (clean_name, normalize_optional(season), normalize_optional(comment), "pending", now, None),
            )
        elif section == "movies":
            connection.execute(
                """
                INSERT INTO movies (name, comment, status, created_at, completed_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (clean_name, normalize_optional(comment), "pending", now, None),
            )

    return redirect_to_media(section)


@app.post("/media/{section}/{item_id}/toggle")
def toggle_media_item(section: str, item_id: int, active_filter: Optional[str] = Form(None)):
    if section not in MEDIA_CONFIG:
        return redirect_to_home()

    config = MEDIA_CONFIG[section]
    table = config["table"]
    done_status = config["done_status"]

    with get_connection() as connection:
        item = connection.execute(
            f"SELECT status FROM {table} WHERE id = ?",
            (item_id,),
        ).fetchone()

        if section == "books" and item and item["status"] == "pending":
            connection.execute(
                "UPDATE books SET status = ?, completed_at = ? WHERE id = ?",
                ("downloaded", None, item_id),
            )
        elif section == "books" and item and item["status"] == "downloaded":
            connection.execute(
                "UPDATE books SET status = ?, completed_at = ? WHERE id = ?",
                ("read", datetime.now().isoformat(timespec="seconds"), item_id),
            )
        elif item and item["status"] == done_status:
            connection.execute(
                f"UPDATE {table} SET status = ?, completed_at = ? WHERE id = ?",
                ("pending", None, item_id),
            )
        elif item:
            connection.execute(
                f"UPDATE {table} SET status = ?, completed_at = ? WHERE id = ?",
                (done_status, datetime.now().isoformat(timespec="seconds"), item_id),
            )

    return redirect_to_media(section, active_filter)


@app.post("/media/{section}/{item_id}/delete")
def delete_media_item(section: str, item_id: int, active_filter: Optional[str] = Form(None)):
    if section not in MEDIA_CONFIG:
        return redirect_to_home()

    table = MEDIA_CONFIG[section]["table"]
    with get_connection() as connection:
        connection.execute(f"DELETE FROM {table} WHERE id = ?", (item_id,))

    return redirect_to_media(section, active_filter)
