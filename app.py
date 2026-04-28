from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import base64
from datetime import datetime
from modules.comparador import comparar_pdf_xml
from modules.validador_contable import auditar
from modules.validador_ubicacion import validar_ubicacion

app = Flask(__name__)
CORS(app)


# ==================== ENDPOINT 1: PDF vs XML ====================
@app.route('/comparar', methods=['POST'])
def comparar():
    print("\n=== NUEVA PETICIÓN A /comparar ===")
    
    try:
        if not request.is_json:
            return jsonify({'status': 'error', 'message': 'Se requiere JSON'}), 400
        
        data = request.get_json()
        archivos = data.get('archivos', {})
        
        pdf_base64 = archivos.get('pdf_base64', '')
        xml_base64 = archivos.get('xml_base64', '')
        
        if not pdf_base64 or not xml_base64:
            return jsonify({'status': 'error', 'message': 'Faltan archivos'}), 400
        
        pdf_bytes = base64.b64decode(pdf_base64)
        xml_bytes = base64.b64decode(xml_base64)
        pdf_nombre = archivos.get('pdf_name', 'factura.pdf')
        xml_nombre = archivos.get('xml_name', 'factura.xml')
        
        resultado = comparar_pdf_xml(pdf_bytes, xml_bytes, pdf_nombre, xml_nombre)
        
        return jsonify({
            'status': 'success',
            'pdf_procesado': pdf_nombre,
            'xml_procesado': xml_nombre,
            'analisis_ia': resultado['analisis'],
            'alerta_discrepancia': resultado['tiene_discrepancias'],
            'num_factura': resultado.get('num_factura', ''),
            'ruc_proveedor': resultado.get('ruc_proveedor', ''), 
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ==================== ENDPOINT 2: VALIDAR CUENTA CONTABLE ====================
@app.route('/auditar', methods=['POST'])
def auditar_cuenta():
    print("\n=== NUEVA PETICIÓN A /auditar ===")
    
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No se recibió JSON'}), 400
        
        descripcion_sql = data.get('descripcion_sql', '')
        cuenta_actual = data.get('cuenta_actual', {})
        proveedor = data.get('proveedor')
        centro_costo = data.get('centro_costo')
        
        if not descripcion_sql:
            return jsonify({'error': 'Falta descripcion_sql'}), 400
        
        if not cuenta_actual.get('AcctCode'):
            return jsonify({'error': 'Falta cuenta_actual.AcctCode'}), 400
        
        resultado = auditar(descripcion_sql, cuenta_actual, proveedor, centro_costo)
        
        return jsonify(resultado)
        
    except Exception as e:
        print(f"❌ ERROR en /auditar: {str(e)}")
        return jsonify({'error': str(e)}), 500


# ==================== ENDPOINTS DE PRUEBA ====================
@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'api': 'Factura Validator + Validador Contable',
        'version': '2.0.0',
        'endpoints': {
            '/comparar': 'POST - Compara PDF vs XML',
            '/auditar': 'POST - Valida cuenta contable'
        }
    })

@app.route('/validar-ubicacion', methods=['POST'])
def validar_ubicacion_endpoint():
    print("\n=== NUEVA PETICIÓN A /validar-ubicacion ===")
    
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No se recibió JSON'}), 400
        
        codigo_sap = data.get('codigo_sap', '')
        archivo_pdf = data.get('archivo_pdf', '')
        direccion_sap = data.get('direccion_sap', '')
        
        if not codigo_sap or not archivo_pdf:
            return jsonify({'error': 'Faltan codigo_sap o archivo_pdf'}), 400
        
        resultado = validar_ubicacion(codigo_sap, archivo_pdf, direccion_sap)
        
        return jsonify(resultado)
        
    except Exception as e:
        print(f"❌ ERROR en /validar-ubicacion: {str(e)}")
        return jsonify({'error': str(e)}), 500
@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    env = os.environ.get('ENVIRONMENT', 'LOCAL')
    
    print("\n" + "="*50)
    print("🚀 API UNIFICADA - Factura + Contabilidad")
    print(f"📡 Puerto: {port}")
    print(f"🌍 Entorno: {env}")
    print("="*50)
    print("\n📌 Endpoints:")
    print("   POST /comparar  - Validar factura (PDF vs XML)")
    print("   POST /auditar   - Validar cuenta contable")
    print("   GET  /health    - Health check")
    print("="*50 + "\n")
    
    app.run(host='0.0.0.0', port=port, debug=(env=='LOCAL'))
