import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import datetime
import io
import unicodedata

# Función para normalizar cadenas (quitar acentos y pasar a minúsculas)
def normalize(text):
    if not isinstance(text, str):
        return ""
    nfkd_form = unicodedata.normalize('NFKD', text)
    return u"".join([c for c in nfkd_form if not unicodedata.combining(c)]).lower()

# Función para detectar columnas requeridas y opcionales en cada DataFrame
def detectar_columnas(df):
    # Diccionario con las palabras clave y el nombre de columna detectado
    columnas_detectadas = {
        "fecha": None,
        "region": None,
        "clics": None,
        "impresiones": None,
        "conversiones": None,
        "coste": None,
        "canal": None,       # opcional
        "campana": None,     # opcional (se busca "campaña" sin tilde)
        "leads": None        # opcional
    }
    for col in df.columns:
        col_norm = normalize(col)
        for key in columnas_detectadas.keys():
            if key in col_norm:
                columnas_detectadas[key] = col
    return columnas_detectadas

# Función para cargar archivos Excel (uno o varios) y combinar hojas en un único DataFrame
def cargar_datos(files):
    lista_df = []
    for file in files:
        # Se leen todas las hojas del Excel
        try:
            xls = pd.ExcelFile(file, engine='openpyxl')
        except Exception as e:
            st.error(f"Error al leer el archivo: {e}")
            continue
        for sheet in xls.sheet_names:
            try:
                df = pd.read_excel(xls, sheet_name=sheet)
                cols = detectar_columnas(df)
                # Verificamos que las columnas esenciales estén presentes
                if None in [cols["fecha"], cols["region"], cols["clics"], cols["impresiones"], cols["conversiones"], cols["coste"]]:
                    st.warning(f"En la hoja '{sheet}' del archivo '{file.name}' no se han detectado todas las columnas esenciales. Se omite.")
                    continue
                # Renombramos las columnas para homogeneizar el DataFrame
                df = df.rename(columns={
                    cols["fecha"]: "fecha",
                    cols["region"]: "region",
                    cols["clics"]: "clics",
                    cols["impresiones"]: "impresiones",
                    cols["conversiones"]: "conversiones",
                    cols["coste"]: "coste"
                })
                # Si existen columnas opcionales, se renombran
                if cols["canal"]:
                    df = df.rename(columns={cols["canal"]: "canal"})
                if cols["campana"]:
                    df = df.rename(columns={cols["campana"]: "campana"})
                if cols["leads"]:
                    df = df.rename(columns={cols["leads"]: "leads"})
                # Convertir la columna fecha a datetime
                df["fecha"] = pd.to_datetime(df["fecha"], errors='coerce')
                df = df.dropna(subset=["fecha"])
                # Cálculo de métricas
                df["CTR"] = np.where(df["impresiones"] > 0, (df["clics"] / df["impresiones"]) * 100, 0)
                df["Coste_por_conversion"] = np.where(df["conversiones"] > 0, df["coste"] / df["conversiones"], np.nan)
                # Agregar columnas para identificar el origen (archivo y hoja)
                df["origen_archivo"] = file.name
                df["origen_hoja"] = sheet
                lista_df.append(df)
            except Exception as e:
                st.error(f"Error procesando la hoja '{sheet}' del archivo '{file.name}': {e}")
    if lista_df:
        datos = pd.concat(lista_df, ignore_index=True)
        return datos
    else:
        return pd.DataFrame()

# Función para agrupar por frecuencia (día, semana, mes)
def agrupar_por_frecuencia(df, columna_fecha, frecuencia):
    if frecuencia == "Diario":
        freq = 'D'
    elif frecuencia == "Semanal":
        freq = 'W'
    elif frecuencia == "Mensual":
        freq = 'M'
    else:
        freq = 'D'
    df_group = df.set_index(columna_fecha).groupby(pd.Grouper(freq=freq)).sum().reset_index()
    return df_group

# Título y estilo general
st.set_page_config(page_title="Dashboard Marketing", layout="wide")
st.title("Dashboard de Resultados de Campañas")

# Subida de archivos Excel
st.sidebar.header("Carga de Archivos")
uploaded_files = st.sidebar.file_uploader("Sube uno o varios archivos Excel", type=["xlsx"], accept_multiple_files=True)

datos = pd.DataFrame()
if uploaded_files:
    datos = cargar_datos(uploaded_files)
    if datos.empty:
        st.warning("No se han cargado datos válidos.")
    else:
        st.success("Datos cargados correctamente.")
else:
    st.info("Sube archivos Excel para comenzar.")

if not datos.empty:
    # Filtros interactivos
    st.sidebar.header("Filtros")
    fecha_min = datos["fecha"].min().date()
    fecha_max = datos["fecha"].max().date()
    rango_fechas = st.sidebar.date_input("Rango de fechas", [fecha_min, fecha_max], min_value=fecha_min, max_value=fecha_max)
    if isinstance(rango_fechas, tuple) or isinstance(rango_fechas, list):
        inicio, fin = rango_fechas
    else:
        inicio = fin = rango_fechas

    # Filtro por Canal si existe
    if "canal" in datos.columns:
        canales = datos["canal"].dropna().unique().tolist()
        seleccion_canales = st.sidebar.multiselect("Canal", canales, default=canales)
    else:
        seleccion_canales = None

    # Filtro por Región
    regiones = datos["region"].dropna().unique().tolist()
    seleccion_regiones = st.sidebar.multiselect("Región", regiones, default=regiones)

    # Filtro por Campaña si existe
    if "campana" in datos.columns:
        campanas = datos["campana"].dropna().unique().tolist()
        seleccion_campanas = st.sidebar.multiselect("Campaña", campanas, default=campanas)
    else:
        seleccion_campanas = None

    # Aplicar filtros
    filtro = (datos["fecha"].dt.date >= inicio) & (datos["fecha"].dt.date <= fin) & (datos["region"].isin(seleccion_regiones))
    if seleccion_canales is not None:
        filtro &= datos["canal"].isin(seleccion_canales)
    if seleccion_campanas is not None:
        filtro &= datos["campana"].isin(seleccion_campanas)
    datos_filtrados = datos[filtro]

    if datos_filtrados.empty:
        st.warning("No hay datos para el rango y filtros seleccionados.")
    else:
        # Crear pestañas para organizar gráficos
        tabs = st.tabs([
            "Evolución Conversiones",
            "Evolución Coste",
            "Coste por Conversión",
            "CTR por Canal",
            "Conversión por Campaña",
            "Comparativa Regiones",
            "Rendimiento por Canal",
            "Leads por Región"
        ])

        # 1. Evolución de Conversiones
        with tabs[0]:
            st.subheader("Evolución de Conversiones")
            freq_sel = st.selectbox("Selecciona la frecuencia", ["Diario", "Semanal", "Mensual"], key="conv_freq")
            df_conv = agrupar_por_frecuencia(datos_filtrados, "fecha", freq_sel)
            if not df_conv.empty and "conversiones" in df_conv.columns:
                fig = px.line(df_conv, x="fecha", y="conversiones", title="Evolución de Conversiones")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No hay datos disponibles para este gráfico.")

        # 2. Evolución de Coste
        with tabs[1]:
            st.subheader("Evolución de Coste")
            freq_sel = st.selectbox("Selecciona la frecuencia", ["Diario", "Semanal", "Mensual"], key="cost_freq")
            df_cost = agrupar_por_frecuencia(datos_filtrados, "fecha", freq_sel)
            if not df_cost.empty and "coste" in df_cost.columns:
                fig = px.line(df_cost, x="fecha", y="coste", title="Evolución de Coste")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No hay datos disponibles para este gráfico.")

        # 3. Coste por Conversión total y su evolución
        with tabs[2]:
            st.subheader("Coste por Conversión")
            total_coste = datos_filtrados["coste"].sum()
            total_conversiones = datos_filtrados["conversiones"].sum()
            coste_conversion_total = total_coste / total_conversiones if total_conversiones > 0 else np.nan
            st.metric("Coste por Conversión Total", f"{coste_conversion_total:.2f}" if not np.isnan(coste_conversion_total) else "N/D")
            # Evolución temporal de coste por conversión
            df_temp = datos_filtrados.copy()
            df_temp = df_temp.sort_values("fecha")
            df_temp["Coste_por_conversion"] = np.where(df_temp["conversiones"] > 0, df_temp["coste"] / df_temp["conversiones"], np.nan)
            if not df_temp.empty:
                fig = px.line(df_temp, x="fecha", y="Coste_por_conversion", title="Evolución de Coste por Conversión")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No hay datos disponibles para este gráfico.")

        # 4. Distribución de CTR por Canal
        with tabs[3]:
            st.subheader("Distribución de CTR por Canal")
            if "canal" in datos_filtrados.columns:
                df_ctr = datos_filtrados.groupby("canal")["CTR"].mean().reset_index()
                fig = px.bar(df_ctr, x="canal", y="CTR", title="CTR Promedio por Canal")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No se detectó la columna 'canal' en los datos.")

        # 5. Conversión por Campaña
        with tabs[4]:
            st.subheader("Conversión por Campaña")
            if "campana" in datos_filtrados.columns:
                df_camp = datos_filtrados.groupby("campana")["conversiones"].sum().reset_index()
                fig = px.bar(df_camp, x="campana", y="conversiones", title="Conversiones por Campaña")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No se detectó la columna 'campana' en los datos.")

        # 6. Comparativa entre Regiones por Canal
        with tabs[5]:
            st.subheader("Comparativa entre Regiones por Canal")
            if "canal" in datos_filtrados.columns:
                df_comp = datos_filtrados.groupby(["region", "canal"])["conversiones"].sum().reset_index()
                fig = px.bar(df_comp, x="region", y="conversiones", color="canal", barmode="group", title="Conversiones por Región y Canal")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No se detectó la columna 'canal' para este gráfico.")

        # 7. Rendimiento por Canal
        with tabs[6]:
            st.subheader("Rendimiento por Canal")
            if "canal" in datos_filtrados.columns:
                df_rend = datos_filtrados.groupby("canal").agg({
                    "clics": "sum",
                    "impresiones": "sum",
                    "conversiones": "sum",
                    "coste": "sum"
                }).reset_index()
                df_rend["CTR"] = np.where(df_rend["impresiones"] > 0, (df_rend["clics"] / df_rend["impresiones"]) * 100, 0)
                fig = px.bar(df_rend, x="canal", y="CTR", title="CTR por Canal")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No se detectó la columna 'canal' en los datos.")

        # 8. Leads por Región
        with tabs[7]:
            st.subheader("Leads por Región")
            if "leads" in datos_filtrados.columns:
                df_leads = datos_filtrados.groupby("region")["leads"].sum().reset_index()
                fig = px.pie(df_leads, names="region", values="leads", title="Distribución de Leads por Región")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No se detectó la columna 'leads' en los datos.")
