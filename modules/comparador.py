import tempfile
import os
import fitz  # PyMuPDF
from groq import Groq
import re

# Configurar cliente Groq
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
client = Groq(api_key=GROQ_API_KEY)


def extraer_texto_pdf(contenido_bytes):
    """Extrae texto de un archivo PDF"""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
        tmp.write(contenido_bytes)
        tmp_path = tmp.name
    
    try:
        texto = ""
        with fitz.open(tmp_path) as doc:
            for page in doc:
                texto += page.get_text()
        return texto[:20000]  # Limitar para no saturar Groq
    finally:
        os.remove(tmp_path)


def extraer_texto_xml(contenido_bytes):
    """Extrae texto de un archivo XML"""
    try:
        texto = contenido_bytes.decode('utf-8')
    except:
        texto = contenido_bytes.decode('latin-1')
    return texto[:20000]


def comparar_con_ia(pdf_texto, xml_texto, pdf_nombre, xml_nombre):
    """Envía a Groq la comparación y devuelve análisis y discrepancias"""
    
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
    
    # 1. Extraer texto
    pdf_texto = extraer_texto_pdf(pdf_bytes)
    xml_texto = extraer_texto_xml(xml_bytes)
    
    # 2. Comparar con IA
    analisis, tiene_discrepancias = comparar_con_ia(pdf_texto, xml_texto, pdf_nombre, xml_nombre)
    
    # 3. Devolver resultado
    return {
        'analisis': analisis,
        'tiene_discrepancias': tiene_discrepancias
    }
