import os
import fitz  # PyMuPDF
from groq import Groq
import re

# Configurar cliente Groq
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None


def extraer_texto_pdf(contenido_bytes):
    """Extrae texto de un PDF directamente desde memoria (sin archivos temporales)"""
    try:
        doc = fitz.open(stream=contenido_bytes, filetype="pdf")
        texto = ""
        for page in doc:
            texto += page.get_text()
        doc.close()
        texto = re.sub(r'\s+', ' ', texto)
        print(f"📄 PDF extraído: {len(texto)} caracteres")
        return texto[:20000]
    except Exception as e:
        print(f"❌ Error extrayendo texto del PDF: {str(e)}")
        return ""


def extraer_texto_xml(contenido_bytes):
    """Extrae texto de un archivo XML"""
    try:
        texto = contenido_bytes.decode('utf-8')
    except:
        texto = contenido_bytes.decode('latin-1')
    texto = re.sub(r'\s+', ' ', texto)
    return texto[:20000]


def extraer_datos_xml(xml_str):
    """Extrae número de factura y RUC del proveedor desde el XML"""
    num_factura = ""
    ruc_proveedor = ""
    
    # Buscar número de factura: <cbc:ID>FF01-17763</cbc:ID>
    match_num = re.search(r'<cbc:ID>([A-Z0-9-]+)</cbc:ID>', xml_str)
    if match_num:
        num_factura = match_num.group(1)
        print(f"📑 Número de factura extraído: {num_factura}")
    
    # Buscar RUC del proveedor: <cbc:ID schemeID="6">20100015014</cbc:ID>
    match_ruc = re.search(r'<cbc:ID schemeID="6".*?>(\d+)</cbc:ID>', xml_str)
    if match_ruc:
        ruc_proveedor = match_ruc.group(1)
        print(f"🏢 RUC del proveedor extraído: {ruc_proveedor}")
    
    return num_factura, ruc_proveedor


def comparar_con_ia(pdf_texto, xml_texto, pdf_nombre, xml_nombre):
    """Envía a Groq la comparación y devuelve análisis y discrepancias"""
    
    if not client:
        return "Error: GROQ_API_KEY no configurada", True
    
    prompt = f"""
    Eres un auditor de facturas electrónicas.

    Compara el PDF y XML de esta factura.

    **PDF:** {pdf_nombre}
    {pdf_texto}

    **XML:** {xml_nombre}
    {xml_texto}

    **Responde EXACTAMENTE con este formato:**

    ===ANALISIS===
    [Escribe aquí qué campos coinciden y cuáles no. Sé específico]

    ===DISCREPANCIAS===
    [Escribe SOLO "true" si hay discrepancias, o "false" si todo coincide]
    """

    completion = client.chat.completions.create(
        messages=[
            {"role": "system", "content": "Eres un auditor de facturas. Sé preciso y profesional."},
            {"role": "user", "content": prompt}
        ],
        model="llama-3.3-70b-versatile",
        temperature=0.1,
        max_tokens=2000
    )

    respuesta = completion.choices[0].message.content
    
    analisis = ""
    tiene_discrepancias = True
    
    if "===ANALISIS===" in respuesta:
        partes = respuesta.split("===DISCREPANCIAS===")
        analisis = partes[0].replace("===ANALISIS===", "").strip()
        if len(partes) > 1:
            texto_discrepancia = partes[1].strip().lower()
            tiene_discrepancias = "true" in texto_discrepancia
    
    return analisis, tiene_discrepancias


def comparar_pdf_xml(pdf_bytes, xml_bytes, pdf_nombre, xml_nombre):
    """Función principal que compara PDF y XML"""
    
    print(f"📄 Procesando: {pdf_nombre} y {xml_nombre}")
    
    # Extraer texto del PDF
    pdf_texto = extraer_texto_pdf(pdf_bytes)
    
    # Extraer texto del XML
    xml_texto = extraer_texto_xml(xml_bytes)
    
    # Extraer datos del XML (número de factura y RUC)
    num_factura, ruc_proveedor = extraer_datos_xml(xml_texto)
    
    print(f"📝 PDF texto: {len(pdf_texto)} caracteres")
    print(f"📝 XML texto: {len(xml_texto)} caracteres")
    
    # Comparar con IA
    analisis, tiene_discrepancias = comparar_con_ia(pdf_texto, xml_texto, pdf_nombre, xml_nombre)
    
    # Devolver resultado incluyendo los datos extraídos del XML
    return {
        'analisis': analisis,
        'tiene_discrepancias': tiene_discrepancias,
        'num_factura': num_factura,
        'ruc_proveedor': ruc_proveedor
    }
