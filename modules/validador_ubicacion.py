import os
import re
import json
import base64
from groq import Groq
from modules.comparador import extraer_texto_pdf

GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# Maestro de sedes SAP Manuchar
MAPEO_SEDES = {
    "ALTRUJ": "ALMACENERA TRUJILLO",
    "ALMAFI": "ALMAFIN",
    "AREQ01": "AREQUIPA PAUCARPATA",
    "CAROLI": "CAROLINA PAITA",
    "Stelle_3": "Centro general 3",
    "COSTO1": "COSTO",
    "DIEF": "DIEF",
    "GAMBET": "GAMBETA",
    "SOLDEX": "LURIN SOLDEXA",
    "NEPTUN": "NEPTUNO",
    "OFICIN": "OFICINA",
    "PIURA1": "PIURA",
    "RCALLA": "RANSA CALLAO",
    "RPISCO": "RANSA PISCO",
    "RPIURA": "RANSA PIURA",
    "RSALAV": "RANSA SALAVERRY",
    "TALPA1": "TALPA",
    "TGSA01": "TGSA",
    "TISUR1": "TISUR",
    "TRANSP": "TRANSPORTE",
    "VENTAN": "VENTANILLA",
    "VENTAN2": "VENTANILLA 2",
    "VENTAN3": "VENTANILLA 3",
    "ZEDMAT": "ZED MATARANI",
    "ZEDPAI": "ZED PAITA"
}


def validar_ubicacion(codigo_sap, archivo_pdf_base64, direccion_sap):
    """
    Valida si la ubicación en el PDF coincide con la sede de SAP
    """
    
    if not client:
        return {"estado": "ERROR", "motivo": "GROQ_API_KEY no configurada"}
    
    try:
        # Decodificar PDF
        pdf_bytes = base64.b64decode(archivo_pdf_base64)
        
        # Extraer texto del PDF
        texto_pdf = extraer_texto_pdf(pdf_bytes)
        
        if not texto_pdf or len(texto_pdf) < 50:
            texto_pdf = "No se pudo extraer texto del PDF"
        
        nombre_sede = MAPEO_SEDES.get(codigo_sap, codigo_sap)
        
        # Prompt limpio
        prompt = f"""
Auditor logistico. Compara ubicacion en PDF vs SAP.

SAP: {nombre_sede} ({codigo_sap})
Direccion SAP: {direccion_sap if direccion_sap else 'No especificada'}

PDF: {texto_pdf[:2000]}

Responde solo JSON:
{{"estado": "OK", "motivo": "explicacion"}}
o
{{"estado": "ALERTA", "motivo": "explicacion"}}
"""
        
        print(f"🔍 Auditando ubicacion: {codigo_sap}")
        
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=150
        )
        
        resultado = json.loads(completion.choices[0].message.content)
        
        if "estado" not in resultado:
            resultado["estado"] = "ERROR"
        if "motivo" not in resultado:
            resultado["motivo"] = "Sin motivo"
        
        if resultado["estado"] not in ["OK", "ALERTA"]:
            resultado["estado"] = "ERROR"
        
        print(f"✅ Ubicacion: {resultado['estado']}")
        
        return resultado
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return {"estado": "ERROR", "motivo": str(e)}
