from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def fecha_hoy() -> date:
    return date(2026, 5, 26)


@pytest.fixture
def texto_diario_mock() -> str:
    return (
        "DECRETO EJECUTIVO N° 123.\n"
        "EL PRESIDENTE DE LA REPÚBLICA,\n"
        "CONSIDERANDO:\n"
        "I. Que es necesario nombrar al Ministro de Hacienda.\n"
        "DECRETA:\n"
        "Art. 1.- Nómbrase al señor Juan Pérez como Ministro de Hacienda.\n"
        "DADO EN CASA PRESIDENCIAL, San Salvador, a los 26 días de mayo de 2026.\n"
        "(Acuerdo N° 123, p. 5)\n"
    )


@pytest.fixture
def html_boletin_mock() -> str:
    return (
        "<h1>Radar Político — Diario Oficial 26/05/2026</h1>"
        "<p><strong>Resumen:</strong> 1 noticia encontrada — Presidencia</p>"
        "<h2>Presidencia de la República</h2>"
        "<h3>Nombramiento de Ministro de Hacienda</h3>"
        "<p>El Presidente nombró a Juan Pérez como Ministro de Hacienda. "
        "<em>(Acuerdo N° 123, p. 5)</em></p>"
    )


@pytest.fixture
def pdf_bytes_mock() -> bytes:
    return b"%PDF-1.4\n%\x93\x8c\x8b\x9e\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\nxref\n0 4\n0000000000 65535 f \n0000000015 00000 n \n0000000068 00000 n \n0000000130 00000 n \ntrailer\n<< /Root 1 0 R /Size 4 >>\nstartxref\n210\n%%EOF"


def crear_mock_response(json_data=None, content=None, status_code=200):
    resp = MagicMock()
    resp.json.return_value = json_data or []
    resp.content = content or b""
    resp.status_code = status_code
    resp.raise_for_status = MagicMock()
    return resp
