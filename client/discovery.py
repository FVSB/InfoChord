from infochord_protocol import codec as wire
#from ..distributed.helper.protocol_codes import FIND_NODES

import socket
import threading
import time
import threading
import Pyro5.api
import random
from shared.logger import log_message
class ThreadingList:
    def __init__(self) -> None:
        self.lock_:threading.RLock=threading.RLock()
        self.lis_:list[str]=[]
    
        
    def update(self,item:list[str]):
        with self.lock_:
            
            self.lis_=item
    
    def get_list(self)->list[str]:
        with self.lock_:
            return self.lis_
        
    
    

class SearchServers:
    def get_remote_objet(url:str,proxy=None):
        """Devuelve el objeto remoto dada una url
            Puede lanzar excep si no la url se desconecto
        Args:
            url (str): _description_
        """
        ns = Pyro5.api.locate_ns()
        #log_message("Esta activo")
        uri = ns.lookup(url)
        #log_message("Encontro la uri")
        if proxy is None:
            return  Pyro5.api.Proxy(uri)
            
        return proxy(uri)



    def start(self):
        threading.Thread(target=self.start_server,daemon=True).start()
        #self.start_server()
        threading.Thread(target=self.broadcast,daemon=True).start()
        
    def __init__(self,ip:str,port:int) -> None:
        self.ip:str=ip
        self.port=port
        self.list_:ThreadingList=ThreadingList()
        self.start()
    
    def get_servers_ip(self)->list[str]:
        return self.list_.get_list()
    
    def get_random_server_ip(self)->str:
        """
        Retorna la ip de un nodo del servidor
        

        Returns:
            str: _description_
        """
        lis=self.list_.get_list()
        deadline = time.monotonic() + 30
        while len(lis)==0:
            if time.monotonic() >= deadline:
                raise TimeoutError("No server nodes discovered within 30 seconds")
            time.sleep(1)
            log_message(f"Esperando que la lista no este vacia")
            lis=self.list_.get_list()
        return random.choice(lis)
    def handle_client(self,client_socket):
        try:
            while True:
                # Recibir datos del servidor
                data = wire.recv_frame(client_socket)
                lis:list[str]=wire.loads(data)
                if not isinstance(lis,list):
                    raise Exception(f"debe recibir una lista de str no un {type(lis)}")
                
                #log_message(f"Mensaje recibido: {lis}", )
                self.list_.update(lis)
                break
        except Exception as e:
            log_message(f"Error al recibir datos: {e}")
        finally:
            client_socket.close()

    def start_server(self):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        host=self.ip
        port=self.port
        server_socket.bind((host, port))
        server_socket.listen(1)
        log_message(f"Escuchando en {host}:{port}")

        while True:
            client_socket, addr = server_socket.accept()
            #log_message(f"Conexión aceptada desde {addr}")
            # Crear un nuevo hilo para manejar el cliente
            client_thread = threading.Thread(target=self.handle_client, args=(client_socket,))
            client_thread.start()


    def broadcast(self,time_:float=2):
        while True :
            try:     
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                to_send = wire.dumps(
                    (28, None)
                )  # Serializar el objeto para poder enviarlo
                s.sendto(
                    to_send, (str(socket.INADDR_BROADCAST), self.port)
                )  # Enviar el broadcast

                s.close()
                time.sleep(time_)
            except:
                log_message("Ocurrio un error al enviar el broadcast")


