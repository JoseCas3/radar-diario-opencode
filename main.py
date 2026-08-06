from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from dataclasses import dataclass
from datetime import date

from dotenv import load_dotenv

from scraper import DiarioOficialScraper
from llm import GeneradorResumenes
from email_sender import EmailNotifier

logger = logging.getLogger(__name__)


@dataclass
class _Config:
    gemini_api_key: str
    email_user: str
    email_password: str
    email_destinatario: str
    base_url: str


def configurar_logging() -> None:
    """Configura logging estructurado: timestamp, nivel, módulo, mensaje."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )


def _cargar_configuracion() -> _Config:
    """Carga variables de entorno y valida las requeridas. Termina con exit(1) si faltan."""
    gemini_api_key = os.getenv("GEMINI_API_KEY", "")
    email_user = os.getenv("EMAIL_USER", "")
    email_password = os.getenv("EMAIL_PASSWORD", "")

    if not gemini_api_key or not email_user or not email_password:
        logger.error(
            "Variables de entorno faltantes. Requeridas: "
            "GEMINI_API_KEY, EMAIL_USER, EMAIL_PASSWORD"
        )
        sys.exit(1)

    if len(email_password) < 16:
        logger.error(
            "EMAIL_PASSWORD parece inválido: %d caracteres. "
            "Debe ser una app password de Gmail (16 caracteres, requiere 2FA).",
            len(email_password),
        )
        sys.exit(1)

    return _Config(
        gemini_api_key=gemini_api_key,
        email_user=email_user,
        email_password=email_password,
        email_destinatario=os.getenv("EMAIL_DESTINATARIO", email_user),
        base_url=os.getenv("BASE_URL", "https://www.diariooficial.gob.sv"),
    )


def validar_html(html: str) -> bool:
    """Verifica que el HTML no esté vacío y comience con '<'."""
    return bool(html.strip()) and html.strip().startswith("<")


def _cargar_estado(ruta_estado: str) -> dict:
    """Carga la última fecha enviada. Devuelve el estado por defecto si falta o es inválido."""
    if not os.path.exists(ruta_estado):
        return {"ultima_fecha_enviada": None}
    try:
        with open(ruta_estado, encoding="utf-8") as archivo:
            datos = json.load(archivo)
        if "ultima_fecha_enviada" not in datos:
            datos["ultima_fecha_enviada"] = None
        return datos
    except (OSError, ValueError) as e:
        logger.warning("No se pudo leer el estado en %s: %s", ruta_estado, e)
        return {"ultima_fecha_enviada": None}


def _guardar_estado(ruta_estado: str, estado: dict) -> None:
    """Persiste el estado (última fecha enviada) en formato JSON."""
    try:
        with open(ruta_estado, "w", encoding="utf-8") as archivo:
            json.dump(estado, archivo, ensure_ascii=False, indent=2)
    except OSError as e:
        logger.warning("No se pudo guardar el estado en %s: %s", ruta_estado, e)


def _parsear_fecha(s: str) -> date:
    """Valida que el argumento --fecha tenga formato YYYY-MM-DD."""
    try:
        return date.fromisoformat(s)
    except ValueError as e:
        raise argparse.ArgumentTypeError(
            f"Fecha inválida '{s}'. Usa el formato YYYY-MM-DD."
        ) from e


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="Radar Diario Oficial",
        description="Extrae noticias políticas del Diario Oficial y envía boletín.",
    )
    parser.add_argument(
        "--fecha",
        type=_parsear_fecha,
        help="Fecha (YYYY-MM-DD) para procesar una edición pasada (backfill).",
    )
    parser.add_argument(
        "--estado",
        default="estado.json",
        help="Ruta al archivo de estado con la última fecha enviada.",
    )
    parser.add_argument(
        "--fuerza",
        action="store_true",
        help="Reenviar aunque la edición ya haya sido enviada (ignora el dedupe).",
    )
    args = parser.parse_args()
    try:
        _ejecutar_pipeline(fecha=args.fecha, ruta_estado=args.estado, fuerza=args.fuerza)
    except Exception:
        logger.exception("Error fatal en el pipeline")
        sys.exit(1)


def _ejecutar_pipeline(
    fecha: date | None = None,
    ruta_estado: str = "estado.json",
    fuerza: bool = False,
) -> None:
    """Orquesta extracción → resumen → envío del boletín del Diario Oficial."""
    configurar_logging()
    load_dotenv()
    config = _cargar_configuracion()

    scraper = DiarioOficialScraper(base_url=config.base_url)
    generador = GeneradorResumenes(api_key=config.gemini_api_key)
    notificador = EmailNotifier(
        smtp_user=config.email_user,
        smtp_password=config.email_password,
        destinatario=config.email_destinatario,
    )

    objetivo = fecha or date.today()
    logger.info("Iniciando pipeline para %s", objetivo.isoformat())

    texto_diario = scraper.obtener_texto_diario(objetivo)
    fecha_publicacion = objetivo

    if texto_diario is None:
        if fecha is not None:
            logger.info(
                "No se encontró publicación para %s en modo backfill. Finalizando.",
                objetivo.isoformat(),
            )
            return
        logger.info(
            "No se encontró publicación para hoy (%s). Buscando última disponible...",
            objetivo.isoformat(),
        )
        resultado = scraper.obtener_texto_ultima_publicacion()
        if resultado is None:
            logger.info("No hay publicaciones disponibles. Finalizando sin enviar.")
            return
        texto_diario, fecha_publicacion = resultado
        logger.info("Usando publicación del %s", fecha_publicacion.isoformat())

    estado = _cargar_estado(ruta_estado)
    if not fuerza and estado.get("ultima_fecha_enviada") == fecha_publicacion.isoformat():
        logger.info(
            "La edición del %s ya fue enviada anteriormente. Saltando sin enviar.",
            fecha_publicacion.isoformat(),
        )
        return

    html_boletin = generador.generar_resumen(
        texto_diario, fecha=fecha_publicacion.strftime("%d/%m/%Y")
    )
    if not validar_html(html_boletin):
        logger.error("El HTML generado por Gemini no es válido: %s", html_boletin[:200])
        sys.exit(1)

    notificador.enviar_boletin(html_boletin, fecha=fecha_publicacion)
    _guardar_estado(ruta_estado, {"ultima_fecha_enviada": fecha_publicacion.isoformat()})
    logger.info("Pipeline completado exitosamente para %s", fecha_publicacion.isoformat())


if __name__ == "__main__":
    main()
