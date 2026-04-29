"""
Excel validation and reading skills for the AI Agent.
Wraps the existing excel_validator module as agent skills.
"""
from typing import Dict, Any, Optional
import os

from skills.base import Skill
from excel_validator import validate_excel_safety, get_safe_excel_content


class ExcelValidateSkill(Skill):
    """Skill to validate an Excel file for malicious content."""

    @property
    def name(self) -> str:
        return "validate_excel"

    @property
    def requires_file_upload(self) -> bool:
        return True

    def get_description(self) -> str:
        return (
            "Valida si un archivo Excel (.xlsx) contiene código malicioso o sospechoso. "
            "Escanea fórmulas en busca de macros VBA peligrosas (Auto_Open, Shell, CreateObject, etc.), "
            "referencias a ejecutables externos, y patrones de descarga remota. "
            "Retorna un reporte detallado de seguridad."
        )

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.get_description(),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Ruta del archivo Excel a validar (archivo temporal)"
                        },
                        "filename": {
                            "type": "string",
                            "description": "Nombre original del archivo"
                        }
                    },
                    "required": ["file_path"]
                }
            }
        }

    async def execute(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        file_path = params.get("file_path")
        if not file_path:
            return {"success": False, "error": "Se requiere la ruta del archivo Excel"}

        if not file_path.endswith('.xlsx'):
            return {
                "success": False,
                "error": f"Formato no válido. Solo se permiten archivos .xlsx"
            }

        try:
            if not os.path.exists(file_path):
                return {"success": False, "error": "El archivo no existe en la ruta especificada"}

            validation_result = validate_excel_safety(file_path)

            # Build a human-readable summary
            details = validation_result["details"]
            summary_parts = [
                f"📊 **Archivo:** {params.get('filename', 'N/A')}",
                f"📑 **Hojas analizadas:** {details['sheets']}",
                f"🔢 **Celdas analizadas:** {details['cells_analyzed']:,}",
                f"📝 **Fórmulas encontradas:** {details['formulas_found']}"
            ]

            if validation_result["safe"]:
                summary_parts.insert(0, "✅ **El archivo es SEGURO**")
                if details.get("has_vba"):
                    summary_parts.append(
                        "⚠️ *Nota: El archivo contiene macros VBA, aunque no se detectaron patrones maliciosos*"
                    )
            else:
                summary_parts.insert(0, "❌ **El archivo CONTIENE código sospechoso**")
                if details["malicious_patterns_found"]:
                    summary_parts.append(f"🚨 **Patrones maliciosos detectados:** {len(details['malicious_patterns_found'])}")
                    for threat in details["malicious_patterns_found"][:5]:
                        summary_parts.append(
                            f"  - Celda {threat['cell']} en '{threat['sheet']}': "
                            f"patrón `{threat['pattern_matched']}`"
                        )

            if details["unusual_cells"]:
                summary_parts.append(f"⚠️ **Celdas con contenido inusual:** {len(details['unusual_cells'])}")

            if validation_result["errors"]:
                summary_parts.append(f"❌ **Errores:** {len(validation_result['errors'])}")

            # Return both structured data and human summary
            return {
                "success": True,
                "is_safe": validation_result["safe"],
                "summary": "\n".join(summary_parts),
                "details": {
                    "sheets_analyzed": details["sheets"],
                    "cells_analyzed": details["cells_analyzed"],
                    "formulas_found": details["formulas_found"],
                    "has_vba": details.get("has_vba", False),
                    "malicious_patterns_count": len(details["malicious_patterns_found"]),
                    "malicious_patterns": [
                        {
                            "sheet": t["sheet"],
                            "cell": t["cell"],
                            "pattern": t["pattern_matched"]
                        }
                        for t in details["malicious_patterns_found"][:20]
                    ],
                    "unusual_cells_count": len(details["unusual_cells"]),
                    "warnings": validation_result["warnings"],
                    "errors": validation_result["errors"]
                }
            }

        except Exception as e:
            return {"success": False, "error": f"Error al validar el archivo Excel: {str(e)}"}


class ExcelReadSkill(Skill):
    """Skill to read the contents of an Excel file safely."""

    @property
    def name(self) -> str:
        return "read_excel"

    @property
    def requires_file_upload(self) -> bool:
        return True

    def get_description(self) -> str:
        return (
            "Lee el contenido de un archivo Excel (.xlsx) de forma segura "
            "(solo valores, sin ejecutar fórmulas). Primero valida que el archivo "
            "no contenga código malicioso. Útil para extraer datos de hojas de cálculo."
        )

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.get_description(),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Ruta del archivo Excel a leer (archivo temporal)"
                        },
                        "filename": {
                            "type": "string",
                            "description": "Nombre original del archivo"
                        }
                    },
                    "required": ["file_path"]
                }
            }
        }

    async def execute(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        file_path = params.get("file_path")
        if not file_path:
            return {"success": False, "error": "Se requiere la ruta del archivo Excel"}

        if not file_path.endswith('.xlsx'):
            return {
                "success": False,
                "error": f"Formato no válido. Solo se permiten archivos .xlsx"
            }

        try:
            if not os.path.exists(file_path):
                return {"success": False, "error": "El archivo no existe en la ruta especificada"}

            # First validate security
            validation = validate_excel_safety(file_path)
            if not validation["safe"]:
                return {
                    "success": False,
                    "error": "El archivo contiene código malicioso y no puede leerse de forma segura",
                    "validation_details": {
                        "malicious_patterns": [
                            {"sheet": t["sheet"], "cell": t["cell"]}
                            for t in validation["details"]["malicious_patterns_found"]
                        ]
                    }
                }

            # Read safe content
            content = get_safe_excel_content(file_path)

            sheets_summary = []
            preview = {}
            for sheet_name, rows in content.get("sheets", {}).items():
                num_rows = len(rows)
                num_cols = max(len(r) for r in rows) if rows else 0
                sheets_summary.append(f"📄 **'{sheet_name}'**: {num_rows} filas x {num_cols} columnas")

                # Include first 5 rows as preview
                preview[sheet_name] = {
                    "rows": num_rows,
                    "columns": num_cols,
                    "preview": rows[:5] if rows else []
                }

            metadata = content.get("metadata", {})
            summary_parts = [
                f"📊 **Archivo:** {metadata.get('filename', params.get('filename', 'N/A'))}",
                f"📑 **Hojas encontradas:** {len(sheets_summary)}",
            ]
            summary_parts.extend(sheets_summary)
            summary_parts.append(f"📏 **Dimensiones:** {metadata.get('rows', 0):,} filas x {metadata.get('columns', 0)} columnas")

            return {
                "success": True,
                "summary": "\n".join(summary_parts),
                "sheets_count": len(content.get("sheets", {})),
                "total_rows": metadata.get("rows", 0),
                "sheets": preview
            }

        except Exception as e:
            return {"success": False, "error": f"Error al leer el archivo Excel: {str(e)}"}
