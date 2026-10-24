from chord.sync_storage_node import *


class DistributedDataBase(SyncStoreNode):
    #################################
    #                               #
    #       Lider Region            #
    #                               #
    #################################


    def _is_all_db_stable(self)->bool:
        """
        Este es un metodo para el lider
        False si no soy el lider o si yo o mi prede no tiene la data actualizada
        True si yo y mi predecesor tienen la data sincronizada

        Returns:
            bytes: _description_
        """
        if not self.i_am_leader:
            return False
        return self.is_sync_data and self.pred.is_data_sync()
    
    
    """
    Esta clase tiene la logica de una base de datos distribuida

    """
    
    def handle_request(self, data, option: int, a) -> bytes:#Override
        
        if option==IS_DATA_SYNC:# Manda a comprobar que la data está sincronizada
            return obj_to_bytes(self._is_sub_ring_db_is_stable())
        
        if option==IS_DB_STABLE:# Es pq soy el lider => respondo si yo and mi pred tienen la data estable
            return obj_to_bytes(self._is_all_db_stable())
        
        return super().handle_request(data, option, a)
    
    
    def data_to_print(self):#Override
        super().data_to_print()
        log_message(f'Es estable la DB: {self.is_db_stable()}',func=self.data_to_print)

    def __init__(self, ip: str, port: int = 8001, flask_port: int = 8000, m: int = 160):
        super().__init__(ip, port, flask_port, m)
      
        

  
            
    def _is_sub_ring_db_is_stable(self)->bool:
        """
        Chequea si yo y mis predecesores tienen la data sincronizada
        True: Si yo y mi predecesore tienen la data sincronizada (Si soy el lider digo True o False respecto a mi propio dato)
        False: Si yo o mi predecesor no tiene sincronizada la data
    
        """
        if self.i_am_leader:# Si soy el lider solo depende de si mi data está actualizada
            return self.is_sync_data
        
        return self.is_sync_data and self.pred.is_data_sync()
    
    
    def is_db_stable(self)->bool:
        """
        Metodo para saber si la base de datos es estable
        True  si la base de datos es consistente Se pueden realizar CUD
        False si la base de datos no es consistente esperar para hacer CUD

        Returns:
            bool: _description_
        """
        try:# Un and entre si yo soy estable y si el antecesor del lider es
            if self.i_am_alone :
                log_message(f"Como soy un solo nodo la db es estable <=> soy estable y la data esta sincronizada",func=self.is_db_stable)
                return self.is_stable and self.is_sync_data
                
            return self.is_sync_data and self.leader.is_data_base_stable()
        except Exception as e:
            log_message(f'Hubo un error tratando de saber si la db es estable Error:{e} \n {traceback.format_exc()}',func=self.is_db_stable)
            return False
    
    ########################
    #                      #
    #     OVERRIDE ZONE    #
    #                      #
    ########################
    def wait_for_stability(self):
        """
        Este metodo espera hasta que la db sea estable para completar cualquier accion
        """
        log_message(f"Entrando a chechear la estabilidad",func=self.wait_for_stability)
        addr_from = request.remote_addr
        deadline = time.monotonic() + 60
        while not self.is_db_stable():
            if time.monotonic() >= deadline:
                raise TimeoutError("Database did not stabilize within 60 seconds")
            log_message(f'Esperando a que la db sea estable para tramitar el post de {addr_from} ',func=self.wait_for_stability)
            time.sleep(0.5) # Tiempo de espera   
    def upload_file(self):
        self.wait_for_stability()
        return super().upload_file()
    def update_file(self):
        self.wait_for_stability()
        return super().update_file()
    def delete_file(self):
        self.wait_for_stability()
        return super().delete_file()
    def get_file_by_name(self):
        self.wait_for_stability()
        return super().get_file_by_name()
        
        
    
   
    
    
        
        
            

if __name__ == "__main__":
    log_message("Hello from Distributed Data Base node")
    ip = socket.gethostbyname(socket.gethostname())
    node = DistributedDataBase(ip, m=3)
    node.start_node()  # Iniciar el pipeline

    while True:
        pass
