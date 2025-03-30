import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.io as pio
from io import BytesIO
from fpdf import FPDF
from PIL import Image
import tempfile
import numpy as np

st.set_page_config(page_title="Marketing Insights Dashboard", layout="wide")
st.title("\U0001F4C8 Marketing Insights Dashboard")
st.write("Sube archivos Excel de campañas (Google Ads, Meta Ads, Mailchimp) para visualizar métricas clave.")

uploaded_files = st.file_uploader("Archivos Excel", type=["xlsx"], accept_multiple_files=True)

if uploaded_files:
    all_data = []
    for uploaded_file in uploaded_files:
        xls = pd.ExcelFile(uploaded_file)
        for sheet in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet)
            df["Fuente"] = sheet
            all_data.append(df)

    df = pd.concat(all_data, ignore_index=True)

    # Cálculos y formatos
    df["CTR (%)"] = round(df["Clics"] / df["Impresiones"] * 100, 2)
    df["Coste por conversión (€)"] = round(df["Coste (€)"] / df["Conversiones"], 2)
    df["Fecha"] = pd.to_datetime(df["Fecha"])

    # Filtros interactivos
    st.sidebar.header("✨ Filtros")
    canales = df["Fuente"].unique().tolist()
    regiones = df["Región"].unique().tolist()
    campañas = df["Campaña"].unique().tolist()
    fecha_min, fecha_max = df["Fecha"].min(), df["Fecha"].max()

    canales_sel = st.sidebar.multiselect("Canales", canales, default=canales)
    regiones_sel = st.sidebar.multiselect("Regiones", regiones, default=regiones)
    campañas_sel = st.sidebar.multiselect("Campañas", campañas, default=campañas)
    rango_fechas = st.sidebar.date_input("Rango de fechas", [fecha_min, fecha_max])

    # Colores personalizados por fuente
    st.sidebar.header("🎨 Colores por fuente")
    colores_fuente = {}
    for canal in canales:
        colores_fuente[canal] = st.sidebar.color_picker(f"Color para {canal}", key=canal)

    df = df[
        (df["Fuente"].isin(canales_sel)) &
        (df["Región"].isin(regiones_sel)) &
        (df["Campaña"].isin(campañas_sel)) &
        (df["Fecha"] >= pd.to_datetime(rango_fechas[0])) &
        (df["Fecha"] <= pd.to_datetime(rango_fechas[1]))
    ]

    df["Semana"] = df["Fecha"].dt.isocalendar().week
    df["Mes"] = df["Fecha"].dt.strftime("%Y-%m")

    imagenes_para_pdf = {}

    def mostrar_y_descargar(fig, nombre_archivo, ancho=True):
        st.plotly_chart(fig, use_container_width=ancho)
        buffer = BytesIO()
        pio.write_image(fig, buffer, format="png")
        imagenes_para_pdf[nombre_archivo] = buffer.getvalue()
        st.download_button("📅 Descargar PNG", data=buffer.getvalue(), file_name=f"{nombre_archivo}.png", mime="image/png")

    st.subheader("📆 Evolución semanal de conversiones")
    semana_conv = df.groupby(["Semana", "Fuente"])["Conversiones"].sum().reset_index()
    fig2 = px.line(semana_conv, x="Semana", y="Conversiones", color="Fuente", markers=True, color_discrete_map=colores_fuente)
    mostrar_y_descargar(fig2, "conversiones_semanales")

    st.subheader("📆 Evolución mensual de coste")
    mes_coste = df.groupby(["Mes", "Fuente"])["Coste (€)"].sum().reset_index()
    fig3 = px.bar(mes_coste, x="Mes", y="Coste (€)", color="Fuente", barmode="group", color_discrete_map=colores_fuente)
    mostrar_y_descargar(fig3, "coste_mensual")

    st.subheader("📊 Rendimiento por canal")
    total_conv = df.groupby("Fuente")[["Conversiones"]].sum().reset_index()
    fig4 = px.bar(total_conv, x="Fuente", y="Conversiones", color="Fuente", color_discrete_map=colores_fuente)
    mostrar_y_descargar(fig4, "conversiones_por_canal")

    st.subheader("💰 Coste por conversión")
    avg_cost = df.groupby("Fuente")[["Coste por conversión (€)"]].mean().reset_index()
    fig5 = px.bar(avg_cost, x="Fuente", y="Coste por conversión (€)", color="Fuente", color_discrete_map=colores_fuente)
    mostrar_y_descargar(fig5, "coste_por_conversion")

    st.subheader("📑 Conversiones por campaña")
    camp_conv = df.groupby("Campaña")["Conversiones"].sum().reset_index()
    fig6 = px.bar(camp_conv, x="Campaña", y="Conversiones", color="Campaña")
    mostrar_y_descargar(fig6, "conversiones_por_campana")

    st.subheader("🌍 Conversiones por región y canal")
    region_canal = df.groupby(["Región", "Fuente"])["Conversiones"].sum().reset_index()
    fig7 = px.bar(region_canal, x="Región", y="Conversiones", color="Fuente", barmode="group", color_discrete_map=colores_fuente)
    mostrar_y_descargar(fig7, "conversiones_por_region")

    st.subheader("🗺️ Mapa de conversiones por región (aproximación)")
    regiones_coords = {
        "Norte": {"lat": 43.3, "lon": -3.8},
        "Sur": {"lat": 37.4, "lon": -5.9},
        "Este": {"lat": 39.5, "lon": -0.4},
        "Oeste": {"lat": 40.0, "lon": -6.0},
        "Centro": {"lat": 40.4, "lon": -3.7}
    }
    df_mapa = df.groupby("Región")["Conversiones"].sum().reset_index()
    df_mapa["lat"] = df_mapa["Región"].map(lambda x: regiones_coords[x]["lat"])
    df_mapa["lon"] = df_mapa["Región"].map(lambda x: regiones_coords[x]["lon"])

    fig_mapa = px.scatter_mapbox(
        df_mapa,
        lat="lat",
        lon="lon",
        size="Conversiones",
        hover_name="Región",
        zoom=5,
        height=500,
        mapbox_style="carto-positron"
    )
    st.plotly_chart(fig_mapa, use_container_width=True)

    st.subheader("📉 Distribución de CTR por canal")
    fig8 = px.box(df, x="Fuente", y="CTR (%)", points="all", color="Fuente", color_discrete_map=colores_fuente)
    mostrar_y_descargar(fig8, "distribucion_ctr")

    st.markdown("---")
    st.subheader("📄 Vista previa de los datos filtrados")

    # Selección de columna para ordenamiento
    columnas_orden = df.columns.tolist()
    col_orden = st.selectbox("Ordenar por columna:", columnas_orden, index=columnas_orden.index("Fecha"))
    ascendente = st.radio("Dirección de orden:", ["Ascendente", "Descendente"]) == "Ascendente"

    datos_ordenados = df.sort_values(by=col_orden, ascending=ascendente)
    st.dataframe(datos_ordenados, use_container_width=True, height=500)

    # Exportar Excel de datos ordenados
    excel_buffer = BytesIO()
    datos_ordenados.to_excel(excel_buffer, index=False)
    st.download_button("📤 Descargar vista actual (Excel)", data=excel_buffer.getvalue(), file_name="vista_filtrada.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # Exportar PDF con todos los gráficos
    if st.button("📄 Descargar todos los gráficos en PDF"):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmpfile:
            pdf = FPDF()
            for nombre, imagen_bytes in imagenes_para_pdf.items():
                with tempfile.NamedTemporaryFile(suffix=".png") as img_tmp:
                    img_tmp.write(imagen_bytes)
                    img_tmp.flush()
                    img = Image.open(img_tmp.name)
                    img_path = img_tmp.name
                    pdf.add_page()
                    pdf.image(img_path, x=10, y=20, w=180)
                    pdf.set_font("Arial", size=12)
                    pdf.ln(10)
                    pdf.cell(200, 10, nombre.replace("_", " ").title(), ln=True)
            pdf.output(tmpfile.name)
            tmpfile.seek(0)
            st.download_button("📄 Descargar PDF de gráficos", data=tmpfile.read(), file_name="report_graficos_marketing.pdf", mime="application/pdf")

else:
    st.info("Sube al menos un archivo Excel para comenzar.")
