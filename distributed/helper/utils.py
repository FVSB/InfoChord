from infochord_protocol import codec as wire
import hashlib
from flask import Flask, request, jsonify, Response
import socket
import uuid
import threading
from enum import Enum, auto


def obj_to_bytes(obj:object)->bytes:
    return wire.dumps(obj)
def getShaRepr(data: str, max_value: int = 1024):
    """Hashea a SHA-1 los datos que entren y lo devuelve en un numero entre 1 y 16

    Args:
        data (str): _description_
        max_value (int, optional): _description_. Defaults to 16.

    Returns:
        _type_: _description_
    """
    # Genera el hash SHA-1 y obtén su representación en hexadecimal
    hash_hex = hashlib.sha1(data.encode()).hexdigest()

    # Convierte el hash hexadecimal a un entero
    hash_int = int(hash_hex, 16)

    # Define un arreglo o lista con los valores del 0 al 16
    values = list(range(max_value + 1))

    # Usa el hash como índice para seleccionar un valor del arreglo
    # Asegúrate de que el índice esté dentro del rango válido
    index = hash_int % len(values)

    # Devuelve el valor seleccionado
    return values[index]


def get_guid() -> str:
    """
    Genera un guid aleatorio

    Returns:
        str: _description_
    """
    # Genera un GUID aleatorio
    guid = uuid.uuid4()

    # Convierte el GUID a string
    guid_str = str(guid)

    return guid_str


def is_equal_list(lis_1:list,list_2:list)->bool:
    """
    Retorna True si la lista 1 y la 2 los objetos en ellas son iguales
    False en otro caso

    Args:
        lis_1 (list): _description_
        list_2 (list): _description_

    Returns:
        bool: _description_
    """
    return set(lis_1)==set(list_2)

def serialize_pyobj_to_json_file(obj) -> Response:
    serialize = wire.dumps(obj)
    return Response(serialize, content_type="application/json")


def deserialize_pyobj_from_json(data):
    return wire.loads(data)


class Paquete:
    def __init__(self, numero, bytes_datos, es_final):
        self.numero = numero
        self.bytes_datos = bytes_datos
        self.es_final = es_final

    def serialize(self):
        return wire.dumps(self)

    @staticmethod
    def deserialize(data) -> "Paquete":
        return wire.loads(data)





class CrudCode(Enum):
    Insert = auto()
    Update = auto()
    Delete = auto()
    ReInsertSelf=auto()

    def __lt__(self, other):
        if self.__class__ is other.__class__:
            return self.value < other.value
        return NotImplemented

    def __eq__(self, other):
        if self.__class__ is other.__class__:
            return self.value == other.value
        return NotImplemented

    def __gt__(self, other):
        if self.__class__ is other.__class__:
            return self.value > other.value
        return NotImplemented
    
    
class ThreadingSet:
    """
    Tener un set que no tiene errores ante el crud en hilos
    
    """
    def __init__(self,type_:type=None) -> None:
        """
        

        Args:
            type_ (type): tipo de datos a guardar None para que puedan ser multiples
        """
        self._type:type=type_
        self._set: set[self._type] = set([])
        self._lock: threading.RLock = threading.RLock()
        
        
    def add_item(self,item)->bool:
        """
        Se agrega un valor con seguridad ante hilos

        Args:
            item (_type_): _description_
        """
        if self._type!=None:
            if not isinstance(item,self._type):
                raise Exception(f'Item debe ser de tipo {self._type} no de tipo {type(item)} item:{item}')
        
        with self._lock:
            if item in self._set:
                return False
            
            self._set.add(item)
        return True
       
    
        
    def contains_item(self,item)->bool:
        """
        Dice si el elemento esta o no con seguridad ante hilos

        Args:
            item (_type_): _description_

        Raises:
            Exception: _description_

        Returns:
            bool: _description_
        """
        if self._type!=None:
            if not isinstance(item,self._type):
                raise Exception(f'Item debe ser de tipo {self._type} no de tipo {type(item)} item:{item}')
        with self._lock:
            return item in self._set
        
    
    def delete_if_exits_item(self,item)->bool:
        """
        True si se elimino, False si no existia 
        """
        with self._lock:
            if not self.contains_item(item):return False
            self._set.remove(item)
            return  True
