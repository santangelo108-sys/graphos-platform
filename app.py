import streamlit as st
import json
import os
import pandas as pd
import anthropic
from neo4j import GraphDatabase

# ── CONFIGURACION ─────────────────────────────────────
st.set_page_config(
    page_title="Graphos Platform",
    page_icon="🕸️",
    layout="wide"
)

ANTHROPIC_API_KEY = st.secrets.get("ANTHROPIC_API_KEY", "")
PROJECTS_FILE = "projects.json"

# ── FUNCIONES DE PROYECTOS ────────────────────────────
def cargar_proyectos():
    if os.path.exists(PROJECTS_FILE):
        with open(PROJECTS_FILE, "r") as f:
            return json.load(f)
    return {}

def guardar_proyectos(proyectos):
    with open(PROJECTS_FILE, "w") as f:
        json.dump(proyectos, f, indent=2)

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

def detectar_esquema_con_claude(df_info, nombre_proyecto):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    prompt = f"""Analiza estas columnas de un archivo CSV para el proyecto '{nombre_proyecto}':

{df_info}

Responde UNICAMENTE en JSON con esta estructura exacta:
{{
  "descripcion": "descripcion breve del dataset en una linea",
  "nodo_principal": "NombreDelNodoPrincipal",
  "propiedades": ["col1", "col2", "col3"],
  "schema_texto": "descripcion del esquema para usar en consultas"
}}"""

    respuesta = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}]
    )
    texto = respuesta.content[0].text.strip()
    texto = texto.replace("```json", "").replace("```", "").strip()
    return json.loads(texto)

def chat_con_grafo(pregunta, proyecto, historial):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    sistema = f"""Eres un asistente experto del proyecto '{proyecto['nombre']}'.
{proyecto['schema_texto']}

Tu tarea:
1. Convertir la pregunta del usuario a Cypher para Neo4j
2. Devolver UNICAMENTE el Cypher, sin explicaciones ni bloques de codigo"""

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
        max_tokens=400,
        system=f"Eres un asistente del proyecto '{proyecto['nombre']}'. Interpreta los datos y responde en español claro y util. Maximo 6 lineas. Si no hay datos, dilo claramente.",
        messages=[{"role": "user", "content": f"Pregunta: {pregunta}\nDatos: {datos}"}]
    )
    return r2.content[0].text, cypher

# ── ESTILOS ───────────────────────────────────────────
st.markdown("""
<style>
.proyecto-card {
    background: #1a1d27;
    border: 1px solid #2d3748;
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 16px;
}
.proyecto-titulo {
    font-size: 18px;
    font-weight: bold;
    color: #a78bfa;
}
.proyecto-desc {
    font-size: 14px;
    color: #9ca3af;
    margin-top: 4px;
}
</style>
""", unsafe_allow_html=True)

# ── NAVEGACION ────────────────────────────────────────
if "pagina" not in st.session_state:
    st.session_state.pagina = "inicio"
if "proyecto_activo" not in st.session_state:
    st.session_state.proyecto_activo = None
if "historial_chat" not in st.session_state:
    st.session_state.historial_chat = []

proyectos = cargar_proyectos()

# ════════════════════════════════════════════════════
# PAGINA: INICIO
# ════════════════════════════════════════════════════
if st.session_state.pagina == "inicio":
    st.title("🕸️ Graphos Platform")
    st.caption("Chatea con tus datos en lenguaje natural")
    st.divider()

    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader("Mis proyectos")
    with col2:
        if st.button("➕ Nuevo proyecto", type="primary", use_container_width=True):
            st.session_state.pagina = "nuevo"
            st.rerun()

    if not proyectos:
        st.info("No tienes proyectos aun. Crea tu primer proyecto con el boton de arriba.")
    else:
        for key, proyecto in proyectos.items():
            with st.container():
                st.markdown(f"""
                <div class='proyecto-card'>
                    <div class='proyecto-titulo'>🗂️ {proyecto['nombre']}</div>
                    <div class='proyecto-desc'>{proyecto.get('descripcion', '')}</div>
                </div>
                """, unsafe_allow_html=True)
                col_a, col_b = st.columns([4, 1])
                with col_b:
                    if st.button("💬 Abrir chat", key=f"chat_{key}", use_container_width=True):
                        st.session_state.proyecto_activo = key
                        st.session_state.historial_chat = []
                        st.session_state.pagina = "chat"
                        st.rerun()

    st.divider()
    st.markdown("**Proyecto demo incluido:** Agrega Escuela Graphos desde 'Nuevo proyecto' usando tus credenciales de Neo4j.")

# ════════════════════════════════════════════════════
# PAGINA: NUEVO PROYECTO
# ════════════════════════════════════════════════════
elif st.session_state.pagina == "nuevo":
    st.title("➕ Nuevo proyecto")
    if st.button("← Volver"):
        st.session_state.pagina = "inicio"
        st.rerun()
    st.divider()

    nombre = st.text_input("Nombre del proyecto", placeholder="Ej: Escuela Graphos")
    
    st.subheader("Conexion Neo4j")
    uri = st.text_input("URI de Neo4j", placeholder="neo4j+s://xxxxxxxx.databases.neo4j.io")
    user = st.text_input("Usuario")
    password = st.text_input("Contrasena", type="password")

    st.subheader("Esquema del grafo")
    st.caption("Describe brevemente que datos tiene este grafo para que el chat funcione bien.")
    schema_manual = st.text_area(
        "Descripcion del esquema",
        placeholder="""Ejemplo:
Nodos: Estudiante(nombre, grado), Calificacion(nota, periodo)
Relaciones: (Estudiante)-[:OBTUVO]->(Calificacion)
Valores: grados: 5to a 3BGU, nota minima aprobatoria: 7.0""",
        height=200
    )

    archivo = st.file_uploader(
        "O sube un CSV/Excel para detectar el esquema automaticamente (opcional)",
        type=["csv", "xlsx"]
    )

    if archivo:
        if archivo.name.endswith(".csv"):
            df = pd.read_csv(archivo)
        else:
            df = pd.read_excel(archivo)
        st.dataframe(df.head(5))
        
        if st.button("🤖 Detectar esquema con Claude"):
            with st.spinner("Claude esta analizando tu archivo..."):
                info = f"Columnas: {list(df.columns)}\nEjemplo de datos:\n{df.head(3).to_string()}"
                try:
                    resultado = detectar_esquema_con_claude(info, nombre or "Nuevo proyecto")
                    st.session_state.esquema_detectado = resultado
                    st.success(f"Esquema detectado: {resultado['descripcion']}")
                    st.code(resultado['schema_texto'])
                except Exception as e:
                    st.error(f"Error al detectar esquema: {e}")

    st.divider()
    if st.button("✅ Guardar proyecto", type="primary"):
        if not nombre:
            st.error("Escribe un nombre para el proyecto")
        elif not uri or not user or not password:
            st.error("Completa las credenciales de Neo4j")
        else:
            ok, msg = probar_conexion(uri, user, password)
            if not ok:
                st.error(f"No se pudo conectar a Neo4j: {msg}")
            else:
                esquema = schema_manual
                if hasattr(st.session_state, 'esquema_detectado'):
                    esquema = st.session_state.esquema_detectado.get('schema_texto', schema_manual)
                
                key = nombre.lower().replace(" ", "_")
                proyectos[key] = {
                    "nombre": nombre,
                    "descripcion": esquema[:100] + "..." if len(esquema) > 100 else esquema,
                    "neo4j_uri": uri,
                    "neo4j_user": user,
                    "neo4j_password": password,
                    "schema_texto": esquema
                }
                guardar_proyectos(proyectos)
                st.success("Proyecto guardado correctamente")
                st.session_state.pagina = "inicio"
                st.rerun()

# ════════════════════════════════════════════════════
# PAGINA: CHAT
# ════════════════════════════════════════════════════
elif st.session_state.pagina == "chat":
    proyecto = proyectos.get(st.session_state.proyecto_activo, {})

    col1, col2 = st.columns([4, 1])
    with col1:
        st.title(f"💬 {proyecto.get('nombre', 'Proyecto')}")
    with col2:
        if st.button("← Volver", use_container_width=True):
            st.session_state.pagina = "inicio"
            st.rerun()

    st.caption("Escribe cualquier pregunta en español sobre tus datos")
    st.divider()

    for mensaje in st.session_state.historial_chat:
        with st.chat_message(mensaje["rol"]):
            st.write(mensaje["contenido"])
            if mensaje["rol"] == "assistant" and "cypher" in mensaje:
                with st.expander("Ver consulta Cypher generada"):
                    st.code(mensaje["cypher"], language="cypher")

    pregunta = st.chat_input("Escribe tu pregunta aqui...")

    if pregunta:
        st.session_state.historial_chat.append({
            "rol": "user",
            "contenido": pregunta
        })
        with st.chat_message("user"):
            st.write(pregunta)

        with st.chat_message("assistant"):
            with st.spinner("Consultando el grafo..."):
                respuesta, cypher = chat_con_grafo(
                    pregunta, proyecto,
                    st.session_state.historial_chat
                )
            st.write(respuesta)
            with st.expander("Ver consulta Cypher generada"):
                st.code(cypher, language="cypher")

        st.session_state.historial_chat.append({
            "rol": "assistant",
            "contenido": respuesta,
            "cypher": cypher
        })
