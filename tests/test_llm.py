from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from llm import GeneradorResumenes, MAX_REINTENTOS, MAX_CARACTERES


class TestGeneradorResumenes:
    def test_generar_resumen_exitoso(self, texto_diario_mock, html_boletin_mock):
        mock_response = MagicMock()
        mock_response.text = html_boletin_mock

        with patch("llm.genai.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.models.generate_content.return_value = mock_response
            mock_client_class.return_value = mock_client

            generador = GeneradorResumenes(api_key="test-key")
            resultado = generador.generar_resumen(texto_diario_mock)

        assert resultado == html_boletin_mock
        mock_client.models.generate_content.assert_called_once()

    def test_generar_resumen_con_fecha(self, texto_diario_mock):
        mock_response = MagicMock()
        mock_response.text = "<h1>Boletín</h1>"

        with patch("llm.genai.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.models.generate_content.return_value = mock_response
            mock_client_class.return_value = mock_client

            generador = GeneradorResumenes(api_key="test-key")
            resultado = generador.generar_resumen(
                texto_diario_mock, fecha="26/05/2026"
            )

        assert "Boletín" in resultado
        call_args = mock_client.models.generate_content.call_args
        assert "26/05/2026" in call_args.kwargs["contents"]

    def test_texto_vacio(self):
        mock_response = MagicMock()
        mock_response.text = "<p>Sin noticias políticas relevantes</p>"

        with patch("llm.genai.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.models.generate_content.return_value = mock_response
            mock_client_class.return_value = mock_client

            generador = GeneradorResumenes(api_key="test-key")
            resultado = generador.generar_resumen("")

        assert resultado == "<p>Sin noticias políticas relevantes</p>"

    def test_reintento_exitoso_segundo_intento(self, texto_diario_mock):
        mock_response_exito = MagicMock()
        mock_response_exito.text = "<h1>Resumen final</h1>"

        with patch("llm.genai.Client") as mock_client_class, patch(
            "llm.time.sleep"
        ) as mock_sleep:
            mock_client = MagicMock()
            mock_client.models.generate_content.side_effect = [
                ConnectionError("Error de red"),
                mock_response_exito,
            ]
            mock_client_class.return_value = mock_client

            generador = GeneradorResumenes(api_key="test-key", max_reintentos=3)
            resultado = generador.generar_resumen(texto_diario_mock)

        assert resultado == "<h1>Resumen final</h1>"
        assert mock_client.models.generate_content.call_count == 2
        mock_sleep.assert_called_once_with(2)

    def test_todos_reintentos_agotados(self, texto_diario_mock):
        with patch("llm.genai.Client") as mock_client_class, patch(
            "llm.time.sleep"
        ) as mock_sleep:
            mock_client = MagicMock()
            mock_client.models.generate_content.side_effect = ConnectionError(
                "Error persistente"
            )
            mock_client_class.return_value = mock_client

            generador = GeneradorResumenes(api_key="test-key", max_reintentos=2)
            with pytest.raises(RuntimeError, match="No se pudo generar el resumen"):
                generador.generar_resumen(texto_diario_mock)

        assert mock_client.models.generate_content.call_count == 2
        assert mock_sleep.call_count == 1

    def test_respuesta_vacia_gemini(self, texto_diario_mock):
        mock_response = MagicMock()
        mock_response.text = None

        with patch("llm.genai.Client") as mock_client_class, patch(
            "llm.time.sleep"
        ) as mock_sleep:
            mock_client = MagicMock()
            mock_client.models.generate_content.return_value = mock_response
            mock_client_class.return_value = mock_client

            generador = GeneradorResumenes(api_key="test-key", max_reintentos=2)
            with pytest.raises(RuntimeError, match="No se pudo generar el resumen"):
                generador.generar_resumen(texto_diario_mock)

    def test_truncar_texto_largo(self):
        mock_response = MagicMock()
        mock_response.text = "<h1>Ok</h1>"

        texto_largo = "A" * (MAX_CARACTERES + 5000)

        with patch("llm.genai.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.models.generate_content.return_value = mock_response
            mock_client_class.return_value = mock_client

            generador = GeneradorResumenes(api_key="test-key")
            resultado = generador.generar_resumen(texto_largo)

        call_args = mock_client.models.generate_content.call_args
        texto_enviado = call_args.kwargs["contents"]
        assert len(texto_enviado) <= MAX_CARACTERES + 200
        assert resultado == "<h1>Ok</h1>"

    def test_texto_dentro_del_limite_no_se_trunca(self, texto_diario_mock):
        mock_response = MagicMock()
        mock_response.text = "<h1>Ok</h1>"

        with patch("llm.genai.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.models.generate_content.return_value = mock_response
            mock_client_class.return_value = mock_client

            generador = GeneradorResumenes(api_key="test-key")
            generador.generar_resumen(texto_diario_mock)

        call_args = mock_client.models.generate_content.call_args
        texto_enviado = call_args.kwargs["contents"]
        assert texto_diario_mock in texto_enviado

    @pytest.mark.parametrize(
        "max_reintentos,fallos_esperados",
        [
            (1, 0),
            (3, 2),
            (5, 4),
        ],
    )
    def test_backoff_exponencial(
        self, texto_diario_mock, max_reintentos, fallos_esperados
    ):
        mock_response_exito = MagicMock()
        mock_response_exito.text = "<h1>Éxito</h1>"

        with patch("llm.genai.Client") as mock_client_class, patch(
            "llm.time.sleep"
        ) as mock_sleep:
            mock_client = MagicMock()
            side_effects = [ConnectionError("Fallo")] * fallos_esperados + [
                mock_response_exito
            ]
            mock_client.models.generate_content.side_effect = side_effects
            mock_client_class.return_value = mock_client

            generador = GeneradorResumenes(
                api_key="test-key", max_reintentos=max_reintentos
            )
            resultado = generador.generar_resumen(texto_diario_mock)

        assert resultado == "<h1>Éxito</h1>"
        assert mock_sleep.call_count == fallos_esperados
