import streamlit as st
import pandas as pd
import re

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="HISTORIAL FIRMANTE", layout="wide")

# --- FUNCIÓN DE LIMPIEZA SIMPLIFICADA ---
def limpiar_importe(val):
    """
    Convierte el formato argentino 1.000,00 a float 1000.00
    Asume que el dato viene correcto de Excel.
    """
    if pd.isna(val) or str(val).strip() == '':
        return 0.0
    
    # Convertimos a string
    val_str = str(val).strip()
    
    # 1. Si ya es un número limpio (ej: 1500.50), lo devolvemos
    try:
        return float(val_str)
    except ValueError:
        pass

    # 2. Limpieza formato ARG (1.234,56)
    # Quitamos el punto de los miles
    val_limpio = val_str.replace('.', '')
    # Cambiamos la coma por punto
    val_limpio = val_limpio.replace(',', '.')
    # Quitamos el signo $ si existe
    val_limpio = val_limpio.replace('$', '').strip()
    
    try:
        return float(val_limpio)
    except ValueError:
        return 0.0

def formato_visual(valor):
    return "{:,.2f}".format(valor).replace(",", "X").replace(".", ",").replace("X", ".")

# --- LECTURA DE ARCHIVO ROBUSTA ---
def cargar_dataframe(uploaded_file):
    """
    Prueba todas las formas posibles de leer un archivo 'Excel' bancario.
    """
    filename = uploaded_file.name.lower()
    
    # ESTRATEGIA 1: HTML (Muy común en archivos .xls que pesan poco y se ven con colores)
    try:
        uploaded_file.seek(0)
        # pd.read_html devuelve una lista de tablas, tomamos la más grande
        dfs = pd.read_html(uploaded_file, encoding='latin-1', decimal=',', thousands='.')
        if dfs:
            # Buscamos la tabla que tenga la columna 'Importe'
            for df in dfs:
                if 'Importe' in df.columns or len(df.columns) > 5:
                    return df
    except Exception:
        pass # No es HTML

    # ESTRATEGIA 2: CSV/TEXTO CON TABULACIONES (Lo que detectamos antes)
    try:
        uploaded_file.seek(0)
        df = pd.read_csv(uploaded_file, sep='\t', encoding='latin-1', dtype=str)
        if 'Importe' in df.columns: return df
    except Exception:
        pass

    # ESTRATEGIA 3: EXCEL REAL (.xlsx)
    try:
        uploaded_file.seek(0)
        df = pd.read_excel(uploaded_file, dtype=str)
        return df
    except Exception:
        pass

    # ESTRATEGIA 4: CSV CON PUNTO Y COMA
    try:
        uploaded_file.seek(0)
        df = pd.read_csv(uploaded_file, sep=';', encoding='latin-1', dtype=str)
        return df
    except Exception:
        return None

# --- APP PRINCIPAL ---
def main():
    st.title("HISTORIAL FIRMANTE")
    st.markdown("---")
    
    st.info("Sube el archivo tal cual lo descargaste. El sistema probará leerlo como HTML, Excel o Texto.")

    uploaded_file = st.file_uploader("Cargar archivo", type=['xls', 'xlsx', 'csv', 'txt'])

    if uploaded_file is not None:
        
        df = cargar_dataframe(uploaded_file)

        if df is None:
            st.error("No se pudo leer el archivo con ningún método conocido.")
            return

        # Limpiamos nombres de columnas (espacios extra)
        df.columns = df.columns.str.strip()

        # Verificamos columnas críticas
        if 'Importe' not in df.columns:
            st.error("El archivo se leyó pero no se encuentra la columna 'Importe'.")
            st.write("Columnas detectadas:", list(df.columns))
            st.dataframe(df.head())
            return

        # --- FILTRADO (Solo Compra) ---
        # Normalizamos la columna para filtrar sin errores
        if 'Tipo de Operación' in df.columns:
            df_filtrado = df[df['Tipo de Operación'].astype(str).str.contains('CO - Compra', case=False, na=False)].copy()
        else:
            st.warning("No se encontró columna 'Tipo de Operación', se procesarán todas las filas.")
            df_filtrado = df.copy()

        if df_filtrado.empty:
            st.warning("No hay operaciones 'CO - Compra'.")
            return

        # --- CONVERSIÓN ---
        # Aplicamos la limpieza
        df_filtrado['Importe_Num'] = df_filtrado['Importe'].apply(limpiar_importe)

        # --- DEBUG VISUAL ---
        # Esto te permitirá ver si está leyendo bien los números
        if st.checkbox("Mostrar verificación de datos (Debug)"):
            st.write("Primeras 5 filas procesadas:")
            st.dataframe(df_filtrado[['Importe', 'Importe_Num']].head())

        # --- CÁLCULOS ---
        importe_total = df_filtrado['Importe_Num'].sum()
        cantidad = len(df_filtrado)

        # Estados
        if 'Estado' in df.columns:
            estados = df_filtrado['Estado'].astype(str).str.upper()
            total_acreditado = df_filtrado.loc[estados.str.contains('ACREDITADO'), 'Importe_Num'].sum()
            total_rechazado = df_filtrado.loc[estados.str.contains('RECHAZADO'), 'Importe_Num'].sum()
        else:
            total_acreditado = 0
            total_rechazado = 0

        # Porcentajes
        if importe_total > 0:
            pct_rechazado = (total_rechazado / importe_total * 100)
            pct_acreditado = (total_acreditado / importe_total * 100)
        else:
            pct_rechazado = 0
            pct_acreditado = 0

        # --- PANTALLA ---
        st.subheader("Resumen de Operaciones (Solo Compra)")
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Importe Total", f"$ {formato_visual(importe_total)}")
        c2.metric("Cantidad Cheques", cantidad)
        c3.metric("Acreditado", f"$ {formato_visual(total_acreditado)}", f"{pct_acreditado:.1f}%")
        c4.metric("Rechazado", f"$ {formato_visual(total_rechazado)}", f"{pct_rechazado:.1f}%", delta_color="inverse")

        st.divider()

        txt_monto = f"$ {formato_visual(importe_total)}"
        
        if total_rechazado > 0:
            st.error(f"Durante los últimos 12 meses se descontaron **{cantidad}** valores de la firma por un total de **{txt_monto}** con un margen de rechazos de **{pct_rechazado:.2f}%**.")
        else:
            st.success(f"Durante los últimos 12 meses se descontaron **{cantidad}** valores de la firma por un total de **{txt_monto}**. **Sin registrar rechazos**.")

        with st.expander("Ver detalle de operaciones"):
            cols_to_show = [c for c in ['Fecha de Op', 'Cheque', 'Importe', 'Estado', 'Cuit Firmante'] if c in df_filtrado.columns]
            st.dataframe(df_filtrado[cols_to_show])

if __name__ == "__main__":
    main()
