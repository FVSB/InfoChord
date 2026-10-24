from infochord_protocol import codec as wire
from datetime import datetime
import tiktoken
import numpy as np
from .utils import getShaRepr


class DocsRecords:
    
    def __init__(self, doc_id: int):
        self.doc_id = doc_id
        self.is_delete: bool = False
        self.last_change: datetime = datetime.utcnow()  # Muestra la hora utc

    def update(self):
        """
        Cuando se llama el cambio actual se registra como ahora
        
        """
        self.last_change=datetime.utcnow()  # Muestra la hora utc
        
    
    def can_update(self, new_doc: "DocsRecords") -> bool:
        """
        Dado el documento nuevo a update se ve si es mas nuevo que el de esta instancia
        

        Args:
            other (DocsRecords): _description_

        Returns:
            bool: True si el other es mas nuevo False si esta instancia es mas nueva
        """
        if not isinstance(new_doc, DocsRecords):
            raise Exception(f'Other debe ser de tipo  DocsRecords no:{type(new_doc)} {new_doc} ')
        
        if self.doc_id != new_doc.doc_id:
            return False
        can_update=self.last_change < new_doc.last_change
        return (
            can_update
        )  # Si el ultimo cambio es mas reciente se queda el ultimo cambio
    def __str__(self)->str:
        return f'Historial: {self.last_change}'
    def __repr__(self) -> str:
        return str(self)
    
def obtener_substring_despues_ultimo_punto(cadena:str):
    """
    Dado un string devuelve el substring despues del ultimo punto
    Si no existe punto en en el string devuelve el string vacio

    Args:
        cadena (str): _description_

    Returns:
        str: _description_
    """
    posicion_ultimo_punto = cadena.rfind('.')
    if posicion_ultimo_punto == -1:
        return ""  # No hay punto en la cadena
    return cadena[posicion_ultimo_punto + 1:]


def dividir_texto(texto, modelo='gpt-3.5-turbo', max_tokens=512):
    # Cargar el codificador para el modelo especificado
    enc = tiktoken.encoding_for_model(modelo)
    
    # Codificar el texto en tokens
    tokens = enc.encode(texto)
    
    # Dividir los tokens en trozos de tamaño máximo
    trozos = [tokens[i:i + max_tokens] for i in range(0, len(tokens), max_tokens)]
    
    # Decodificar los trozos de tokens de vuelta a texto
    trozos_texto = [enc.decode(trozo) for trozo in trozos]
    
    return trozos_texto, len(tokens)

# Ejemplo de uso


class Document:
    def _get_extention(self,title)->str:
        """
        Dado el titulo retorna la extension

        Args:
            title (_type_): _description_

        Returns:
            str: _description_
        """
        ext=obtener_substring_despues_ultimo_punto(title)
        
        return ext if ext!="" else 'PlainText'
    
    
    def __init__(self, title: str, text: str, max_value=16):
        self.id = getShaRepr(title)#, max_value)
        self.title: str = title
        self.extension:str=self._get_extention(title)
        self.text: str = text
        self.record: DocsRecords = DocsRecords(self.id)
    def get_in_bytes(self) -> bytes:
        return wire.dumps(self)

    def delete(self):
        """
        Hace como que el documento fue eliminado
        """
        self.text=None
        self.record.is_delete=True
        self.record.update()
    def update(self,other:'Document')->bool:
        """
        Dado otro documento toma la decision si modificarlo
        o no 

        Args:
            other (Document): Nuevo documento a upgradear

        Returns:
            bool:True  si se actualizo con la info del other
                 False Si se quedo en este mismo documento
        """
        if self.id!=other.id:
            return False
        if not self.record.can_update(other.record):
            return False
        
        self.text=other.text
        self.record.update()
        return True
def get_document_from_bytes(data:bytes)->Document:
    """
    Dado unos bytes devuelve el objeto documento
    

    Args:
        data (bytes): bytes que serializan un documento

    Raises:
        Exception: Si al deserializar no es de tipo Document

    Returns:
        Document: _description_
    """
    doc= wire.loads(data)
    if not isinstance(doc, Document):
        raise Exception(f'los bytes deben contener un document pero contienen un {type(doc) } {doc}')
    return doc


class EmbeddingDocument(Document):
    def __init__(self, title: str, text: str,embedding_text_list:list[np.array],embedding_title_list:list[np.array],text_chunks:list[str], max_value=16):
        super().__init__(title, text, max_value)
        self.embedding_title_list:list[np.array]=embedding_title_list
        self.embedding_list:list[np.array]=embedding_text_list
        self.text_chunks:list[str]=text_chunks
        
    def delete(self):
        self.embedding_list=None
        self.embedding_title_list=None
        super().delete()
        
    def update(self, other: "EmbeddingDocument") -> bool:
        if not isinstance(other,EmbeddingDocument):
            raise Exception(f"Pther debe ser de tipo Embedding Document no de tipo {type(other)}")
        if super().update(other):
            self.embedding_list=other.embedding_list
            self.embedding_title_list=other.embedding_title_list
            self.text_chunks=other.text_chunks
            return True
        return False
    
    
    
if __name__ == "__main__":
    pass
