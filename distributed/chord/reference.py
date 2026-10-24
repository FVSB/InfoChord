from infochord_protocol import codec as wire
import socket
import traceback
import logging
from helper.protocol_codes import *
from shared.logger import log_message
from helper.utils import getShaRepr
from helper.query import QueryHandle
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import zmq

# Class to reference a Chord node
class ChordNodeReference:
    """
    Class to reference a Chord node
    """
    def __init__(self, ip: str, port: int = 8001):
        self.id = getShaRepr(ip)
        self.ip = ip
        self.port = port

    def _send_data(self, op: int, data: str = "") -> "ChordNodeReference":
        if isinstance(data, ChordNodeReference):
            data = {"op": op, "id": data.id, "ip": data.ip}
        # if not (isinstance(data,tuple) or isinstance(data,dict) or isinstance(data,str)):
        #    log_message(f'El data {data} es de tipo {type(data)}',func=self._send_data)
        data = data if data is not None else ""
        # log_message(f'Typo de op {type(op)}  tipo de data{type(data)}')
        data = (op, data)
        # Serializar el objeto
        data = wire.dumps(data)
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(wire.SOCKET_TIMEOUT)
                s.connect((self.ip, self.port))
                wire.send_frame(s, data)
                new_data = wire.recv_frame(s)
                # log_message(f'La data es {new_data}',func=self._send_data)
                if len(new_data) < 1:
                    log_message(
                        f"Se quiso enviar al nodo {self.ip } una peticion de tipo {op} y el len de new_data es {len(new_data)}",
                        func=self._send_data,
                    )
                data_format = wire.loads(new_data)  # Al tipo de dato de python

                # if not isinstance(data_format,ChordNodeReference):
                #    log_message(f'La respuesta recibida del nodo {self.id} es {data_format} de tipo {type(data_format)}',func=self._send_data)

                # log_message(f'A llegado un objeto {data_format} de tipo {type(data_format)}',func=self._send_data)
                return data_format
        except Exception as e:
            # print(f"ERROR sending data: {e} al nodo con id {self.id} e ip {self.ip}")
            log_message(
                f"ERROR sending data: {e} al nodo con id {self.id} en la opcion {op} e ip {self.ip} ,Error:{str(traceback.format_exc())}",
                level="ERROR",
            )
            # logger.info()
            traceback.print_exc()
            raise Exception(f"Exception in node reference sendata")

    def find_successor(self, id: int) -> "ChordNodeReference":
        """Method to find the successor of a given id"""
        response = -1
        # try:
        #    response = self._send_data(FIND_SUCCESSOR, id)
        #    response.port=self.port
        #    return response
        # except Exception as e:
        #    log_message(f'Hubo un error en find_successor con response {response} de tipo {type(response)} con Error:{e}',func=self.find_successor)
        response = self._send_data(FIND_SUCCESSOR, id)
        return response

    # Method to find the predecessor of a given id
    def find_predecessor(self, id: int) -> "ChordNodeReference":
        # try:
        #    response = self._send_data(FIND_PREDECESSOR, id)
        #    return response
        # except Exception as e:
        #    log_message(f'Hubo un error en find_successor con response {response} de tipo {type(response)} con Error:{e}',func=self.find_predecessor)

        response = self._send_data(FIND_PREDECESSOR, id)
        return response

    def find_key_owner(self, id: int) -> "ChordNodeReference":
        response = self._send_data(FIND_KEY_OWNER, id)
        return response

    # Property to get the successor of the current node
    @property
    def succ(self) -> "ChordNodeReference":
        response = self._send_data(GET_SUCCESSOR)
        # log_message(f'EL sucesor del nodo {self.id} es el nodo {response.id}',)
        return response

    # Property to get the predecessor of the current node
    @property
    def pred(self) -> "ChordNodeReference":
        response = self._send_data(GET_PREDECESSOR)
        return response
    
    @property
    def leader(self)->"ChordNodeReference":
        response=self._send_data(GET_LEADER)
        return response

    # Method to notify the current node about another node
    def notify(self, node: "ChordNodeReference"):
        self._send_data(NOTIFY, node)

    # Method to check if the predecessor is alive
    def check_predecessor(self) -> bool:
        # log_message(f'Enviando menajse al predecesor',func=self.check_predecessor)
        response = None
        try:
            response = self._send_data(CHECK_PREDECESSOR)
        except:
            log_message(
                f"Error tratando de comunicar con el predecesor ",
                func=self.check_predecessor,
            )
            return False
        # print(f'La respuesta de si esta vivo el nodo vivo o no es {response}')
        # log_message(
        #    f"La respuesta de si esta vivo el nodo vivo o no es {response}",
        #    func=ChordNodeReference.check_predecessor,
        #    extra_data={"func": "check_predecesor from ChordReferenceNode"},
        # )
        if response in ["", " ", None, EMPTYBIT]:
            return False
        try:
            node = response
            return node.id == self.id
        except:
            log_message(
                f"Hubo problemas al tratar de conocer la respuesta del nodo predecesor que el envio",
                level="ERROR",
                func=self.check_predecessor,
            )
            return False

    # Method to find the closest preceding finger of a given id
    def closest_preceding_finger(self, id: int) -> "ChordNodeReference":
        response = self._send_data(CLOSEST_PRECEDING_FINGER, id)
        return response

    # Method to store a key-value pair in the current node
    def store_key(self, key: str, value: str):
        response = self._send_data(STORE_KEY, (key, value))
        return response

    # Method to retrieve a value for a given key from the current node
    def retrieve_key(self, key: str) -> str:
        response = self._send_data(RETRIEVE_KEY, key)
        return response

    ###################################
    #                                 #
    #       Añadido nuevo             #
    #                                 #
    ###################################
    
    def _check_boolean_option(self,op:int,default_in_except:bool=False)->bool:
        """
        Dada una opcion devuelve la respuesta booleana de esta
        Args:
            op (int): operacion a ejercert
            default_in_except (bool, optional): Valor booleano en caso de exepcion . Defaults to False.
        """
        try:
            response: bool = self._send_data(op=op)
            if not isinstance(response, bool):
                raise Exception(
                    f"response debe ser bool no {type(response)} {response}"
                )
            return response
        except Exception as e:
            log_message(
                f"No se pudo preguntar al nodo {self.id} por la opción {op} Error:{e} \n {traceback.format_exc()}",
                func=self._check_boolean_option,
            )
            return default_in_except

    def check_network_stability(self) -> bool:
        """
         Esto lo puede responder solo el lider
         El lider responde si esta estable la red o no

        Returns:
            bool: True: La red es estable , False: La red no es estable
        """
        return self._check_boolean_option(op=CHECK_NETWORK_STABILITY,default_in_except=False)

    def check_in_election(self) -> bool:
        """
        Chequea si yo estoy en elección, el lider toma la iniciativa

        Returns:
            bool: True si lo esta False si no
        """
        log_message(f"Voy a preguntar al nodo {self.id} si esta en eleccion",func=self.check_in_election)
        return self._check_boolean_option(op=CHECK_IN_ELECTION,default_in_except=True)
    
    def is_data_sync(self)->bool:
        """
        True si tengo la data sincronizada 
        False en otro caso
        """      
        return self._check_boolean_option(op=IS_DATA_SYNC,default_in_except=False)
    
    
    def is_data_base_stable(self)->bool:
        """
        True si la database es estable
        False si no lo es o hubo error

        Returns:
            bool: _description_
        """
        return self._check_boolean_option(op=IS_DB_STABLE,default_in_except=False)
    
    ##############################
    #                            #
    #     Nuevo ahora para terminar la resincronizacion adecuada #
    #                            #
    ###############################
    
    def can_update_data(self)->bool:
        """
        Retorna True si ya sincronize mi data  se supone que mis antecesores
        False si ocurrio un errror

        Returns:
            bool: _description_
        """
        return self._check_boolean_option(op=CAN_UPDATE_DATA,default_in_except=False)
    #######################
    #
    # Nuevo para comprobar que estoy vivo
    #
    ##########################
    def ping(self)->bool:
        return self._check_boolean_option(op=PING,default_in_except=False)
    
    def i_am_leader(self)->bool:
        return self._check_boolean_option(op=I_AM_LEADER,default_in_except=False)
    
    def __str__(self) -> str:
        return f"ChordNodeReference:{self.id},{self.ip},{self.port}"

    def __repr__(self) -> str:
        return str(self)

    def __eq__(self, value: "ChordNodeReference") -> bool:
        if not isinstance(value, ChordNodeReference):
            # raise Exception(f'Value tiene que ser de tipo ChordNodeReference no de tipo {type(value)}, {value}')
            return False
        return self.ip == value.ip

    def __hash__(self) -> int:
        return hash(self.ip)
