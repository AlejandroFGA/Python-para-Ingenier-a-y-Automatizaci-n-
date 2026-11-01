import streamlit as st
import numpy as np
import plotly.graph_objects as go
import math
import time

# Configuración de la página (ancho completo)
st.set_page_config(layout="wide", page_title="Simulador de Transformador 3D")

# ---------------------------------------------------------
# FÓRMULAS MATEMÁTICAS (DEGRADACIÓN TÉRMICA)
# ---------------------------------------------------------
def calcular_salud(anos, temp):
    # Ecuación de envejecimiento
    tasa = (temp - 50) * 0.0038
    ppm = 0.01 * math.exp(tasa * anos)
    
    # Ecuación de Chendong para el DP
    dp = (1.51 - math.log10(max(ppm, 0.0001))) / 0.0035
    
    # Estimación de fuerza mecánica (100% = DP > 800)
    resistencia = max(0, min(100, (dp / 1000) * 100))
    return ppm, dp, resistencia

# ---------------------------------------------------------
# CONSTRUCCIÓN DEL MODELO 3D INTERACTIVO
# ---------------------------------------------------------
def dibujar_transformador(color_bobina, vibracion=0):
    fig = go.Figure()

    # Función auxiliar para dibujar cajas (El núcleo de acero)
    def add_box(xc, yc, zc, dx, dy, dz, color_hex):
        x = [xc-dx/2, xc+dx/2, xc+dx/2, xc-dx/2, xc-dx/2, xc+dx/2, xc+dx/2, xc-dx/2]
        y = [yc-dy/2, yc-dy/2, yc+dy/2, yc+dy/2, yc-dy/2, yc-dy/2, yc+dy/2, yc+dy/2]
        z = [zc-dz/2, zc-dz/2, zc-dz/2, zc-dz/2, zc+dz/2, zc+dz/2, zc+dz/2, zc+dz/2]
        i, j, k = [7,0,0,0,4,4,6,6,4,0,3,2], [3,4,1,2,5,6,5,2,0,1,6,3], [0,7,2,3,6,7,1,1,5,5,7,6]
        fig.add_trace(go.Mesh3d(x=x, y=y, z=z, i=i, j=j, k=k, color=color_hex, flatshading=True, hoverinfo='skip'))

    # Función auxiliar para dibujar cilindros (Los devanados)
    def add_cylinder(xc, yc, zc, radius, height, color_hex):
        z = np.linspace(zc - height/2, zc + height/2, 20)
        theta = np.linspace(0, 2*np.pi, 20)
        theta_grid, z_grid = np.meshgrid(theta, z)
        x_grid = xc + radius * np.cos(theta_grid) + vibracion
        y_grid = yc + radius * np.sin(theta_grid) + vibracion
        surfacecolor = np.ones_like(z_grid)
        fig.add_surface(x=x_grid, y=y_grid, z=z_grid, surfacecolor=surfacecolor, 
                        colorscale=[[0, color_hex], [1, color_hex]], showscale=False, hoverinfo='skip')

    # Dibujamos el yugo superior e inferior (Acero gris oscuro)
    color_acero = '#2C3E50'
    add_box(0, 0, 4.5, 13, 2, 1, color_acero)  # Top
    add_box(0, 0, -4.5, 13, 2, 1, color_acero) # Bottom

    # Dibujamos las 3 bobinas
    add_cylinder(-4, 0, 0, 1.6, 8, color_bobina)
    add_cylinder(0, 0, 0, 1.6, 8, color_bobina)
    add_cylinder(4, 0, 0, 1.6, 8, color_bobina)

    # Configuramos la cámara para que parezca un software CAD
    fig.update_layout(
        scene=dict(
            xaxis=dict(visible=False), yaxis=dict(visible=False), zaxis=dict(visible=False),
            camera=dict(eye=dict(x=1.8, y=-1.5, z=0.8)) # Ángulo de vista inicial
        ),
        margin=dict(l=0, r=0, b=0, t=0),
        height=450,
        paper_bgcolor='rgba(0,0,0,0)', 
    )
    return fig

# ---------------------------------------------------------
# INTERFAZ DE USUARIO (DASHBOARD)
# ---------------------------------------------------------
st.title("⚡ Degradación del Aislamiento de Transformador")
st.markdown("Simulación termomecánica y cálculo del Grado de Polimerización (DP) en la celulosa.")
st.divider()

# Layout: Controles a la izquierda, 3D a la derecha
col_izq, col_der = st.columns([1, 1.5])

with col_izq:
    st.subheader("Parámetros Operativos")
    anos = st.slider("Años de Operación", 0, 40, 10)
    temp = st.slider("Temperatura Nominal (°C)", 50, 120, 85)
    
    # Calcular variables
    ppm, dp, resistencia = calcular_salud(anos, temp)
    
    # Determinar lógica de colores y alertas
    if dp > 800:
        estado, color_ui, color_bobina = "NUEVO / ÓPTIMO", "normal", "#F39C12" # Naranja brillante
    elif dp > 400:
        estado, color_ui, color_bobina = "DESGASTE NORMAL", "off", "#D35400" # Naranja oscuro
    elif dp > 200:
        estado, color_ui, color_bobina = "ALERTA PREVENTIVA", "inverse", "#6E2C00" # Café
    else:
        estado, color_ui, color_bobina = "CRÍTICO (Riesgo Falla)", "inverse", "#17202A" # Negro/Carbonizado

    st.markdown("### Resultados del Diagnóstico")
    # Tarjetas de métricas tipo dashboard
    m1, m2 = st.columns(2)
    m1.metric("Grado Polimerización (DP)", f"{int(dp)}", estado, delta_color=color_ui)
    m2.metric("Furanos Acumulados", f"{ppm:.2f} PPM")
    st.metric("Resistencia Mecánica Restante", f"{int(resistencia)} %")
    
    # Botón de Inrush
    inrush_btn = st.button("⚡ SIMULAR INRUSH (Vibración Mecánica)", use_container_width=True, type="primary")

with col_der:
    # Lógica de animación si se presiona el botón Inrush
    if inrush_btn:
        if dp < 200:
            st.error("💥 ¡Falla Catastrófica! El aislamiento estaba muy débil y el cortocircuito destruyó el equipo.")
            # Simular vibración fuerte
            grafica = dibujar_transformador(color_bobina, vibracion=np.random.uniform(-0.5, 0.5))
        else:
            st.success("✅ El aislamiento soportó las fuerzas de Lorentz del Inrush sin romperse.")
            # Simular vibración leve
            grafica = dibujar_transformador(color_bobina, vibracion=np.random.uniform(-0.1, 0.1))
    else:
        grafica = dibujar_transformador(color_bobina)
        
    # Renderizar el modelo 3D
    st.plotly_chart(grafica, use_container_width=True)