import os
import tempfile
import fitz  # PyMuPDF
from groq import Groq
import re

GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None


def extraer_texto_pdf(contenido_bytes):
    """Extrae texto de un PDF usando archivo temporal (método que funciona en Render)"""
    temp_path = None
    try:
        # Crear archivo temporal
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
            tmp.write(contenido_bytes)
            temp_path = tmp.name
        
        # Abrir PDF desde el archivo temporal
        doc = fitz.open(temp_path)
        texto = ""
        for page in doc:
            texto += page.get_text()
        doc.close()
        
        texto = re.sub(r'\s+', ' ', texto).strip()
        print(f"📄 PDF extraído: {len(texto)} caracteres")
        return texto[:5000]
        
    except Exception as e:
        print(f"❌ Error extrayendo texto del PDF: {str(e)}")
        return ""
    finally:
        # Limpiar archivo temporal
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except:
                pass


def extraer_texto_xml(contenido_bytes):
    """Extrae texto de un archivo XML"""
    try:
        texto = contenido_bytes.decode('utf-8')
    except:
        texto = contenido_bytes.decode('latin-1')
    texto = re.sub(r'\s+', ' ', texto)
    return texto[:5000]


def extraer_datos_xml(xml_bytes):
    """Extrae número de factura y RUC del proveedor"""
    num_factura = ""
    ruc_proveedor = ""
    
    try:
        xml_str = xml_bytes.decode('utf-8', errors='ignore')
        
        # Buscar número de factura
        match_num = re.search(r'<cbc:ID>([A-Z0-9-]+)</cbc:ID>', xml_str)
        if match_num:
            num_factura = match_num.group(1)
            print(f"📑 Número de factura: {num_factura}")
        
        # Buscar RUC (2 patrones diferentes)
        match_ruc = re.search(r'<cbc:ID schemeID="6".*?>(\d+)</cbc:ID>', xml_str)
        if not match_ruc:
            match_ruc = re.search(r'<cbc:ID>(\d{11})</cbc:ID>', xml_str)
        if match_ruc:
            ruc_proveedor = match_ruc.group(1)
            print(f"🏢 RUC: {ruc_proveedor}")
            
    except Exception as e:
        print(f"❌ Error extrayendo datos XML: {str(e)}")
    
    return num_factura, ruc_proveedor


def comparar_con_ia(pdf_texto, xml_texto, pdf_nombre, xml_nombre):
    """Compara PDF vs XML con IA"""
    
    if not client:
        return "Error: GROQ_API_KEY no configurada", True
    
    if not pdf_texto or len(pdf_texto) < 100:
        analisis = f"⚠️ No se pudo extraer texto del PDF ({pdf_nombre}). Verificar manualmente."
        return analisis, True
    
    prompt = f"""
Eres un auditor de facturas electrónicas.

PDF ({pdf_nombre}): {pdf_texto[:2000]}
XML ({xml_nombre}): {xml_texto[:1500]}

Responde EXACTAMENTE:

===ANALISIS===
[Qué campos coinciden y cuáles no]

===DISCREPANCIAS===
[true o false]
"""

    try:
        completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "Auditor de facturas. Sé preciso."},
                {"role": "user", "content": prompt}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.1,
            max_tokens=500
        )

        respuesta = completion.choices[0].message.content
        
        analisis = ""
        tiene_discrepancias = True
        
        if "===ANALISIS===" in respuesta:
            partes = respuesta.split("===DISCREPANCIAS===")
            analisis = partes[0].replace("===ANALISIS===", "").strip()
            if len(partes) > 1:
                tiene_discrepancias = "true" in partes[1].lower()
        
        return analisis, tiene_discrepancias
        
    except Exception as e:
        print(f"❌ Error en IA: {str(e)}")
        return f"Error en IA: {str(e)}", True


def comparar_pdf_xml(pdf_bytes, xml_bytes, pdf_nombre, xml_nombre):
    """Función principal"""
    
    print(f"\n📄 Procesando: {pdf_nombre}")
    
    pdf_texto = extraer_texto_pdf(pdf_bytes)
    xml_texto = extraer_texto_xml(xml_bytes)
    num_factura, ruc_proveedor = extraer_datos_xml(xml_bytes)
    
    print(f"📝 PDF: {len(pdf_texto)} chars | XML: {len(xml_texto)} chars")
    
    analisis, tiene_discrepancias = comparar_con_ia(pdf_texto, xml_texto, pdf_nombre, xml_nombre)
    
    return {
        'analisis': analisis,
        'tiene_discrepancias': tiene_discrepancias,
        'num_factura': num_factura,
        'ruc_proveedor': ruc_proveedor
    }
