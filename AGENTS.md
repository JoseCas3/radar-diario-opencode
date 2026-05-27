# Radar Diario Oficial

Pipeline automatizado: obtiene PDF del Diario Oficial de El Salvador (vía API REST) → Gemini 2.5 Flash extrae noticias políticas → envía boletín por correo.

## Stack

- Python 3.11, Docker, GitHub Actions (cron diario 5:00 AM SV)
- `requests` + `PyPDF2` (descarga y extrae PDFs)
- `google-genai` (Gemini 2.5 Flash) — genera resumen HTML
- `smtplib` Gmail (envío de boletín)
- Sin Selenium, sin Playwright, sin BeautifulSoup (innecesarios)

## Arquitectura (3 módulos modulares)

| Módulo | Archivo | Clase | Rol |
|--------|---------|-------|-----|
| Extracción | `scraper.py` | `DiarioOficialScraper` | POST a API → filtra hoy → descarga PDF → PyPDF2 extrae texto |
| Procesamiento | `llm.py` | `GeneradorResumenes` | Prompt → Gemini → HTML |
| Notificación | `email_sender.py` | `EmailNotifier` | Envía boletín vía Gmail SMTP |

`main.py` orquesta: extraer → resumir → enviar.

## API del Diario Oficial

| Endpoint | Método | Body | Respuesta |
|----------|--------|------|-----------|
| `/api/v1/meses-disponibles` | POST | `{"year":2026}` (JSON) | Meses con publicaciones |
| `/api/v1/diarios-disponibles` | POST | `year=2026&month=5` (form-urlencoded) | PDFs del mes: `[{"Id","FechaInicio","NombreArchivo"}]` |
| `/seleccion/{Id}` | GET | — | Descarga directa del PDF (~2 MB) |

El `Id` es numérico. `FechaInicio` es formato `YYYY-MM-DD`.

## Setup local

```bash
python -m venv venv
source venv/Scripts/activate  # Windows
# source venv/bin/activate    # Linux/Mac
pip install -r requirements.txt
```

`.env`:
```
GEMINI_API_KEY=...
EMAIL_USER=radar.politico.sv@gmail.com
EMAIL_PASSWORD=...
```

Ejecutar: `python main.py`

## Estándares de código (aplicar siempre)

### Python

- **Type hints en todas las funciones** — parámetros y retorno. Usar tipos modernos (`list[str]` no `List[str]`, `|` para uniones).
- **EAFP** — try/except, no if guardias. Encadenar excepciones con `raise X from e`.
- **Logging estructurado** — `logging` con niveles (INFO, WARNING, ERROR), nunca `print()`.
- **Constantes en MAYÚSCULAS** — URLs, timeouts, config.
- **`load_dotenv()` solo en `main.py`** — los módulos reciben config por constructor/parámetro.
- **Funciones < 30 líneas**, una responsabilidad.
- **Sin comentarios** — solo docstrings mínimos de clase/método si aportan claridad.
- **Sin dependencias innecesarias** — no agregar BeautifulSoup, Selenium, Playwright.
- **Context managers** — usar `with` para archivos, conexiones, recursos.
- **Dataclasses** para objetos de datos simples.
- **Nombres en español** — coherente con el dominio del Diario Oficial.
- **Cada archivo importable y testeable por separado** — sin side effects al importar.

### Bash / CI-CD

- **Siempre** `set -Eeuo pipefail` en scripts shell.
- **Variables siempre entre comillas dobles**: `"$VAR"`
- **`[[ ]]` para condicionales**, no `[ ]`.
- **Trap para limpiar** recursos temporales (`EXIT`, `ERR`).
- **Logging con timestamp** en scripts shell: `echo "[$(date +'%Y-%m-%d %H:%M:%S')] INFO: ..."`.
- **Validar dependencias** antes de ejecutar.
- **Soportar dry-run** cuando sea relevante.
- **Idempotencia** — scripts deben poder ejecutarse múltiples veces sin daño.

### Testing

- **pytest** como framework — no `unittest`.
- **Tests en `tests/`** con naming `test_<modulo>.py`.
- **Fixture scope adecuado** — `function` por defecto, `session` solo para recursos caros.
- **Mockear IO** — API, Gemini, SMTP con `unittest.mock` / `monkeypatch`.
- **Parametrizar** casos borde con `@pytest.mark.parametrize`.
- **Probar errores** — `pytest.raises`, no solo happy path.
- **Conftest** para fixtures compartidos.
- **Cobertura** — `pytest --cov=... --cov-report=term-missing`.

## Flujo de trabajo para el asistente

1. **Antes de escribir código**, reconocer qué tipo de tarea es y aplicar los estándares correspondientes.
2. **Seguir los estándares** de la sección superior.
3. **Verificar con `pip install -r requirements.txt`** si se agregó dependencia.
4. **No committear** a menos que el usuario lo pida explícitamente.
5. **Ejecutar tests** existentes después de cambios.

## Estado actual del código

- **scraper.py**: Funcional — API real (`meses-disponibles`, `diarios-disponibles`, `/seleccion/{Id}`), PyPDF2 con soporte AES, reintentos HTTP con backoff exponencial (3 intentos), sin BeautifulSoup.
- **llm.py**: Funcional — Gemini 2.5 Flash, prompt anti-alucinación con `temperature=0.1`, reintentos con backoff, truncado a 800K caracteres, validación de respuesta vacía.
- **email_sender.py**: Funcional — SMTP Gmail con reintentos y backoff, `ehlo()` post-TLS, MIME multipart con HTML + texto plano alternativo.
- **main.py**: Orquesta con `logging` estructurado, `load_dotenv()` solo aquí, validación HTML del boletín, try/except global con `logger.exception`.
- **CI/CD**: GitHub Actions con cron diario 5:00 AM SV, paso de tests antes del build, `concurrency` para evitar duplicados, timeout 15 min.
- **Docker**: Alpine 3.11, `PYTHONUNBUFFERED=1`, `.dockerignore`, `*.py` wildcard.
- **Tests**: 41 tests en 5 archivos (`test_scraper.py`, `test_llm.py`, `test_email.py`, `test_main.py`, `conftest.py`), 92% de cobertura. Sin side effects al importar.

## Próximas tareas (opcionales)

1. **Soporte para backfill** — flag `--fecha YYYY-MM-DD` en `main.py` para procesar fechas pasadas.
2. **Notificación de fallos** — alerta por email alternativo o GitHub Issue si el pipeline falla.
3. **Estrategia de truncado inteligente** — preservar secciones del final del PDF en vez de cortar al inicio.
4. **Métricas de uso de Gemini** — loguear tokens consumidos por corrida.
