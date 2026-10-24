import os
import shutil

def limpiar_carpeta(path_relativo):
    # Verificar si el directorio existe
    if not os.path.exists(path_relativo):
        raise FileNotFoundError(f"El directorio '{path_relativo}' no existe.")
    
    # Verificar si el path es un directorio
    if not os.path.isdir(path_relativo):
        raise NotADirectoryError(f"'{path_relativo}' no es un directorio.")
    
    # Eliminar todo el contenido dentro del directorio sin eliminar el directorio en sí
    for archivo in os.listdir(path_relativo):
        archivo_path = os.path.join(path_relativo, archivo)
        if os.path.isfile(archivo_path) or os.path.islink(archivo_path):
            os.unlink(archivo_path)  # Eliminar archivos y enlaces simbólicos
        elif os.path.isdir(archivo_path):
            shutil.rmtree(archivo_path)  # Eliminar carpetas y su contenido

    #print(f"El directorio '{path_relativo}' ha sido limpiado exitosamente.")

# Ejemplo de uso
try:
    for i in range(1,8):
        limpiar_carpeta(f"logs/container_{i}")
except FileNotFoundError as e:
    print(e)
except NotADirectoryError as e:
    print(e)
except Exception as e:
    print(f"Ha ocurrido un error: {e}")

print('Limpiado exitosamente los logs')