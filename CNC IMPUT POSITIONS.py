import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

st.set_page_config(page_title="Simulador de Trayectoria CNC", layout="wide")
st.title("Visualización de Trayectoria XYZ - Silueta de Avión")

trayectoria = [
    {"Paso": "Inicio/Aproximación", "X": 17.0, "Y": 7.0, "Z": 5.0},
    {"Paso": "Penetración (G01)", "X": 17.0, "Y": 7.0, "Z": -5.0},
    {"Paso": "Contorno", "X": 17.0, "Y": 9.0, "Z": -5.0},
    {"Paso": "Contorno", "X": 21.0, "Y": 13.0, "Z": -5.0},
    {"Paso": "Contorno", "X": 21.0, "Y": 20.0, "Z": -5.0},
    {"Paso": "Contorno", "X": 9.0, "Y": 17.0, "Z": -5.0},
    {"Paso": "Contorno", "X": 9.0, "Y": 22.0, "Z": -5.0},
    {"Paso": "Contorno", "X": 21.0, "Y": 30.0, "Z": -5.0},
    {"Paso": "Contorno", "X": 21.0, "Y": 43.0, "Z": -5.0},
    {"Paso": "Arco G02 (Fin)", "X": 29.0, "Y": 43.0, "Z": -5.0},
    {"Paso": "Contorno", "X": 29.0, "Y": 30.0, "Z": -5.0},
    {"Paso": "Contorno", "X": 41.0, "Y": 22.0, "Z": -5.0},
    {"Paso": "Contorno", "X": 41.0, "Y": 17.0, "Z": -5.0},
    {"Paso": "Contorno", "X": 29.0, "Y": 20.0, "Z": -5.0},
    {"Paso": "Contorno", "X": 29.0, "Y": 13.0, "Z": -5.0},
    {"Paso": "Contorno", "X": 33.0, "Y": 9.0, "Z": -5.0},
    {"Paso": "Contorno", "X": 33.0, "Y": 7.0, "Z": -5.0},
    {"Paso": "Cierre Perfil", "X": 17.0, "Y": 7.0, "Z": -5.0},
    {"Paso": "Retracción", "X": 17.0, "Y": 7.0, "Z": 10.0}
]

df = pd.DataFrame(trayectoria)

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("Tabla de Coordenadas Absolutas")
    # Corrección aplicada aquí según la advertencia de tu terminal
    st.dataframe(df, width='stretch')

with col2:
    st.subheader("Gráfico Espacial 3D (Toolpath)")
    
    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection='3d')
    
    ax.plot(df['X'], df['Y'], df['Z'], color='blue', linewidth=2, marker='o', markersize=4, label='Trayectoria Herramienta')
    
    ax.scatter(df['X'].iloc[0], df['Y'].iloc[0], df['Z'].iloc[0], color='green', s=100, label='Inicio (G00)')
    ax.scatter(df['X'].iloc[-1], df['Y'].iloc[-1], df['Z'].iloc[-1], color='red', s=100, label='Fin/Retracción')

    ax.set_xlabel('Eje X (mm)')
    ax.set_ylabel('Eje Y (mm)')
    ax.set_zlabel('Eje Z (mm) - Profundidad')
    ax.set_title('Trayectoria de Fresado G-Code')
    ax.legend()
    
    st.pyplot(fig)