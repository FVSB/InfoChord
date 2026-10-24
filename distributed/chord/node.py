from infochord_protocol import codec as wire
import socket
import threading
import sys
import time
import hashlib
import traceback
import logging
from helper.protocol_codes import *
from shared.logger import log_message
from helper.utils import getShaRepr
from chord.reference import ChordNodeReference
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import zmq


# Function to hash a string using SHA-1 and return its integer representation
# def getShaRepr(data: str):
#    return int(hashlib.sha1(data.encode()).hexdigest(), 16)
#




# Class representing a Chord node
class ChordNode:
    
    import socket

    def _send_data(self,ip: str, data: bytes,port:int=8001) -> bool:
        """metodo para enviar data

        Args:
            addr (str): _description_
            data (bytes): _description_

        Returns:
            bool: _description_
        """
        try:
           

            # Crear el socket del cliente
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

            # Conectar al servidor
            client_socket.settimeout(wire.SOCKET_TIMEOUT)
            client_socket.connect((ip, port))

            # Enviar los datos
            wire.send_frame(client_socket, data)

            # Cerrar la conexión
            client_socket.close()
            log_message(f"Enviado la data al addr {(ip,port)}",func=self._send_data)
            return True
        except Exception as e:
            log_message(f"Error enviando data al addr {(ip,port)} Error: {e} \n {traceback.format_exc()}",func=self._send_data)
            return False



    def start_node(self):
        """
        Llamar despues de inicializar para poder iniciar todo
        """
        log_message(f"Inicializando los hilos", func=self.start_node)
        self.start_threads()
        log_message(f"Levantado los hilos")

    def start_threads(self):
        """Levanta los hilos"""
        # Start background threads for stabilization, fixing fingers, and checking predecessor
        threading.Thread(
           target=self.stabilize, daemon=True  
        ).start()  # Start stabilize thread
        threading.Thread(
            target=self.fix_fingers, daemon=True
        ).start()  # Start fix fingers thread
        threading.Thread(
            target=self.check_predecessor, daemon=True
        ).start()  # Start check predecessor thread
        threading.Thread(
            target=self.start_server, daemon=True
        ).start()  # Start server thread
        threading.Thread(
            target=self.show, daemon=True
        ).start()  # Start funcion que se esta printeando todo el tipo cada n segundos
        threading.Thread(
            target=self._search_successor,
            daemon=True,
            args=(
                JOIN,
                self.ref,
            ),
        ).start()  # Enviar broadcast cuando no tengo sucesor
        threading.Thread(
            target=self._recive_broadcastt, daemon=True
        ).start()  # Recibir continuamente broadcast
        threading.Thread(target=self.stabilize_finger, daemon=True).start()

    # threading.Thread(target=self.search_test,daemon=True).start()

    def __init__(self, ip: str, port: int = 8001, m: int = 160):  # m=160
        """
        Devuelve un nodo de chord es

        Args:
            ip (str): _description_
            port (int, optional): _description_. Defaults to 8001.
            m (int, optional): _description_. Defaults to 160.
        """
        self.id = getShaRepr(ip)
        self.ip = ip
        self.port = port
        self.ref: ChordNodeReference = ChordNodeReference(self.ip, self.port)
        self.succ_: ChordNodeReference = self.ref  # Initial successor is itself
        """
        Initial successor is itself
        """
        self.succ_lock_: threading.RLock = threading.RLock()
        """ 
        Lock para que no haya problemas entre hilos para conocer el sucesor
        """
        self.pred_: ChordNodeReference = None  # Initially no predecessor
        """
        Referencia del predecesor
        """
        self.pred_lock_: threading.RLock = threading.RLock()
        """
        Lock para tener seguridad entre hilos del predecesor
        """

        self.m = m  # Number of bits in the hash/key space
        self.finger = [self.ref] * self.m  # Finger table
        self.index_in_fingers: dict[int, set[int]] = (
            {}
        )  # Diccionario que a cada id le asigna que indices ocupa en la finger table
        self.next = 0  # Finger table index to fix next
        self.data = {}  # Dictionary to store key-value pairs
        self.fingers_ok: bool = False  # Dice si los fingers estan ok o no
        self._key_range = (
            -1,
            self.ip,
        )  # the key_range [a,b) if a =-1 because no have predecesor
        self.cache: dict[int, str] = (
            {}
        )  # diccionario con la cache de todos los nodos de la red
        self._broadcast_lock: threading.RLock = (
            threading.RLock()
        )  # Lock para saber si puedo o no cambiar el valor de is succ
        # self.Is_Search_Succ_:bool=False #

    @property
    def succ(self) -> ChordNodeReference:
        """
        Retorna con seguridad de hilos al sucesor

        Returns:
            ChordNodeReference: _description_
        """
        with self.succ_lock_:
            if self.succ_ is None:
                self.succ_ = self.ref
            return self.succ_

    @succ.setter
    def succ(self, value: ChordNodeReference):
        """
        Guarda con seguridad de hilos el nuevo valor del sucesor

        Args:
            value (_type_): _description_

        Returns:
            _type_: _description_
        """
        with self.succ_lock_:
            self.succ_ = value

    @property
    def pred(self) -> ChordNodeReference:
        """
        Retorna con seguridad entre hilos la referencia del predecesor



        Returns:
            ChordNodeReference: _description_
        """
        with self.pred_lock_:
            return self.pred_

    @pred.setter
    def pred(self, value: ChordNodeReference | None):
        """
        Modificar el valor del predecesor

        Args:
            value (_type_): _description_



        Returns:
            _type_: _description_
        """
        with self.pred_lock_:
            self.pred_ = value

    @property
    def key_range(self):
        """
        The key range of the chrod node [a,b) b is the id of this node

        """
        return self._key_range

    def search_test(self):

        while True:
            try:
                time.sleep(3)
                log_message("%" * 20, level="INFO")
                # with ThreadPoolExecutor(max_workers=3) as executor:
                #    for i in range(0,20):
                #        future=executor.submit(self.find_succ,i) # Meterlo en el pool de hilos
                #        node=future.result(timeout=10)
                #
                #        log_message(f'El nodo que le pertenece el id {i} es el nodo con id {node.id}')
                for i in range(0, 20):
                    node = self.find_succ(i)
                    log_message(
                        f"El nodo que le pertenece el id {i} es el nodo con id {node.id}"
                    )

                log_message("+" * 20, level="INFO")
            except Exception as e:
                log_message(f"Error buscando informacion {e}", self.search_test)

    def show(self, time_: int = 3):
        """
        Show my ip and id and mi predecessor and succesors ips and ids
        """
        while True:
            log_message("-" * 20, level="INFO")
            log_message(
                f"Mi predecesor es {self.pred.id if self.pred else None} con ip {self.pred.ip if self.pred else None} ",
                level="INFO",
            )
            log_message(f"Yo soy id:{self.id},con ip:{self.ip} ", level="INFO")
            if self.succ.id == self.id:
                if self.succ.ip != self.ip:
                    log_message(
                        "El sucesor tiene igual ID pero no tiene igual ip", level="INFO"
                    )
                log_message(f"Todavia no tengo sucesor", level="INFO"),
            else:
                log_message(
                    f"Mi sucesor es {self.succ.id if self.succ else None} con ip {self.succ.ip  if self.succ else None}",
                    level="INFO",
                )

            log_message(
                f"La finger table es {self.finger} y está en estado {self.fingers_ok}",
                func=self.show,
            )

            log_message("*" * 20, level="INFO")

            time.sleep(time_)  # Se presenta cada 10 segundos

    def _search_successor(self, op: int, data: str = None, time_: float = 0.5) -> bytes:
        """Busca un sucesor si no tengo o si mi pred es None

        Args:
            op (int): _description_
            data (str, optional): _description_. Defaults to None.

        Returns:
            bytes: _description_
        """
        # Enviar broadcast cada vez que sienta que mi sucesor no existe
        while True:
            log_message(f"Tratando de hacer broadcast", func=self._search_successor)
            # Enviar broadcast para descubrir mi nuevo sucesor
            if self.succ.id == self.id or (
                self.succ.id != self.id and self.pred is None
            ):
                # with self._broadcast_lock:
                log_message(
                    f"Voy a enviar un broadcast para buscar un sucesor ",
                    func=self._search_successor,
                )
                try:
                    self._send_broadcast(op, data)
                    log_message(
                        f"Enviado el broadcas para buscar succ",
                        func=self._search_successor,
                    )

                    # self.Is_Search_Succ=True
                    time.sleep(2)  # Esperar 2 segundos
                except Exception as e:
                    log_message(
                        f"Ocurrio un problema enviando el broadcast: {e}",
                        level="ERROR",
                        func=self._search_successor,
                    )
            time.sleep(time_)

    def _send_broadcast(self, op: int, data: ChordNodeReference, time_=1):
        with self._broadcast_lock:
            log_message(
                f"Voy a enviar un broadcast con op {op} y data {data}",
                func=self._send_broadcast,
            )
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            to_send = wire.dumps(
                (op, data)
            )  # Serializar el objeto para poder enviarlo
            s.sendto(
                to_send, (str(socket.INADDR_BROADCAST), self.port)
            )  # Enviar el broadcast
            log_message(f"Enviado el broadcast", func=self._search_successor)
            s.close()
            time.sleep(time_)
            log_message(
                f"Acabo de enviar un broadcast con op: {op} y data {data}",
                func=self._send_broadcast,
            )

    def broadcast_handle(
        self, op: int, message: tuple[int, ChordNodeReference], address: str
    ):
        """
        Dado lo que se recibió en el broadcast toma las decisiones

        Args:
            op (int): _description_
            message (tuple[int, ChordNodeReference]): _description_
            address (str): _description_
        """
        op, node = message
        if int(op) == JOIN:
            log_message(
                f"El mensaje recibido al broadcast era para join desde el ip {address} de tipo {type(address)}"
            )

            self.join(node)

    def _recive_broadcastt(self,time_:float=1):
        try:
            # with self._broadcast_lock:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            client_socket.bind(
                ("", self.port)
            )  # Escucha en todas las interfaces en el puerto 8001
            client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            # Habilitar el uso compartido del puerto
            # client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            # Configurar un tiempo de espera
            # client_socket.settimeout(0.2)  # Tiempo de espera de 200 ms

            while True:
                try:
                    # with self._broadcast_lock:
                    log_message("Esperando Broadcast", func=self._recive_broadcastt)
                    message, address = client_socket.recvfrom(1024)
                    log_message(
                        f"El tipo de lo recibido en broadcast es {type(message)} ,  {type(address)}"
                    )
                    message: tuple[int, ChordNodeReference] = wire.loads(message)
                    log_message(
                        f"El tipo de lo recibido deserializado en broadcast es {type(message)} ,  {type(address)}"
                    )
                    log_message(
                        f"Mensaje recibido desde {address}: {message}",
                        func=self._recive_broadcastt,
                    )
                    if address[0] != socket.gethostbyname(socket.gethostname()):
                        log_message(
                            "Se recibio desde otro nodo", func=self._recive_broadcastt
                        )

                        log_message(
                            f"Este ahora es el mensaje {message} que tiene un tipo {type(message)}",
                            func=self._recive_broadcastt,
                        )

                        op, node = message
                        op = int(op)
                        log_message(
                            f"LLego la respuesta con opcion {op} de tipo {type(op)}"
                        )
                        log_message(
                            f"LLamando al handle para que tramite esto {op}",
                            func=self._recive_broadcastt,
                        )
                        self.broadcast_handle(op, message, address[0])

                    time.sleep(time_)  # FUncionaba ok con 3
                except:
                    log_message(
                        f"Error en el while True del recv broadcast Error: {traceback.format_exc()}",
                        self._recive_broadcastt,
                    )
        except Exception as e:
            log_message(
                f"Error recibiendo broadcast {e}, Error: {traceback.format_exc()}",
                func=self._recive_broadcastt,
                level="ERROR",
            )

    # Helper method to check if a value is in the range (start, end]
    def _inbetween(self, k: int, start: int, end: int) -> bool:
        """Helper method to check if a value is in the range (start, end]

        Args:
            k (int): _description_
            start (int): _description_
            end (int): _description_

        Returns:
            bool: _description_
        """
        if start < end:
            return start < k <= end
        else:  # The interval wraps around 0
            return start < k or k <= end

    # Method to find the successor of a given id
    def find_succ(self, id: int) -> "ChordNodeReference":
        """Method to find the successor of a given id

        Args:
            id (int): _description_

        Returns:
            ChordNodeReference: _description_
        """
        if id == self.id:
            return (
                self.ref
            )  # Osea si el id a buscar es el mismo que el mio que me devuelva

        node = self.find_pred(id)  # Find predecessor of id
        # log_message(f'El resultado de buscar el predecesor del nodo {id} es el nodo {node.id}',func=self.find_succ)
        if node.id != self.id:
            #  log_message(f'Para el id {id } se entregó el nodo {node.id}',func=self.find_succ)
            return node.succ
        else:
            #   log_message(f'Para el id {id } se entregó Se entregó mi sucesor {self.succ.id}',func=self.find_succ)
            return self.succ

    # Method to find the predecessor of a given id
    def find_pred(self, id: int) -> "ChordNodeReference":
        """Method to find the predecessor of a given id

        Args:
            id (int): _description_

        Returns:
            ChordNodeReference: _description_

        """
        # Comprobar que mi predecesor sea el predecesor de ello
        if self.pred and self._inbetween(id, self.pred.id, self.id):
            return self.pred

        node: ChordNodeReference = self
        # Comprobar que el sucesor esta vivo, sino se comprueba por
        i = 0
        while not self._inbetween(id, node.id, node.succ.id):

            i += 1

            if node.id == id:
                return (
                    node.pred
                )  # Es pq en el finguer se guardan sucesores de ids entonces si se pide el figuer mas cercano a ese nodo puede ser que devuelva el finguer con ese id

            if node.id == self.id:
                node = self.closest_preceding_finger(id)
            else:
                node = node.closest_preceding_finger(id)

            if i > 2 * self.m:  # Es pq se ha estancado entre yo y mi sucesor
                # log_message(f'Se va a buscar predecesor mas cercano en el finger del sucesor {self.succ.id} el id {id}',func=self.find_pred)
                node = self.succ.closest_preceding_finger(id)
            # log_message(f'El nodo mas cercano del finger es {node.id} que se le mandó a preguntar al sucesor {self.succ.id} por el id {id}',func=self.find_pred)

            # log_message(f'Se está buscando el nodo sucessor del id {id} se va por el nodo {node.id} iteracion {i}')
            if i > 4 * self.m:
                log_message(
                    f"Se ha superado el maximo de busqueda del finger mas cercano al id {id} con i {i}",
                    func=self.find_pred,
                )
                raise Exception(
                    f"Se ha superado el maximo de busqueda del finger mas cercano al id {id} con i {i}"
                )

        return node

    # Method to find the closest preceding finger of a given id
    def closest_preceding_finger(self, id: int) -> "ChordNodeReference":
        """Method to find the closest preceding finger of a given id

        Args:
            id (int): _description_

        Returns:
            ChordNodeReference: _description_
        """

        for i in range(self.m - 1, -1, -1):
            if self.finger[i].id == self.id:
                continue  # Dale continue pq no se puede seleccionar uno mismo en el finger table
            if self.finger[i] and self._inbetween(self.finger[i].id, self.id, id):
                # log_message(f'El nodo pred mas cercano por el finger al id {id} es el nodo {self.finger[i]}')
                return self.finger[i]
        # log_message(f'El más cercano soy yo del id {id}',func=ChordNode.closest_preceding_finger)
        return self.ref

    # Method to join a Chord network using 'node' as an entry point
    def join(self, node: "ChordNodeReference"):
        """
            Method to join a Chord network using 'node' as an entry point
            Siempre se busca un sucesor por lo tanto tengo que chequear si el nodo puede ser predecesor mio
        Args:
            node (ChordNodeReference): _description_
        """
        log_message(
            f"El nodo {node.id} mando solicitud de unirse como predecesor",
            func=ChordNode.join,
        )
        # Si

        if node:
            
            
            
            if (
                self.succ.id == self.id
            ):  # Es pq no tengo sucesor entonces acepto a cualquiera
                # Acepto y le digo que me haga su predecesor
                # Mi succ nuevo será el sucesor en el nuevo nodo
                self.succ = node  # node.find_successor(self.id) # Si da bateo solo quedarme con el nodo
                log_message(
                    f"Acabo de actualizar mi sucesor al nodo {self.succ.id}",
                    func=self.join,
                )
                self.succ.notify(self.ref)
                log_message(
                    f"Mande a notificar a mi nuevo sucesor :{self.succ.id} para que me haga su predecesor ",
                    func=self.join,
                )
            elif  self.pred is None and self.succ.id==node.id  and self.id!=node.id: # Entonces lo acepto como predecesor
                log_message(f"Voy aceptar como predecesor al nodo {node.id}",func=self.join)
                self.pred=node
                node.notify(self.ref)
            else:  # Caso que ya tengo un sucesor
                # Le pido al nodo el sucesor mio en su anillo
                log_message(f"Entro aca la peticion del nodo {node.id}", func=self.join)
                node_succ = node  # .find_successor(self.id) # Despues añado que busque al sucesor
                if (
                    self._inbetween(node_succ.id, self.id, self.succ.id)
                    or self.pred is None
                ):  # Es que se puede insertar pq debe estar entre yo y mi sucesor
                    self.succ = (
                        node_succ if node_succ.id < self.id else node
                    )  # Actualizo mi sucesor
                    log_message(
                        f"Acabo de actualizar mi sucesor al nodo {self.succ.id}",
                        func=self.join,
                    )
                    self.succ.notify(
                        self.ref
                    )  # Notifico para que me haga su predecesor
                    log_message(
                        f"Mande a notificar a mi nuevo sucesor :{self.succ.id} para que me haga su predecesor ",
                        func=self.join,
                    )

        else:  # Despues eliminar esto
            self.succ = self.ref
            self.pred = None
        # Si no puedo le respondo por mis ips

    def stabilize_finger(self, time_=5):
        """Comprueba si los fingers estan estables

        Args:
            time_ (int, optional): _description_. Defaults to 5.
        """
        while True:
            time.sleep(time_)
            try:
                log_message(
                    f"Chequeando estabilidad de los fingues", func=self.stabilize_finger
                )
                antes = self.fingers_ok
                succ_id = self.succ.id
                succ_check = succ_id == self.find_succ(succ_id).id
                check_pred = True
                if self.pred:
                    pred_id = self.pred.id
                    check_pred = pred_id == self.find_succ(pred_id).id
                my_check = self.id == (self.find_succ(self.id).id)
                self.fingers_ok = succ_check and check_pred and my_check

                if antes != self.fingers_ok:
                    log_message(
                        f" Los finges ahora estan en {self.fingers_ok} antes estaban {antes}",
                        func=self.stabilize_finger,
                    )

            except Exception as e:
                log_message(
                    f"Error chequeando que los finguers estan bien {e}",
                    func=self.stabilize_finger,
                )

    # Stabilize method to periodically verify and update the successor and predecessor
    def stabilize(self, time_: float = 0.5):  # COn uno funcionaba ok
        """Stabilize method to periodically verify and update the successor and predecessor"""
        Is = False
        node = None
        count_failed = 0  # Cant de veces que se a tratado de establecer conexion  sin exito con el predecesor del sucesor
        x = None
        while True:
            try:
                Is = False
                if self.succ.id != self.id:  # Es pq tengo sucesor
                    log_message("stabilize", func=ChordNode.stabilize)
                    if self.succ is None:
                        self.succ = self.ref
                    try:
                        x = (
                            self.succ.pred
                        )  # Aca seria preguntar por quien es el sucesor de mi id
                        if not isinstance(x, ChordNodeReference):
                            log_message(
                                f"El sucesor debe ser un chordnode reference x:{x} es de tipo {type(x)}"
                            )
                    except:  # Esto es que no responde el sucesor
                        count_failed += 1

                        if count_failed > 3:
                            # Trata de contactar con el succ y preguntarle por el predecesor si pasa algun problema en la peticion
                            # Mi sucesor soy yo
                            # Si mi sucesor era mi antecesor entonces hago el antecesor null
                            # if self.succ.id==self.pred.id: self.pred=None
                            # time.sleep(20)
                            # log_message(
                            #    "Seleccionando_Nuevo_Sucesor", func=ChordNode.stabilize
                            # )
                            # nearest_node = self.find_succ(self.id + 1)
                            # log_message(
                            #    f"EL nodo que tiene {nearest_node.id} el mas cercano",
                            #    func=ChordNode.stabilize,
                            # )
                            # self.succ = (
                            #    nearest_node
                            #    if nearest_node.id != self.succ.id
                            #    else self.ref
                            # )
                            # continue   Lo anterior funcionaba antes
                            self.succ = self.ref

                    log_message(f" Este es X {x}", func=ChordNode.stabilize)
                    if x and x.id != self.id:
                        log_message(f"Otra vez x {x}", func=ChordNode.stabilize)
                        if x and self._inbetween(x.id, self.id, self.succ.id):
                            self.succ = x
                        log_message("A Notificar", func=ChordNode.stabilize)
                        try:
                            self.succ.notify(self.ref)
                        except (
                            Exception
                        ) as e:  # Si no se puede conumicar con el nuevo sucesor caso que sea que era sucesor y predecesor
                            # y se desconecto pues poner al sucesor como yo mismo
                            log_message(
                                f" Fallo comunicarse con el nuevo sucesor {e}",
                                func=ChordNode.stabilize,
                                level="ERROR",
                            )
                            self.succ = self.ref

            except Exception as e:

                log_message(
                    f"  Is_True:{Is}_  node:{node}_  _::: ERROR in stabilize: {e}",
                    func=ChordNode.stabilize,
                    level="ERROR",
                )
                traceback.print_exc()

            log_message(
                f"successor : {self.succ} predecessor {self.pred}",
                func=ChordNode.stabilize,
            )
            time.sleep(time_)  # Poner en produccion en 1 segundo Funcionaba bien con 5

    # Notify method to INFOrm the node about another node
    def notify(self, node: "ChordNodeReference"):
        """Notify method to INFOrm the node about another node"""
        if node.id == self.id:
            log_message(f"Me llego un notify de mi mismo",func=self.notify)
        if not self.pred or self._inbetween(node.id, self.pred.id, self.id):
            self.pred = node
        elif self.succ.id==self.id and self.pred.id==node.id:# Es que no tengo sucesor
            log_message(f"Voy hacer el nodoc {node.id} como mi sucesor dado que solo estamos los dos",func=self.notify)
            self.succ=node
        else:
            pass  # Enviar mensaje que de no puede y le paso al que tengo como como predecesor de ese id

    def _delete_from_all_ocurrencies(self, id_node: int, new_node: ChordNodeReference):
        """Dado un id de un nodo a eliminar de la finger table y otro nodo para remplazar
            Se actualiza la finger table

        Args:
            id_node (int): ID del nodo a eliminar
            new_node (ChordNodeReference): NOdo a insertar

        Raises:
            Exception: _description_
        """
        log_message(
            f"La finger table antes {self.finger}",
            func=self._delete_from_all_ocurrencies,
        )
        if id_node not in self.index_in_fingers:
            log_message(
                f"El nodo de id {id_node} no esta en el diccionario de fingers con su posicion{self.index_in_fingers} ",
                func=self._delete_from_all_ocurrencies,
            )
            return
        lis_to_change = self.index_in_fingers[
            id_node
        ]  # cambiar pir mi todas las  apararicones d ela finger table
        log_message(
            f"La lista de ocurrencias es {lis_to_change}",
            func=self._delete_from_all_ocurrencies,
        )
        for index in lis_to_change:
            temp = self.finger[index]
            if temp.id != id_node:
                raise Exception(
                    f"Para poder quitar de la finger table tiene que coincidir el que esta en la table {temp.id} en el index {index} con {new_node.id}"
                )
            self.finger[index] = new_node
            # ELiminar la llave del diccionario
        del self.index_in_fingers[id_node]
        log_message(
            f"Se elimino de la lista de fungers_index el nodo {id_node} por el nodo {new_node.id}",
            func=self._delete_from_all_ocurrencies,
        )
        log_message(
            f"la nueva finger table {self.finger}",
            func=self._delete_from_all_ocurrencies,
        )

    # Fix fingers method to periodically update the finger table
    def fix_fingers(self):
        """Fix fingers method to periodically update the finger table"""
        while True:
            log_message(f"La finger table {self.finger}", func=self.fix_fingers)
            try:
                self.next += 1
                if self.next >= self.m:
                    self.next = 0
                rr = (self.id + 2**self.next) % 2**self.m
                # log_message(f'Mandando a buscar el sucesor del nodo con id {rr}',func=self.fix_fingers)
                a = self.find_succ((self.id + 2**self.next) % 2**self.m)
                # log_message(f'El resultado de buscar el sucesor de {rr} es {a.id} ',func=self.fix_fingers)
                ok = False
                for _ in range(3):
                    if a.check_predecessor():  # Chequear que el nodo esta vivo
                        if a.id == 8:
                            log_message(
                                f"Al nodo 8 se le dio ok,", func=self.fix_fingers
                            )
                        ok = True
                        break
                    else:
                        log_message(
                            f"El nodo {a.id} no se encuentra en fix fingers",
                            func=ChordNode.fix_fingers,
                        )
                    time.sleep(0.5)
                # a=a.succ if not ok else a
                if not ok:
                    log_message(
                        f"El nodo {a.id} se desconecto de la red",
                        func=ChordNode.fix_fingers,
                    )
                    try:
                        i = self.next + 1
                        k = i if self.next < self.m else 0
                        change = False
                        while i != self.next:
                            q = self.closest_preceding_finger(
                                i
                            )  # Buscar por los antecesores
                            log_message(
                                f"El nodo q ahora es {q.id} con i = {i}",
                                func=self.fix_fingers,
                            )
                            if q.id != a.id:  # Encontrar el primero que sea distinto
                                self._delete_from_all_ocurrencies(
                                    a.id, q
                                )  # ELiminar todas las ocurriencias de id y poner las de q
                                a = q
                                log_message(
                                    f"Se va a parar aca el while con q ={q.id}",
                                    func=self.fix_fingers,
                                )
                                change = True
                                break
                            i = i + 1 if i < self.m else 0

                        if not change:  # Entonces lo cambio por mi en la finger table

                            log_message(
                                f"No se pudo encontrar un nuevo sucesor para el nodo {a.id} por lo tanto yo sere el sucesor",
                                func=ChordNode.fix_fingers,
                            )
                            self._delete_from_all_ocurrencies(
                                a.id, self.ref
                            )  # Eliminar las referencias de la finger table y ponerme a mi como sucesor de ese id

                            a = (
                                self.ref
                            )  # Despues ver si se puede llamar al nodo '0' para que sea el

                        log_message(
                            f"El nodo a ahora es {a}", func=ChordNode.fix_fingers
                        )
                    except Exception as e:
                        log_message(
                            f"Fallo buscar el sucesor del prececesor del nodo {a.id+1} {e} \n Error:{traceback.format_exc()} ",
                            func=self.fix_fingers,
                        )

                log_message(
                    f"Se a añadido el nodo {a.id} a la lista de fingers",
                    func=self.fix_fingers,
                )
                self.finger[self.next] = a
                # Añadir al diccionario
                self.index_in_fingers.setdefault(a.id, set([self.next]))
                self.index_in_fingers[a.id].add(self.next)

            except Exception as e:
                log_message(
                    f"ERROR in fix_fingers: {e} Error:{traceback.format_exc()}",
                    func=ChordNode.fix_fingers,
                    level="ERROR",
                )
            time.sleep(5)  # 10

    # Check predecessor method to periodically verify if the predecessor is alive
    def check_predecessor(self, time_: float = 0.5):  # Por defecto 2
        """Check predecessor method to periodically verify if the predecessor is alive"""
        counter = 0
        while True:
            try:
                time.sleep(time_)

                log_message(f"Chequeando predecesor", func=self.check_predecessor)
                if self.pred:
                    if (
                        not self.pred.check_predecessor()
                        or self.pred.succ.id != self.id
                    ):  # Saber si esta vivo y su sucesor soy yo
                        counter += 1
                        if counter > 3:
                            log_message(
                                f"No se restablecio conexion con el predecesor {self.pred} ",
                                func=ChordNode.check_predecessor,
                                level="ERROR",
                            )
                            raise Exception(
                                f"No se restablecio conexion con el predecesor {self.pred} "
                            )
                    else:
                        counter = 0
                        log_message(
                            f"El predecesor de mi sucesor es { self.pred.succ.id}",
                            func=self.check_predecessor,
                        )

                    log_message(
                        f"Chequeando predecesor ...", func=ChordNode.check_predecessor
                    )
            except Exception as e:
                log_message(
                    f"Se desconecto el predecesor con id {self.pred.id} e ip {self.pred.ip},error:{e}",
                    func=ChordNode.check_predecessor,
                    level="ERROR",
                )
                traceback.print_exc()
                self.pred = None  # Hago mi predecesor en None

    def find_key_owner(self, key: int) -> ChordNodeReference:
        """Localiza al dueño de una llave

        Args:
            key (int): _description_

        Returns:
            ChordNodeReference: _description_
        """
        log_message(
            f"Me han llamado para buscar el nodo dueño de la llave {key}",
            func=self.find_key_owner,
        )

        if (self.succ.id == self.id and self.pred is None) or self._inbetween(
            key, self.pred.id, self.id
        ):  # Si está entre mi predecesor y yo me devuelvo
            # Si esta entre yo y mi sucesor o si soy el unico nodo en la red
            log_message(f"Yo soy el dueño de la llave {key}", func=self.find_key_owner)
            return self.ref

        if self.succ.id != self.id and self.pred is None:
            log_message(f"Anillo inestable", func=self.find_key_owner)
            raise Exception("Anillo Inestable")

        log_message(
            f"Enviando a mi sucesor a que se encargue de la llave {key}",
            func=self.find_key_owner,
        )
        return self.succ.find_key_owner(key)

    def store_key(self, key: int, value) -> ChordNodeReference:
        log_message(
            f"Me han llamado a guardar la llave {key}, con el value {value} de tipo {type(value)}",
            func=self.store_key,
        )

        node_to_store = self.find_key_owner(key)  # Buscar quien debe tener la llave
        if self.id == node_to_store.id:  # Yo debo guardar la llave
            self.data.setdefault(key, value)
            return self.ref

        log_message(
            f"Enviando al nodo {node_to_store.id} la llave {key} y valor {value} para que la guarden",
            func=self.store_key,
        )
        return node_to_store.store_key(key, value)

    def retrieve_key(self, key: int) -> tuple[ChordNodeReference, int, object]:
        """Intenta devuelve la llave si el nodo la contiene None si no está

        Args:
            key (int): _description_

        Returns:
            tuple[ChordNodeReference,int,object]: _description_
        """
        try:
            log_message(
                f"Se ha mandado a buscar el valor de la llave {key}",
                func=self.retrieve_key,
            )
            node_to_retrieve = self.find_key_owner(key)
            log_message(
                f"El nodo que le pertenece esa llave {key} es {node_to_retrieve.id}",
                func=self.retrieve_key,
            )
            if self.id == node_to_retrieve.id:  # Entonces debo Hacer retrieve yo
                log_message(
                    f"Yo soy el dueño de la llave {key}", func=self.retrieve_key
                )
                value = self.data.get(
                    key, None
                )  # Si no esta la llave que devuelva None
                response = (self.ref, key, value)
                log_message(
                    f"Como resultado del retrieval de la key {key} es {response}",
                    func=self.retrieve_key,
                )
                return response
            response = node_to_retrieve.retrieve_key(key)
            log_message(
                f"La respuesta de retrieval al nodo con id{node_to_retrieve.id} es {response}",
                func=self.retrieve_key,
            )
            return response
        except Exception as e:
            log_message(
                f"Hubo un error en el retrieve key: {e} \n {traceback.format_exc()} ",
                func=self.retrieve_key,
            )

    def client_store_key(self, key: int, value) -> tuple[int, int]:
        """Es paraa que el cliente temporal de chord meta una llave

        Args:
            key (int): _description_
            value (_type_): _description_

        Returns:
            tuple(int,int): (id nodo que lo guardo , llave guardada)
        """
        node = self.store_key(key, value)
        log_message(
            f"El nodo encargado de guardar la llace {key } es {node.id}",
            func=self.client_store_key,
        )
        return (node.id, key)

    def client_retrieve_key(self, key: int):
        """_summary_

        Args:
            key (int): _description_

        Returns:
            tuple(int,int,obj): Id nodo que la tenia, llave a buscar, valor guardado
        """
        log_message(
            f"El cliente ha mandado a tomar lo que guarda la llave {key}",
            func=self.client_retrieve_key,
        )
        node, key, value = self.retrieve_key(key)
        log_message(
            f"El nodo que tenia la llave:{key}, tiene id:{node.id}, el valor es {value} de tipo{type(value)}",
            func=self.client_retrieve_key,
        )
        return (node.id, key, value)

    def handle_request(self, data, option, a):
        """
        Recibe las peticiones en los distintos hilos

        Args:
            data (_type_): _description_
            option (int): Dice el tipo que es
            a (_type_): _description_

        Returns:
            _type_: _description_
        """

        data_resp: bytes = None
        if option == FIND_SUCCESSOR:
            id = int(data[1])
            data_resp = self.find_succ(id)
        elif option == FIND_PREDECESSOR:

            id = int(data[1])
            # log_message(f'Me llego una peticion de buscar el predecesor de {id}',func=ChordNode.start_server)
            # log_message(f'Me llego una peticion de buscar el predecesor de {id}',func=self.start_server)
            data_resp = self.find_pred(id)
        elif option == GET_SUCCESSOR:
            # log_message(f'Se a mandando a pedir el sucesor del nodo',func=self.handle_request)
            data_resp = self.succ if self.succ else self.ref
        # log_message(f'Se a mandando a pedir el sucesor del nodo se a respondido {data_resp.id}',func=self.handle_request)
        elif option == GET_PREDECESSOR:
            data_resp = self.pred if self.pred else self.ref
        elif option == NOTIFY:

            # log_message(f'Llego una notificacion del ip:{ip}',func=ChordNode.start_server)

            node: ChordNodeReference = data[1]
            log_message(f'LLegado al notify {node}',func=self.start_server)
            id = node.id
            ip = node.ip
            # log_message(f'Llego una notificacion del ip:{ip}',func=self.start_server)
            self.notify(ChordNodeReference(ip, self.port))
        elif option == CHECK_PREDECESSOR:

            data_resp = self.ref
            data_resp = self.ref
        elif option == CLOSEST_PRECEDING_FINGER:
            id = int(data[1])
            # log_message(f'Se esta buscando el finger mas cercano para el id {id}',func=self.handle_request)
            data_resp = self.closest_preceding_finger(id)
        # log_message(f'El nodo que esta mas cerca al id { id} en la table de finger es {data_resp.id}',func=self.handle_request)
        elif option == JOIN:
            ip = data[2]
            # log_message(f'Recibido la peticion de JOIN desde ip {ip} con id: {getShaRepr(ip)} ')
            self.join(ChordNodeReference(ip, self.port))

            node: ChordNodeReference = data[1]
            ip = node.ip
            # log_message(f'Recibido la peticion de JOIN desde ip {ip} con id: {getShaRepr(ip)} ',func=self.start_server)
            self.join(node)
        elif option == STORE_KEY:
            # Trae una tupla (key,value)
            log_message(
                f"A llegado una peticion de guardar la llave {a[0] } de  tipo {type(a[0])} y el valor {a[1]} de tipo {type(a[1])}",
                func=self.start_server,
            )
            data_resp = self.store_key(a[0], a[1])
            log_message(
                f"El nodo que guardo la llave es {data_resp.id}",
                func=self.server_handle,
            )
        elif option == STORE_KEY_CLIENT:
            key = a[0]
            value = a[1]
            log_message(
                f"Ha llegado una peticion de un cliente de meter una llave y valor key{key} valor {value}",
                func=self.server_handle,
            )
            data_resp = self.client_store_key(key, value)
            log_message(
                f"La respues al cliente de guardar la llava {key} y el value {value} es {data_resp} de tipo {type(data_resp)}",
                func=self.server_handle,
            )
        elif option == RETRIEVE_KEY:
            search_key = int(a)
            log_message(
                f"Se ha enviado hacer Retrieve a la llave {search_key}",
                func=self.server_handle,
            )
            response = self.retrieve_key(search_key)
            node, key, value = response
            log_message(
                f"El resultado de retrieve la llave {search_key} es  {node}, llave encontrada:{key},valor:{value} de tipo {type(value)}",
                func=self.server_handle,
            )
            data_resp = response
        elif option == RETRIEVE_KEY_CLIENT:
            key = int(a)
            log_message(
                f"A llegado desde un cliente la peticion de tomar el valor que guarda la llave {key}",
                func=self.server_handle,
            )
            data_resp = self.client_retrieve_key(key)
            node_id, key_to_search, value = data_resp
            log_message(
                f"El nodo con id {node_id}, guardaba el valor {value} de tipo {type(value)} de la llave {key_to_search}",
                func=self.server_handle,
            )

        elif option == FIND_KEY_OWNER:  # Buscando a quien le toca esa id
            log_message(
                f"Ha llegado una peticion de saber si yo debo ser el dueño de esa llave {a}, {type(a)}",
                func=self.server_handle,
            )
            data_resp = self.find_key_owner(
                a
            )  # Busca el nodo que puede tener esa llave ojo no significa que la tenga
            log_message(
                f"El que debe tener la llave {a}, {type(a)} es {data_resp.id} de tipo {type(data_resp)}",
                func=self.server_handle,
            )
        elif option == PING:#Para saber si estoy vivo
            log_message(f"Se me ha llamado hacer ping",func=self.server_handle)
            data_resp=True

        if data_resp:

            response = wire.dumps(data_resp)
            if len(response) < 1 or len(response) > 1020:
                log_message(
                    f"El len de la respuesta a enviar es de {len(response) } que era un {data_resp.id}",
                    func=self.server_handle,
                )

            # conn.sendall(response)
            # socket.send(response)
        else:
            # socket.send(wire.dumps(' '))
            response = wire.dumps("Errrorrrrrr ")

            log_message(
                f"El len de la respuesta a enviar es de {len(response) } que era un Enviando el string error  buscando la opcion {option}",
                func=self.server_handle,
            )
        return response

    def server_handle(self, conn, addr):
        # log_message(f'new connection from {addr}',func=ChordNode.start_server)

        try:
            data = wire.loads(wire.recv_frame(conn))
            if not isinstance(data, tuple) or len(data) != 2 or type(data[0]) is not int:
                raise wire.ProtocolError("Expected (operation, payload)")
            option, a = data
            if isinstance(a, dict):
                data = (option, ChordNodeReference(a["ip"]))
            response = self.handle_request(data, option, a)
            wire.send_frame(conn, response)
        except (ValueError, OSError) as exc:
            log_message(f"Rejected node request: {type(exc).__name__}")
        finally:
            conn.close()

    def start_server(self):

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((self.ip, self.port))
            s.listen(50) # Con 10 iba bien
            pool = ThreadPoolExecutor(max_workers=40)
            while True:

                try:

                    conn, addr = s.accept()
                    # pool.submit(self.server_handle,conn,addr)
                    threading.Thread(
                        target=self.server_handle,
                        args=(
                            conn,
                            addr,
                        ),
                    ).start()

                except Exception as e:
                    log_message(
                        f"Error en start server {traceback.format_exc()}",
                        func=self.start_server,
                    )


if __name__ == "__main__":
    print("Hello dht")

    ip = socket.gethostbyname(socket.gethostname())
    log_message(f" Mi ip es {ip}")
    node = ChordNode(ip, m=4)
    # node.start_threads()  # Iniciar el nodo
    node.start_node()  # Iniciar el nodo

    while True:
        pass
