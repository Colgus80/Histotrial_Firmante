import streamlit as st
import pandas as pd
import io

# --- FUNCIÓN DE LIMPIEZA "BLINDADA" ---
def limpiar_importe_argentino(val):
    """
    Convierte strings con formato argentino (puntos para miles, coma para decimales)
    a float de Python.
    Ejemplos: 
    "21.354.480,00" -> 21354480.0
    "$ 1.500,50" -> 1500.50
    """
    if pd.isna(val) or str(val).strip() == '':
        return 0.0
    
    val_str = str(val).strip()
    
    # 1. Eliminar caracteres que no son números ni separadores
    # Mantenemos solo dígitos, puntos, comas y el signo menos
    val_limpio = ''.join([c for c in val_str if c.isdigit() or c in ['.', ',', '-']])
    
    # 2. Lógica específica Argentina:
    # Eliminar TODOS los puntos (son separadores de miles)
    val_limpio = val_limpio.replace('.', '')
    
    # Reemplazar la coma por punto (para que sea el decimal válido en Python)
    val_limpio = val_limpio.replace(',', '.')
    
    try:
        return float(val_limpio)
    except ValueError:
        return 0.0

def formato_argentino(valor):
    if pd.isna(valor):
        return "0,00"
    return "{:,.2f}".format(valor).replace(",", "X").replace(".", ",").replace("X", ".")

def cargar_datos(uploaded_file):
    # Intentamos leer forzando que todo sea texto (dtype=str) para evitar conversiones erróneas automáticas
    
    # 1. Estrategia Excel Real
    try:
        df = pd.read_excel(uploaded_file, dtype=str)
        return df
    except:
        pass

    uploaded_file.seek(0)

    # 2. Estrategia Tabulaciones (Tu caso más probable)
    try:
        df = pd.read_csv(uploaded_file, sep='\t', encoding='latin-1', dtype=str)
        if len(df.columns) > 1: return df
    except:
        pass

    uploaded_file.seek(0)

    # 3. Estrategia Punto y Coma
    try:
        df = pd.read_csv(uploaded_file, sep=';', encoding='latin-1', dtype=str)
        if len(df.columns) > 1: return df
    except:
        pass

    uploaded_file.seek(0)
    
    # 4. Estrategia Coma
    try:
        df = pd.read_csv(uploaded_file, sep=',', encoding='latin-1', dtype=str)
        return df
    except:
        return None

# --- APP PRINCIPAL ---
def main():
    st.set_page_config(page_title="HISTORIAL FIRMANTE", layout="wide")
    st.title("HISTORIAL FIRMANTE")
    st.markdown("---")
    
    st.info("Sube tu archivo. El sistema procesará los importes con formato '1.000,00' (Argentina).")

    uploaded_file = st.file_uploader("Cargar archivo", type=['csv', 'txt', 'xlsx', 'xls'])

    if uploaded_file is not None:
        
        df = cargar_datos(uploaded_file)

        if df is None:
            st.error("No se pudo leer el archivo. Verifica que no esté corrupto.")
            return

        # Limpieza de nombres de columnas
        df.columns = df.columns.str.strip()

        # Validación de columnas
        required_cols = ['Tipo de Operación', 'Importe', 'Estado']
        missing = [col for col in required_cols if col not in df.columns]
        
        if missing:
            st.error(f"Faltan columnas clave: {', '.join(missing)}")
            st.write("Columnas detectadas:", list(df.columns))
            return

        # --- FILTRADO ---
        # Filtramos primero
        df_filtrado = df[df['Tipo de Operación'].astype(str).str.contains('CO - Compra', case=False, na=False)].copy()

        if df_filtrado.empty:
            st.warning("No hay registros de 'CO - Compra'.")
            st.write("Primeras 5 filas del archivo original para revisión:")
            st.dataframe(df.head())
            return

        # --- CONVERSIÓN DE IMPORTES ---
        # Aplicamos la limpieza
        df_filtrado['Importe_Num'] = df_filtrado['Importe'].apply(limpiar_importe_argentino)

        # --- VALIDACIÓN DE SUMA (DEBUG) ---
        # Verificamos si hubo filas que quedaron en 0 pero tenían texto original (posible error)
        errores = df_filtrado[ (df_filtrado['Importe_Num'] == 0) & (df_filtrado['Importe'].astype(str).str.strip() != '0') & (df_filtrado['Importe'].astype(str).str.strip() != '0,00') ]
        
        if not errores.empty and len(errores) > 0:
            st.warning(f"Atención: Hay {len(errores)} filas donde el importe no se pudo leer correctamente y se sumaron como $0.")
            with st.expander("Ver filas con error de lectura de importe"):
                st.dataframe(errores[['Tipo de Operación', 'Importe', 'Estado']])

        # --- CÁLCULOS FINALES ---
        importe_total_descontado = df_filtrado['Importe_Num'].sum()
        cantidad_cheques = len(df_filtrado)

        estados = df_filtrado['Estado'].astype(str).str.upper()
        mask_acreditado = estados.str.contains('ACREDITADO')
        mask_rechazado = estados.str.contains('RECHAZADO')

        total_acreditado = df_filtrado.loc[mask_acreditado, 'Importe_Num'].sum()
        total_rechazado = df_filtrado.loc[mask_rechazado, 'Importe_Num'].sum()

        pct_rechazado = (total_rechazado / importe_total_descontado * 100) if importe_total_descontado > 0 else 0
        pct_acreditado = (total_acreditado / importe_total_descontado * 100) if importe_total_descontado > 0 else 0

        # --- VISUALIZACIÓN ---
        st.subheader("Resumen de Operaciones (Solo Compra)")
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Importe Total Descontado", f"$ {formato_argentino(importe_total_descontado)}")
        col2.metric("Cantidad de Cheques", cantidad_cheques)
        col3.metric("Total Acreditado", f"$ {formato_argentino(total_acreditado)}", f"{pct_acreditado:.2f}%")
        col4.metric("Total Rechazado", f"$ {formato_argentino(total_rechazado)}", f"{pct_rechazado:.2f}%", delta_color="inverse")

        st.divider()

        txt_importe = f"$ {formato_argentino(importe_total_descontado)}"
        if total_rechazado > 0:
            msg = (f"Durante los últimos 12 meses se descontaron **{cantidad_cheques}** valores de la firma "
                   f"por un total de **{txt_importe}** con un margen de rechazos de **{pct_rechazado:.2f}%**.")
            st.error(msg)
        else:
            msg = (f"Durante los últimos 12 meses se descontaron **{cantidad_cheques}** valores de la firma "
                   f"por un total de **{txt_importe}**. **Sin registrar rechazos**.")
            st.success(msg)

        with st.expander("Ver detalle de operaciones incluidas en el cálculo"):
            st.dataframe(df_filtrado[['Fecha de Op', 'Cheque', 'Importe', 'Importe_Num', 'Estado']])

if __name__ == "__main__":
    main()
