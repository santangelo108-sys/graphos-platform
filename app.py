import streamlit as st
import json
import os
import pandas as pd
import anthropic
import plotly.express as px
from neo4j import GraphDatabase
from datetime import datetime

st.set_page_config(
    page_title="Graphos Platform",
    page_icon="🕸️",
    layout="wide",
    initial_sidebar_state="expanded"
)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# Proyectos hardcodeados como base + los que se agreguen en sesion
PROYECTOS_DEFAULT = {
    "escuela_graphos": {
        "nombre": "Escuela Graphos",
        "descripcion": "Sistema educativo con estudiantes, calificaciones, asistencias y convivencia",
        "neo4j_uri": "neo4j+s://7c3c4e8f.databases.neo4j.io",
        "neo4j_user": "7c3c4e8f",
        "neo4j_password": os.environ.get("NEO4J_PASSWORD", ""),
        "schema_texto": """
Nodos: Estudiante(nombre, apellido, grado, perfil), Docente(nombre, apellido),
Materia(nombre), Calificacion(nota, periodo, aprobado), Ausencia(fecha, justificada),
EventoConvivencia(tipo, positivo, fecha), Matricula(estado_pago, costo_mensual, meses_adeudados)
Relaciones:
(Estudiante)-[:OBTUVO]->(Calificacion)-[:EN_MATERIA]->(Materia)
(Estudiante)-[:TUVO_AUSENCIA]->(Ausencia)
(Estudiante)-[:INVOLUCRADO_EN]->(EventoConvivencia)
(Estudiante)-[:TIENE_MATRICULA]->(Matricula)
(Estudiante)-[:PERTENECE_A]->(Grado)
(Representante)-[:REPRESENTA_A]->(Estudiante)
(Docente)-[:ENSEÑA]->(Materia)
Valores: grados: 5to,6to,7mo,8vo,9no,10mo,1BGU,2BGU,3BGU
periodos: 2024-P1,2024-P2,2024-P3,2024-P4
estado_pago: al_dia, mora_1mes, mora
