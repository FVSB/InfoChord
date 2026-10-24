

from searcher import *
import Pyro5.api
import subprocess

def register_url(object,url:str,daemon:Pyro5.server.Daemon,ns=None)->bool:
        """
        Dado una instancia de un objeto , la url y el daemon de pyro lo registra
        Args:
            object (_type_): _description_
            url (_type_): _description_
            daemon (_type_): _description_
            ns:Pyro Locate_ns()
        """
        
        if ns is None:
            ns=Pyro5.api.locate_ns()
        
        # Registrar los objetos remotos en el servidor de nombres
        uri1 = daemon.register(object)
        ns.register(url, uri1)
        log_message(f'Registrada la url {url}',func=register_url)
        return True

@Pyro5.api.expose
class SearcherServer(DistributedSearcher):
    """
    En esta clase añadimos el controlador de pyro

    Args:
        DistributedSearcher (_type_): _description_
        
    """
    def start_threads(self):
        super().start_threads()
        threading.Thread(target=self.check_name_server,daemon=True).start()# Chequea el name server
    
    def data_to_print(self):#Override
        super().data_to_print()
        log_message(f"Soy el duenno del server {self.i_am_name_server_owner}",func=self.data_to_print)
    
    
    def broadcast_handle(self, op: int, message: tuple[int, ChordNodeReference], address: str):
        
        if op==FIND_NODES:
            log_message(f"El cliente con direccion {address} ha pedido que le envie info")
            return self.response_network_to_client(address)
        return super().broadcast_handle(op, message, address)
    def __init__(self, ip: str, query_gestor: QueryGestor, port: int = 8001, flask_port: int = 8000, m: int = 160,url:str="search.search"):
        super().__init__(ip, query_gestor, port, flask_port, m)
        self.url:str=url
        """
        Url del server de pyro5
        """
        self.i_am_name_server_owner_:bool=False
        """
        Booleano para comprobar si yo soy el dueño del name server
        """
        self.i_am_name_server_owner_lock:threading.RLock=threading.RLock()
        
        self.name_server_process_=None
        """
        Variable para que cuando levante el proceso pueda
        guardar aca la variable para que despues pueda apagar el server
        """
        self.name_server_process_lock:threading.RLock=threading.RLock()
        
        
        self.daemon = Pyro5.server.Daemon(self.ip)
        """
        Esto es para tener un deamon de pyro5
        """
        
    def response_network_to_client(self,addr:str):
        try:
            nodes=self.get_nodes_ips()
            self._send_data(addr,obj_to_bytes(nodes))
            log_message(f"Respondido al cliente {addr}",func=self.response_network_to_client)
        except Exception as e:
            log_message(f"No se pudo responder al cliente {addr} Por el error Error: {e} \n {traceback.format_exc()}",func=self.response_network_to_client)
    
    
    def get_nodes_ips(self)->list[str]:
        """
        Devuelve una lista de ips 
        """
        log_message(f"Me han llamado para dar las ips ",func=self.get_nodes_ips)
        lis:list[ChordNodeReference]=[self.ip]
        try:
            succ=self.succ
            while succ.id!=self.id:
                lis.append(succ.ip)
                succ=succ.succ
            return lis
        except Exception as e:
            log_message(f"Ocurrio un error tratando de capturar todas las ips de la red Error: {e} \n {traceback.format_exc()}",func=self.get_nodes_ips)
            return lis
        
    def clear_nameserver(self):
        """
        Limpia el nameserver
        """
        try:
            # Conectar al Name Server
            ns = Pyro5.api.locate_ns()

            # Obtener todos los nombres registrados
            registered_names = ns.list()

            # Eliminar cada nombre registrado
            for name in registered_names:
                ns.remove(name)
                log_message(f"Removed {name}",func=self.clear_nameserver)

            log_message("All names removed from the Name Server.",func=self.clear_nameserver)

        except Pyro5.errors.NamingError as e:
            log_message(f"Error locating the Name Server: {e}",func=self.clear_nameserver)

        except Pyro5.errors.PyroError as e:
            log_message(f"Pyro error: {e}",func=self.clear_nameserver)

        except Exception as e:
            log_message(f"An unexpected error occurred: {e}",func=self.clear_nameserver)

    
    def is_active_name_server(self)->bool:
        """
        Dice True si el name server esta levantado False en caso contrario

        Returns:
            bool: _description_
        """
        
        try:
                        # Intentar conectar al servidor de nombres
                        ns = Pyro5.api.locate_ns()
                        log_message(f'El name server de pyro está activo',func=self.is_active_name_server)
                        return True
        except:
            log_message("El server esta apagado",func=self.is_active_name_server)
            return False
    
    def start_name_server(self)->bool:
        """
        Este metodo inicia el servidor de pyro 5
        Devuelve True si lo puede iniciar False en caso contrario

        Returns:
            bool: _description_
        """
        try:
            process =  subprocess.Popen(["python3", "-m", "Pyro5.nameserver",'--host','0.0.0.0'])
            log_message(f"Se inicio correctamente el servidor de pyro",func=self.start_name_server)
            self.name_server_process=process
            self.i_am_name_server_owner=True
            log_message(f"Se va a mandar a limpiar el nameserver",func=self.start_name_server)
            self.clear_nameserver()
            log_message(f"Se ha limpiado  el nameserver",func=self.start_name_server)
            return True
        except Exception as e: 
            log_message(f"El server esta ocupado no se ha podido iniciar aca Error:{e} \n {traceback.format_exc()}",func=self.start_name_server)
            return False
    
    def stop_name_server(self)->bool:
        """
        Manda a parar el name server si soy el duenno
        True si lo paro False en caso contrario
        Returns:
            bool: _description_
        """
        try:
            if not self.i_am_name_server_owner:
                raise Exception(f"No soy el duenno del namse server como lo voy a mandar a parar")
            process=self.name_server_process
            # Terminar el proceso
            process.terminate()

            # Esperar a que el proceso termine correctamente
            process.wait()
            log_message(f"Se finalizo correctamente el nameserver",func=self.stop_name_server)
            
            # Ahora ya no soy el duenno del name server
            self.i_am_name_server_owner=False
            
            return True            
            
        except Exception as e:
            log_message(f"Ha ocurrido un error tratando de parar el nameserver Error: {e} \n {traceback.format_exc()}",func=self.stop_name_server)
            return False
    
    def check_name_server(self,time_:float=2):
        while True:
            try:
            
                time.sleep(time_)
                if self.is_stable and self.i_am_leader:# Debo tener levantado el nameserver
                    if self.is_active_name_server() : 
                        log_message(f"El name server esta activo",func=self.check_name_server)
                        continue
                    # Entonces mandar a levantar yo el nameserver
                    log_message(f"Como soy el lider y no tengo levantado el name_server lo voy a mandar a levantar",func=self.check_name_server)
                    while not self.start_name_server():
                        log_message(f"No se ha podido iniciar el nameserver",func=self.check_name_server)
                    log_message(f"Voy a registrar mi url",func=self.check_name_server)
                    if register_url(self,self.url,self.daemon):
                        log_message(f"Se a registrado correctamente la url: {self.url}",func=self.check_name_server)
                        #Comantar esto si da problemas
                        threading.Thread(target=self.daemon.requestLoop,daemon=True).start()
                        log_message(f'Corriendo hilo del demonio de pyro para el url',func=self.check_name_server)
                    else:# Si hubo un error
                        log_message(f"No se registro correctamente la url",func=self.check_name_server)
                        
                elif self.i_am_name_server_owner:# No soy el lider pero soy el lider pero soy soy el duenno del proceso
                    # Lo apago
                    if self.stop_name_server():
                        log_message(f"Se apago correctamente el name server",func=self.check_name_server)
                    else: 
                        log_message(f"No se pudo apagar correctmante el nameserver Soy el duenno del nameserver {self.i_am_name_server_owner}",func=self.check_name_server)
            except Exception as e:
                log_message(f"Ha ocurrido un error chequeando el nameserver Error: {e} \n {traceback.format_exc()}",func=self.check_name_server)

    
        
    @property
    def i_am_name_server_owner(self)->bool:
        """
        Retorna si soy el dueño o no del name server 

        Returns:
            _type_: _description_
        """
        with self.i_am_name_server_owner_lock:
            return self.i_am_name_server_owner_
        
    @i_am_name_server_owner.setter
    def i_am_name_server_owner(self,value:bool):
        if not isinstance(value,bool):
            log_message(f"value debe ser de tipo bool no {type(value)}",func="i_am_name_server_owner")
            raise Exception(f"value debe ser de tipo bool no {type(value)}")
        with self.i_am_name_server_owner_lock:
            self.i_am_name_server_owner_=value
            
    @property
    def name_server_process(self):
        """
        Retorna seguro ante hilos la variable
        que tiene el proceso que creo el server
        """
        with self.name_server_process_lock:
            return self.name_server_process_
    
    @name_server_process.setter
    def name_server_process(self,value):
        with self.name_server_process_lock:
            self.name_server_process_=value
        
if __name__ == "__main__":
    log_message("Hello from Server node")
    ip = socket.gethostbyname(socket.gethostname())
    query_gestor=QueryGestor(func_get_embedding_list=create_embedding,func_score_embedding=cosine_similarity)
    node = SearcherServer(ip, m=10,query_gestor=query_gestor,url="search.search")
    node.start_node()  # Iniciar el pipeline

    while True:
        time.sleep(1)
