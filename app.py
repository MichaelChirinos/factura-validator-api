from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import base64
from datetime import datetime
import PyPDF2
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
# FUNCIONES DE EXTRACCIÓN DE TEXTO
# ============================================

def extraer_texto_pdf(contenido_bytes):
    """Extrae texto de un archivo PDF usando PyPDF2"""
    try:
        # Crear un objeto de archivo en memoria
        pdf_file = BytesIO(contenido_bytes)
        # Leer el PDF
        reader = PyPDF2.PdfReader(pdf_file)
        texto = ""
        
        # Extraer texto de cada página
        for page_num, page in enumerate(reader.pages):
            page_text = page.extract_text()
            if page_text:
                texto += page_text
            print(f"📄 Página {page_num + 1}: {len(page_text)} caracteres")
        
        # Limitar a 20000 caracteres para no saturar Groq
        return texto[:20000]
    except Exception as e:
        print(f"❌ Error extrayendo texto del PDF: {str(e)}")
        return ""

def extraer_texto_xml(contenido_bytes):
    """Extrae texto de un archivo XML"""
    try:
        # Intentar decodificar como UTF-8
        texto = contenido_bytes.decode('utf-8')
    except UnicodeDecodeError:
        try:
            # Si falla, intentar con latin-1
            texto = contenido_bytes.decode('latin-1')
        except:
            # Si todo falla, convertir a string
            texto = str(contenido_bytes)
    
    # Limitar a 20000 caracteres
    return texto[:20000]

# ============================================
# FUNCIÓN DE COMPARACIÓN CON IA
# ============================================

def comparar_con_ia(pdf_texto, xml_texto, pdf_nombre, xml_nombre):
    """Envía a Groq la comparación y devuelve análisis y discrepancias"""
    
    if not client:
        return "Error: GROQ_API_KEY no configurada", True
    
    prompt = f"""
    Eres un auditor de facturas electrónicas peruanas.

    Compara el PDF y XML de esta factura.

    === ARCHIVO PDF ===
    Nombre: {pdf_nombre}
    Contenido:
    {pdf_texto[:8000]}

    === ARCHIVO XML ===
    Nombre: {xml_nombre}
    Contenido:
    {xml_texto[:8000]}

    === TAREA ===
    Compara los datos del PDF contra los datos del XML.
    Verifica especialmente: RUC, Serie, Número, Fecha, Monto Total.

    === FORMATO DE RESPUESTA ===
    ===ANALISIS===
    [Escribe aquí tu análisis detallado de qué campos coinciden y cuáles no]

    ===DISCREPANCIAS===
    [Escribe SOLO "true" si hay discrepancias, o "false" si todo coincide]
    """

    try:
        print("🤖 Llamando a Groq...")
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
        print("✅ Respuesta recibida de Groq")
        
        # Parsear la respuesta
        analisis = ""
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
        # 1. Obtener y validar el JSON de entrada
        if not request.is_json:
            return jsonify({'status': 'error', 'message': 'Se requiere Content-Type: application/json'}), 400
        
        data = request.get_json()
        archivos = data.get('archivos', {})
        
        # 2. Extraer los archivos en Base64
        pdf_base64 = archivos.get('pdf_base64', '')
        xml_base64 = archivos.get('xml_base64', '')
        
        if not pdf_base64:
            return jsonify({'status': 'error', 'message': 'Falta pdf_base64'}), 400
        if not xml_base64:
            return jsonify({'status': 'error', 'message': 'Falta xml_base64'}), 400
        
        # 3. Decodificar Base64 a bytes
        try:
            pdf_bytes = base64.b64decode(pdf_base64)
            xml_bytes = base64.b64decode(xml_base64)
        except Exception as e:
            return jsonify({'status': 'error', 'message': f'Error decodificando Base64: {str(e)}'}), 400
        
        # 4. Obtener nombres de los archivos
        pdf_nombre = archivos.get('pdf_name', 'documento.pdf')
        xml_nombre = archivos.get('xml_name', 'documento.xml')
        
        print(f"📄 PDF: {pdf_nombre} ({len(pdf_bytes)} bytes)")
        print(f"📄 XML: {xml_nombre} ({len(xml_bytes)} bytes)")
        
        # 5. Extraer texto de los archivos
        print("📖 Extrayendo texto del PDF...")
        pdf_texto = extraer_texto_pdf(pdf_bytes)
        
        print("📖 Extrayendo texto del XML...")
        xml_texto = extraer_texto_xml(xml_bytes)
        
        print(f"📝 Texto PDF extraído: {len(pdf_texto)} caracteres")
        print(f"📝 Texto XML extraído: {len(xml_texto)} caracteres")
        
        if not pdf_texto and not xml_texto:
            return jsonify({'status': 'error', 'message': 'No se pudo extraer texto de los archivos'}), 500
        
        # 6. Comparar con IA
        print("🤖 Enviando a Groq para comparación...")
        analisis, tiene_discrepancias = comparar_con_ia(pdf_texto, xml_texto, pdf_nombre, xml_nombre)
        
        # 7. Devolver respuesta
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
# ENDPOINT DE PRUEBA (HEALTH CHECK)
# ============================================

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'api': 'Factura Validator API',
        'version': '2.0.0',
        'status': 'ok',
        'endpoints': {
            '/comparar': 'POST - Compara un PDF con su XML',
            '/': 'GET - Información de la API'
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
    print("🚀 FACTURA VALIDATOR API")
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
