import streamlit as st
from query import query
#from app.download_file import download_file_page
#from app.upload_file import upload_file_page
#from app.delete_file import delete_file_page
#from app.update_file import update_file_page

st.set_page_config(page_title="Motor de Búsqueda", page_icon="🔍")

st.title("🔍 Motor de Búsqueda Personalizado")

st.write("Selecciona una opción:")

options = {
    "Realizar Búsqueda": query,
    #"Descargar Archivo": download_file_page,
    #"Subir Archivo": upload_file_page,
    #"Eliminar Archivo": delete_file_page,
    #"Actualizar Archivo": update_file_page
}

selected_option = st.selectbox("", list(options.keys()))

options[selected_option]()