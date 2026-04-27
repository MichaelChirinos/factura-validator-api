import os
import fitz  # PyMuPDF
from groq import Groq
import re

GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None


def extraer_texto_pdf(contenido_bytes):
    """Extrae texto del PDF (limitado a 3000 caracteres)"""
    try:
        doc = fitz.open(stream=contenido_bytes, filetype="pdf")
        texto = ""
        for page in doc:
            texto += page.get_text()
        doc.close()
        texto = re.sub(r'\s+', ' ', texto)
        # Limitar a 3000 caracteres para reducir tokens
        return texto[:3000]
    except Exception as e:
        print(f"❌ Error PDF: {str(e)}")
        return ""


def extraer_texto_xml(contenido_bytes):
    """Extrae texto del XML (limitado a 3000 caracteres)"""
    try:
        texto = contenido_bytes.decode('utf-8')
    except:
        texto = contenido_bytes.decode('latin-1')
    texto = re.sub(r'\s+', ' ', texto)
    return texto[:3000]


def extraer_datos_xml(xml_str):
    """Extrae número de factura y RUC del proveedor"""
    num_factura = ""
    ruc_proveedor = ""
    
    match_num = re.search(r'<cbc:ID>([A-Z0-9-]+)</cbc:ID>', xml_str)
    if match_num:
        num_factura = match_num.group(1)
    
    match_ruc = re.search(r'<cbc:ID schemeID="6".*?>(\d+)</cbc:ID>', xml_str)
    if match_ruc:
        ruc_proveedor = match_ruc.group(1)
    
    return num_factura, ruc_proveedor


def comparar_con_ia(pdf_texto, xml_texto, pdf_nombre, xml_nombre):
    """Compara PDF vs XML con IA (prompt optimizado)"""
    
    if not client:
        return "Error: GROQ_API_KEY no configurada", True
    
    prompt = f"""
Compara el PDF y XML de esta factura.

PDF ({pdf_nombre}): {pdf_texto[:1500]}
XML ({xml_nombre}): {xml_texto[:1500]}

Responde EXACTAMENTE con este formato:
===ANALISIS===
[Lista qué campos coinciden y cuáles no]
===DISCREPANCIAS===
[true o false]
"""

    completion = client.chat.completions.create(
        messages=[
            {"role": "system", "content": "Eres un auditor de facturas. Sé preciso."},
            {"role": "user", "content": prompt}
        ],
        model="llama-3.3-70b-versatile",
        temperature=0.1,
        max_tokens=500  # Reducido de 2000 a 500
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


def comparar_pdf_xml(pdf_bytes, xml_bytes, pdf_nombre, xml_nombre):
    """Función principal"""
    
    print(f"📄 Procesando: {pdf_nombre}")
    
    pdf_texto = extraer_texto_pdf(pdf_bytes)
    xml_texto = extraer_texto_xml(xml_bytes)
    num_factura, ruc_proveedor = extraer_datos_xml(xml_texto)
    analisis, tiene_discrepancias = comparar_con_ia(pdf_texto, xml_texto, pdf_nombre, xml_nombre)
    
    return {
        'analisis': analisis,
        'tiene_discrepancias': tiene_discrepancias,
        'num_factura': num_factura,
        'ruc_proveedor': ruc_proveedor
    }
