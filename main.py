import streamlit as st
import core
import pandas as pd
import ifcopenshell
import tempfile

st.title(" IME_GET_DATA_IFC")

uploaded_file = st.file_uploader(label="Selecione o arquivo IFC:", type=["ifc"])


if uploaded_file:
    st.balloons()
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
    st.dataframe(df_info_geral)

    st.header(f"Dados Janelas Externas:")    
    st.write(f"Quantidade: {len(dados_janelas)} janelas.")
    st.dataframe(df_janelas)
    
    
    st.header("Dados Paredes Externas:")    
    st.write(f"Quantidade: {len(dados_paredes)} paredes.")
    st.dataframe(df_paredes)
    
    
    st.header("Dados Telhados:")    
    st.dataframe(df_telhados)