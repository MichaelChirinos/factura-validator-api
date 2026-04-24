from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import base64
from datetime import datetime

# Importar módulos
from modules.comparador import comparar_pdf_xml

app = Flask(__name__)
CORS(app)

# ============================================
# ENDPOINT PRINCIPAL: COMPARAR PDF vs XML
# ============================================
@app.route('/comparar', methods=['POST'])
def comparar():
    print("\n=== COMPARANDO PDF vs XML ===")
    
    try:
        # 1. Recibir archivos desde Power Automate
        if request.is_json:
            data = request.get_json()
            archivos = data.get('archivos', {})
            
            # Decodificar Base64
            pdf_bytes = base64.b64decode(archivos.get('pdf_base64', ''))
            xml_bytes = base64.b64decode(archivos.get('xml_base64', ''))
            pdf_nombre = archivos.get('pdf_name', 'documento.pdf')
            xml_nombre = archivos.get('xml_name', 'documento.xml')
            
        else:
            # Para pruebas desde formulario
            pdf_file = request.files.get('pdf')
            xml_file = request.files.get('xml')
            pdf_bytes = pdf_file.read()
            xml_bytes = xml_file.read()
            pdf_nombre = pdf_file.filename
            xml_nombre = xml_file.filename
        
        # 2. Llamar al módulo de comparación
        resultado = comparar_pdf_xml(pdf_bytes, xml_bytes, pdf_nombre, xml_nombre)
        
        # 3. Devolver respuesta
        return jsonify({
            'status': 'success',
            'pdf': pdf_nombre,
            'xml': xml_nombre,
            'analisis': resultado['analisis'],
            'tiene_discrepancias': resultado['tiene_discrepancias'],
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ============================================
# ENDPOINT PARA PROBAR QUE LA API VIVE
# ============================================
@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'api': 'Factura Validator API',
        'version': '1.0.0',
        'endpoints': {
            '/comparar': 'POST - Compara PDF vs XML'
        }
    })


# ============================================
# INICIO DEL SERVIDOR
# ============================================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    env = os.environ.get('ENVIRONMENT', 'LOCAL')
    
    print("\n" + "="*50)
    print("🚀 API Factura Validator")
    print(f"📡 Puerto: {port}")
    print(f"🌍 Entorno: {env}")
    print("="*50)
    
    app.run(host='0.0.0.0', port=port, debug=(env=='LOCAL'))
