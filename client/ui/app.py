"""Local-only InfoChord demonstration interface."""

import streamlit as st
from api import insert_document, update_document, delete_document, make_query, download_file

st.set_page_config(page_title="InfoChord", page_icon="🔍")


def call_api(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except Exception as exc:
        st.error(str(exc))
        return None


pagina = st.sidebar.selectbox("Selecciona una página:", [
    "Inicio", "Motor de Búsqueda", "Solicitar Archivo", "Subir un archivo",
    "Actualizar un archivo", "Eliminar un archivo",
])

if pagina == "Inicio":
    st.title("InfoChord · búsqueda semántica distribuida")
    st.write("Prototipo local con nodos Chord, embeddings y almacenamiento SQLite.")
    st.info("Usa únicamente documentos de muestra. No es un servicio de producción.")
elif pagina in ("Subir un archivo", "Actualizar un archivo"):
    inserting = pagina == "Subir un archivo"
    st.title("Subir documento" if inserting else "Actualizar documento")
    uploaded = st.file_uploader("O selecciona un archivo de texto UTF-8", type=["txt", "md", "csv", "json", "log"])
    suggested_title, suggested_text = "", ""
    if uploaded is not None:
        if uploaded.size > 9 * 1024 * 1024:
            st.error("El archivo supera el límite de 9 MiB de la interfaz.")
            st.stop()
        try:
            suggested_title, suggested_text = uploaded.name, uploaded.getvalue().decode("utf-8")
        except UnicodeDecodeError:
            st.error("Selecciona un archivo de texto UTF-8.")
            st.stop()
    title = st.text_input("Nombre del documento (por ejemplo, ejemplo.txt)", value=suggested_title)
    text = st.text_area("Contenido del documento", value=suggested_text)
    if st.button("Subir documento" if inserting else "Actualizar documento"):
        if not title.strip() or not text.strip():
            st.warning("Introduce un nombre y contenido.")
        else:
            result = call_api(insert_document if inserting else update_document, title, text)
            if result is not None:
                st.success("Operación completada")
                st.write(str(result.get("message", "Operación completada")) if isinstance(result, dict) else str(result))
elif pagina == "Motor de Búsqueda":
    st.title("Búsqueda semántica")
    query = st.text_input("Introduce tu consulta:")
    extensions = st.text_input("Extensiones separadas por comas (opcional):")
    if st.button("Realizar Búsqueda"):
        if not query.strip():
            st.warning("Introduce una consulta.")
        else:
            results = call_api(make_query, query, extensions.replace(",", " ").split())
            if results is not None:
                st.session_state["results"] = results
    # Persist results across rerenders so retrieval buttons remain functional.
    for doc in st.session_state.get("results", []):
        with st.expander(f"{doc['title']} · {doc['score']:.3f}"):
            st.write(doc["snipet"])
            if st.button("Mostrar documento", key=f"document-{doc['id']}"):
                text = call_api(download_file, doc["title"])
                if text is not None:
                    st.write(text)
elif pagina == "Solicitar Archivo":
    st.title("Solicitar documento")
    title = st.text_input("Nombre del documento:")
    if st.button("Enviar Solicitud"):
        if not title.strip():
            st.warning("Introduce el nombre del documento.")
        else:
            text = call_api(download_file, title)
            if text is not None:
                st.write(text)
                st.download_button("Descargar texto", text, file_name=title)
elif pagina == "Eliminar un archivo":
    st.title("Eliminar documento")
    title = st.text_input("Nombre del documento que deseas eliminar:")
    confirmed = st.checkbox("Confirmo que quiero eliminar este documento")
    if st.button("Eliminar documento"):
        if not title.strip() or not confirmed:
            st.warning("Introduce el nombre y confirma la eliminación.")
        else:
            result = call_api(delete_document, title.strip())
            if result is not None:
                st.write(str(result.get("message", "Operación completada")) if isinstance(result, dict) else str(result))
