from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import base64
from datetime import datetime
import pdfplumber
from io import BytesIO
from groq import Groq
import re

app = Flask(__name__)
CORS(app)

# ============================================
# CONFIGURACIÓN
# ============================================
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
if not GROQ_API_KEY:
    print("⚠️ ADVERTENCIA: GROQ_API_KEY no está configurada")
    client = None
else:
    client = Groq(api_key=GROQ_API_KEY)
    print("✅ Groq configurado correctamente")

# ============================================
# FUNCIÓN: EXTRAER TEXTO DEL PDF
# ============================================

def extraer_texto_pdf(contenido_bytes):
    """Extrae texto de un archivo PDF usando pdfplumber"""
    try:
        pdf_file = BytesIO(contenido_bytes)
        texto_completo = ""
        
        with pdfplumber.open(pdf_file) as pdf:
            for page_num, page in enumerate(pdf.pages):
                page_text = page.extract_text()
                if page_text:
                    texto_completo += f"\n===== Página {page_num + 1} =====\n{page_text}\n"
                else:
                    # Si no hay texto, intentar extraer tablas
                    tables = page.extract_tables()
                    if tables:
                        for table in tables:
                            for row in table:
                                texto_completo += " | ".join([str(cell) for cell in row if cell]) + "\n"
        
        # Limpiar espacios múltiples
        texto_completo = re.sub(r'\s+', ' ', texto_completo)
        texto_completo = texto_completo.strip()
        
        print(f"📄 Texto PDF extraído: {len(texto_completo)} caracteres")
        return texto_completo[:20000]
        
    except Exception as e:
        print(f"❌ Error extrayendo texto del PDF: {str(e)}")
        return ""

# ============================================
# FUNCIÓN: EXTRAER TEXTO DEL XML
# ============================================

def extraer_texto_xml(contenido_bytes):
    """Extrae texto de un archivo XML"""
    try:
        texto = contenido_bytes.decode('utf-8')
    except UnicodeDecodeError:
        try:
            texto = contenido_bytes.decode('latin-1')
        except:
            texto = str(contenido_bytes)
    
    texto = re.sub(r'\s+', ' ', texto)
    print(f"📄 Texto XML extraído: {len(texto)} caracteres")
    return texto[:20000]

# ============================================
# FUNCIÓN: EXTRAER DATOS DEL XML
# ============================================

def extraer_datos_xml(xml_texto):
    """Extrae los datos más importantes del XML"""
    datos = {}
    
    # RUC del emisor (proveedor)
    ruc_match = re.search(r'<cbc:ID schemeID="6".*?>(\d+)</cbc:ID>', xml_texto)
    datos['ruc_emisor'] = ruc_match.group(1) if ruc_match else "No encontrado"
    
    # RUC del cliente (comprador)
    customer_section = xml_texto[xml_texto.find("AccountingCustomerParty"):] if "AccountingCustomerParty" in xml_texto else ""
    ruc_cliente_match = re.search(r'<cbc:ID schemeID="6".*?>(\d+)</cbc:ID>', customer_section)
    datos['ruc_cliente'] = ruc_cliente_match.group(1) if ruc_cliente_match else "No encontrado"
    
    # Número de factura
    numero_match = re.search(r'<cbc:ID>([A-Z0-9-]+)</cbc:ID>', xml_texto)
    datos['numero_factura'] = numero_match.group(1) if numero_match else "No encontrado"
    
    # Fecha de emisión
    fecha_match = re.search(r'<cbc:IssueDate>(\d{4}-\d{2}-\d{2})</cbc:IssueDate>', xml_texto)
    datos['fecha_emision'] = fecha_match.group(1) if fecha_match else "No encontrado"
    
    # Fecha de vencimiento
    vencimiento_match = re.search(r'<cbc:DueDate>(\d{4}-\d{2}-\d{2})</cbc:DueDate>', xml_texto)
    datos['fecha_vencimiento'] = vencimiento_match.group(1) if vencimiento_match else "No encontrado"
    
    # Moneda
    moneda_match = re.search(r'<cbc:DocumentCurrencyCode>([A-Z]{3})</cbc:DocumentCurrencyCode>', xml_texto)
    datos['moneda'] = moneda_match.group(1) if moneda_match else "No encontrado"
    
    # Monto total (PayableAmount)
    monto_match = re.search(r'<cbc:PayableAmount currencyID="([A-Z]{3})">([\d.]+)</cbc:PayableAmount>', xml_texto)
    if monto_match:
        datos['monto_moneda'] = monto_match.group(1)
        datos['monto_total'] = monto_match.group(2)
    else:
        datos['monto_moneda'] = "No encontrado"
        datos['monto_total'] = "No encontrado"
    
    # Monto gravado (base imponible)
    gravado_match = re.search(r'<cbc:TaxableAmount currencyID="[A-Z]{3}">([\d.]+)</cbc:TaxableAmount>', xml_texto)
    datos['monto_gravado'] = gravado_match.group(1) if gravado_match else "No encontrado"
    
    # IGV
    igv_match = re.search(r'<cbc:TaxAmount currencyID="[A-Z]{3}">([\d.]+)</cbc:TaxAmount>', xml_texto)
    datos['igv'] = igv_match.group(1) if igv_match else "No encontrado"
    
    return datos

# ============================================
# FUNCIÓN: COMPARAR CON IA
# ============================================

def comparar_con_ia(pdf_texto, xml_texto, pdf_nombre, xml_nombre):
    """Envía a Groq la comparación y devuelve análisis y discrepancias"""
    
    if not client:
        return "Error: GROQ_API_KEY no configurada", True
    
    # Extraer datos del XML
    datos = extraer_datos_xml(xml_texto)
    
    # Construir el prompt DINÁMICO (sin valores fijos)
    prompt = f"""
    Eres un auditor de facturas electrónicas peruanas.

    === DATOS DEL XML (estos son los valores CORRECTOS que debe tener la factura) ===
    - RUC del Emisor (proveedor): {datos['ruc_emisor']}
    - RUC del Cliente (comprador): {datos['ruc_cliente']}
    - Número de Factura: {datos['numero_factura']}
    - Fecha de Emisión: {datos['fecha_emision']}
    - Fecha de Vencimiento: {datos['fecha_vencimiento']}
    - Moneda: {datos['moneda']}
    - Monto Total (incluye IGV): {datos['monto_total']} {datos['monto_moneda']}
    - Monto Gravado (base imponible): {datos['monto_gravado']} {datos['monto_moneda']}
    - IGV (18%): {datos['igv']} {datos['monto_moneda']}

    === CONTENIDO EXTRAÍDO DEL PDF ===
    {pdf_texto[:15000]}

    === TAREA ===
    Compara los datos visuales del PDF contra los datos del XML que te di arriba.
    
    Verifica si los siguientes campos COINCIDEN entre el PDF y el XML:
    1. RUC del emisor
    2. Número de factura
    3. Fecha de emisión
    4. Monto total
    
    Si algún campo NO coincide o no se encuentra en el PDF, indica cuál es la discrepancia.

    === FORMATO DE RESPUESTA ===
    ===ANALISIS===
    [Explica qué campos coinciden y cuáles no. Menciona específicamente los valores que ves en el PDF y compáralos con los del XML]

    ===DISCREPANCIAS===
    [Escribe SOLO "true" si hay ALGUNA discrepancia, o "false" si TODO coincide perfectamente]
    """

    try:
        print("🤖 Llamando a Groq...")
        print(f"   RUC XML: {datos['ruc_emisor']}")
        print(f"   Número XML: {datos['numero_factura']}")
        print(f"   Monto XML: {datos['monto_total']} {datos['monto_moneda']}")
        
        completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "Eres un auditor de facturas electrónicas peruanas. Compara el PDF con los datos del XML. Sé preciso y específico."},
                {"role": "user", "content": prompt}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.1,
            max_tokens=2000
        )

        respuesta = completion.choices[0].message.content
        print("✅ Respuesta recibida de Groq")
        
        # Parsear la respuesta
        analisis = respuesta
        tiene_discrepancias = True
        
        if "===ANALISIS===" in respuesta:
            partes = respuesta.split("===DISCREPANCIAS===")
            analisis = partes[0].replace("===ANALISIS===", "").strip()
            if len(partes) > 1:
                texto_discrepancia = partes[1].strip().lower()
                tiene_discrepancias = "true" in texto_discrepancia
        
        return analisis, tiene_discrepancias
        
    except Exception as e:
        print(f"❌ Error llamando a Groq: {str(e)}")
        return f"Error en IA: {str(e)}", True

# ============================================
# ENDPOINT PRINCIPAL: COMPARAR PDF vs XML
# ============================================

@app.route('/comparar', methods=['POST'])
def comparar():
    print("\n" + "="*50)
    print("📨 NUEVA PETICIÓN A /comparar")
    print("="*50)
    
    try:
        # Validar que sea JSON
        if not request.is_json:
            return jsonify({'status': 'error', 'message': 'Se requiere Content-Type: application/json'}), 400
        
        data = request.get_json()
        archivos = data.get('archivos', {})
        
        # Obtener Base64
        pdf_base64 = archivos.get('pdf_base64', '')
        xml_base64 = archivos.get('xml_base64', '')
        
        if not pdf_base64:
            return jsonify({'status': 'error', 'message': 'Falta pdf_base64'}), 400
        if not xml_base64:
            return jsonify({'status': 'error', 'message': 'Falta xml_base64'}), 400
        
        # Decodificar Base64
        try:
            pdf_bytes = base64.b64decode(pdf_base64)
            xml_bytes = base64.b64decode(xml_base64)
        except Exception as e:
            return jsonify({'status': 'error', 'message': f'Error decodificando Base64: {str(e)}'}), 400
        
        # Nombres de archivos
        pdf_nombre = archivos.get('pdf_name', 'documento.pdf')
        xml_nombre = archivos.get('xml_name', 'documento.xml')
        
        print(f"📄 PDF: {pdf_nombre} ({len(pdf_bytes)} bytes)")
        print(f"📄 XML: {xml_nombre} ({len(xml_bytes)} bytes)")
        
        # Extraer texto
        print("📖 Extrayendo texto del PDF...")
        pdf_texto = extraer_texto_pdf(pdf_bytes)
        
        print("📖 Extrayendo texto del XML...")
        xml_texto = extraer_texto_xml(xml_bytes)
        
        print(f"📝 PDF texto: {len(pdf_texto)} caracteres")
        print(f"📝 XML texto: {len(xml_texto)} caracteres")
        
        if not pdf_texto and not xml_texto:
            return jsonify({'status': 'error', 'message': 'No se pudo extraer texto de los archivos'}), 500
        
        # Comparar con IA
        analisis, tiene_discrepancias = comparar_con_ia(pdf_texto, xml_texto, pdf_nombre, xml_nombre)
        
        # Respuesta final
        respuesta = {
            'status': 'success',
            'pdf': pdf_nombre,
            'xml': xml_nombre,
            'analisis': analisis,
            'tiene_discrepancias': tiene_discrepancias,
            'timestamp': datetime.now().isoformat()
        }
        
        print(f"✅ Comparación completada. Discrepancias: {tiene_discrepancias}")
        return jsonify(respuesta)
        
    except Exception as e:
        print(f"❌ ERROR INESPERADO: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ============================================
# ENDPOINTS DE PRUEBA
# ============================================

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'api': 'Factura Validator API',
        'version': '3.0.0',
        'status': 'ok',
        'endpoints': {
            '/comparar': 'POST - Compara un PDF con su XML',
            '/health': 'GET - Health check'
        }
    })

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'healthy',
        'groq_configured': client is not None,
        'timestamp': datetime.now().isoformat()
    })

# ============================================
# INICIO DEL SERVIDOR
# ============================================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    env = os.environ.get('ENVIRONMENT', 'LOCAL')
    
    print("\n" + "="*50)
    print("🚀 FACTURA VALIDATOR API v3.0")
    print("="*50)
    print(f"📡 Puerto: {port}")
    print(f"🌍 Entorno: {env}")
    print(f"🤖 Groq: {'✅ Configurado' if client else '❌ No configurado'}")
    print("="*50)
    print("\n📌 Endpoints disponibles:")
    print("   POST /comparar  - Comparar PDF vs XML")
    print("   GET  /          - Información")
    print("   GET  /health    - Health check")
    print("="*50 + "\n")
    
    app.run(host='0.0.0.0', port=port, debug=(env=='LOCAL'))
