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
    "matplotlib": "matplotlib",   # gráficas dentro del PDF
    "reportlab": "reportlab",     # generación del informe PDF
    "pandas": "pandas",           # tablas en pantalla
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
import io
import math
import re
import datetime
from xml.sax.saxutils import escape as esc
import numpy as np
import pandas as pd
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
# 2. MOTOR DE CÁLCULO, CATÁLOGOS Y MOTOR DE RECOMENDACIONES
# -----------------------------------------------------------------------------
DP_NUEVO = 800        # DP > 800  -> papel en buen estado
DP_DESGASTE = 400     # DP > 400  -> desgaste normal
DP_ALERTA = 200       # DP > 200  -> alerta; DP <= 200 -> crítico
PPM_BASE = 0.01       # Furanos iniciales (ppm) en un equipo nuevo

# Tipos de aislamiento. 'factor' multiplica la tasa de degradación:
# 1.0 = papel Kraft estándar en aceite mineral (modelo base).
# Los factores son ILUSTRATIVOS (aprox. de literatura técnica); ajústalos con
# datos reales de tu fabricante si los tienes.
TIPOS_AISLAMIENTO = {
    "Papel Kraft estándar + aceite mineral": dict(
        factor=1.00, desc="Aislamiento convencional. Es el modelo base."),
    "Papel termoestabilizado (TUK) + aceite mineral": dict(
        factor=0.40, desc="Papel con aditivos que frenan la degradación térmica."),
    "Papel Kraft estándar + aceite éster natural": dict(
        factor=0.30, desc="El éster absorbe humedad del papel y ralentiza su envejecimiento."),
    "Papel TUK + aceite éster natural": dict(
        factor=0.15, desc="Combinación de papel mejorado y fluido éster."),
    "Aramida (Nomex) híbrido": dict(
        factor=0.05, desc="Clase térmica muy alta. OJO: la aramida no genera furanos, "
                          "por lo que el diagnóstico por furanos pierde validez."),
}

TENSIONES_KV = [13.8, 23.0, 34.5, 69.0, 115.0, 138.0, 230.0, 345.0, 400.0]
# Nivel básico de aislamiento al impulso (BIL, kV pico) TÍPICO por clase de tensión
BIL_TIPICO_KV = {13.8: 110, 23.0: 150, 34.5: 200, 69.0: 350, 115.0: 550,
                 138.0: 650, 230.0: 900, 345.0: 1050, 400.0: 1300}


def bil_tipico(kv):
    """BIL típico (kV) de la clase de tensión inmediata superior; None si no aplica."""
    for clase in sorted(BIL_TIPICO_KV):
        if kv <= clase:
            return BIL_TIPICO_KV[clase]
    return None


def calcular_salud(anos, temp, factor=1.0):
    """
    Devuelve (ppm_furanos, dp, resistencia_pct).
    - tasa_degradacion = (T - 50) * 0.0038 * factor_aislamiento
    - ppm = 0.01 * exp(tasa * años)
    - DP (Chendong) = (1.51 - log10(ppm)) / 0.0035   [se limita a >= 0]
    - Resistencia mecánica: 100 % con DP >= 800, lineal hacia abajo.
    """
    tasa_degradacion = (temp - 50) * 0.0038 * factor
    ppm_furanos = PPM_BASE * math.exp(tasa_degradacion * anos)
    dp = (1.51 - math.log10(max(ppm_furanos, 0.0001))) / 0.0035
    dp = max(dp, 0.0)
    resistencia = max(0.0, min(100.0, (dp / DP_NUEVO) * 100.0))
    return ppm_furanos, dp, resistencia


def clasificar_estado(dp):
    """Devuelve (nombre_estado, color_UI, color_devanado_3D) según el DP."""
    if dp > DP_NUEVO:
        return "ÓPTIMO", "#2ECC71", "#F6B26B"
    if dp > DP_DESGASTE:
        return "DESGASTE NORMAL", "#F1C40F", "#D35400"
    if dp > DP_ALERTA:
        return "ALERTA", "#E67E22", "#6E2C00"
    return "CRÍTICO", "#E74C3C", "#17202A"


def anos_hasta_dp_critico(temp, anos_actuales, factor=1.0):
    """Años que faltan para DP = 200 a la temperatura actual (None = no degrada)."""
    tasa = (temp - 50) * 0.0038 * factor
    if tasa <= 0:
        return None
    ppm_limite = 10 ** (1.51 - DP_ALERTA * 0.0035)
    return max(0.0, math.log(ppm_limite / PPM_BASE) / tasa - anos_actuales)


@st.cache_data(show_spinner=False)
def serie_temporal(temp, factor=1.0, anos_max=40, puntos=161):
    """Curvas completas (años, ppm, dp) vectorizadas y cacheadas."""
    anos = np.linspace(0, anos_max, puntos)
    tasa = (temp - 50) * 0.0038 * factor
    ppm = PPM_BASE * np.exp(tasa * anos)
    dp = np.maximum((1.51 - np.log10(np.maximum(ppm, 0.0001))) / 0.0035, 0.0)
    return anos, ppm, dp


# ---------------------------- COSTOS ORIENTATIVOS ----------------------------
# Modelo de costo de un transformador NUEVO (USD): ley de potencia anclada a
# rangos públicos recientes (aprox. 1.4 M para 10 MVA y 6.5 M para 300 MVA a
# 115-138 kV; los valores $/MVA publicados para unidades grandes rondan
# 15-21 k USD/MVA). Es una ORIENTACIÓN: siempre pedir cotización formal.
def factor_voltaje(kv):
    if kv <= 34.5:
        return 0.80
    if kv <= 69:
        return 0.90
    if kv <= 138:
        return 1.00
    if kv <= 230:
        return 1.15
    return 1.30


def costo_nuevo_base(mva, kv):
    return 1_400_000 * (max(mva, 5.0) / 10.0) ** 0.45 * factor_voltaje(kv)


def plazo_entrega_nuevo(mva):
    """Plazos de entrega orientativos (el mercado 2025-2026 está muy saturado)."""
    if mva <= 20:
        return "12-24 meses"
    if mva <= 100:
        return "18-30 meses"
    return "30-40 meses"


def fmt_usd(x):
    """Formato legible: 2.30 M / 115 k / 26,000 / 500."""
    if x >= 1e6:
        return f"US$ {x / 1e6:.2f} M"
    if x >= 1e5:
        return f"US$ {x / 1e3:,.0f} k"
    return f"US$ {round(x, -2) if x >= 1000 else round(x):,.0f}"


def fmt_rango(lo, hi):
    if lo is None:
        return "Ver opciones de reemplazo"
    return f"{fmt_usd(lo)} - {fmt_usd(hi)}"


ORDEN_PRIORIDAD = {"Inmediata": 0, "Alta": 1, "Media": 2, "Baja": 3}


def generar_acciones(estado, temp, anos_rest, factor, mva, kv):
    """Plan de acción priorizado según estado del aislamiento, temperatura y vida restante."""
    base = costo_nuevo_base(mva, kv)
    acciones = []

    def add(prio, accion, plazo, lo, hi, detalle):
        acciones.append(dict(prioridad=prio, accion=accion, plazo=plazo,
                             lo=lo, hi=hi, detalle=detalle))

    frecuencia = {"ÓPTIMO": "anual", "DESGASTE NORMAL": "semestral",
                  "ALERTA": "trimestral", "CRÍTICO": "mensual"}[estado]
    prio_base = {"ÓPTIMO": "Baja", "DESGASTE NORMAL": "Media",
                 "ALERTA": "Alta", "CRÍTICO": "Alta"}[estado]

    add(prio_base, f"Análisis de aceite (DGA, furanos, humedad, acidez) con frecuencia {frecuencia}",
        "Continuo", 500, 2500,
        "Cada campaña. Permite detectar fallas incipientes y confirmar la tendencia del DP.")
    add("Baja" if estado == "ÓPTIMO" else "Media", "Termografía e inspección del sistema de enfriamiento",
        "Anual", 2000, 8000,
        "Detecta puntos calientes, radiadores obstruidos o ventiladores/bombas fuera de servicio.")

    if temp >= 85:
        add("Alta" if temp >= 95 else "Media",
            "Reducir temperatura de operación: revisar enfriamiento y perfil de carga",
            "1-3 meses", 0.01 * base, 0.04 * base,
            "Como regla práctica, cada 6-8 °C por encima del diseño duplica la velocidad de "
            "envejecimiento del papel. Revisar ventiladores, radiadores, nivel de aceite y picos de carga.")

    if estado in ("DESGASTE NORMAL", "ALERTA", "CRÍTICO"):
        add("Media" if estado == "DESGASTE NORMAL" else "Alta",
            "Regeneración / filtrado y secado del aceite",
            "3-6 meses", 0.02 * base, 0.05 * base,
            "Elimina humedad, ácidos y lodos. Importante: mejora el aceite pero NO restituye "
            "la resistencia ya perdida por el papel.")

    if estado in ("DESGASTE NORMAL", "ALERTA") and factor >= 0.9:
        add("Media", "Evaluar conversión (retrofill) a aceite éster natural",
            "6-12 meses", 0.03 * base, 0.07 * base,
            "Ralentiza el envejecimiento de la celulosa restante. Requiere estudio de compatibilidad "
            "de materiales y empaques con el fabricante.")

    if estado in ("ALERTA", "CRÍTICO"):
        add("Alta", "Instalar monitoreo en línea (gases disueltos, temperatura y humedad)",
            "3-6 meses", 15000, 60000,
            "Alerta temprana ante fallas mientras se gestiona la rehabilitación o el reemplazo.")
        add("Alta", "Pruebas eléctricas: FRA, factor de potencia, relación de transformación, resistencia de aislamiento",
            "1-3 meses", 5000, 20000,
            "El FRA detecta deformaciones de devanados tras cortocircuitos o corrientes Inrush severas.")

    if estado == "ALERTA":
        add("Alta", "Planear ya el reemplazo o rebobinado (los plazos de entrega son largos)",
            "Iniciar ahora", None, None,
            "Con plazos de 1.5 a 3 años en el mercado actual, conviene iniciar la especificación y "
            "el presupuesto de inmediato. Evitar sobrecargas y maniobras que generen Inrush intenso.")

    if estado == "CRÍTICO":
        add("Inmediata", "Confirmar el DP real (muestra de papel / pruebas) y retirar el equipo de servicio de forma programada",
            "Inmediato", 3000, 15000,
            "Con DP < 200 el papel no resiste esfuerzos de cortocircuito. No reenergizar sin pruebas.")
        add("Inmediata", "Asegurar unidad de reserva o transformador móvil (renta) y verificar protecciones",
            "Inmediato", None, None,
            "Reduce el riesgo de interrupción prolongada mientras llega el reemplazo.")

    if estado in ("ÓPTIMO", "DESGASTE NORMAL") and anos_rest is not None and anos_rest < 5:
        add("Media", "Incluir reemplazo o rebobinado en el plan de inversión (horizonte 3-5 años)",
            "Próximo ciclo presupuestal", None, None,
            f"A esta temperatura quedan aprox. {anos_rest:.1f} años para llegar a DP = 200.")

    if estado in ("ALERTA", "CRÍTICO") and factor >= 0.9:
        add("Media", "Si se rebobina o reemplaza: especificar papel TUK o aramida y fluido éster",
            "Al especificar", None, None,
            "Reduce de forma importante la tasa de envejecimiento frente al aislamiento convencional.")

    acciones.sort(key=lambda a: ORDEN_PRIORIDAD[a["prioridad"]])
    return acciones


def opciones_reemplazo(mva, kv):
    """Opciones de reemplazo / reconstrucción con rango de costo y plazo (orientativo)."""
    base = costo_nuevo_base(mva, kv)
    plazo = plazo_entrega_nuevo(mva)
    marcas = [
        ("Hitachi Energy", "Premium", 1.15,
         "Gama amplia de transformadores de potencia; opción premium con monitoreo digital integrable."),
        ("Siemens Energy", "Premium", 1.15,
         "Gran experiencia en alta tensión; opción premium."),
        ("Prolec GE", "Intermedia", 1.00,
         "Con operación industrial en México (Monterrey): puede facilitar soporte y logística locales."),
        ("WEG", "Intermedia-económica", 0.92,
         "Presencia en Latinoamérica; buena relación costo-beneficio."),
        ("Hyundai Electric", "Económica", 0.85,
         "Fabricante coreano con fuerte perfil exportador; opción de menor costo."),
    ]
    filas = []
    for marca, gama, mult, nota in marcas:
        filas.append(dict(opcion=f"Nuevo - {marca}", gama=gama,
                          lo=0.75 * base * mult, hi=1.35 * base * mult,
                          plazo=plazo, notas=nota))
    filas.append(dict(opcion="Reacondicionado / de inventario certificado", gama="Alternativa rápida",
                      lo=0.50 * base, hi=0.75 * base, plazo="3-12 meses",
                      notas="Verificar pruebas de fábrica, antigüedad del aislamiento y garantía por escrito."))
    filas.append(dict(opcion="Rebobinado en taller con aislamiento mejorado", gama="Reconstrucción",
                      lo=0.40 * base, hi=0.60 * base, plazo="8-18 meses",
                      notas="Reutiliza núcleo y tanque. Especificar papel TUK/aramida y fluido éster."))
    return filas


def recomendacion_global(estado):
    return {
        "ÓPTIMO": "Mantener el equipo en servicio con monitoreo de rutina. No se requiere inversión mayor.",
        "DESGASTE NORMAL": "Mantener en servicio reforzando el monitoreo y el mantenimiento del aceite; "
                           "iniciar la planeación del reemplazo a mediano plazo.",
        "ALERTA": "Rehabilitar (aceite, enfriamiento, monitoreo) para ganar tiempo y, en paralelo, "
                  "especificar un reemplazo o rebobinado. La reparación económica por sí sola no recupera el papel.",
        "CRÍTICO": "Reemplazar (unidad nueva, reacondicionada o rebobinado). Reparar el aceite no restituye "
                   "el DP perdido; operar el equipo supone riesgo de falla catastrófica.",
    }[estado]


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
def construir_grafica_tendencia(tipo, anos_sel, temp_sel, valor_sel, factor, escala_log=False):
    """
    tipo: 'ppm' (Furanos vs Años) o 'dp' (DP vs Años).
    Curvas: Sano (60 °C), Sobrecalentado (95 °C) y Tu transformador, todas con el
    tipo de aislamiento elegido. Si no es Kraft estándar, se agrega una curva gris
    punteada con Kraft estándar a tu misma temperatura para ver el beneficio.
    """
    idx = 1 if tipo == "ppm" else 2
    anos = serie_temporal(60, factor)[0]
    y_sano = serie_temporal(60, factor)[idx]
    y_rojo = serie_temporal(95, factor)[idx]
    y_tuyo = serie_temporal(temp_sel, factor)[idx]

    fig = go.Figure()

    if tipo == "dp":
        zonas = [(DP_NUEVO, 1100, "#2ECC71"), (DP_DESGASTE, DP_NUEVO, "#F1C40F"),
                 (DP_ALERTA, DP_DESGASTE, "#E67E22"), (0, DP_ALERTA, "#E74C3C")]
        for y0, y1, col in zonas:
            fig.add_hrect(y0=y0, y1=y1, fillcolor=col, opacity=0.10, line_width=0)

    fig.add_trace(go.Scatter(x=anos, y=y_sano, mode="lines", name="Referencia Sano (60 °C)",
                             line=dict(color="#2ECC71", width=2.5, dash="dash")))
    fig.add_trace(go.Scatter(x=anos, y=y_rojo, mode="lines", name="Referencia Sobrecalentado (95 °C)",
                             line=dict(color="#E74C3C", width=2.5, dash="dash")))
    if abs(factor - 1.0) > 1e-9:
        fig.add_trace(go.Scatter(x=anos, y=serie_temporal(temp_sel, 1.0)[idx], mode="lines",
                                 name=f"Kraft estándar a {temp_sel} °C (comparación)",
                                 line=dict(color="#95A5A6", width=2, dash="dot")))
    fig.add_trace(go.Scatter(x=anos, y=y_tuyo, mode="lines", name=f"Tu Transformador ({temp_sel} °C)",
                             line=dict(color="#3498DB", width=5)))

    fig.add_trace(go.Scatter(
        x=[anos_sel], y=[valor_sel], mode="markers+text", name="Hoy",
        marker=dict(color="#FFFFFF", size=15, line=dict(color="#3498DB", width=4)),
        text=[f"{valor_sel:.2f}" if tipo == "ppm" else f"{valor_sel:.0f}"],
        textposition="top center", textfont=dict(color="#FFFFFF", size=13),
        showlegend=False,
    ))

    if tipo == "ppm":
        ppm_limite = 10 ** (1.51 - DP_ALERTA * 0.0035)
        fig.add_hline(y=ppm_limite, line=dict(color="#E74C3C", width=1.5, dash="dot"),
                      annotation_text=f"Límite crítico (DP=200 = {ppm_limite:.1f} ppm)",
                      annotation_font_color="#E74C3C", annotation_position="top left")
        titulo, eje_y = "Furanos 2-FAL vs Años de Operación", "Furanos (ppm)"
        if escala_log:
            fig.update_yaxes(type="log")
        else:
            fig.update_yaxes(range=[0, max(12, valor_sel * 1.4)])
    else:
        titulo, eje_y = "Grado de Polimerización (DP) vs Años de Operación", "DP"
        fig.update_yaxes(range=[0, 1100])

    fig.update_layout(
        template="plotly_dark", title=dict(text=titulo, font=dict(size=17)),
        xaxis_title="Años de operación", yaxis_title=eje_y,
        height=430, margin=dict(l=10, r=10, t=60, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#121820",
        legend=dict(orientation="h", yanchor="bottom", y=-0.38, x=0),
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
# 5. GENERADOR DE INFORME PDF
# -----------------------------------------------------------------------------
def figura_para_pdf(anos_sel, temp, factor, ppm, dp):
    """Gráficas (estilo impresión) para incrustar en el PDF. Devuelve un buffer PNG."""
    from matplotlib.figure import Figure

    fig = Figure(figsize=(11, 3.8))
    ax1, ax2 = fig.subplots(1, 2)
    for ax, idx, ylabel, titulo, valor in (
        (ax1, 1, "Furanos (ppm)", "Furanos vs Años", ppm),
        (ax2, 2, "DP", "DP vs Años", dp),
    ):
        anos = serie_temporal(60, factor)[0]
        if idx == 2:
            for y0, y1, col in ((DP_NUEVO, 1100, "#2ECC71"), (DP_DESGASTE, DP_NUEVO, "#F1C40F"),
                                (DP_ALERTA, DP_DESGASTE, "#E67E22"), (0, DP_ALERTA, "#E74C3C")):
                ax.axhspan(y0, y1, color=col, alpha=0.12)
        ax.plot(anos, serie_temporal(60, factor)[idx], "--", color="#27AE60", lw=2, label="Sano (60 °C)")
        ax.plot(anos, serie_temporal(95, factor)[idx], "--", color="#E74C3C", lw=2, label="Sobrecalentado (95 °C)")
        if abs(factor - 1.0) > 1e-9:
            ax.plot(anos, serie_temporal(temp, 1.0)[idx], ":", color="#7F8C8D", lw=2,
                    label=f"Kraft estándar ({temp} °C)")
        ax.plot(anos, serie_temporal(temp, factor)[idx], "-", color="#2980B9", lw=3.5, label=f"Este equipo ({temp} °C)")
        ax.scatter([anos_sel], [valor], s=90, color="white", edgecolor="#2980B9", linewidth=2.5, zorder=5)
        ax.set_title(titulo, fontsize=11, fontweight="bold")
        ax.set_xlabel("Años de operación")
        ax.set_ylabel(ylabel)
        ax.set_xlim(0, 40)
        ax.grid(True, ls=":", alpha=0.6)
        ax.legend(fontsize=7, loc="upper left" if idx == 1 else "lower left")
    ax1.set_ylim(0, max(12, ppm * 1.4))
    ax2.set_ylim(0, 1100)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=160)
    buf.seek(0)
    return buf


def generar_pdf(d):
    """Construye el informe PDF completo y devuelve sus bytes. 'd' = diccionario de datos."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    estilos = getSampleStyleSheet()
    cuerpo = ParagraphStyle("cuerpo", parent=estilos["Normal"], fontName="Helvetica", fontSize=9.5, leading=13)
    chico = ParagraphStyle("chico", parent=cuerpo, fontSize=8, leading=10)
    chico_b = ParagraphStyle("chico_b", parent=chico, fontName="Helvetica-Bold")
    h2 = ParagraphStyle("h2", parent=estilos["Heading2"], fontName="Helvetica-Bold", fontSize=13,
                        textColor=colors.HexColor("#1F3A5F"), spaceBefore=10, spaceAfter=5)
    azul = colors.HexColor("#1F3A5F")
    gris = colors.HexColor("#CBD5E1")

    def P(txt, st_=chico):
        return Paragraph(txt, st_)

    def estilo_tabla(extra=None):
        base = [("BACKGROUND", (0, 0), (-1, 0), azul), ("GRID", (0, 0), (-1, -1), 0.4, gris),
                ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4), ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F1F5F9")])]
        return TableStyle(base + (extra or []))

    def enc(txt):
        return P(f'<font color="white"><b>{txt}</b></font>')

    story = []
    nombre = esc(d["nombre"])

    # ---- Encabezado ----
    cab = Table([[P(f'<font color="white" size="16"><b>INFORME DE DIAGNÓSTICO PREDICTIVO</b></font><br/>'
                    f'<font color="white" size="10">Transformador {nombre}</font>', cuerpo),
                  P(f'<font color="white" size="9">Fecha: {d["fecha"]}</font>', cuerpo)]],
                colWidths=[14 * cm, 4 * cm])
    cab.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), azul), ("TOPPADDING", (0, 0), (-1, -1), 10),
                             ("BOTTOMPADDING", (0, 0), (-1, -1), 10), ("LEFTPADDING", (0, 0), (-1, -1), 10)]))
    story += [cab, Spacer(1, 8)]

    # ---- Ficha técnica ----
    bil = f'{d["bil"]} kV (típico)' if d["bil"] else "N/D"
    ficha = [[enc("Dato"), enc("Valor"), enc("Dato"), enc("Valor")],
             [P("<b>Nombre / ID</b>"), P(nombre), P("<b>Años de operación</b>"), P(f'{d["anos"]}')],
             [P("<b>Tensión nominal AT</b>"), P(f'{d["kv"]:g} kV'), P("<b>Temperatura nominal</b>"), P(f'{d["temp"]} °C')],
             [P("<b>BIL</b>"), P(bil), P("<b>Potencia nominal</b>"), P(f'{d["mva"]:g} MVA')],
             [P("<b>Aislamiento</b>"), P(esc(d["aislamiento"])), P("<b>Factor de envejecimiento</b>"),
              P(f'{d["factor"]:.2f} (1.00 = Kraft estándar)')]]
    t = Table(ficha, colWidths=[3.6 * cm, 5.4 * cm, 3.8 * cm, 5.2 * cm])
    t.setStyle(estilo_tabla())
    story += [Paragraph("1. Ficha técnica del equipo", h2), t]

    # ---- Resultados ----
    vida = "Sin degradación (T = 50 °C)" if d["anos_rest"] is None else f'{d["anos_rest"]:.1f} años'
    res = [[enc("DP estimado"), enc("Furanos 2-FAL"), enc("Resistencia mecánica"), enc("Vida hasta DP = 200"), enc("Estado")],
           [P(f'<font size="13"><b>{d["dp"]:.0f}</b></font>'), P(f'<font size="13"><b>{d["ppm"]:.3f} ppm</b></font>'),
            P(f'<font size="13"><b>{d["resistencia"]:.0f} %</b></font>'), P(f'<font size="11"><b>{vida}</b></font>'),
            P(f'<font size="11" color="{d["color_estado"]}"><b>{d["estado"]}</b></font>')]]
    t = Table(res, colWidths=[3 * cm, 3.4 * cm, 3.8 * cm, 4.2 * cm, 3.6 * cm])
    t.setStyle(estilo_tabla())
    story += [Paragraph("2. Resultados del diagnóstico", h2), t, Spacer(1, 4)]

    diag = (f"Tras {d['anos']} años de operación a {d['temp']} °C con aislamiento <i>{esc(d['aislamiento'])}</i>, "
            f"el transformador {nombre} presenta un DP estimado de <b>{d['dp']:.0f}</b> y "
            f"<b>{d['ppm']:.3f} ppm</b> de furanos, lo que equivale a una resistencia mecánica residual de "
            f"<b>{d['resistencia']:.0f} %</b>. Estado: <b>{d['estado']}</b>. "
            f"<b>Recomendación general:</b> {recomendacion_global(d['estado'])}")
    story.append(Paragraph(diag, cuerpo))
    if d["aramida"]:
        story.append(Spacer(1, 3))
        story.append(Paragraph("<b>Aviso:</b> la aramida no genera furanos; el diagnóstico basado en furanos "
                               "debe complementarse con DGA y pruebas directas del papel.", cuerpo))

    # ---- Gráficas ----
    story += [Paragraph("3. Tendencias de vida útil", h2),
              Image(figura_para_pdf(d["anos"], d["temp"], d["factor"], d["ppm"], d["dp"]),
                    width=18 * cm, height=18 * cm * 3.8 / 11)]

    # ---- Plan de acción ----
    colores_prio = {"Inmediata": ("#E74C3C", "white"), "Alta": ("#E67E22", "white"),
                    "Media": ("#F1C40F", "black"), "Baja": ("#2ECC71", "black")}
    filas = [[enc("Prioridad"), enc("Acción y justificación"), enc("Plazo"), enc("Costo estimado (USD)")]]
    extra = []
    for n, a in enumerate(d["acciones"], start=1):
        fondo, txt = colores_prio[a["prioridad"]]
        filas.append([P(f'<font color="{txt}"><b>{a["prioridad"]}</b></font>'),
                      P(f'<b>{esc(a["accion"])}</b><br/>{esc(a["detalle"])}'),
                      P(esc(a["plazo"])), P(fmt_rango(a["lo"], a["hi"]))])
        extra.append(("BACKGROUND", (0, n), (0, n), colors.HexColor(fondo)))
    t = Table(filas, colWidths=[2.2 * cm, 9 * cm, 2.6 * cm, 4.2 * cm], repeatRows=1)
    t.setStyle(estilo_tabla(extra))
    story += [Paragraph("4. Plan de acción recomendado (mejorar o reparar)", h2), t]

    # ---- Reemplazo ----
    filas = [[enc("Opción"), enc("Gama"), enc("Costo estimado (USD)"), enc("Plazo"), enc("Notas")]]
    for o in d["opciones"]:
        filas.append([P(f'<b>{esc(o["opcion"])}</b>'), P(esc(o["gama"])), P(fmt_rango(o["lo"], o["hi"])),
                      P(esc(o["plazo"])), P(esc(o["notas"]))])
    t = Table(filas, colWidths=[3.8 * cm, 2.3 * cm, 4 * cm, 2.2 * cm, 5.7 * cm], repeatRows=1)
    t.setStyle(estilo_tabla())
    story += [Paragraph(f'5. Opciones de reemplazo o reconstrucción ({d["mva"]:g} MVA, {d["kv"]:g} kV)', h2), t,
              Spacer(1, 4),
              Paragraph(f'Referencia: un transformador nuevo equivalente se estima en aprox. '
                        f'<b>{fmt_usd(d["costo_base"])}</b> (valor central), con una variación típica de -25 % a +35 % '
                        f'según marca, especificación, enfriamiento, pruebas y transporte.', cuerpo)]

    # ---- Notas ----
    story += [Paragraph("6. Notas y limitaciones", h2),
              Paragraph(
                  "• El DP y los furanos se calculan con un modelo simplificado (tasa de degradación exponencial "
                  "con la temperatura y la correlación DP-furanos de Chendong). Es una herramienta de apoyo para "
                  "priorizar; <b>no sustituye</b> el análisis de laboratorio (DGA, furanos medidos, DP directo) ni la "
                  "inspección de un especialista.<br/>"
                  "• Los factores de tipo de aislamiento son aproximaciones ilustrativas.<br/>"
                  "• Los costos son <b>orientativos</b>, en USD, calibrados con rangos públicos recientes del mercado "
                  "(2024-2026); los precios de transformadores han subido de forma muy marcada desde 2020 y los plazos "
                  "de entrega de unidades grandes rondan los 2.5 a 3 años. Los rangos por marca son una referencia de "
                  "gama, no una cotización: solicita cotizaciones formales a cada fabricante.<br/>"
                  "• Los resultados deben validarse antes de tomar decisiones de inversión u operación.", cuerpo)]

    def pie(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#64748B"))
        canvas.drawString(1.8 * cm, 1.1 * cm, f"Diagnóstico predictivo - {d['nombre']} - {d['fecha']}")
        canvas.drawRightString(letter[0] - 1.8 * cm, 1.1 * cm, f"Página {doc.page}")
        canvas.restoreState()

    salida = io.BytesIO()
    doc = SimpleDocTemplate(salida, pagesize=letter, leftMargin=1.8 * cm, rightMargin=1.8 * cm,
                            topMargin=1.5 * cm, bottomMargin=1.8 * cm,
                            title=f"Informe {d['nombre']}", author="Dashboard de Mantenimiento Predictivo")
    doc.build(story, onFirstPage=pie, onLaterPages=pie)
    return salida.getvalue()


# -----------------------------------------------------------------------------
# 6. BARRA LATERAL (ENTRADAS)
# -----------------------------------------------------------------------------
with st.sidebar:
    st.header("🏷️ Identificación del Equipo")
    nombre = st.text_input("Nombre / ID del transformador", value="TR-01", max_chars=40).strip() or "SIN-NOMBRE"
    opcion_kv = st.selectbox("Tensión nominal AT (kV)", [f"{v:g}" for v in TENSIONES_KV] + ["Otra"], index=4)
    if opcion_kv == "Otra":
        kv = float(st.number_input("Tensión AT (kV)", min_value=1.0, max_value=800.0, value=115.0, step=1.0))
    else:
        kv = float(opcion_kv)
    mva = float(st.number_input("Potencia nominal (MVA)", min_value=5.0, max_value=500.0, value=30.0, step=5.0))

    st.header("🧪 Aislamiento")
    tipo_aislamiento = st.selectbox("Tipo de aislamiento", list(TIPOS_AISLAMIENTO))
    info_aisl = TIPOS_AISLAMIENTO[tipo_aislamiento]
    factor = info_aisl["factor"]
    st.caption(f"{info_aisl['desc']}  \nFactor de envejecimiento: **{factor:.2f}** (1.00 = Kraft estándar)")

    st.header("⚙️ Parámetros Operativos")
    anos = st.slider("Años de Operación", 0, 40, 10)
    temp = st.slider("Temperatura Nominal (°C)", 50, 120, 85)
    st.divider()
    escala_log = st.checkbox("Escala logarítmica en gráfica de Furanos", value=False)
    st.divider()
    st.caption("**Modelo utilizado**")
    st.code(
        "tasa = (T - 50) * 0.0038 * factor\n"
        "ppm  = 0.01 * exp(tasa * años)\n"
        "DP   = (1.51 - log10(ppm)) / 0.0035",
        language="text",
    )
    st.caption("Resistencia mecánica = DP / 800 (máx. 100 %).")

# -----------------------------------------------------------------------------
# 7. CÁLCULOS PRINCIPALES
# -----------------------------------------------------------------------------
ppm_actual, dp_actual, resistencia_actual = calcular_salud(anos, temp, factor)
estado, color_estado, color_3d = clasificar_estado(dp_actual)
anos_restantes = anos_hasta_dp_critico(temp, anos, factor)
bil = bil_tipico(kv)
es_aramida = tipo_aislamiento.startswith("Aramida")

# -----------------------------------------------------------------------------
# 8. SECCIÓN 1: ENCABEZADO Y TARJETAS DE MÉTRICAS
# -----------------------------------------------------------------------------
st.title("⚡ Diagnóstico Predictivo de Transformador de Potencia")
st.markdown(
    f"""<div class="estado-card" style="text-align:left">
    <span style="font-size:1.25rem;font-weight:800;color:#FFFFFF">{esc(nombre)}</span>
    &nbsp;·&nbsp; <b>{kv:g} kV</b> (BIL típico: {bil if bil else 'N/D'} kV)
    &nbsp;·&nbsp; <b>{mva:g} MVA</b>
    &nbsp;·&nbsp; {esc(tipo_aislamiento)}</div>""",
    unsafe_allow_html=True,
)
st.write("")

if es_aramida:
    st.warning("ℹ️ La aramida (Nomex) no genera furanos: los valores de furanos/DP son solo "
               "referenciales. Complementa con DGA y pruebas directas del papel.")

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
# 9. SECCIÓN 2: MODELO 3D INTERACTIVO + BOTÓN INRUSH
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
# 10. SECCIÓN 3: GRÁFICAS DE TENDENCIA 2D
# -----------------------------------------------------------------------------
st.header("📈 Tendencias de Vida Útil")
g1, g2 = st.columns(2)
with g1:
    mostrar_plotly(construir_grafica_tendencia("ppm", anos, temp, ppm_actual, factor, escala_log))
with g2:
    mostrar_plotly(construir_grafica_tendencia("dp", anos, temp, dp_actual, factor))

st.caption("🟢 Sano (60 °C) · 🔴 Sobrecalentado (95 °C) · 🔵 Tu transformador (temperatura del slider). "
           "El punto blanco marca el año seleccionado.")

st.divider()

# -----------------------------------------------------------------------------
# 11. SECCIÓN 4: PLAN DE ACCIÓN, REEMPLAZO E INFORME PDF
# -----------------------------------------------------------------------------
st.header("🛠️ Plan de Acción y Opciones de Reemplazo")
st.info(f"**Recomendación general:** {recomendacion_global(estado)}")

acciones = generar_acciones(estado, temp, anos_restantes, factor, mva, kv)
opciones = opciones_reemplazo(mva, kv)
costo_base = costo_nuevo_base(mva, kv)

tab_plan, tab_reemplazo = st.tabs(["🔧 Mejorar / Reparar", "🔁 Reemplazar (marcas de referencia)"])
with tab_plan:
    df_plan = pd.DataFrame([{
        "Prioridad": a["prioridad"], "Acción": a["accion"], "Plazo": a["plazo"],
        "Costo estimado (USD)": fmt_rango(a["lo"], a["hi"]), "Detalle": a["detalle"],
    } for a in acciones])
    df_plan.index = range(1, len(df_plan) + 1)
    st.table(df_plan)

with tab_reemplazo:
    st.caption(f"Transformador nuevo equivalente ({mva:g} MVA, {kv:g} kV): valor central aprox. "
               f"**{fmt_usd(costo_base)}**. Los rangos por marca son referencias de gama, NO cotizaciones.")
    df_op = pd.DataFrame([{
        "Opción": o["opcion"], "Gama": o["gama"], "Costo estimado (USD)": fmt_rango(o["lo"], o["hi"]),
        "Plazo": o["plazo"], "Notas": o["notas"],
    } for o in opciones])
    df_op.index = range(1, len(df_op) + 1)
    st.table(df_op)

st.subheader("📄 Informe PDF")
st.write("Genera un informe con la ficha del equipo, el diagnóstico, las gráficas, el plan de acción "
         "y las opciones de reemplazo con costos orientativos.")

firma = (nombre, kv, mva, tipo_aislamiento, anos, temp)
if st.button("📄 Generar informe PDF"):
    with st.spinner("Generando informe..."):
        datos_pdf = dict(
            nombre=nombre, kv=kv, mva=mva, bil=bil, aislamiento=tipo_aislamiento, factor=factor,
            anos=anos, temp=temp, ppm=ppm_actual, dp=dp_actual, resistencia=resistencia_actual,
            estado=estado, color_estado=color_estado, anos_rest=anos_restantes, aramida=es_aramida,
            acciones=acciones, opciones=opciones, costo_base=costo_base,
            fecha=datetime.date.today().strftime("%d/%m/%Y"),
        )
        try:
            st.session_state["pdf_bytes"] = generar_pdf(datos_pdf)
            st.session_state["pdf_firma"] = firma
        except Exception as error:  # robustez: nunca romper el dashboard por el PDF
            st.error(f"No se pudo generar el PDF: {error}")

if st.session_state.get("pdf_firma") == firma:
    nombre_archivo = re.sub(r"[^A-Za-z0-9_-]+", "_", nombre).strip("_") or "Transformador"
    st.download_button(
        "⬇️ Descargar informe PDF", data=st.session_state["pdf_bytes"],
        file_name=f"Informe_{nombre_archivo}_{datetime.date.today():%Y%m%d}.pdf",
        mime="application/pdf",
    )
elif "pdf_firma" in st.session_state:
    st.info("Cambiaste los parámetros desde el último informe. Genera uno nuevo para actualizarlo.")
