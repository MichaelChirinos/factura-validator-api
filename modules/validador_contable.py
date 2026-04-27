import os
import re
from thefuzz import process, fuzz
from groq import Groq
import json
from modules.cargador_datos import cargar_catalogo, cargar_historico, cargar_memoria, guardar_memoria

GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# Cargar datos al iniciar
catalogo_dict, nombre_a_codigo, codigos_validos = cargar_catalogo()
df_historico = cargar_historico()
historico_desc_list = df_historico['Dscription'].tolist() if not df_historico.empty else []
desc_to_acct = dict(zip(df_historico['Dscription'].str.lower(), df_historico['AcctName'])) if not df_historico.empty else {}

# Crear índice búsqueda mejorada (descripción + proveedor)
historico_mejorado = []
if not df_historico.empty:
    for _, row in df_historico.iterrows():
        historico_mejorado.append({
            'desc': row['Dscription'],
            'acct_code': row.get('AcctCode', ''),
            'acct_name': row['AcctName'],
            'proveedor': row.get('Proveedor', '')
        })

MEMORIA = cargar_memoria()


def extraer_patron_inteligente(desc, proveedor=None):
    """Extrae un patrón más inteligente usando descripción y proveedor"""
    if not desc:
        return ""
    
    desc_limpia = desc.lower()
    # Eliminar códigos y números
    desc_limpia = re.sub(r'dcc\s*\d+\s*-?\s*', '', desc_limpia)
    desc_limpia = re.sub(r'\b\d+\b', '', desc_limpia)
    # Eliminar palabras comunes
    palabras_comunes = ['para', 'con', 'por', 'del', 'de', 'la', 'el', 'los', 'las', 'y', 'o', 'un', 'una']
    palabras = re.findall(r'[a-záéíóúñ]{4,}', desc_limpia)
    palabras = [p for p in palabras if p not in palabras_comunes]
    
    patron_base = ' '.join(palabras[:4])
    
    # Si hay proveedor, agregarlo al patrón
    if proveedor and proveedor != 'No especificado':
        proveedor_limpio = re.sub(r'\s+(S\.A\.|S\.A\.C\.|SAC|SRL|EIRL|PERU)', '', proveedor, flags=re.IGNORECASE)
        proveedor_limpio = re.sub(r'\s+', ' ', proveedor_limpio).strip()
        return f"{patron_base}|{proveedor_limpio[:20]}"
    
    return patron_base


def buscar_contexto_historico_mejorado(descripcion, proveedor=None, umbral=70):
    """Busca coincidencias en histórico usando descripción y proveedor"""
    if not historico_mejorado:
        return []
    
    contexto = []
    
    # 1. Búsqueda por descripción (fuzzy)
    desc_matches = process.extract(descripcion, [h['desc'] for h in historico_mejorado], limit=5, scorer=fuzz.token_set_ratio)
    
    for match_desc, score in desc_matches:
        if score >= umbral:
            # Encontrar el elemento completo
            for item in historico_mejorado:
                if item['desc'] == match_desc:
                    contexto.append({
                        'descripcion': match_desc[:60],
                        'cuenta': item['acct_name'],
                        'codigo': item['acct_code'],
                        'proveedor': item['proveedor'],
                        'score': score
                    })
                    break
    
    # 2. Si hay proveedor, buscar también por proveedor
    if proveedor and len(contexto) < 2:
        for item in historico_mejorado:
            if item['proveedor'] and proveedor.lower() in item['proveedor'].lower():
                if item not in contexto:
                    contexto.append({
                        'descripcion': item['desc'][:60],
                        'cuenta': item['acct_name'],
                        'codigo': item['acct_code'],
                        'proveedor': item['proveedor'],
                        'score': 85
                    })
                    if len(contexto) >= 2:
                        break
    
    return contexto[:3]


def es_codigo_valido(codigo):
    """Verifica si un código existe en el catálogo"""
    if not codigo:
        return False
    codigo_str = str(codigo).strip()
    # Si es número, asegurar formato string
    return codigo_str in codigos_validos


def obtener_codigo_sugerido_desde_contexto(contexto):
    """Obtiene el código más frecuente del contexto"""
    if not contexto:
        return None, None
    
    # Contar frecuencias de códigos
    frecuencias = {}
    for item in contexto:
        codigo = item.get('codigo')
        if codigo and es_codigo_valido(codigo):
            frecuencias[codigo] = frecuencias.get(codigo, 0) + item.get('score', 50)
    
    if frecuencias:
        codigo_sugerido = max(frecuencias, key=frecuencias.get)
        nombre_sugerido = catalogo_dict.get(codigo_sugerido, '')
        return codigo_sugerido, nombre_sugerido
    
    return None, None


def auditar(descripcion_sql, cuenta_actual, proveedor=None, centro_costo=None):
    """
    Función principal que valida si la cuenta contable es correcta
    """
    codigo_actual = str(cuenta_actual.get('AcctCode', '')).strip()
    nombre_actual = cuenta_actual.get('AcctName', '')
    
    print(f"\n🔍 Auditando:")
    print(f"   Descripción: {descripcion_sql[:80]}")
    print(f"   Cuenta actual: {codigo_actual} - {nombre_actual}")
    print(f"   Proveedor: {proveedor}")
    
    # 1. Buscar en MEMORIA (aprendizaje previo)
    patron = extraer_patron_inteligente(descripcion_sql, proveedor)
    
    if patron and patron in MEMORIA:
        recordado = MEMORIA[patron]
        print(f"   📚 Memoria encontrada: {recordado['codigo']}")
        
        if recordado['codigo'] != codigo_actual and es_codigo_valido(recordado['codigo']):
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
    
    # 2. Buscar en HISTÓRICO (fuzzy matching mejorado)
    contexto = buscar_contexto_historico_mejorado(descripcion_sql, proveedor, umbral=65)
    
    if contexto:
        print(f"   📊 Contexto histórico encontrado: {len(contexto)} coincidencias")
        for ctx in contexto:
            print(f"      - {ctx['descripcion']} → {ctx['cuenta']} (score: {ctx['score']})")
        
        # Si el contexto es consistente (misma cuenta), sugerir esa
        codigo_sugerido, nombre_sugerido = obtener_codigo_sugerido_desde_contexto(contexto)
        
        if codigo_sugerido and codigo_sugerido != codigo_actual and es_codigo_valido(codigo_sugerido):
            return {
                "es_correcta": False,
                "codigo_sugerido": codigo_sugerido,
                "nombre_sugerido": nombre_sugerido,
                "justificacion": f"📊 Basado en {len(contexto)} casos históricos similares",
                "confianza": 0.85
            }
    
    # 3. Usar IA solo si hay contexto o es necesario (prompt más restrictivo)
    if client:
        # Construir contexto para IA (limitado)
        contexto_str = ""
        for ctx in contexto[:2]:
            contexto_str += f"- {ctx['descripcion']} → {ctx['cuenta']} (código: {ctx['codigo']})\n"
        
        prompt = f"""Eres un auditor contable. Evalúa si la cuenta actual es correcta.

DESCRIPCIÓN: "{descripcion_sql[:100]}"
PROVEEDOR: {proveedor if proveedor else 'No especificado'}
CUENTA ACTUAL: {codigo_actual} - {nombre_actual}

CONTEXTO HISTÓRICO (si existe):
{contexto_str if contexto_str else 'No hay contexto histórico disponible'}

REGLAS ESTRICTAS:
1. Si el contexto histórico muestra una cuenta consistente, sugiere ESA cuenta
2. Si NO hay contexto claro o la descripción no coincide, responde es_correcta = true
3. NUNCA inventes cuentas que no estén en el contexto
4. SOLO puedes sugerir códigos que sean números de 4-6 dígitos existentes

RESPONDE EXACTAMENTE ESTE JSON:
{{"es_correcta": true, "codigo_sugerido": "{codigo_actual}", "nombre_sugerido": "{nombre_actual}", "justificacion": "Explicación corta"}}"""

        try:
            print("   🤖 Llamando a Groq (prompt optimizado)...")
            res = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=200
            )
            resultado = json.loads(res.choices[0].message.content)
            print(f"   ✅ IA respondió: es_correcta={resultado.get('es_correcta')}")
            
            # Validar que el código sugerido existe en catálogo
            codigo_sug = str(resultado.get('codigo_sugerido', ''))
            if not es_codigo_valido(codigo_sug):
                resultado['codigo_sugerido'] = codigo_actual
                resultado['nombre_sugerido'] = nombre_actual
                resultado['es_correcta'] = True
                resultado['justificacion'] = "Código inválido, se mantiene cuenta actual"
            
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
    
    # 4. Aprender y guardar en memoria (solo si hubo discrepancia y hay contexto)
    if patron and not resultado['es_correcta'] and contexto:
        if patron not in MEMORIA:
            MEMORIA[patron] = {
                'codigo': resultado['codigo_sugerido'],
                'nombre': resultado['nombre_sugerido'],
                'veces': 1
            }
        else:
            MEMORIA[patron]['veces'] += 1
        guardar_memoria(MEMORIA)
        print(f"   🧠 Aprendido nuevo patrón: {patron[:50]}...")
    
    return resultado
