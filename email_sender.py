from __future__ import annotations

import logging
import re
import smtplib
import time
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

SMTP_SERVIDOR = "smtp.gmail.com"
SMTP_PUERTO = 587
DESTINATARIO_POR_DEFECTO = "radar.politico.sv@gmail.com"
MAX_REINTENTOS = 3
BACKOFF_INICIAL = 2


class EmailNotifier:
    """Envía el boletín HTML del Diario Oficial por correo electrónico vía SMTP."""

    def __init__(
        self,
        smtp_user: str,
        smtp_password: str,
        destinatario: str = DESTINATARIO_POR_DEFECTO,
        smtp_server: str = SMTP_SERVIDOR,
        smtp_port: int = SMTP_PUERTO,
    ) -> None:
        self._smtp_user = smtp_user
        self._smtp_password = smtp_password
        self._destinatario = destinatario
        self._smtp_server = smtp_server
        self._smtp_port = smtp_port

    def enviar_boletin(self, html_contenido: str, fecha: date | None = None) -> None:
        """Envía el boletín HTML por correo con reintentos ante fallos transitorios."""
        fecha_obj = fecha or date.today()
        asunto = f"Radar Político — Diario Oficial {fecha_obj.strftime('%d/%m/%Y')}"

        texto_plano = re.sub(r"<[^>]+>", "", html_contenido).strip()
        mensaje = MIMEMultipart("alternative")
        mensaje["Subject"] = asunto
        mensaje["From"] = self._smtp_user
        mensaje["To"] = self._destinatario
        mensaje.attach(MIMEText(texto_plano, "plain", "utf-8"))
        mensaje.attach(MIMEText(html_contenido, "html", "utf-8"))

        self._intentar_enviar(mensaje, asunto)

    def _intentar_enviar(self, mensaje: MIMEMultipart, asunto: str) -> None:
        """Envía el mensaje SMTP con reintentos ante errores transitorios de red."""
        ultima_excepcion: Exception | None = None
        for intento in range(1, MAX_REINTENTOS + 1):
            try:
                with smtplib.SMTP(
                    self._smtp_server, self._smtp_port, timeout=30
                ) as server:
                    server.starttls()
                    server.ehlo()
                    server.login(self._smtp_user, self._smtp_password)
                    server.send_message(mensaje)
                logger.info(
                    "Boletín enviado a %s (asunto: %s)", self._destinatario, asunto
                )
                return
            except smtplib.SMTPAuthenticationError as e:
                logger.error("Error de autenticación SMTP: credenciales inválidas")
                raise
            except (smtplib.SMTPException, OSError) as e:
                ultima_excepcion = e
                if intento < MAX_REINTENTOS:
                    espera = BACKOFF_INICIAL**intento
                    logger.warning(
                        "Error SMTP (intento %d/%d): %s. Reintentando en %ds...",
                        intento,
                        MAX_REINTENTOS,
                        e,
                        espera,
                    )
                    time.sleep(espera)
                else:
                    logger.error(
                        "Fallaron los %d intentos SMTP. Último error: %s",
                        MAX_REINTENTOS,
                        e,
                    )
        raise ultima_excepcion
