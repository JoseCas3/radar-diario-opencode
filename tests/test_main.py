from __future__ import annotations

import logging
import os
from argparse import ArgumentTypeError
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

import main
from main import (
    _cargar_configuracion,
    _cargar_estado,
    _guardar_estado,
    _ejecutar_pipeline,
    configurar_logging,
    validar_html,
    _Config,
    _parsear_fecha,
)


class TestConfigurarLogging:
    def test_configura_root_logger(self):
        with patch("main.logging.basicConfig") as mock_basic:
            configurar_logging()
            mock_basic.assert_called_once()
            assert mock_basic.call_args.kwargs["level"] == logging.INFO
            assert mock_basic.call_args.kwargs["format"] == (
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
            )


class TestCargarConfiguracion:
    def test_variables_requeridas_exitoso(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
        monkeypatch.setenv("EMAIL_USER", "user@test.com")
        monkeypatch.setenv("EMAIL_PASSWORD", "abcdefghijklmnop")
        monkeypatch.delenv("EMAIL_DESTINATARIO", raising=False)
        monkeypatch.delenv("BASE_URL", raising=False)

        config = _cargar_configuracion()

        assert config.gemini_api_key == "fake-key"
        assert config.email_user == "user@test.com"
        assert config.email_password == "abcdefghijklmnop"
        assert config.email_destinatario == "user@test.com"
        assert config.base_url == "https://www.diariooficial.gob.sv"

    def test_variables_opcionales_personalizadas(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "key")
        monkeypatch.setenv("EMAIL_USER", "u@t.com")
        monkeypatch.setenv("EMAIL_PASSWORD", "abcdefghijklmnop")
        monkeypatch.setenv("EMAIL_DESTINATARIO", "editor@medio.sv")
        monkeypatch.setenv("BASE_URL", "https://api.custom.sv")

        config = _cargar_configuracion()

        assert config.email_destinatario == "editor@medio.sv"
        assert config.base_url == "https://api.custom.sv"

    def test_variable_faltante_termina(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "key")
        monkeypatch.delenv("EMAIL_USER", raising=False)
        monkeypatch.delenv("EMAIL_PASSWORD", raising=False)

        with pytest.raises(SystemExit) as exc:
            _cargar_configuracion()

        assert exc.value.code == 1

    def test_solo_falta_una_variable(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "key")
        monkeypatch.setenv("EMAIL_USER", "u@t.com")
        monkeypatch.delenv("EMAIL_PASSWORD", raising=False)

        with pytest.raises(SystemExit):
            _cargar_configuracion()

    def test_password_corto_termina(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "key")
        monkeypatch.setenv("EMAIL_USER", "u@t.com")
        monkeypatch.setenv("EMAIL_PASSWORD", "12345")

        with pytest.raises(SystemExit) as exc:
            _cargar_configuracion()

        assert exc.value.code == 1


class TestValidarHtml:
    def test_html_valido(self):
        assert validar_html("<h1>Radar Político</h1>") is True

    def test_html_vacio(self):
        assert validar_html("") is False

    def test_html_solo_espacios(self):
        assert validar_html("   ") is False

    def test_html_sin_tags(self):
        assert validar_html("Esto no es HTML") is False


class TestParsearFecha:
    def test_fecha_valida(self):
        assert _parsear_fecha("2026-07-14").isoformat() == "2026-07-14"

    def test_fecha_invalida(self):
        with pytest.raises(ArgumentTypeError):
            _parsear_fecha("14/07/2026")


class TestEstado:
    def test_archivo_inexistente(self, tmp_path):
        estado = _cargar_estado(str(tmp_path / "no_existe.json"))
        assert estado == {"ultima_fecha_enviada": None}

    def test_json_valido(self, tmp_path):
        ruta = tmp_path / "estado.json"
        ruta.write_text('{"ultima_fecha_enviada": "2026-05-26"}', encoding="utf-8")
        assert _cargar_estado(str(ruta)) == {"ultima_fecha_enviada": "2026-05-26"}

    def test_json_corrupto(self, tmp_path):
        ruta = tmp_path / "estado.json"
        ruta.write_text("{no valido", encoding="utf-8")
        assert _cargar_estado(str(ruta)) == {"ultima_fecha_enviada": None}

    def test_json_sin_clave(self, tmp_path):
        ruta = tmp_path / "estado.json"
        ruta.write_text('{"otra_clave": 1}', encoding="utf-8")
        estado = _cargar_estado(str(ruta))
        assert estado["ultima_fecha_enviada"] is None

    def test_guardar_y_recargar(self, tmp_path):
        ruta = tmp_path / "estado.json"
        _guardar_estado(str(ruta), {"ultima_fecha_enviada": "2026-05-26"})
        assert _cargar_estado(str(ruta))["ultima_fecha_enviada"] == "2026-05-26"


class TestEjecutarPipeline:
    @pytest.fixture
    def pipeline_mocks(self, monkeypatch, texto_diario_mock, html_boletin_mock):
        monkeypatch.setattr(main, "configurar_logging", lambda: None)
        monkeypatch.setattr(main, "load_dotenv", lambda: None)
        config = MagicMock()
        config.base_url = "https://example.com"
        config.gemini_api_key = "key"
        config.email_user = "u@t.com"
        config.email_password = "x" * 16
        config.email_destinatario = "d@t.com"
        monkeypatch.setattr(main, "_cargar_configuracion", lambda: config)

        scraper = MagicMock()
        scraper.obtener_texto_diario.return_value = texto_diario_mock
        generador = MagicMock()
        generador.generar_resumen.return_value = html_boletin_mock
        notificador = MagicMock()

        monkeypatch.setattr(main, "DiarioOficialScraper", lambda **k: scraper)
        monkeypatch.setattr(main, "GeneradorResumenes", lambda **k: generador)
        monkeypatch.setattr(main, "EmailNotifier", lambda **k: notificador)
        return scraper, generador, notificador

    def test_salta_si_edicion_ya_enviada(self, pipeline_mocks, tmp_path):
        _, generador, notificador = pipeline_mocks
        ruta = tmp_path / "estado.json"
        _guardar_estado(str(ruta), {"ultima_fecha_enviada": "2026-05-26"})

        _ejecutar_pipeline(fecha=date(2026, 5, 26), ruta_estado=str(ruta))

        generador.generar_resumen.assert_not_called()
        notificador.enviar_boletin.assert_not_called()

    def test_envia_y_actualiza_estado(self, pipeline_mocks, tmp_path):
        _, generador, notificador = pipeline_mocks
        ruta = tmp_path / "estado.json"
        _guardar_estado(str(ruta), {"ultima_fecha_enviada": "2026-05-25"})

        _ejecutar_pipeline(fecha=date(2026, 5, 26), ruta_estado=str(ruta))

        generador.generar_resumen.assert_called_once()
        notificador.enviar_boletin.assert_called_once()
        assert _cargar_estado(str(ruta))["ultima_fecha_enviada"] == "2026-05-26"

    def test_fuerza_reenvia_aun_si_coincide(self, pipeline_mocks, tmp_path):
        _, generador, notificador = pipeline_mocks
        ruta = tmp_path / "estado.json"
        _guardar_estado(str(ruta), {"ultima_fecha_enviada": "2026-05-26"})

        _ejecutar_pipeline(
            fecha=date(2026, 5, 26), ruta_estado=str(ruta), fuerza=True
        )

        generador.generar_resumen.assert_called_once()
        notificador.enviar_boletin.assert_called_once()

    def test_fallback_no_repite_ultima_publicacion(
        self, pipeline_mocks, tmp_path, texto_diario_mock
    ):
        scraper, generador, notificador = pipeline_mocks
        scraper.obtener_texto_diario.return_value = None
        scraper.obtener_texto_ultima_publicacion.return_value = (
            texto_diario_mock,
            date(2026, 5, 26),
        )
        ruta = tmp_path / "estado.json"
        _guardar_estado(str(ruta), {"ultima_fecha_enviada": "2026-05-26"})

        _ejecutar_pipeline(ruta_estado=str(ruta))

        generador.generar_resumen.assert_not_called()
        notificador.enviar_boletin.assert_not_called()
