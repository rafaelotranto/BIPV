import streamlit as st
import core
import pandas as pd
import numpy as np
import ifcopenshell
import tempfile
import base64
import streamlit.components.v1 as components
import pvlib


st.set_page_config(page_title="BIPV IFC",
                   page_icon = "☀️",
                   layout="wide")

with st.sidebar:
    with st.container(border=False):
        col_esq, col_centro, col_dir = st.columns([1, 2, 1])
        with col_centro:
            st.image("ime.png", width=100)

    uploaded_file = st.file_uploader("Selecione o arquivo IFC:", type=["ifc"])

    st.write("Apoie nosso trabalho com um PIX")
    st.image("Captura de tela 2025-08-19 113232.png")

st.title("BIM-BIPV")

if uploaded_file:
    st.success("Arquivo carregado com sucesso!")
    with tempfile.NamedTemporaryFile(delete=False, suffix=".ifc") as tmp:
        tmp.write(uploaded_file.getbuffer())  # salva conteúdo no temp
        tmp_path = tmp.name  # caminho do arquivo temporário

    # agora abre com o ifcopenshell
    ifc_file = ifcopenshell.open(tmp_path)


    info_geral = core.extrair_info_geografica(ifc_file)
    norte_vetor_principal = core.find_true_north(ifc_file)

    df_info_geral = pd.DataFrame(info_geral)


    dados_paredes = core.extrair_dados_paredes(ifc_file, norte_vetor_principal)
    df_paredes = pd.DataFrame(dados_paredes)

    dados_janelas = core.extrair_dados_janelas(ifc_file, norte_vetor_principal)
    df_janelas = pd.DataFrame(dados_janelas)


    dados_telhados = core.extrair_dados_telhados(ifc_file, norte_vetor_principal)
    df_telhados = pd.DataFrame(dados_telhados)

    st.header("Informações Gerais:")
    st.dataframe(df_info_geral, use_container_width=True)


    latitude = str(info_geral[0]['Latitude'])
    longitude = str(info_geral[0]['Longitude'])

    # Monta o link do Google Maps com as coordenadas
    map_url = f"https://www.google.com/maps?q={latitude},{longitude}&hl=pt&z=16&t=k&output=embed"


    # Exibe o mapa no Streamlit
    st.markdown(
        f"""
        <iframe
        src="{map_url}"
        width="100%"
        height="500"
        style="border:0;"
        allowfullscreen=""
        loading="lazy"
        ></iframe>
        """,
        unsafe_allow_html=True
    )

    st.header("Dados Telhados:")    
    st.dataframe(df_telhados)

    
   
   #CALCULO PVLIB

    dados = core.extrair_info_geografica(ifc_file)
    dados_df = pd.DataFrame(dados)
    latitude = dados[0]['Latitude']
    longitude = dados[0]['Longitude']

    norte_vetor_principal = core.find_true_north(ifc_file)
    

    dados_telhado = core.extrair_dados_telhados(ifc_file, norte_vetor_principal)
    dados_telhado_df = pd.DataFrame(dados_telhado)
    altitude = 0
    coordinates = [(latitude, longitude, "Rio de Janeiro", altitude,'Etc/GMT-3')]

    dados_tmy = []

    for location in coordinates:
        latitude, longitude, name, altitude, timezone = location

    weather = pvlib.iotools.get_pvgis_tmy(latitude, longitude)[0]
    weather.index.name = "utc_time"
    dados_tmy.append(weather)

    posicao_sol = pvlib.solarposition.get_solarposition(
        time=weather.index,
        latitude=latitude,
        longitude=longitude,
        altitude=altitude,
        temperature=weather["temp_air"],
        pressure=weather["pressure"],)
    # 2. Parâmetros do sistema fotovoltaico
    area_total_paineis = [area for area in dados_telhado_df['Área Bruta (m²)']] # em metros quadrados
    inclinacao = [inclinacao for inclinacao in dados_telhado_df['Inclinação (°)']]       # inclinação dos painéis em graus
    azimuth = [azimuth for azimuth in dados_telhado_df['Orientação (Azimute °)']]         # Orientação (180 graus = norte no hemisfério sul)

    lista_paramentos = zip(area_total_paineis, inclinacao, azimuth)

    # 3. Eficiência e Perdas
    eficiencia_painel = 0.22  # 20% de eficiência do módulo
    eficiencia_inversor = 0.96 # 96% de eficiência do inversor
    perdas_sistema = 0.09     # 14% de perdas totais (sujeira, cabos, temperatura, etc.)

    lista_geracoes_telhados = []

    for item in lista_paramentos:
        area_total_paineis, inclinacao, azimuth = item

        irradiacao_plano_inclinado = pvlib.irradiance.get_total_irradiance(
            surface_tilt=inclinacao,
            surface_azimuth=azimuth,
            solar_zenith=posicao_sol['apparent_zenith'],
            solar_azimuth=posicao_sol['azimuth'],
            dni=dados_tmy[0]['dni'],
            ghi=dados_tmy[0]['ghi'],
            dhi=dados_tmy[0]['dhi']
            )
        # Converter a irradiação para um DataFrame do pandas
        irradiacao_df = pd.DataFrame(irradiacao_plano_inclinado)

        # Calcular a potência de saída CC (Corrente Contínua) do sistema
        # A potência do painel é a área x eficiência
        potencia_paineis = area_total_paineis * eficiencia_painel

        # A energia CC é a irradiação (em W/m²) x potência dos painéis
        # Dividimos por 1000 para converter de W para kW
        energia_dc = (irradiacao_df['poa_global'] / 1000) * potencia_paineis

        # Calcular a energia de saída CA (Corrente Alternada), considerando as perdas
        energia_ac = energia_dc * eficiencia_inversor * (1 - perdas_sistema)

        # Calcular a geração anual total somando a energia de cada hora
        geracao_anual_kwh = energia_ac.sum()

        lista_geracoes_telhados.append({'Área dos Painéis':area_total_paineis, 'Inclinação':inclinacao, 'Orientação: Norte': azimuth, 'Geração Anual Estimada':geracao_anual_kwh})

    lista_geracoes_telhados_df = pd.DataFrame(lista_geracoes_telhados)
    lista_geracoes_telhados_df_renomeado = lista_geracoes_telhados_df.rename(columns={'Orientação: Norte': 'Orientação (Azimute °)'})

    df_unidos = pd.merge(
    dados_telhado_df,
    lista_geracoes_telhados_df_renomeado[['Orientação (Azimute °)', 'Geração Anual Estimada']],
    on='Orientação (Azimute °)')

    # col1, col2, col3 = st.columns(3)
    # with col1:
    #     st.image('pvlib_logo_horiz.webp', width=300)
    # with col2:
    #     st.header("Cálculo por meio do PVLIB")
    
    with st.container(horizontal_alignment="center", horizontal=True):
        st.image("pvlib.png", width=900, output_format="auto")
    st.dataframe(df_unidos)

    st.header(f"Dados Janelas Externas:")    
    st.write(f"Quantidade: {len(dados_janelas)} janelas.")
    st.dataframe(df_janelas, use_container_width=True)
    
    
    st.header("Dados Paredes Externas:")    
    st.write(f"Quantidade: {len(dados_paredes)} paredes.")
    st.dataframe(df_paredes, use_container_width=True)

