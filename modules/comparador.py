import os
import base64
import fitz  # PyMuPDF
from groq import Groq
import re
import xml.etree.ElementTree as ET

# Configurar cliente Groq
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None


def extraer_texto_pdf(contenido_bytes):
    """Extrae texto de un PDF desde bytes en memoria (sin archivos temporales)"""
    try:
        # Abrir PDF directamente desde los bytes en memoria
        doc = fitz.open(stream=contenido_bytes, filetype="pdf")
        texto = ""
        for page in doc:
            texto += page.get_text()
        doc.close()
        
        # Limpiar espacios
        texto = re.sub(r'\s+', ' ', texto)
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


def extraer_datos_xml(xml_bytes):
    """Extrae datos estructurados del XML"""
    try:
        xml_content = xml_bytes.decode('utf-8', errors='ignore')
        root = ET.fromstring(xml_content)
        
        ns = {
            'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
            'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2'
        }
        
        datos = {}
        
        # Número de factura
        factura_elem = root.find('cbc:ID', ns)
        datos['numero_factura'] = factura_elem.text.strip() if factura_elem is not None else "No encontrado"
        
        # RUC del emisor
        ruc_elem = root.find('.//cac:AccountingSupplierParty/cac:Party/cac:PartyIdentification/cbc:ID', ns)
        datos['ruc_emisor'] = ruc_elem.text.strip() if ruc_elem is not None else "No encontrado"
        
        # Fecha de emisión
        fecha_elem = root.find('cbc:IssueDate', ns)
        datos['fecha_emision'] = fecha_elem.text.strip() if fecha_elem is not None else "No encontrado"
        
        # Monto total
        monto_elem = root.find('cbc:PayableAmount', ns)
        if monto_elem is not None:
            datos['monto_total'] = monto_elem.text.strip()
            datos['moneda'] = monto_elem.get('currencyID', 'No encontrado')
        else:
            datos['monto_total'] = "No encontrado"
            datos['moneda'] = "No encontrado"
        
        # RUC del cliente
        cliente_ruc_elem = root.find('.//cac:AccountingCustomerParty/cac:Party/cac:PartyIdentification/cbc:ID', ns)
        datos['ruc_cliente'] = cliente_ruc_elem.text.strip() if cliente_ruc_elem is not None else "No encontrado"
        
        # Nombre del cliente
        cliente_nombre_elem = root.find('.//cac:AccountingCustomerParty/cac:Party/cac:PartyLegalEntity/cbc:RegistrationName', ns)
        datos['nombre_cliente'] = cliente_nombre_elem.text.strip() if cliente_nombre_elem is not None else "No encontrado"
        
        return datos
    except Exception as e:
        print(f"❌ Error extrayendo datos del XML: {str(e)}")
        return {
            'numero_factura': 'Error',
            'ruc_emisor': 'Error',
            'fecha_emision': 'Error',
            'monto_total': 'Error',
            'moneda': 'Error',
            'ruc_cliente': 'Error',
            'nombre_cliente': 'Error'
        }


def comparar_con_ia(pdf_texto, xml_texto, datos_xml, pdf_nombre, xml_nombre):
    """Envía a Groq la comparación y devuelve análisis y discrepancias"""
    
    if not client:
        return "Error: GROQ_API_KEY no configurada", True
    
    prompt = f"""
    Eres un auditor de facturas electrónicas peruanas.

    === DATOS DEL XML (VALORES CORRECTOS) ===
    - Número de Factura: {datos_xml['numero_factura']}
    - RUC Emisor: {datos_xml['ruc_emisor']}
    - RUC Cliente: {datos_xml['ruc_cliente']}
    - Nombre Cliente: {datos_xml['nombre_cliente']}
    - Fecha Emisión: {datos_xml['fecha_emision']}
    - Moneda: {datos_xml['moneda']}
    - Monto Total: {datos_xml['monto_total']} {datos_xml['moneda']}

    === CONTENIDO EXTRAÍDO DEL PDF ===
    {pdf_texto[:10000]}

    === TAREA ===
    Compara los datos del PDF visual contra los datos del XML.
    Verifica: RUC emisor, Número de Factura, Fecha y Monto Total.

    Responde EXACTAMENTE con este formato:

    ===ANALISIS===
    [Tu análisis detallado de qué campos coinciden y cuáles no]

    ===DISCREPANCIAS===
    [Escribe SOLO "true" si hay alguna discrepancia, o "false" si todo coincide]
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
    
    # Parsear respuesta
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
    
    # 1. Extraer texto del PDF (sin archivos temporales)
    pdf_texto = extraer_texto_pdf(pdf_bytes)
    
    # 2. Extraer texto del XML
    xml_texto = extraer_texto_xml(xml_bytes)
    
    # 3. Extraer datos estructurados del XML
    datos_xml = extraer_datos_xml(xml_bytes)
    
    # 4. Comparar con IA
    analisis, tiene_discrepancias = comparar_con_ia(pdf_texto, xml_texto, datos_xml, pdf_nombre, xml_nombre)
    
    # 5. Devolver resultado
    return {
        'analisis': analisis,
        'tiene_discrepancias': tiene_discrepancias,
        'datos_xml': datos_xml
    }
