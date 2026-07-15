"""Agente conversacional que consulta de forma segura el dataset SQLite."""

from __future__ import annotations

import asyncio
import json
import os
import re
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from openai import AsyncOpenAI


DEFAULT_DATABASE = Path(__file__).parent / "data" / "stock-y-ventas" / "Ventas_3.db"
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
MAX_ROWS = 200

SYSTEM_PROMPT = """Eres un analista de negocio conversacional que responde en español.
Tu única fuente para afirmaciones sobre el negocio es la base SQLite disponible mediante
la herramienta consultar_dataset. Usa la herramienta siempre que la pregunta requiera
datos, cálculos o verificaciones. No inventes cifras ni supongas la moneda: el dataset no
la especifica, así que presenta importes como valores monetarios sin atribuir una divisa.

Explica los resultados de forma clara, permite preguntas de seguimiento y señala límites
o ambigüedades del dataset. Para ingresos, une FACT_PROD con FACTURA y PRECIO usando el
producto y el mismo mes: substr(PRECIO.Fecha,1,7) = substr(FACTURA.Fecha,1,7). El importe
de una línea es FACT_PROD.Cantidad * PRECIO.Precio. Para stock actual usa el registro de
mayor id de STOCK para cada Product_id, porque puede haber varios registros por día.

Esquema:
- FACTURA(id, Comentario, CC_comprador_hash, Fecha)
- FACT_PROD(id, Factura_id, Producto_id, Cantidad)
- PRECIO(id, Producto_id, Fecha, Precio), un precio mensual por producto
- PRODUCTOS(id, Nombre, Descripcion)
- STOCK(id, Product_id, Cantidad, Fecha)

Solo tienes datos desde 2015-01-01 hasta 2024-12-31. Distingue ingresos, unidades,
facturas, clientes y stock. Resume tablas largas y ofrece conclusiones accionables cuando
los datos las respalden."""

SYSTEM_PROMPT += """

Cuando el usuario solicite una gráfica, usa crear_grafica. La consulta debe devolver
exactamente una columna de etiquetas y una columna numérica. Para participaciones con
más de 12 categorías prefiere barras horizontales; usa circular solo con 12 o menos.
Limita el resultado a 30 categorías y explica brevemente qué muestra la imagen."""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "consultar_dataset",
            "description": (
                "Ejecuta una única consulta SQLite de solo lectura sobre ventas, productos, "
                "precios, facturas y stock. Devuelve columnas y hasta 200 filas."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "Consulta SQL SQLite que comienza con SELECT o WITH.",
                    }
                },
                "required": ["sql"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "crear_grafica",
            "description": (
                "Crea una imagen PNG a partir de una consulta SQLite de solo lectura. "
                "Úsala cuando el usuario solicite una gráfica o visualización."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "SELECT que devuelve etiquetas y valores numéricos.",
                    },
                    "titulo": {"type": "string"},
                    "tipo": {
                        "type": "string",
                        "enum": ["barras", "lineas", "circular"],
                    },
                    "columna_etiqueta": {"type": "string"},
                    "columna_valor": {"type": "string"},
                },
                "required": [
                    "sql",
                    "titulo",
                    "tipo",
                    "columna_etiqueta",
                    "columna_valor",
                ],
                "additionalProperties": False,
            },
        },
    },
]

FORBIDDEN_SQL = re.compile(
    r"\b(attach|detach|insert|update|delete|replace|create|alter|drop|truncate|"
    r"vacuum|reindex|analyze|pragma|load_extension)\b",
    re.IGNORECASE,
)


class DatasetQueryError(ValueError):
    """Consulta rechazada o inválida."""


class DatasetReader:
    """Ejecutor SQLite limitado a consultas de solo lectura."""

    def __init__(self, database: Path = DEFAULT_DATABASE) -> None:
        if not database.exists():
            raise FileNotFoundError(f"No se encontró la base de datos: {database}")
        self.database = database.resolve()

    def query(self, sql: str) -> dict[str, Any]:
        normalized = sql.strip()
        if not re.match(r"^(select|with)\b", normalized, re.IGNORECASE):
            raise DatasetQueryError("Solo se permiten consultas SELECT o WITH.")
        if ";" in normalized.rstrip(";") or FORBIDDEN_SQL.search(normalized):
            raise DatasetQueryError("La consulta contiene una operación no permitida.")

        connection = sqlite3.connect(f"file:{self.database.as_posix()}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only = ON")
        deadline = time.monotonic() + 5
        connection.set_progress_handler(lambda: int(time.monotonic() > deadline), 10_000)
        try:
            cursor = connection.execute(normalized)
            rows = cursor.fetchmany(MAX_ROWS + 1)
            columns = [item[0] for item in cursor.description or []]
        except sqlite3.Error as exc:
            raise DatasetQueryError(f"SQLite rechazó la consulta: {exc}") from exc
        finally:
            connection.close()

        truncated = len(rows) > MAX_ROWS
        rows = rows[:MAX_ROWS]
        return {
            "columns": columns,
            "rows": [[row[column] for column in columns] for row in rows],
            "row_count": len(rows),
            "truncated": truncated,
        }


@dataclass
class AssistantReply:
    """Respuesta textual y archivos gráficos producidos durante el análisis."""

    text: str
    charts: list[Path]


class ChartGenerator:
    """Genera gráficos PNG a partir de resultados validados del dataset."""

    def __init__(self, reader: DatasetReader) -> None:
        self.reader = reader
        self.output_dir = Path(__file__).parent / "tmp" / "charts"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def create(
        self,
        sql: str,
        title: str,
        chart_type: str,
        label_column: str,
        value_column: str,
    ) -> Path:
        result = self.reader.query(sql)
        if label_column not in result["columns"] or value_column not in result["columns"]:
            raise DatasetQueryError("Las columnas indicadas no aparecen en la consulta.")
        if not result["rows"]:
            raise DatasetQueryError("La consulta no devolvió datos para graficar.")
        if len(result["rows"]) > 30:
            raise DatasetQueryError("La gráfica admite como máximo 30 categorías.")

        label_index = result["columns"].index(label_column)
        value_index = result["columns"].index(value_column)
        labels = [str(row[label_index]) for row in result["rows"]]
        try:
            values = [float(row[value_index]) for row in result["rows"]]
        except (TypeError, ValueError) as exc:
            raise DatasetQueryError("La columna de valores debe ser numérica.") from exc

        height = max(5.0, min(12.0, len(labels) * 0.42))
        figure, axis = plt.subplots(figsize=(11, height))
        if chart_type == "circular":
            if len(labels) > 12:
                raise DatasetQueryError("Una gráfica circular admite máximo 12 categorías.")
            axis.pie(values, labels=labels, autopct="%1.1f%%", startangle=90)
            axis.axis("equal")
        elif chart_type == "lineas":
            axis.plot(labels, values, marker="o", linewidth=2)
            axis.tick_params(axis="x", rotation=45)
            axis.grid(axis="y", alpha=0.25)
        else:
            axis.barh(labels, values, color="#4C78A8")
            axis.invert_yaxis()
            axis.grid(axis="x", alpha=0.25)

        axis.set_title(title, fontsize=14, pad=14)
        figure.tight_layout()
        path = self.output_dir / f"chart-{uuid.uuid4().hex}.png"
        figure.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(figure)
        return path


class AIBusinessAssistant:
    """Mantiene una conversación independiente por chat de Telegram."""

    def __init__(self) -> None:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("Define GROQ_API_KEY antes de iniciar el bot.")
        self.client = AsyncOpenAI(api_key=api_key, base_url=GROQ_BASE_URL)
        self.reader = DatasetReader()
        self.chart_generator = ChartGenerator(self.reader)
        self.histories: dict[int, list[dict[str, str]]] = {}
        self.locks: dict[int, asyncio.Lock] = {}

    def reset(self, chat_id: int) -> None:
        self.histories.pop(chat_id, None)

    async def answer(self, chat_id: int, message: str) -> AssistantReply:
        lock = self.locks.setdefault(chat_id, asyncio.Lock())
        async with lock:
            history = self.histories.setdefault(chat_id, [])
            working_messages: list[dict[str, Any]] = [
                {"role": "system", "content": SYSTEM_PROMPT},
                *history,
                {"role": "user", "content": message},
            ]
            charts: list[Path] = []

            for _ in range(6):
                response = await self.client.chat.completions.create(
                    model=MODEL,
                    messages=working_messages,
                    tools=TOOLS,
                    tool_choice="auto",
                )
                response_message = response.choices[0].message
                calls = response_message.tool_calls or []
                if not calls:
                    answer = response_message.content or "No pude generar una respuesta."
                    history.extend(
                        [
                            {"role": "user", "content": message},
                            {"role": "assistant", "content": answer},
                        ]
                    )
                    self.histories[chat_id] = history[-20:]
                    return AssistantReply(text=answer, charts=charts)

                working_messages.append(response_message.model_dump(exclude_none=True))
                for call in calls:
                    try:
                        arguments = json.loads(call.function.arguments)
                        if call.function.name == "consultar_dataset":
                            result = self.reader.query(arguments["sql"])
                            output = json.dumps(result, ensure_ascii=False)
                        elif call.function.name == "crear_grafica":
                            chart = self.chart_generator.create(
                                sql=arguments["sql"],
                                title=arguments["titulo"],
                                chart_type=arguments["tipo"],
                                label_column=arguments["columna_etiqueta"],
                                value_column=arguments["columna_valor"],
                            )
                            charts.append(chart)
                            output = json.dumps(
                                {"grafica_creada": True, "archivo": chart.name},
                                ensure_ascii=False,
                            )
                        else:
                            raise DatasetQueryError("La herramienta solicitada no existe.")
                    except (KeyError, json.JSONDecodeError, DatasetQueryError) as exc:
                        output = json.dumps({"error": str(exc)}, ensure_ascii=False)
                    working_messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.id,
                            "content": output,
                        }
                    )

            raise RuntimeError("La IA excedió el límite de consultas para una respuesta.")
