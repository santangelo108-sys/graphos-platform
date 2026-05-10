import streamlit as st
import json
import os
import pandas as pd
import anthropic
import plotly.graph_objects as go
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
PROJECTS_FILE = "projects.json"
HISTORY_FILE = "history.json"

st.markdown("""
<style>
[data-testid="stAppViewContainer"] { background: #0f1117; }
[data-testid="stSidebar"] { background: #1a1d27; border-right: 1px solid #2d3748; }
[data-testid="stSidebar"] * { color: #e2e8f0 !important; }
.main-title { font-size: 28px; font-weight: 800; color: #a78bfa; margin-bottom: 4px; }
.main-subtitle { font-size: 14px; color: #6b7280; margin-bottom: 24px; }
.proyecto-card {
    background: #1a1d27;
    border: 1px solid #2d3748;
    border-radius: 12px;
    padding: 20px 24px;
    margin-bottom: 12px;
    transition: border-color 0.2s;
}
.proyecto-card:hover { border-color: #7c3aed; }
.proyecto-titulo { font-size: 17px; font-weight: 700; color: #a78bfa; }
.proyecto-desc { font-size: 13px; color: #9ca3af; margin-top: 6px; line-height: 1.5; }
.metric-card {
    background: #1a1d27;
    border: 1px solid #2d3748;
    border-radius: 10px;
    padding: 16px;
    text-align: center;
}
.metric-value { font-size: 32px; font-weight: 800; color: #a78bfa; }
.metric-label { font-size: 12px; color: #6b7280; margin-top: 4px; }
.stTextInput input, .stTextArea textarea {
    background: #1a1d27 !important;
    color: #e2e8f0 !important;
    border: 1px solid #2d3748 !important;
}
div[data-testid="stChatMessage"] {
    background: #1a1d27;
    border-radius: 12px;
    margin-bottom: 8px;
    padding: 4px;
}
</style>
""", unsafe_allow_html=True)

def cargar_proyectos():
    if os.path.exists(PROJECTS_FILE):
        with open(PROJECTS_FILE, "r") as f:
            return json.load(f)
    return {}

def guardar_proyectos(proyectos):
    with open(PROJECTS_FILE, "w") as f:
        json.dump(proyectos, f, indent=2)

def cargar_historial():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    return {}

def guardar_historial(historial):
    with open(HISTORY_FILE, "w") as f:
        json.dump(historial, f, indent=2)

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
Maximo 8 lineas. Si no hay datos, dilo claramente.""",
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

# ── SIDEBAR ──────────────────────────────────────────
proyectos = cargar_proyectos()
historial_global = cargar_historial()

with st.sidebar:
    st.markdown("### 🕸️ Graphos Platform")
    st.markdown("---")

    if proyectos:
        st.markdown("**Mis proyectos**")
        for key, p in proyectos.items():
            if st.button(f"🗂️ {p['nombre']}", key=f"nav_{key}", use_container_width=True):
                st.session_state.pagina = "chat"
                st.session_state.proyecto_activo = key
                if "historial_chat" not in st.session_state:
                    st.session_state.historial_chat = []
                st.rerun()

    st.markdown("---")
    if st.button("➕ Nuevo proyecto", use_container_width=True):
        st.session_state.pagina = "nuevo"
        st.rerun()
    if st.button("🏠 Inicio", use_container_width=True):
        st.session_state.pagina = "inicio"
        st.rerun()

# ── ESTADO INICIAL ────────────────────────────────────
if "pagina" not in st.session_state:
    st.session_state.pagina = "inicio"
if "proyecto_activo" not in st.session_state:
    st.session_state.proyecto_activo = None
if "historial_chat" not in st.session_state:
    st.session_state.historial_chat = []

# ════════════════════════════════════════════════════
# PAGINA: INICIO
# ════════════════════════════════════════════════════
if st.session_state.pagina == "inicio":
    st.markdown('<div class="main-title">🕸️ Graphos Platform</div>', unsafe_allow_html=True)
    st.markdown('<div class="main-subtitle">Chatea con tus datos en lenguaje natural</div>', unsafe_allow_html=True)

    if not proyectos:
        st.info("No tienes proyectos aun. Crea tu primer proyecto desde el menu lateral.")
    else:
        cols = st.columns(2)
        for i, (key, proyecto) in enumerate(proyectos.items()):
            with cols[i % 2]:
                msgs = len(historial_global.get(key, []))
                st.markdown(f"""
                <div class='proyecto-card'>
                    <div class='proyecto-titulo'>🗂️ {proyecto['nombre']}</div>
                    <div class='proyecto-desc'>{proyecto.get('descripcion','')[:120]}...</div>
                    <div style='margin-top:10px;font-size:12px;color:#6b7280'>
                        💬 {msgs} mensajes en historial
                    </div>
                </div>
                """, unsafe_allow_html=True)
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("💬 Chat", key=f"chat_{key}", use_container_width=True):
                        st.session_state.proyecto_activo = key
                        st.session_state.historial_chat = historial_global.get(key, [])
                        st.session_state.pagina = "chat"
                        st.rerun()
                with c2:
                    if st.button("📊 Dashboard", key=f"dash_{key}", use_container_width=True):
                        st.session_state.proyecto_activo = key
                        st.session_state.pagina = "dashboard"
                        st.rerun()

# ════════════════════════════════════════════════════
# PAGINA: DASHBOARD
# ════════════════════════════════════════════════════
elif st.session_state.pagina == "dashboard":
    proyecto = proyectos.get(st.session_state.proyecto_activo, {})
    st.markdown(f'<div class="main-title">📊 {proyecto.get("nombre","")}</div>', unsafe_allow_html=True)
    st.markdown('<div class="main-subtitle">Dashboard de analisis</div>', unsafe_allow_html=True)

    with st.spinner("Cargando datos del grafo..."):
        conteo, total_rel = obtener_metricas(proyecto)

    if conteo:
        total_nodos = sum(r['total'] for r in conteo)
        cols = st.columns(4)
        with cols[0]:
            st.markdown(f'<div class="metric-card"><div class="metric-value">{total_nodos:,}</div><div class="metric-label">Total nodos</div></div>', unsafe_allow_html=True)
        with cols[1]:
            st.markdown(f'<div class="metric-card"><div class="metric-value">{total_rel:,}</div><div class="metric-label">Total relaciones</div></div>', unsafe_allow_html=True)
        with cols[2]:
            st.markdown(f'<div class="metric-card"><div class="metric-value">{len(conteo)}</div><div class="metric-label">Tipos de nodos</div></div>', unsafe_allow_html=True)
        with cols[3]:
            msgs = len(historial_global.get(st.session_state.proyecto_activo, []))
            st.markdown(f'<div class="metric-card"><div class="metric-value">{msgs}</div><div class="metric-label">Consultas realizadas</div></div>', unsafe_allow_html=True)

        st.markdown("---")
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### Distribucion de nodos")
            df = pd.DataFrame(conteo)
            fig = px.bar(df, x='total', y='tipo', orientation='h',
                color='total', color_continuous_scale='Purples',
                template='plotly_dark')
            fig.update_layout(
                plot_bgcolor='#1a1d27', paper_bgcolor='#1a1d27',
                showlegend=False, coloraxis_showscale=False,
                margin=dict(l=10, r=10, t=10, b=10)
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.markdown("#### Proporcion por tipo")
            fig2 = px.pie(df, values='total', names='tipo',
                color_discrete_sequence=px.colors.sequential.Purples_r,
                template='plotly_dark')
            fig2.update_layout(
                plot_bgcolor='#1a1d27', paper_bgcolor='#1a1d27',
                margin=dict(l=10, r=10, t=10, b=10)
            )
            st.plotly_chart(fig2, use_container_width=True)

        st.markdown("---")
        st.markdown("#### Consulta personalizada al grafo")
        cypher_manual = st.text_area("Escribe una consulta Cypher directamente:", height=80,
            placeholder="MATCH (n) RETURN labels(n)[0], count(n)")
        if st.button("Ejecutar consulta"):
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

    if st.button("← Volver al inicio"):
        st.session_state.pagina = "inicio"
        st.rerun()

# ════════════════════════════════════════════════════
# PAGINA: CHAT
# ════════════════════════════════════════════════════
elif st.session_state.pagina == "chat":
    proyecto = proyectos.get(st.session_state.proyecto_activo, {})

    col1, col2 = st.columns([4, 1])
    with col1:
        st.markdown(f'<div class="main-title">💬 {proyecto.get("nombre","")}</div>', unsafe_allow_html=True)
        st.markdown('<div class="main-subtitle">Escribe cualquier pregunta en español</div>', unsafe_allow_html=True)
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🗑️ Limpiar chat", use_container_width=True):
            st.session_state.historial_chat = []
            historial_global[st.session_state.proyecto_activo] = []
            guardar_historial(historial_global)
            st.rerun()

    st.markdown("---")

    for mensaje in st.session_state.historial_chat:
        with st.chat_message(mensaje["rol"]):
            st.markdown(mensaje["contenido"])
            if mensaje["rol"] == "assistant" and "cypher" in mensaje:
                with st.expander("Ver consulta Cypher generada"):
                    st.code(mensaje["cypher"], language="cypher")

    pregunta = st.chat_input("Escribe tu pregunta aqui...")

    if pregunta:
        st.session_state.historial_chat.append({
            "rol": "user",
            "contenido": pregunta,
            "timestamp": datetime.now().isoformat()
        })
        with st.chat_message("user"):
            st.markdown(pregunta)

        with st.chat_message("assistant"):
            with st.spinner("Consultando el grafo..."):
                respuesta, cypher = chat_con_grafo(pregunta, proyecto)
            st.markdown(respuesta)
            with st.expander("Ver consulta Cypher generada"):
                st.code(cypher, language="cypher")

        st.session_state.historial_chat.append({
            "rol": "assistant",
            "contenido": respuesta,
            "cypher": cypher,
            "timestamp": datetime.now().isoformat()
        })

        historial_global[st.session_state.proyecto_activo] = st.session_state.historial_chat
        guardar_historial(historial_global)
        st.rerun()

# ════════════════════════════════════════════════════
# PAGINA: NUEVO PROYECTO
# ════════════════════════════════════════════════════
elif st.session_state.pagina == "nuevo":
    st.markdown('<div class="main-title">➕ Nuevo proyecto</div>', unsafe_allow_html=True)
    st.markdown("---")

    nombre = st.text_input("Nombre del proyecto", placeholder="Ej: Escuela Graphos")
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

    st.markdown("#### Esquema del grafo")
    st.caption("Describe los nodos, relaciones y valores importantes para que el chat funcione bien.")
    schema = st.text_area("Descripcion del esquema", height=200,
        placeholder="Nodos: Estudiante(nombre, grado)\nRelaciones: (Estudiante)-[:OBTUVO]->(Calificacion)")

    st.markdown("---")
    col_a, col_b = st.columns([1, 1])
    with col_a:
        if st.button("Cancelar", use_container_width=True):
            st.session_state.pagina = "inicio"
            st.rerun()
    with col_b:
        if st.button("Guardar proyecto", type="primary", use_container_width=True):
            if not nombre:
                st.error("Escribe un nombre")
            elif not uri or not user or not password:
                st.error("Completa las credenciales de Neo4j")
            elif not schema:
                st.error("Describe el esquema del grafo")
            else:
                ok, msg = probar_conexion(uri, user, password)
                if not ok:
                    st.error(f"No se pudo conectar: {msg}")
                else:
                    key = nombre.lower().replace(" ", "_")
                    proyectos[key] = {
                        "nombre": nombre,
                        "descripcion": schema[:150],
                        "neo4j_uri": uri,
                        "neo4j_user": user,
                        "neo4j_password": password,
                        "schema_texto": schema,
                        "creado": datetime.now().isoformat()
                    }
                    guardar_proyectos(proyectos)
                    st.success("Proyecto guardado")
                    st.session_state.pagina = "inicio"
                    st.rerun()
