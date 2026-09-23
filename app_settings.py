from database import get_connection, init_db


def get_setting(key: str, default: str = "") -> str:
    init_db()
    with get_connection() as connection:
        row = connection.execute(
            "SELECT value FROM settings WHERE key = ?",
            (key,),
        ).fetchone()
    return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    init_db()
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )


def is_reminder_enabled() -> bool:
    return get_setting("daily_reminder_enabled", "0") == "1"


def set_reminder_enabled(enabled: bool) -> None:
    set_setting("daily_reminder_enabled", "1" if enabled else "0")


def get_reminder_status() -> dict:
    return {
        "enabled": is_reminder_enabled(),
        "time": get_setting("daily_reminder_time", "09:00"),
        "chat_id": get_setting("telegram_chat_id", ""),
    }
