import streamlit as st
import pandas as pd
import re

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="HISTORIAL FIRMANTE", layout="wide")

# --- FUNCIONES DE LIMPIEZA Y FORMATO ---

def limpiar_importe_formato_ingles(val):
    """
    Interpreta formato 1,234.56 (Coma miles, Punto decimal).
    """
    if pd.isna(val) or str(val).strip() == '':
        return 0.0
    
    val_str = str(val).strip()
    # Limpieza de símbolos
    val_limpio = val_str.replace('$', '').replace(' ', '')
    # ELIMINAR LA COMA (Separador de miles)
    val_limpio = val_limpio.replace(',', '')
    
    try:
        return float(val_limpio)
    except ValueError:
        return 0.0

def formato_visual_sin_decimales(valor):
    """
    Para las TARJETAS (Métricas): Muestra el número entero con PUNTO como separador de miles.
    """
    if pd.isna(valor): return "0"
    val_str = "{:,.0f}".format(valor)
    return val_str.replace(",", ".")

def formato_humano(valor):
    """
    Para la FRASE FINAL: Muestra "1.5 millones" o "560 mil".
    """
    if valor >= 1_000_000:
        millones = valor / 1_000_000
        # Muestra 1 decimal (ej: 1.5 millones). 
        return f"${millones:.1f} millones"
    elif valor >= 1_000:
        miles = valor / 1_000
        # Muestra sin decimales para miles (ej: 560 mil)
        return f"${miles:.0f} mil"
    else:
        # Menor a mil, muestra el número normal
        return f"${valor:,.0f}".replace(",", ".")

# --- CARGA DE ARCHIVO ---
def cargar_datos(uploaded_file):
    # Estrategia 1: HTML
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
    
    uploaded_file = st.file_uploader("Cargar archivo", type=['xls', 'xlsx', 'csv', 'txt'])

    if uploaded_file is not None:
        
        df = cargar_datos(uploaded_file)

        if df is None:
            st.error("No se pudo leer el archivo.")
            return

        df.columns = df.columns.str.strip()

        if 'Importe' not in df.columns:
            st.error("No se encontró la columna 'Importe'.")
            return

        # 1. FILTRADO
        if 'Tipo de Operación' in df.columns:
            df_filtrado = df[df['Tipo de Operación'].astype(str).str.contains('CO - Compra', case=False, na=False)].copy()
        else:
            df_filtrado = df.copy()

        if df_filtrado.empty:
            st.warning("No hay operaciones 'CO - Compra'.")
            return

        # 2. OBTENER NOMBRE DEL FIRMANTE
        nombre_firmante = "No identificado"
        posibles_cols_nombre = ['Den. Firmante', 'Denominación', 'Firmante', 'Nombre', 'Razon Social']
        
        for col in posibles_cols_nombre:
            if col in df_filtrado.columns:
                val = df_filtrado[col].dropna().iloc[0]
                if val:
                    nombre_firmante = str(val).strip()
                    break

        # 3. CONVERSIÓN
        df_filtrado['Importe_Num'] = df_filtrado['Importe'].apply(limpiar_importe_formato_ingles)

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

        # --- VISUALIZACIÓN ---
        
        # CAMBIO 1: Etiqueta "Firmante"
        st.header(f"Firmante: {nombre_firmante}")
        st.subheader("Resumen de Operaciones (Solo Compra)")
        
        col1, col2, col3, col4 = st.columns(4)
        
        # Métricas (mantienen el formato numérico exacto pero limpio)
        col1.metric("Importe Total", f"$ {formato_visual_sin_decimales(importe_total)}")
        col2.metric("Cantidad Cheques", cantidad)
        col3.metric("Acreditado", f"$ {formato_visual_sin_decimales(total_acreditado)}", f"{pct_acreditado:.0f}%")
        col4.metric("Rechazado", f"$ {formato_visual_sin_decimales(total_rechazado)}", f"{pct_rechazado:.0f}%", delta_color="inverse")

        st.divider()

        # CAMBIO 2: Frase Final (Sin negrita, texto cambiado, formato millones/mil)
        txt_monto_humano = formato_humano(importe_total)
        
        if total_rechazado > 0:
            st.error(f"Durante los últimos 12 meses se descontaron en nuestra entidad {cantidad} valores de este firmante por un total de {txt_monto_humano} con un margen de rechazos de {pct_rechazado:.2f}%.")
        else:
            st.success(f"Durante los últimos 12 meses se descontaron en nuestra entidad {cantidad} valores de este firmante por un total de {txt_monto_humano}, sin registrar rechazos.")

        with st.expander("Ver detalle completo"):
            cols_interes = ['Fecha de Op', 'Cheque', 'Importe', 'Estado']
            if nombre_firmante != "No identificado":
                for col in posibles_cols_nombre:
                    if col in df_filtrado.columns:
                        cols_interes.append(col)
                        break
            
            cols_finales = [c for c in cols_interes if c in df_filtrado.columns]
            st.dataframe(df_filtrado[cols_finales])

if __name__ == "__main__":
    main()
