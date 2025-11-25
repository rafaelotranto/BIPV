import streamlit as st
import pandas as pd
import ifcopenshell
import tempfile
import pvlib
import core  # mantém suas funções
import calculopvlib
#from utils import icon_text


st.set_page_config(page_title="BIPV IFC", page_icon="☀️", layout="wide")

# --- Inicialização do session_state para armazenar os resultados ---
if "df_telhados_resultados" not in st.session_state:
    st.session_state["df_telhados_resultados"] = None
if "df_janelas_resultados" not in st.session_state:
    st.session_state["df_janelas_resultados"] = None
if "df_paredes_resultados" not in st.session_state:
    st.session_state["df_paredes_resultados"] = None

# -------------------------
# SIDEBAR
# -------------------------
with st.sidebar:
    with st.container(border=False):
        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
            st.image("ime.png", width=100)

    uploaded_file = st.file_uploader("Selecione o arquivo .ifc:", type=["ifc"])
    
    with st.container(border=False):
        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
            st.image("ifc.logo.png", width=100)
            st.write("IFC")
            st.image("ifc_openshell.png", width=100)
            st.write("IFC Openshell")
            st.image("pvlib_logo.png", width=100)
            st.write("PVLIB")


# -------------------------
# TÍTULO
# -------------------------
st.title("BIM-BIPV")


# -------------------------
# FLUXO PRINCIPAL
# -------------------------
if uploaded_file:
    st.success("Arquivo IFC carregado com sucesso!")

    # Salva o arquivo temporariamente para leitura pelo ifcopenshell
    with tempfile.NamedTemporaryFile(delete=False, suffix=".ifc") as tmp:
        tmp.write(uploaded_file.getbuffer())
        tmp_path = tmp.name
    ifc_file = ifcopenshell.open(tmp_path)

    # --- Extração de Dados do IFC ---
    with st.spinner("Extraindo dados do modelo BIM..."):
        info_geral = core.extrair_info_geografica(ifc_file)
        df_info_geral = pd.DataFrame(info_geral)

        norte_vetor_principal = core.find_true_leste(ifc_file)

        dados_paredes = core.extrair_dados_paredes(ifc_file, norte_vetor_principal)
        df_paredes = pd.DataFrame(dados_paredes)

        dados_janelas = core.extrair_dados_janelas(ifc_file, norte_vetor_principal)
        df_janelas = pd.DataFrame(dados_janelas)

        dados_telhados = core.extrair_dados_telhados(ifc_file, norte_vetor_principal)
        df_telhados = pd.DataFrame(dados_telhados)

    # --- SEÇÃO DE INFORMAÇÕES GERAIS ---
    st.header("Informações Gerais do Projeto")
    st.dataframe(df_info_geral.drop(columns=['Vetor Norte Verdadeiro']), use_container_width=True)

    # --- SEÇÃO DE TELHADOS ---
    st.header("Potencial Fotovoltaico - Telhados")
    if not df_telhados.empty:
        st.dataframe(df_telhados, use_container_width=True)
        with st.expander("Parâmetros do Sistema Fotovoltaico (Telhados)", expanded=True):
            col1, col2, col3 = st.columns(3)
            with col1:
                ef_painel_t = st.number_input("Eficiência do Painel (0–1)", 0.0, 1.0, 0.22, 0.01, key="painel_t")
            with col2:
                ef_inversor_t = st.number_input("Eficiência do Inversor (0–1)", 0.0, 1.0, 0.96, 0.01, key="inversor_t")
            with col3:
                perdas_t = st.number_input("Perdas do Sistema (0–1)", 0.0, 1.0, 0.14, 0.01, key="perdas_t")

        if st.button("Calcular Geração dos Telhados", icon="☀️"):
            with st.spinner("Calculando geração com PVLib para os telhados..."):
                st.session_state["df_telhados_resultados"] = calculopvlib.calcular_geracao_pv(
                    df_info_geral, df_telhados, ef_painel_t, ef_inversor_t, perdas_t
                )
    else:
        st.warning("Nenhum telhado encontrado no arquivo IFC.")

    if st.session_state["df_telhados_resultados"] is not None:
        st.subheader("Resultados — Geração Estimada (Telhados) ")
        df_final_t = st.session_state["df_telhados_resultados"]
        st.dataframe(df_final_t, use_container_width=True)
        st.success(f"Geração Anual Total (Telhados): {df_final_t['Geração Anual Estimada (kWh)'].sum():,.2f} kWh")

    # --- SEÇÃO DE JANELAS ---
    st.header("Potencial Fotovoltaico - Janelas")
    if not df_janelas.empty:
        st.dataframe(df_janelas, use_container_width=True)
        with st.expander("Parâmetros do Sistema Fotovoltaico (Janelas)", expanded=True):
            col1j, col2j, col3j = st.columns(3)
            with col1j:
                ef_painel_j = st.number_input("Eficiência do Painel (0–1)", 0.0, 1.0, 0.18, 0.01, key="painel_j", help="A eficiência de painéis para fachadas (vidros fotovoltaicos) pode ser diferente.")
            with col2j:
                ef_inversor_j = st.number_input("Eficiência do Inversor (0–1)", 0.0, 1.0, 0.96, 0.01, key="inversor_j")
            with col3j:
                perdas_j = st.number_input("Perdas do Sistema (0–1)", 0.0, 1.0, 0.15, 0.01, key="perdas_j")

        if st.button("Calcular Geração das Janelas"):
            df_janelas_pv = df_janelas.copy()
            df_janelas_pv['Inclinação (°)'] = 90.0
            df_janelas_pv.rename(columns={'Área (m²)': 'Área Bruta (m²)'}, inplace=True)
            
            with st.spinner("Calculando geração com PVLib para as janelas..."):
                st.session_state["df_janelas_resultados"] = calculopvlib.calcular_geracao_pv(
                    df_info_geral, df_janelas_pv, ef_painel_j, ef_inversor_j, perdas_j
                )
    else:
        st.warning("Nenhuma janela encontrada no arquivo IFC.")

    if st.session_state["df_janelas_resultados"] is not None:
        st.subheader("🪟 Resultados — Geração Estimada (Janelas)")
        df_final_j = st.session_state["df_janelas_resultados"]
        st.dataframe(df_final_j, use_container_width=True)
        st.success(f"Geração Anual Total (Janelas): {df_final_j['Geração Anual Estimada (kWh)'].sum():,.2f} kWh")

    # --- NOVA SEÇÃO DE PAREDES ---
    st.header("Potencial Fotovoltaico - Paredes")
    if not df_paredes.empty:
        # Usamos a área líquida para as paredes, pois as aberturas não geram energia
        df_paredes_pv = df_paredes[['ID', 'Nome', 'Orientação (Azimute °)', 'Área Líquida (m²)']].copy()
        df_paredes_pv.rename(columns={'Área Líquida (m²)': 'Área Bruta (m²)'}, inplace=True)
        st.dataframe(df_paredes_pv, use_container_width=True)

        with st.expander("Parâmetros do Sistema Fotovoltaico (Paredes)", expanded=True):
            col1p, col2p, col3p = st.columns(3)
            with col1p:
                ef_painel_p = st.number_input("Eficiência do Painel (0–1)", 0.0, 1.0, 0.15, 0.01, key="painel_p", help="A eficiência de sistemas BIPV para paredes pode variar.")
            with col2p:
                ef_inversor_p = st.number_input("Eficiência do Inversor (0–1)", 0.0, 1.0, 0.96, 0.01, key="inversor_p")
            with col3p:
                perdas_p = st.number_input("Perdas do Sistema (0–1)", 0.0, 1.0, 0.16, 0.01, key="perdas_p")

        if st.button("Calcular Geração das Paredes"):
            df_paredes_pv['Inclinação (°)'] = 90.0
            
            with st.spinner("Calculando geração com PVLib para as paredes..."):
                st.session_state["df_paredes_resultados"] = calculopvlib.calcular_geracao_pv(
                    df_info_geral, df_paredes_pv, ef_painel_p, ef_inversor_p, perdas_p
                )
    else:
        st.warning("Nenhuma parede externa encontrada no arquivo IFC.")

    if st.session_state["df_paredes_resultados"] is not None:
        st.subheader("🧱 Resultados — Geração Estimada (Paredes)")
        df_final_p = st.session_state["df_paredes_resultados"]
        st.dataframe(df_final_p, use_container_width=True)
        st.success(f"Geração Anual Total (Paredes): {df_final_p['Geração Anual Estimada (kWh)'].sum():,.2f} kWh")


else:
    st.info("Aguardando o carregamento de um arquivo IFC para iniciar a análise.")
    st.warning("Verifique seu arquico .ifc com IDS antes de carregá-lo!")
    with open("IDS-BIPV.ids","rb") as file:
        st.download_button(label="Baixe aqui o IDS", data=file, file_name="IDS-BIPV.ids")
        col1, col2, col3 = st.columns([1, 3, 1])
    with col2:
        

        st.image("zero_energy.png", width=700,)

