# =============================================================================
#  DASHBOARD DE MANTENIMIENTO PREDICTIVO - TRANSFORMADOR DE POTENCIA
#  Análisis químico (Furanos 2-FAL) + degradación de celulosa (DP) +
#  modelo 3D termomecánico con simulación de corriente Inrush.
#
#  Cómo ejecutarlo (cualquiera de las dos formas):
#       py app.py
#       py -m streamlit run app.py
#  Si faltan librerías (streamlit, numpy, plotly) el propio programa las instala.
# =============================================================================

# -----------------------------------------------------------------------------
# 0. AUTO-INSTALACIÓN DE LIBRERÍAS FALTANTES
# -----------------------------------------------------------------------------
import sys
import subprocess
import importlib
import importlib.util

# {nombre del módulo al importar : nombre del paquete en pip}
LIBRERIAS_REQUERIDAS = {
    "streamlit": "streamlit",
    "numpy": "numpy",
    "plotly": "plotly",
}


def instalar_librerias_faltantes():
    """Revisa cada librería y, si no existe, la descarga con pip automáticamente."""
    faltantes = [
        paquete
        for modulo, paquete in LIBRERIAS_REQUERIDAS.items()
        if importlib.util.find_spec(modulo) is None
    ]
    if not faltantes:
        return
    print(f"[SETUP] Instalando librerías faltantes: {', '.join(faltantes)} ...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", *faltantes])
        importlib.invalidate_caches()
        print("[SETUP] Instalación completada.")
    except subprocess.CalledProcessError as error:
        print(f"[SETUP] ERROR instalando librerías: {error}")
        print("        Intenta manualmente:  py -m pip install streamlit numpy plotly")
        sys.exit(1)


instalar_librerias_faltantes()

# -----------------------------------------------------------------------------
# Imports (ya garantizados)
# -----------------------------------------------------------------------------
import math
import numpy as np
import plotly.graph_objects as go
import streamlit as st

# Si el usuario ejecutó "py app.py" (sin streamlit), nos relanzamos con streamlit.
try:
    from streamlit import runtime as _st_runtime

    if __name__ == "__main__" and not _st_runtime.exists():
        subprocess.call([sys.executable, "-m", "streamlit", "run", __file__])
        sys.exit(0)
except ImportError:
    pass  # Versión antigua de streamlit: se asume ejecución con "streamlit run"

# -----------------------------------------------------------------------------
# 1. CONFIGURACIÓN DE PÁGINA Y ESTILO VISUAL
# -----------------------------------------------------------------------------
st.set_page_config(
    layout="wide",
    page_title="Diagnóstico Predictivo de Transformador",
    page_icon="⚡",
)

# CSS: tema oscuro industrial, tarjetas de métricas y badge de estado
st.markdown(
    """
    <style>
    .stApp { background-color: #0E1117; color: #E6EDF3; }
    [data-testid="stSidebar"] { background-color: #151B23; }
    [data-testid="stMetric"] {
        background: linear-gradient(145deg, #1A222C, #121820);
        border: 1px solid #2B3644; border-radius: 12px;
        padding: 14px 18px; box-shadow: 0 2px 10px rgba(0,0,0,.45);
    }
    [data-testid="stMetricValue"] { color: #FFFFFF; }
    [data-testid="stMetricLabel"] p { color: #9FB0C3; }
    .estado-card {
        border-radius: 12px; padding: 14px 18px; text-align: center;
        border: 1px solid #2B3644; box-shadow: 0 2px 10px rgba(0,0,0,.45);
        background: linear-gradient(145deg, #1A222C, #121820);
    }
    .estado-card .t { font-size: 0.85rem; color: #9FB0C3; margin-bottom: 4px; }
    .estado-card .v { font-size: 1.7rem; font-weight: 800; }
    .leyenda-dot { display:inline-block; width:12px; height:12px;
                   border-radius:50%; margin-right:8px; border:1px solid #555; }
    h1, h2, h3 { color: #FFFFFF; }
    </style>
    """,
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# 2. MOTOR DE CÁLCULO (QUÍMICO + MECÁNICO)
# -----------------------------------------------------------------------------
DP_NUEVO = 800        # DP > 800  -> papel en buen estado
DP_DESGASTE = 400     # DP > 400  -> desgaste normal
DP_ALERTA = 200       # DP > 200  -> alerta; DP <= 200 -> crítico
PPM_BASE = 0.01       # Furanos iniciales (ppm) en un equipo nuevo


def calcular_salud(anos, temp):
    """
    Devuelve (ppm_furanos, dp, resistencia_pct) para unos años y temperatura.

    - tasa_degradacion = (T - 50) * 0.0038
    - ppm = 0.01 * exp(tasa * años)
    - DP (Chendong) = (1.51 - log10(ppm)) / 0.0035   [se limita a >= 0]
    - Resistencia mecánica: 100 % con DP >= 800, lineal hacia abajo.
    """
    tasa_degradacion = (temp - 50) * 0.0038
    ppm_furanos = PPM_BASE * math.exp(tasa_degradacion * anos)
    dp = (1.51 - math.log10(max(ppm_furanos, 0.0001))) / 0.0035
    dp = max(dp, 0.0)  # un DP negativo no tiene sentido físico
    resistencia = max(0.0, min(100.0, (dp / DP_NUEVO) * 100.0))
    return ppm_furanos, dp, resistencia


def clasificar_estado(dp):
    """Devuelve (nombre_estado, color_UI, color_devanado_3D) según el DP."""
    if dp > DP_NUEVO:
        return "ÓPTIMO", "#2ECC71", "#F6B26B"          # Crema / naranja claro
    if dp > DP_DESGASTE:
        return "DESGASTE NORMAL", "#F1C40F", "#D35400"  # Naranja oscuro
    if dp > DP_ALERTA:
        return "ALERTA", "#E67E22", "#6E2C00"           # Café oscuro
    return "CRÍTICO", "#E74C3C", "#17202A"              # Negro carbonizado


def anos_hasta_dp_critico(temp, anos_actuales):
    """
    Años que le quedan al equipo antes de llegar a DP = 200 a la temperatura
    actual. Devuelve None si la tasa es 0 (T = 50 °C: no degrada en este modelo).
    """
    tasa = (temp - 50) * 0.0038
    if tasa <= 0:
        return None
    ppm_limite = 10 ** (1.51 - DP_ALERTA * 0.0035)       # ppm cuando DP = 200
    anos_totales = math.log(ppm_limite / PPM_BASE) / tasa
    return max(0.0, anos_totales - anos_actuales)


@st.cache_data(show_spinner=False)
def serie_temporal(temp, anos_max=40, puntos=161):
    """Curvas completas (años, ppm, dp) para una temperatura fija.
    Vectorizado con numpy y cacheado: las curvas de referencia (60 y 95 °C)
    se calculan una sola vez en toda la sesión."""
    anos = np.linspace(0, anos_max, puntos)
    tasa = (temp - 50) * 0.0038
    ppm = PPM_BASE * np.exp(tasa * anos)
    dp = np.maximum((1.51 - np.log10(np.maximum(ppm, 0.0001))) / 0.0035, 0.0)
    return anos, ppm, dp


# -----------------------------------------------------------------------------
# 3. MODELO 3D REALISTA (NÚCLEO + DEVANADOS + BUSHINGS + TANQUE)
# -----------------------------------------------------------------------------
def oscurecer(hex_color, factor):
    """Multiplica el brillo de un color hex (factor < 1 oscurece)."""
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    return "#{:02X}{:02X}{:02X}".format(
        *(max(0, min(255, int(c * factor))) for c in (r, g, b))
    )


# Iluminación para que las superficies parezcan metal / barniz y no planas
LUZ_SUPERFICIE = dict(ambient=0.45, diffuse=0.9, specular=0.55, roughness=0.35, fresnel=0.25)


def caja(x0, x1, y0, y1, z0, z1, color, opacity=1.0):
    """Prisma rectangular (Mesh3d) entre las esquinas (x0,y0,z0) y (x1,y1,z1)."""
    x = [x0, x0, x1, x1, x0, x0, x1, x1]
    y = [y0, y1, y1, y0, y0, y1, y1, y0]
    z = [z0, z0, z0, z0, z1, z1, z1, z1]
    i = [7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2]
    j = [3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3]
    k = [0, 7, 2, 3, 6, 7, 1, 1, 5, 5, 7, 6]
    return go.Mesh3d(
        x=x, y=y, z=z, i=i, j=j, k=k, color=color, opacity=opacity,
        flatshading=True, lighting=LUZ_SUPERFICIE, hoverinfo="skip",
    )


def cajas_combinadas(lista_cajas, color):
    """Fusiona varias cajas (x0,x1,y0,y1,z0,z1) en UNA sola traza Mesh3d (más rápido)."""
    xs, ys, zs, I, J, K = [], [], [], [], [], []
    base_i = [7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2]
    base_j = [3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3]
    base_k = [0, 7, 2, 3, 6, 7, 1, 1, 5, 5, 7, 6]
    for n, (x0, x1, y0, y1, z0, z1) in enumerate(lista_cajas):
        off = 8 * n
        xs += [x0, x0, x1, x1, x0, x0, x1, x1]
        ys += [y0, y1, y1, y0, y0, y1, y1, y0]
        zs += [z0, z0, z0, z0, z1, z1, z1, z1]
        I += [v + off for v in base_i]
        J += [v + off for v in base_j]
        K += [v + off for v in base_k]
    return go.Mesh3d(x=xs, y=ys, z=zs, i=I, j=J, k=K, color=color,
                     flatshading=True, lighting=LUZ_SUPERFICIE, hoverinfo="skip")


def superficie_color(x, y, z, color):
    """go.Surface de un solo color con iluminación."""
    return go.Surface(
        x=x, y=y, z=z, surfacecolor=np.ones_like(z),
        colorscale=[[0, color], [1, color]], showscale=False,
        lighting=LUZ_SUPERFICIE, hoverinfo="skip",
    )


def devanado(xc, yc, r_in, r_out, z0, z1, color, jx=0.0, jy=0.0, vueltas=14):
    """
    Devanado hueco (tubo) con espiras acanaladas en la cara exterior y anillos
    de cartón prensado arriba y abajo. Optimizado: solo la cara exterior usa
    malla densa; interior y anillos usan mallas mínimas.
    jx, jy = desplazamiento por vibración (Inrush).
    """
    theta = np.linspace(0, 2 * np.pi, 40)
    z = np.linspace(z0, z1, vueltas * 5)
    T, Z = np.meshgrid(theta, z)

    # Relieve de las espiras (ondulación pequeña del radio)
    relieve = 0.04 * np.sin(2 * np.pi * vueltas * (Z - z0) / (z1 - z0))
    R_ext = r_out + relieve

    # Cara interior: cilindro liso -> solo 2 filas
    T2, Z2 = np.meshgrid(theta, [z0, z1])

    trazas = [
        superficie_color(xc + jx + R_ext * np.cos(T), yc + jy + R_ext * np.sin(T), Z, color),
        superficie_color(xc + jx + r_in * np.cos(T2), yc + jy + r_in * np.sin(T2), Z2,
                         oscurecer(color, 0.7)),
    ]

    # Anillos superior e inferior (2 filas de malla)
    Ta, Ra = np.meshgrid(theta, [r_in, r_out])
    for z_anillo in (z0, z1):
        trazas.append(
            superficie_color(
                xc + jx + Ra * np.cos(Ta), yc + jy + Ra * np.sin(Ta),
                np.full_like(Ra, z_anillo), "#D9CBA8",
            )
        )
    return trazas


def bushing(xc, yc, z0, z1, color_porcelana="#8B5A3C"):
    """Aislador pasante (bushing) con faldones de porcelana. Superficie de revolución."""
    z = np.linspace(z0, z1, 64)
    radio = 0.28 + 0.13 * np.abs(np.sin(np.pi * (z - z0) / 0.42))  # faldones
    theta = np.linspace(0, 2 * np.pi, 24)
    T, Z = np.meshgrid(theta, z)
    R = np.tile(radio[:, None], (1, len(theta)))
    trazas = [superficie_color(xc + R * np.cos(T), yc + R * np.sin(T), Z, color_porcelana)]

    # Tapa metálica superior (terminal)
    z_t = np.linspace(z1, z1 + 0.35, 2)
    Tt, Zt = np.meshgrid(theta, z_t)
    trazas.append(superficie_color(xc + 0.18 * np.cos(Tt), yc + 0.18 * np.sin(Tt), Zt, "#B8C2CC"))
    return trazas


def tanque_alambre(x0, x1, y0, y1, z0, z1, color="#5B6B7D"):
    """Contorno (wireframe) del tanque de aceite para dar contexto de equipo real."""
    c = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
         (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    aristas = [(0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4),
               (0, 4), (1, 5), (2, 6), (3, 7)]
    xs, ys, zs = [], [], []
    for a, b in aristas:
        xs += [c[a][0], c[b][0], None]
        ys += [c[a][1], c[b][1], None]
        zs += [c[a][2], c[b][2], None]
    return go.Scatter3d(x=xs, y=ys, z=zs, mode="lines", hoverinfo="skip",
                        line=dict(color=color, width=3), opacity=0.55)


def construir_modelo_3d(color_devanado, amplitud_vibracion=0.0):
    """
    Construye la figura 3D completa.
      - color_devanado: color según el DP.
      - amplitud_vibracion: si > 0 desplaza X/Y de cada devanado con ruido
        aleatorio (simula la fuerza electrodinámica del Inrush).
    """
    fig = go.Figure()
    rng = np.random.default_rng()

    COLOR_NUCLEO = "#3B4252"       # Acero al silicio (gris oscuro)
    COLOR_CONDUCTOR = "#C77B30"    # Cobre de las conexiones
    posiciones_fase = (-5.0, 0.0, 5.0)

    # --- Base y tanque -------------------------------------------------------
    fig.add_trace(caja(-8.5, 8.5, -4.2, 4.2, -6.3, -5.8, "#1B2430"))
    fig.add_trace(tanque_alambre(-8.5, 8.5, -4.2, 4.2, -5.8, 9.4))

    # --- Núcleo tipo "E": yugo superior, yugo inferior y 3 columnas ----------
    piezas_nucleo = [(-6.5, 6.5, -1.3, 1.3, 4.0, 5.6),     # yugo superior
                     (-6.5, 6.5, -1.3, 1.3, -5.6, -4.0)]   # yugo inferior
    piezas_nucleo += [(xc - 1.1, xc + 1.1, -1.2, 1.2, -4.0, 4.0) for xc in posiciones_fase]
    fig.add_trace(cajas_combinadas(piezas_nucleo, COLOR_NUCLEO))

    # --- Devanados (BT interior + AT exterior) y bushings --------------------
    for xc in posiciones_fase:
        # Cada fase vibra de forma independiente
        jx = rng.uniform(-amplitud_vibracion, amplitud_vibracion) if amplitud_vibracion else 0.0
        jy = rng.uniform(-amplitud_vibracion, amplitud_vibracion) if amplitud_vibracion else 0.0

        # Devanado de baja tensión (más oscuro) y de alta tensión
        for traza in devanado(xc, 0, 1.75, 1.97, -3.2, 3.2, oscurecer(color_devanado, 0.82), jx, jy, 11):
            fig.add_trace(traza)
        for traza in devanado(xc, 0, 2.12, 2.42, -3.4, 3.4, color_devanado, jx, jy, 14):
            fig.add_trace(traza)

        # Cable de salida: del devanado AT hasta el bushing
        fig.add_trace(go.Scatter3d(
            x=[xc + jx, xc + jx, xc], y=[2.42 + jy, 2.42 + jy, 0], z=[3.4, 6.5, 6.5],
            mode="lines", line=dict(color=COLOR_CONDUCTOR, width=7), hoverinfo="skip",
        ))
        # Bushing sobre el yugo
        for traza in bushing(xc, 0, 5.6, 8.6):
            fig.add_trace(traza)

    # --- Cámara y escena estilo CAD ------------------------------------------
    fig.update_layout(
        scene=dict(
            xaxis=dict(visible=False), yaxis=dict(visible=False), zaxis=dict(visible=False),
            aspectmode="data",
            bgcolor="#0E1117",
            camera=dict(eye=dict(x=1.5, y=-1.9, z=0.85)),
        ),
        margin=dict(l=0, r=0, t=0, b=0),
        height=600,
        paper_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
    )
    return fig


@st.cache_resource(show_spinner=False)
def modelo_3d_estatico(color_devanado):
    """Modelo en reposo cacheado: solo existen 4 colores posibles, así que se
    construye una vez por color y luego se reutiliza al instante."""
    return construir_modelo_3d(color_devanado, 0.0)


def modelo_3d(color_devanado, amplitud):
    """Reposo -> figura cacheada. Inrush -> figura nueva con vibración."""
    if amplitud <= 0:
        return modelo_3d_estatico(color_devanado)
    return construir_modelo_3d(color_devanado, amplitud)


# -----------------------------------------------------------------------------
# 4. GRÁFICAS 2D DE TENDENCIA
# -----------------------------------------------------------------------------
def construir_grafica_tendencia(tipo, anos_sel, temp_sel, valor_sel, escala_log=False):
    """
    tipo: 'ppm' (Furanos vs Años) o 'dp' (DP vs Años).
    Dibuja 3 curvas: Sano (60 °C), Sobrecalentado (95 °C) y Tu transformador.
    Agrega un marcador en el año seleccionado sobre la curva azul.
    """
    idx = 1 if tipo == "ppm" else 2
    anos, *_ = serie_temporal(60)
    y_sano = serie_temporal(60)[idx]
    y_rojo = serie_temporal(95)[idx]
    y_tuyo = serie_temporal(temp_sel)[idx]  # cacheado por temperatura

    fig = go.Figure()

    if tipo == "dp":
        # Zonas de color de fondo según el estado del papel
        zonas = [(DP_NUEVO, 1100, "#2ECC71"), (DP_DESGASTE, DP_NUEVO, "#F1C40F"),
                 (DP_ALERTA, DP_DESGASTE, "#E67E22"), (0, DP_ALERTA, "#E74C3C")]
        for y0, y1, col in zonas:
            fig.add_hrect(y0=y0, y1=y1, fillcolor=col, opacity=0.10, line_width=0)

    fig.add_trace(go.Scatter(x=anos, y=y_sano, mode="lines", name="Referencia Sano (60 °C)",
                             line=dict(color="#2ECC71", width=2.5, dash="dash")))
    fig.add_trace(go.Scatter(x=anos, y=y_rojo, mode="lines", name="Referencia Sobrecalentado (95 °C)",
                             line=dict(color="#E74C3C", width=2.5, dash="dash")))
    fig.add_trace(go.Scatter(x=anos, y=y_tuyo, mode="lines", name=f"Tu Transformador ({temp_sel} °C)",
                             line=dict(color="#3498DB", width=5)))

    # Marcador en el año seleccionado
    fig.add_trace(go.Scatter(
        x=[anos_sel], y=[valor_sel], mode="markers+text", name="Hoy",
        marker=dict(color="#FFFFFF", size=15, line=dict(color="#3498DB", width=4)),
        text=[f"{valor_sel:.2f}" if tipo == "ppm" else f"{valor_sel:.0f}"],
        textposition="top center", textfont=dict(color="#FFFFFF", size=13),
        showlegend=False,
    ))

    if tipo == "ppm":
        # Línea del nivel de furanos equivalente a DP = 200
        ppm_limite = 10 ** (1.51 - DP_ALERTA * 0.0035)
        fig.add_hline(y=ppm_limite, line=dict(color="#E74C3C", width=1.5, dash="dot"),
                      annotation_text=f"Límite crítico (DP=200 ≈ {ppm_limite:.1f} ppm)",
                      annotation_font_color="#E74C3C", annotation_position="top left")
        titulo, eje_y = "Furanos 2-FAL vs Años de Operación", "Furanos (ppm)"
        if escala_log:
            fig.update_yaxes(type="log")
        else:
            # Evita que la curva roja/azul extrema aplaste todo lo demás
            fig.update_yaxes(range=[0, max(12, valor_sel * 1.4)])
    else:
        titulo, eje_y = "Grado de Polimerización (DP) vs Años de Operación", "DP"
        fig.update_yaxes(range=[0, 1100])

    fig.update_layout(
        template="plotly_dark", title=dict(text=titulo, font=dict(size=17)),
        xaxis_title="Años de operación", yaxis_title=eje_y,
        height=430, margin=dict(l=10, r=10, t=60, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#121820",
        legend=dict(orientation="h", yanchor="bottom", y=-0.35, x=0),
        hovermode="x unified",
    )
    fig.update_xaxes(range=[0, 40], gridcolor="#2B3644")
    fig.update_yaxes(gridcolor="#2B3644")
    return fig


def mostrar_plotly(fig):
    """Compatibilidad entre versiones de Streamlit al mostrar figuras Plotly."""
    try:
        st.plotly_chart(fig, width="stretch")
    except TypeError:
        st.plotly_chart(fig, use_container_width=True)


# -----------------------------------------------------------------------------
# 5. BARRA LATERAL (ENTRADAS)
# -----------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Parámetros Operativos")
    anos = st.slider("Años de Operación", 0, 40, 10)
    temp = st.slider("Temperatura Nominal (°C)", 50, 120, 85)
    st.divider()
    escala_log = st.checkbox("Escala logarítmica en gráfica de Furanos", value=False)
    st.divider()
    st.caption("**Modelo utilizado**")
    st.code(
        "tasa = (T - 50) * 0.0038\n"
        "ppm  = 0.01 * exp(tasa * años)\n"
        "DP   = (1.51 - log10(ppm)) / 0.0035",
        language="text",
    )
    st.caption("Resistencia mecánica = DP / 800 (máx. 100 %).")

# -----------------------------------------------------------------------------
# 6. CÁLCULOS PRINCIPALES
# -----------------------------------------------------------------------------
ppm_actual, dp_actual, resistencia_actual = calcular_salud(anos, temp)
estado, color_estado, color_3d = clasificar_estado(dp_actual)
anos_restantes = anos_hasta_dp_critico(temp, anos)

# -----------------------------------------------------------------------------
# 7. SECCIÓN 1: ENCABEZADO Y TARJETAS DE MÉTRICAS
# -----------------------------------------------------------------------------
st.title("⚡ Diagnóstico Predictivo de Transformador de Potencia")
st.caption("Análisis químico (Furanos), degradación de celulosa (DP) y comportamiento "
           "termomecánico ante corriente Inrush.")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Grado de Polimerización (DP)", f"{dp_actual:.0f}",
          help="DP > 800 óptimo · > 400 desgaste normal · > 200 alerta · < 200 crítico")
c2.metric("Furanos 2-FAL", f"{ppm_actual:.3f} ppm")
c3.metric("Resistencia Mecánica", f"{resistencia_actual:.0f} %")
c4.markdown(
    f"""<div class="estado-card"><div class="t">Estado del Aislamiento</div>
    <div class="v" style="color:{color_estado}">{estado}</div></div>""",
    unsafe_allow_html=True,
)
st.progress(int(round(resistencia_actual)))

if estado == "ÓPTIMO":
    st.success("✅ Aislamiento en excelentes condiciones.")
elif estado == "DESGASTE NORMAL":
    st.info("ℹ️ Desgaste normal. Continuar con el monitoreo de rutina.")
elif estado == "ALERTA":
    st.warning("⚠️ Papel muy degradado. Programar mantenimiento preventivo.")
else:
    st.error("🚨 Estado crítico: riesgo de falla inminente (DP < 200).")

st.divider()

# -----------------------------------------------------------------------------
# 8. SECCIÓN 2: MODELO 3D INTERACTIVO + BOTÓN INRUSH
# -----------------------------------------------------------------------------
st.header("🧲 Modelo 3D del Núcleo y Devanados")
col_3d, col_info = st.columns([2.3, 1])

with col_info:
    st.subheader("Simulación de Falla")
    st.write("La corriente **Inrush** genera fuerzas electrodinámicas (Lorentz) que "
             "hacen vibrar los devanados. Con papel degradado, el aislamiento no resiste.")
    inrush = st.button("⚡ SIMULAR INRUSH (Vibración Mecánica)", type="primary")

    st.markdown("**Código de color de los devanados**")
    st.markdown(
        """
        <div><span class="leyenda-dot" style="background:#F6B26B"></span>DP &gt; 800 · Óptimo</div>
        <div><span class="leyenda-dot" style="background:#D35400"></span>DP &gt; 400 · Desgaste normal</div>
        <div><span class="leyenda-dot" style="background:#6E2C00"></span>DP &gt; 200 · Alerta</div>
        <div><span class="leyenda-dot" style="background:#17202A"></span>DP &lt; 200 · Carbonizado</div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("---")
    if anos_restantes is None:
        st.metric("Vida restante hasta DP = 200", "∞")
    else:
        st.metric("Vida restante hasta DP = 200", f"{anos_restantes:.1f} años")
    st.caption("Arrastra para rotar · rueda del mouse para acercar.")

# Amplitud de vibración: aumenta mientras más débil esté el papel
amplitud = 0.0
if inrush:
    amplitud = 0.06 + 0.45 * (1 - resistencia_actual / 100.0)

with col_3d:
    mostrar_plotly(modelo_3d(color_3d, amplitud))

if inrush:
    if dp_actual < DP_ALERTA:
        st.error("💥 ¡CORTOCIRCUITO CATASTRÓFICO! El aislamiento (DP < 200) no soportó las "
                 "fuerzas del Inrush: los devanados se deformaron y el equipo falló.")
    elif dp_actual < DP_DESGASTE:
        st.warning("⚠️ El transformador resistió el Inrush, pero con vibración severa. "
                   "El aislamiento quedó comprometido.")
    else:
        st.success("✅ El aislamiento soportó las fuerzas del Inrush sin daños.")

st.divider()

# -----------------------------------------------------------------------------
# 9. SECCIÓN 3: GRÁFICAS DE TENDENCIA 2D
# -----------------------------------------------------------------------------
st.header("📈 Tendencias de Vida Útil")
g1, g2 = st.columns(2)
with g1:
    mostrar_plotly(construir_grafica_tendencia("ppm", anos, temp, ppm_actual, escala_log))
with g2:
    mostrar_plotly(construir_grafica_tendencia("dp", anos, temp, dp_actual))

st.caption("🟢 Sano (60 °C) · 🔴 Sobrecalentado (95 °C) · 🔵 Tu transformador (temperatura del slider). "
           "El punto blanco marca el año seleccionado.")
