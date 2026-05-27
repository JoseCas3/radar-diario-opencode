from __future__ import annotations

import smtplib
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from email_sender import EmailNotifier


class TestEmailNotifier:
    def test_enviar_boletin_exitoso(self, html_boletin_mock):
        with patch("email_sender.smtplib.SMTP") as mock_smtp_class:
            mock_smtp = MagicMock()
            mock_smtp_class.return_value.__enter__.return_value = mock_smtp

            notificador = EmailNotifier(
                smtp_user="remitente@test.com",
                smtp_password="password123",
                destinatario="destino@test.com",
            )
            resultado = notificador.enviar_boletin(html_boletin_mock)

        assert resultado is None
        mock_smtp.starttls.assert_called_once()
        mock_smtp.ehlo.assert_called_once()
        mock_smtp.login.assert_called_once_with("remitente@test.com", "password123")
        mock_smtp.send_message.assert_called_once()
        mensaje = mock_smtp.send_message.call_args[0][0]
        assert mensaje["To"] == "destino@test.com"

    def test_asunto_incluye_fecha(self, html_boletin_mock):
        with patch("email_sender.smtplib.SMTP") as mock_smtp_class:
            mock_smtp = MagicMock()
            mock_smtp_class.return_value.__enter__.return_value = mock_smtp

            notificador = EmailNotifier(
                smtp_user="u@t.com", smtp_password="p", destinatario="d@t.com"
            )
            notificador.enviar_boletin(html_boletin_mock, fecha=date(2026, 5, 26))

        mensaje = mock_smtp.send_message.call_args[0][0]
        assert "26/05/2026" in mensaje["Subject"]

    def test_asunto_fecha_por_defecto_hoy(self, html_boletin_mock):
        with patch("email_sender.smtplib.SMTP") as mock_smtp_class:
            mock_smtp = MagicMock()
            mock_smtp_class.return_value.__enter__.return_value = mock_smtp

            notificador = EmailNotifier(
                smtp_user="u@t.com", smtp_password="p", destinatario="d@t.com"
            )
            notificador.enviar_boletin(html_boletin_mock)

        mensaje = mock_smtp.send_message.call_args[0][0]
        hoy_str = date.today().strftime("%d/%m/%Y")
        assert hoy_str in mensaje["Subject"]

    def test_error_autenticacion_smtp(self, html_boletin_mock):
        with patch("email_sender.smtplib.SMTP") as mock_smtp_class:
            mock_smtp = MagicMock()
            mock_smtp.login.side_effect = smtplib.SMTPAuthenticationError(
                535, b"Invalid credentials"
            )
            mock_smtp_class.return_value.__enter__.return_value = mock_smtp

            notificador = EmailNotifier(
                smtp_user="mal@test.com",
                smtp_password="incorrecta",
            )
            with pytest.raises(smtplib.SMTPAuthenticationError):
                notificador.enviar_boletin(html_boletin_mock)

    def test_error_conexion_smtp(self, html_boletin_mock):
        with patch("email_sender.smtplib.SMTP") as mock_smtp_class, patch(
            "email_sender.time.sleep"
        ):
            mock_smtp_class.side_effect = OSError("Connection refused")

            notificador = EmailNotifier(
                smtp_user="u@t.com", smtp_password="p"
            )
            with pytest.raises(OSError, match="Connection refused"):
                notificador.enviar_boletin(html_boletin_mock)

    def test_error_smtp_generico(self, html_boletin_mock):
        with patch("email_sender.smtplib.SMTP") as mock_smtp_class, patch(
            "email_sender.time.sleep"
        ):
            mock_smtp = MagicMock()
            mock_smtp.send_message.side_effect = smtplib.SMTPException(
                "Error al enviar"
            )
            mock_smtp_class.return_value.__enter__.return_value = mock_smtp

            notificador = EmailNotifier(
                smtp_user="u@t.com", smtp_password="p"
            )
            with pytest.raises(smtplib.SMTPException, match="Error al enviar"):
                notificador.enviar_boletin(html_boletin_mock)

    @pytest.mark.parametrize(
        "destinatario,esperado",
        [
            ("editor@medio.sv", "editor@medio.sv"),
            ("jefe@redaccion.sv", "jefe@redaccion.sv"),
        ],
    )
    def test_destinatario_personalizado(
        self, html_boletin_mock, destinatario, esperado
    ):
        with patch("email_sender.smtplib.SMTP") as mock_smtp_class:
            mock_smtp = MagicMock()
            mock_smtp_class.return_value.__enter__.return_value = mock_smtp

            notificador = EmailNotifier(
                smtp_user="u@t.com",
                smtp_password="p",
                destinatario=destinatario,
            )
            notificador.enviar_boletin(html_boletin_mock)

        mensaje = mock_smtp.send_message.call_args[0][0]
        assert mensaje["To"] == esperado
