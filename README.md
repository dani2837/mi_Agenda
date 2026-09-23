# Mi app de tareas

Aplicacion local en Python para gestionar tareas personales, ideas, lista de compra, libros, series y peliculas.

## Tecnologias

- Python
- FastAPI
- SQLite
- Jinja2
- HTML y CSS
- python-telegram-bot
- Open-Meteo para el tiempo

## Configuracion local

Crear entorno virtual:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Instalar dependencias:

```powershell
pip install -r requirements.txt
```

Crear el archivo `.env` usando `.env.example` como referencia:

```env
TELEGRAM_BOT_TOKEN=pon_tu_token_aqui
WEATHER_CITY=Sevilla
```

## Ejecutar la app web

```powershell
uvicorn main:app --reload
```

Abrir en el navegador:

```text
http://localhost:8000
```

## Ejecutar el bot

```powershell
python bot.py
```

## Datos locales

La base de datos SQLite se crea automaticamente como `tasks.db`.

Ese archivo contiene tus datos personales y no debe subirse a GitHub.

## Seguridad

No subir:

- `.env`
- `tasks.db`
- `.venv/`
- lanzadores `.bat` locales con rutas personales
- `__pycache__/`

El repositorio incluye `.env.example` y lanzadores `.example.bat` sin informacion privada.
