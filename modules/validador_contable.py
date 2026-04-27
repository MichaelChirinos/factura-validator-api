import os
import re
from thefuzz import process, fuzz
from groq import Groq
import json
from modules.cargador_datos import cargar_catalogo, cargar_historico, cargar_memoria, guardar_memoria

GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# Cargar datos al iniciar el módulo
catalogo_dict, nombre_a_codigo, codigos_validos = cargar_catalogo()
df_historico = cargar_historico()
historico_desc_list = df_historico['Dscription'].tolist() if not df_historico.empty else []
desc_to_acct = dict(zip(df_historico['Dscription'].str.lower(), df_historico['AcctName'])) if not df_historico.empty else {}

MEMORIA = cargar_memoria()


def extraer_patron(desc):
    """Extrae un patrón simplificado de la descripción para buscar en memoria"""
    if not desc:
        return ""
    desc = desc.lower()
    desc = re.sub(r'dcc\s*\d+\s*-?\s*', '', desc)
    desc = re.sub(r'[a-z]+\s+[a-z]+\s+[a-z]+', '', desc)
    desc = re.sub(r'\d+', '#', desc)
    desc = re.sub(r'[^\w\s]', ' ', desc)
    palabras = re.findall(r'[a-záéíóúñ]{4,}', desc)
    return ' '.join(palabras[:3])


def buscar_contexto_historico(descripcion, proveedor=None):
    """Busca coincidencias similares en el histórico usando fuzzy matching"""
    if not historico_desc_list:
        return ""
    
    matches = process.extract(descripcion, historico_desc_list, limit=5, scorer=fuzz.token_set_ratio)
    contexto = []
    for val, score in matches:
        if score > 50:
            nombre = desc_to_acct.get(val.lower(), '')
            if nombre:
                contexto.append(f"- '{val[:60]}' → {nombre}")
    return '\n'.join(contexto)


def es_codigo_valido(codigo):
    """Verifica si un código existe en el catálogo"""
    return str(codigo) in codigos_validos


def obtener_nombre_desde_codigo(codigo):
    """Obtiene el nombre de la cuenta desde el código"""
    return catalogo_dict.get(str(codigo))


def auditar(descripcion_sql, cuenta_actual, proveedor=None, centro_costo=None):
    """
    Función principal que valida si la cuenta contable es correcta
    """
    codigo_actual = str(cuenta_actual.get('AcctCode', ''))
    nombre_actual = cuenta_actual.get('AcctName', '')
    patron = extraer_patron(descripcion_sql)
    
    print(f"🔍 Auditando: {descripcion_sql[:50]}...")
    print(f"   Cuenta actual: {codigo_actual} - {nombre_actual}")
    
    # 1. Buscar en MEMORIA (aprendizaje previo)
    if patron and patron in MEMORIA:
        recordado = MEMORIA[patron]
        print(f"   📚 Encontrado en memoria: {recordado['codigo']} (veces: {recordado['veces']})")
        
        if recordado['codigo'] != codigo_actual:
            return {
                "es_correcta": False,
                "codigo_sugerido": recordado['codigo'],
                "nombre_sugerido": recordado['nombre'],
                "justificacion": f"📚 Aprendido de {recordado['veces']} casos similares",
                "confianza": 0.9
            }
        else:
            return {
                "es_correcta": True,
                "codigo_sugerido": codigo_actual,
                "nombre_sugerido": nombre_actual,
                "justificacion": "✓ Consistente con aprendizaje previo",
                "confianza": 0.9
            }
    
    # 2. Buscar en HISTÓRICO (fuzzy matching)
    contexto = buscar_contexto_historico(descripcion_sql, proveedor)
    
    # 3. Usar IA (Groq) para decidir
    if client:
        prompt = f"""Eres un auditor contable. Analiza esta factura:

DESCRIPCIÓN: "{descripcion_sql[:150]}"
CUENTA ACTUAL: {codigo_actual} - {nombre_actual}
PROVEEDOR: {proveedor if proveedor else 'No especificado'}

CONTEXTO HISTÓRICO (descripciones similares y sus cuentas):
{contexto}

REGLAS:
- Si el contexto histórico muestra una cuenta consistente, sugiere esa
- Si no hay contexto claro, mantén la cuenta actual
- NO inventes códigos que no existan
- Responde SOLO con un JSON válido

RESPONDE EXACTAMENTE ESTE FORMATO:
{{"es_correcta": true/false, "codigo_sugerido": "string", "nombre_sugerido": "string", "justificacion": "string"}}"""

        try:
            print("   🤖 Llamando a Groq...")
            res = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=300
            )
            resultado = json.loads(res.choices[0].message.content)
            print(f"   ✅ IA respondió: {resultado.get('es_correcta')}")
            
        except Exception as e:
            print(f"   ❌ Error en IA: {str(e)}")
            resultado = {
                "es_correcta": True,
                "codigo_sugerido": codigo_actual,
                "nombre_sugerido": nombre_actual,
                "justificacion": "Error en IA, se mantiene cuenta actual"
            }
    else:
        resultado = {
            "es_correcta": True,
            "codigo_sugerido": codigo_actual,
            "nombre_sugerido": nombre_actual,
            "justificacion": "Sin IA, se mantiene cuenta actual"
        }
    
    # 4. Validar que el código sugerido exista en el catálogo
    codigo_sugerido = str(resultado.get('codigo_sugerido', ''))
    nombre_sugerido = resultado.get('nombre_sugerido', '')
    
    if not es_codigo_valido(codigo_sugerido):
        # Buscar por nombre
        codigo_por_nombre = nombre_a_codigo.get(nombre_sugerido)
        if codigo_por_nombre:
            resultado['codigo_sugerido'] = codigo_por_nombre
            resultado['justificacion'] = f"🔍 '{codigo_sugerido}' no existe, se usó {codigo_por_nombre}"
        else:
            # No existe, mantener el actual
            resultado['codigo_sugerido'] = codigo_actual
            resultado['nombre_sugerido'] = nombre_actual
            resultado['es_correcta'] = True
            resultado['justificacion'] = f"⚠️ Código inválido. Se mantiene {codigo_actual}"
    
    # 5. Aprender y guardar en memoria (solo si hubo discrepancia)
    if patron and not resultado['es_correcta']:
        if patron not in MEMORIA:
            MEMORIA[patron] = {
                'codigo': resultado['codigo_sugerido'],
                'nombre': resultado['nombre_sugerido'],
                'veces': 1
            }
        else:
            MEMORIA[patron]['veces'] += 1
        guardar_memoria(MEMORIA)
        print(f"   🧠 Aprendido nuevo patrón: {patron}")
    
    return resultado
