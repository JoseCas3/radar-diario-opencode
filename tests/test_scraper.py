from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest
import requests

from scraper import DiarioOficialScraper
from tests.conftest import crear_mock_response


class TestDiarioOficialScraper:
    def test_obtener_texto_diario_exitoso(self, fecha_hoy):
        mock_session = MagicMock()
        mock_session.post.side_effect = [
            crear_mock_response(json_data=[{"month": "5"}]),
            crear_mock_response(
                json_data=[
                    {
                        "Id": 42,
                        "FechaInicio": "2026-05-26",
                        "NombreArchivo": "diario-2026-05-26.pdf",
                    }
                ]
            ),
        ]
        mock_session.get.return_value = crear_mock_response(content=b"fake-pdf")

        with patch("scraper.requests.Session", return_value=mock_session), patch(
            "scraper.PdfReader"
        ) as mock_reader_class:
            mock_page = MagicMock()
            mock_page.extract_text.return_value = "Texto extraído del decreto."
            mock_reader_class.return_value.pages = [mock_page]

            scraper = DiarioOficialScraper()
            resultado = scraper.obtener_texto_diario(fecha_hoy)

        assert resultado == "Texto extraído del decreto."

    def test_sin_publicacion_hoy(self, fecha_hoy):
        mock_session = MagicMock()
        mock_session.post.side_effect = [
            crear_mock_response(json_data=[{"month": "5"}]),
            crear_mock_response(
                json_data=[
                    {
                        "Id": 41,
                        "FechaInicio": "2026-05-25",
                        "NombreArchivo": "diario-2026-05-25.pdf",
                    }
                ]
            ),
        ]

        with patch("scraper.requests.Session", return_value=mock_session):
            scraper = DiarioOficialScraper()
            resultado = scraper.obtener_texto_diario(fecha_hoy)

        assert resultado is None

    def test_mes_sin_publicaciones(self, fecha_hoy):
        mock_session = MagicMock()
        mock_session.post.return_value = crear_mock_response(json_data=[{"month": "1"}, {"month": "3"}])

        with patch("scraper.requests.Session", return_value=mock_session):
            scraper = DiarioOficialScraper()
            resultado = scraper.obtener_texto_diario(fecha_hoy)

        assert resultado is None
        mock_session.post.assert_called_once()

    def test_error_meses_disponibles(self, fecha_hoy):
        mock_session = MagicMock()
        mock_session.post.side_effect = requests.ConnectionError("Sin conexión")

        with patch("scraper.requests.Session", return_value=mock_session):
            scraper = DiarioOficialScraper()
            with pytest.raises(requests.ConnectionError):
                scraper.obtener_texto_diario(fecha_hoy)

    def test_error_diarios_disponibles(self, fecha_hoy):
        mock_session = MagicMock()
        mock_session.post.side_effect = [
            crear_mock_response(json_data=[{"month": "5"}]),
            requests.Timeout("Timeout"),
        ]

        with patch("scraper.requests.Session", return_value=mock_session):
            scraper = DiarioOficialScraper()
            with pytest.raises(requests.Timeout):
                scraper.obtener_texto_diario(fecha_hoy)

    def test_error_descarga_pdf(self, fecha_hoy):
        mock_session = MagicMock()
        mock_session.post.side_effect = [
            crear_mock_response(json_data=[{"month": "5"}]),
            crear_mock_response(
                json_data=[
                    {
                        "Id": 42,
                        "FechaInicio": "2026-05-26",
                        "NombreArchivo": "diario-2026-05-26.pdf",
                    }
                ]
            ),
        ]
        mock_session.get.side_effect = requests.HTTPError("404 Not Found")

        with patch("scraper.requests.Session", return_value=mock_session):
            scraper = DiarioOficialScraper()
            with pytest.raises(requests.HTTPError):
                scraper.obtener_texto_diario(fecha_hoy)

    def test_fecha_personalizada(self):
        mock_session = MagicMock()
        mock_session.post.side_effect = [
            crear_mock_response(json_data=[{"month": "3"}]),
            crear_mock_response(
                json_data=[
                    {
                        "Id": 10,
                        "FechaInicio": "2026-03-15",
                        "NombreArchivo": "diario-2026-03-15.pdf",
                    }
                ]
            ),
        ]
        mock_session.get.return_value = crear_mock_response(content=b"pdf-marzo")

        with patch("scraper.requests.Session", return_value=mock_session), patch(
            "scraper.PdfReader"
        ) as mock_reader_class:
            mock_page = MagicMock()
            mock_page.extract_text.return_value = "Decreto de marzo."
            mock_reader_class.return_value.pages = [mock_page]

            scraper = DiarioOficialScraper()
            resultado = scraper.obtener_texto_diario(date(2026, 3, 15))

        assert resultado == "Decreto de marzo."

    def test_pdf_sin_texto_extraible(self, fecha_hoy):
        mock_session = MagicMock()
        mock_session.post.side_effect = [
            crear_mock_response(json_data=[{"month": "5"}]),
            crear_mock_response(
                json_data=[
                    {
                        "Id": 99,
                        "FechaInicio": "2026-05-26",
                        "NombreArchivo": "diario-escaneado.pdf",
                    }
                ]
            ),
        ]
        mock_session.get.return_value = crear_mock_response(content=b"pdf-sin-texto")

        with patch("scraper.requests.Session", return_value=mock_session), patch(
            "scraper.PdfReader"
        ) as mock_reader_class:
            mock_page = MagicMock()
            mock_page.extract_text.return_value = ""
            mock_reader_class.return_value.pages = [mock_page]

            scraper = DiarioOficialScraper()
            resultado = scraper.obtener_texto_diario(fecha_hoy)

        assert resultado == ""

    def test_extraer_texto_pdf_error(self):
        scraper = DiarioOficialScraper()
        pdf_invalido = b"no-es-un-pdf-real"

        with pytest.raises(Exception):
            scraper._extraer_texto_pdf(pdf_invalido)
        mock_session = MagicMock()
        mock_session.get.return_value = crear_mock_response(content=b"contenido")

        with patch("scraper.requests.Session", return_value=mock_session):
            scraper = DiarioOficialScraper(base_url="https://api.ejemplo.sv")
            scraper._descargar_pdf(42)

        mock_session.get.assert_called_once_with(
            "https://api.ejemplo.sv/seleccion/42", timeout=30
        )

    @pytest.mark.parametrize(
        "diarios, fecha_str, esperado",
        [
            (
                [
                    {"Id": 1, "FechaInicio": "2026-05-25", "NombreArchivo": "a.pdf"},
                    {"Id": 2, "FechaInicio": "2026-05-26", "NombreArchivo": "b.pdf"},
                ],
                "2026-05-26",
                2,
            ),
            (
                [
                    {"Id": 1, "FechaInicio": "2026-05-24", "NombreArchivo": "x.pdf"},
                ],
                "2026-05-26",
                None,
            ),
            ([], "2026-05-26", None),
        ],
    )
    def test_filtro_fecha_publicacion(self, diarios, fecha_str, esperado):
        mock_session = MagicMock()
        mock_session.post.side_effect = [
            crear_mock_response(json_data=[{"month": "5"}]),
            crear_mock_response(json_data=diarios),
        ]

        with patch("scraper.requests.Session", return_value=mock_session):
            scraper = DiarioOficialScraper()
            resultado = scraper._buscar_publicacion(
                date.fromisoformat(fecha_str)
            )

        if esperado is None:
            assert resultado is None
        else:
            assert resultado is not None
            assert resultado.id == esperado
