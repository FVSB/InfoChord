import streamlit as st
from api import *
from shared.logger import log_message

# Simulación de documentos con score
log_message(f"Iniciado")

# Función para realizar la búsqueda
def realizar_busqueda(query, extensiones):
    documentos = make_query(query=query, posibles_extensions=extensiones)
    return documentos
  
def subir_o_actualizar_archivo(subir:bool):
    name="Subir" if subir else "Actualizar"
    st.title(f"📤 {name} un Archivo") 

    # Especificar el nombre del archivo a buscar
    nombre_archivo = st.text_input("Introduce el nombre del archivo que deseas buscar en 'app/database':")
    
    # Ruta de la carpeta donde se buscará el archivo
    ruta_archivo = os.path.join("app", "database", nombre_archivo)

    # Botón para buscar y subir el archivo
    if st.button(f"Buscar y {name} Archivo"):
        if os.path.isfile(ruta_archivo):
            # Si el archivo existe, permitir subirlo
            with open(ruta_archivo, "rb") as file:
                st.download_button(label="Descargar Archivo", data=file, file_name=nombre_archivo)
                st.success(f"El archivo '{nombre_archivo}' ha sido encontrado y está listo para descargar.")
                contenido_archivo = file.read()  # Leer el contenido del archivo como str
                contenido_str = contenido_archivo.decode("utf-8") 
                st.text_area("Contenido del Archivo:", contenido_str, height=300)  # Mostrar contenido en un área de texto
                response=""
                if subir:
                    response=insert_document(title=nombre_archivo,text=contenido_str)
                else:
                    response=update_document(title=nombre_archivo,text=contenido_str)
                st.success(f"El archivo '{nombre_archivo} {response}' .")
        else:
            st.error(f"El archivo '{nombre_archivo}' no existe en la carpeta 'app/database'.")
    
    # Opción para escribir un nuevo archivo
    st.write("O también puedes escribir el contenido de un nuevo archivo:")
    contenido_nuevo = st.text_area("Escribe el contenido del nuevo archivo:")
    
    # Botón para subir el nuevo archivo
    if st.button(f"{name} Nuevo Archivo"):
        #if contenido_nuevo:
        #    # Guardar el nuevo archivo en la carpeta especificada
        #    with open(ruta_archivo, "w") as new_file:
        #        new_file.write(contenido_nuevo)
        #    st.success(f"El nuevo archivo '{nombre_archivo}' ha sido creado y subido a 'app/database'.")
        response=""
        if contenido_nuevo:
            if subir:
                    response=insert_document(title=nombre_archivo,text=contenido_nuevo)
            else:
                    response=update_document(title=nombre_archivo,text=contenido_nuevo) 
           
            st.success(f"El nuevo archivo '{nombre_archivo}' {response}'.")
        else:
            st.warning("Por favor, escribe algo en el contenido del nuevo archivo.")
    
# Configuración de la página
st.set_page_config(page_title="Motor de Búsqueda", page_icon="🔍")

# Menú de selección de páginas
pagina = st.sidebar.selectbox("Selecciona una página:", ["Inicio", "Motor de Búsqueda", "Solicitar Archivo","Subir un archivo","Actualizar un archivo","Eliminar un archivo"])

# Página de Inicio
if pagina == "Inicio":
    st.title("Bienvenido al Motor de Búsqueda")
    st.write("Esta aplicación te permite buscar documentos y solicitar archivos.")
    st.write("Utiliza el menú en la barra lateral para navegar a las diferentes secciones.")

# Página de Motor de Búsqueda
elif pagina == "Motor de Búsqueda":
    st.title("🔍 Motor de Búsqueda Personalizado")

    # Entrada de la consulta
    query = st.text_input("Introduce tu consulta:")

    # Entrada de extensiones
    extensiones = st.text_input("Introduce extensiones posibles separadas por comas:")
    extensiones = extensiones.replace(',', ' ').split()
    extensiones = [ext for ext in extensiones if ext]

    # Botón para realizar la búsqueda
    if st.button("Realizar Búsqueda"):
        if query:
            resultados = realizar_busqueda(query, extensiones)
            
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

# Página para solicitar archivos
elif pagina == "Solicitar Archivo":
    st.title("📁 Solicitar Archivo")

    # Entrada del nombre del archivo
    file_name = st.text_input("Introduce el nombre del archivo:")

    # Botón para enviar la solicitud
    if st.button("Enviar Solicitud"):
        if file_name:
            # Lógica para enviar la solicitud
            st.success(f"Solicitud enviada para el archivo '{file_name}'.")
            text=download_file(file_name,False)
            st.write(f"El texto es \n {text}")
        else:
            st.warning("Por favor, completa todos los campos.")
# Página para subir un archivo
elif pagina == "Subir un archivo":
   subir_o_actualizar_archivo(True)
elif pagina== "Actualizar un archivo":
    subir_o_actualizar_archivo(False)
elif  pagina== "Eliminar un archivo":
    st.title("🗑️ Eliminar un Archivo")

    # Entrada del nombre del archivo
    nombre_archivo = st.text_input("Introduce el nombre del archivo que deseas eliminar en 'app/database':")
    
    confirmar = st.checkbox("Confirmo que quiero eliminar este documento")
    if st.button("Eliminar documento", type="primary"):
        if not nombre_archivo.strip():
            st.warning("Introduce el nombre del archivo que deseas eliminar.")
        elif not confirmar:
            st.warning("Confirma la eliminación antes de continuar.")
        else:
            response = delete_document(nombre_archivo.strip())
            st.write(f"Respuesta \n {response}")
