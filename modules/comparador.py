import os
from groq import Groq
import re

GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# Intentar importar las librerías de PDF
try:
    import fitz  # PyMuPDF
    FITZ_DISPONIBLE = True
except ImportError:
    FITZ_DISPONIBLE = False
    print("⚠️ PyMuPDF no disponible")

try:
    from pypdf import PdfReader
    from io import BytesIO
    PYPDF_DISPONIBLE = True
except ImportError:
    PYPDF_DISPONIBLE = False
    print("⚠️ pypdf no disponible")

try:
    import pdfplumber
    PDFPLUMBER_DISPONIBLE = True
except ImportError:
    PDFPLUMBER_DISPONIBLE = False
    print("⚠️ pdfplumber no disponible")


def extraer_texto_pdf(contenido_bytes):
    """Extrae texto del PDF usando el primer método disponible"""
    
    texto = ""
    
    # Método 1: PyMuPDF (fitz)
    if FITZ_DISPONIBLE and not texto:
        try:
            doc = fitz.open(stream=contenido_bytes, filetype="pdf")
            for page in doc:
                texto += page.get_text() + " "
            doc.close()
            texto = re.sub(r'\s+', ' ', texto).strip()
            if len(texto) > 50:
                print(f"📄 PyMuPDF: {len(texto)} caracteres")
                return texto[:5000]
        except Exception as e:
            print(f"⚠️ PyMuPDF falló: {str(e)}")
    
    # Método 2: pypdf
    if PYPDF_DISPONIBLE and not texto:
        try:
            pdf_file = BytesIO(contenido_bytes)
            reader = PdfReader(pdf_file)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    texto += page_text + " "
            texto = re.sub(r'\s+', ' ', texto).strip()
            if len(texto) > 50:
                print(f"📄 pypdf: {len(texto)} caracteres")
                return texto[:5000]
        except Exception as e:
            print(f"⚠️ pypdf falló: {str(e)}")
    
    # Método 3: pdfplumber
    if PDFPLUMBER_DISPONIBLE and not texto:
        try:
            pdf_file = BytesIO(contenido_bytes)
            with pdfplumber.open(pdf_file) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        texto += page_text + " "
            texto = re.sub(r'\s+', ' ', texto).strip()
            if len(texto) > 50:
                print(f"📄 pdfplumber: {len(texto)} caracteres")
                return texto[:5000]
        except Exception as e:
            print(f"⚠️ pdfplumber falló: {str(e)}")
    
    if texto and len(texto) > 50:
        return texto[:5000]
    
    print("❌ No se pudo extraer texto del PDF (todos los métodos fallaron)")
    return ""


def extraer_texto_xml(contenido_bytes):
    """Extrae texto del XML"""
    try:
        texto = contenido_bytes.decode('utf-8')
    except:
        texto = contenido_bytes.decode('latin-1')
    texto = re.sub(r'\s+', ' ', texto)
    return texto[:5000]


def extraer_datos_xml(xml_str):
    """Extrae número de factura y RUC del proveedor"""
    num_factura = ""
    ruc_proveedor = ""
    
    match_num = re.search(r'<cbc:ID>([A-Z0-9-]+)</cbc:ID>', xml_str)
    if match_num:
        num_factura = match_num.group(1)
        print(f"📑 Número de factura: {num_factura}")
    
    match_ruc = re.search(r'<cbc:ID schemeID="6".*?>(\d+)</cbc:ID>', xml_str)
    if match_ruc:
        ruc_proveedor = match_ruc.group(1)
        print(f"🏢 RUC: {ruc_proveedor}")
    
    return num_factura, ruc_proveedor


def comparar_con_ia(pdf_texto, xml_texto, pdf_nombre, xml_nombre):
    """Compara PDF vs XML con IA"""
    
    if not client:
        return "Error: GROQ_API_KEY no configurada", True
    
    # Si no hay texto en el PDF
    if not pdf_texto or len(pdf_texto) < 100:
        analisis = f"⚠️ No se pudo extraer texto del PDF ({pdf_nombre}). Verificar manualmente."
        return analisis, True
    
    prompt = f"""
Eres un auditor de facturas electrónicas.

PDF ({pdf_nombre}): {pdf_texto[:2000]}
XML ({xml_nombre}): {xml_texto[:1000]}

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
    num_factura, ruc_proveedor = extraer_datos_xml(xml_texto)
    
    print(f"📝 PDF: {len(pdf_texto)} chars | XML: {len(xml_texto)} chars")
    
    analisis, tiene_discrepancias = comparar_con_ia(pdf_texto, xml_texto, pdf_nombre, xml_nombre)
    
    return {
        'analisis': analisis,
        'tiene_discrepancias': tiene_discrepancias,
        'num_factura': num_factura,
        'ruc_proveedor': ruc_proveedor
    }
