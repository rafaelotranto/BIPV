import ifcopenshell
import ifcopenshell.geom
import numpy as np
import math
import pandas as pd

# --- Configurações Iniciais ---
# Substitua pelo caminho do seu arquivo IFC

# Nome do arquivo de saída da planilha
# EXCEL_OUTPUT_PATH = "Relatorio_Analise_IFC2.xlsx"

# Configurações de geometria do ifcopenshell
SETTINGS = ifcopenshell.geom.settings()
SETTINGS.set(SETTINGS.USE_WORLD_COORDS, True)
SETTINGS.set(SETTINGS.WELD_VERTICES, True)

# ------------------------------------------------------------------------------
# Funções Auxiliares (Otimizadas e Centralizadas)
# ------------------------------------------------------------------------------

def converter_angulo_para_decimal(angulo_ifc):
    if not isinstance(angulo_ifc, (list, tuple)) or len(angulo_ifc) < 3:
        return None
    try:
        D, M, S = float(angulo_ifc[0]), float(angulo_ifc[1]), float(angulo_ifc[2])
        uS = float(angulo_ifc[3]) if len(angulo_ifc) > 3 else 0.0
        sinal = -1.0 if D < 0 or M < 0 or S < 0 else 1.0
        graus_decimais = abs(D) + abs(M)/60.0 + (abs(S) + abs(uS)/1000000.0)/3600.0
        return sinal * graus_decimais
    except (ValueError, TypeError):
        return None

def find_true_north(ifc_file):
    map_conversions = ifc_file.by_type("IfcMapConversion")
    if map_conversions:
        mc = map_conversions[0]
        if hasattr(mc, "XAxisAbscissa") and hasattr(mc, "XAxisOrdinate"):
            x, y = mc.XAxisAbscissa, mc.XAxisOrdinate
            if x is not None and y is not None: return (x, y)

    contexts = ifc_file.by_type('IfcGeometricRepresentationContext')
    for context in contexts:
        if hasattr(context, 'TrueNorth') and context.TrueNorth and context.TrueNorth.is_a('IfcDirection'):
            ratios = context.TrueNorth.DirectionRatios
            if len(ratios) >= 2: return (ratios[0], ratios[1])

    print("AVISO: Norte Verdadeiro não encontrado. Usando Norte padrão (0, 1).")
    return (0.0, 1.0)

def calcular_angulo_vetor_graus(vetor):
    return math.degrees(math.atan2(vetor[1], vetor[0]))

def vector_to_angle_vs_north(vector, true_north_vector):
    vec_2d = np.array([vector[0], vector[1]])
    north_2d = np.array(true_north_vector)
    if np.linalg.norm(vec_2d) < 1e-6: return None
    norm_vec = vec_2d / np.linalg.norm(vec_2d)
    norm_north = north_2d / np.linalg.norm(north_2d)
    angle_rad = math.atan2(norm_vec[0], norm_vec[1]) - math.atan2(norm_north[0], norm_north[1])
    angle_deg = math.degrees(angle_rad)
    return (angle_deg + 360) % 360

# --- FUNÇÃO RE-ADICIONADA ---
def get_orientation_from_normal(normal_vector, true_north):
    """Calcula o azimute de uma face em relação ao Norte Verdadeiro."""
    proj_xy = (normal_vector[0], normal_vector[1])
    mag = math.sqrt(proj_xy[0]**2 + proj_xy[1]**2)
    if mag == 0:
        return None

    proj_unit = (proj_xy[0]/mag, proj_xy[1]/mag)
    # Produto escalar para encontrar o ângulo
    dot = max(min(proj_unit[0]*true_north[0] + proj_unit[1]*true_north[1], 1.0), -1.0)
    ang_rad = math.acos(dot)
    ang_deg = math.degrees(ang_rad)

    # Produto vetorial (cruzado) para determinar o quadrante
    cross = proj_unit[0]*true_north[1] - proj_unit[1]*true_north[0]
    if cross < 0:
        ang_deg = 360 - ang_deg

    return ang_deg

def get_element_orientation_from_mesh(element):
    try:
        shape = ifcopenshell.geom.create_shape(SETTINGS, element)
        verts = np.array(shape.geometry.verts).reshape((-1, 3))
        faces = np.array(shape.geometry.faces).reshape((-1, 3))
        v0, v1, v2 = verts[faces[:, 0]], verts[faces[:, 1]], verts[faces[:, 2]]
        face_normals = np.cross(v1 - v0, v2 - v0)
        face_areas = np.linalg.norm(face_normals, axis=1) / 2.0
        valid_mask = (face_areas > 1e-6) & (np.abs(face_normals[:, 2]) < 0.2)
        if not np.any(valid_mask): return None
        rounded_normals = np.round(face_normals[valid_mask], decimals=2)
        unique_normals, inverse_indices = np.unique(rounded_normals, axis=0, return_inverse=True)
        total_area_per_normal = np.bincount(inverse_indices, weights=face_areas[valid_mask])
        dominant_normal = unique_normals[np.argmax(total_area_per_normal)]
        return dominant_normal / np.linalg.norm(dominant_normal)
    except Exception:
        return None

def get_pitch_angle_from_normal(normal_vector):
    cos_alpha = abs(normal_vector[2])
    cos_alpha_clamped = max(min(cos_alpha, 1.0), -1.0)
    pitch_rad = math.acos(cos_alpha_clamped)
    # A inclinação é 90 graus menos o ângulo com o eixo Z
    return 90 - math.degrees(pitch_rad)

def get_quantity_value(quantity):
    """
    Extrai o valor numérico de um objeto IfcQuantity de forma segura.
    """
    if quantity.is_a("IfcQuantityLength"): return quantity.LengthValue
    elif quantity.is_a("IfcQuantityArea"): return quantity.AreaValue
    elif quantity.is_a("IfcQuantityVolume"): return quantity.VolumeValue
    elif quantity.is_a("IfcQuantityCount"): return quantity.CountValue
    elif quantity.is_a("IfcQuantityWeight"): return quantity.WeightValue
    elif hasattr(quantity, 'wrappedValue'): return quantity.wrappedValue
    return None

# ------------------------------------------------------------------------------
# Funções de Extração de Dados
# ------------------------------------------------------------------------------

def extrair_info_geografica(ifc_file):
    sites = ifc_file.by_type('IfcSite')
    lat, lon = (None, None)
    if sites:
        site = sites[0]
        if site.RefLatitude: lat = converter_angulo_para_decimal(site.RefLatitude)
        if site.RefLongitude: lon = converter_angulo_para_decimal(site.RefLongitude)
    norte_vetor = find_true_north(ifc_file)
    norte_angulo = calcular_angulo_vetor_graus(norte_vetor)
    return [{"Latitude": lat, "Longitude": lon, "Vetor Norte Verdadeiro": str(norte_vetor), "Ângulo Norte (vs Leste)": norte_angulo}]

def extrair_dados_paredes(ifc_file, norte_vetor):
    dados_paredes = []
    for wall in ifc_file.by_type("IfcWall"):
        is_external = False
        for rel in wall.IsDefinedBy:
            if rel.is_a("IfcRelDefinesByProperties"):
                prop_def = rel.RelatingPropertyDefinition
                if prop_def.is_a("IfcPropertySet") and prop_def.Name == 'Pset_WallCommon':
                    for prop in prop_def.HasProperties:
                        if prop.Name == 'IsExternal' and hasattr(prop, 'NominalValue') and prop.NominalValue.wrappedValue:
                            is_external = True; break
            if is_external: break
        if not is_external: continue

        normal = get_element_orientation_from_mesh(wall)
        orientacao = vector_to_angle_vs_north(normal, norte_vetor) if normal is not None else None

        quantities = {}
        for rel in ifc_file.get_inverse(wall):
            if rel.is_a("IfcRelDefinesByProperties") and rel.RelatingPropertyDefinition.is_a("IfcElementQuantity"):
                for q in rel.RelatingPropertyDefinition.Quantities:
                    quantities[q.Name] = get_quantity_value(q)

        area_aberturas = sum(get_quantity_value(q) for opening in wall.HasOpenings for fill in opening.RelatedOpeningElement.HasFillings for rel_prop in ifc_file.get_inverse(fill.RelatedBuildingElement) if rel_prop.is_a("IfcRelDefinesByProperties") and rel_prop.RelatingPropertyDefinition.is_a("IfcElementQuantity") for q in rel_prop.RelatingPropertyDefinition.Quantities if q.is_a("IfcQuantityArea") and q.Name == 'Area' and get_quantity_value(q) is not None)

        # dados_paredes.append({"ID": wall.GlobalId, "Nome": wall.Name or "Sem Nome", "Orientação (Azimute °)": orientacao, "Comprimento (m)": quantities.get('Length'), "Altura (m)": quantities.get('Height'), "Área Bruta (m²)": quantities.get('GrossArea'), "Área de Aberturas (m²)": area_aberturas, "Área Líquida (m²)": quantities.get('NetArea')})
        dados_paredes.append({"ID": wall.GlobalId, "Nome": wall.Name or "Sem Nome", "Orientação (Azimute °)": orientacao, "Comprimento (m)": quantities.get('Length'), "Altura (m)": quantities.get('Height'), "Área Bruta (m²)": quantities.get('Height') * quantities.get('Length'), "Área de Aberturas (m²)": area_aberturas, "Área Líquida (m²)": (quantities.get('Height') * quantities.get('Length')) - area_aberturas})
    return dados_paredes

def extrair_dados_janelas(ifc_file, norte_vetor):
    dados_janelas = []
    for window in ifc_file.by_type("IfcWindow"):
        normal = get_element_orientation_from_mesh(window)
        orientacao = vector_to_angle_vs_north(normal, norte_vetor) if normal is not None else None

        quantities = {}
        for rel in ifc_file.get_inverse(window):
            if rel.is_a("IfcRelDefinesByProperties") and rel.RelatingPropertyDefinition.is_a("IfcElementQuantity"):
                for q in rel.RelatingPropertyDefinition.Quantities:
                    quantities[q.Name] = get_quantity_value(q)

        dados_janelas.append({"ID": window.GlobalId, "Nome": window.Name or "Sem Nome", "Orientação (Azimute °)": orientacao, "Área (m²)": quantities.get('Area'), "Largura (m)": quantities.get('Width'), "Altura (m)": quantities.get('Height')})
    return dados_janelas

def extrair_dados_telhados(ifc_file, norte_vetor):
    dados_telhados = []
    for slab in ifc_file.by_type("IfcSlab"):
        if slab.PredefinedType != "ROOF": continue
        normal_geom = None
        try:
            rep = next(r for r in slab.Representation.Representations if r.RepresentationIdentifier == 'Body')
            solid = next(i for i in rep.Items if i.is_a("IfcExtrudedAreaSolid"))
            normal_geom = solid.ExtrudedDirection.DirectionRatios
        except (AttributeError, StopIteration): pass

        # Agora a chamada para a função funcionará
        orientacao = get_orientation_from_normal(normal_geom, norte_vetor) if normal_geom else None
        inclinacao = get_pitch_angle_from_normal(normal_geom) if normal_geom else None

        quantities = {}
        for rel in ifc_file.get_inverse(slab):
            if rel.is_a("IfcRelDefinesByProperties") and rel.RelatingPropertyDefinition.is_a("IfcElementQuantity"):
                for q in rel.RelatingPropertyDefinition.Quantities:
                    quantities[q.Name] = get_quantity_value(q)

        properties = {p.Name: p.NominalValue.wrappedValue for rel in ifc_file.get_inverse(slab) if rel.is_a("IfcRelDefinesByProperties") and rel.RelatingPropertyDefinition.is_a("IfcPropertySet") for p in rel.RelatingPropertyDefinition.HasProperties if p.is_a("IfcPropertySingleValue")}

        dados_telhados.append({"ID": slab.GlobalId, "Nome": slab.Name or "Sem Nome", "Orientação (Azimute °)": orientacao, "Inclinação (°)": properties.get('PitchAngle', inclinacao), "Área Bruta (m²)": quantities.get('GrossArea'), "Área Líquida (m²)": quantities.get('NetArea')})
    return dados_telhados

# ------------------------------------------------------------------------------
# Script Principal
# ------------------------------------------------------------------------------
# if __name__ == '__main__':
#     try:
#         ifc_file = ifcopenshell.open(IFC_PATH)
#         print(f"Arquivo IFC '{IFC_PATH}' aberto com sucesso.")
#     except Exception as e:
#         print(f"ERRO: Não foi possível abrir o arquivo IFC. {e}"); exit()

#     print("Extraindo informações geográficas e de orientação...")
#     info_geral = extrair_info_geografica(ifc_file)
#     df_geral = pd.DataFrame([info_geral])
#     norte_vetor_principal = find_true_north(ifc_file)

#     print("Analisando paredes externas...")
#     dados_paredes = extrair_dados_paredes(ifc_file, norte_vetor_principal)
#     df_paredes = pd.DataFrame(dados_paredes)

#     print("Analisando janelas...")
#     dados_janelas = extrair_dados_janelas(ifc_file, norte_vetor_principal)
#     df_janelas = pd.DataFrame(dados_janelas)

#     print("Analisando telhados...")
#     dados_telhados = extrair_dados_telhados(ifc_file, norte_vetor_principal)
#     df_telhados = pd.DataFrame(dados_telhados)

    # try:
    #     with pd.ExcelWriter(EXCEL_OUTPUT_PATH, engine='openpyxl') as writer:
    #         df_geral.to_excel(writer, sheet_name='Info_Geral', index=False)
    #         if not df_paredes.empty: df_paredes.to_excel(writer, sheet_name='Paredes_Externas', index=False)
    #         if not df_janelas.empty: df_janelas.to_excel(writer, sheet_name='Janelas', index=False)
    #         if not df_telhados.empty: df_telhados.to_excel(writer, sheet_name='Telhados', index=False)
    #     print(f"\n✅ Análise concluída! Os dados foram exportados para '{EXCEL_OUTPUT_PATH}'")
    # except Exception as e:
    #     print(f"\nERRO: Não foi possível salvar a planilha Excel. {e}")