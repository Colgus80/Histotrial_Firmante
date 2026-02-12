import streamlit as st
import pandas as pd
import re

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="HISTORIAL FIRMANTE", layout="wide")

# --- FUNCIONES DE LIMPIEZA ---

def limpiar_importe_formato_ingles(val):
    """
    Interpreta formato 1,234.56 (Coma miles, Punto decimal).
    """
    if pd.isna(val) or str(val).strip() == '':
        return 0.0
    
    val_str = str(val).strip()
    
    # 1. Limpieza de símbolos de moneda y espacios
    val_limpio = val_str.replace('$', '').replace(' ', '')
    
    # 2. ELIMINAR LA COMA (Separador de miles en este formato)
    # Ejemplo: "21,354,480.00" -> "21354480.00"
    val_limpio = val_limpio.replace(',', '')
    
    # 3. El punto ya es el decimal correcto para Python, no lo tocamos.
    
    try:
        return float(val_limpio)
    except ValueError:
        return 0.0

def formato_visual_salida(valor):
    """
    Muestra el resultado final en formato visual amigable (con separadores).
    """
    return "{:,.2f}".format(valor)

# --- CARGA DE ARCHIVO ---
def cargar_datos(uploaded_file):
    """
    Intenta leer el archivo (Excel, HTML, CSV)
    """
    # Estrategia 1: HTML (para "falsos excel")
    try:
        uploaded_file.seek(0)
        dfs = pd.read_html(uploaded_file, encoding='latin-1', decimal='.', thousands=',')
        if dfs:
            for df in dfs:
                if 'Importe' in df.columns or len(df.columns) > 5:
                    return df
    except Exception:
        pass

    # Estrategia 2: CSV/Texto con Tabulaciones
    try:
        uploaded_file.seek(0)
        df = pd.read_csv(uploaded_file, sep='\t', encoding='latin-1', dtype=str)
        if 'Importe' in df.columns: return df
    except Exception:
        pass

    # Estrategia 3: Excel real
    try:
        uploaded_file.seek(0)
        df = pd.read_excel(uploaded_file, dtype=str)
        return df
    except Exception:
        pass
    
    # Estrategia 4: CSV genérico
    try:
        uploaded_file.seek(0)
        df = pd.read_csv(uploaded_file, sep=',', encoding='latin-1', dtype=str)
        return df
    except Exception:
        return None

# --- APP PRINCIPAL ---
def main():
    st.title("HISTORIAL FIRMANTE")
    st.markdown("---")
    
    st.info("Configuración actual: **Punto (.) como decimal** y **Coma (,) como miles**.")

    uploaded_file = st.file_uploader("Cargar archivo", type=['xls', 'xlsx', 'csv', 'txt'])

    if uploaded_file is not None:
        
        df = cargar_datos(uploaded_file)

        if df is None:
            st.error("No se pudo leer el archivo.")
            return

        df.columns = df.columns.str.strip()

        # Validación básica
        if 'Importe' not in df.columns:
            st.error("No se encontró la columna 'Importe'.")
            st.write("Columnas detectadas:", list(df.columns))
            return

        # 1. FILTRADO
        if 'Tipo de Operación' in df.columns:
            df_filtrado = df[df['Tipo de Operación'].astype(str).str.contains('CO - Compra', case=False, na=False)].copy()
        else:
            df_filtrado = df.copy()

        if df_filtrado.empty:
            st.warning("No hay operaciones 'CO - Compra'.")
            return

        # 2. CONVERSIÓN CON NUEVO FORMATO
        df_filtrado['Importe_Num'] = df_filtrado['Importe'].apply(limpiar_importe_formato_ingles)

        # 3. DEBUG (Para que verifiques visualmente)
        with st.expander("Verificación de lectura de importes"):
            st.write("Revisa si la columna 'Importe_Num' coincide con 'Importe' (sin comas de miles):")
            st.dataframe(df_filtrado[['Importe', 'Importe_Num']].head(10))

        # 4. CÁLCULOS
        importe_total = df_filtrado['Importe_Num'].sum()
        cantidad = len(df_filtrado)

        if 'Estado' in df.columns:
            estados = df_filtrado['Estado'].astype(str).str.upper()
            total_acreditado = df_filtrado.loc[estados.str.contains('ACREDITADO'), 'Importe_Num'].sum()
            total_rechazado = df_filtrado.loc[estados.str.contains('RECHAZADO'), 'Importe_Num'].sum()
        else:
            total_acreditado = 0
            total_rechazado = 0

        if importe_total > 0:
            pct_rechazado = (total_rechazado / importe_total * 100)
            pct_acreditado = (total_acreditado / importe_total * 100)
        else:
            pct_rechazado = 0
            pct_acreditado = 0

        # 5. VISUALIZACIÓN
        st.subheader("Resumen de Operaciones (Solo Compra)")
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Importe Total", f"$ {formato_visual_salida(importe_total)}")
        c2.metric("Cantidad Cheques", cantidad)
        c3.metric("Acreditado", f"$ {formato_visual_salida(total_acreditado)}", f"{pct_acreditado:.2f}%")
        c4.metric("Rechazado", f"$ {formato_visual_salida(total_rechazado)}", f"{pct_rechazado:.2f}%", delta_color="inverse")

        st.divider()

        txt_monto = f"$ {formato_visual_salida(importe_total)}"
        
        if total_rechazado > 0:
            st.error(f"Durante los últimos 12 meses se descontaron **{cantidad}** valores de la firma por un total de **{txt_monto}** con un margen de rechazos de **{pct_rechazado:.2f}%**.")
        else:
            st.success(f"Durante los últimos 12 meses se descontaron **{cantidad}** valores de la firma por un total de **{txt_monto}**. **Sin registrar rechazos**.")

        with st.expander("Ver detalle completo"):
            cols = [c for c in ['Fecha de Op', 'Cheque', 'Importe', 'Estado'] if c in df_filtrado.columns]
            st.dataframe(df_filtrado[cols])

if __name__ == "__main__":
    main()
