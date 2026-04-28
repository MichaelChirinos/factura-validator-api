import os
from groq import Groq
from modules.comparador import extraer_texto_pdf, extraer_datos_xml

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
    """Valida si la ubicación en el PDF coincide con la sede de SAP"""
    
    if not client:
        return {"estado": "ERROR", "motivo": "GROQ_API_KEY no configurada"}
    
    try:
        # 1. Decodificar PDF
        import base64
        pdf_bytes = base64.b64decode(archivo_pdf_base64)
        
        # 2. Extraer texto del PDF (reutilizando función existente)
        texto_pdf = extraer_texto_pdf(pdf_bytes)
        
        if not texto_pdf or len(texto_pdf) < 50:
            texto_pdf = "ERROR: No se pudo extraer texto del PDF (posiblemente es una imagen escaneada)"
        
        # 3. Obtener nombre de la sede
        nombre_largo = MAPEO_SEDES.get(codigo_sap, codigo_sap)
        
        # 4. Prompt optimizado
        prompt = f"""
Actúa como un auditor logístico experto para Manuchar Perú.

DATOS SAP:
- Sede: {nombre_largo} ({codigo_sap})
- Dirección SAP: {direccion_sap if direccion_sap else 'No especificada'}

CONTENIDO DEL PDF:
{texto_pdf[:3000]}

INSTRUCCIONES:
1. Busca en el PDF la dirección, punto de entrega o ubicación del servicio
2. Responde OK si coincide con la sede SAP o su distrito
3. Responde ALERTA si hay contradicción geográfica (ej: SAP dice GAMBETA/CALLAO pero PDF dice LURIN/SURCO)
4. Si el PDF no tiene ubicación clara, responde OK

RESPONDE SOLO JSON:
{{"estado": "OK" o "ALERTA", "motivo": "explicación breve"}}
"""
        
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=300
        )
        
        import json
        resultado = json.loads(completion.choices[0].message.content)
        return resultado
        
    except Exception as e:
        return {"estado": "ERROR", "motivo": str(e)}
