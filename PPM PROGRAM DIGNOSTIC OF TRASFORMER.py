import numpy as np
import matplotlib.pyplot as plt

def simular_furanos_ppm(anos, temp):
    """Calcula matemáticamente los Furanos (PPM) generados por envejecimiento térmico."""
    furanos_base = 0.01 
    tasa_degradacion = (temp - 50) * 0.0038 
    return furanos_base * np.exp(tasa_degradacion * anos)

print("=== SIMULADOR DE CRECIMIENTO DE FURANOS (PPM) ===")
anos_input = float(input("Ingresa los años de operación actuales: "))
temp_input = float(input("Ingresa la temperatura promedio histórica (°C): "))

# 1. Calcular el valor exacto de PPM para tu equipo hoy
ppm_actual = simular_furanos_ppm(anos_input, temp_input)

# 2. Generar arreglos de tiempo para trazar las curvas (0 a 30 años)
anos_array = np.linspace(0, 30, 100)

# Curva 1: El Bueno (Operación óptima a 60°C)
ppm_bueno = simular_furanos_ppm(anos_array, 60)

# Curva 2: El Chingado (Operación crítica/sobrecalentado a 95°C)
ppm_malo = simular_furanos_ppm(anos_array, 95)

# Curva 3: El Tuyo (Basado en la temperatura ingresada)
ppm_tuyo = simular_furanos_ppm(anos_array, temp_input)

# --- CREACIÓN DE LA GRÁFICA (SOLO PPM) ---
plt.figure(figsize=(10, 6))

# Trazar las tres curvas comparativas de crecimiento de Furanos
plt.plot(anos_array, ppm_bueno, color='green', linestyle='--', linewidth=2, label='Referencia: Sano (60°C)')
plt.plot(anos_array, ppm_malo, color='red', linestyle='--', linewidth=2, label='Referencia: Sobrecalentado (95°C)')
plt.plot(anos_array, ppm_tuyo, color='blue', linewidth=3, label=f'Tu Equipo ({temp_input}°C)')

# Marcar el punto exacto donde estás parado hoy
plt.scatter([anos_input], [ppm_actual], color='black', s=100, zorder=5)

# Poner una etiqueta clara con el resultado que vas a exportar al otro programa
plt.annotate(f"  {anos_input} Años\n  PPM Generados: {ppm_actual:.3f}", 
             (anos_input, ppm_actual), textcoords="offset points", xytext=(10, -10), 
             ha='left', fontweight='bold', backgroundcolor='white',
             bbox=dict(boxstyle="round,pad=0.3", edgecolor="blue", facecolor="white", alpha=0.9))

# Formato de la gráfica
plt.title('Simulación de Envejecimiento Químico: Generación de Furanos (PPM)', fontsize=14, fontweight='bold', pad=15)
plt.xlabel('Años de Operación', fontweight='bold')
plt.ylabel('Concentración de Furanos 2-FAL (PPM)', fontweight='bold')

# Escalar el eje Y para que no se dispare al infinito por culpa de la curva roja
# Limitamos la vista a un máximo razonable (ej. 20 ppm)
limite_y = max(15, ppm_actual * 1.5)
plt.ylim(0, limite_y)
plt.xlim(0, 30)

plt.legend(loc='upper left')
plt.grid(True, linestyle=':', alpha=0.7)
plt.tight_layout()
plt.show()

print("\n--- RESULTADO DE LA SIMULACIÓN ---")
print(f"Condiciones: {anos_input} años operando a {temp_input}°C")
print(f"VALOR A EXPORTAR: {ppm_actual:.3f} PPM")