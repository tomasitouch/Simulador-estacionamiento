import streamlit as st
import pandas as pd
import plotly.express as px

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Sensibilidad ZEAL 2055", layout="wide")

st.title("🔋 Simulador de Sensibilidad: ZEAL 2055")
st.markdown("""
Esta herramienta evalúa cómo cambia la rentabilidad de los 6 escenarios de electrificación al variar parámetros clave del mercado.  
*Nota metodológica:* El cálculo del VAN replica la estructura del documento original, aplicando correcciones sobre el CAPEX fotovoltaico del Escenario III.
""")

# --- PANEL LATERAL: PARÁMETROS DE SENSIBILIDAD ---
st.sidebar.header("Parámetros Sensibles")

r_pct = st.sidebar.slider("Tasa de descuento anual (%)", min_value=1.0, max_value=15.0, value=5.0, step=0.5)
r = r_pct / 100.0

E_precio = st.sidebar.slider("Precio Energía Red (USD/MWh)", min_value=30.0, max_value=150.0, value=65.0, step=5.0)

P_pan_precio = st.sidebar.slider("CAPEX Paneles Solares (MMUSD/MWp)", min_value=0.50, max_value=1.50, value=0.9135, step=0.05)

mult_bat = st.sidebar.slider("Multiplicador Precio Baterías (%)", min_value=30, max_value=200, value=100, step=10) / 100.0

st.sidebar.markdown("---")
P_pot_L = st.sidebar.slider("Precio Potencia Cliente Libre (kUSD/MW-año)", min_value=50.0, max_value=200.0, value=120.0, step=10.0)
P_pot_R = st.sidebar.slider("Precio Potencia Cliente Regulado (kUSD/MW-año)", min_value=30.0, max_value=150.0, value=60.0, step=10.0)

# --- CONSTANTES OPERACIONALES ---
T = 30
E_anual = 23487
P_contratada = 3.217

# --- DATOS BASE DE LOS ESCENARIOS ---
scenarios = [
    {"name": "I. Solar+BESS 20.4h", "P_pan": 17.875, "C_bat": 54.697, "E_red": 0, "P_bat_kUSD": 70.0, "Pot_price": 0, "Carga_price": 2.988, "OPEX_bat_anual": 0.02681},
    {"name": "II. Solo Red", "P_pan": 0.0, "C_bat": 0.0, "E_red": 23487, "P_bat_kUSD": 0.0, "Pot_price": P_pot_L, "Carga_price": 3.480, "OPEX_bat_anual": 0.0},
    {"name": "III. Solar+Red", "P_pan": 2.681, "C_bat": 0.0, "E_red": 19964, "P_bat_kUSD": 0.0, "Pot_price": P_pot_L, "Carga_price": 3.480, "OPEX_bat_anual": 0.0},
    {"name": "IV. Híbrido 6h", "P_pan": 7.150, "C_bat": 16.087, "E_red": 14092, "P_bat_kUSD": 97.22, "Pot_price": P_pot_L, "Carga_price": 3.480, "OPEX_bat_anual": 0.02681},
    {"name": "V. Híbrido 12h", "P_pan": 11.619, "C_bat": 32.174, "E_red": 8221, "P_bat_kUSD": 85.88, "Pot_price": P_pot_L, "Carga_price": 3.480, "OPEX_bat_anual": 0.02681},
    {"name": "VI. Solar+Net Billing Reg.", "P_pan": 17.875, "C_bat": 0.0, "E_red": 19964, "P_bat_kUSD": 0.0, "Pot_price": P_pot_R, "Carga_price": 2.881, "OPEX_bat_anual": 0.0},
]

# --- MOTOR DE CÁLCULO ---
results = []
# Factor de valor presente para anualidades (PVIFA)
pvifa = (1 - (1 + r)**-T) / r if r > 0 else T

for s in scenarios:
    # 1. Inversiones (CAPEX)
    capex_pan = s["P_pan"] * P_pan_precio
    capex_bat_0 = s["C_bat"] * (s["P_bat_kUSD"] * mult_bat / 1000.0)
    capex_carga = s["Carga_price"]
    
    # El modelo asume un reemplazo de baterías a mitad de vida que se suma nominalmente al CAPEX
    capex_total_nominal = capex_pan + (capex_bat_0 * 2) + capex_carga 

    # 2. Costos Operacionales Anuales (OPEX)
    opex_pan_anual = s["P_pan"] * 0.020
    opex_bat_anual = s["OPEX_bat_anual"] if s["C_bat"] > 0 else 0
    costo_pot_anual = P_contratada * s["Pot_price"] / 1000.0
    costo_ene_anual = s["E_red"] * E_precio / 1000000.0
    
    opex_total_anual = opex_pan_anual + opex_bat_anual + costo_pot_anual + costo_ene_anual
    
    # 3. Cálculo de VAN y LCOE
    van = capex_total_nominal + opex_total_anual * pvifa
    lcoe = (van * 1_000_000) / (E_anual * T)
    
    results.append({
        "Escenario": s["name"],
        "CAPEX (MM$)": round(capex_total_nominal, 2),
        "OPEX (MM$/año)": round(opex_total_anual, 3),
        "VAN (MM$)": round(van, 2),
        "USD/MWh": round(lcoe, 2)
    })

df = pd.DataFrame(results)

# --- RENDERIZADO UI ---
winner_row = df.loc[df['VAN (MM$)'].idxmin()]

st.success(f"🏆 **El escenario ganador es:** {winner_row['Escenario']} con un VAN de **{winner_row['VAN (MM$)']} MMUSD**")

# Gráfico de barras interactivo
fig = px.bar(
    df, 
    x='Escenario', 
    y='VAN (MM$)', 
    text='VAN (MM$)', 
    color='VAN (MM$)', 
    color_continuous_scale='Blues_r',
    title="Comparación de VAN por Escenario"
)
fig.update_traces(textposition='outside')
fig.update_layout(yaxis_range=[0, df['VAN (MM$)'].max() * 1.15]) # Dar espacio al texto
st.plotly_chart(fig, use_container_width=True)

# Tabla de datos
st.subheader("📊 Desglose de Resultados")
st.dataframe(
    df.style.highlight_min(subset=['VAN (MM$)', 'USD/MWh'], color='#a8e6cf', axis=0)
            .format({'CAPEX (MM$)': '{:.2f}', 'OPEX (MM$/año)': '{:.3f}', 'VAN (MM$)': '{:.2f}', 'USD/MWh': '{:.2f}'}),
    use_container_width=True
)
