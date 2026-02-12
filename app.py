import streamlit as st
import pandas as pd

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
    Intenta leer el archivo como Excel real (.xlsx/.xls).
    Si falla, intenta como CSV con ; y luego con ,
    """
    # 1. Intento: Como Excel nativo
    try:
        df = pd.read_excel(uploaded_file)
        return df
    except Exception:
        pass # Si falla, seguimos al siguiente intento

    # Reseteamos el puntero del archivo para leerlo desde el principio
    uploaded_file.seek(0)

    # 2. Intento: Como CSV separado por punto y coma (común en latam)
    try:
        df = pd.read_csv(uploaded_file, sep=';', encoding='latin-1')
        # Verificación rápida: si solo tiene 1 columna, probablemente el separador estaba mal
        if len(df.columns) > 1:
            return df
    except Exception:
        pass

    uploaded_file.seek(0)

    # 3. Intento: Como CSV separado por coma
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

    st.info("Sube tu archivo (Excel .xlsx, .xls o CSV). El sistema detectará el formato automáticamente.")
    
    # Aceptamos múltiples extensiones
    uploaded_file = st.file_uploader("Cargar archivo", type=['csv', 'txt', 'xlsx', 'xls'])

    if uploaded_file is not None:
        
        # Cargamos los datos usando la función inteligente
        df = cargar_datos(uploaded_file)

        if df is None:
            st.error("No se pudo leer el archivo. Asegúrate de que sea un Excel o CSV válido.")
            return

        # Normalización de nombres de columnas (quita espacios extra al principio/final)
        df.columns = df.columns.str.strip()

        # Validación de columnas necesarias
        required_cols = ['Tipo de Operación', 'Importe', 'Estado']
        missing = [col for col in required_cols if col not in df.columns]
        
        if missing:
            st.error(f"El archivo leído no tiene las columnas requeridas: {', '.join(missing)}")
            st.write("Columnas detectadas:", list(df.columns))
            return

        # --- LOGICA DE NEGOCIO ---

        # 1. Filtrar solo COMPRA
        df_filtrado = df[df['Tipo de Operación'].astype(str).str.contains('CO - Compra', case=False, na=False)].copy()

        if df_filtrado.empty:
            st.warning("El archivo se leyó correctamente, pero no hay registros 'CO - Compra'.")
            return

        # 2. Convertir Importes
        # Detectamos si la columna ya vino como número (Excel real) o texto (CSV)
        if pd.api.types.is_numeric_dtype(df_filtrado['Importe']):
            df_filtrado['Importe_Num'] = df_filtrado['Importe']
        else:
            # Si es texto, aplicamos la limpieza argentina
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

        # Porcentajes (Evitando división por cero)
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

        # Frase Resumen
        txt_importe = f"$ {formato_argentino(importe_total_descontado)}"
        
        if total_rechazado > 0:
            msg = (f"Durante los últimos 12 meses se descontaron **{cantidad_cheques}** valores de la firma "
                   f"por un total de **{txt_importe}** con un margen de rechazos de **{pct_rechazado:.2f}%**.")
            st.error(msg)
        else:
            msg = (f"Durante los últimos 12 meses se descontaron **{cantidad_cheques}** valores de la firma "
                   f"por un total de **{txt_importe}**. **Sin registrar rechazos**.")
            st.success(msg)

        with st.expander("Ver datos procesados"):
            st.dataframe(df_filtrado)

if __name__ == "__main__":
    main()
