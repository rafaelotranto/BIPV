import streamlit as st
import pandas as pd
import ifcopenshell
import tempfile
import pvlib
import core  # mantém suas funções

st.set_page_config(page_title="BIPV IFC", page_icon="☀️", layout="wide")

# -------------------------
# SIDEBAR
# -------------------------
with st.sidebar:
    with st.container(border=False):
        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
            st.image("ime.png", width=100)

    uploaded_file = st.file_uploader("Selecione o arquivo IFC:", type=["ifc"])

    st.write("Apoie nosso trabalho com um PIX")
    st.image("Captura de tela 2025-08-19 113232.png")

# -------------------------
# TÍTULO
# -------------------------
st.title("BIM-BIPV")

# -------------------------
# FUNÇÃO DE CÁLCULO (SOMENTE CÁLCULO → RETORNA DADOS)
# -------------------------
def calcular_pvlib(df_info_geral, df_telhados, eficiencia_painel, eficiencia_inversor, perdas_sistema):
    # Cópia para evitar alterar original
    df_telhados = df_telhados.copy()

    # Latitude/Longitude
    latitude = float(df_info_geral.loc[0, "Latitude"])
    longitude = float(df_info_geral.loc[0, "Longitude"])
    altitude = 0.0

    # Chave estável (evita merge por float)
    if "TelhadoID" not in df_telhados.columns:
        df_telhados["TelhadoID"] = range(1, len(df_telhados) + 1)

    # Meteo TMY (PVGIS) — pode ser cacheado se quiser
    weather = pvlib.iotools.get_pvgis_tmy(latitude, longitude)[0]
    weather.index.name = "utc_time"

    # Posição solar
    posicao_sol = pvlib.solarposition.get_solarposition(
        time=weather.index,
        latitude=latitude,
        longitude=longitude,
        altitude=altitude,
        temperature=weather["temp_air"],
        pressure=weather["pressure"],
    )

    # Cálculo por telhado
    resultados = []
    cols_req = ["TelhadoID", "Área Bruta (m²)", "Inclinação (°)", "Orientação (Azimute °)"]
    telhados = df_telhados[cols_req].copy()

    for _, row in telhados.iterrows():
        area_total = float(row["Área Bruta (m²)"])
        tilt = float(row["Inclinação (°)"])
        azm = float(row["Orientação (Azimute °)"])

        irr = pvlib.irradiance.get_total_irradiance(
            surface_tilt=tilt,
            surface_azimuth=azm,
            solar_zenith=posicao_sol["apparent_zenith"],
            solar_azimuth=posicao_sol["azimuth"],
            dni=weather["dni"],
            ghi=weather["ghi"],
            dhi=weather["dhi"],
        )
        irr_df = pd.DataFrame(irr)

        # Potência equivalente dos módulos (kW para POA=1000 W/m²)
        potencia_paineis_kw = area_total * eficiencia_painel

        # Energia DC horária (kWh)
        energia_dc_kwh = (irr_df["poa_global"] / 1000.0) * potencia_paineis_kw

        # Energia AC (kWh) com perdas
        energia_ac_kwh = energia_dc_kwh * eficiencia_inversor * (1.0 - perdas_sistema)

        resultados.append({
            "TelhadoID": row["TelhadoID"],
            "Geração Anual Estimada (kWh)": float(energia_ac_kwh.sum())
        })

    df_res = pd.DataFrame(resultados)
    df_unidos = df_telhados.merge(df_res, on="TelhadoID", how="left")
    return df_unidos

# -------------------------
# FLUXO PRINCIPAL
# -------------------------
if uploaded_file:
    st.success("Arquivo carregado com sucesso!")

    # Salva temporário e abre
    with tempfile.NamedTemporaryFile(delete=False, suffix=".ifc") as tmp:
        tmp.write(uploaded_file.getbuffer())
        tmp_path = tmp.name
    ifc_file = ifcopenshell.open(tmp_path)

    # Extrai dados
    info_geral = core.extrair_info_geografica(ifc_file)
    df_info_geral = pd.DataFrame(info_geral)

    norte_vetor_principal = core.find_true_north(ifc_file)

    dados_paredes = core.extrair_dados_paredes(ifc_file, norte_vetor_principal)
    df_paredes = pd.DataFrame(dados_paredes)

    dados_janelas = core.extrair_dados_janelas(ifc_file, norte_vetor_principal)
    df_janelas = pd.DataFrame(dados_janelas)

    dados_telhados = core.extrair_dados_telhados(ifc_file, norte_vetor_principal)
    df_telhados = pd.DataFrame(dados_telhados)

    # --- INFORMAÇÕES GERAIS ---
    st.header("Informações Gerais")
    st.dataframe(df_info_geral, use_container_width=True)

    # Mapa (só converte para string aqui)
    lat_str = str(df_info_geral.loc[0, "Latitude"])
    lon_str = str(df_info_geral.loc[0, "Longitude"])
    map_url = f"https://www.google.com/maps?q={lat_str},{lon_str}&hl=pt&z=16&t=k&output=embed"

    st.markdown(
        f"""
        <iframe
          src="{map_url}"
          width="100%"
          height="500"
          style="border:0;"
          loading="lazy"
          referrerpolicy="no-referrer-when-downgrade"></iframe>
        """,
        unsafe_allow_html=True
    )

    # --- TELHADOS ---
    st.header("Dados Telhados")
    st.dataframe(df_telhados, use_container_width=True)

    # Parâmetros do sistema
    with st.expander("Parâmetros do Sistema (ajuste conforme necessário)", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            eficiencia_painel = st.number_input(
                "Eficiência do Painel (0–1)", min_value=0.0, max_value=1.0, value=0.22, step=0.01,
                help="Ex.: 0.22 = 22%"
            )
        with col2:
            eficiencia_inversor = st.number_input(
                "Eficiência do Inversor (0–1)", min_value=0.0, max_value=1.0, value=0.96, step=0.01
            )
        with col3:
            perdas_sistema = st.number_input(
                "Perdas do Sistema (0–1)", min_value=0.0, max_value=1.0, value=0.14, step=0.01,
                help="Perdas agregadas: cabos, sujeira, mismatch, temperatura etc."
            )

    # --------- BOTÃO ---------
    # O cálculo é feito no clique e os dados ficam no session_state
    if st.button("Calcular"):
        with st.spinner("Calculando geração com PVLib..."):
            st.session_state["df_unidos"] = calcular_pvlib(
                df_info_geral=df_info_geral,
                df_telhados=df_telhados,
                eficiencia_painel=eficiencia_painel,
                eficiencia_inversor=eficiencia_inversor,
                perdas_sistema=perdas_sistema
            )

    # -------------------------
    # PLACEHOLDER POSICIONADO *AQUI* (DEPOIS DO BOTÃO E DAS SEÇÕES)
    # -------------------------
    resultados_box = st.container()

    # Renderização ANCORADA no placeholder
    with resultados_box:
        if "df_unidos" in st.session_state:
            st.image("pvlib.png", width=900, output_format="auto")
            st.subheader("Resultados — Geração Estimada")
            st.dataframe(st.session_state["df_unidos"], use_container_width=True)

            st.subheader("Dados Janelas Externas")
            st.write(f"Quantidade: {len(df_janelas)} janelas.")
            st.dataframe(df_janelas, use_container_width=True)

            st.subheader("Dados Paredes Externas")
            st.write(f"Quantidade: {len(df_paredes)} paredes.")
            st.dataframe(df_paredes, use_container_width=True)

else:
    st.info("Carregue um arquivo IFC para iniciar.")




