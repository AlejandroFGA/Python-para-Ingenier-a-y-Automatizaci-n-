
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EVALUACION DE MEDIO CURSO - MANTENIMIENTO A SUBESTACIONES ELECTRICAS (UANL-FIME)
Transformador de potencia 30 MVA, 115/13.8 kV, Delta-Estrella (Dyn11)

Simulacion en Python (equivalente a lo que se pide en PSCAD):
  1) Operacion normal 30 ciclos, carga 0 % y 100 %
  2) Corriente de inrush (15 ciclos, 60 Hz)
  3) Proteccion diferencial 87T - falla EXTERNA
  4) Proteccion diferencial 87T - falla INTERNA
  5) Diagrama unifilar

MODELO
  Banco/nucleo de 3 columnas (una por fase). Cada columna se modela en por unidad:
    - devanado delta (primario) alimentado por la fuente de 115 kV
    - impedancia de dispersion  Zcc = Rcc + jXcc  (10 %)
    - rama de magnetizacion NO LINEAL (saturacion) -> permite el inrush
    - devanado estrella (secundario) con carga / falla (conductancia)
  ODE resuelta con scipy (Radau, metodo para sistemas rigidos).

USO:   python simulacion_87T.py
Requiere: numpy, scipy, matplotlib  (reportlab opcional para la hoja PDF)
"""
import os
import numpy as np
from scipy.integrate import solve_ivp
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle
from matplotlib.gridspec import GridSpec

OUT = os.path.dirname(os.path.abspath(__file__))

# =====================================================================
# 1. DATOS DEL TRANSFORMADOR Y DEL SISTEMA
# =====================================================================
S_N, V1_LL, V2_LL, F = 30e6, 115e3, 13.8e3, 60.0
W = 2 * np.pi * F
I1_N = S_N / (np.sqrt(3) * V1_LL)          # 150.6 A  (linea AT)
I2_N = S_N / (np.sqrt(3) * V2_LL)          # 1255 A   (linea BT)
V2_PH = V2_LL / np.sqrt(3)

# bases pico
VB1 = np.sqrt(2) * V1_LL                   # tension de columna delta (= L-L)
IB1_COL = np.sqrt(2) * I1_N / np.sqrt(3)   # corriente de fase del delta
VB2 = np.sqrt(2) * V2_PH                   # tension fase-neutro BT
IB2 = np.sqrt(2) * I2_N                    # corriente BT

# parametros electricos (pu, base 30 MVA)
ZCC, RCC = 0.10, 0.005
R_CC = RCC
X_L = np.sqrt(ZCC**2 - RCC**2)             # reactancia de dispersion
XM = 100.0                                 # corriente de excitacion ~1 %
PSI_K = 1.15                               # rodilla de saturacion (pu de flujo)
X_SAT = 0.15                               # pendiente saturada (nucleo de aire)
PSI_RES = np.array([0.8, -0.4, -0.4])      # flujo remanente para el inrush (pu)

TH = np.array([0.0, -2 * np.pi / 3, 2 * np.pi / 3])   # desfase de cada columna

NS = 64                                    # muestras por ciclo
DT = 1.0 / (F * NS)

# parametros del rele 87T
SLP1, SLP2, BRK, IMIN = 0.25, 0.65, 3.0, 0.20   # pendientes / quiebre / minimo (pu)
H2_BLOQ = 0.15                                  # bloqueo por 2o armonico
TAP_ERR = 0.02                                  # error de relacion TC lado BT (2 %)

G_100, G_0 = 1.0, 1e-4                          # conductancia de carga (pu)
RF = 0.005                                      # resistencia de falla (pu)

COL = ["#d62728", "#1f77b4", "#2ca02c"]
FASES = ["A", "B", "C"]


# =====================================================================
# 2. MODELO (ODE)
# =====================================================================
def im(psi):
    """Corriente de magnetizacion con saturacion suave (pu)."""
    w = 0.03
    ex = np.abs(psi) - PSI_K
    return psi / XM + np.sign(psi) * w * np.logaddexp(0, ex / w) / X_SAT


def rhs(t, y, Rl):
    psi, i1 = y[:3], y[3:]
    v1 = np.sin(W * t + TH)
    e = Rl * (i1 - im(psi))                # tension interna = tension de carga
    dpsi = W * e
    di1 = W * (v1 - R_CC * i1 - e) / X_L
    return np.concatenate([dpsi, di1])


def estado_estable(G):
    y0 = np.concatenate([-np.cos(TH), np.zeros(3)])
    sol = solve_ivp(rhs, (0, 1.0), y0, method="Radau", args=(1 / np.full(3, G),),
                    rtol=1e-8, atol=1e-10, t_eval=[1.0])
    return sol.y[:, -1]


def simular(y0, sched, t_end):
    """sched: lista de dict(t, Gtot[3], Gct[3]).  Gtot = conductancia total en el
    secundario (carga + falla); Gct = parte que 've' el TC del lado BT."""
    y = np.array(y0, float)
    ts, Ys, Gt, Gc = [], [], [], []
    lim = [s["t"] for s in sched] + [t_end]
    for k, s in enumerate(sched):
        ta, tb = lim[k], lim[k + 1]
        n = int(round((tb - ta) / DT))
        te = ta + DT * np.arange(n + 1)
        gt = np.asarray(s["Gtot"], float)
        sol = solve_ivp(rhs, (ta, te[-1]), y, method="Radau", t_eval=te,
                        args=(1 / gt,), rtol=1e-7, atol=1e-9)
        sl = slice(None) if k == len(sched) - 1 else slice(None, -1)
        m = len(te[sl])
        ts.append(te[sl])
        Ys.append(sol.y[:, sl])
        Gt.append(np.tile(gt[:, None], (1, m)))
        Gc.append(np.tile(np.asarray(s["Gct"], float)[:, None], (1, m)))
        y = sol.y[:, -1]
    t = np.concatenate(ts)
    Y = np.hstack(Ys)
    Gt, Gc = np.hstack(Gt), np.hstack(Gc)
    psi, i1 = Y[:3], Y[3:]
    i2 = i1 - im(psi)                      # corriente total del secundario (pu)
    e = i2 / Gt
    return dict(t=t, psi=psi, i1=i1, i2=i2, e=e, i2ct=e * Gc,
                v1=np.sin(W * t[None, :] + TH[:, None]))


def magnitudes(s):
    """Convierte a unidades fisicas (kV, A)."""
    iab, ibc, ica = s["i1"]
    I_AT = np.array([iab - ica, ibc - iab, ica - ibc]) * IB1_COL
    V_AT = s["v1"] * VB1 / 1e3
    e = s["e"]
    V_BT = np.array([e[0] - e[1], e[1] - e[2], e[2] - e[0]]) * VB2 / 1e3
    I_BT = s["i2ct"] * IB2
    return V_AT, I_AT, V_BT, I_BT


def rms(x):
    return np.sqrt(np.mean(x**2, axis=-1))


# =====================================================================
# 3. RELE DIFERENCIAL 87T
# =====================================================================
def dft(x, k=1, N=NS):
    n = np.arange(N)
    h = (2.0 / N) * np.exp(-2j * np.pi * k * (N - 1 - n) / N)
    return np.convolve(x, h)[: len(x)]


def entradas_rele(s):
    """Corrientes en pu (base de linea) ya con compensacion de grupo:
    AT (delta) -> TC en estrella ; BT (estrella) -> combinacion (Ia-Ic)/sqrt3."""
    iab, ibc, ica = s["i1"]
    I1 = np.array([iab - ica, ibc - iab, ica - ibc]) / np.sqrt(3)
    Ia, Ib, Ic = s["i2ct"] * (1 - TAP_ERR)
    I2 = np.array([Ia - Ic, Ib - Ia, Ic - Ib]) / np.sqrt(3)
    return I1, I2


def umbral(irest):
    f = np.where(irest < BRK, SLP1 * irest, SLP1 * BRK + SLP2 * (irest - BRK))
    return np.maximum(f, IMIN)


def rele_87T(s):
    I1, I2 = entradas_rele(s)
    t = s["t"]
    valido = np.arange(len(t)) >= NS - 1   # el filtro necesita 1 ciclo
    idif = np.zeros_like(I1)
    irest = np.zeros_like(I1)
    h2 = np.zeros_like(I1)
    for k in range(3):
        d = I1[k] - I2[k]
        D1, D2 = dft(d, 1), dft(d, 2)
        idif[k] = np.abs(D1)
        irest[k] = (np.abs(dft(I1[k])) + np.abs(dft(I2[k]))) / 2
        h2[k] = np.abs(D2) / np.maximum(np.abs(D1), 1e-9)
    raw = (idif > umbral(irest)) & valido
    nper = NS // 4                          # seguridad: 1/4 de ciclo sostenido
    trip_ph = np.array([np.convolve(x.astype(float), np.ones(nper))[: len(x)] >= nper for x in raw])
    bloq = (h2 > H2_BLOQ).any(axis=0)
    return dict(t=t, idif=idif, irest=irest, h2=h2,
                trip_ph=trip_ph.astype(float),
                trip_sin=trip_ph.any(axis=0).astype(float),
                trip_con=(trip_ph & ~bloq).any(axis=0).astype(float))


def t_disparo(t, trip, tf):
    idx = np.where((t >= tf) & (trip > 0))[0]
    return None if len(idx) == 0 else t[idx[0]] - tf


# =====================================================================
# 4. PUNTO 1 - OPERACION NORMAL
# =====================================================================
def punto1():
    res = {}
    fig, ax = plt.subplots(4, 2, figsize=(15, 12.5), sharex=True)
    for c, (nom, G) in enumerate([("0 %", G_0), ("100 %", G_100)]):
        s = simular(estado_estable(G), [dict(t=0.0, Gtot=[G] * 3, Gct=[G] * 3)], 0.5)
        V_AT, I_AT, V_BT, I_BT = magnitudes(s)
        r = dict(V_AT=rms(V_AT).mean(), I_AT=rms(I_AT).mean(),
                 V_BT=rms(V_BT).mean(), I_BT=rms(I_BT).mean())
        res[nom] = r
        datos = [(V_AT, "Tensión AT línea-línea [kV]", f"V_AT = {r['V_AT']:.2f} kV rms"),
                 (I_AT, "Corriente AT de línea [A]", f"I_AT = {r['I_AT']:.1f} A rms"),
                 (V_BT, "Tensión BT línea-línea [kV]", f"V_BT = {r['V_BT']:.2f} kV rms"),
                 (I_BT, "Corriente BT de línea [A]", f"I_BT = {r['I_BT']:.0f} A rms")]
        for rw, (y, lab, txt) in enumerate(datos):
            a = ax[rw, c]
            for k in range(3):
                a.plot(s["t"], y[k], color=COL[k], lw=1.3, label=f"Fase {FASES[k]}")
            a.set_ylabel(lab, fontsize=9)
            a.grid(alpha=.3)
            a.text(0.015, 0.93, txt, transform=a.transAxes, va="top", fontsize=10,
                   bbox=dict(boxstyle="round", fc="white", ec="gray"))
            if rw == 1 and c == 0:
                a.set_ylim(-3, 3)           # con 0 % solo hay corriente de excitación
        ax[0, c].set_title(f"Cargabilidad {nom}  (30 ciclos = 0.5 s)", fontweight="bold")
        ax[3, c].set_xlabel("Tiempo [s]")
    ax[0, 0].legend(loc="upper right", ncol=3, fontsize=8)
    fig.suptitle("PUNTO 1 - Tensiones y corrientes nominales, Transformador 30 MVA 115/13.8 kV Dyn11",
                 fontsize=13, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, .97])
    fig.savefig(os.path.join(OUT, "punto1_operacion_normal.png"), dpi=130)
    plt.close(fig)
    return res


# =====================================================================
# 5. PUNTO 2 - INRUSH
# =====================================================================
def punto2():
    y0 = np.concatenate([PSI_RES, im(PSI_RES)])
    s = simular(y0, [dict(t=0.0, Gtot=[G_0] * 3, Gct=[G_0] * 3)], 15 / F)
    _, I_AT, _, _ = magnitudes(s)
    r = rele_87T(s)
    t = s["t"]
    pico = np.abs(I_AT).max()
    pico_nom = np.sqrt(2) * I1_N
    res = dict(pico=pico, veces=pico / pico_nom,
               h2max=float(r["h2"][:, NS * 3:].max(axis=0).max()),
               trip_sin=t_disparo(t, r["trip_sin"], 0.0),
               trip_con=t_disparo(t, r["trip_con"], 0.0))

    fig, ax = plt.subplots(4, 1, figsize=(13, 12), sharex=True)
    for k in range(3):
        ax[0].plot(t, I_AT[k], color=COL[k], lw=1.3, label=f"Fase {FASES[k]}")
        ax[1].plot(t, s["psi"][k], color=COL[k], lw=1.3, label=f"Columna {FASES[k]}")
        ax[2].plot(t[NS:], 100 * r["h2"][k][NS:], color=COL[k], lw=1.3)
    ax[0].set_ylabel("Corriente AT de línea [A]")
    ax[0].text(0.015, 0.95, f"Pico = {pico:.0f} A  ({res['veces']:.1f} × I_nom pico = {pico_nom:.0f} A)",
               transform=ax[0].transAxes, va="top", bbox=dict(boxstyle="round", fc="white", ec="gray"))
    ax[0].axhline(pico_nom, color="k", ls=":", lw=1)
    ax[0].axhline(-pico_nom, color="k", ls=":", lw=1)
    ax[0].legend(loc="upper right", ncol=3)
    ax[1].axhline(PSI_K, color="k", ls="--", lw=1)
    ax[1].axhline(-PSI_K, color="k", ls="--", lw=1)
    ax[1].set_ylabel("Flujo en el núcleo [pu]")
    ax[1].text(0.015, 0.93, "Líneas punteadas = rodilla de saturación (1.15 pu)", transform=ax[1].transAxes,
               va="top", fontsize=9)
    ax[2].axhline(100 * H2_BLOQ, color="k", ls="--", lw=1)
    ax[2].set_ylabel("2º armónico / fundamental [%]")
    ax[2].set_ylim(0, 100)
    ax[2].text(0.015, 0.93, "Línea punteada = umbral de bloqueo (15 %)", transform=ax[2].transAxes,
               va="top", fontsize=9)
    ax[3].step(t, r["trip_sin"], where="post", color="tab:red", lw=2, label="87T sin restricción de armónicos")
    ax[3].step(t, r["trip_con"] * 0.9, where="post", color="tab:green", lw=2, label="87T con bloqueo por 2º armónico")
    ax[3].set_ylim(-.1, 1.3)
    ax[3].set_yticks([0, 1])
    ax[3].set_ylabel("Salida del relé")
    ax[3].legend(loc="upper right")
    ax[3].set_xlabel("Tiempo [s]   (15 ciclos = 0.25 s)")
    for a in ax:
        a.grid(alpha=.3)
    fig.suptitle("PUNTO 2 - Corriente de inrush (energización en vacío, 60 Hz, flujo remanente 0.8 pu)",
                 fontsize=13, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, .97])
    fig.savefig(os.path.join(OUT, "punto2_inrush.png"), dpi=130)
    plt.close(fig)
    return res


# =====================================================================
# 6. PUNTOS 3 y 4 - PROTECCION 87T
# =====================================================================
def punto_falla(tipo, Gf, archivo, titulo, tf=0.10, t_end=0.25):
    G0 = estado_estable(G_100)
    Gtot_f = np.array([G_100 + Gf[k] for k in range(3)])
    Gct_f = Gtot_f if tipo == "externa" else np.full(3, G_100)   # interna: el TC BT no ve la falla
    s = simular(G0, [dict(t=0.0, Gtot=[G_100] * 3, Gct=[G_100] * 3),
                     dict(t=tf, Gtot=Gtot_f, Gct=Gct_f)], t_end)
    _, I_AT, _, I_BT = magnitudes(s)
    r = rele_87T(s)
    t = s["t"]
    td = t_disparo(t, r["trip_sin"], tf)
    pre = r["trip_sin"][t < tf].any()
    ipost = (t > tf + 1.5 / F)
    res = dict(td=td, falso_pre=bool(pre),
               idif_max=float(r["idif"][:, ipost].max()),
               irest_max=float(r["irest"][:, ipost].max()),
               iat_pico=float(np.abs(I_AT).max()), ibt_pico=float(np.abs(I_BT).max()))

    fig = plt.figure(figsize=(15, 12))
    gs = GridSpec(4, 2, width_ratios=[2.2, 1], figure=fig)
    axs = [fig.add_subplot(gs[0, 0])]
    for i in range(1, 4):
        axs.append(fig.add_subplot(gs[i, 0], sharex=axs[0]))
    for k in range(3):
        axs[0].plot(t, I_AT[k], color=COL[k], lw=1.2, label=f"Fase {FASES[k]}")
        axs[1].plot(t, I_BT[k] / 1e3, color=COL[k], lw=1.2)
        axs[2].plot(t, r["idif"][k], color=COL[k], lw=1.6, label=f"Idif {FASES[k]}")
        axs[2].plot(t, r["irest"][k], color=COL[k], lw=1.0, ls="--", label=f"Irest {FASES[k]}")
    axs[0].set_ylabel("Corriente AT (TC1) [A]")
    axs[1].set_ylabel("Corriente BT (TC2) [kA]")
    axs[2].set_ylabel("Idif / Irest [pu]")
    axs[2].axhline(IMIN, color="k", ls=":", lw=1)
    axs[2].text(0.005, IMIN + 0.2, "Imín = 0.2 pu", fontsize=8)
    axs[3].step(t, r["trip_sin"], where="post", color="k", lw=2.5, label="Salida 87T (disparo)")
    for k in range(3):
        axs[3].step(t, r["trip_ph"][k] * (0.9 - 0.08 * k), where="post", color=COL[k], lw=1, ls="--",
                    label=f"87T-{FASES[k]}")
    axs[3].set_ylim(-.1, 1.35)
    axs[3].set_yticks([0, 1])
    axs[3].set_ylabel("Señal de salida del relé")
    axs[3].set_xlabel("Tiempo [s]   (15 ciclos = 0.25 s)")
    for a in axs:
        a.axvline(tf, color="gray", ls="-.", lw=1.2)
        a.grid(alpha=.3)
    axs[0].legend(loc="upper left", ncol=3, fontsize=8)
    axs[2].legend(loc="upper left", ncol=3, fontsize=7)
    axs[3].legend(loc="upper left", ncol=4, fontsize=8)
    axs[0].text(tf + .002, axs[0].get_ylim()[1] * .85, "inicio de falla", fontsize=9, color="gray")
    txt = "NO DISPARA (restringe)" if td is None else f"DISPARA en {td*1000:.1f} ms ({td*F:.2f} ciclos)"
    axs[3].text(0.60, 0.55, txt, transform=axs[3].transAxes, fontsize=12, fontweight="bold",
                color=("tab:green" if td is None else "tab:red"),
                bbox=dict(boxstyle="round", fc="white", ec="gray"))

    # plano de operacion
    axc = fig.add_subplot(gs[0:2, 1])
    xm = max(res["irest_max"] * 1.15, 6)
    ym = max(res["idif_max"] * 1.15, 6)
    x = np.linspace(0, xm, 400)
    axc.fill_between(x, umbral(x), ym * 2, color="#ffcccc", alpha=.7, label="Zona de operación")
    axc.fill_between(x, 0, umbral(x), color="#ccffcc", alpha=.7, label="Zona de restricción")
    axc.plot(x, umbral(x), "k", lw=2)
    v = np.arange(len(t)) >= NS - 1
    for k in range(3):
        axc.plot(r["irest"][k][v], r["idif"][k][v], color=COL[k], lw=1.2, marker=".", ms=2,
                 label=f"fase {FASES[k]}")
    axc.set_xlim(0, xm)
    axc.set_ylim(0, ym)
    axc.set_xlabel("Irest [pu]")
    axc.set_ylabel("Idif [pu]")
    axc.set_title("Característica de operación 87T\n(25 % / 65 %, quiebre 3 pu)", fontsize=10)
    axc.legend(fontsize=7, loc="upper left")
    axc.grid(alpha=.3)

    axt = fig.add_subplot(gs[2:4, 1])
    axt.axis("off")
    ft = {"externa": "Falla trifásica en barra de 13.8 kV, DESPUÉS del TC2",
          "interna": "Falla fase A-tierra en terminales BT del transformador, ANTES del TC2"}[tipo]
    lineas = [ft, "",
              f"Corriente de falla pico AT: {res['iat_pico']:.0f} A",
              (f"Corriente pico BT (TC2): {res['ibt_pico']/1e3:.1f} kA" if tipo == "externa" else
               "El TC2 NO ve la corriente de falla\n(solo corriente de carga)"), "",
              f"Idif máx: {res['idif_max']:.2f} pu",
              f"Irest máx: {res['irest_max']:.2f} pu",
              f"Umbral en ese Irest: {float(umbral(np.array(res['irest_max']))):.2f} pu", "",
              "Resultado: " + ("el relé NO opera" if td is None else "el relé OPERA")]
    axt.text(0, 1, "\n".join(lineas), va="top", fontsize=10.5,
             bbox=dict(boxstyle="round", fc="#f7f7f7", ec="gray"), wrap=True)
    fig.suptitle(titulo, fontsize=13, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, .97])
    fig.savefig(os.path.join(OUT, archivo), dpi=130)
    plt.close(fig)
    return res


# =====================================================================
# 7. PUNTO 5 - DIAGRAMA UNIFILAR
# =====================================================================
def unifilar():
    fig, ax = plt.subplots(figsize=(15, 7.6))
    ax.set_xlim(0, 15)
    ax.set_ylim(0, 8)
    ax.axis("off")
    y = 5.0
    lw = 2.2
    # fuente
    ax.add_patch(Circle((1.0, y), 0.5, fill=False, lw=lw))
    ax.text(1.0, y, "~", ha="center", va="center", fontsize=24)
    ax.text(1.0, y + 0.75, "Red 115 kV\n60 Hz", ha="center", fontsize=9)
    # lineas principales
    ax.plot([1.5, 6.05], [y, y], "k", lw=lw)
    ax.plot([8.25, 12.5], [y, y], "k", lw=lw)
    # interruptores
    for xb, nom in [(2.7, "52-1"), (10.2, "52-2")]:
        ax.add_patch(Rectangle((xb, y - .25), .5, .5, fc="white", ec="k", lw=lw, zorder=3))
        ax.text(xb + .25, y + .45, nom, ha="center", fontsize=9)
    # TC
    for xc, nom in [(4.6, "TC1  200:5\n(conexión Y)"), (9.2, "TC2  1500:5\n(Δ comp. en relé)")]:
        ax.add_patch(Circle((xc, y), 0.28, fc="white", ec="tab:blue", lw=lw, zorder=3))
        ax.text(xc, y + .45, nom, ha="center", fontsize=8.5, color="tab:blue")
    # transformador
    ax.add_patch(Circle((6.7, y), 0.65, fill=False, lw=lw))
    ax.add_patch(Circle((7.6, y), 0.65, fill=False, lw=lw))
    ax.text(6.4, y, "Δ", ha="center", va="center", fontsize=20)
    ax.text(7.9, y, "Y", ha="center", va="center", fontsize=18)
    ax.text(7.15, y + 0.95, "T1   30 MVA   115/13.8 kV   Dyn11   Zcc = 10 %", ha="center", fontsize=9, fontweight="bold")
    # neutro a tierra
    ax.plot([7.9, 7.9], [y - .55, y - 1.0], "k", lw=lw)
    for i, wd in enumerate([.35, .22, .1]):
        ax.plot([7.9 - wd, 7.9 + wd], [y - 1.0 - .1 * i] * 2, "k", lw=lw)
    # zona de proteccion
    ax.add_patch(Rectangle((4.6, y - 1.9), 4.6, 3.9, fill=False, ec="tab:red", ls="--", lw=1.6))
    ax.text(6.9, y + 1.45, "ZONA PROTEGIDA 87T", ha="center", color="tab:red", fontsize=10, fontweight="bold")
    # carga
    ax.plot([12.5, 12.5], [y, y - .6], "k", lw=lw)
    zx = [12.5, 12.2, 12.8, 12.2, 12.8, 12.2, 12.5]
    zy = np.linspace(y - .6, y - 2.0, len(zx))
    ax.plot(zx, zy, "k", lw=lw)
    ax.plot([12.5, 12.5], [y - 2.0, y - 2.3], "k", lw=lw)
    for i, wd in enumerate([.35, .22, .1]):
        ax.plot([12.5 - wd, 12.5 + wd], [y - 2.3 - .1 * i] * 2, "k", lw=lw)
    ax.text(13.0, y - 1.3, "Carga\n0 % / 100 %\n(30 MVA)", fontsize=9, va="center")
    ax.text(11.5, y + .45, "Barra 13.8 kV", fontsize=9, ha="center")

    def rayo(x, ydir, etq, dx, ha):
        y0 = y + .05 * ydir
        pts = [(x, y0), (x - .12, y0 + .35 * ydir), (x + .12, y0 + .6 * ydir),
               (x - .12, y0 + .95 * ydir), (x, y0 + 1.25 * ydir)]
        ax.plot(*zip(*pts), color="tab:red", lw=2)
        ax.annotate("", xy=(x, y0 + 1.5 * ydir), xytext=(x, y0 + 1.2 * ydir),
                    arrowprops=dict(arrowstyle="-|>", color="tab:red", lw=2))
        ax.text(x + dx, y0 + 1.0 * ydir, etq, color="tab:red", fontsize=9, fontweight="bold", ha=ha)

    rayo(11.4, -1, "F1\nexterna", -.2, "right")
    rayo(8.65, -1, "F2\ninterna", .15, "left")
    ax.text(14.9, 0.35, "F1 = falla externa (fuera de la zona, después del TC2)\n"
            "F2 = falla interna (dentro de la zona, antes del TC2)", color="tab:red", fontsize=9,
            ha="right", va="bottom")
    # rele
    ax.add_patch(Rectangle((5.5, 1.0), 2.8, 1.0, fc="#fff3cd", ec="k", lw=lw))
    ax.text(6.9, 1.5, "RELÉ 87T\nIdif = |I1 − I2c|   Irest = (|I1|+|I2c|)/2",
            ha="center", va="center", fontsize=8.5, fontweight="bold")
    ax.plot([4.6, 4.6, 5.5], [y - .28, 1.5, 1.5], color="tab:blue", lw=1.6)
    ax.plot([9.2, 9.2, 8.3], [y - .28, 1.5, 1.5], color="tab:blue", lw=1.6)
    ax.plot([6.9, 6.9, 2.95, 2.95], [1.0, .5, .5, y - .25], color="tab:red", lw=1.6, ls=":")
    ax.plot([6.9, 10.45, 10.45], [.5, .5, y - .25], color="tab:red", lw=1.6, ls=":")
    ax.text(3.0, .7, "Disparo 87T", color="tab:red", fontsize=9)
    ax.set_title("PUNTO 5 - Diagrama unifilar del sistema de prueba (protección diferencial 87T)",
                 fontsize=13, fontweight="bold")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "punto5_diagrama_unifilar.png"), dpi=130)
    plt.close(fig)


# =====================================================================
# 8. HOJA DE RESPUESTAS (PDF)
# =====================================================================
def hoja_pdf(r1, r2, r3, r4):
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak, Table, TableStyle)
        from reportlab.lib import colors
        from PIL import Image as PI
    except ImportError:
        print("reportlab/Pillow no instalado: se omite el PDF.")
        return
    st = getSampleStyleSheet()
    doc = SimpleDocTemplate(os.path.join(OUT, "hoja_de_respuestas.pdf"), pagesize=letter,
                            leftMargin=1.5 * cm, rightMargin=1.5 * cm, topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    W_ = letter[0] - 3 * cm

    def img(nombre):
        p = os.path.join(OUT, nombre)
        w, h = PI.open(p).size
        return Image(p, width=W_, height=W_ * h / w)

    def td(x):
        return "no dispara" if x is None else f"{x*1000:.1f} ms ({x*F:.2f} ciclos)"

    S = []
    S.append(Paragraph("UNIVERSIDAD AUTÓNOMA DE NUEVO LEÓN - FIME", st["Title"]))
    S.append(Paragraph("EVALUACIÓN DE MEDIO CURSO - MANTENIMIENTO A SUBESTACIONES ELÉCTRICAS", st["Heading3"]))
    T = Table([["Nombre Completo:", ""], ["Matrícula:", ""], ["Grupo:", ""], ["Fecha:", ""]],
              colWidths=[4 * cm, 12 * cm], rowHeights=[.8 * cm] * 4)
    T.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), .8, colors.black)]))
    S += [T, Spacer(1, .5 * cm), Paragraph("<b>HOJA DE RESPUESTAS</b>", st["Heading2"]),
          Paragraph("Transformador de potencia 30 MVA, 115/13.8 kV, conexión Delta-Y (Dyn11). "
                    "I nominal AT = 150.6 A, I nominal BT = 1255 A. Zcc = 10 %.", st["Normal"]),
          Spacer(1, .4 * cm),
          Paragraph("<b>1. Operación normal, 30 ciclos.</b>", st["Normal"]), img("punto1_operacion_normal.png"),
          Paragraph(f"Con 0 %: V_AT = {r1['0 %']['V_AT']:.1f} kV, V_BT = {r1['0 %']['V_BT']:.2f} kV, corriente solo de "
                    f"excitación. Con 100 %: I_AT = {r1['100 %']['I_AT']:.1f} A, I_BT = {r1['100 %']['I_BT']:.0f} A "
                    f"(V_BT = {r1['100 %']['V_BT']:.2f} kV).", st["Normal"]),
          PageBreak(),
          Paragraph("<b>2. Corriente de inrush, 15 ciclos, 60 Hz.</b>", st["Normal"]), img("punto2_inrush.png"),
          Paragraph(f"Pico = {r2['pico']:.0f} A ({r2['veces']:.1f} veces la corriente nominal pico). Contenido de 2º armónico "
                    f"hasta {100*r2['h2max']:.0f} %, por eso se usa el bloqueo por armónicos.", st["Normal"]),
          PageBreak(),
          Paragraph("<b>3. Protección 87T, falla EXTERNA.</b>", st["Normal"]), img("punto3_87T_falla_externa.png"),
          Paragraph(f"Idif máx = {r3['idif_max']:.2f} pu con Irest = {r3['irest_max']:.2f} pu: el punto queda en la zona de "
                    f"restricción. Salida del relé: {td(r3['td'])}.", st["Normal"]),
          PageBreak(),
          Paragraph("<b>4. Protección 87T, falla INTERNA.</b>", st["Normal"]), img("punto4_87T_falla_interna.png"),
          Paragraph(f"Idif máx = {r4['idif_max']:.2f} pu, Irest = {r4['irest_max']:.2f} pu: el punto cae en la zona de "
                    f"operación. Tiempo de disparo: {td(r4['td'])}.", st["Normal"]),
          PageBreak(),
          Paragraph("<b>5. Diagrama unifilar del sistema de prueba.</b>", st["Normal"]),
          img("punto5_diagrama_unifilar.png")]
    doc.build(S)


# =====================================================================
if __name__ == "__main__":
    print("== Datos: I_nom AT = %.1f A, I_nom BT = %.0f A ==" % (I1_N, I2_N))
    r1 = punto1()
    for k, v in r1.items():
        print(f"[P1] carga {k:>5}:  V_AT={v['V_AT']:.2f} kV  I_AT={v['I_AT']:.1f} A  "
              f"V_BT={v['V_BT']:.3f} kV  I_BT={v['I_BT']:.1f} A")
    r2 = punto2()
    print(f"[P2] inrush: pico={r2['pico']:.0f} A ({r2['veces']:.1f} x Inom pico), "
          f"2o arm. max={100*r2['h2max']:.0f} %, "
          f"87T sin bloqueo dispara: {r2['trip_sin']}, con bloqueo: {r2['trip_con']}")
    r3 = punto_falla("externa", [1 / RF] * 3, "punto3_87T_falla_externa.png",
                     "PUNTO 3 - 87T con FALLA EXTERNA (trifásica en barra de 13.8 kV, fuera de la zona)")
    print(f"[P3] externa: Idif max={r3['idif_max']:.2f} pu, Irest max={r3['irest_max']:.2f} pu, "
          f"disparo={r3['td']}, falso disparo previo={r3['falso_pre']}")
    r4 = punto_falla("interna", [1 / RF, 0, 0], "punto4_87T_falla_interna.png",
                     "PUNTO 4 - 87T con FALLA INTERNA (fase A-tierra dentro de la zona del transformador)")
    print(f"[P4] interna: Idif max={r4['idif_max']:.2f} pu, Irest max={r4['irest_max']:.2f} pu, "
          f"disparo={r4['td']}, falso disparo previo={r4['falso_pre']}")
    unifilar()
    hoja_pdf(r1, r2, r3, r4)
    print("Listo. Imagenes y PDF guardados en:", OUT)
