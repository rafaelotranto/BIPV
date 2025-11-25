import pvlib
import pandas as pd

def calcular_geracao_pv(df_info_geral, df_elementos, eficiencia_painel, eficiencia_inversor, perdas_sistema):
    """
    Calcula a geração de energia fotovoltaica para uma lista de elementos (telhados ou janelas).

    Esta função é genérica e pode ser usada para qualquer superfície, desde que o DataFrame
    de entrada contenha as colunas necessárias.

    Args:
        df_info_geral (pd.DataFrame): DataFrame contendo 'Latitude' e 'Longitude'.
        df_elementos (pd.DataFrame): DataFrame com os dados dos elementos a serem calculados.
                                     Deve conter as colunas:
                                     - 'Área Bruta (m²)'
                                     - 'Inclinação (°)'
                                     - 'Orientação (Azimute °)'
        eficiencia_painel (float): Eficiência do módulo fotovoltaico (ex: 0.22 para 22%).
        eficiencia_inversor (float): Eficiência do inversor (ex: 0.96 para 96%).
        perdas_sistema (float): Perdas totais agregadas do sistema (ex: 0.14 para 14%).

    Returns:
        pd.DataFrame: O DataFrame original dos elementos com uma nova coluna
                      'Geração Anual Estimada (kWh)'.
    """
    # Cria uma cópia para não modificar o DataFrame original que está no Streamlit
    df_elementos = df_elementos.copy()

    # --- 1. Obtenção de Dados Geográficos e Climáticos ---
    latitude = float(df_info_geral.loc[0, "Latitude"])
    longitude = float(df_info_geral.loc[0, "Longitude"])
    altitude = 0.0

    # Garante uma chave única para o merge, caso o DataFrame não tenha um ID
    if "ElementoID" not in df_elementos.columns:
        df_elementos["ElementoID"] = range(1, len(df_elementos) + 1)

    # CORREÇÃO APLICADA AQUI:
    # A função get_pvgis_tmy retorna uma tupla. O primeiro elemento [0] é o DataFrame
    # com os dados meteorológicos que precisamos. A tentativa de desempacotar 4 valores
    # causava o erro, pois a função retorna menos que isso em algumas versões/chamadas.
    weather = pvlib.iotools.get_pvgis_tmy(latitude, longitude, map_variables=True)[0]
    weather.index.name = "utc_time"

    # --- 2. Cálculo da Posição Solar ---
    posicao_sol = pvlib.solarposition.get_solarposition(
        time=weather.index,
        latitude=latitude,
        longitude=longitude,
        altitude=altitude,
        temperature=weather["temp_air"],
        pressure=weather["pressure"],
    )

    # --- 3. Cálculo de Geração por Elemento ---
    resultados = []
    cols_req = ["ElementoID", "Área Bruta (m²)", "Inclinação (°)", "Orientação (Azimute °)"]
    elementos_para_calculo = df_elementos[cols_req].copy()

    for _, row in elementos_para_calculo.iterrows():
        area_total = float(row["Área Bruta (m²)"])
        tilt = float(row["Inclinação (°)"])
        azimuth = float(row["Orientação (Azimute °)"])

        # Calcula a irradiância total no plano do elemento (POA - Plane of Array)
        irr = pvlib.irradiance.get_total_irradiance(
            surface_tilt=tilt,
            surface_azimuth=azimuth,
            solar_zenith=posicao_sol["apparent_zenith"],
            solar_azimuth=posicao_sol["azimuth"],
            dni=weather["dni"],
            ghi=weather["ghi"],
            dhi=weather["dhi"],
        )
        irr_df = pd.DataFrame(irr)

        # Potência de pico dos módulos (kW) para uma irradiância padrão de 1000 W/m²
        potencia_paineis_kw = area_total * eficiencia_painel

        # Energia DC horária (kWh) = Irradiância (kW/m²) * Área (m²) * Eficiência
        energia_dc_kwh = (irr_df["poa_global"] / 1000.0) * potencia_paineis_kw

        # Energia AC (kWh) considerando eficiências do inversor e perdas do sistema
        energia_ac_kwh = energia_dc_kwh * eficiencia_inversor * (1.0 - perdas_sistema)

        # Adiciona o resultado anual total à lista
        resultados.append({
            "ElementoID": row["ElementoID"],
            "Geração Anual Estimada (kWh)": float(energia_ac_kwh.sum())
        })

    # --- 4. Consolidação dos Resultados ---
    df_resultados = pd.DataFrame(resultados)
    df_unidos = df_elementos.merge(df_resultados, how="left")

    df_unidos = df_unidos.drop(columns=["ElementoID"])

    return df_unidos