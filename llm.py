from __future__ import annotations

import logging
import time

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

MODELO_POR_DEFECTO = "gemini-2.5-flash"
MAX_REINTENTOS = 3
BACKOFF_INICIAL = 2
MAX_CARACTERES = 800_000

PROMPT_SISTEMA = """\
Eres un asistente editorial especializado para el Jefe de Redacción Política de un \
medio de comunicación en El Salvador. Tu única fuente de información es el texto del \
Diario Oficial de El Salvador que se te proporciona.

INSTRUCCIONES CRÍTICAS:
1. CERO ALUCINACIÓN: Solo puedes reportar información que aparezca EXPLÍCITAMENTE \
en el texto fuente. Está prohibido inferir, interpretar, contextualizar o añadir \
cualquier dato que no conste literalmente en el documento.
2. Si el texto no contiene noticias de relevancia política, debes generar un HTML \
que simplemente indique "Sin noticias políticas relevantes en esta edición".
3. Cada noticia debe incluir referencia exacta al documento fuente: número de \
acuerdo, decreto o resolución, y número de página cuando esté disponible.
4. NO incluyas: avisos de licitación, edictos judiciales de rutina, avisos de \
remate, convocatorias genéricas ni esquelas, a menos que involucren directamente \
a altos funcionarios del Estado.

QUÉ CONSTITUYE NOTICIA POLÍTICA:
- Nombramientos, renuncias o destituciones de funcionarios públicos
- Nuevos decretos ejecutivos o legislativos
- Reformas a leyes o reglamentos
- Creación, fusión o reestructuración de instituciones públicas
- Presupuestos, asignaciones o modificaciones presupuestarias de entidades estatales
- Tratados, convenios o acuerdos internacionales
- Declaratorias de estado de emergencia, calamidad o duelo nacional
- Decisiones de alto impacto de ministerios, presidencia, asamblea legislativa \
o corte suprema de justicia

FORMATO DE SALIDA:
Genera únicamente HTML válido, sin bloques de código, sin markdown. La estructura \
debe ser:

<h1>Radar Político — Diario Oficial [FECHA]</h1>
<p><strong>Resumen:</strong> [1-2 líneas con cantidad de noticias encontradas y \
entidades mencionadas]</p>

<h2>[MINISTERIO / ENTIDAD]</h2>
<h3>[Título descriptivo de la noticia]</h3>
<p>[Resumen objetivo de 2-3 líneas] <em>(Acuerdo N° XXX, p. YY)</em></p>

Repite el bloque h2/h3/p por cada entidad. Agrupa las noticias por ministerio o \
entidad. Si una entidad tiene múltiples noticias, agrúpalas bajo el mismo h2.

Aplica CSS inline: fuente system-ui o sans-serif, color #1a1a1a, fondo blanco, \
títulos en #0d47a1, líneas separatorias sutiles, espaciado generoso. El diseño \
debe ser limpio, profesional y escaneable en segundos."""


class GeneradorResumenes:
    """Genera un boletín HTML de noticias políticas a partir del texto del Diario Oficial."""

    def __init__(
        self,
        api_key: str,
        modelo: str = MODELO_POR_DEFECTO,
        max_reintentos: int = MAX_REINTENTOS,
    ) -> None:
        self._modelo = modelo
        self._max_reintentos = max_reintentos
        self._cliente = genai.Client(api_key=api_key)

    def generar_resumen(self, texto_diario: str, fecha: str = "") -> str:
        """Genera el boletín HTML de noticias políticas desde el texto del Diario Oficial."""
        texto_truncado = self._truncar_texto(texto_diario)
        prompt_usuario = self._construir_prompt(texto_truncado, fecha)
        config = types.GenerateContentConfig(
            system_instruction=PROMPT_SISTEMA,
            temperature=0.1,
            top_p=0.95,
            max_output_tokens=8192,
        )
        return self._intentar_generar(prompt_usuario, config)

    def _truncar_texto(self, texto: str) -> str:
        """Trunca el texto si excede MAX_CARACTERES para no sobrepasar el contexto del modelo."""
        if len(texto) <= MAX_CARACTERES:
            return texto
        logger.warning(
            "Texto truncado a %d caracteres (original: %d)",
            MAX_CARACTERES,
            len(texto),
        )
        return texto[:MAX_CARACTERES]

    def _intentar_generar(
        self, prompt: str, config: types.GenerateContentConfig
    ) -> str:
        """Llama a Gemini con reintentos y backoff. Lanza RuntimeError si todos fallan."""
        ultima_excepcion: Exception | None = None
        for intento in range(1, self._max_reintentos + 1):
            try:
                response = self._cliente.models.generate_content(
                    model=self._modelo, contents=prompt, config=config
                )
                if not response.text:
                    raise ValueError("Gemini devolvió una respuesta vacía")
                logger.info(
                    "Resumen generado: %d caracteres (intento %d/%d)",
                    len(response.text),
                    intento,
                    self._max_reintentos,
                )
                return response.text
            except Exception as e:
                ultima_excepcion = e
                if intento < self._max_reintentos:
                    espera = BACKOFF_INICIAL**intento
                    logger.warning(
                        "Error en intento %d/%d: %s. Reintentando en %ds...",
                        intento,
                        self._max_reintentos,
                        e,
                        espera,
                    )
                    time.sleep(espera)
                else:
                    logger.error(
                        "Fallaron los %d intentos. Último error: %s",
                        self._max_reintentos,
                        e,
                    )
        raise RuntimeError(
            f"No se pudo generar el resumen tras {self._max_reintentos} intentos"
        ) from ultima_excepcion

    def _construir_prompt(self, texto: str, fecha: str) -> str:
        encabezado = f"FECHA DEL DIARIO OFICIAL: {fecha}" if fecha else ""
        return f"{encabezado}\n\nTEXTO DEL DIARIO OFICIAL:\n\n{texto}"
