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

PROYECTOS_DEFAULT = {
    "escuela_graphos": {
        "nombre": "Escuela Graphos",
        "descripcion": "Sistema educativo con estudiantes, calificaciones, asistencias y convivencia",
        "neo4j_uri": os.environ.get("NEO4J_URI", ""),
        "neo4j_user": os.environ.get("NEO4J_USER", ""),
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
estado_pago: al_dia, mora_1mes, mora_2meses, becado, exonerado
Nota minima aprobatoria: 7.0
""",
        "creado": "2024-01-01"
    },
    "life_compass": {
        "nombre": "Life Compass",
        "descripcion": "Seguimiento semanal de categorias de vida personal con puntajes 0-100",
        "neo4j_uri": os.environ.get("NEO4J_URI", ""),
        "neo4j_user": os.environ.get("NEO4J_USER", ""),
        "neo4j_password": os.environ.get("NEO4J_PASSWORD", ""),
        "schema_texto": """
Nodos: LCCategoria(nombre), LCSubcategoria(nombre, categoria),
LCEvaluacion(fecha, semana), LCPuntaje(valor, fecha, tipo)
Relaciones:
(LCEvaluacion)-[:INCLUYE]->(LCPuntaje)-[:DE_CATEGORIA]->(LCCategoria)
(LCEvaluacion)-[:INCLUYE]->(LCPuntaje)-[:DE_SUBCATEGORIA]->(LCSubcategoria)
(LCSubcategoria)-[:PERTENECE_A]->(LCCategoria)
Categorias: Body, Mind, Work, Energy, Love, Money and Finances, Admin,
Trauma Healing, Health and Fitness, Partner and Love, Fun and Recreation,
Spirituality, Creative Force
Valores: puntajes de 0 a 100, fechas en formato YYYY-MM-DD
""",
        "creado": "2026-05-24"
    }
}

st.markdown("""
<style>
section[data-testid="stMain"] { background-color: #ffffff !important; }
section[data-testid="stSidebar"] { background-color: #f3f4f6 !important; }
section[data-testid="stSidebar"] * { color: #111827 !important; }
.block-container { background-color: #ffffff !important; }
h1, h2, h3, h4, p, span, div, label { color: #111827 !important; }
.main-title { font-size: 28px; font-weight: 800; color: #7c3aed !important; margin-bottom: 4px; }
.main-subtitle { font-size: 14px; color: #6b7280 !important; margin-bottom: 24px; }
.proyecto-card {
    background: #f9fafb;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    padding: 20px 24px;
    margin-bottom: 12px;
}
.proyecto-titulo { font-size: 17px; font-weight: 700; color: #7c3aed !important; }
.proyecto-desc { font-size: 13px; color: #6b7280 !important; margin-top: 6px; }
.metric-card {
    background: #f9fafb;
    border: 1px solid #e5e7eb;
    border-radius: 10px;
    padding: 16px;
    text-align: center;
}
.metric-value { font-size: 32px; font-weight: 800; color: #7c3aed !important; }
.metric-label { font-size: 12px; color: #6b7280 !important; margin-top: 4px; }
div[data-testid="stChatMessage"] {
    background: #f9fafb !important;
    border-radius: 12px;
    margin-bottom: 8px;
}
</style>
""", unsafe_allow_html=True)

def cargar_proyectos():
    if "proyectos" not in st.session_state:
        st.session_state.proyectos = PROYECTOS_DEFAULT.copy()
    return st.session_state.proyectos

def guardar_proyecto_nuevo(key, datos):
    if "proyectos" not in st.session_state:
        st.session_state.proyectos = PROYECTOS_DEFAULT.copy()
    st.session_state.proyectos[key] = datos

def probar_conexion(uri, user, password):
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        driver.verify_connectivity()
        driver.close()
        return True, "Conexion exitosa"
    except Exception as e:
        return False, str(e)

def ejecutar_cypher(uri, user, password, cypher):
    driver = GraphDatabase.driver(uri, auth=(user, password))
    with driver.session() as s:
        resultado = s.run(cypher).data()
    driver.close()
    return resultado

def chat_con_grafo(pregunta, proyecto):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    sistema = f"""Eres un asistente experto del proyecto '{proyecto['nombre']}'.
{proyecto['schema_texto']}
Convierte la pregunta del usuario a Cypher para Neo4j.
Devuelve UNICAMENTE el Cypher, sin explicaciones ni bloques de codigo."""

    r1 = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        system=sistema,
        messages=[{"role": "user", "content": pregunta}]
    )
    cypher = r1.content[0].text.strip()

    try:
        datos = ejecutar_cypher(
            proyecto['neo4j_uri'],
            proyecto['neo4j_user'],
            proyecto['neo4j_password'],
            cypher
        )
        error = None
    except Exception as e:
        datos = []
        error = str(e)

    if error:
        return f"Error al ejecutar la consulta: {error}", cypher

    r2 = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=600,
        system=f"""Eres un asistente del proyecto '{proyecto['nombre']}'.
Interpreta los datos y responde en español claro y util.
Usa tablas markdown cuando haya listas de datos.
Maximo 8 lineas.""",
        messages=[{"role": "user", "content":
            f"Pregunta: {pregunta}\nDatos: {datos}"}]
    )
    return r2.content[0].text, cypher

def obtener_metricas(proyecto):
    try:
        conteo = ejecutar_cypher(
            proyecto['neo4j_uri'],
            proyecto['neo4j_user'],
            proyecto['neo4j_password'],
            "MATCH (n) RETURN labels(n)[0] AS tipo, count(n) AS total ORDER BY total DESC"
        )
        relaciones = ejecutar_cypher(
            proyecto['neo4j_uri'],
            proyecto['neo4j_user'],
            proyecto['neo4j_password'],
            "MATCH ()-[r]->() RETURN count(r) AS total"
        )
        return conteo, relaciones[0]['total'] if relaciones else 0
    except:
        return [], 0

if "pagina" not in st.session_state:
    st.session_state.pagina = "inicio"
if "proyecto_activo" not in st.session_state:
    st.session_state.proyecto_activo = None
if "historial_chat" not in st.session_state:
    st.session_state.historial_chat = []

proyectos = cargar_proyectos()

with st.sidebar:
    st.markdown("### 🕸️ Graphos Platform")
    st.markdown("---")
    if proyectos:
        st.markdown("**Mis proyectos**")
        for key, p in proyectos.items():
            if st.button(f"🗂️ {p['nombre']}", key=f"nav_{key}", use_container_width=True):
                st.session_state.pagina = "chat"
                st.session_state.proyecto_activo = key
                st.session_state.historial_chat = []
                st.rerun()
    st.markdown("---")
    if st.button("➕ Nuevo proyecto", use_container_width=True):
        st.session_state.pagina = "nuevo"
        st.rerun()
    if st.button("🏠 Inicio", use_container_width=True):
        st.session_state.pagina = "inicio"
        st.rerun()

if st.session_state.pagina == "inicio":
    st.markdown('<div class="main-title">🕸️ Graphos Platform</div>', unsafe_allow_html=True)
    st.markdown('<div class="main-subtitle">Chatea con tus datos en lenguaje natural</div>', unsafe_allow_html=True)

    cols = st.columns(2)
    for i, (key, proyecto) in enumerate(proyectos.items()):
        with cols[i % 2]:
            st.markdown(f"""
            <div class='proyecto-card'>
                <div class='proyecto-titulo'>🗂️ {proyecto['nombre']}</div>
                <div class='proyecto-desc'>{proyecto.get('descripcion','')[:120]}</div>
            </div>
            """, unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            with c1:
                if st.button("💬 Chat", key=f"chat_{key}", use_container_width=True):
                    st.session_state.proyecto_activo = key
                    st.session_state.historial_chat = []
                    st.session_state.pagina = "chat"
                    st.rerun()
            with c2:
                if st.button("📊 Dashboard", key=f"dash_{key}", use_container_width=True):
                    st.session_state.proyecto_activo = key
                    st.session_state.pagina = "dashboard"
                    st.rerun()

elif st.session_state.pagina == "dashboard":
    proyecto = proyectos.get(st.session_state.proyecto_activo, {})
    st.markdown(f'<div class="main-title">📊 {proyecto.get("nombre","")}</div>', unsafe_allow_html=True)
    st.markdown('<div class="main-subtitle">Dashboard de analisis</div>', unsafe_allow_html=True)

    with st.spinner("Cargando datos del grafo..."):
        conteo, total_rel = obtener_metricas(proyecto)

    if conteo:
        total_nodos = sum(r['total'] for r in conteo)
        cols = st.columns(3)
        with cols[0]:
            st.markdown(f'<div class="metric-card"><div class="metric-value">{total_nodos:,}</div><div class="metric-label">Total nodos</div></div>', unsafe_allow_html=True)
        with cols[1]:
            st.markdown(f'<div class="metric-card"><div class="metric-value">{total_rel:,}</div><div class="metric-label">Total relaciones</div></div>', unsafe_allow_html=True)
        with cols[2]:
            st.markdown(f'<div class="metric-card"><div class="metric-value">{len(conteo)}</div><div class="metric-label">Tipos de nodos</div></div>', unsafe_allow_html=True)

        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### Distribucion de nodos")
            df = pd.DataFrame(conteo)
            fig = px.bar(df, x='total', y='tipo', orientation='h',
                color='total', color_continuous_scale='Purples',
                template='plotly_white')
            fig.update_layout(showlegend=False, coloraxis_showscale=False,
                margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            st.markdown("#### Proporcion por tipo")
            fig2 = px.pie(df, values='total', names='tipo',
                color_discrete_sequence=px.colors.sequential.Purples_r,
                template='plotly_white')
            fig2.update_layout(margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig2, use_container_width=True)

        st.markdown("---")
        st.markdown("#### Consulta Cypher directa")
        cypher_manual = st.text_area("Escribe una consulta:", height=80,
            placeholder="MATCH (n) RETURN labels(n)[0], count(n)")
        if st.button("Ejecutar"):
            try:
                resultado = ejecutar_cypher(
                    proyecto['neo4j_uri'],
                    proyecto['neo4j_user'],
                    proyecto['neo4j_password'],
                    cypher_manual
                )
                st.dataframe(pd.DataFrame(resultado))
            except Exception as e:
                st.error(f"Error: {e}")

    if st.button("← Volver"):
        st.session_state.pagina = "inicio"
        st.rerun()

elif st.session_state.pagina == "chat":
    proyecto = proyectos.get(st.session_state.proyecto_activo, {})
    col1, col2 = st.columns([4, 1])
    with col1:
        st.markdown(f'<div class="main-title">💬 {proyecto.get("nombre","")}</div>', unsafe_allow_html=True)
        st.markdown('<div class="main-subtitle">Escribe cualquier pregunta en español</div>', unsafe_allow_html=True)
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🗑️ Limpiar", use_container_width=True):
            st.session_state.historial_chat = []
            st.rerun()

    st.markdown("---")

    for mensaje in st.session_state.historial_chat:
        with st.chat_message(mensaje["rol"]):
            st.markdown(mensaje["contenido"])
            if mensaje["rol"] == "assistant" and "cypher" in mensaje:
                with st.expander("Ver Cypher generado"):
                    st.code(mensaje["cypher"], language="cypher")

    pregunta = st.chat_input("Escribe tu pregunta aqui...")
    if pregunta:
        st.session_state.historial_chat.append({"rol": "user", "contenido": pregunta})
        with st.chat_message("user"):
            st.markdown(pregunta)
        with st.chat_message("assistant"):
            with st.spinner("Consultando el grafo..."):
                respuesta, cypher = chat_con_grafo(pregunta, proyecto)
            st.markdown(respuesta)
            with st.expander("Ver Cypher generado"):
                st.code(cypher, language="cypher")
        st.session_state.historial_chat.append({
            "rol": "assistant", "contenido": respuesta, "cypher": cypher
        })
        st.rerun()

elif st.session_state.pagina == "nuevo":
    st.markdown('<div class="main-title">➕ Nuevo proyecto</div>', unsafe_allow_html=True)
    st.markdown("---")
    nombre = st.text_input("Nombre del proyecto", placeholder="Ej: Hospital Central")
    col1, col2 = st.columns(2)
    with col1:
        uri = st.text_input("URI de Neo4j", placeholder="neo4j+s://xxxxxxxx.databases.neo4j.io")
        user = st.text_input("Usuario")
    with col2:
        password = st.text_input("Contrasena", type="password")
        if uri and user and password:
            if st.button("Probar conexion"):
                ok, msg = probar_conexion(uri, user, password)
                if ok:
                    st.success("Conexion exitosa")
                else:
                    st.error(msg)
    schema = st.text_area("Esquema del grafo", height=200,
        placeholder="Nodos: ...\nRelaciones: ...")
    st.markdown("---")
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Cancelar", use_container_width=True):
            st.session_state.pagina = "inicio"
            st.rerun()
    with col_b:
        if st.button("Guardar proyecto", type="primary", use_container_width=True):
            if not nombre or not uri or not user or not password or not schema:
                st.error("Completa todos los campos")
            else:
                ok, msg = probar_conexion(uri, user, password)
                if not ok:
                    st.error(f"No se pudo conectar: {msg}")
                else:
                    key = nombre.lower().replace(" ", "_")
                    guardar_proyecto_nuevo(key, {
                        "nombre": nombre,
                        "descripcion": schema[:150],
                        "neo4j_uri": uri,
                        "neo4j_user": user,
                        "neo4j_password": password,
                        "schema_texto": schema,
                        "creado": datetime.now().isoformat()
                    })
                    st.success("Proyecto guardado")
                    st.session_state.pagina = "inicio"
                    st.rerun()
