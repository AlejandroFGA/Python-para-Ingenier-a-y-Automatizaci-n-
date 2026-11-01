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
import time
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
    page_title="TecnoAutoElectroG | Diagnóstico de Transformadores",
    page_icon="⚡",
    initial_sidebar_state="expanded",
)
 
# Fragmentos: permiten que un botón actualice SOLO su sección (mucho más rápido).
fragmento = getattr(st, "fragment", None) or getattr(st, "experimental_fragment", None) or (lambda f: f)
 
CSS_BASE = """
<style>
:root{--borde:#243044;--txt:#E6EDF3;--sub:#93A4B8;}
.stApp{background:radial-gradient(1200px 600px at 8% -10%, #14213a 0%, #0B0F17 55%) no-repeat, #0B0F17;
       color:var(--txt);font-family:'Segoe UI','Inter','Helvetica Neue',Arial,sans-serif;}
#MainMenu, footer{visibility:hidden;}
header[data-testid="stHeader"]{background:transparent;}
[data-testid="stSidebar"]{background:#0F151E;border-right:1px solid var(--borde);}
.block-container{padding-top:1.2rem;max-width:1500px;}
h1,h2,h3,h4{color:#FFFFFF;}
 
.hero{background:linear-gradient(120deg,#0f2a44 0%,#1b4f72 55%,#0e7490 100%);border-radius:18px;
      padding:22px 28px;border:1px solid #2b5d86;box-shadow:0 8px 30px rgba(0,0,0,.45);margin-bottom:16px;}
.hero-top{display:flex;justify-content:space-between;color:#BFE3FF;font-size:.85rem;
          letter-spacing:.14em;text-transform:uppercase;font-weight:700;}
.hero h1{margin:.35rem 0 .75rem;font-size:2.05rem;color:#fff;font-weight:800;padding:0;}
.chip{display:inline-block;background:rgba(255,255,255,.13);border:1px solid rgba(255,255,255,.25);
      color:#fff;border-radius:999px;padding:4px 13px;margin:2px 6px 2px 0;font-size:.86rem;}
 
.kpi{background:linear-gradient(160deg,#18212e,#10161f);border:1px solid var(--borde);
     border-top:4px solid var(--ac);border-radius:14px;padding:14px 16px;
     box-shadow:0 4px 16px rgba(0,0,0,.4);height:100%;}
.kpi-l{color:var(--sub);font-size:.76rem;text-transform:uppercase;letter-spacing:.08em;font-weight:600;}
.kpi-v{color:var(--ac);font-size:2rem;font-weight:800;line-height:1.15;margin-top:2px;}
.kpi-s{color:var(--sub);font-size:.8rem;}
.barra{height:7px;background:#243044;border-radius:6px;margin-top:8px;overflow:hidden;}
.barra div{height:100%;border-radius:6px;}
 
.aviso{border-radius:12px;padding:12px 18px;margin:14px 0 4px;border:1px solid var(--ac);
       background:linear-gradient(90deg,rgba(255,255,255,.05),rgba(255,255,255,.01));
       border-left:6px solid var(--ac);color:#E6EDF3;font-size:1rem;}
 
.sec{margin:26px 0 10px;padding-left:14px;border-left:6px solid #38BDF8;}
.sec-t{font-size:1.55rem;font-weight:800;color:#fff;}
.sec-s{color:var(--sub);font-size:.95rem;}
 
.paso{background:#121923;border:1px solid var(--borde);border-left:6px solid var(--ac);
      border-radius:12px;padding:12px 18px;margin:8px 0;animation:entra .5s ease;}
.paso-t{font-weight:800;color:#fff;font-size:1.08rem;}
.paso-x{color:#C5D2E0;font-size:.97rem;margin-top:2px;}
@keyframes entra{from{opacity:0;transform:translateY(10px);}to{opacity:1;transform:none;}}
 
.veredicto{border-radius:16px;padding:18px 24px;margin:14px 0;border:2px solid var(--ac);
           background:linear-gradient(120deg,rgba(255,255,255,.07),rgba(255,255,255,.01));
           box-shadow:0 0 28px rgba(0,0,0,.45), 0 0 18px var(--ac);animation:entra .6s ease;}
.v-t{font-size:1.8rem;font-weight:900;color:var(--ac);}
.v-s{font-size:1.02rem;color:#E6EDF3;margin-top:4px;}
 
.callout{background:#121923;border:1px solid var(--borde);border-radius:12px;padding:14px 18px;margin:10px 0;color:#D5DEE9;}
.guion{background:linear-gradient(120deg,#12301f,#10201a);border:1px solid #1f6b3f;border-radius:12px;
       padding:16px 20px;margin:12px 0;color:#E6F7EC;font-size:1.02rem;}
.guion b{color:#7CF0A8;}
 
.tabla-comp{width:100%;border-collapse:collapse;margin:8px 0;}
.tabla-comp th{background:#1B2A3F;color:#fff;text-align:left;padding:8px 12px;font-size:.85rem;
               text-transform:uppercase;letter-spacing:.05em;}
.tabla-comp td{border-bottom:1px solid var(--borde);padding:9px 12px;font-size:.93rem;color:#D5DEE9;vertical-align:top;}
.tabla-comp tr:hover td{background:rgba(56,189,248,.06);}
 
[data-testid="stTable"] table{border-collapse:collapse;width:100%;}
[data-testid="stTable"] th{background:#1B2A3F;color:#fff;}
[data-testid="stTable"] td, [data-testid="stTable"] th{border:1px solid #243044;padding:6px 10px;font-size:.86rem;}
 
.leyenda-dot{display:inline-block;width:12px;height:12px;border-radius:50%;margin-right:8px;border:1px solid #555;}
.pie{text-align:center;color:#6B7C93;font-size:.8rem;margin:34px 0 8px;letter-spacing:.06em;}
</style>
"""
st.markdown(CSS_BASE, unsafe_allow_html=True)
 
CSS_PRESENTACION = """
<style>
.kpi-v{font-size:2.6rem !important;} .kpi-l{font-size:.9rem !important;}
.paso-t{font-size:1.35rem !important;} .paso-x{font-size:1.15rem !important;}
.v-t{font-size:2.3rem !important;} .v-s{font-size:1.2rem !important;}
.guion{font-size:1.2rem !important;} .tabla-comp td{font-size:1.05rem !important;}
.sec-t{font-size:1.9rem !important;} .hero h1{font-size:2.4rem !important;}
</style>
"""
 
 
def seccion(titulo, subtitulo=""):
    """Encabezado de sección con barra de acento."""
    st.markdown(f'<div class="sec"><div class="sec-t">{titulo}</div>'
                f'<div class="sec-s">{subtitulo}</div></div>', unsafe_allow_html=True)
 
 
def kpi(etiqueta, valor, sub="", color="#38BDF8", barra=None):
    """Tarjeta KPI con color de acento y barra opcional (0-100)."""
    b = (f'<div class="barra"><div style="width:{max(0, min(100, barra)):.0f}%;background:{color}"></div></div>'
         if barra is not None else "")
    return (f'<div class="kpi" style="--ac:{color}"><div class="kpi-l">{etiqueta}</div>'
            f'<div class="kpi-v">{valor}</div><div class="kpi-s">{sub}</div>{b}</div>')
 
 
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
 
EMPRESA = "TecnoAutoElectroG"   # Empresa (ficticia) que firma los informes
 
# Casos de ejemplo (SOLO LECTURA): edificios con tensiones y estados distintos.
# Permiten darse una idea de cómo se comporta cada nivel de desgaste.
EJEMPLOS = [
    dict(id="ej_a", nombre="Edificio A - Hospital Regional", kv=13.8, mva=10.0,
         aislamiento="Papel TUK + aceite éster natural", anos=12, temp=65),
    dict(id="ej_b", nombre="Edificio B - Centro Comercial", kv=34.5, mva=25.0,
         aislamiento="Papel Kraft estándar + aceite mineral", anos=25, temp=80),
    dict(id="ej_c", nombre="Edificio C - Planta Industrial", kv=69.0, mva=50.0,
         aislamiento="Papel Kraft estándar + aceite mineral", anos=32, temp=95),
    dict(id="ej_d", nombre="Edificio D - Torre Corporativa", kv=115.0, mva=60.0,
         aislamiento="Papel Kraft estándar + aceite mineral", anos=35, temp=100),
]
 
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
        ("Siemens Energy", "Premium", 1.14,
         "Gran experiencia en alta tensión; opción premium."),
        ("Prolec GE", "Intermedia", 1.00,
         "Con operación industrial en México (Monterrey): puede facilitar soporte y logística locales."),
        ("WEG", "Intermedia-económica", 0.94,
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
 
 
# ------------------------- ANÁLISIS DEL EVENTO INRUSH -------------------------
# Modelo DIDÁCTICO: el Inrush se supone de 8 veces la corriente nominal (rango típico
# 5-12x). La fuerza sobre los devanados es proporcional a I^2 -> 8^2 = 64 veces la
# normal. Un papel nuevo se supone capaz de soportar 4 veces esa fuerza (256 unidades) y
# su capacidad baja en proporción a la resistencia mecánica residual. Con esto:
#       factor de seguridad (FS) = capacidad / fuerza = resistencia% / 25
# FS >= 2 sin daño | 1 < FS < 2 comprometido | FS <= 1 falla (equivale a DP < 200).
MULT_INRUSH = 8.0
CAPACIDAD_DISENO = 256.0
 
# (icono, color de pantalla, texto) por estado de componente
ESTADOS_COMP = {"ok": ("✅", "#2ECC71", "SIN DAÑO"), "warn": ("⚠️", "#F1C40F", "AFECTADO"),
                "fail": ("❌", "#E74C3C", "FALLA"), "info": ("ℹ️", "#38BDF8", "INFO")}
COLOR_PDF = {"ok": "#15803D", "warn": "#B45309", "fail": "#B91C1C", "info": "#0369A1"}
 
 
def analizar_inrush(nombre, kv, mva, aislamiento, anos, temp, factor, ppm, dp, res):
    """Explica QUÉ pasa en un Inrush, POR QUÉ y QUÉ componentes se afectan."""
    i_nom = mva * 1e6 / (math.sqrt(3) * kv * 1e3)       # corriente de línea nominal (A)
    i_pico = MULT_INRUSH * i_nom
    fuerza = MULT_INRUSH ** 2
    capacidad = CAPACIDAD_DISENO * res / 100.0
    fs = capacidad / fuerza
 
    if fs >= 2.0:
        nivel, veredicto, icono, color = "ok", "SIN DAÑO PERMANENTE", "✅", "#2ECC71"
        resumen = "El papel aislante resiste el esfuerzo con margen suficiente."
    elif fs > 1.0:
        nivel, veredicto, icono, color = "warn", "AISLAMIENTO COMPROMETIDO", "⚠️", "#F39C12"
        resumen = "El aislamiento resiste, pero con margen insuficiente: queda con daño acumulado."
    else:
        nivel, veredicto, icono, color = "fail", "CORTOCIRCUITO CATASTRÓFICO", "💥", "#E74C3C"
        resumen = "La fuerza supera lo que el papel degradado puede soportar: el aislamiento se rompe."
 
    texto_resultado = {
        "ok": "El papel resiste con margen: el equipo queda sin daño permanente.",
        "warn": "El margen es insuficiente: el aislamiento resiste pero acumula daño y queda más expuesto al siguiente evento.",
        "fail": "La fuerza supera la capacidad del papel: el aislamiento entre espiras se rompe y el equipo falla.",
    }[nivel]
 
    pasos = [
        ("⚡", "Energización del transformador",
         f"Se cierra el interruptor en {kv:g} kV. El flujo remanente del núcleo y el instante de cierre lo llevan "
         "a saturación: el equipo absorbe una corriente de magnetización mucho mayor que la nominal."),
        ("📈", f"Corriente Inrush: {i_pico:,.0f} A",
         f"Equivale a unas {MULT_INRUSH:.0f} veces la corriente nominal ({i_nom:,.0f} A para {mva:g} MVA a {kv:g} kV). "
         "Son pulsos de un solo sentido, ricos en armónicos, que decaen en pocos segundos."),
        ("🧲", f"Fuerza electrodinámica: {fuerza:.0f} veces la normal",
         f"La fuerza sobre los devanados es proporcional al cuadrado de la corriente (F = k·I²): "
         f"{MULT_INRUSH:.0f}² = {fuerza:.0f}. Empuja y comprime los devanados en dirección radial y axial, "
         "haciéndolos vibrar al doble de la frecuencia de red."),
        ("🧪", f"Causa raíz: aislamiento con DP {dp:.0f}",
         f"Tras {anos} años a {temp} °C con {aislamiento}, el papel generó {ppm:.3f} ppm de furanos y quedó con "
         f"{res:.0f} % de su resistencia mecánica. Su capacidad de soporte es {capacidad:.0f} unidades "
         f"frente a {fuerza:.0f} aplicadas."),
        ("⚖️", f"Resultado: factor de seguridad {fs:.2f}", texto_resultado),
    ]
 
    comps = {
        "ok": [
            ("Devanados (cobre)", "Vibración leve a doble frecuencia; sin deformación permanente.", "ok"),
            ("Papel aislante entre espiras", f"Esfuerzo dentro de su capacidad (FS = {fs:.2f}); sin microfisuras.", "ok"),
            ("Espaciadores y prensado", "La presión de sujeción se mantiene.", "ok"),
            ("Núcleo", "Saturación momentánea; sin daño.", "ok"),
            ("Aceite y tanque", "Sin generación anormal de gases.", "ok"),
            ("Protección diferencial", "La restricción por 2ª armónica evita un disparo falso durante el Inrush.", "info"),
        ],
        "warn": [
            ("Devanados (cobre)", "Desplazamiento axial/radial temporal; posible aflojamiento de espiras.", "warn"),
            ("Papel aislante entre espiras", f"Microfisuras y pérdida de adherencia; margen de solo FS = {fs:.2f}.", "warn"),
            ("Espaciadores y prensado", "Pérdida parcial de la presión de sujeción.", "warn"),
            ("Núcleo", "Saturación momentánea; sin daño.", "ok"),
            ("Aceite y tanque", "Posibles trazas de gases (H2, C2H2): hacer análisis DGA.", "warn"),
            ("Protección diferencial", "Si hubo deformación, podría disparar en la próxima energización.", "info"),
        ],
        "fail": [
            ("Devanados (cobre)", "Deformación por pandeo radial y axial: fuerza mayor que la que resiste.", "fail"),
            ("Papel aislante entre espiras", f"Ruptura del papel (FS = {fs:.2f} menor a 1): cortocircuito entre espiras.", "fail"),
            ("Espaciadores y prensado", "Pérdida de sujeción: los devanados quedan libres de moverse.", "fail"),
            ("Núcleo", "Daño secundario por la falla (calentamiento localizado).", "warn"),
            ("Aceite y tanque", "El arco genera gases (acetileno) y sobrepresión: riesgo de ruptura del tanque.", "fail"),
            ("Protección diferencial", "Disparo por diferencial/Buchholz: salida de servicio del equipo.", "fail"),
        ],
    }[nivel]
 
    _, dp_sano, res_sano = calcular_salud(anos, 60, factor)
    fs_sano = CAPACIDAD_DISENO * res_sano / 100.0 / fuerza
    ratio_t = max(temp - 50, 0) / 10.0
    causas = [f"{anos} años de operación",
              (f"{temp} °C: degradación {ratio_t:.1f} veces más rápida que a 60 °C" if temp > 50
               else "50 °C: sin degradación térmica en este modelo"),
              f"{aislamiento} (factor de envejecimiento {factor:.2f})"]
    contrafactual = (f"Con los mismos {anos} años pero operando a 60 °C, el DP sería {dp_sano:.0f} "
                     f"({res_sano:.0f} % de resistencia) y el factor de seguridad {fs_sano:.2f}.")
 
    guion = {
        "ok": (f"Al energizar el transformador {nombre} se produjo una corriente de arranque (Inrush) de unos "
               f"{i_pico:,.0f} A, cerca de {MULT_INRUSH:.0f} veces la nominal. Esa corriente genera fuerzas sobre los "
               f"devanados proporcionales a su cuadrado, unas {fuerza:.0f} veces las normales. Como el papel conserva "
               f"{res:.0f} % de su resistencia (DP {dp:.0f}), su capacidad es {fs:.1f} veces la fuerza aplicada: "
               "resistió sin daño."),
        "warn": (f"Al energizar el transformador {nombre} la corriente de arranque llegó a unos {i_pico:,.0f} A "
                 f"({MULT_INRUSH:.0f} veces la nominal) y generó fuerzas de {fuerza:.0f} veces las normales. El papel, "
                 f"con DP {dp:.0f} y {res:.0f} % de resistencia, solo tiene {fs:.1f} veces de margen: aguantó, "
                 "pero quedó con daño acumulado. Conviene hacer DGA y FRA y planear el mantenimiento."),
        "fail": (f"Al energizar el transformador {nombre} la corriente de arranque llegó a unos {i_pico:,.0f} A "
                 f"({MULT_INRUSH:.0f} veces la nominal) y generó fuerzas de {fuerza:.0f} veces las normales. El papel, "
                 f"con DP {dp:.0f}, conserva apenas {res:.0f} % de su resistencia: su capacidad es {fs:.2f} veces la "
                 "fuerza aplicada (menor a 1). Se rompió el aislamiento entre espiras y ocurrió el cortocircuito."),
    }[nivel]
 
    return dict(
        i_nom=i_nom, i_pico=i_pico, fuerza_rel=fuerza, capacidad=capacidad, fs=fs, nivel=nivel,
        veredicto=veredicto, icono=icono, color=color, resumen=resumen, pasos=pasos, componentes=comps,
        causas=causas, contrafactual=contrafactual, guion=guion,
        amplitud=0.06 + 0.45 * (1 - res / 100.0),
        nota_modelo=("Modelo didáctico: se supone un Inrush de 8 veces la corriente nominal (rango típico 5 a 12 "
                     "veces) y que un papel nuevo soporta 4 veces la fuerza de ese evento; el factor de seguridad "
                     "baja en proporción a la resistencia mecánica residual. No sustituye un estudio de fuerzas "
                     "del fabricante."),
    )
 
 
# -----------------------------------------------------------------------------
# 3. MODELO 3D REALISTA (MALLAS FUSIONADAS: POCAS TRAZAS = POCA RAM Y GPU)
# -----------------------------------------------------------------------------
# Idea de optimización: en vez de ~45 superficies sueltas (cada una con su propio
# búfer en la GPU), todo se fusiona en ~14 mallas Mesh3d con color por vértice
# (intensidad + escala de color). Menos trazas = menos memoria y menos trabajo.
def oscurecer(hex_color, factor):
    """Multiplica el brillo de un color hex (factor < 1 oscurece, > 1 aclara)."""
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    return "#{:02X}{:02X}{:02X}".format(
        *(max(0, min(255, int(c * factor))) for c in (r, g, b))
    )
 
 
LUZ_MALLA = dict(ambient=0.50, diffuse=0.85, specular=0.40, roughness=0.50, fresnel=0.20)
LUZ_PLANA = dict(ambient=0.55, diffuse=0.85, specular=0.45, roughness=0.40, fresnel=0.15)
POS_LUZ = dict(x=3000, y=-3500, z=4500)
 
# Niveles de calidad (más vértices = más bonito pero más RAM/GPU)
CALIDADES_3D = {
    "Ligera (PC modesta)": dict(n_theta=28, filas_hv=30, filas_lv=24, turns_hv=6, turns_lv=5),
    "Equilibrada": dict(n_theta=36, filas_hv=56, filas_lv=44, turns_hv=12, turns_lv=9),
    "Alta calidad": dict(n_theta=56, filas_hv=110, filas_lv=88, turns_hv=22, turns_lv=17),
}
CALIDAD_ANIMACION = "Ligera (PC modesta)"   # la vibración Inrush usa la malla ligera
 
# Tanque y entorno
TANQUE = dict(x=8.5, y=4.2, z0=-6.0, z1=9.8)
POS_FASES = (-5.0, 0.0, 5.0)
 
 
class Malla:
    """Acumula vértices (x, y, z, intensidad) y triángulos para fusionarlos en UNA sola
    traza Mesh3d. Las rejillas se cierran en la dirección angular (sin costura)."""
 
    def __init__(self):
        self._v, self._f, self.n = [], [], 0
        self._cache = None
 
    def rejilla(self, X, Y, Z, I, invertir=False):
        """Añade una rejilla (filas x columnas). Orientación por defecto: normal hacia afuera
        cuando las filas avanzan en z y las columnas en ángulo creciente."""
        filas, cols = X.shape
        idx = np.arange(filas * cols).reshape(filas, cols) + self.n
        a, b = idx[:-1, :], np.roll(idx, -1, axis=1)[:-1, :]
        c, d = idx[1:, :], np.roll(idx, -1, axis=1)[1:, :]
        f = np.vstack([np.stack([a, b, c], -1).reshape(-1, 3), np.stack([b, d, c], -1).reshape(-1, 3)])
        if invertir:
            f = f[:, [0, 2, 1]]
        self._v.append(np.stack([X.ravel(), Y.ravel(), Z.ravel(), I.ravel()], 1))
        self._f.append(f)
        self.n += filas * cols
        self._cache = None
 
    def arrays(self):
        if self._cache is None:
            tipo_idx = np.uint16 if self.n < 65535 else np.int32   # índices compactos: la mitad de peso
            self._cache = (np.vstack(self._v).astype(np.float32), np.vstack(self._f).astype(tipo_idx))
        return self._cache
 
    def traza(self, escala, dx=0.0, dy=0.0, luz=None):
        V, F = self.arrays()
        return go.Mesh3d(
            x=V[:, 0] + np.float32(dx), y=V[:, 1] + np.float32(dy), z=V[:, 2],
            i=F[:, 0], j=F[:, 1], k=F[:, 2], intensity=V[:, 3], intensitymode="vertex",
            colorscale=escala, cmin=0, cmax=1, showscale=False, flatshading=False,
            lighting=luz or LUZ_MALLA, lightposition=POS_LUZ, hoverinfo="skip",
        )
 
 
def escala_plana(color):
    return [[0.0, color], [1.0, color]]
 
 
def cilindro(m, xc, yc, r, z0, z1, n, inten):
    """Cilindro macizo (lado + tapas) dentro de una Malla."""
    th = np.linspace(0, 2 * np.pi, n, endpoint=False)
    T, Z = np.meshgrid(th, [z0, z1])
    m.rejilla(xc + r * np.cos(T), yc + r * np.sin(T), Z, np.full_like(Z, inten))
    Ta, Ra = np.meshgrid(th, [0.0, r])
    for zc in (z0, z1):
        m.rejilla(xc + Ra * np.cos(Ta), yc + Ra * np.sin(Ta), np.full_like(Ra, zc),
                  np.full_like(Ra, inten), invertir=(zc == z1))
 
 
def malla_devanado(xc, q):
    """
    Una fase completa en UNA malla: devanado de alta (exterior) y baja tensión (interior)
    con espiras onduladas, canales de enfriamiento (franjas oscuras) y anillos de cartón.
    Bandas de intensidad: 0-0.30 = AT, 0.35-0.65 = BT, 0.70-1.00 = cartón prensado.
    """
    m = Malla()
    nt = q["n_theta"]
    th = np.linspace(0, 2 * np.pi, nt, endpoint=False)
    canales = (np.arange(nt) % max(4, nt // 8)) == 0
    capas = ((2.12, 2.42, -3.4, 3.4, q["filas_hv"], q["turns_hv"], 0.00),
             (1.75, 1.97, -3.2, 3.2, q["filas_lv"], q["turns_lv"], 0.35))
    for r_in, r_out, z0, z1, filas, vueltas, banda in capas:
        z = np.linspace(z0, z1, filas)
        T, Z = np.meshgrid(th, z)
        onda = np.sin(2 * np.pi * vueltas * (Z - z0) / (z1 - z0))
        R = r_out + 0.035 * onda                                   # espiras en relieve
        I = banda + 0.10 + 0.08 * (0.5 + 0.5 * onda)               # variación de brillo por espira
        I = np.where(canales[None, :], banda + 0.01, I)            # canales de enfriamiento
        m.rejilla(xc + R * np.cos(T), R * np.sin(T), Z, I)
        Ti, Zi = np.meshgrid(th, [z0, z1])                         # pared interior (lisa)
        m.rejilla(xc + r_in * np.cos(Ti), r_in * np.sin(Ti), Zi, np.full_like(Zi, banda + 0.05), invertir=True)
        Ta, Ra = np.meshgrid(th, [r_in, r_out])                    # anillos de cartón arriba y abajo
        for zc in (z0, z1):
            m.rejilla(xc + Ra * np.cos(Ta), Ra * np.sin(Ta), np.full_like(Ra, zc),
                      np.full_like(Ra, 0.85), invertir=(zc == z1))
    return m
 
 
def escala_devanado(color):
    """Escala de color de la fase según el DP (AT, BT algo más oscuro y cartón beige)."""
    hv, lv = color, oscurecer(color, 0.82)
    return [[0.00, oscurecer(hv, 0.45)], [0.05, oscurecer(hv, 0.65)], [0.10, oscurecer(hv, 0.88)],
            [0.18, oscurecer(hv, 1.08)], [0.30, oscurecer(hv, 1.08)],
            [0.34, oscurecer(lv, 0.45)], [0.40, oscurecer(lv, 0.70)], [0.45, oscurecer(lv, 0.90)],
            [0.53, oscurecer(lv, 1.08)], [0.65, oscurecer(lv, 1.08)],
            [0.70, "#B4A683"], [1.00, "#E6DABB"]]
 
 
def malla_bushings():
    """Tres aisladores pasantes de porcelana con faldones (una sola malla) + herrajes metálicos."""
    porcelana, metal = Malla(), Malla()
    z = np.linspace(6.0, 9.0, 56)
    u = (z - 6.0) / 3.0
    r = (0.26 + 0.14 * np.abs(np.sin(np.pi * (z - 6.0) / 0.45)) ** 0.6) * (1.35 - 0.35 * u)
    inten = 0.15 + 0.80 * (r - r.min()) / (r.max() - r.min())
    th = np.linspace(0, 2 * np.pi, 20, endpoint=False)
    T, Z = np.meshgrid(th, z)
    R, I = np.tile(r[:, None], (1, len(th))), np.tile(inten[:, None], (1, len(th)))
    for xc in POS_FASES:
        porcelana.rejilla(xc + R * np.cos(T), R * np.sin(T), Z, I)
        cilindro(metal, xc, 0, 0.62, 6.0, 6.28, 20, 0.5)      # brida de montaje
        cilindro(metal, xc, 0, 0.20, 9.0, 9.45, 16, 0.5)      # vástago del terminal
        cilindro(metal, xc, 0, 0.36, 9.45, 9.60, 16, 0.5)     # tapa del terminal
    return porcelana, metal
 
 
def cajas_combinadas(lista_cajas, color, opacity=1.0):
    """Fusiona cajas (x0,x1,y0,y1,z0,z1) en UNA sola traza Mesh3d de sombreado plano."""
    xs, ys, zs, I, J, K = [], [], [], [], [], []
    bi, bj, bk = [7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2], [3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3], [0, 7, 2, 3, 6, 7, 1, 1, 5, 5, 7, 6]
    for n, (x0, x1, y0, y1, z0, z1) in enumerate(lista_cajas):
        off = 8 * n
        xs += [x0, x0, x1, x1, x0, x0, x1, x1]
        ys += [y0, y1, y1, y0, y0, y1, y1, y0]
        zs += [z0, z0, z0, z0, z1, z1, z1, z1]
        I += [v + off for v in bi]
        J += [v + off for v in bj]
        K += [v + off for v in bk]
    return go.Mesh3d(x=np.array(xs, np.float32), y=np.array(ys, np.float32), z=np.array(zs, np.float32),
                     i=np.array(I, np.uint16), j=np.array(J, np.uint16), k=np.array(K, np.uint16),
                     color=color, opacity=opacity, flatshading=True, lighting=LUZ_PLANA,
                     lightposition=POS_LUZ, hoverinfo="skip")
 
 
def cajas_nucleo():
    """Núcleo tipo E con sección ESCALONADA (cruciforme) como en un núcleo laminado real."""
    cajas = []
    for xc in POS_FASES:                               # 3 columnas con 3 escalones cada una
        for w, d in ((2.2, 1.0), (1.8, 1.8), (1.3, 2.4)):
            cajas.append((xc - w / 2, xc + w / 2, -d / 2, d / 2, -4.0, 4.0))
    for hx, hy in ((6.5, 0.55), (6.3, 0.95), (6.1, 1.30)):   # yugos escalonados
        for z0, z1 in ((4.0, 5.6), (-5.6, -4.0)):
            cajas.append((-hx, hx, -hy, hy, z0, z1))
    return cajas
 
 
def cajas_herrajes():
    """Vigas de apriete (clamps) y placas laterales del núcleo."""
    return [(-6.9, 6.9, -1.55, 1.55, 5.6, 6.0), (-6.9, 6.9, -1.55, 1.55, -6.0, -5.6),
            (6.55, 6.85, -1.4, 1.4, -5.6, 5.6), (-6.85, -6.55, -1.4, 1.4, -5.6, 5.6)]
 
 
def cajas_radiadores():
    """Bancos de radiadores en los costados del tanque (paneles verticales + colectores)."""
    cajas = []
    for lado in (1, -1):
        x0, x1 = sorted((lado * TANQUE["x"], lado * 9.8))
        for n in range(9):
            y0 = -3.0 + n * 0.75
            cajas.append((x0, x1, y0, y0 + 0.12, -4.8, 7.4))
        cajas.append((x0, x1, -3.0, 3.1, 7.4, 7.75))
        cajas.append((x0, x1, -3.0, 3.1, -5.15, -4.8))
    return cajas
 
 
def wire_tanque():
    t = TANQUE
    c = [(-t["x"], -t["y"], t["z0"]), (t["x"], -t["y"], t["z0"]), (t["x"], t["y"], t["z0"]), (-t["x"], t["y"], t["z0"]),
         (-t["x"], -t["y"], t["z1"]), (t["x"], -t["y"], t["z1"]), (t["x"], t["y"], t["z1"]), (-t["x"], t["y"], t["z1"])]
    aristas = [(0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4), (0, 4), (1, 5), (2, 6), (3, 7)]
    xs, ys, zs = [], [], []
    for a, b in aristas:
        xs += [c[a][0], c[b][0], None]
        ys += [c[a][1], c[b][1], None]
        zs += [c[a][2], c[b][2], None]
    return go.Scatter3d(x=xs, y=ys, z=zs, mode="lines", hoverinfo="skip",
                        line=dict(color="#6B7C93", width=3), opacity=0.7)
 
 
def cables_salida(offsets=None):
    """Cables de cobre del devanado AT hasta cada bushing (una sola traza con cortes)."""
    xs, ys, zs = [], [], []
    for n, xc in enumerate(POS_FASES):
        dx, dy = offsets[n] if offsets else (0.0, 0.0)
        xs += [xc + dx, xc + dx, xc, None]
        ys += [2.42 + dy, 2.42 + dy, 0, None]
        zs += [3.4, 6.9, 6.9, None]
    return xs, ys, zs
 
 
R_CAMARA = 2.7                           # distancia de la cámara al centro
ANGULO_INICIAL = math.atan2(-1.9, 1.5)   # ángulo de la vista inicial
Z_CAMARA = 0.80
 
 
def _ojo_camara(angulo):
    return dict(x=R_CAMARA * math.cos(angulo), y=R_CAMARA * math.sin(angulo), z=Z_CAMARA)
 
 
def _botones_animacion(etiqueta_play, duracion_ms):
    """Botones Play / Pausa dentro de la propia figura (no requieren recargar Streamlit)."""
    return [dict(
        type="buttons", direction="left", x=0.02, y=0.98, xanchor="left", yanchor="top",
        bgcolor="#1A222C", bordercolor="#2B3644", font=dict(color="#FFFFFF"),
        buttons=[
            dict(label=etiqueta_play, method="animate",
                 args=[None, dict(frame=dict(duration=duracion_ms, redraw=True),
                                  transition=dict(duration=0), fromcurrent=True, mode="immediate")]),
            dict(label="⏸ Pausa", method="animate",
                 args=[[None], dict(frame=dict(duration=0, redraw=False),
                                    transition=dict(duration=0), mode="immediate")]),
        ])]
 
 
def construir_modelo_3d(color_devanado, amplitud_vibracion=0.0, animar=False, calidad="Equilibrada"):
    """
    Figura 3D completa en ~14 trazas.
      - animar=False: modelo en reposo con botón "Girar 360°" (frames de cámara, muy ligeros).
      - animar=True : animación Inrush (oscilación amortiguada) con malla ligera; se reproduce sola.
      - amplitud_vibracion > 0 y animar=False: desplazamiento estático (respaldo).
    """
    q = CALIDADES_3D[CALIDAD_ANIMACION if animar else calidad]
    rng = np.random.default_rng()
    fig = go.Figure()
 
    # --- Entorno: base, tanque translúcido y contorno ---------------------------
    t = TANQUE
    fig.add_trace(cajas_combinadas([(-9.0, 9.0, -4.6, 4.6, -6.8, -6.0)], "#161D27"))
    fig.add_trace(cajas_combinadas([(-t["x"], t["x"], -t["y"], t["y"], t["z0"], t["z1"])], "#8FA3BF", opacity=0.05))
    fig.add_trace(wire_tanque())
    fig.add_trace(cajas_combinadas(cajas_radiadores(), "#68758A"))
 
    # --- Núcleo laminado y herrajes ----------------------------------------------
    fig.add_trace(cajas_combinadas(cajas_nucleo(), "#465063"))
    fig.add_trace(cajas_combinadas(cajas_herrajes(), "#6B7686"))
 
    # --- Devanados: UNA malla por fase (así cada fase vibra por separado) -----------
    escala = escala_devanado(color_devanado)
    mallas, indices_fase, offsets = [], [], []
    for xc in POS_FASES:
        m = malla_devanado(xc, q)
        if amplitud_vibracion and not animar:
            off = (rng.uniform(-amplitud_vibracion, amplitud_vibracion), rng.uniform(-amplitud_vibracion, amplitud_vibracion))
        else:
            off = (0.0, 0.0)
        mallas.append(m)
        offsets.append(off)
        indices_fase.append(len(fig.data))
        fig.add_trace(m.traza(escala, dx=off[0], dy=off[1]))
 
    # --- Cables, bushings y etiquetas -------------------------------------------------
    cx, cy, cz = cables_salida(offsets if amplitud_vibracion and not animar else None)
    idx_cables = len(fig.data)
    fig.add_trace(go.Scatter3d(x=cx, y=cy, z=cz, mode="lines", hoverinfo="skip",
                               line=dict(color="#C77B30", width=7)))
    porcelana, metal = malla_bushings()
    fig.add_trace(porcelana.traza([[0.0, "#5E3520"], [1.0, "#C48A58"]]))
    fig.add_trace(metal.traza(escala_plana("#AAB4BF"), luz=LUZ_PLANA))
    fig.add_trace(go.Scatter3d(x=list(POS_FASES), y=[0, 0, 0], z=[11.2] * 3, mode="text",
                               text=["FASE A", "FASE B", "FASE C"], hoverinfo="skip",
                               textfont=dict(color="#9FB0C3", size=13)))
 
    # --- Animaciones ----------------------------------------------------------------------
    if animar:
        n_frames, duracion_total, frecuencia, decaimiento = 24, 2.4, 2.0, 2.4
        fases = rng.uniform(0, 2 * np.pi, size=(3, 2))
        base = [m.arrays()[0][:, :2] for m in mallas]          # (x, y) originales de cada fase
        frames = []
        for n in range(n_frames + 1):
            tt = duracion_total * n / n_frames
            env = amplitud_vibracion * math.exp(-decaimiento * tt) if n < n_frames else 0.0
            datos, trazas, desp = [], [], []
            for f in range(3):
                dx = env * math.sin(2 * math.pi * frecuencia * tt + fases[f, 0])
                dy = env * math.sin(2 * math.pi * frecuencia * tt + fases[f, 1])
                desp.append((dx, dy))
                datos.append(go.Mesh3d(x=(base[f][:, 0] + dx).astype(np.float32),
                                       y=(base[f][:, 1] + dy).astype(np.float32)))
                trazas.append(indices_fase[f])
            fx, fy, _ = cables_salida(desp)
            datos.append(go.Scatter3d(x=fx, y=fy))
            trazas.append(idx_cables)
            frames.append(go.Frame(data=datos, traces=trazas, name=f"v{n}"))
        fig.frames = frames
        menus = _botones_animacion("▶ Repetir Inrush", 100)
    else:
        n_giro = 48
        fig.frames = [go.Frame(layout=dict(scene=dict(camera=dict(
            eye=_ojo_camara(ANGULO_INICIAL + 2 * math.pi * n / n_giro)))), name=f"r{n}")
            for n in range(n_giro + 1)]
        menus = _botones_animacion("▶ Girar 360°", 75)
 
    fig.update_layout(
        scene=dict(
            xaxis=dict(visible=False), yaxis=dict(visible=False), zaxis=dict(visible=False),
            aspectmode="data", bgcolor="#0E1117",
            camera=dict(eye=_ojo_camara(ANGULO_INICIAL)),
        ),
        margin=dict(l=0, r=0, t=0, b=0), height=600,
        paper_bgcolor="rgba(0,0,0,0)", showlegend=False, updatemenus=menus,
        uirevision="modelo3d",
    )
    return fig
 
 
@st.cache_resource(show_spinner=False, max_entries=3)
def modelo_3d_estatico(color_devanado, calidad):
    """Modelo en reposo cacheado: se construye una vez por (color, calidad)."""
    return construir_modelo_3d(color_devanado, 0.0, calidad=calidad)
 
 
def html_animado(fig):
    """HTML autónomo de la figura con autoplay (la vibración Inrush arranca sola)."""
    html = fig.to_html(
        full_html=True, include_plotlyjs=True, auto_play=True,
        config=dict(displaylogo=False, responsive=True),
        animation_opts=dict(frame=dict(duration=100, redraw=True), transition=dict(duration=0),
                            fromcurrent=True, mode="immediate"),
    )
    estilo = "<style>html,body{margin:0;padding:0;background:#0E1117;overflow:hidden}</style>"
    return html.replace("<head>", "<head>" + estilo, 1)
 
 
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
        transition=dict(duration=300, easing="cubic-in-out"),  # las curvas se deslizan al mover sliders
        uirevision=f"tendencia_{tipo}",                         # conserva el zoom del usuario
    )
    fig.update_xaxes(range=[0, 40], gridcolor="#2B3644")
    fig.update_yaxes(gridcolor="#2B3644")
    return fig
 
 
def mostrar_html(html, altura):
    """Incrusta HTML propio. Usa st.iframe (versiones nuevas) o components.html (antiguas)."""
    if hasattr(st, "iframe"):
        st.iframe(html, height=altura)
    else:
        import streamlit.components.v1 as components
        components.html(html, height=altura)
 
 
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
    from reportlab.platypus import Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
 
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
                  P(f'<font color="white" size="9"><b>{EMPRESA}</b><br/>Fecha: {d["fecha"]}</font>', cuerpo)]],
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
 
    # ---- Análisis de Inrush ----
    A = d["inrush"]
    tin = [[enc("Corriente nominal"), enc("Pico Inrush"), enc("Fuerza aplicada"), enc("Capacidad papel"),
            enc("Factor seg."), enc("Veredicto")],
           [P(f'{A["i_nom"]:,.0f} A'), P(f'{A["i_pico"]:,.0f} A'), P(f'{A["fuerza_rel"]:.0f} x normal'),
            P(f'{A["capacidad"]:.0f} x normal'), P(f'<b>{A["fs"]:.2f}</b>'),
            P(f'<font color="{COLOR_PDF[A["nivel"]]}"><b>{esc(A["veredicto"])}</b></font>')]]
    t = Table(tin, colWidths=[2.6 * cm, 2.5 * cm, 2.9 * cm, 2.9 * cm, 2.2 * cm, 4.9 * cm])
    t.setStyle(estilo_tabla())
    story += [Paragraph("4. Análisis de Inrush (energización del transformador)", h2), t, Spacer(1, 5)]
    for n, (_, tit, txt) in enumerate(A["pasos"], start=1):
        story += [Paragraph(f"<b>{n}. {esc(tit)}.</b> {esc(txt)}", cuerpo), Spacer(1, 2)]
    filas = [[enc("Componente"), enc("Qué le hizo el Inrush"), enc("Estado")]]
    for comp, txt, est in A["componentes"]:
        filas.append([P(f'<b>{esc(comp)}</b>'), P(esc(txt)),
                      P(f'<font color="{COLOR_PDF[est]}"><b>{ESTADOS_COMP[est][2]}</b></font>')])
    t = Table(filas, colWidths=[4 * cm, 10.2 * cm, 3.8 * cm], repeatRows=1)
    t.setStyle(estilo_tabla())
    story += [Spacer(1, 4), t, Spacer(1, 5),
              Paragraph(f"<b>Explicación general:</b> {esc(A['guion'])}", cuerpo), Spacer(1, 3),
              Paragraph(f"<b>Comparación:</b> {esc(A['contrafactual'])}", cuerpo), Spacer(1, 3),
              Paragraph(f"<i>{esc(A['nota_modelo'])}</i>", chico)]
 
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
    story += [Paragraph("5. Plan de acción recomendado (mejorar o reparar)", h2), t]
 
    # ---- Reemplazo ----
    filas = [[enc("Opción"), enc("Gama"), enc("Costo estimado (USD)"), enc("Plazo"), enc("Notas")]]
    for o in d["opciones"]:
        filas.append([P(f'<b>{esc(o["opcion"])}</b>'), P(esc(o["gama"])), P(fmt_rango(o["lo"], o["hi"])),
                      P(esc(o["plazo"])), P(esc(o["notas"]))])
    t = Table(filas, colWidths=[3.8 * cm, 2.3 * cm, 4 * cm, 2.2 * cm, 5.7 * cm], repeatRows=1)
    t.setStyle(estilo_tabla())
    story += [Paragraph(f'6. Opciones de reemplazo o reconstrucción ({d["mva"]:g} MVA, {d["kv"]:g} kV)', h2), t,
              Spacer(1, 4),
              Paragraph(f'Referencia: un transformador nuevo equivalente se estima en aprox. '
                        f'<b>{fmt_usd(d["costo_base"])}</b> (valor central), con una variación típica de -25 % a +35 % '
                        f'según marca, especificación, enfriamiento, pruebas y transporte.', cuerpo)]
 
    # ---- Cierre: empresa que elabora el informe ----
    banda = Table([[P(f'<font color="white" size="15"><b>{EMPRESA}</b></font><br/>'
                      f'<font color="white" size="9">Ingeniería y mantenimiento predictivo de transformadores</font>', cuerpo)]],
                  colWidths=[18 * cm])
    banda.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), azul), ("TOPPADDING", (0, 0), (-1, -1), 8),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 8), ("LEFTPADDING", (0, 0), (-1, -1), 10)]))
    firmas = Table([[P("<br/><br/><br/>______________________________<br/><b>Elaboró</b><br/>"
                       f"Ingeniería de diagnóstico - {EMPRESA}", chico),
                     P("<br/><br/><br/>______________________________<br/><b>Revisó / Autorizó</b>", chico)]],
                   colWidths=[9 * cm, 9 * cm])
    fino = ParagraphStyle("fino", parent=chico, fontSize=7, leading=9, textColor=colors.HexColor("#64748B"))
    story += [KeepTogether([
        Paragraph(f"7. Elaborado por {EMPRESA}", h2),
        banda, Spacer(1, 6),
        Paragraph(f"{EMPRESA} realizó este diagnóstico predictivo del transformador {nombre} a partir de los "
                  "parámetros operativos proporcionados. Nuestros servicios incluyen: diagnóstico predictivo "
                  "(análisis de aceite, furanos y grado de polimerización), rehabilitación y regeneración de aceite, "
                  "monitoreo en línea, y asesoría para la especificación y adquisición de transformadores de reemplazo.",
                  cuerpo),
        Spacer(1, 4), firmas, Spacer(1, 6),
        Paragraph("Nota: los resultados provienen de un modelo simplificado y los costos son orientativos (no son "
                  "cotizaciones); validar con pruebas de laboratorio antes de tomar decisiones de inversión u operación.",
                  fino),
    ])]
 
    def pie(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#64748B"))
        canvas.drawString(1.8 * cm, 1.1 * cm, f"{EMPRESA} - Diagnóstico predictivo - {d['nombre']} - {d['fecha']}")
        canvas.drawRightString(letter[0] - 1.8 * cm, 1.1 * cm, f"Página {doc.page}")
        canvas.restoreState()
 
    salida = io.BytesIO()
    doc = SimpleDocTemplate(salida, pagesize=letter, leftMargin=1.8 * cm, rightMargin=1.8 * cm,
                            topMargin=1.5 * cm, bottomMargin=1.8 * cm,
                            title=f"Informe {d['nombre']}", author=EMPRESA)
    doc.build(story, onFirstPage=pie, onLaterPages=pie)
    return salida.getvalue()
 
 
# -----------------------------------------------------------------------------
# 6. BARRA LATERAL (ENTRADAS)
# -----------------------------------------------------------------------------
CASO_EDITABLE = "✏️ Mi transformador (editable)"
TIPOS_LISTA = list(TIPOS_AISLAMIENTO)
OPCIONES_KV = [f"{v:g}" for v in TENSIONES_KV] + ["Otra"]
 
# Memoria de "Mi transformador": así no se pierden tus datos al ver un ejemplo.
ed = st.session_state.setdefault("_ed", dict(
    nombre="TR-01", kvsel="115", kvotra=115.0, mva=30.0, aisl=TIPOS_LISTA[0], anos=10, temp=85))
 
with st.sidebar:
    st.markdown(f"### 🏭 {EMPRESA}")
    st.caption("Mantenimiento predictivo de transformadores")
    modo_pres = st.checkbox("🎤 Modo presentación (letras más grandes)", value=False)
    calidad_3d = st.selectbox("🖥️ Calidad del modelo 3D", list(CALIDADES_3D), index=1,
                              help="Si tu PC va lenta o con poca RAM, elige «Ligera». "
                                   "«Alta calidad» solo para equipos potentes.")
    caso_sel = st.selectbox("Caso a analizar", [CASO_EDITABLE] + [e["nombre"] for e in EJEMPLOS])
    ejemplo = next((e for e in EJEMPLOS if e["nombre"] == caso_sel), None)
    bloqueado = ejemplo is not None
    k = ejemplo["id"] if bloqueado else "ed"
    if bloqueado:
        st.info("🔒 Ejemplo de solo lectura. Para modificar valores elige «Mi transformador».")
 
    st.header("🏷️ Identificación del Equipo")
    nombre = st.text_input(
        "Nombre / ID del transformador", max_chars=40, key=f"nombre_{k}", disabled=bloqueado,
        value=ejemplo["nombre"] if bloqueado else ed["nombre"]).strip() or "SIN-NOMBRE"
 
    kv_ini = f"{ejemplo['kv']:g}" if bloqueado else ed["kvsel"]
    opcion_kv = st.selectbox("Tensión nominal AT (kV)", OPCIONES_KV, index=OPCIONES_KV.index(kv_ini),
                             key=f"kvsel_{k}", disabled=bloqueado)
    if opcion_kv == "Otra":
        kv = float(st.number_input("Tensión AT (kV)", min_value=1.0, max_value=800.0, step=1.0,
                                   value=float(ed["kvotra"]), key=f"kvotra_{k}", disabled=bloqueado))
    else:
        kv = float(opcion_kv)
 
    mva = float(st.number_input("Potencia nominal (MVA)", min_value=5.0, max_value=500.0, step=5.0,
                                value=ejemplo["mva"] if bloqueado else float(ed["mva"]),
                                key=f"mva_{k}", disabled=bloqueado))
 
    st.header("🧪 Aislamiento")
    aisl_ini = ejemplo["aislamiento"] if bloqueado else ed["aisl"]
    tipo_aislamiento = st.selectbox("Tipo de aislamiento", TIPOS_LISTA, index=TIPOS_LISTA.index(aisl_ini),
                                    key=f"aisl_{k}", disabled=bloqueado)
    info_aisl = TIPOS_AISLAMIENTO[tipo_aislamiento]
    factor = info_aisl["factor"]
    st.caption(f"{info_aisl['desc']}  \nFactor de envejecimiento: **{factor:.2f}** (1.00 = Kraft estándar)")
 
    st.header("⚙️ Parámetros Operativos")
    anos = st.slider("Años de Operación", 0, 40, ejemplo["anos"] if bloqueado else int(ed["anos"]),
                     key=f"anos_{k}", disabled=bloqueado)
    temp = st.slider("Temperatura Nominal (°C)", 50, 120, ejemplo["temp"] if bloqueado else int(ed["temp"]),
                     key=f"temp_{k}", disabled=bloqueado)
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
 
# Guardar los valores de "Mi transformador" cuando se está editando
if not bloqueado:
    ed.update(nombre=nombre, kvsel=opcion_kv, mva=mva, aisl=tipo_aislamiento, anos=anos, temp=temp)
    if opcion_kv == "Otra":
        ed["kvotra"] = kv
 
# -----------------------------------------------------------------------------
# 7. CÁLCULOS PRINCIPALES
# -----------------------------------------------------------------------------
ppm_actual, dp_actual, resistencia_actual = calcular_salud(anos, temp, factor)
estado, color_estado, color_3d = clasificar_estado(dp_actual)
anos_restantes = anos_hasta_dp_critico(temp, anos, factor)
bil = bil_tipico(kv)
es_aramida = tipo_aislamiento.startswith("Aramida")
 
# -----------------------------------------------------------------------------
# 8. ENCABEZADO (HERO) Y TARJETAS KPI
# -----------------------------------------------------------------------------
if modo_pres:
    st.markdown(CSS_PRESENTACION, unsafe_allow_html=True)
 
fecha_hoy = datetime.date.today().strftime("%d/%m/%Y")
etiqueta_ej = '<span class="chip">🔒 Ejemplo de solo lectura</span>' if bloqueado else ""
st.markdown(
    f"""<div class="hero">
    <div class="hero-top"><span>⚡ {EMPRESA}</span><span>{fecha_hoy}</span></div>
    <h1>Diagnóstico Predictivo de Transformador de Potencia</h1>
    <span class="chip"><b>{esc(nombre)}</b></span>
    <span class="chip">{kv:g} kV · BIL típico {bil if bil else 'N/D'} kV</span>
    <span class="chip">{mva:g} MVA</span>
    <span class="chip">{esc(tipo_aislamiento)}</span>
    <span class="chip">{anos} años · {temp} °C</span>{etiqueta_ej}
    </div>""",
    unsafe_allow_html=True,
)
 
if es_aramida:
    st.warning("ℹ️ La aramida (Nomex) no genera furanos: los valores de furanos/DP son solo "
               "referenciales. Complementa con DGA y pruebas directas del papel.")
 
vida_txt = "∞" if anos_restantes is None else f"{anos_restantes:.1f} años"
k1, k2, k3, k4, k5 = st.columns(5)
k1.markdown(kpi("Grado de polimerización", f"{dp_actual:.0f}", "DP · papel aislante", color_estado), unsafe_allow_html=True)
k2.markdown(kpi("Furanos 2-FAL", f"{ppm_actual:.3f}", "ppm en el aceite", "#38BDF8"), unsafe_allow_html=True)
k3.markdown(kpi("Resistencia mecánica", f"{resistencia_actual:.0f} %", "del papel original", color_estado,
                barra=resistencia_actual), unsafe_allow_html=True)
k4.markdown(kpi("Vida hasta DP = 200", vida_txt, "a esta temperatura", "#A78BFA"), unsafe_allow_html=True)
k5.markdown(kpi("Estado del aislamiento", estado, "clasificación por DP", color_estado), unsafe_allow_html=True)
 
mensajes_estado = {
    "ÓPTIMO": "✅ Aislamiento en excelentes condiciones.",
    "DESGASTE NORMAL": "ℹ️ Desgaste normal. Continuar con el monitoreo de rutina.",
    "ALERTA": "⚠️ Papel muy degradado. Programar mantenimiento preventivo.",
    "CRÍTICO": "🚨 Estado crítico: riesgo de falla inminente (DP < 200).",
}
st.markdown(f'<div class="aviso" style="--ac:{color_estado}">{mensajes_estado[estado]}</div>', unsafe_allow_html=True)
 
# Análisis del Inrush (se calcula siempre; se muestra al presionar el botón y va al PDF)
analisis = analizar_inrush(nombre, kv, mva, tipo_aislamiento, anos, temp, factor,
                           ppm_actual, dp_actual, resistencia_actual)
 
# -----------------------------------------------------------------------------
# 9. MODELO 3D + INRUSH CON EXPLICACIÓN EN TIEMPO REAL
# -----------------------------------------------------------------------------
def fig_gauge(A):
    """Medidor del factor de seguridad mecánico."""
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=A["fs"],
        number=dict(suffix=" ×", font=dict(size=46, color="#FFFFFF")),
        title=dict(text="Factor de seguridad mecánico", font=dict(size=15, color="#9FB0C3")),
        gauge=dict(axis=dict(range=[0, 4], tickcolor="#9FB0C3"), bar=dict(color=A["color"], thickness=0.35),
                   bgcolor="#121820", borderwidth=0,
                   steps=[dict(range=[0, 1], color="#5B1E1E"), dict(range=[1, 2], color="#5B4A1E"),
                          dict(range=[2, 4], color="#1E4D2E")],
                   threshold=dict(line=dict(color="#FFFFFF", width=4), thickness=0.85, value=1)),
    ))
    fig.update_layout(template="plotly_dark", height=300, margin=dict(l=20, r=20, t=60, b=10),
                      paper_bgcolor="rgba(0,0,0,0)")
    return fig
 
 
def fig_onda(A):
    """Forma de onda típica de la corriente Inrush (60 Hz, decae en ~1 s)."""
    t = np.linspace(0, 1.2, 1200)
    i = A["i_pico"] * np.exp(-t / 0.4) * np.maximum(0, np.sin(2 * np.pi * 60 * t))
    fig = go.Figure(go.Scatter(x=t, y=i, mode="lines", fill="tozeroy",
                               line=dict(color="#38BDF8", width=1.5), fillcolor="rgba(56,189,248,0.25)",
                               hovertemplate="%{x:.3f} s · %{y:,.0f} A<extra></extra>"))
    fig.add_hline(y=A["i_nom"], line=dict(color="#2ECC71", width=1.5, dash="dash"),
                  annotation_text=f"Nominal {A['i_nom']:,.0f} A", annotation_font_color="#2ECC71",
                  annotation_position="top right")
    fig.add_annotation(x=1 / 240, y=A["i_pico"], text=f"Pico {A['i_pico']:,.0f} A", showarrow=True,
                       arrowcolor="#F59E0B", font=dict(color="#F59E0B", size=13), ax=60, ay=-10)
    fig.update_layout(template="plotly_dark", height=300, margin=dict(l=10, r=10, t=60, b=10),
                      title=dict(text="Corriente Inrush al energizar", font=dict(size=15, color="#9FB0C3")),
                      xaxis_title="Tiempo (s)", yaxis_title="Corriente (A)",
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#121820", showlegend=False)
    fig.update_xaxes(gridcolor="#2B3644")
    fig.update_yaxes(gridcolor="#2B3644", range=[0, A["i_pico"] * 1.25])
    return fig
 
 
def fig_fuerza(A):
    """Fuerza aplicada por el Inrush frente a la capacidad del papel."""
    col_cap = "#2ECC71" if A["fs"] >= 2 else ("#F39C12" if A["fs"] > 1 else "#E74C3C")
    fig = go.Figure(go.Bar(
        y=["Capacidad del papel", "Fuerza del Inrush"], x=[A["capacidad"], A["fuerza_rel"]], orientation="h",
        marker_color=[col_cap, "#F59E0B"], text=[f"{A['capacidad']:.0f} ×", f"{A['fuerza_rel']:.0f} ×"],
        textposition="outside", textfont=dict(color="#FFFFFF", size=14)))
    fig.update_layout(template="plotly_dark", height=300, margin=dict(l=10, r=40, t=60, b=10),
                      title=dict(text="Fuerza vs capacidad (× fuerza normal)", font=dict(size=15, color="#9FB0C3")),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#121820", showlegend=False,
                      xaxis=dict(range=[0, CAPACIDAD_DISENO * 1.2], gridcolor="#2B3644"))
    return fig
 
 
def panel_inrush(A, animado):
    """Explicación del Inrush. Si 'animado', los pasos aparecen uno a uno (tiempo real)."""
    seccion("⚡ ¿Qué pasó con el Inrush?", "Explicación paso a paso: qué ocurrió, por qué y qué se afectó")
 
    # Pasos en tiempo real (sincronizados con la vibración del modelo 3D)
    huecos = [st.empty() for _ in A["pasos"]]
    for hueco, (ic, titulo, texto) in zip(huecos, A["pasos"]):
        hueco.markdown(f'<div class="paso" style="--ac:{A["color"]}"><div class="paso-t">{ic} {esc(titulo)}</div>'
                       f'<div class="paso-x">{esc(texto)}</div></div>', unsafe_allow_html=True)
        if animado:
            time.sleep(0.6)
 
    # Veredicto
    st.markdown(f'<div class="veredicto" style="--ac:{A["color"]}"><div class="v-t">{A["icono"]} {A["veredicto"]}</div>'
                f'<div class="v-s">{esc(A["resumen"])}</div></div>', unsafe_allow_html=True)
 
    g1, g2, g3 = st.columns([1, 1.3, 1.2])
    with g1:
        mostrar_plotly(fig_gauge(A))
    with g2:
        mostrar_plotly(fig_onda(A))
    with g3:
        mostrar_plotly(fig_fuerza(A))
 
    # ¿Por qué? causas + comparación con un equipo sano
    chips = "".join(f'<span class="chip" style="background:#1B2A3F;border-color:#2B4A6B">{esc(c)}</span>' for c in A["causas"])
    st.markdown(f'<div class="callout"><b>¿Qué causó el desgaste del papel?</b><br/>{chips}<br/><br/>'
                f'<b>Comparación:</b> {esc(A["contrafactual"])}</div>', unsafe_allow_html=True)
 
    # Qué se afectó, componente por componente
    filas = ""
    for comp, texto, est in A["componentes"]:
        ic, col, etq = ESTADOS_COMP[est]
        filas += (f'<tr><td><b>{esc(comp)}</b></td><td>{esc(texto)}</td>'
                  f'<td style="color:{col};font-weight:700;white-space:nowrap">{ic} {etq}</td></tr>')
    st.markdown("**🔍 Qué se afectó, componente por componente**")
    st.markdown(f'<table class="tabla-comp"><tr><th>Componente</th><th>Qué le hizo el Inrush</th><th>Estado</th></tr>'
                f'{filas}</table>', unsafe_allow_html=True)
 
    st.markdown(f'<div class="guion"><b>Explicación general del evento</b><br/>{esc(A["guion"])}</div>', unsafe_allow_html=True)
    with st.expander("📐 Supuestos y fórmulas del modelo"):
        st.write(A["nota_modelo"])
        st.code("Inrush = 8 × corriente nominal        (típico 5 a 12×)\n"
                "Fuerza  = Inrush² = 64 × fuerza normal   (F = k·I²)\n"
                "Capacidad del papel = 256 × (resistencia % / 100)\n"
                "Factor de seguridad = Capacidad / Fuerza = resistencia % / 25\n"
                "FS ≥ 2: sin daño · 1 < FS < 2: comprometido · FS ≤ 1: falla (DP < 200)", language="text")
 
 
@fragmento
def seccion_modelo_inrush(P):
    """Sección completa (3D + botón + explicación). Como es un fragmento, al presionar
    Inrush solo se actualiza esta sección y no toda la aplicación."""
    seccion("🧲 Modelo 3D y Simulación de Inrush",
            "Gira el modelo con el mouse o con el botón ▶ y presiona Inrush para energizar el equipo")
    col_3d, col_info = st.columns([2.3, 1])
    A = P["analisis"]
 
    with col_info:
        st.markdown("#### Simulación de energización")
        st.write("Al energizar, la corriente **Inrush** genera fuerzas electrodinámicas sobre los devanados. "
                 "Con papel degradado, el aislamiento puede no resistir.")
        presionado = st.button("⚡ SIMULAR INRUSH", type="primary", key="btn_inrush")
        st.markdown("**Color de los devanados**")
        st.markdown(
            """
            <div><span class="leyenda-dot" style="background:#F6B26B"></span>DP &gt; 800 · Óptimo</div>
            <div><span class="leyenda-dot" style="background:#D35400"></span>DP &gt; 400 · Desgaste normal</div>
            <div><span class="leyenda-dot" style="background:#6E2C00"></span>DP &gt; 200 · Alerta</div>
            <div><span class="leyenda-dot" style="background:#17202A"></span>DP &lt; 200 · Carbonizado</div>
            """, unsafe_allow_html=True)
        st.caption("Arrastra para rotar · rueda para acercar · botón ▶ dentro del modelo para girarlo 360°.")
 
    if presionado:
        st.session_state["inrush_firma"] = P["firma"]
 
    with col_3d:
        if presionado:
            try:  # la vibración arranca sola y se amortigua en ~2.4 s
                mostrar_html(html_animado(construir_modelo_3d(P["color_3d"], A["amplitud"], animar=True)), 610)
            except Exception:
                mostrar_plotly(construir_modelo_3d(P["color_3d"], A["amplitud"]))  # respaldo estático
        else:
            mostrar_plotly(modelo_3d_estatico(P["color_3d"], P["calidad"]))
 
    # La explicación se conserva mientras no cambies los parámetros
    if st.session_state.get("inrush_firma") == P["firma"]:
        panel_inrush(A, animado=presionado)
 
 
firma = (nombre, kv, mva, tipo_aislamiento, anos, temp)
seccion_modelo_inrush(dict(analisis=analisis, color_3d=color_3d, firma=firma, calidad=calidad_3d))
 
# -----------------------------------------------------------------------------
# 10. SECCIÓN 3: GRÁFICAS DE TENDENCIA 2D
# -----------------------------------------------------------------------------
seccion("📈 Tendencias de Vida Útil", "Furanos y DP frente a los años: tu equipo contra referencias sana y sobrecalentada")
g1, g2 = st.columns(2)
with g1:
    mostrar_plotly(construir_grafica_tendencia("ppm", anos, temp, ppm_actual, factor, escala_log))
with g2:
    mostrar_plotly(construir_grafica_tendencia("dp", anos, temp, dp_actual, factor))
 
st.caption("🟢 Sano (60 °C) · 🔴 Sobrecalentado (95 °C) · 🔵 Tu transformador (temperatura del slider). "
           "El punto blanco marca el año seleccionado.")
 
st.divider()
 
# -----------------------------------------------------------------------------
# 10b. COMPARATIVO: MI TRANSFORMADOR vs EJEMPLOS
# -----------------------------------------------------------------------------
seccion("🏢 Comparativo de Ejemplos", "Cuatro edificios de ejemplo (solo lectura) frente a tu transformador")
 
kv_ed = float(ed["kvotra"]) if ed["kvsel"] == "Otra" else float(ed["kvsel"])
casos = [dict(nombre=f"{ed['nombre']} (mío)", kv=kv_ed, mva=float(ed["mva"]), aisl=ed["aisl"],
              anos=int(ed["anos"]), temp=int(ed["temp"]))]
casos += [dict(nombre=e["nombre"], kv=e["kv"], mva=e["mva"], aisl=e["aislamiento"],
               anos=e["anos"], temp=e["temp"]) for e in EJEMPLOS]
 
filas_comp, nombres_c, dps_c, colores_c = [], [], [], []
for c in casos:
    ppm_c, dp_c, res_c = calcular_salud(c["anos"], c["temp"], TIPOS_AISLAMIENTO[c["aisl"]]["factor"])
    est_c, col_c, _ = clasificar_estado(dp_c)
    filas_comp.append({"Caso": c["nombre"], "kV": f"{c['kv']:g}", "MVA": f"{c['mva']:g}",
                       "Aislamiento": c["aisl"], "Años": c["anos"], "°C": c["temp"],
                       "DP": f"{dp_c:.0f}", "Furanos (ppm)": f"{ppm_c:.3f}",
                       "Resistencia": f"{res_c:.0f} %", "Estado": est_c})
    nombres_c.append(c["nombre"])
    dps_c.append(dp_c)
    colores_c.append(col_c)
 
fig_comp = go.Figure(go.Bar(x=nombres_c, y=dps_c, marker_color=colores_c,
                            text=[f"{v:.0f}" for v in dps_c], textposition="outside",
                            textfont=dict(color="#FFFFFF")))
for nivel, etiqueta, col in ((DP_NUEVO, "Óptimo", "#2ECC71"), (DP_DESGASTE, "Desgaste", "#F1C40F"),
                             (DP_ALERTA, "Crítico", "#E74C3C")):
    fig_comp.add_hline(y=nivel, line=dict(color=col, width=1.5, dash="dot"),
                       annotation_text=f"DP {nivel} · {etiqueta}", annotation_font_color=col,
                       annotation_position="top right")
fig_comp.update_layout(
    template="plotly_dark", title=dict(text="DP actual por caso", font=dict(size=17)),
    yaxis=dict(title="DP", range=[0, 1150], gridcolor="#2B3644"), height=400,
    margin=dict(l=10, r=10, t=60, b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#121820",
    uirevision="comparativo",
)
mostrar_plotly(fig_comp)
df_comp = pd.DataFrame(filas_comp)
df_comp.index = range(1, len(df_comp) + 1)
st.table(df_comp)
 
st.divider()
 
# -----------------------------------------------------------------------------
# 11. SECCIÓN 4: PLAN DE ACCIÓN, REEMPLAZO E INFORME PDF
# -----------------------------------------------------------------------------
seccion("🛠️ Plan de Acción y Opciones de Reemplazo", "Qué hacer para mejorar o reparar, y alternativas de reemplazo con costos orientativos")
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
 
seccion("📄 Informe PDF", "Ficha del equipo, diagnóstico, gráficas, análisis de Inrush, plan de acción y reemplazo")
 
datos_pdf = dict(
    nombre=nombre, kv=kv, mva=mva, bil=bil, aislamiento=tipo_aislamiento, factor=factor,
    anos=anos, temp=temp, ppm=ppm_actual, dp=dp_actual, resistencia=resistencia_actual,
    estado=estado, color_estado=color_estado, anos_rest=anos_restantes, aramida=es_aramida,
    acciones=acciones, opciones=opciones, costo_base=costo_base, inrush=analisis,
    fecha=datetime.date.today().strftime("%d/%m/%Y"),
)
 
 
@fragmento
def seccion_pdf(D, firma_actual):
    """Generar/descargar PDF dentro de un fragmento: no recarga el resto de la app."""
    if st.button("📄 Generar informe PDF", key="btn_pdf"):
        with st.spinner("Generando informe..."):
            try:
                st.session_state["pdf_bytes"] = generar_pdf(D)
                st.session_state["pdf_firma"] = firma_actual
            except Exception as error:  # robustez: el PDF nunca rompe el dashboard
                st.error(f"No se pudo generar el PDF: {error}")
 
    if st.session_state.get("pdf_firma") == firma_actual:
        nombre_archivo = re.sub(r"[^A-Za-z0-9_-]+", "_", D["nombre"]).strip("_") or "Transformador"
        opciones_dl = dict(data=st.session_state["pdf_bytes"], mime="application/pdf",
                           file_name=f"Informe_{nombre_archivo}_{datetime.date.today():%Y%m%d}.pdf")
        try:  # on_click="ignore": descargar no vuelve a ejecutar la app (versiones nuevas)
            st.download_button("⬇️ Descargar informe PDF", on_click="ignore", **opciones_dl)
        except TypeError:
            st.download_button("⬇️ Descargar informe PDF", **opciones_dl)
    elif "pdf_firma" in st.session_state:
        st.info("Cambiaste los parámetros desde el último informe. Genera uno nuevo para actualizarlo.")
 
 
seccion_pdf(datos_pdf, firma)
 
st.markdown(f'<div class="pie">{EMPRESA} · DIAGNÓSTICO PREDICTIVO DE TRANSFORMADORES · {fecha_hoy}</div>',
            unsafe_allow_html=True)