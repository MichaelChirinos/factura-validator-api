import pandas as pd
import json
import os

DATA_DIR = 'data'


def cargar_catalogo():
    """Carga el catálogo de cuentas (results_1.csv)"""
    try:
        df = pd.read_csv(
            os.path.join(DATA_DIR, 'results_1.csv'),
            sep=';',
            names=['AcctCode', 'AcctName'],
            encoding='latin-1',
            on_bad_lines='skip'
        )
        catalogo_dict = dict(zip(df['AcctCode'].astype(str), df['AcctName']))
        nombre_a_codigo = {v: k for k, v in catalogo_dict.items()}
        codigos_validos = set(catalogo_dict.keys())
        print(f"📚 Catálogo cargado: {len(codigos_validos)} cuentas")
        return catalogo_dict, nombre_a_codigo, codigos_validos
    except Exception as e:
        print(f"❌ Error cargando catálogo: {str(e)}")
        return {}, {}, set()


def cargar_historico():
    """Carga el histórico de facturas (results.csv)"""
    try:
        df = pd.read_csv(
            os.path.join(DATA_DIR, 'results.csv'),
            sep=';',
            names=['ItemCode', 'Dscription', 'AcctName', 'Proveedor',
                   'ItmsGrpNam', 'U_TipGasCos', 'U_TipOper', 'OcrCode3'],
            encoding='latin-1',
            on_bad_lines='skip'
        )
        df = df.dropna(subset=['Dscription', 'AcctName'])
        print(f"📊 Histórico cargado: {len(df)} registros")
        return df
    except Exception as e:
        print(f"❌ Error cargando histórico: {str(e)}")
        return pd.DataFrame()


def cargar_memoria():
    """Carga la memoria persistente (aprendizaje)"""
    memoria_path = os.path.join(DATA_DIR, 'memoria.json')
    if os.path.exists(memoria_path):
        try:
            with open(memoria_path, 'r', encoding='latin-1') as f:
                memoria = json.load(f)
                print(f"🧠 Memoria cargada: {len(memoria)} patrones")
                return memoria
        except:
            return {}
    print("🧠 Memoria nueva (vacía)")
    return {}


def guardar_memoria(memoria):
    """Guarda la memoria persistente"""
    memoria_path = os.path.join(DATA_DIR, 'memoria.json')
    try:
        with open(memoria_path, 'w', encoding='latin-1') as f:
            json.dump(memoria, f, indent=2)
        print(f"💾 Memoria guardada: {len(memoria)} patrones")
    except Exception as e:
        print(f"❌ Error guardando memoria: {str(e)}")
