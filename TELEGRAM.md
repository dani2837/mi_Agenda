# Bot de Telegram

## Crear el bot con BotFather

1. Abre Telegram y busca `@BotFather`.
2. Escribe `/newbot`.
3. Elige un nombre para el bot.
4. Elige un usuario terminado en `bot`, por ejemplo `mi_app_tareas_bot`.
5. BotFather te dará un token.
6. Copia ese token en el archivo `.env`:

```text
TELEGRAM_BOT_TOKEN=tu_token_real_aqui
```

## Instalar dependencias

Desde la carpeta del proyecto:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Ejecutar el bot

```powershell
python bot.py
```

El bot usa la misma base de datos SQLite que la app web: `tasks.db`.

## Comandos disponibles

```text
/start
/tarea llamar al banco
/tarea llamar al banco + preguntar por recibo + 20/06/2026
/tarea llamar al banco, preguntar por recibo, 20/06/2026
/tarea llamar a pepe, recuerdale la cita 17/06/2026
/urgente pagar factura luz + vence pronto + 20/06/2026
/urgente pagar factura luz, vence pronto, 20/06/2026
/comprar leche
/comprar + leche
/comprar leche, huevos, aceite
/listacompra
/info
/tiempo
/hoy
/pendientes
```

En `/tarea` y `/urgente`, la descripcion y la fecha son opcionales.
La fecha debe escribirse en formato `dd/mm/aaaa`.
Puedes separar titulo, descripcion y fecha con `+` o con coma.
Si la fecha va al final, tambien se reconoce aunque no pongas una coma antes de la fecha.
Si no indicas fecha desde Telegram, la tarea se guarda automaticamente para manana.

Tambien puedes usar un guion despues del comando:

```text
/tarea - llamar al banco + preguntar por recibo + 20/06/2026
```

`/info` devuelve un resumen de todos los comandos disponibles.

## Configurar ciudad para el tiempo

El comando `/tiempo` y la caja lateral de la web usan `WEATHER_CITY`.
Anade esta linea a tu archivo `.env`:

```text
WEATHER_CITY=Sevilla
```

Si no configuras ciudad, se usara `Madrid` por defecto.
