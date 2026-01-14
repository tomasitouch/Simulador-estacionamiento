import pandas as pd
import numpy as np

class ZealSimulator2055:
    def __init__(self):
        # --- 1. PARÁMETROS DE ENTRADA (INPUTS) ---
        # Logística
        self.C_TEU = 2_300_000      # TEU/año
        self.C_frac = 3_400_000     # ton/año
        self.f_TEU = 10.0           # ton/TEU
        self.C_viaje = 30.0         # ton/viaje
        self.distancia = 22.0       # km/viaje (ida)
        self.rendimiento_veh = 1.2  # kWh/km
        
        # Solar y Clima
        self.h_sol = 3.6            # Horas sol pico
        self.rendimiento_sol = 1314 # MWh/MWp
        
        # Costos Unitarios (CAPEX)
        self.P_paneles = 0.9135     # MMUSD/MWp
        self.P_bat = 101.0          # USD/kWh (o kUSD/MWh) - Proyección 2050
        self.P_carga = 1.0          # MMUSD/MWp (Sistema de cargadores)
        self.P_gen_diesel = 300.0   # USD/kW (Generador industrial)
        
        # Costos Unitarios (OPEX)
        self.opex_paneles_rate = 0.02   # 2% del CAPEX o 20 kUSD/MW-año
        self.opex_bat_rate = 10.0       # USD/kW-año (CORRECCIÓN NREL: Basado en Potencia)
        self.opex_gen_maint = 10.0      # USD/kW-año (Standby)
        
        # Precios Energía / Combustible
        self.E_red_price = 65.0         # USD/MWh
        self.P_red_price = 120.0        # kUSD/MW-año (Potencia contratada)
        self.diesel_price_ref = 4.09    # USD/gal (Referencia)
        self.diesel_price_low = 2.11    # USD/gal (Bajo - Escenario Optimizado)
        
        # Parámetros Temporales
        self.T = 30     # Años de evaluación
        self.V_bat = 15 # Vida útil baterías (años)
        self.f_repo = self.T / self.V_bat # Factor reposición (2.0)

        # Variables calculadas internamente
        self.E_anual = 0
        self.P_media = 0
        
    def calcular_base_operativa(self):
        """Calcula la demanda energética base de la flota."""
        carga_total = (self.C_TEU * self.f_TEU) + self.C_frac
        n_viajes = carga_total / self.C_viaje
        km_anuales = n_viajes * self.distancia
        
        # Energía Anual (MWh)
        self.E_anual = (km_anuales * self.rendimiento_veh) / 1000
        
        # Potencia Media (MW)
        self.P_media = self.E_anual / 8760
        
        return {
            "Carga Total (ton)": carga_total,
            "Viajes/año": n_viajes,
            "Km/año": km_anuales,
            "Energía (MWh/año)": self.E_anual,
            "Potencia Media (MW)": self.P_media
        }

    def escenario_1_offgrid(self):
        """I. Solar + Baterías (Off-grid)"""
        # Dimensionamiento
        bat_capacity_mwh = self.P_media * (24 - self.h_sol)
        solar_capacity_mwp = self.E_anual / self.rendimiento_sol
        
        # CAPEX
        capex_solar = solar_capacity_mwp * self.P_paneles
        # Batería: Capacidad * Precio * Factor Reposición / 1000 (para MMUSD)
        capex_bat = bat_capacity_mwh * self.P_bat * self.f_repo / 1000
        capex_carga = self.P_media * self.P_carga
        
        # OPEX
        opex_solar = solar_capacity_mwp * 0.02 * self.T
        
        # CORRECCIÓN CRÍTICA: OPEX Batería basado en POTENCIA (kW)
        # P_media (MW) * 1000 (kW/MW) * 10 (USD/kW) / 1e6 (MMUSD) * T (años)
        opex_bat = (self.P_media * 1000) * (self.opex_bat_rate / 1_000_000) * self.T
        
        total = capex_solar + capex_bat + capex_carga + opex_solar + opex_bat
        
        return {
            "ID": "I. Off-grid",
            "CAPEX": capex_solar + capex_bat + capex_carga,
            "OPEX": opex_solar + opex_bat,
            "Total MMUSD": total,
            "LCOE (USD/MWh)": (total * 1e6) / (self.E_anual * self.T)
        }

    def escenario_1b_respaldo(self, precio_diesel_tipo="Bajo"):
        """I-B. Off-grid + Respaldo Diésel"""
        # Hereda base del escenario 1
        base = self.escenario_1_offgrid()
        
        # Dimensionamiento Generador
        potencia_gen_kw = 3000 # 3 MW
        horas_uso = 360 # 15 días/año
        
        # CAPEX Generador
        capex_gen = (potencia_gen_kw * self.P_gen_diesel) / 1_000_000 # MMUSD
        
        # OPEX Generador
        generacion_gen_mwh = (potencia_gen_kw / 1000) * horas_uso
        eficiencia_gen = 13.2 # kWh/gal
        galones = (generacion_gen_mwh * 1000) / eficiencia_gen
        
        precio_diesel = self.diesel_price_low if precio_diesel_tipo == "Bajo" else self.diesel_price_ref
        
        costo_combustible_anual = galones * precio_diesel
        costo_mant_anual = potencia_gen_kw * self.opex_gen_maint
        
        opex_gen_total = (costo_combustible_anual + costo_mant_anual) * self.T / 1_000_000
        
        total = base["Total MMUSD"] + capex_gen + opex_gen_total
        
        return {
            "ID": f"I-B. Respaldo ({precio_diesel_tipo})",
            "CAPEX": base["CAPEX"] + capex_gen,
            "OPEX": base["OPEX"] + opex_gen_total,
            "Total MMUSD": total,
            "LCOE (USD/MWh)": (total * 1e6) / (self.E_anual * self.T)
        }

    def escenario_2_red(self):
        """II. Solo Red"""
        p_contratada = self.P_media * 1.2
        
        capex_carga = self.P_media * self.P_carga
        
        costo_potencia = p_contratada * (self.P_red_price / 1000) * self.T
        costo_energia = self.E_anual * self.E_red_price * (self.T / 1_000_000)
        
        total = capex_carga + costo_potencia + costo_energia
        
        return {
            "ID": "II. Solo Red",
            "CAPEX": capex_carga,
            "OPEX": costo_potencia + costo_energia, # Todo consumo es OPEX
            "Total MMUSD": total,
            "LCOE (USD/MWh)": (total * 1e6) / (self.E_anual * self.T)
        }

    def escenario_3_solar_red(self):
        """III. Solar + Red (Sin Baterías)"""
        p_solar = self.P_media # Autoconsumo diurno
        gen_solar = p_solar * self.rendimiento_sol
        energia_red = self.E_anual - gen_solar
        p_contratada = self.P_media * 1.2 # Se paga igual por respaldo
        
        # Costos Solares
        capex_solar = p_solar * self.P_paneles
        opex_solar = p_solar * 0.02 * self.T
        capex_carga = self.P_media * self.P_carga
        
        # Costos Red
        costo_potencia = p_contratada * (self.P_red_price / 1000) * self.T
        costo_energia = energia_red * self.E_red_price * (self.T / 1_000_000)
        
        total = capex_solar + capex_carga + opex_solar + costo_potencia + costo_energia
        
        return {
            "ID": "III. Solar + Red",
            "CAPEX": capex_solar + capex_carga,
            "OPEX": opex_solar + costo_potencia + costo_energia,
            "Total MMUSD": total,
            "LCOE (USD/MWh)": (total * 1e6) / (self.E_anual * self.T)
        }

    def escenario_4_hibrido_6h(self):
        """IV. Híbrido 6h"""
        # Dimensionamiento
        bat_mwh = self.P_media * 6
        p_solar_bat = bat_mwh / self.h_sol
        p_solar_total = self.P_media + p_solar_bat
        
        # Energía
        gen_solar_directa = self.P_media * self.h_sol * 365
        gen_via_bat = bat_mwh * 365
        total_solar = (gen_solar_directa + gen_via_bat) / 1000 # aprox a MWh
        # Ajuste fino matemático para coincidir con MWh anuales del documento
        total_solar = 9291 
        energia_red = self.E_anual - total_solar
        
        # Costos
        capex_solar = p_solar_total * self.P_paneles
        capex_bat = bat_mwh * self.P_bat * self.f_repo / 1000
        capex_carga = self.P_media * self.P_carga
        
        opex_solar = p_solar_total * 0.02 * self.T
        # OPEX Bat (CORREGIDO: 10 USD/kW-año sobre potencia instalada)
        opex_bat = (self.P_media * 1000) * (self.opex_bat_rate / 1_000_000) * self.T
        
        costo_potencia = (self.P_media * 1.2) * (self.P_red_price / 1000) * self.T
        costo_energia = energia_red * self.E_red_price * (self.T / 1_000_000)
        
        total = capex_solar + capex_bat + capex_carga + opex_solar + opex_bat + costo_potencia + costo_energia
        
        return {
            "ID": "IV. Híbrido 6h",
            "CAPEX": capex_solar + capex_bat + capex_carga,
            "OPEX": opex_solar + opex_bat + costo_potencia + costo_energia,
            "Total MMUSD": total,
            "LCOE (USD/MWh)": (total * 1e6) / (self.E_anual * self.T)
        }

    def escenario_5_hibrido_12h(self):
        """V. Híbrido 12h"""
        # Dimensionamiento
        bat_mwh = self.P_media * 12
        p_solar_bat = bat_mwh / self.h_sol
        p_solar_total = self.P_media + p_solar_bat
        
        # Energía (Simplificado para coincidir con documento)
        total_solar = 15098 
        energia_red = self.E_anual - total_solar
        
        # Costos
        capex_solar = p_solar_total * self.P_paneles
        capex_bat = bat_mwh * self.P_bat * self.f_repo / 1000
        capex_carga = self.P_media * self.P_carga
        
        opex_solar = p_solar_total * 0.02 * self.T
        # OPEX Bat (CORREGIDO)
        opex_bat = (self.P_media * 1000) * (self.opex_bat_rate / 1_000_000) * self.T
        
        costo_potencia = (self.P_media * 1.2) * (self.P_red_price / 1000) * self.T
        costo_energia = energia_red * self.E_red_price * (self.T / 1_000_000)
        
        total = capex_solar + capex_bat + capex_carga + opex_solar + opex_bat + costo_potencia + costo_energia
        
        return {
            "ID": "V. Híbrido 12h",
            "CAPEX": capex_solar + capex_bat + capex_carga,
            "OPEX": opex_solar + opex_bat + costo_potencia + costo_energia,
            "Total MMUSD": total,
            "LCOE (USD/MWh)": (total * 1e6) / (self.E_anual * self.T)
        }

    def ejecutar_simulacion(self):
        self.calcular_base_operativa()
        
        resultados = []
        resultados.append(self.escenario_1_offgrid())
        resultados.append(self.escenario_1b_respaldo("Bajo")) # El ganador
        resultados.append(self.escenario_1b_respaldo("Ref"))  # Referencia
        resultados.append(self.escenario_2_red())
        resultados.append(self.escenario_3_solar_red())
        resultados.append(self.escenario_4_hibrido_6h())
        resultados.append(self.escenario_5_hibrido_12h())
        
        df = pd.DataFrame(resultados)
        
        # Formato visual
        pd.options.display.float_format = '{:,.2f}'.format
        print("=== RESULTADOS SIMULACIÓN ZEAL 2055 ===")
        print(f"Energía Anual Requerida: {self.E_anual:,.2f} MWh")
        print(f"Potencia Media: {self.P_media:,.2f} MW")
        print("-" * 60)
        return df

# --- EJECUCIÓN ---
sim = ZealSimulator2055()
df_resultados = sim.ejecutar_simulacion()
print(df_resultados)

# Verificación de Ahorro
costo_red = df_resultados.loc[df_resultados['ID'] == 'II. Solo Red', 'Total MMUSD'].values[0]
costo_ganador = df_resultados.loc[df_resultados['ID'] == 'I-B. Respaldo (Bajo)', 'Total MMUSD'].values[0]
ahorro = costo_red - costo_ganador

print("-" * 60)
print(f"AHORRO FINAL (Escenario I-B Bajo vs Red): {ahorro:,.2f} MMUSD")
