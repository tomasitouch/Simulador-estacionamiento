import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# --- CONFIGURACION DE LA INTERFAZ ---
st.set_page_config(
    page_title="ZEAL 2055 - Terminal de Inteligencia",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- PALETA DE COLORES Y ESTILO CORPORATIVO ---
STYLE = {
    "bg_base": "#0f172a",
    "bg_card": "linear-gradient(135deg, #1e293b 0%, #0f172a 100%)",
    "accent_primary": "#38bdf8",
    "accent_secondary": "#2dd4bf",
    "text_main": "#f1f5f9",
    "text_muted": "#94a3b8",
    "grid_line": "#334155",
    "danger": "#f43f5e",
    "font_family": "'Inter', sans-serif"
}

# --- INYECCION DE CSS PROFESIONAL ---
st.markdown(f"""
    <style>
    .stApp {{
        background-color: {STYLE['bg_base']};
        color: {STYLE['text_main']};
        font-family: {STYLE['font_family']};
    }}
    
    div[data-testid="stMetric"] {{
        background: {STYLE['bg_card']};
        border: 1px solid {STYLE['grid_line']};
        padding: 20px !important;
        border-radius: 8px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    }}
    
    div[data-testid="stMetricValue"] {{
        background: linear-gradient(to right, {STYLE['accent_primary']}, {STYLE['accent_secondary']});
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
        font-size: 2rem !important;
    }}

    section[data-testid="stSidebar"] {{
        background-color: #111827 !important;
        border-right: 1px solid {STYLE['grid_line']};
    }}

    .stTabs [data-baseweb="tab-list"] {{
        gap: 30px;
        border-bottom: 1px solid {STYLE['grid_line']};
    }}
    
    .impact-box {{
        padding: 8px;
        border-left: 2px solid {STYLE['accent_primary']};
        background: rgba(56, 189, 248, 0.05);
        margin-bottom: 12px;
        font-size: 0.75rem;
        color: {STYLE['text_muted']};
    }}
    </style>
""", unsafe_allow_html=True)

# --- BACKEND MATEMATICO INTEGRAL ---
class MotorZEAL:
    @staticmethod
    def calcular(p):
        # 1. Calculo de Demanda Logistica
        total_viajes = p['teu'] + (p['ton_frac'] / 30.0)
        distancia_anual = total_viajes * p['km_trip']
        # Usamos multiplicación para que 1.2 funcione como kWh/km
        demand_mwh = (distancia_anual * p['truck_eff']) / 1000
        
        # 2. Parametros de Inversion
        solar_cost_final = p['sol_base'] * (1 + p['struct_extra']) 
        ch_cost = p['ch_cost']
        opex_solar_mwp = p['om_usd_mwp'] / 1e6
        
        e_dia = demand_mwh * (1 - p['night_ratio'])
        e_noche = demand_mwh * p['night_ratio']
        res = {}

        # ESCENARIO 5: SOLO RED (Inacción)
        s5_mw = 0.0
        s5_capex = ch_cost
        s5_opex = (demand_mwh * (p['grid_e'] / 1e6)) + (p['contract_mw'] * (p['grid_p'] / 1e6))
        s5_total = s5_capex + (s5_opex * 30)
        res['Solo Red (Inacción)'] = {
            'Total': s5_total, 'CAPEX': s5_capex, 'MW': s5_mw, 'MWh_Bat': 0.0,
            'LCOE': (s5_total * 1e6) / (demand_mwh * 30), 'Color': STYLE['danger']
        }

        # ESCENARIO 3: BASE RED (Excel)
        s3_mw = 43.6
        s3_capex = (s3_mw * solar_cost_final) + ch_cost
        s3_opex = (s3_mw * opex_solar_mwp) + (e_noche * (p['grid_e'] / 1e6)) + (p['contract_mw'] * (p['grid_p'] / 1e6))
        s3_total = s3_capex + (s3_opex * 30)
        res['Solar + Red (Excel)'] = {
            'Total': s3_total, 'CAPEX': s3_capex, 'MW': s3_mw, 'MWh_Bat': 0.0,
            'LCOE': (s3_total * 1e6) / (demand_mwh * 30), 'Color': STYLE['text_muted']
        }

        # ESCENARIO 4: HIBRIDO ESTRATEGICO (Peak Shaving)
        e_n_bat = e_noche * 0.5
        e_n_grid = e_noche * 0.5
        s4_mw = (e_dia + (e_n_bat / 0.9)) / p['gen_f']
        s4_bat = (e_n_bat / 365.0) * 1.1 
        s4_capex = (s4_mw * solar_cost_final) + (s4_bat * (p['bat_kwh']/1000)) + ch_cost
        s4_opex = (s4_mw * opex_solar_mwp) + (e_n_grid * (p['grid_e'] / 1e6)) + (3.0 * (p['grid_p'] / 1e6))
        s4_total = s4_capex + (s4_opex * 30)
        res['Hibrido Óptimo'] = {
            'Total': s4_total, 'CAPEX': s4_capex, 'MW': s4_mw, 'MWh_Bat': s4_bat,
            'LCOE': (s4_total * 1e6) / (demand_mwh * 30), 'Color': STYLE['accent_primary']
        }

        # ESCENARIO 2: AUTONOMIA TOTAL (Off-Grid)
        s2_mw = (e_dia + (e_noche / 0.9)) / p['gen_f']
        s2_bat = (e_noche / 365.0) * 1.1
        s2_capex = (s2_mw * solar_cost_final) + (s2_bat * (p['bat_kwh']/1000)) + ch_cost
        s2_opex = (s2_mw * opex_solar_mwp)
        s2_total = s2_capex + (s2_opex * 30)
        res['Autonomía Total'] = {
            'Total': s2_total, 'CAPEX': s2_capex, 'MW': s2_mw, 'MWh_Bat': s2_bat,
            'LCOE': (s2_total * 1e6) / (demand_mwh * 30), 'Color': STYLE['accent_secondary']
        }

        df = pd.DataFrame(res).T
        df['Area_Ha'] = (df['MW'] * p['area_f']) / 10000
        return df, demand_mwh

# --- LOGICA DE INTERFAZ ---
def main():
    st.title("TERMINAL DE ESTRATEGIA ENERGETICA ZEAL 2055")
    st.markdown("SISTEMA DE SOPORTE A DECISIONES BASADO EN METODOLOGIA NREL/TP-462-5173")
    st.write("---")

    with st.sidebar:
        st.subheader("DATOS LOGISTICOS")
        teu = st.number_input("TEUs Anuales", value=2300000)
        ton = st.number_input("Toneladas Fraccionadas", value=3400000)
        truck_eff = st.number_input("Consumo Vehicular (kWh/km)", value=1.2)
        
        st.subheader("SOLAR Y ALMACENAMIENTO")
        sol_base = st.number_input("CAPEX Base (MMUSD/MWp)", value=0.8667)
        struct_extra = st.slider("Adicional Estructura %", 0, 20, 5) / 100.0
        bat_kwh = st.slider("CAPEX Bateria (USD/kWh)", 50, 300, 101)
        
        st.subheader("MERCADO Y OPEX")
        grid_e = st.number_input("Precio Energia (USD/MWh)", value=65.0)
        grid_p = st.number_input("Precio Potencia (USD/MW-año)", value=120000.0)
        night_r = st.slider("Consumo Nocturno %", 0, 100, 65) / 100.0

    p = {
        'teu': teu, 'ton_frac': ton, 'truck_eff': truck_eff, 'km_trip': 22,
        'sol_base': sol_base, 'struct_extra': struct_extra, 'bat_kwh': bat_kwh,
        'gen_f': 1314.0, 'area_f': 4333.3, 'grid_e': grid_e, 'grid_p': grid_p,
        'contract_mw': 8.0, 'night_ratio': night_r, 'ch_cost': 4.0, 'om_usd_mwp': 20000.0
    }
    
    df, demanda = MotorZEAL.calcular(p)
    ahorro = df.loc['Solo Red (Inacción)', 'Total'] - df.loc['Hibrido Óptimo', 'Total']

    c = st.columns(4)
    c[0].metric("DEMANDA CALCULADA", f"{demanda/1000:,.1f} GWh")
    c[1].metric("AHORRO VS INACCIÓN", f"${ahorro:,.1f} M")
    c[2].metric("LCOE ÓPTIMO", f"${df['LCOE'].min():,.2f}")
    c[3].metric("TERRENO HÍBRIDO", f"{df.loc['Hibrido Óptimo','Area_Ha']:,.1f} Ha")

    st.write("###")

    tab1, tab2 = st.tabs(["COMPARATIVA FINANCIERA", "SENSIBILIDAD DE MERCADO"])

    with tab1:
        col_a, col_b = st.columns(2)
        with col_a:
            fig = go.Figure([go.Bar(
                x=df.index, y=df['Total'],
                marker_color=df['Color'],
                text=df['Total'].round(1), textposition='outside'
            )])
            fig.update_layout(title="Costo Total de Propiedad (30 Años) - MMUSD", template="plotly_dark",
                              paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig, use_container_width=True)

        with col_b:
            df_st = df[['CAPEX']].copy()
            df_st['OPEX_30Y'] = df['Total'] - df['CAPEX']
            fig2 = go.Figure()
            fig2.add_trace(go.Bar(name='Inversión (CAPEX)', x=df_st.index, y=df_st['CAPEX'], marker_color=STYLE['accent_primary']))
            fig2.add_trace(go.Bar(name='Operación (OPEX 30A)', x=df_st.index, y=df_st['OPEX_30Y'], marker_color=STYLE['grid_line']))
            fig2.update_layout(barmode='stack', title="Estructura de Capital vs Gasto Operativo", template="plotly_dark",
                              paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig2, use_container_width=True)

    with tab2:
        st.write("ANÁLISIS DE RESILIENCIA: HÍBRIDO VS INACCIÓN")
        x_rango = np.linspace(50, 400, 25)
        lista_s = []
        for v in x_rango:
            p_tmp = p.copy(); p_tmp['bat_kwh'] = v
            r_tmp, _ = MotorZEAL.calcular(p_tmp)
            lista_s.append({'Val': v, 'Inacción': r_tmp.loc['Solo Red (Inacción)','Total'], 'Hibrido': r_tmp.loc['Hibrido Óptimo','Total']})
        
        df_s = pd.DataFrame(lista_s)
        fig3 = go.Figure()
        fig3.add_trace(go.Scatter(x=df_s['Val'], y=df_s['Inacción'], name="Solo Red", line=dict(color=STYLE['danger'], dash='dash')))
        fig3.add_trace(go.Scatter(x=df_s['Val'], y=df_s['Hibrido'], name="Estrategia Híbrida", line=dict(color=STYLE['accent_primary'], width=4)))
        fig3.update_layout(template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                          xaxis_title="Costo Batería (USD/kWh)", yaxis_title="Costo Total 30 Años (MMUSD)")
        st.plotly_chart(fig3, use_container_width=True)

    with st.expander("REGISTRO DE AUDITORÍA DE DATOS"):
        # ELIMINAMOS LA COLUMNA 'Color' para evitar el ValueError de formato str
        df_audit = df.drop(columns=['Color'])
        st.dataframe(df_audit.style.format("{:,.2f}").background_gradient(cmap='Blues_r'))

if __name__ == "__main__":
    main()
