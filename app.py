import streamlit as st
import pandas as pd
import io

# --- FUNCIONES AUXILIARES ---

def formato_argentino(valor):
    """Convierte un float a string con formato 1.000,00"""
    if pd.isna(valor):
        return "0,00"
    return "{:,.2f}".format(valor).replace(",", "X").replace(".", ",").replace("X", ".")

def limpiar_importe_argentino(val):
    """
    Convierte strings como '21.354.480,00' o '$ 1.500,50' a float python (21354480.0)
    """
    if pd.isna(val): 
        return 0.0
    val = str(val)
    # Eliminamos el punto de los miles
    val = val.replace('.', '')
    # Reemplazamos la coma decimal por punto
    val = val.replace(',', '.')
    # Eliminamos símbolos de moneda y espacios
    val = val.replace('$', '').strip()
    try:
        return float(val)
    except ValueError:
        return 0.0

def cargar_datos(uploaded_file):
    """
    Intenta leer el archivo con múltiples estrategias:
    1. Como Excel real.
    2. Como Texto separado por TABULACIONES (Detectado en tu imagen).
    3. Como CSV con punto y coma.
    4. Como CSV con coma.
    """
    
    # --- ESTRATEGIA 1: EXCEL NATIVO ---
    try:
        # Engine 'openpyxl' es para .xlsx, para .xls viejos a veces falla si no son reales
        df = pd.read_excel(uploaded_file)
        return df
    except Exception:
        pass # Falló, probablemente no es un Excel binario real

    # Reseteamos el puntero para leer desde cero
    uploaded_file.seek(0)

    # --- ESTRATEGIA 2: TEXTO CON TABULACIONES (La más probable según tu foto) ---
    try:
        # sep='\t' indica tabulación
        df = pd.read_csv(uploaded_file, sep='\t', encoding='latin-1')
        # Verificamos si leyó bien las columnas clave
        if 'Tipo de Operación' in df.columns or len(df.columns) > 1:
            return df
    except Exception:
        pass

    uploaded_file.seek(0)

    # --- ESTRATEGIA 3: CSV con PUNTO Y COMA ---
    try:
        df = pd.read_csv(uploaded_file, sep=';', encoding='latin-1')
        if len(df.columns) > 1:
            return df
    except Exception:
        pass

    uploaded_file.seek(0)

    # --- ESTRATEGIA 4: CSV con COMA ---
    try:
        df = pd.read_csv(uploaded_file, sep=',', encoding='latin-1')
        return df
    except Exception:
        return None

# --- APP PRINCIPAL ---

def main():
    st.set_page_config(page_title="HISTORIAL FIRMANTE", layout="wide")
    
    st.title("HISTORIAL FIRMANTE")
    st.markdown("---")

    st.info("Sube tu archivo 'recuperoPrestamo...'. El sistema detectará automáticamente si es Excel o Texto.")
    
    uploaded_file = st.file_uploader("Cargar archivo", type=['csv', 'txt', 'xlsx', 'xls'])

    if uploaded_file is not None:
        
        # Cargamos los datos
        df = cargar_datos(uploaded_file)

        if df is None:
            st.error("No se pudo leer el archivo. El formato no coincide con Excel, CSV ni Tabulaciones.")
            return

        # Normalización de nombres de columnas
        df.columns = df.columns.str.strip()

        # Validación de columnas necesarias
        required_cols = ['Tipo de Operación', 'Importe', 'Estado']
        missing = [col for col in required_cols if col not in df.columns]
        
        if missing:
            st.error(f"Se leyó el archivo pero faltan columnas clave: {', '.join(missing)}")
            st.write("Columnas detectadas:", list(df.columns))
            # Mostramos las primeras filas para que el usuario entienda qué pasó
            st.dataframe(df.head())
            return

        # --- LOGICA DE NEGOCIO ---

        # 1. Filtrar solo COMPRA
        df_filtrado = df[df['Tipo de Operación'].astype(str).str.contains('CO - Compra', case=False, na=False)].copy()

        if df_filtrado.empty:
            st.warning("El archivo se leyó correctamente, pero no se encontraron filas con 'CO - Compra'.")
            st.write("Muestra de datos leídos (primeras 5 filas):")
            st.dataframe(df.head())
            return

        # 2. Convertir Importes
        if pd.api.types.is_numeric_dtype(df_filtrado['Importe']):
            df_filtrado['Importe_Num'] = df_filtrado['Importe']
        else:
            df_filtrado['Importe_Num'] = df_filtrado['Importe'].apply(limpiar_importe_argentino)

        # 3. Cálculos
        importe_total_descontado = df_filtrado['Importe_Num'].sum()
        cantidad_cheques = len(df_filtrado)

        # Filtros de Estado
        estados = df_filtrado['Estado'].astype(str).str.upper()
        mask_acreditado = estados.str.contains('ACREDITADO')
        mask_rechazado = estados.str.contains('RECHAZADO')

        total_acreditado = df_filtrado.loc[mask_acreditado, 'Importe_Num'].sum()
        total_rechazado = df_filtrado.loc[mask_rechazado, 'Importe_Num'].sum()

        if importe_total_descontado > 0:
            pct_rechazado = (total_rechazado / importe_total_descontado * 100)
            pct_acreditado = (total_acreditado / importe_total_descontado * 100)
        else:
            pct_rechazado = 0
            pct_acreditado = 0

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

        with st.expander("Ver detalle de datos procesados"):
            st.dataframe(df_filtrado)

if __name__ == "__main__":
    main()
