# Radar Diario Oficial

Pipeline automatizado que descarga el Diario Oficial de El Salvador, extrae noticias políticas con Gemini 2.5 Flash y envía un boletín HTML por correo.

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
cp .env.example .env
# Editar .env con tus credenciales
```

## Uso

```bash
python main.py
```

Si el Diario Oficial no se publicó hoy, el pipeline termina sin enviar.

## Docker

```bash
docker build -t radar-diario .
docker run --rm \
  -e GEMINI_API_KEY="tu-key" \
  -e EMAIL_USER="tu-email@gmail.com" \
  -e EMAIL_PASSWORD="tu-app-password" \
  radar-diario
```

## Tests

```bash
python -m pytest tests/ -v --cov=. --cov-report=term-missing
```
