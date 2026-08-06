# Radar Diario Oficial

Pipeline automatizado que descarga el Diario Oficial de El Salvador, extrae noticias políticas con Gemini 2.5 Flash y envía un boletín HTML por correo.

## Cómo funciona

El flujo es: **extraer → resumir → enviar**.

1. **Extracción** (`scraper.py`): consulta la API del Diario Oficial, filtra la publicación de hoy, extrae el texto del PDF con pypdf y lo limpia página por página (une palabras partidas, elimina membretes y números de página).
2. **Resumen** (`llm.py`): Gemini 2.5 Flash genera un boletín HTML con las noticias políticas relevantes.
3. **Envío** (`email_sender.py`): se envía el boletín por SMTP de Gmail (HTML + texto plano alternativo).
4. **Memoria anti-duplicados**: cada envío exitoso se registra en `estado.json`. Si un día la misma edición vuelve a aparecer (por ejemplo, cuando el Diario no publica por varios días y se usa la última edición disponible), **no se reenvía**.

En GitHub Actions hay un cron diario que ejecuta el pipeline de forma automática.

## Requisitos

- Python 3.11+
- API key de Gemini (gratis en [Google AI Studio](https://aistudio.google.com/apikey))
- App password de Gmail (requiere 2FA activado)

## Setup

```bash
python -m venv venv
source venv/Scripts/activate   # Windows
# source venv/bin/activate     # Linux/Mac
pip install -r requirements.txt
```

Crear un archivo `.env` en la raíz con las credenciales:

```bash
GEMINI_API_KEY=tu_api_key_de_gemini
EMAIL_USER=radar.politico.sv@gmail.com
EMAIL_PASSWORD=tu_app_password_de_gmail
```

Variables opcionales (usan los valores por defecto si se omiten):

```bash
EMAIL_DESTINATARIO=radar.politico.sv@gmail.com
BASE_URL=https://www.diariooficial.gob.sv
```

- `EMAIL_PASSWORD` debe ser una **app password de Gmail de 16 caracteres** (requiere 2FA).
- `EMAIL_DESTINATARIO` es quien recibe el boletín (por defecto, el mismo `EMAIL_USER`).

## Uso

```bash
python main.py
```

Si el Diario Oficial no se publicó hoy, el pipeline busca la **última edición disponible** y la envía. Si esa edición ya fue enviada en una corrida anterior (registrada en `estado.json`), se salta sin enviar ni consumir tokens de Gemini.

Opciones de línea de comandos:

| Flag | Descripción |
|------|-------------|
| `--fecha YYYY-MM-DD` | Procesa una edición pasada (backfill). |
| `--fuerza` | Reenvía aunque la edición ya haya sido enviada. |
| `--estado RUTA` | Ruta al archivo de estado (por defecto `estado.json`). |

## Docker

```bash
docker build -t radar-diario .
docker run --rm \
  -v "$(pwd)/estado.json:/app/estado.json" \
  -u root \
  -e GEMINI_API_KEY="tu-key" \
  -e EMAIL_USER="tu-email@gmail.com" \
  -e EMAIL_PASSWORD="tu-app-password" \
  -e EMAIL_DESTINATARIO="destinatario@gmail.com" \
  radar-diario
```

El mount `-v estado.json:/app/estado.json` (con `-u root` para poder escribir el archivo) persiste la memoria anti-duplicados entre corridas.

## Tests

```bash
python -m pytest tests/ -v --cov=. --cov-report=term-missing
```

71 tests, ~90% de cobertura.
