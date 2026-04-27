import os
import fitz  # PyMuPDF
from groq import Groq
import re
from io import BytesIO

GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# Intentar importar OCR (opcional, si falla sigue funcionando)
try:
    from pdf2image import convert_from_bytes
    import pytesseract
    from PIL import Image
    OCR_DISPONIBLE = True
    print("✅ OCR disponible (pytesseract + pdf2image)")
except ImportError:
    OCR_DISPONIBLE = False
    print("⚠️ OCR no disponible, solo se extraerá texto nativo")


def extraer_texto_pdf(contenido_bytes):
    """Extrae texto del PDF, con OCR si es necesario"""
    try:
        # Primero intentar extraer texto nativo con PyMuPDF
        doc = fitz.open(stream=contenido_bytes, filetype="pdf")
        texto_nativo = ""
        for page in doc:
            texto_nativo += page.get_text()
        doc.close()
        
        texto_nativo = re.sub(r'\s+', ' ', texto_nativo).strip()
        
        # Si hay texto nativo (más de 50 caracteres), usarlo
        if len(texto_nativo) > 50:
            print(f"📄 PDF con texto nativo: {len(texto_nativo)} caracteres")
            return texto_nativo[:3000]
        
        # Si no hay texto nativo y OCR está disponible, intentar OCR
        if OCR_DISPONIBLE and len(texto_nativo) < 50:
            print("⚠️ PDF sin texto nativo, intentando OCR...")
            try:
                images = convert_from_bytes(contenido_bytes, dpi=200)
                texto_ocr = ""
                for i, image in enumerate(images):
                    # Preprocesar imagen
                    image = image.convert('L')  # Escala de grises
                    text = pytesseract.image_to_string(image, lang='spa+eng')
                    texto_ocr += text + " "
                    print(f"   Página {i+1}: {len(text)} caracteres OCR")
                
                texto_ocr = re.sub(r'\s+', ' ', texto_ocr).strip()
                if len(texto_ocr) > 50:
                    print(f"📄 OCR exitoso: {len(texto_ocr)} caracteres")
                    return texto_ocr[:3000]
                else:
                    print("⚠️ OCR no encontró texto significativo")
            except Exception as e:
                print(f"❌ Error en OCR: {str(e)}")
        
        # Si llegamos aquí, no hay texto
        print("⚠️ No se pudo extraer texto del PDF (puede ser imagen sin OCR)")
        return ""
        
    except Exception as e:
        print(f"❌ Error extrayendo texto del PDF: {str(e)}")
        return ""


def extraer_texto_xml(contenido_bytes):
    """Extrae texto del XML"""
    try:
        texto = contenido_bytes.decode('utf-8')
    except:
        texto = contenido_bytes.decode('latin-1')
    texto = re.sub(r'\s+', ' ', texto)
    return texto[:3000]


def extraer_datos_xml(xml_bytes):
    """Extrae número de factura y RUC del proveedor desde los bytes originales del XML"""
    num_factura = ""
    ruc_proveedor = ""
    
    try:
        xml_str = xml_bytes.decode('utf-8', errors='ignore')
        
        # Buscar número de factura: <cbc:ID>F009-1828</cbc:ID>
        match_num = re.search(r'<cbc:ID>([A-Z0-9-]+)</cbc:ID>', xml_str)
        if match_num:
            num_factura = match_num.group(1)
            print(f"📑 Número de factura: {num_factura}")
        
        # Buscar RUC: <cbc:ID schemeID="6">20100039207</cbc:ID>
        match_ruc = re.search(r'<cbc:ID schemeID="6".*?>(\d+)</cbc:ID>', xml_str)
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
    
    # Si no hay texto en el PDF
    if not pdf_texto or len(pdf_texto) < 50:
        analisis = f"""
⚠️ **No se pudo extraer texto del PDF** ({pdf_nombre})

El archivo PDF podría ser una imagen escaneada o tener el texto no seleccionable.

**Datos extraídos del XML:**
- Factura: {xml_nombre}

**Recomendación:** Verifica manualmente que el PDF coincida con el XML.
"""
        return analisis, True
    
    prompt = f"""
Compara el PDF y XML de esta factura.

PDF ({pdf_nombre}): {pdf_texto[:1500]}
XML ({xml_nombre}): {xml_texto[:1500]}

Responde EXACTAMENTE:
===ANALISIS===
[Lista qué campos coinciden y cuáles no]
===DISCREPANCIAS===
[true o false]
"""

    try:
        completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "Eres un auditor de facturas. Sé preciso."},
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
    
    # Extraer texto del PDF (con OCR si es necesario)
    pdf_texto = extraer_texto_pdf(pdf_bytes)
    print(f"📝 PDF texto: {len(pdf_texto)} caracteres")
    
    # Extraer texto del XML
    xml_texto = extraer_texto_xml(xml_bytes)
    print(f"📝 XML texto: {len(xml_texto)} caracteres")
    
    # Extraer datos del XML
    num_factura, ruc_proveedor = extraer_datos_xml(xml_bytes)
    
    # Comparar con IA
    analisis, tiene_discrepancias = comparar_con_ia(pdf_texto, xml_texto, pdf_nombre, xml_nombre)
    
    return {
        'analisis': analisis,
        'tiene_discrepancias': tiene_discrepancias,
        'num_factura': num_factura,
        'ruc_proveedor': ruc_proveedor
    }
