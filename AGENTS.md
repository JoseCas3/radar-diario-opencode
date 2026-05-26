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

- **scraper.py**: ROTO — usa placeholder hardcodeado, BeautifulSoup innecesario, PDF dummy. **Necesita reescritura completa** para usar API real.
- **llm.py**: Funcional — Gemini 2.5 Flash, reintentos con backoff. `load_dotenv()` duplicado (mover a main.py).
- **email_sender.py**: Funcional — SMTP Gmail. `load_dotenv()` duplicado (mover a main.py).
- **main.py**: Orquesta, pero usa `print()` en vez de `logging`.
- **CI/CD**: GitHub Actions funcional. Dockerfile Alpine correcto.
- **Tests**: 0 — crear suite completa en `tests/`.

## Próximas tareas prioritarias

1. **Reconstruir scraper** — eliminar BeautifulSoup, implementar API real, devolver `None` si no hay publicación hoy.
2. **Migrar a logging** — reemplazar `print()` en los 4 archivos.
3. **Mover `load_dotenv()`** solo a `main.py`; los módulos reciben config en `__init__`.
4. **Escribir tests** — `test_scraper.py`, `test_llm.py`, `test_email.py`.
5. **Mejorar prompt LLM** — secciones explícitas, validar HTML de salida.
6. **Verificación SMTP** — probar conectividad antes de enviar.
