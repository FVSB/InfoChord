from infochord_protocol import codec as wire
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    Text,
    LargeBinary,
    Boolean,
    update,
    func,
    DateTime,
)
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from helper.docs import Document
from shared.logger import log_message
import datetime
import traceback
# Crear el motor de base de datos
from config import DB_PATH
engine = create_engine(DB_PATH)

# Refuse legacy object blobs before creating or changing any application tables.
with engine.begin() as connection:
    version = connection.exec_driver_sql("PRAGMA user_version").scalar()
    tables = connection.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    if version != 1 and tables:
        raise RuntimeError("Legacy/incompatible database. Use a NEW demo volume; old databases are never migrated automatically.")
    if version not in (0, 1):
        raise RuntimeError("Unsupported database format")
    connection.exec_driver_sql("PRAGMA user_version=1")

# Crear una sesión
Session = sessionmaker(bind=engine)
session = Session()


# Crear la base declarativa
Base = declarative_base()


# Definir el modelo de la tabla
class Docs(Base):
    __tablename__ = "docs"

    id = Column(Integer, primary_key=True)
    """
    Llave primaria
    """
    title = Column(Text)
    """
    Titulo 
    """
    extension=Column(Text)
    """
    Tipo de documento osea la extension 
    """
    document = Column(LargeBinary)
    """
    Documento
    """
    persistent = Column(Boolean, default=False)
    """
    Si es persistente o no
    """

    last_update = Column(DateTime, default=func.now(), onupdate=func.now())

    node_id = Column(Integer)

    text=Column(Text)#BOrrar despues
    
    
    
# Crear la tabla si no existe
Base.metadata.create_all(engine)


def insert_document(document: Document, node_id: int, persistent: bool = False) -> bool:
    """
        Dado un documento se trata de insertar, True si se inserto ,False si hubo algun error


    Args:
        document (Document): _description_
        persistent (bool, optional): _description_. Defaults to False.

    Returns:
        bool: _description_
    """
    try:
        session = Session()
        serialized_data = wire.dumps(document)
        to_save = Docs(
            id=document.id,
            title=document.title,
            node_id=node_id,
            document=serialized_data,
            persistent=persistent,
            text=document.text,
            extension=document.extension,
        )
        session.add(to_save)
        session.commit()
        session.close()
        return True
    except Exception as e:
        log_message(
            f"Ocurrio un error insertando el documento con id {document.id} y titulo {document.title} Error:{e} \n {traceback.format_exc()}",
            func=insert_document,
        )
        return False


def has_document(id_document: int) -> bool:
    """
    Devuelve True o False si el documento esta o no en la DB

    Args:
        id_document (int): _description_

    Returns:
        bool: _description_
    """
    try:
        session = Session()
        doc = session.query(Docs).filter_by(id=id_document).first()
        session.close()
        return doc is not None
    except Exception as e:
        log_message(
            f"Ocurrion un problema preguntando si existe el documento con id {id_document} {e}",
            func=has_document,
        )


def persist_document(id_document: int):
    """
    Dado el id de un documento lo hace persistente osea que ya se entrego el mensaje de check en la base de datos

    Args:
        id_document (int): _description_

    Returns:
        _type_: _description_
    """

    try:
        session = Session()
        doc = session.query(Docs).filter_by(id=id_document).first()
        if doc is None:  # Es que no existe el documento
            log_message(
                f"No se puede hacer persistente el documento con id {id_document} pq no esta en la base de datos",
                func=persist_document,
            )
            return False
        doc.persistent = True  # Se hizo persistente el documento
        session.commit()
        session.close()
        return True
    except Exception as e:
        log_message(
            f"Ocurrio una excepcion intentando hacer persistente el documento con id {id_document} \n {e}",
            func=persist_document,
        )
        return False


def make_false_persist_document(id_document: int):

    session = Session()
    doc = session.query(Docs).filter_by(id=id_document).first()
    if doc is None:
        log_message(
            f"El documento con id {id_document } no se puedo hacer no persistente pq no esta en la base de datos",
            func=make_false_persist_document,
        )
        return False
    doc.persistent = False
    session.commit()
    session.close()
    return False


def is_document_persistent(id_document: int) -> bool:
    """
    Retorna True o False si la columna persistente de un documento esta en True o False
    None si el documento no se encuentra en la base de datos
    Puede lanzar exeptions

    Args:
        id_document (int): _description_

    Returns:
        bool: _description_
    """

    session = Session()
    doc = session.query(Docs).filter_by(id=id_document).first()
    session.close()
    if doc is None:
        return None

    return doc.persistent


def make_false_persist_all_nodes_rows(node_id: int):
    """
    Dado el id de un nodo de chord todas las filas que lo tengan a el como dueño le van hacer el campo persist como False
    Retorna True si se pudo completar exitosamente la operacion
    False si ocurrio un error

    Args:
        node_id (int): _description_
    """
    try:
        session = Session()
        session.query(Docs).filter(Docs.node_id == node_id).update(
            {Docs.persistent: False}
        )
        session.commit()
        session.close()
        return True
    except Exception as e:
        log_message(
            f"Hubo un error tratando de hacer False la columna persistent de el nodo {node_id}"
        )
        return False
def make_false_persist_all_rows():
    """
    Hace la columna persistent en todas las filas Falso
    """
    session=Session()
    session.query(Docs).update({Docs.persistent: False})
    session.commit()
    session.close()

def get_document_by_id(id_document: int) -> Document:
    """
    Dado un id de documento trata de devolver el documento
    None si el documento no existe

    Args:
        id_document (int): _description_

    Returns:
        Document: Documento
        El documento si existe, None si no existe
    """
    session = Session()
    doc = session.query(Docs).filter_by(id=id_document).first()
    data = None
    if doc:
        
        data: Document = wire.loads(doc.document)  # Tomar el documento como objeto
    session.close()
    return data

def get_all_documents_by_extension(extensions:list[str],node_id:int)->list[Document]:
    """
    Dado una lista de extensiones puede ser vacia, y el id de un nodo
    devuelve todos los archivos con esas coincidencias

    Args:
        extensions (list[str]): _description_
        node_id (int): _description_

    Returns:
        list[Document]: _description_
    """
    session = Session()
    response:list[str]=[]
    docs:list[Docs]=None
    if len(extensions)==0:
        docs=session.query(Docs).filter(Docs.node_id == node_id).all()
    else: # Si hay extensiones
        docs=session.query(Docs).filter(Docs.extension.in_(extensions),Docs.node_id==node_id).all()
    if docs is None:
        return response
    for doc in docs:
        data:Document=wire.loads(doc.document)
        response.append(data)
    return response

def get_node_id_owner_by_doc_id(id_document: int) -> int:
    """
    Dado un id de documento devuelve quien es el dueño de ese documento
    int con el id si existe la fila,  None si no Existe

    Args:
        id_document (int): _description_

    Returns:
        int: _description_
    """
    session = Session()
    doc = session.query(Docs).filter_by(id=id_document).first()
    id_ = None
    if doc:
        id_ = doc.node_id
    session.close()
    return id_


def get_all_nodes_i_save() -> set[int]:
    """
    Retorna un set con todos ids de nodos que guarda
    Lo maximo que puede guardar es 3

    Returns:
        set[int]: _description_
    """
    session = Session()
    nodes = session.query(Docs.node_id).all()
    session.close()
    response = set()
    for node in nodes:
        response.add(node[0])  # Pq node es una tupla
    return response



def get_all_docs_keys()->list[int]:
    """
    Retorna todas las llaves que hay en la db

    Returns:
        list[int]: Todas las llaves que hay en la base de datos
    """
    session=Session()
    docs=session.query(Docs).all()
    session.close()
    return sorted([int(doc.id) for doc in docs],reverse=True)
    

def update_document(
    id_document: int,
    new_data: Document,
    node_id: int = -1,
    make_no_persist: bool = True,
):
    """
    Dado el id de un documento cambia el campo document por el que se le pasa
    si el node_id>-1 tb se actualiza el nodo del que es dueño

    Args:
        id_document (int): _description_
        new_data (Document): _description_
        node_id (int, optional): _description_. Defaults to -1.
        make_no_persist:bool Default True: True para decir que cuando haga el update cambie a que Se NO persit osea False ahi
    Returns:
        _type_: _description_
    """
    session = Session()
    doc = session.query(Docs).filter_by(id=id_document).first()
    response = False
    if doc:  
        doc.document = new_data.get_in_bytes()
        doc.text=new_data.text  
        if (
            node_id > -1
        ):  # Es que se quiere actualizar tb el nodo que es dueño ademas de la data
            doc.node_id = node_id
            if make_no_persist:  # Si quiero que lo haga no persisrente
                doc.persistent = False
        session.commit()

        response = True
    session.close()
    return response


def delete_document(document_id: int):
    """
    Se elimina el documento, pero no se elimina  la fila, solo se pone en None la columna documento

    Args:
        document_id (int): _description_
    """
    document=get_document_by_id(document_id)
    return update_document(document_id, document.delete())


def delete_document_all(document_id: int):
    """
    Se elimina toda la fila del documento en cuestion

    Args:
        document_id (int): _description_
    """
    session = Session()
    doc = session.query(Docs).filter_by(id=document_id).first()
    response = False
    if doc:
        session.delete(doc)
        session.commit()
        response = True
    session.close()
    return response
