from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import base64
from datetime import datetime
import tempfile
import fitz  # PyMuPDF
from groq import Groq
import re

app = Flask(__name__)
CORS(app)

GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
client = Groq(api_key=GROQ_API_KEY)

def extraer_texto_pdf(contenido_bytes):
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
        tmp.write(contenido_bytes)
        tmp_path = tmp.name
    try:
        texto = ""
        with fitz.open(tmp_path) as doc:
            for page in doc:
                texto += page.get_text()
        return texto[:20000]
    finally:
        os.remove(tmp_path)

def extraer_texto_xml(contenido_bytes):
    try:
        texto = contenido_bytes.decode('utf-8')
    except:
        texto = contenido_bytes.decode('latin-1')
    return texto[:20000]

def comparar_con_ia(pdf_texto, xml_texto, pdf_nombre, xml_nombre):
    prompt = f"""
    Compara el PDF y XML de esta factura.

    PDF: {pdf_nombre}
    {pdf_texto}

    XML: {xml_nombre}
    {xml_texto}

    Responde EXACTAMENTE con este formato:

    ===ANALISIS===
    [Tu análisis aquí]

    ===DISCREPANCIAS===
    [true o false]
    """
    completion = client.chat.completions.create(
        messages=[
            {"role": "system", "content": "Eres un auditor de facturas."},
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
            tiene_discrepancias = "true" in partes[1].lower()
    return analisis, tiene_discrepancias

@app.route('/comparar', methods=['POST'])
def comparar():
    print("\n=== COMPARANDO PDF vs XML ===")
    try:
        data = request.get_json()
        archivos = data.get('archivos', {})
        pdf_bytes = base64.b64decode(archivos.get('pdf_base64', ''))
        xml_bytes = base64.b64decode(archivos.get('xml_base64', ''))
        pdf_nombre = archivos.get('pdf_name', 'documento.pdf')
        xml_nombre = archivos.get('xml_name', 'documento.xml')
        print(f"📄 Procesando: {pdf_nombre} y {xml_nombre}")
        pdf_texto = extraer_texto_pdf(pdf_bytes)
        xml_texto = extraer_texto_xml(xml_bytes)
        analisis, tiene_discrepancias = comparar_con_ia(pdf_texto, xml_texto, pdf_nombre, xml_nombre)
        return jsonify({
            'status': 'success',
            'pdf': pdf_nombre,
            'xml': xml_nombre,
            'analisis': analisis,
            'tiene_discrepancias': tiene_discrepancias,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/', methods=['GET'])
def home():
    return jsonify({'api': 'Factura Validator', 'status': 'ok'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
