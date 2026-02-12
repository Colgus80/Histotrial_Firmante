import streamlit as st
import pandas as pd

# Función para formatear números al estilo argentino para la visualización final
# Ejemplo: convierte 1500.50 en "1.500,50"
def formato_argentino(valor):
    return "{:,.2f}".format(valor).replace(",", "X").replace(".", ",").replace("X", ".")

def main():
    st.set_page_config(page_title="HISTORIAL FIRMANTE", layout="wide")
    
    st.title("HISTORIAL FIRMANTE")
    st.markdown("---")

    st.write("Sube tu archivo CSV (exportado con formato similar a Excel).")
    uploaded_file = st.file_uploader("Cargar archivo", type=['csv', 'txt'])

    if uploaded_file is not None:
        try:
            # 1. INTENTO DE LECTURA DEL ARCHIVO
            # Los CSV bancarios a veces usan ; o tabulaciones. Probamos los más comunes.
            try:
                df = pd.read_csv(uploaded_file, sep=';', encoding='latin-1')
                if 'Tipo de Operación' not in df.columns: # Si falla, probamos con coma
                    uploaded_file.seek(0)
                    df = pd.read_csv(uploaded_file, sep=',', encoding='latin-1')
            except:
                st.error("Error leyendo el formato CSV. Asegurate de que esté separado por comas (,) o punto y coma (;).")
                return

            # Limpiamos espacios en los nombres de las columnas
            df.columns = df.columns.str.strip()

            # 2. VALIDACIÓN DE COLUMNAS
            # Basado en tu imagen, buscamos estas columnas clave
            required_cols = ['Tipo de Operación', 'Importe', 'Estado']
            missing_cols = [col for col in required_cols if col not in df.columns]
            
            if missing_cols:
                st.error(f"Faltan las siguientes columnas en el archivo: {', '.join(missing_cols)}")
                return

            # 3. FILTRADO: Solo 'CO - Compra'
            # Convertimos a string para evitar errores si hay datos vacíos
            df_filtrado = df[df['Tipo de Operación'].astype(str).str.contains('CO - Compra', case=False, na=False)].copy()

            if df_filtrado.empty:
                st.warning("El archivo no contiene registros con 'CO - Compra'.")
                return

            # 4. LIMPIEZA DE LA COLUMNA IMPORTE
            # El formato de la imagen es "21.354.480,00" (Punto miles, Coma decimales)
            def limpiar_importe(val):
                val = str(val)
                # Eliminamos el punto de los miles
                val = val.replace('.', '')
                # Reemplazamos la coma decimal por punto (para que Python lo entienda)
                val = val.replace(',', '.')
                # Eliminamos cualquier otro símbolo (como $)
                val = val.replace('$', '').strip()
                try:
                    return float(val)
                except ValueError:
                    return 0.0

            df_filtrado['Importe_Num'] = df_filtrado['Importe'].apply(limpiar_importe)

            # 5. CÁLCULOS
            importe_total_descontado = df_filtrado['Importe_Num'].sum()
            cantidad_cheques = len(df_filtrado)

            # Agrupación por Estado (ACREDITADO vs RECHAZADO)
            # Normalizamos a mayúsculas para asegurar coincidencia
            estados = df_filtrado['Estado'].astype(str).str.upper()
            
            # Filtros de estado
            mask_acreditado = estados.str.contains('ACREDITADO')
            mask_rechazado = estados.str.contains('RECHAZADO')

            total_acreditado = df_filtrado.loc[mask_acreditado, 'Importe_Num'].sum()
            total_rechazado = df_filtrado.loc[mask_rechazado, 'Importe_Num'].sum()

            # Cálculo de porcentajes
            pct_rechazado = (total_rechazado / importe_total_descontado * 100) if importe_total_descontado > 0 else 0
            pct_acreditado = (total_acreditado / importe_total_descontado * 100) if importe_total_descontado > 0 else 0

            # 6. VISUALIZACIÓN (MÉTRICAS)
            st.subheader("Análisis de Operaciones de Compra")
            
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("Importe Total Descontado", f"$ {formato_argentino(importe_total_descontado)}")
            with col2:
                st.metric("Cantidad de Cheques", cantidad_cheques)
            with col3:
                st.metric("Total Acreditado", f"$ {formato_argentino(total_acreditado)}", f"{pct_acreditado:.2f}%")
            with col4:
                # Delta invertido: rojo si sube (malo), verde si baja (bueno)
                st.metric("Total Rechazado", f"$ {formato_argentino(total_rechazado)}", f"{pct_rechazado:.2f}%", delta_color="inverse")

            st.markdown("---")

            # 7. GENERACIÓN DE LA FRASE FINAL
            txt_importe = f"$ {formato_argentino(importe_total_descontado)}"
            
            if total_rechazado > 0:
                mensaje_final = (
                    f"Durante los últimos 12 meses se descontaron **{cantidad_cheques}** valores de la firma "
                    f"por un total de **{txt_importe}** con un margen de rechazos de **{pct_rechazado:.2f}%**."
                )
                st.error(mensaje_final) # Usamos color rojo suave (error) para resaltar que hubo rechazos
            else:
                mensaje_final = (
                    f"Durante los últimos 12 meses se descontaron **{cantidad_cheques}** valores de la firma "
                    f"por un total de **{txt_importe}**. **Sin registrar rechazos**."
                )
                st.success(mensaje_final) # Color verde si está limpio

            # 8. MUESTRA DE DATOS (Opcional)
            with st.expander("Ver detalle de datos procesados"):
                st.dataframe(df_filtrado[['Fecha de Op', 'Cheque', 'Importe', 'Estado', 'Cuit Firmante', 'Den. Firmante']])

        except Exception as e:
            st.error(f"Ocurrió un error procesando el archivo: {e}")

if __name__ == "__main__":
    main()
