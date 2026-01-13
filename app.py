import streamlit as st
import pandas as pd
import plotly.express as px

# Configuración de la página
st.set_page_config(page_title="Evaluación ZEAL 2055 - 5 Escenarios", layout="wide", page_icon="⚡")

def main():
    st.title("⚡ ZEAL 2055: Simulador Completo (5 Escenarios)")
    st.markdown("""
    Comparativa de estrategias de electrificación para tractocamiones:
    * **I. Solar + Baterías (Off-grid)**: Independencia total.
    * **II. Solo Red**: Conexión tradicional.
    * **III. Solar + Red**: Autoconsumo diurno.
    * **IV. Híbrido 6h**: Solar + Batería para punta tarde + Red noche.
    * **V. Híbrido 12h**: Solar + Batería extendida + Red madrugada.
    """)

    # --- BARRA LATERAL: INPUTS ---
    st.sidebar.header("1. Datos Operativos")
    
    col1, col2 = st.sidebar.columns(2)
    with col1:
        carga_teu = st.number_input("Carga TEU/año", value=2300000)
        carga_fracc = st.number_input("Carga Fracc. (ton)", value=3400000)
        distancia_km = st.number_input("Distancia Viaje (km)", value=22.0)
    with col2:
        factor_teu_ton = st.number_input("Factor Ton/TEU", value=10.0)
        rendimiento = st.number_input("Rendimiento (kWh/km)", value=1.2)
        # Calculamos viajes implícitos para cuadrar con el Excel
        # Si tienes el dato exacto de viajes, mejor, pero lo derivamos de la carga
        carga_por_viaje = st.number_input("Carga/Viaje (ton)", value=30.0)

    st.sidebar.header("2. Costos e Inversión")
    inv_paneles = st.number_input("Capex Paneles (MMUSD/MWp)", value=0.9135, format="%.4f")
    precio_sis_carga = st.number_input("Capex Cargadores (MMUSD/MWp)", value=1.0)
    
    st.sidebar.subheader("Precios Energía 2055")
    precio_energia = st.number_input("Energía Red (USD/MWh)", value=65.0)
    precio_potencia = st.number_input("Potencia Red (kUSD/MW-año)", value=120.0)
    precio_bat_capex = st.number_input("Baterías Capex (kUSD/MWh)", value=101.0)

    st.sidebar.subheader("Parámetros Técnicos")
    horas_sol = st.number_input("Horas Sol Pico/día", value=3.6)
    rendimiento_solar = st.number_input("Rendimiento (MWh/MWp)", value=1314.0)
    factor_area = st.number_input("Uso Suelo (m²/MWp)", value=4333.0)

    # --- CÁLCULOS BASE ---
    total_carga = (carga_teu * factor_teu_ton) + carga_fracc
    num_viajes = total_carga / carga_por_viaje
    km_anuales = num_viajes * distancia_km
    
    energia_anual_mwh = (km_anuales * rendimiento) / 1000
    potencia_media_mw = energia_anual_mwh / 8760
    # Potencia contratada a la red (con factor de seguridad del Excel ~1.2)
    potencia_red_mw = potencia_media_mw * 1.2

    # Variables de vida útil
    anios_eval = 30
    vida_bateria = 15
    factor_repo_bat = anios_eval / vida_bateria # 2.0
    
    # OPEX estimados (según Excel)
    opex_paneles_mmusd_mw = 20000 / 1e6 # 20 kUSD/MW
    opex_bat_mmusd_mwh = 10000 / 1e6   # 10 kUSD/MWh (approx 10 USD/kWh)

    escenarios = []

    # ==========================================
    # LÓGICA DE LOS 5 ESCENARIOS
    # ==========================================

    # 1. ESCENARIO I: OFF-GRID TOTAL
    # Solar cubre todo. Batería cubre las horas sin sol (24 - 3.6 = 20.4h)
    e1_bat_cap_mwh = potencia_media_mw * (24 - horas_sol)
    # Paneles deben generar la energía anual completa
    e1_panel_mwp = energia_anual_mwh / rendimiento_solar 
    
    costo_e1 = {
        "capex_panel": e1_panel_mwp * inv_paneles,
        "capex_bat": e1_bat_cap_mwh * (precio_bat_capex/1000) * factor_repo_bat,
        "capex_carga": potencia_media_mw * precio_sis_carga,
        "opex_panel": e1_panel_mwp * opex_paneles_mmusd_mw * anios_eval,
        "opex_bat": e1_bat_cap_mwh * opex_bat_mmusd_mwh * anios_eval,
        "costo_red_pot": 0,
        "costo_red_ene": 0
    }
    
    # 2. ESCENARIO II: SOLO RED
    costo_e2 = {
        "capex_panel": 0,
        "capex_bat": 0,
        "capex_carga": potencia_media_mw * precio_sis_carga,
        "opex_panel": 0,
        "opex_bat": 0,
        "costo_red_pot": potencia_red_mw * (precio_potencia/1000) * anios_eval,
        "costo_red_ene": energia_anual_mwh * precio_energia * anios_eval / 1e6
    }

    # 3. ESCENARIO III: SOLAR + RED (Sin Baterías)
    # Solar cubre consumo directo durante horas de sol.
    e3_panel_mwp = potencia_media_mw # Dimensionado solo para consumo instantáneo
    e3_gen_solar = e3_panel_mwp * rendimiento_solar # Total generado = Total autoconsumido
    e3_red_ene = energia_anual_mwh - e3_gen_solar
    
    costo_e3 = {
        "capex_panel": e3_panel_mwp * inv_paneles,
        "capex_bat": 0,
        "capex_carga": potencia_media_mw * precio_sis_carga,
        "opex_panel": e3_panel_mwp * opex_paneles_mmusd_mw * anios_eval,
        "opex_bat": 0,
        "costo_red_pot": potencia_red_mw * (precio_potencia/1000) * anios_eval,
        "costo_red_ene": e3_red_ene * precio_energia * anios_eval / 1e6
    }

    # 4. ESCENARIO IV: HÍBRIDO (6 Horas Batería)
    # Batería dimensionada para 6 horas
    e4_bat_cap_mwh = potencia_media_mw * 6
    # Paneles deben cubrir consumo directo (3.6h) + Cargar Batería (en esas 3.6h)
    # Potencia carga bat = Capacidad / Horas Sol
    e4_panel_bat_mw = e4_bat_cap_mwh / horas_sol
    e4_panel_total_mwp = potencia_media_mw + e4_panel_bat_mw
    
    # Energía: Solar Directo + Solar via Bat
    e4_solar_directo = potencia_media_mw * horas_sol * 365
    e4_solar_bat = e4_bat_cap_mwh * 365
    e4_total_solar = e4_solar_directo + e4_solar_bat
    e4_red_ene = energia_anual_mwh - e4_total_solar

    costo_e4 = {
        "capex_panel": e4_panel_total_mwp * inv_paneles,
        "capex_bat": e4_bat_cap_mwh * (precio_bat_capex/1000) * factor_repo_bat,
        "capex_carga": potencia_media_mw * precio_sis_carga,
        "opex_panel": e4_panel_total_mwp * opex_paneles_mmusd_mw * anios_eval,
        "opex_bat": e4_bat_cap_mwh * opex_bat_mmusd_mwh * anios_eval,
        "costo_red_pot": potencia_red_mw * (precio_potencia/1000) * anios_eval, # Paga potencia igual
        "costo_red_ene": e4_red_ene * precio_energia * anios_eval / 1e6
    }

    # 5. ESCENARIO V: HÍBRIDO (12 Horas Batería)
    e5_bat_cap_mwh = potencia_media_mw * 12
    e5_panel_bat_mw = e5_bat_cap_mwh / horas_sol
    e5_panel_total_mwp = potencia_media_mw + e5_panel_bat_mw
    
    e5_solar_directo = potencia_media_mw * horas_sol * 365
    e5_solar_bat = e5_bat_cap_mwh * 365
    e5_total_solar = e5_solar_directo + e5_solar_bat
    e5_red_ene = energia_anual_mwh - e5_total_solar

    costo_e5 = {
        "capex_panel": e5_panel_total_mwp * inv_paneles,
        "capex_bat": e5_bat_cap_mwh * (precio_bat_capex/1000) * factor_repo_bat,
        "capex_carga": potencia_media_mw * precio_sis_carga,
        "opex_panel": e5_panel_total_mwp * opex_paneles_mmusd_mw * anios_eval,
        "opex_bat": e5_bat_cap_mwh * opex_bat_mmusd_mwh * anios_eval,
        "costo_red_pot": potencia_red_mw * (precio_potencia/1000) * anios_eval,
        "costo_red_ene": e5_red_ene * precio_energia * anios_eval / 1e6
    }

    # --- CONSOLIDACIÓN ---
    raw_data = [
        {"Escenario": "I. Solar + Bat (Off-grid)", "Datos": costo_e1, "MWp": e1_panel_mwp, "Bat_MWh": e1_bat_cap_mwh},
        {"Escenario": "II. Solo Red", "Datos": costo_e2, "MWp": 0, "Bat_MWh": 0},
        {"Escenario": "III. Solar + Red", "Datos": costo_e3, "MWp": e3_panel_mwp, "Bat_MWh": 0},
        {"Escenario": "IV. Solar + Bat (6h) + Red", "Datos": costo_e4, "MWp": e4_panel_total_mwp, "Bat_MWh": e4_bat_cap_mwh},
        {"Escenario": "V. Solar + Bat (12h) + Red", "Datos": costo_e5, "MWp": e5_panel_total_mwp, "Bat_MWh": e5_bat_cap_mwh},
    ]

    final_rows = []
    for item in raw_data:
        d = item["Datos"]
        capex_total = d["capex_panel"] + d["capex_bat"] + d["capex_carga"]
        opex_total = d["opex_panel"] + d["opex_bat"] + d["costo_red_pot"] + d["costo_red_ene"]
        costo_total = capex_total + opex_total
        
        final_rows.append({
            "Escenario": item["Escenario"],
            "CAPEX (MMUSD)": capex_total,
            "OPEX (MMUSD)": opex_total,
            "Costo Total (30 años)": costo_total,
            "Costo Unitario (USD/MWh)": (costo_total * 1e6) / (energia_anual_mwh * anios_eval),
            "Paneles (MWp)": item["MWp"],
            "Área (hectáreas)": (item["MWp"] * factor_area) / 10000,
            "Baterías (MWh)": item["Bat_MWh"]
        })

    df = pd.DataFrame(final_rows)

    # --- VISUALIZACIÓN ---
    
    # Métricas Globales
    st.subheader("📊 Resumen Operativo")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Energía Anual", f"{energia_anual_mwh:,.0f} MWh")
    k2.metric("Potencia Media", f"{potencia_media_mw:.2f} MW")
    k3.metric("Flota Estimada", f"{int(num_viajes/(365*10.12))} Tractos")
    k4.metric("Km Anuales", f"{km_anuales/1e6:.1f} Millones")
    
    st.divider()

    # Ganador
    mejor = df.loc[df["Costo Total (30 años)"].idxmin()]
    st.success(f"🏆 MEJOR ESCENARIO: **{mejor['Escenario']}** con **{mejor['Costo Total (30 años)']:.2f} MMUSD**")

    # Gráficos
    tab1, tab2 = st.tabs(["💰 Financiero", "🏗️ Infraestructura"])
    
    with tab1:
        st.subheader("Costo Total a 30 Años (CAPEX + OPEX)")
        fig = px.bar(df, x="Escenario", y=["CAPEX (MMUSD)", "OPEX (MMUSD)"], 
                     title="Composición de Costos", text_auto=".1f")
        fig.update_layout(yaxis_title="Millones USD")
        st.plotly_chart(fig, use_container_width=True)
        
    with tab2:
        col_a, col_b = st.columns(2)
        with col_a:
            st.subheader("Uso de Terreno (Paneles)")
            fig2 = px.bar(df, x="Escenario", y="Área (hectáreas)", color="Área (hectáreas)",
                          color_continuous_scale="Reds", text_auto=".1f")
            st.plotly_chart(fig2, use_container_width=True)
        with col_b:
            st.subheader("Capacidad de Baterías")
            fig3 = px.bar(df, x="Escenario", y="Baterías (MWh)", color="Baterías (MWh)",
                          color_continuous_scale="Blues", text_auto=".1f")
            st.plotly_chart(fig3, use_container_width=True)

    # Tabla Detalle
    st.subheader("Matriz Detallada")
    st.dataframe(df.style.format({
        "CAPEX (MMUSD)": "{:.2f}",
        "OPEX (MMUSD)": "{:.2f}",
        "Costo Total (30 años)": "{:.2f}",
        "Costo Unitario (USD/MWh)": "{:.2f}",
        "Paneles (MWp)": "{:.2f}",
        "Área (hectáreas)": "{:.2f}",
        "Baterías (MWh)": "{:.2f}"
    }))

if __name__ == "__main__":
    main()
