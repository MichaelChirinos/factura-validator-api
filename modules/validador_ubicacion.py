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
    
    Args:
        codigo_sap (str): Código de la sede SAP (ej: GAMBET)
        archivo_pdf_base64 (str): PDF en Base64
        direccion_sap (str): Dirección registrada en SAP
    
    Returns:
        dict: {"estado": "OK" o "ALERTA", "motivo": "explicación"}
    """
    
    if not client:
        return {"estado": "ERROR", "motivo": "GROQ_API_KEY no configurada"}
    
    try:
        # 1. Decodificar PDF
        pdf_bytes = base64.b64decode(archivo_pdf_base64)
        
        # 2. Extraer texto del PDF (reutilizando función de comparador.py)
        texto_pdf = extraer_texto_pdf(pdf_bytes)
        
        if not texto_pdf or len(texto_pdf) < 50:
            texto_pdf = "No se pudo extraer texto del PDF (posiblemente es una imagen escaneada)"
        
        # 3. Obtener nombre de la sede desde el mapeo
        nombre_sede = MAPEO_SEDES.get(codigo_sap, codigo_sap)
        
        # 4. Prompt optimizado para auditoría geográfica
        prompt = f"""
Actúa como un auditor logístico experto para Manuchar Perú.

DATOS DE SAP:
- Código de sede: {codigo_sap}
- Nombre de sede: {nombre_sede}
- Dirección registrada en SAP: {direccion_sap if direccion_sap else 'No especificada'}

CONTENIDO EXTRAÍDO DEL PDF:
{texto_pdf[:3000]}

INSTRUCCIONES DE AUDITORÍA:
1. Busca en el PDF la dirección, punto de entrega, destino o ubicación del servicio.
2. Analiza si la ubicación en el PDF coincide con la sede de SAP.
3. Responde OK si:
   - La ubicación coincide exactamente
   - Está en el mismo distrito
   - Es un sinónimo lógico (ej: "Gambeta" = "Av. Néstor Gambetta")
   - El PDF no menciona ubicación clara
4. Responde ALERTA si:
   - El PDF menciona una ciudad o distrito INCOMPATIBLE con la sede SAP
   - Ejemplo: SAP dice GAMBETA (Callao) pero PDF dice LURÍN (Surco)
   - Ejemplo: SAP dice PAITA (Piura) pero PDF dice AREQUIPA

CONOCIMIENTO GEOGRÁFICO:
- GAMBETA, VENTANILLA, RCALLA → Callao
- PAITA, CAROLI, ZEDPAI → Piura
- AREQ01 → Arequipa
- SOLDEX, LURIN → Lima Sur
- TRUJILLO → La Libertad

RESPONDE ÚNICAMENTE EN JSON (sin texto adicional):
{
  "estado": "OK" o "ALERTA",
  "motivo": "Explicación breve de la decisión (máximo 100 caracteres)"
}
"""

        print(f"🔍 Auditando ubicación: {codigo_sap}")
        
        # 5. Llamar a Groq
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=300
        )
        
        # 6. Parsear respuesta
        resultado = json.loads(completion.choices[0].message.content)
        
        # 7. Validar que el resultado tenga los campos esperados
        if "estado" not in resultado:
            resultado["estado"] = "ERROR"
        if "motivo" not in resultado:
            resultado["motivo"] = "Respuesta de IA inválida"
        
        print(f"✅ Ubicación: {resultado['estado']} - {resultado['motivo'][:50]}")
        
        return resultado
        
    except Exception as e:
        print(f"❌ Error en validar_ubicacion: {str(e)}")
        return {"estado": "ERROR", "motivo": f"Error interno: {str(e)}"}
