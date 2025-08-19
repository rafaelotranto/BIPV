import streamlit as st
import core
import pandas as pd
import ifcopenshell
import tempfile
import base64
import streamlit.components.v1 as components

st.set_page_config(page_title="BIPV IFC",
                   page_icon = "☀️",
                   layout="wide")

with st.sidebar:

    with st.container(horizontal=True ,horizontal_alignment="center"):
        st.image(image="ime.png", width=100)
    
    uploaded_file = st.file_uploader(label="Selecione o arquivo IFC:", type=["ifc"])

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

    st.header(f"Dados Janelas Externas:")    
    st.write(f"Quantidade: {len(dados_janelas)} janelas.")
    st.dataframe(df_janelas, use_container_width=True)
    
    
    st.header("Dados Paredes Externas:")    
    st.write(f"Quantidade: {len(dados_paredes)} paredes.")
    st.dataframe(df_paredes, use_container_width=True)
    
   