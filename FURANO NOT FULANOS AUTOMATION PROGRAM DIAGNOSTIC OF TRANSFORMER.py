import numpy as np
import matplotlib.pyplot as plt

print("=== SISTEMA PREDICTIVO: SALUD DEL TRANSFORMADOR ===")
trafo_id = input("1. Ingresa el nombre o ID del Transformador (ej. TR-01): ")
furanos = float(input("2. Ingresa la cantidad de Furanos 2-FAL (ppm) del laboratorio: "))

# Calculamos el DP (Grado de Polimerización) del papel
# Si DP > 800 (Papel nuevo), si DP < 200 (Papel destruido / Cortocircuito inminente)
furanos_calc = max(furanos, 0.0001) # Evitamos error si el valor es 0 exacto
dp = (1.51 - np.log10(furanos_calc)) / 0.0035

print("\n--- RESULTADO DEL DIAGNÓSTICO ---")
print(f"Transformador: {trafo_id}")
print(f"Grado de Polimerización (DP) estimado: {dp:.2f}")

# Evaluamos si está "chingado" o no
if dp > 800:
    estado = "ÓPTIMO (Aislamiento como nuevo)"
    color_punto = 'green'
elif dp > 400:
    estado = "DESGASTE NORMAL (Monitoreo de rutina)"
    color_punto = 'gold'
elif dp > 200:
    estado = "ALERTA PREVENTIVA (Papel muy degradado)"
    color_punto = 'darkorange'
else:
    estado = "CRÍTICO / CHINGADO (Riesgo de falla inminente, DP < 200)"
    color_punto = 'red'

print(f"Estado de la celulosa: {estado}")

# --- GENERAR LA GRÁFICA VISUAL ---
# Creamos un fondo con los colores de las zonas de peligro
plt.figure(figsize=(10, 6))
plt.axhspan(800, 1200, color='green', alpha=0.15, label='Zona Óptima')
plt.axhspan(400, 800, color='gold', alpha=0.15, label='Zona de Desgaste')
plt.axhspan(200, 400, color='darkorange', alpha=0.15, label='Zona de Alerta')
plt.axhspan(0, 200, color='red', alpha=0.15, label='Zona Crítica (Destruido)')

# Dibujamos una curva de referencia de cómo decae normalmente
x_ref = np.linspace(0.01, max(15, furanos + 2), 100)
y_ref = (1.51 - np.log10(x_ref)) / 0.0035
plt.plot(x_ref, y_ref, color='black', linestyle='--', alpha=0.5, label='Curva de degradación esperada')

# PONEMOS EL PUNTO EXACTO DE TU TRANSFORMADOR
plt.scatter([furanos], [dp], color=color_punto, s=250, edgecolor='black', zorder=5, 
            label=f'Tu Equipo ({trafo_id})')

# Le ponemos texto al punto para que sea súper claro
plt.annotate(f"  {estado}", (furanos, dp), textcoords="offset points", 
             xytext=(10,0), ha='left', va='center', fontweight='bold', color='black')

# Formato final de la gráfica
plt.title(f'Diagnóstico de Aislamiento - {trafo_id}', fontsize=14, fontweight='bold', pad=15)
plt.xlabel('Moléculas de Furanos en Aceite (ppm)', fontweight='bold')
plt.ylabel('Salud del Papel Dieléctrico (DP)', fontweight='bold')
plt.ylim(0, 1200)
plt.xlim(0, max(10, furanos + 2))
plt.legend(loc='upper right')
plt.grid(True, linestyle=':', alpha=0.7)

plt.tight_layout()
plt.show()