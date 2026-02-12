import streamlit as st
import pandas as pd
import re
import csv

# --- FUNCIONES DE LIMPIEZA ---

def limpiar_importe_agresivo(val):
    """
    Limpieza agresiva para recuperar montos financieros argentinos.
    1. Convierte a string.
    2. Elimina TODO lo que no sea dígito, coma (decimal) o guion (negativo).
    3. Reemplaza la coma por punto.
    """
    if pd.isna(val) or str(val).strip() == '':
        return 0.0
    
    val_str = str(val).strip()
    
    # Excepción común: Si la celda contiene texto largo (error de columna desplazada), devolver error
    if len(val_str) > 50: 
        return None # Esto disparará el contador de errores
        
    # Usamos Expresiones Regulares (Regex)
    # Paso 1: Mantener solo dígitos (0-9), comas (,) y guiones (-)
    # Esto elimina puntos de miles, símbolos $, letras, espacios, comillas, etc.
    val_limpio = re.sub(r'[^\d,-]', '', val_str)
    
    # Paso 2: Manejo de signo negativo al final (ej: "100,00-") típico de contabilidad
    if val_limpio.endswith('-'):
        val_limpio = '-' + val_limpio[:-1]
        
    # Paso 3: Reemplazar coma decimal por punto python
    val_limpio = val_limpio.replace(',', '.')
    
    try:
        return float(val_limpio)
    except ValueError:
        return None # Retornamos None para contar esto como error

def formato_argentino(valor):
    if pd.isna(valor): return "0,00"
    return "{:,.2f}".format(valor).replace(",", "X").replace(".", ",").replace("X", ".")

# --- CARGA INTELIGENTE ---

def cargar_datos(uploaded_file):
    """
    Intenta leer el archivo forzando la separación por tabulaciones pura,
    ignorando comillas que puedan romper las columnas.
    """
    strategies = [
        # Estrategia 1: Tabulaciones estricta (CSV.QUOTE_NONE)
        # Fundamental para archivos "Falso Excel" que tienen comillas en los nombres
        {'sep': '\t', 'quoting': csv.QUOTE_NONE, 'encoding': 'latin-1'},
        
        # Estrategia 2: Tabulaciones estándar
        {'sep': '\t', 'encoding': 'latin-1'},
        
        # Estrategia 3: Punto y coma
        {'sep': ';', 'encoding': 'latin-1'},
        
        # Estrategia 4: Excel real
        {'engine': 'openpyxl'}
    ]

    for params in strategies:
        try:
            uploaded_file.seek(0)
            if 'engine' in params:
                df = pd.read_excel(uploaded_file, dtype=str)
            else:
                # Leemos todo como texto (dtype=str) para no perder ceros a la izquierda o decimales
                df = pd.read_csv(uploaded_file, dtype=str, on_bad_lines='skip', **params)
            
            # Verificación básica de éxito
            if len(df.columns) > 1 and 'Tipo de Operación' in df.columns:
                return df
        except Exception:
            continue
            
    return None

# --- APP PRINCIPAL ---

def main():
    st.set_page_config(page_title="HISTORIAL FIRMANTE", layout="wide")
    st.title("HISTORIAL FIRMANTE")
    st.markdown("---")

    uploaded_file = st.file_uploader("Cargar archivo (Excel o Texto)", type=['csv', 'txt', 'xlsx', 'xls'])

    if uploaded_file is not None:
        
        df = cargar_datos(uploaded_file)

        if df is None:
            st.error("Error crítico: No se pudo interpretar el formato del archivo.")
            return

        # Normalizar columnas
        df.columns = df.columns.str.strip()
        
        # Validar columnas
        req_cols = ['Tipo de Operación', 'Importe', 'Estado']
        missing = [c for c in req_cols if c not in df.columns]
        if missing:
            st.error(f"Faltan columnas: {', '.join(missing)}")
            st.write("Columnas encontradas:", list(df.columns))
            return

        # 1. FILTRADO
        df_filtrado = df[df['Tipo de Operación'].astype(str).str.contains('CO - Compra', case=False, na=False)].copy()

        if df_filtrado.empty:
            st.warning("No se encontraron operaciones 'CO - Compra'.")
            return

        # 2. LIMPIEZA DE IMPORTES
        # Aplicamos la limpieza y guardamos en una nueva columna numérica
        df_filtrado['Importe_Num'] = df_filtrado['Importe'].apply(limpiar_importe_agresivo)

        # 3. DETECCIÓN DE ERRORES DE LECTURA
        # Buscamos filas donde la limpieza devolvió None (falló)
        filas_error = df_filtrado[df_filtrado['Importe_Num'].isna()]
        
        # Rellenamos los None con 0.0 para poder sumar sin error
        df_filtrado['Importe_Num'] = df_filtrado['Importe_Num'].fillna(0.0)

        # Alerta de errores
        if not filas_error.empty:
            st.warning(f"⚠️ Atención: Hay {len(filas_error)} filas con importes ilegibles (se contaron como $0).")
            with st.expander("🔍 Ver qué falló (Diagnóstico)"):
                st.write("Estas son las filas donde el Importe no se pudo entender. Verifica si la columna 'Importe' tiene texto desplazado.")
                # Mostramos la columna Importe original para ver qué tiene adentro
                st.dataframe(filas_error[['Tipo de Operación', 'Importe', 'Estado']])

        # 4. CÁLCULOS
        importe_total = df_filtrado['Importe_Num'].sum()
        cantidad_cheques = len(df_filtrado) # Cuenta todas, incluso las que dieron error de importe (son cheques físicos igual)

        mask_acreditado = df_filtrado['Estado'].astype(str).str.upper().str.contains('ACREDITADO')
        mask_rechazado = df_filtrado['Estado'].astype(str).str.upper().str.contains('RECHAZADO')

        total_acreditado = df_filtrado.loc[mask_acreditado, 'Importe_Num'].sum()
        total_rechazado = df_filtrado.loc[mask_rechazado, 'Importe_Num'].sum()

        if importe_total > 0:
            pct_rechazado = (total_rechazado / importe_total * 100)
            pct_acreditado = (total_acreditado / importe_total * 100)
        else:
            pct_rechazado = 0
            pct_acreditado = 0

        # 5. VISUALIZACIÓN
        st.subheader("Resumen de Operaciones (Solo Compra)")
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Importe Total", f"$ {formato_argentino(importe_total)}")
        c2.metric("Cheques", cantidad_cheques)
        c3.metric("Acreditado", f"$ {formato_argentino(total_acreditado)}", f"{pct_acreditado:.2f}%")
        c4.metric("Rechazado", f"$ {formato_argentino(total_rechazado)}", f"{pct_rechazado:.2f}%", delta_color="inverse")

        st.divider()

        # Frase
        txt_monto = f"$ {formato_argentino(importe_total)}"
        if total_rechazado > 0:
            st.error(f"Durante los últimos 12 meses se descontaron **{cantidad_cheques}** valores por **{txt_monto}** con rechazos del **{pct_rechazado:.2f}%**.")
        else:
            st.success(f"Durante los últimos 12 meses se descontaron **{cantidad_cheques}** valores por **{txt_monto}**. **Sin registrar rechazos**.")

        with st.expander("Ver detalle completo"):
            st.dataframe(df_filtrado[['Fecha de Op', 'Cheque', 'Importe', 'Importe_Num', 'Estado']])

if __name__ == "__main__":
    main()
