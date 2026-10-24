from infochord_protocol import codec as wire
from chord.node import *



class ChordNodeLiderReference(ChordNodeReference):
    def __init__(self, ip: str, port: int = 8001):
        super().__init__(ip, port)
        
    #def check_predecessors_stability(self)->bool:
    #    """
    #    Comprueba si yo y todos los predecesores en el anillo son estables
    #    Si es el lider el se pone estable 
#
    #    Returns:
    #        bool: Si yo y mi predecesor es estable
    #    """
    #    try:
    #        response:bool=self._send_data(op=CHECK_STABILITY)
    #        if not isinstance(response,bool):
    #            raise Exception(f'response debe ser bool no {type(response)} {response}')
    #        return response
    #    except Exception as e:
    #        log_message(f'No se pudo preguntar al nodo {self.id} si es estable Error:{e} \n {traceback.format_exc()}',func=self.check_predecessors_stability)
    #        return False
    #def check_in_election(self)->bool:
    #    """
    #    Chequea si yo estoy en elección, el lider toma la iniciativa
#
    #    Returns:
    #        bool: _description_
    #    """
    #    try:
    #        response:bool=self._send_data(op=CHECK_IN_ELECTION)
    #        if not isinstance(response,bool):
    #            raise Exception(f'response debe ser bool no {type(response)} {response}')
    #        return response
    #        
    #    except Exception as e:
    #        log_message(f'Error no se le pudo preguntar al predecesor {self.id} si tiene está en eleccion Error:{e} \n {traceback.format_exc()}',func=self.check_in_election)
            
        
class Leader(ChordNode):
    
    def make_election(self):
        """Convoco hacer elecciones
        """
        log_message(f'Mandando hacer eleccion',func=self.make_election)
        with self.in_election_lock:
            self.in_election_=True
        log_message(f"Como estamos en eleccion me propongo yo de lider inicialmente")
        self.leader=self.ref
        self._send_broadcast(ELECTION,self.ref) # Enviar a todos que yo Convoco Elecciones
    
    def check_i_am_alone(self,time_=10):
        while True:
            time.sleep(time_)
            try:
                result:bool=(self.pred is None and self.succ.id==self.id)
                self.i_am_alone=result
                if not result: continue
                with self.in_election_lock:
                    self.in_election_=False
                log_message(f"Como estoy solo voy hacer yo el lider",func=self.check_i_am_alone)
                self.leader=self.ref
                
                self.i_am_leader=True
                
            except Exception as e:
                log_message(f'Error chequeando que estoy solo error{e} \n {traceback.format_exc()}',func=self.check_i_am_alone)
    
    def _check_make_election(self,time_=4):
        """Chequea que el nodo tenga que estar en eleccion si es necesario

        Args:
            time_ (int, optional): _description_. Defaults to 4.
        """
        while True:
            time.sleep(time_)
            try:
               # log_message(f'Comprobando si debo hacer una Eleccion',func=self._check_make_election)
                
                if self.in_election:# Si estoy en eleccion continue  ANTES NO ESTABA
                   # log_message(f'COmo estoy en eleccion => no hago mas elecciones',func=self._check_make_election)
                    continue
                
                if  self.pred or self.i_am_alone: 
                    
                   # log_message(f'Tengo predecesor {self.pred} o estoy solo {self.i_am_alone} no debo hacer broadcast',func=self._check_make_election)
                    
                    continue # Si Tengo buscando predecesor continuo
                self.leader=self.ref # Mi lider ahora soy yo
               # log_message(f'Ahora yo soy mi lider',func=self._check_make_election)
                #self.Is_Search_Succ=False # Se supone que entonces ahora debo hacer elecciones
              #  log_message(f'No tengo sucessor debo hacer broadcast de Election',func=self._check_make_election)
                self.make_election()# Mandar hacer eleccion
                
            except Exception as e:
                log_message(f'Error tratando de hacer Elecciones: {e} \n {traceback.format_exc()}',func=self._check_make_election)
        
   
    def broadcast_handle(self, op: int, message: tuple[int, ChordNodeReference], address: str):
        super().broadcast_handle(op, message, address)
        _,node=message
        if op==ELECTION:# Es que estan en eleccion
            log_message(f'El nodo {node.id} está haciendo eleccion',func=self.broadcast_handle)
            self.Election_handler(node)
        elif op==ELECTION_WINNER:# Es que alguien gano las elecciones
            log_message(f'El ganador de las elecciones es {node.id} y el que yo creia como lider es {self.leader.id}',func=self.broadcast_handle)
            #self.Election_handler(node)     COn esto funcionaba ante
            self.winner_handle(node) 
             
    def find_key_owner(self, key: int) -> ChordNodeReference:
        """
        Busca la el dueño de la llave Si no es estable la red espera un segundo para buscarlo

        Args:
            key (int): _description_

        Returns:
            ChordNodeReference: _description_
        """
        while not (self.is_stable and self.succ_list_ok):
            time.sleep(1) # mientras no sea estable
            log_message(f'Se mando a buscar la llave {key} pero no es estable la sit ',func=self.find_key_owner)
        
        for i in range(5):
            try:
                return super().find_key_owner(key)
            except Exception as e:
                log_message(f"No se puede recuperar el duenno del la llave {key } en el intento {i}", func=self.find_key_owner)
                time.sleep(i*2)
        
        log_message(f"Como se ha superado el maximo numero de intentos voy a devolverme a mi mismo",func=self.find_key_owner)
        return self.ref
    def data_to_print(self):
        """Para poder añadir cosas a pintar"""
        log_message(f'Mi predecesor es {self.pred.id if self.pred else None} con ip {self.pred.ip if self.pred else None} ',level='INFO')
        log_message(f'Yo soy id:{self.id},con ip:{self.ip} ',level='INFO')
        if self.succ.id == self.id:
            if self.succ.ip !=self.ip:
                log_message('El sucesor tiene igual ID pero no tiene igual ip',level='INFO')
            log_message(f'Todavia no tengo sucesor',level='INFO'),
        else:
            log_message(f'Mi sucesor es {self.succ.id if self.succ else None} con ip {self.succ.ip  if self.succ else None}',level='INFO')
        
        log_message(f'Estoy en eleccion {self.in_election}',func=self.data_to_print)
        
        log_message(f'Soy Estable {self.is_stable} ',func=self.data_to_print)
        
        log_message(f'El lider es {self.leader.id}',func=self.data_to_print)
        
        log_message(f"Soy el lider {self.i_am_leader}",func=self.data_to_print)
        
        log_message(f'La lista de sucesores es {self.succ_list}',func=self.data_to_print)
        
        log_message(f"Estoy solo {self.i_am_alone}",func=self.data_to_print)
        
        log_message(f'Se puede confiar en la lista de sucesores {self.succ_list_ok}',func=self.data_to_print)
    
    def show(self,time_:int=3, print_final:bool=True):
        """
        Show my ip and id and mi predecessor and succesors ips and ids
        """
        print(f'ENtro en print')
        """Printea quien soy yo"""
        while True:
            try:
                log_message('-'*20,level='INFO')

                self.data_to_print()# Printear los logs
                if print_final:log_message('*'*20,level='INFO') # Printea el final en este hilo


                time.sleep(time_) # Se presenta cada 10 segundos
    
            except Exception as e:
                log_message(f'Ocurrio un error {e} Printeando SHow {traceback.format_exc()}',func=self.show)
    def check_i_am_stable(self,time_=0.5):#Antes con 2 funcionaba
        """
        Chequea contantemente si estoy estable o no 

        Args:
            time_ (int, optional): _description_. Defaults to 2.
        """
        while True:
           # log_message(f'Se va a comprobar si soy estable hasta ahora soy estable {self.is_stable}',func=self.check_i_am_stable)
            time.sleep(time_)
            try:
                in_election=self.in_election
                
                        
                if in_election:
                  #  log_message(f'Como estoy en eleccion no puedo ser estable ',func=self.check_i_am_stable)
                    self.is_stable=False
                    continue
                
                if  self.i_am_alone and self.i_am_leader:# SI no tengo predecesor => estoy solo
                     #   log_message(f'Como estoy solo entonces soy estable si y solo si no estoy en elección {self.in_election}',func=self.check_i_am_stable)
                        self.is_stable=not in_election
                        continue
                is_pred_stable=self.pred.check_in_election()
              #  log_message(f"Mi predecesor es estable {is_pred_stable} el predecesor es {self.pred}",func=self.check_i_am_stable)
                is_network_stable=self.leader.check_network_stability()
              #  log_message(f"Mi lider si la red es estable {is_network_stable} el lider es {self.leader}",func=self.check_i_am_stable)
                if self.i_am_leader:#Si soy el lider digo que soy estable Si no estoy en elección y mi predecesor es estable
                  #  log_message(f'COmo soy el lider entonces compruebo si puedo ser estable',func=self.check_i_am_stable)
                    if  self.i_am_alone:# SI no tengo predecesor => estoy solo
                      #  log_message(f'Como estoy solo entonces soy estable si y solo si no estoy en elección {self.in_election}',func=self.check_i_am_stable)
                        self.is_stable=not in_election
                        continue
                    # Si no estoy solo => tengo predecesor
                    
                  #  log_message(f'Soy el lider pero no estoy solo por tanto mi predecesor es estable {is_pred_stable} y estoy en eleccion {in_election}',func=self.check_i_am_stable)
                    self.is_stable= not (is_pred_stable or in_election) # Si soy el lider y no estoy solo todo es estable si mi predecesor es estable
                    
                elif not self.i_am_alone:# Si no soy el lider tengo que ver que yo no estoy en elección ni mi predecesor y además el lider sea estable
                  #  log_message(f'Como no soy el lider compruebo si la red es estable {is_network_stable}, Estoy en eleccion {in_election} mi predecesor esta en eleccion {is_pred_stable}',func=self.check_i_am_stable)
                    
                    is_stable=(not (in_election or is_pred_stable)) and is_network_stable
                    self.is_stable=is_stable #if isinstance(is_stable,bool) else False
                    log_message(f'Ahora soy estable  {self.is_stable}',func=self.check_i_am_stable)
                else:
                    self.is_stable= not self.in_election
            except Exception as e:
                log_message(f'Error en chequear si soy un nodo estable Error:{e}  {traceback.format_exc()}',func=self.is_stable)
                self.is_stable=False # Si hay error => No es estable
                time.sleep(4)
                
    def start_threads(self):
        super().start_threads()
        threading.Thread(target=self._check_make_election,daemon=True).start()# Comprobar si debo hacer eleccion o no
        threading.Thread(target=self.check_election_valid,daemon=True).start()# Comprobar que estoy en eleccion
        threading.Thread(target=self.check_i_am_alone,daemon=True).start()#Chequea si estoy solo
        #threading.Thread(target=self.show,daemon=True).start()
        threading.Thread(target=self.check_i_am_stable,daemon=True).start()# Chequeo constantemente si soy un nodo estable
        threading.Thread(target=self.check_succ_list,daemon=True).start() # Chequeo de que la lista de sucesores este actualizada
        threading.Thread(target=self.check_correct_leader,daemon=True).start()#Chequeo que cuando no esté en elección mi lider y el de atras coincidan
    
    
    
    def handle_request(self, data, option:int, a)->bytes:
        if option==CHECK_IN_ELECTION: # Se quiere comprobar que se está en elección
           # log_message(F"Se quiere saber la opcion {CHECK_IN_ELECTION} CHECK_IN_ELECTION ",func=self.handle_request)
            r=self._check_sub_ring_in_election()
            b=wire.dumps(r)
           # log_message(F"La respuesta  la opcion {CHECK_IN_ELECTION} CHECK_IN_ELECTION  es {r} en bytes {b}",func=self.handle_request)
            return b
        if option==CHECK_NETWORK_STABILITY:# Esto solo lo responde el lider, Responde si su predecesor no esta en eleccion ni el tampoco
          #  log_message(F"Se quiere saber la opcion {CHECK_NETWORK_STABILITY} CHECK_NETWORK_STABILITY ",func=self.handle_request)
            r=self._check_network_stability()
            b=wire.dumps(r)
          #  log_message(F"La respuesta  la opcion {CHECK_NETWORK_STABILITY} CHECK_NETWORK_STABILITY  es {r} en bytes {b}",func=self.handle_request)
            return b # Retorna True si la red es estable False si no lo es
        if option==GET_LEADER:# Quiere que devuelvas el lider
          #  log_message(F"Se quiere saber la opcion {GET_LEADER} GET_LEADER ",func=self.handle_request)
            r=self.leader
            b=wire.dumps(r)
          #  log_message(F"La respuesta  la opcion {GET_LEADER} GET_LEADER  es {r} en bytes {b}",func=self.handle_request)
            return b
        return super().handle_request(data,option,a)
    
    def _check_network_stability(self)->bool:
        """
        SI soy el lider retorno True si mi predecesor

        Returns:
            bool: _description_
        """
        try:
            if not self.i_am_leader:
               # log_message(f'Me mandaron a preguntar si la red es estable pero yo no soy el lider {self.leader} yo soy el lider {self.i_am_leader}',func=self._check_network_stability)
                return False
            return self.is_stable
        except Exception as e:
            log_message(f'Ocurrio un error Tratando de saber si la red es estable el lider  es {self.leader} yo soy el lider {self.i_am_leader} Error:{e} \n {traceback.format_exc()}',func=self._check_network_stability)
            return False 
            
    def _check_sub_ring_in_election(self)->bool:
        """
        Devuelve si mis predecesores y yo estamos en eleccion True: Yo o mi Predecesor estamos en elección
        False: Si Yo y mi predecesor no estamos en eleccion
        Si soy el lider solo depende si estoy en eleccion: True Si estoy en elección 
        False : Si no estoy en eleccion

        Returns:
            bool: _description_
        """
        try:
            if self.i_am_leader: #SI soy el lider solo depende de que yo no este en elección
                return  self.in_election
          #  log_message(f"Aca compruebo si el pred esta en eleccion mi lider es {self.leader}",func=self._check_make_election)
            leader_ping= self.leader.ping()
          #  log_message(f"Se le hizo ping al lider y dio {leader_ping}",func=self._check_sub_ring_in_election)
            
            if not leader_ping:# Comprobar que exista un lider sino en caso de dos nodos se satura la red 
                log_message(f"Como no hay lider elegido dibgo que la subred esta en eleccion esta vivo el lider {leader_ping}",func=self._check_sub_ring_in_election)
                return True
            
            return self.in_election or self.pred.check_in_election()
        except Exception as e:
            time_=3
            log_message(f'Ocurrio un error tratando de comprobar si el subanillo esta en eleccion Error:{e} \n {traceback.format_exc()}',func=self._check_sub_ring_in_election)
            #time.sleep(time_) # Esto se añadio ahora antes funcionaba sin ello
            #log_message(f"Sali del tiempo de espera {time_} por el Error:{e} ",func=self._check_sub_ring_in_election)
            return True # Si ocurre un error devuelvo True

    
    
    def __init__(self, ip: str, port: int = 8001, m: int = 160,succ_lis_count:int=2):
        super().__init__(ip, port, m)
        self.leader_:ChordNodeReference=self.ref
        self.leader_lock:threading.RLock=threading.RLock()#Lock para conocer quien es el lider
        self.i_am_leader_:bool=True
        self.i_am_leader_lock:threading.RLock=threading.RLock()#Lock para conocer si soy el lider
        self.in_election_:bool=True
        """
        True si estoy en eleccion False si no lo estoy
        """
        self.in_election_lock:threading.RLock=threading.RLock()
        self.i_am_alone_:bool=False # EMpiezo pensando que no para hacer descubrimiento
        self.i_am_alone_lock:threading.RLock=threading.RLock()
        self.is_stable_:bool=False
        """Dicta si estoy estable la red o no"""
        
        self.is_stable_lock:threading.RLock=threading.RLock()
        
        
        
        self.succ_list_count_:int=succ_lis_count
        """
        Dice cuantos es la lista de sucesores
        """
        self.succ_list_:list[ChordNodeReference]=[self.ref]*self.succ_list_count_
        """
        Dice mi lista de sucesores para la posterior replicación
        """
        self.succ_list_lock:threading.RLock=threading.RLock()
        """
        Lock para la lista de sucesores
        """
        self.succ_list_ok_:bool=False 
        """
        Dice si está o no actualizado la lista de sucesores
        """
        self.succ_list_ok_lock:threading.RLock=threading.RLock()        
        

        
        #Threads
    
        #self.start_threads()
        
    @property 
    def succ_list_ok(self)->bool:
        """
        Retonar si está actualizado o no la lista de sucesores

        Returns:
            bool: _description_
        """
        with self.succ_list_ok_lock:
            return self.succ_list_ok_
        
    @succ_list_ok.setter
    def succ_list_ok(self,value:bool):
        if not isinstance(value,bool):
            raise Exception(f'Value debe de ser de tipo bool no de tipo: {type(value)} value: {value}' )
        with self.succ_list_ok_lock:
            self.succ_list_ok_=value
        
    @property 
    def in_election(self)->bool:
        """Retorna con seguridad entre hilos si se está o no en eleccion

        Raises:
         
        Returns:
            bool: _description_
        """
        with self.in_election_lock:
            return self.in_election_
        
    @property 
    def succ_list(self)->list[ChordNodeReference]:
        """
        Da la lista de sucesores en vista a la replicación

        Returns:
            list[ChordNodeReference]: _description_
        """
        with self.succ_list_lock:
            return self.succ_list_ 
        
    @succ_list.setter
    def succ_list(self,value:list[ChordNodeReference]):
        if not isinstance(value,list) or not all(isinstance(item, ChordNodeReference) for item in value):
            log_message(f'Value no es una lista de ChordNodeReference para la lista de succesores',func=self.succ_list)
            raise Exception(f'Value no es una lista de ChordNodeReference para la lista de succesores')
        with self.succ_list_lock:
            self.succ_list_=value
            
        
    @property
    def is_stable(self)->bool:
        """
        Dice si estoy estable o no => que me aseguré que ningun nodo esta en elecciones
        Seguro ante hilos
        Raises:
            
        Returns:
            _type_: _description_
        """
        with self.is_stable_lock:
            if self.in_election:
                self.is_stable_=False
            return self.is_stable_
    
    @is_stable.setter
    def is_stable(self,value:bool):
        if not isinstance(value,bool):
            log_message(f'Error al setear is estable, is estable es bool, value es {type(value)} {value}',func='is_stable')
            raise Exception(f'Error al setear is estable, is estable es bool, value es {type(value)} {value}')
        with self.is_stable_lock:
            self.is_stable_=value
        
   
    @property 
    def i_am_alone(self)->bool:
        """
        Dice True si estoy Solo False si no 
        Es seguro ante hilos

        Returns:
            bool: _description_
        """
        with self.i_am_alone_lock:
            return self.i_am_alone_
    @i_am_alone.setter
    def i_am_alone(self,value):
        if not isinstance(value,bool):
            raise Exception(f'Value es de tipo {type(value)} no bool {value} ')
        with self.i_am_alone_lock:
            self.i_am_alone_=value 
    @property
    def leader(self):
        """
        Dice con seguridad de hilos quien es el lider

        Returns:
            _type_: _description_
        """
        with self.leader_lock:
            return self.leader_
        
    @leader.setter
    def leader(self,value):
        if not isinstance(value,ChordNodeReference):
            self.leader_=self.ref
            log_message(f'value:{value} no es de tipo ChordNodeReference es de tipo:{type(value)}',func="self.leader")
            raise Exception(f'value:{value} no es de tipo ChordNodeReference es de tipo:{type(value)}') 
        with self.leader_lock:
            self.leader_=value  
    
    @property
    def i_am_leader(self):
        """
        Dice si yo soy el lider con seguridad de hilos
        No tiene setter
        Returns:
            _type_: _description_
        """
        with self.i_am_leader_lock:
            self.i_am_leader_=self.leader==self.ref
            return self.i_am_leader_
    
    @i_am_leader.setter
    def i_am_leader(self,value):
        if not isinstance(value,bool):
            raise Exception(f'Value es de tipo {type(value)} no de tipo bool value:{value}')
        self.i_am_leader_=value
    
    
    
    def check_election_valid(self,time_:float=0.5,wait_election_time:float=10): # Funcionaba ok con esto time_5   wait_election_time_=10
        """
        Chequea si estoy en eleccion para terminarla 
       
    

        Args:
            time_ (float, optional): cada cuanto chequea. Defaults to 0.5.
            wait_election_time (float, optional): cuanto tiempo se da despues que se sabe que se esta en eleccion. Defaults to 10.
        """
        while True: # Compruebo si estoy en eleccion
            time.sleep(time_)
            try:
                log_message(f'Chequeando si estoy en eleccion',func=self.check_election_valid)                   
                with self.in_election_lock:# Desbloqueando
                     
                    log_message(f'Comprobando si estoy en eleccion {self.in_election_}')
                    if  not self.in_election_:
                        log_message(f'No estoy en eleccion',func=self.check_election_valid)
                        continue
                    # Estoy en eleccion
                    time.sleep(wait_election_time)
                    self.in_election_=False 
                    log_message(f'Terminada la elección mi lider es {self.leader}',func=self.check_election_valid) 
                    if self.leader.id == self.id  :  # Es que soy el lider, mandar confirmación
                        log_message(f'Yo soy el lider por tanto mando a confirmar',func=self.check_election_valid)
                        self._send_broadcast(op=ELECTION_WINNER,data=self.leader) #Soy el ganador 
                        log_message(f'Enviado el mensaje de soy el lider',func=self.check_election_valid)
                        #Esperar y pedirle a mi predecesor que me rellene una lista con los nodos que tiene 
                                      
            except Exception as e:
                log_message(f'Error chequeando si hay eleccion {e} \n {traceback.format_exc()}',func=self.check_election_valid)
    def check_correct_leader(self,time_:float=1):# Antes 10
        """Comprobar que el lider este sincronizado correctamente en toda la red"""
        while True:
            time.sleep(time_)
            try:
              #  log_message(f"Comprobando el lider correcto",func=self.check_correct_leader)
                if self.in_election:
                  #  log_message(f"Como estoy en eleccion espero",func=self.check_correct_leader)
                    continue #Si estoy en eleccion pregunto cuando no esté
                if self.i_am_alone or self.pred is None:
                  #  log_message(f"Como estoy solo continuo ",func=self.check_correct_leader)
                    continue
                
                
              #  log_message(f"Voy a mandar hacer ping al supuesto lider {self.leader}",func=self.check_correct_leader)
                leader_ping=self.leader.ping()
              #  log_message(f"Lider actual {self.leader} ping {leader_ping}",func=self.check_correct_leader)
                if  not leader_ping:
                  #  log_message(f"COmo el lider {self.leader} no está vivo convoco elecciones",func=self.check_correct_leader)
                    self.make_election()
                    continue
                
                
                if self.pred.check_in_election():
                 #   log_message(f"Como mi predecesor esta en eleccion continuo",func=self.check_correct_leader)
                    continue
                pred_leader=self.pred.leader
                
                if self.leader!=pred_leader :
                  #  log_message(f"Como el lider del predecesor es {pred_leader} y el mio es {self.leader} mando hacer eleccion",func=self.check_correct_leader)
                    self.make_election()
                    continue
            except Exception as e:
                log_message(f"Ocurrio un error tratando de ver si es el mismo lider de mi pred que el mio Error{e}\n {traceback.format_exc()}",func=self.check_correct_leader)
            
        
        
    def _get_k_succ(self,k:int)->list[ChordNodeReference]:
        """
        Dado el factor k devuelve una lista con las referencias a los k sucesores

        Args:
            k (int): _description_

        Returns:
            list[ChordNodeReference]: _description_
        """
        succ:ChordNodeReference=self.succ # Pongo primero a mi sucesor
        succ_list:list[ChordNodeReference]=self.succ_list # Capto la anterior primero
        for i in range(k): # Iterar por la cant de nodos que tenemos 
            succ_list[i]=succ
            succ=succ.succ # Ahora el sucesor es el sucesor de mi sucesor
        return succ_list
    
    def check_succ_list(self,time_:int=0.1):
        check=True # Dice si hay que chequear o no la lista de sucesores
        while True:
            time.sleep(time_)
            try:

                if self.in_election or not self.is_stable:
                    check=True # Si estoy en eleccion cuando deje de estarlo tengo que chequear
                    self.succ_list_ok=False # No se debe mirar en la lista de sucesores
                
                if  self.in_election or not check:# Si está en elecciones o no hay que chequear mejor que vuelva a preguntar
                    continue 
                
                if not self.is_stable:# Si no se está estable esperar a estar estable
                    continue
                #Esto funcionaba
                #succ:ChordNodeReference=self.succ # Pongo primero a mi sucesor
                #succ_list:list[ChordNodeReference]=self.succ_list # Capto la anterior primero
                #for i in range(self.succ_list_count_): # Iterar por la cant de nodos que tenemos 
                #    succ_list[i]=succ
                #    succ=succ.succ # Ahora el sucesor es el sucesor de mi sucesor
                
                succ_list:list[ChordNodeReference]=self._get_k_succ(self.succ_list_count_)
                if not self.in_election and self.is_stable: #
                    self.succ_list=succ_list
                    self.succ_list_ok=True # Se puede volver a confiar en la lista de sucesores
                    #check=False
            except Exception as e:
                log_message(f'Ocurrio un error actualizando la lista de sucesores {e} \n {traceback.format_exc()}',func=self.check_succ_list)  

    
    def winner_handle(self,winner_node:ChordNodeReference):
        """Comprueba el ganador de lider 
            Si el lider ganador es menor que el que tenia propuesto lo acepto
            Si es mayor que el propuesto mando broadcast de proponerme de lider

        Args:
            winner_node (ChordNodeReference): _description_
        """
        log_message(f'EL ganador de las elecciones fue {winner_node.id}',func=self.winner_handle)
        if self.id<winner_node.id:
            log_message(f'El id del ganador de las elecciones es mayor que el mio, id_ganador{winner_node.id} mi id {self.id}',func=self.winner_handle)
            self.make_election()
            return
        if self.leader.id<winner_node.id:
            log_message(f'El id del nodo ganador es{winner_node.id} y mi lider propuesto es {self.leader.id}',func=self.winner_handle)
            self.make_election()
            return 
        self.leader=winner_node
        with self.in_election_lock:
            self.in_election_=False # Ya no estoy en elecciones
        
    def Election_handler(self,node_propose:ChordNodeReference):
        """
        Maneja las propuestas de ser el lider 

        Args:
            node_propose (ChordNodeReference): _description_
        """
        
        with self.in_election_lock:
            if not self.in_election_:# Si no estaba en eleccion ahora estoy en eleccion
                self.in_election_=True
                if self.pred and self.pred.id<self.id: # Si tengo predecesor momentaneamente este es mi lider
                    self.leader=self.pred
                else: # Si no tengo predecesor voy a proponerme de lider
                    #self.leader=self.ref
                    self.make_election()
        if node_propose.id<self.leader.id:# Si el nodo que se propuso es menor que el nodo que tengo como lider
            self.leader=node_propose # Actualizo mi lider
            log_message(f'Mi nuevo lider es {self.leader.id}',func=self.Election_handler)
        
    
  
    
if __name__ == "__main__":
    print("Hello from Lider node")
    ip = socket.gethostbyname(socket.gethostname())
    node = Leader(ip,m=3,succ_lis_count=2)
    #node.start_threads()#Iniciar los nodos
    node.start_node() # Iniciar el pipeline
    while True:
        pass


        
        
    
    
    
        