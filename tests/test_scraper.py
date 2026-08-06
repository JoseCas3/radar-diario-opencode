from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest
import requests

from scraper import DiarioOficialScraper, MAX_CARACTERES_PDF
from tests.conftest import crear_mock_response


class TestLimpiarTexto:
    @pytest.fixture
    def scraper(self):
        return DiarioOficialScraper()

    def test_une_palabras_partidas(self, scraper):
        texto = "enco-\nmendaci\u00f3n presupuestaria"
        assert scraper._limpiar_texto(texto) == "encomendaci\u00f3n presupuestaria"

    def test_no_une_guion_legitimo(self, scraper):
        texto = "Art. 1-\nSe reforma el art\u00edculo."
        assert scraper._limpiar_texto(texto) == "Art. 1-\nSe reforma el art\u00edculo."

    def test_quita_numero_de_pagina(self, scraper):
        texto = "Contenido de la noticia.\n15\n"
        assert scraper._limpiar_texto(texto) == "Contenido de la noticia."

    def test_quita_membrete_encabezado(self, scraper):
        texto = "REP\u00daBLICA DE EL SALVADOR\nDIARIO OFICIAL\nDecreto de hoy."
        assert scraper._limpiar_texto(texto) == "Decreto de hoy."

    def test_colapsa_lineas_en_blanco(self, scraper):
        texto = "Primera l\u00ednea.\n\n\n\nSegunda l\u00ednea."
        assert scraper._limpiar_texto(texto) == "Primera l\u00ednea.\nSegunda l\u00ednea."

    def test_quita_linea_solo_espacios(self, scraper):
        texto = "  \t\nNoticia real."
        assert scraper._limpiar_texto(texto) == "Noticia real."


class TestUnirLimitado:
    def test_cabe_todo_sin_recortar(self):
        scraper = DiarioOficialScraper()
        paginas = ["p1", "p2", "p3"]
        assert scraper._unir_limitado(paginas, max_caracteres=100) == "p1\np2\np3"

    def test_recorta_paginas_completas(self):
        scraper = DiarioOficialScraper()
        paginas = ["aaaaa", "bbbbb", "ccccc"]
        texto = scraper._unir_limitado(paginas, max_caracteres=10)
        assert texto == "aaaaa"

    def test_presupuesto_considera_saltos_de_linea(self):
        scraper = DiarioOficialScraper()
        paginas = ["aaaaa", "bbbbb", "ccccc"]
        texto = scraper._unir_limitado(paginas, max_caracteres=12)
        assert texto == "aaaaa\nbbbbb"

    def test_incluye_siempre_la_primera_pagina(self):
        scraper = DiarioOficialScraper()
        paginas = ["a" * 50, "b"]
        texto = scraper._unir_limitado(paginas, max_caracteres=5)
        assert texto == "a" * 50

    def test_paginas_vacias(self):
        scraper = DiarioOficialScraper()
        assert scraper._unir_limitado([], max_caracteres=100) == ""
        assert scraper._unir_limitado([""], max_caracteres=100) == ""


class TestDiarioOficialScraper:
    def test_obtener_texto_diario_exitoso(self, fecha_hoy):
        with patch("scraper.requests.Session"), patch(
            "scraper.PdfReader"
        ) as mock_reader_class:
            mock_page = MagicMock()
            mock_page.extract_text.return_value = "Texto extraído del decreto."
            mock_reader_class.return_value.pages = [mock_page]

            scraper = DiarioOficialScraper()
            scraper._reintentar_http = MagicMock(
                side_effect=[
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
                    crear_mock_response(content=b"fake-pdf"),
                ]
            )
            resultado = scraper.obtener_texto_diario(fecha_hoy)

        assert resultado == "Texto extraído del decreto."

    def test_sin_publicacion_hoy(self, fecha_hoy):
        with patch("scraper.requests.Session"):
            scraper = DiarioOficialScraper()
            scraper._reintentar_http = MagicMock(
                side_effect=[
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
            )
            resultado = scraper.obtener_texto_diario(fecha_hoy)

        assert resultado is None

    def test_mes_sin_publicaciones(self, fecha_hoy):
        with patch("scraper.requests.Session"):
            scraper = DiarioOficialScraper()
            scraper._reintentar_http = MagicMock(
                side_effect=[
                    crear_mock_response(
                        json_data=[{"month": "1"}, {"month": "3"}]
                    ),
                ]
            )
            resultado = scraper.obtener_texto_diario(fecha_hoy)

        assert resultado is None
        scraper._reintentar_http.assert_called_once()

    def test_error_meses_disponibles(self, fecha_hoy):
        with patch("scraper.requests.Session"):
            scraper = DiarioOficialScraper()
            scraper._reintentar_http = MagicMock(
                side_effect=requests.ConnectionError("Sin conexión")
            )
            with pytest.raises(requests.ConnectionError):
                scraper.obtener_texto_diario(fecha_hoy)

    def test_error_diarios_disponibles(self, fecha_hoy):
        with patch("scraper.requests.Session"):
            scraper = DiarioOficialScraper()
            scraper._reintentar_http = MagicMock(
                side_effect=[
                    crear_mock_response(json_data=[{"month": "5"}]),
                    requests.Timeout("Timeout"),
                ]
            )
            with pytest.raises(requests.Timeout):
                scraper.obtener_texto_diario(fecha_hoy)

    def test_error_descarga_pdf(self, fecha_hoy):
        with patch("scraper.requests.Session"):
            scraper = DiarioOficialScraper()
            scraper._reintentar_http = MagicMock(
                side_effect=[
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
                    requests.HTTPError("404 Not Found"),
                ]
            )
            with pytest.raises(requests.HTTPError):
                scraper.obtener_texto_diario(fecha_hoy)

    def test_fecha_personalizada(self):
        with patch("scraper.requests.Session"), patch(
            "scraper.PdfReader"
        ) as mock_reader_class:
            mock_page = MagicMock()
            mock_page.extract_text.return_value = "Decreto de marzo."
            mock_reader_class.return_value.pages = [mock_page]

            scraper = DiarioOficialScraper()
            scraper._reintentar_http = MagicMock(
                side_effect=[
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
                    crear_mock_response(content=b"pdf-marzo"),
                ]
            )
            resultado = scraper.obtener_texto_diario(date(2026, 3, 15))

        assert resultado == "Decreto de marzo."

    def test_pdf_sin_texto_extraible(self, fecha_hoy):
        with patch("scraper.requests.Session"), patch(
            "scraper.PdfReader"
        ) as mock_reader_class:
            mock_page = MagicMock()
            mock_page.extract_text.return_value = ""
            mock_reader_class.return_value.pages = [mock_page]

            scraper = DiarioOficialScraper()
            scraper._reintentar_http = MagicMock(
                side_effect=[
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
                    crear_mock_response(content=b"pdf-sin-texto"),
                ]
            )
            resultado = scraper.obtener_texto_diario(fecha_hoy)

        assert resultado == ""

    def test_extraer_texto_pdf_error(self):
        scraper = DiarioOficialScraper()
        pdf_invalido = b"no-es-un-pdf-real"

        with pytest.raises(Exception):
            scraper._extraer_texto_pdf(pdf_invalido)

    def test_extraer_texto_pdf_devuelve_paginas_limpias(self):
        scraper = DiarioOficialScraper()
        with patch("scraper.PdfReader") as mock_reader_class:
            paginas_mock = [MagicMock(), MagicMock()]
            paginas_mock[0].extract_text.return_value = "Decreto uno.\n12\n"
            paginas_mock[1].extract_text.return_value = ""
            mock_reader_class.return_value.pages = paginas_mock

            resultado = scraper._extraer_texto_pdf(b"pdf")

        assert resultado == ["Decreto uno."]

    def test_obtener_texto_diario_recorta_por_paginas(self, fecha_hoy):
        with patch("scraper.requests.Session"), patch(
            "scraper.PdfReader"
        ) as mock_reader_class:
            paginas_mock = [MagicMock(), MagicMock()]
            paginas_mock[0].extract_text.return_value = "P\u00e1gina uno con contenido."
            paginas_mock[1].extract_text.return_value = "P\u00e1gina dos con noticia."
            mock_reader_class.return_value.pages = paginas_mock

            scraper = DiarioOficialScraper()
            scraper._reintentar_http = MagicMock(
                side_effect=[
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
                    crear_mock_response(content=b"fake-pdf"),
                ]
            )
            resultado = scraper.obtener_texto_diario(fecha_hoy, max_caracteres=20)

        assert "P\u00e1gina uno" in resultado
        assert "P\u00e1gina dos" not in resultado

    def test_descargar_pdf_url_correcta(self):
        scraper = DiarioOficialScraper(base_url="https://api.ejemplo.sv")
        scraper._reintentar_http = MagicMock(
            return_value=crear_mock_response(content=b"contenido")
        )
        scraper._descargar_pdf(42)

        scraper._reintentar_http.assert_called_once_with(
            "descargar-pdf", "https://api.ejemplo.sv/seleccion/42", "GET"
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
        with patch("scraper.requests.Session"):
            scraper = DiarioOficialScraper()
            scraper._reintentar_http = MagicMock(
                side_effect=[
                    crear_mock_response(json_data=[{"month": "5"}]),
                    crear_mock_response(json_data=diarios),
                ]
            )
            resultado = scraper._buscar_publicacion(
                date.fromisoformat(fecha_str)
            )

        if esperado is None:
            assert resultado is None
        else:
            assert resultado is not None
            assert resultado.id == esperado

    def test_obtener_texto_ultima_publicacion_exitoso(self):
        with patch("scraper.requests.Session"), patch(
            "scraper.PdfReader"
        ) as mock_reader_class:
            mock_page = MagicMock()
            mock_page.extract_text.return_value = "Texto del último diario."
            mock_reader_class.return_value.pages = [mock_page]

            scraper = DiarioOficialScraper()
            scraper._reintentar_http = MagicMock(
                side_effect=[
                    crear_mock_response(json_data=[{"month": "5"}]),
                    crear_mock_response(
                        json_data=[
                            {
                                "Id": 40,
                                "FechaInicio": "2026-05-10",
                                "NombreArchivo": "diario-2026-05-10.pdf",
                            },
                            {
                                "Id": 42,
                                "FechaInicio": "2026-05-14",
                                "NombreArchivo": "diario-2026-05-14.pdf",
                            },
                            {
                                "Id": 41,
                                "FechaInicio": "2026-05-12",
                                "NombreArchivo": "diario-2026-05-12.pdf",
                            },
                        ]
                    ),
                    crear_mock_response(content=b"fake-pdf"),
                ]
            )
            resultado = scraper.obtener_texto_ultima_publicacion()

        assert resultado is not None
        texto, fecha_pub = resultado
        assert texto == "Texto del último diario."
        assert fecha_pub == date(2026, 5, 14)

    def test_obtener_texto_ultima_publicacion_sin_publicaciones(self):
        with patch("scraper.requests.Session"):
            scraper = DiarioOficialScraper()
            scraper._reintentar_http = MagicMock(
                side_effect=[
                    crear_mock_response(json_data=[]),
                    crear_mock_response(json_data=[]),
                ]
            )
            resultado = scraper.obtener_texto_ultima_publicacion()

        assert resultado is None

    def test_buscar_ultima_publicacion_selecciona_mas_reciente(self):
        with patch("scraper.requests.Session"):
            scraper = DiarioOficialScraper()
            scraper._reintentar_http = MagicMock(
                side_effect=[
                    crear_mock_response(
                        json_data=[{"month": "3"}, {"month": "5"}, {"month": "1"}]
                    ),
                    crear_mock_response(
                        json_data=[
                            {
                                "Id": 10,
                                "FechaInicio": "2026-05-05",
                                "NombreArchivo": "diario-05.pdf",
                            },
                            {
                                "Id": 15,
                                "FechaInicio": "2026-05-20",
                                "NombreArchivo": "diario-20.pdf",
                            },
                            {
                                "Id": 12,
                                "FechaInicio": "2026-05-14",
                                "NombreArchivo": "diario-14.pdf",
                            },
                        ]
                    ),
                ]
            )
            resultado = scraper._buscar_ultima_publicacion(2026)

        assert resultado is not None
        assert resultado.id == 15
        assert resultado.fecha_inicio == "2026-05-20"
