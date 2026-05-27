from __future__ import annotations

import logging
import os
from unittest.mock import patch

import pytest

from main import _cargar_configuracion, configurar_logging, validar_html, _Config


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
        monkeypatch.setenv("EMAIL_PASSWORD", "password")
        monkeypatch.delenv("EMAIL_DESTINATARIO", raising=False)
        monkeypatch.delenv("BASE_URL", raising=False)

        config = _cargar_configuracion()

        assert config.gemini_api_key == "fake-key"
        assert config.email_user == "user@test.com"
        assert config.email_password == "password"
        assert config.email_destinatario == "user@test.com"
        assert config.base_url == "https://www.diariooficial.gob.sv"

    def test_variables_opcionales_personalizadas(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "key")
        monkeypatch.setenv("EMAIL_USER", "u@t.com")
        monkeypatch.setenv("EMAIL_PASSWORD", "p")
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


class TestValidarHtml:
    def test_html_valido(self):
        assert validar_html("<h1>Radar Político</h1>") is True

    def test_html_vacio(self):
        assert validar_html("") is False

    def test_html_solo_espacios(self):
        assert validar_html("   ") is False

    def test_html_sin_tags(self):
        assert validar_html("Esto no es HTML") is False
