from __future__ import annotations

import logging
import smtplib
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

SMTP_SERVIDOR = "smtp.gmail.com"
SMTP_PUERTO = 587
DESTINATARIO_POR_DEFECTO = "radar.politico.sv@gmail.com"


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

    def enviar_boletin(self, html_contenido: str, fecha: date | None = None) -> bool:
        """Envía el boletín HTML por correo. Retorna True si fue exitoso."""
        fecha_obj = fecha or date.today()
        asunto = f"Radar Político — Diario Oficial {fecha_obj.strftime('%d/%m/%Y')}"

        mensaje = MIMEMultipart("alternative")
        mensaje["Subject"] = asunto
        mensaje["From"] = self._smtp_user
        mensaje["To"] = self._destinatario
        mensaje.attach(MIMEText(html_contenido, "html", "utf-8"))

        try:
            with smtplib.SMTP(self._smtp_server, self._smtp_port, timeout=30) as server:
                server.starttls()
                server.login(self._smtp_user, self._smtp_password)
                server.send_message(mensaje)
        except smtplib.SMTPAuthenticationError as e:
            logger.error("Error de autenticación SMTP: credenciales inválidas")
            raise
        except smtplib.SMTPException as e:
            logger.error("Error SMTP al enviar boletín: %s", e)
            raise
        except OSError as e:
            logger.error("Error de conexión SMTP: %s", e)
            raise

        logger.info(
            "Boletín enviado a %s (asunto: %s)", self._destinatario, asunto
        )
        return True
