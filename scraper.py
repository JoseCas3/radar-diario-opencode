from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import date
from io import BytesIO

import requests
from PyPDF2 import PdfReader
from PyPDF2.errors import PyPdfError

logger = logging.getLogger(__name__)

BASE_URL = "https://www.diariooficial.gob.sv"
TIMEOUT_SEGUNDOS = 30
MAX_REINTENTOS = 3
BACKOFF_INICIAL = 2


@dataclass
class PublicacionDiario:
    id: int
    fecha_inicio: str
    nombre_archivo: str


class DiarioOficialScraper:
    """Extrae el texto del Diario Oficial de El Salvador para la fecha solicitada."""

    def __init__(
        self,
        base_url: str = BASE_URL,
        timeout: int = TIMEOUT_SEGUNDOS,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._sesion = requests.Session()
        self._sesion.headers.update({"User-Agent": "RadarDiarioOficial/1.0"})

    def obtener_texto_diario(self, fecha: date | None = None) -> str | None:
        """Obtiene el texto completo del Diario Oficial para la fecha dada (hoy por defecto).

        Retorna None si no existe publicación para la fecha solicitada.
        """
        fecha_obj = fecha or date.today()
        publicacion = self._buscar_publicacion(fecha_obj)
        if publicacion is None:
            logger.info(
                "No hay publicación del Diario Oficial para %s", fecha_obj.isoformat()
            )
            return None
        pdf_bytes = self._descargar_pdf(publicacion.id)
        texto = self._extraer_texto_pdf(pdf_bytes)
        logger.info("Texto extraído del Diario Oficial: %d caracteres", len(texto))
        return texto

    def obtener_texto_ultima_publicacion(self) -> tuple[str, date] | None:
        """Obtiene el texto de la publicación más reciente disponible.

        Retorna una tupla (texto, fecha_publicacion) o None si no hay publicaciones.
        """
        hoy = date.today()
        publicacion = self._buscar_ultima_publicacion(hoy.year)
        if publicacion is None and hoy.year > 2020:
            publicacion = self._buscar_ultima_publicacion(hoy.year - 1)
        if publicacion is None:
            logger.info("No se encontró ninguna publicación disponible")
            return None
        fecha_pub = date.fromisoformat(publicacion.fecha_inicio)
        pdf_bytes = self._descargar_pdf(publicacion.id)
        texto = self._extraer_texto_pdf(pdf_bytes)
        logger.info(
            "Texto extraído de última publicación (%s): %d caracteres",
            publicacion.fecha_inicio,
            len(texto),
        )
        return texto, fecha_pub

    def _buscar_ultima_publicacion(self, year: int) -> PublicacionDiario | None:
        try:
            meses = self._obtener_meses_disponibles(year)
        except Exception:
            logger.warning("No se pudieron obtener meses del año %d", year)
            return None
        if not meses:
            return None
        ultimo_mes = max(meses)
        diarios = self._obtener_diarios_disponibles(year, ultimo_mes)
        if not diarios:
            return None
        diarios_ordenados = sorted(diarios, key=lambda d: d.fecha_inicio, reverse=True)
        ultima = diarios_ordenados[0]
        logger.info(
            "Última publicación encontrada: ID=%s, %s",
            ultima.id,
            ultima.nombre_archivo,
        )
        return ultima

    def _buscar_publicacion(self, fecha_obj: date) -> PublicacionDiario | None:
        meses = self._obtener_meses_disponibles(fecha_obj.year)
        if fecha_obj.month not in meses:
            logger.info(
                "El mes %d/%d no tiene publicaciones en el Diario Oficial",
                fecha_obj.month,
                fecha_obj.year,
            )
            return None
        diarios = self._obtener_diarios_disponibles(fecha_obj.year, fecha_obj.month)
        fecha_str = fecha_obj.isoformat()
        for diario in diarios:
            if diario.fecha_inicio == fecha_str:
                logger.info(
                    "Publicación encontrada: ID=%d, %s",
                    diario.id,
                    diario.nombre_archivo,
                )
                return diario
        return None

    def _obtener_meses_disponibles(self, year: int) -> list[int]:
        try:
            respuesta = self._reintentar_http(
                "meses-disponibles",
                f"{self._base_url}/api/v1/meses-disponibles",
                "POST",
                json={"year": year},
            )
            return [int(item["month"]) for item in respuesta.json()]
        except (requests.RequestException, KeyError, ValueError) as e:
            logger.error(
                "Error al consultar meses disponibles año=%d: %s", year, e
            )
            raise

    def _obtener_diarios_disponibles(
        self, year: int, month: int
    ) -> list[PublicacionDiario]:
        try:
            respuesta = self._reintentar_http(
                "diarios-disponibles",
                f"{self._base_url}/api/v1/diarios-disponibles",
                "POST",
                data={"year": str(year), "month": str(month)},
            )
            datos = respuesta.json()
        except (requests.RequestException, KeyError, ValueError, TypeError) as e:
            logger.error(
                "Error al consultar diarios disponibles año=%d mes=%d: %s",
                year,
                month,
                e,
            )
            raise
        return [
            PublicacionDiario(
                id=item["Id"],
                fecha_inicio=item["FechaInicio"],
                nombre_archivo=item["NombreArchivo"],
            )
            for item in datos
        ]

    def _descargar_pdf(self, id_publicacion: int) -> bytes:
        url = f"{self._base_url}/seleccion/{id_publicacion}"
        try:
            respuesta = self._reintentar_http(
                "descargar-pdf", url, "GET"
            )
            logger.info("PDF descargado: %d bytes", len(respuesta.content))
            return respuesta.content
        except requests.RequestException as e:
            logger.error("Error al descargar PDF ID=%d: %s", id_publicacion, e)
            raise

    def _reintentar_http(self, operacion: str, url: str, metodo: str, **kwargs):
        """Ejecuta una petición HTTP con reintentos y backoff exponencial."""
        ultima_excepcion: Exception | None = None
        for intento in range(1, MAX_REINTENTOS + 1):
            try:
                respuesta = self._sesion.request(
                    metodo, url, timeout=self._timeout, **kwargs
                )
                respuesta.raise_for_status()
                return respuesta
            except requests.RequestException as e:
                ultima_excepcion = e
                if intento < MAX_REINTENTOS:
                    espera = BACKOFF_INICIAL**intento
                    logger.warning(
                        "Error en %s (intento %d/%d): %s. Reintentando en %ds...",
                        operacion,
                        intento,
                        MAX_REINTENTOS,
                        e,
                        espera,
                    )
                    time.sleep(espera)
                else:
                    logger.error(
                        "Fallaron los %d intentos en %s: %s",
                        MAX_REINTENTOS,
                        operacion,
                        e,
                    )
        raise ultima_excepcion

    def _extraer_texto_pdf(self, pdf_bytes: bytes) -> str:
        """Extrae el texto de un PDF en memoria usando PyPDF2."""
        try:
            with BytesIO(pdf_bytes) as stream:
                reader = PdfReader(stream)
                paginas_texto: list[str] = []
                for pagina in reader.pages:
                    texto = pagina.extract_text()
                    if texto:
                        paginas_texto.append(texto)
                return "\n".join(paginas_texto)
        except (ValueError, TypeError, OSError, PyPdfError) as e:
            logger.error("Error al extraer texto del PDF: %s", e)
            raise
