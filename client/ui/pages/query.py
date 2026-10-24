import streamlit as st
from api import *
from shared.logger import log_message
# Simulación de documentos con score
log_message(f"Iniciado")


# Función para realizar la búsqueda
def realizar_busqueda(query, extensiones):
    documentos = make_query(query=query,posibles_extensions=extensiones)
    return documentos
def query():
    # Configuración de la página
    st.set_page_config(page_title="Motor de Búsqueda", page_icon="🔍")

    st.title("🔍 Motor de Búsqueda Personalizado")

    # Entrada de la consulta
    query = st.text_input("Introduce tu consulta:")

    # Entrada de extensiones
    extensiones:str = st.text_input("Introduce extensiones posibles separadas por comas:")

    extensiones=extensiones.replace(',',' ')

    extensiones=extensiones.split(' ')

    temp=[]

    for ext in extensiones:
        if ext not in ['', ' ']:
            temp.append(ext)

    extensiones=temp
    # Botón para realizar la búsqueda
    if st.button("Realizar Búsqueda"):
        if query:
            resultados:list = realizar_busqueda(query, extensiones)

            if resultados and len(resultados) > 0:
                for doc in resultados:
                    title = doc['title']
                    snippet = doc["snipet"]
                    id_ = doc["id"]
                    score = doc["score"]

                    with st.expander(f"{title} (Score: {score})"):
                        st.write(snippet)

                        # Crear una clave única para cada botón
                        button_key = f"button_{id_}"
                        if st.button(f"Mostrar contenido completo de {title}", key=button_key):
                            st.session_state[button_key] = True

                        # Mostrar el contenido completo si se presionó el botón
                        if st.session_state.get(button_key):
                            st.write(f"Buscando el documento completo de {title}")
                            text = download_file(title, True)
                            st.write(text)
            else:
                st.info("No se encontraron documentos que coincidan con la consulta.")
        else:
            st.warning("Por favor, introduce una consulta.")
