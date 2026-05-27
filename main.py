from __future__ import annotations

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
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )


def _cargar_configuracion() -> _Config:
    gemini_api_key = os.getenv("GEMINI_API_KEY", "")
    email_user = os.getenv("EMAIL_USER", "")
    email_password = os.getenv("EMAIL_PASSWORD", "")

    if not gemini_api_key or not email_user or not email_password:
        logger.error(
            "Variables de entorno faltantes. Requeridas: "
            "GEMINI_API_KEY, EMAIL_USER, EMAIL_PASSWORD"
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
    return bool(html.strip()) and html.strip().startswith("<")


def main() -> None:
    try:
        _ejecutar_pipeline()
    except Exception:
        logger.exception("Error fatal en el pipeline")
        sys.exit(1)


def _ejecutar_pipeline() -> None:
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

    hoy = date.today()
    logger.info("Iniciando pipeline para %s", hoy.isoformat())

    texto_diario = scraper.obtener_texto_diario(hoy)
    if texto_diario is None:
        logger.info(
            "No se encontró publicación para hoy (%s). Finalizando sin enviar.",
            hoy.isoformat(),
        )
        return

    html_boletin = generador.generar_resumen(
        texto_diario, fecha=hoy.strftime("%d/%m/%Y")
    )
    if not validar_html(html_boletin):
        logger.error("El HTML generado por Gemini no es válido: %s", html_boletin[:200])
        sys.exit(1)

    notificador.enviar_boletin(html_boletin, fecha=hoy)
    logger.info("Pipeline completado exitosamente para %s", hoy.isoformat())


if __name__ == "__main__":
    main()
