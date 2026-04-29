import re
from openpyxl import load_workbook
from typing import List, Dict, Any

# Patrones de código malicioso (funciones estándar de Excel son permitidas)
MALICIOUS_PATTERNS = [
    # Macros y ejecución automática
    r'(?i)Auto_?Open',
    r'(?i)Auto_?Close',
    r'(?i)Auto_?Activate',
    r'(?i)Auto_?Deactivate',
    r'(?i)Auto_?Exec',
    r'(?i)Auto_?Run',
    
    # Ejecución de comandos del sistema
    r'(?i)Shell\s*\(',
    r'(?i)WScript\.Shell',
    r'(?i)CreateObject\s*\(\s*["\']WScript\.Shell["\']',
    r'(?i)CreateObject\s*\(\s*["\']Shell\.Application["\']',
    r'(?i)Run\s*\(',
    r'(?i)Exec\s*\(',
    
    # Acceso a sistema de archivos
    r'(?i)CreateObject\s*\(\s*["\']Scripting\.FileSystemObject["\']',
    r'(?i)FileSystemObject',
    r'(?i)\.DeleteFile\s*\(',
    r'(?i)\.DeleteFolder\s*\(',
    r'(?i)\.CopyFile\s*\(',
    r'(?i)\.MoveFile\s*\(',
    r'(?i)\.WriteLine\s*\(',
    r'(?i)\.Write\s*\(',
    r'(?i)\.SaveToFile\s*\(',
    r'(?i)\.OpenTextFile\s*\(',
    
    # Comandos del sistema operativo
    r'(?i)cmd\s*\.',
    r'(?i)PowerShell\s*\.',
    r'(?i)MSHTA',
    r'(?i)CertUtil',
    r'(?i)BitsAdmin',
    r'(?i)wmic\s+',
    r'(?i)regsvr32\s+',
    
    # Descarga y ejecución remota
    r'(?i)URLDownloadToFile',
    r'(?i)WinHttp\.WinHttpRequest',
    r'(?i)XMLHTTP',
    r'(?i)\.send\s*\(',
    r'(?i)\.responseText',
    r'(?i)\.responseBody',
    
    # Conexiones externas no autorizadas
    r'(?i)CreateObject\s*\(\s*["\']MSXML2\.',
    r'(?i)CreateObject\s*\(\s*["\']WinHttp\.',
    r'(?i)\.open\s*\(\s*["\']GET["\']',
    r'(?i)\.open\s*\(\s*["\']POST["\']',
    
    # Funciones peligrosas de VBA
    r'(?i)VBA\.Shell',
    r'(?i)VBA\.CreateObject',
    r'(?i)VBA\.CallByName',
    r'(?i)\.FormulaHidden\s*=\s*True',
    r'(?i)\.VeryHidden\s*=\s*True',
]

# Funciones estándar de Excel permitidas (para no generar falsos positivos)
STANDARD_EXCEL_FUNCTIONS = {
    
    # Estadísticas
    'AVEDEV', 'AVERAGE', 'AVERAGEA', 'AVERAGEIF', 'AVERAGEIFS',
    'BETA.DIST', 'BETA.INV', 'BINOM.DIST', 'BINOM.DIST.RANGE',
    'BINOM.INV', 'CHISQ.DIST', 'CHISQ.DIST.RT', 'CHISQ.INV',
    'CHISQ.INV.RT', 'CHISQ.TEST', 'CONFIDENCE', 'CONFIDENCE.NORM',
    'CONFIDENCE.T', 'CORREL', 'COUNT', 'COUNTA', 'COUNTBLANK',
    'COUNTIF', 'COUNTIFS', 'COVARIANCE', 'COVARIANCE.P', 'COVARIANCE.S',
    'DEVSQ', 'EXPON.DIST', 'F.DIST', 'F.DIST.RT', 'F.INV', 'F.INV.RT',
    'F.TEST', 'FISHER', 'FISHERINV', 'FORECAST', 'FORECAST.ETS',
    'FORECAST.ETS.CONFINT', 'FORECAST.ETS.SEASONALITY',
    'FORECAST.ETS.STAT', 'FORECAST.LINEAR', 'FREQUENCY', 'GAMMA',
    'GAMMA.DIST', 'GAMMA.INV', 'GAMMALN', 'GAMMALN.PRECISE', 'GAUSS',
    'GEOMEAN', 'GROWTH', 'HARMEAN', 'HYPGEOM.DIST', 'INTERCEPT',
    'KURT', 'LARGE', 'LINEST', 'LOGEST', 'LOGNORM.DIST', 'LOGNORM.INV',
    'MAX', 'MAXA', 'MAXIFS', 'MEDIAN', 'MIN', 'MINA', 'MINIFS', 'MODE',
    'MODE.MULT', 'MODE.SNGL', 'NEGBINOM.DIST', 'NORM.DIST', 'NORM.INV',
    'NORM.S.DIST', 'NORM.S.INV', 'PEARSON', 'PERCENTILE', 'PERCENTILE.EXC',
    'PERCENTILE.INC', 'PERCENTRANK', 'PERCENTRANK.EXC', 'PERCENTRANK.INC',
    'PERMUT', 'PERMUTATIONA', 'PHI', 'POISSON.DIST', 'PROB', 'QUARTILE',
    'QUARTILE.EXC', 'QUARTILE.INC', 'RANK', 'RANK.AVG', 'RANK.EQ',
    'RSQ', 'SKEW', 'SKEW.P', 'SLOPE', 'SMALL', 'STANDARDIZE', 'STDEV',
    'STDEV.P', 'STDEV.S', 'STDEVA', 'STDEVPA', 'STEYX', 'T.DIST',
    'T.DIST.2T', 'T.DIST.RT', 'T.INV', 'T.INV.2T', 'T.TEST', 'TREND',
    'TRIMMEAN', 'VAR', 'VAR.P', 'VAR.S', 'VARA', 'VARPA', 'WEIBULL.DIST',
    'Z.TEST',
    
    # Fecha y hora
    'DATE', 'DATEVALUE', 'DAY', 'DAYS', 'DAYS360', 'EDATE', 'EOMONTH',
    'HOUR', 'ISOWEEKNUM', 'MINUTE', 'MONTH', 'NETWORKDAYS',
    'NETWORKDAYS.INTL', 'NOW', 'SECOND', 'TIME', 'TIMEVALUE', 'TODAY',
    'WEEKDAY', 'WEEKNUM', 'WORKDAY', 'WORKDAY.INTL', 'YEAR', 'YEARFRAC',
    
    # Finanzas
    'ACCRINT', 'ACCRINTM', 'AMORDEGRC', 'AMORLINC', 'COUPDAYBS',
    'COUPDAYS', 'COUPDAYSNC', 'COUPNCD', 'COUPNUM', 'COUPPCD',
    'CUMIPMT', 'CUMPRINC', 'DB', 'DDB', 'DISC', 'DOLLARDE', 'DOLLARFR',
    'DURATION', 'EFFECT', 'FV', 'FVSCHEDULE', 'INTRATE', 'IPMT',
    'IRR', 'ISPMT', 'MDURATION', 'MIRR', 'NOMINAL', 'NPER', 'NPV',
    'ODDFPRICE', 'ODDFYIELD', 'ODDLPRICE', 'ODDLYIELD', 'PDURATION',
    'PMT', 'PPMT', 'PRICE', 'PRICEDISC', 'PRICEMAT', 'PV', 'RATE',
    'RECEIVED', 'RRI', 'SLN', 'STOCKHISTORY', 'SYD', 'TBILLEQ',
    'TBILLPRICE', 'TBILLYIELD', 'VDB', 'XIRR', 'XNPV', 'YIELD',
    'YIELDDISC', 'YIELDMAT',

}

def validate_excel_safety(file_path: str) -> Dict[str, Any]:
    """
    Valida que un archivo Excel no contenga código malicioso.
    
    Args:
        file_path: Ruta al archivo Excel
    
    Returns:
        Dict con resultado de la validación
    """
    result = {
        "safe": True,
        "warnings": [],
        "errors": [],
        "details": {
            "sheets": 0,
            "cells_analyzed": 0,
            "formulas_found": 0,
            "malicious_patterns_found": [],
            "unusual_cells": [],
        }
    }
    
    try:
        workbook = load_workbook(file_path, data_only=False, keep_vba=True)
        result["details"]["sheets"] = len(workbook.sheetnames)
        
        # # Verificar si hay macros o VBA
        # if workbook.vbaProject:
        #     result["warnings"].append("El archivo contiene macros VBA. Se requiere revisión manual.")
        #     result["details"]["has_vba"] = True
        
        # Analizar cada hoja
        for sheet_name in workbook.sheetnames:
            worksheet = workbook[sheet_name]
            
            for row in worksheet.iter_rows():
                for cell in row:
                    result["details"]["cells_analyzed"] += 1
                    
                    # Analizar fórmulas
                    if cell.value and isinstance(cell.value, str) and cell.value.startswith('='):
                        result["details"]["formulas_found"] += 1
                        formula = cell.value[1:]  # Quitar el '='
                        
                        # Verificar patrones maliciosos
                        for pattern in MALICIOUS_PATTERNS:
                            if re.search(pattern, formula):
                                # Verificar que no sea una función estándar de Excel
                                is_standard = False
                                for func in STANDARD_EXCEL_FUNCTIONS:
                                    if func in formula.upper():
                                        is_standard = True
                                        break
                                
                                if not is_standard:
                                    result["safe"] = False
                                    malicious_info = {
                                        "sheet": sheet_name,
                                        "cell": cell.coordinate,
                                        "pattern_matched": pattern,
                                        "formula": formula[:200],  # Truncar fórmulas largas
                                    }
                                    result["details"]["malicious_patterns_found"].append(malicious_info)
                                    result["errors"].append(
                                        f"Celda {cell.coordinate} en hoja '{sheet_name}': "
                                        f"posible código malicioso detectado"
                                    )
                    
                    # Verificar nombres de rango ocultos o sospechosos
                    if cell.value and isinstance(cell.value, str):
                        suspicious_names = [
                            'auto_open', 'auto_close', 'auto_activate',
                            'shell', 'exec', 'run', 'cmd', 'powershell',
                            'wscript', 'createobject', 'filesystemobject',
                        ]
                        cell_lower = cell.value.lower()
                        for suspicious in suspicious_names:
                            if suspicious in cell_lower:
                                result["details"]["unusual_cells"].append({
                                    "sheet": sheet_name,
                                    "cell": cell.coordinate,
                                    "suspicious_content": suspicious,
                                })
        
        # Verificar relaciones externas (DDE, OLE)
        for sheet_name in workbook.sheetnames:
            worksheet = workbook[sheet_name]
            for row in worksheet.iter_rows():
                for cell in row:
                    if cell.value and isinstance(cell.value, str):
                        # Detectar referencias externas peligrosas
                        if re.search(r'(?i)\[.*\]|\'.*\'!', cell.value):
                            if any(ext in cell.value.lower() for ext in ['.exe', '.bat', '.cmd', '.ps1', '.vbs', '.js', '.jar']):
                                result["safe"] = False
                                result["errors"].append(
                                    f"Celda {cell.coordinate} en hoja '{sheet_name}': "
                                    f"referencia externa a archivo ejecutable detectada"
                                )
        
        workbook.close()
        
    except Exception as e:
        result["safe"] = False
        result["errors"].append(f"Error al procesar el archivo: {str(e)}")
    
    return result


def get_safe_excel_content(file_path: str) -> Dict[str, Any]:
    """
    Lee el contenido seguro de un archivo Excel (solo valores, sin fórmulas).
    
    Args:
        file_path: Ruta al archivo Excel
    
    Returns:
        Dict con el contenido del archivo
    """
    content = {
        "sheets": {},
        "metadata": {
            "filename": file_path.split('/')[-1] if '/' in file_path else file_path,
        }
    }
    
    try:
        workbook = load_workbook(file_path, data_only=True)  # data_only=True para obtener valores
        
        for sheet_name in workbook.sheetnames:
            worksheet = workbook[sheet_name]
            sheet_data = []
            
            for row in worksheet.iter_rows(values_only=True):
                cleaned_row = []
                for cell_value in row:
                    if cell_value is None:
                        cleaned_row.append("")
                    elif isinstance(cell_value, (str, int, float, bool)):
                        cleaned_row.append(str(cell_value))
                    else:
                        cleaned_row.append(str(cell_value))
                sheet_data.append(cleaned_row)
            
            content["sheets"][sheet_name] = sheet_data
            content["metadata"]["columns"] = max(len(row) for row in sheet_data) if sheet_data else 0
            content["metadata"]["rows"] = len(sheet_data)
        
        workbook.close()
        
    except Exception as e:
        content["error"] = str(e)
    
    return content
