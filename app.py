from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import base64
from datetime import datetime
from modules.comparador import comparar_pdf_xml

app = Flask(__name__)
CORS(app)


@app.route('/comparar', methods=['POST'])
def comparar():
    print("\n" + "="*50)
    print("📨 NUEVA PETICIÓN A /comparar")
    print("="*50)
    
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
        
        pdf_nombre = archivos.get('pdf_name', 'documento.pdf')
        xml_nombre = archivos.get('xml_name', 'documento.xml')
        
        print(f"📄 PDF: {pdf_nombre} ({len(pdf_bytes)} bytes)")
        print(f"📄 XML: {xml_nombre} ({len(xml_bytes)} bytes)")
        
        resultado = comparar_pdf_xml(pdf_bytes, xml_bytes, pdf_nombre, xml_nombre)
        
        respuesta = {
            'status': 'success',
            'pdf': pdf_nombre,
            'xml': xml_nombre,
            'analisis': resultado['analisis'],
            'tiene_discrepancias': resultado['tiene_discrepancias'],
            'datos_xml': resultado.get('datos_xml', {}),
            'timestamp': datetime.now().isoformat()
        }
        
        print(f"✅ Completado. Discrepancias: {resultado['tiene_discrepancias']}")
        return jsonify(respuesta)
        
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'api': 'Factura Validator API',
        'version': '4.0.0',
        'status': 'ok'
    })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
