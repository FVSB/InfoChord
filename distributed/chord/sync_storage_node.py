from infochord_protocol import codec as wire
from chord.storage_node import *


#app = Flask(__name__)
#app.logger.disabled = (
#    True  # Desactivar el  logguer de flask para que no haya conflicto con el mio
#)
#log = logging.getLogger("werkzeug")
#log.disabled = True  # Desactivar los otros posibles logguers que no sea el mio


class SyncStoreNode(StoreNode):
    
    
    
    def handle_request(self, data, option: int, a) -> bytes:
        if option==CAN_UPDATE_DATA: 
            return obj_to_bytes(self.is_sync_data) # Retorna si esta o no sincronizada la data
        
        return super().handle_request(data, option, a)
    def __init__(self, ip: str, port: int = 8001, flask_port: int = 8000, m: int = 160):
        super().__init__(ip, port, flask_port, m)
        self.is_sync_data_: bool = False
        """
        True Si la data esta sincronizada => que ya despues de la ultima eleccion
        los nodos responsables de cada archivo se hicieron cargo
        """
        self.is_sync_data_lock_: threading.RLock = threading.RLock()
        """
        Lock para saber si la data esta sincronizada o no
        """
        self.can_other_sync_data_with_me_: bool = False
        """
        True si en la resincronización puedo recibir data
        False si todavia no he hecho no persistente mis datos
        """
        self.can_other_sync_data_with_me_lock: threading.RLock = threading.RLock()
        """
        lock para saber si puedo recibir data de otros
        """
        
        
        

    def data_to_print(self):
        super().data_to_print()
        log_message(
            f"Los datos están sincronizados {self.is_sync_data}", func=self.show
        )
        log_message(
            f"Se pueden sincronizar los datos {self.can_other_sync_data_with_me}",
            func=self.data_to_print,
        )
    
    @property
    def can_other_sync_data_with_me(self):
        """
         True si en la resincronización puedo recibir data
        False si todavia no he hecho no persistente mis datos
        Es seguro ante hilos
        Returns:
            _type_: _description_
        """
        with self.can_other_sync_data_with_me_lock:
            return self.can_other_sync_data_with_me_

    @can_other_sync_data_with_me.setter
    def can_other_sync_data_with_me(self, value: bool):
        if not isinstance(value, bool):
            raise Exception(
                f"Se esperaba que value fuera Bool no {type(value)} {value}"
            )
        with self.can_other_sync_data_with_me_lock:
            self.can_other_sync_data_with_me_ = value

    @property
    def is_sync_data(self) -> bool:
        """
        Retorna de forma segura entre hilos
        Si la data mia esta sincronizada True
        Si mi data esta sincronizanda False
        Si no soy estable en ese momento False

        Returns:
            bool: _description_
        """
        with self.is_sync_data_lock_:
            if not self.is_stable:
                log_message(f'Se pregunto si la data está sincronizada {self.is_sync_data_} pero la red no es estable',func="self.is_sync_data")
                self.is_sync_data_=False
            return self.is_sync_data_

    @is_sync_data.setter
    def is_sync_data(self, value):
        """
        Setea con seguridad en hilos los valores de value

        Args:
            value (_type_): _description_

        Raises:
            Exception: _description_
        """
        if not isinstance(value, bool):
            raise Exception(f"Value tiene que ser bool no {type(value)} {value}")
        with self.is_sync_data_lock_:
            self.is_sync_data_ = value

    def start_threads(self):
        super().start_threads()
        threading.Thread(
            target=self.check_need_sync_store_data, daemon=True
        ).start()  # Está revisando si es necesario sincronizar con la red la data
        threading.Thread(
            target=self.check_can_other_sync_data_with_me, daemon=True
        ).start()  # Chequea si en caso ser inestable puede insertar valores

    def setup_routes(self):
        super().setup_routes()
        app.add_url_rule(
            "/sync_keys_from_others",
            view_func=self.sync_keys_from_others,
            methods=["POST"],
        )  # Metodo que recibe los documentos que ahora le pertenecen en la resincronización
        
        app.add_url_rule("/can_recive_update_documents",view_func=self.can_recive_update_documents,
            methods=["GET"]) # Saber si puedo o no recibir documentos como resincronización
        
        
        app.add_url_rule(
            "/re_update_document_like_replica_after_sync",
            view_func=self.re_update_document_like_replica_after_sync,
            methods=["POST"]
        )# Este endpoint es para resincronizar la data y que no se sobrescriban mal los datos
        
        ###########################
        #                         #
        #       Endpoints         #
        #                         #
        ###########################
        
    #Endpoint para que llame desde los nuevos dueños para que no haya sobreescritura defectuosa    
    def re_update_document_like_replica_after_sync(self):
        """
        Endpoint para cuando se resincronize la red 
        """
        try:
            addr_from = request.remote_addr
            log_message(
                f"Se a mandado actualizar un archivo como replica que envio el addr: {addr_from} ",
                func=self.re_update_document_like_replica_after_sync,
            )
            
            
            
            data = self.get_data_from_request()  # Retornar los bytes con la data
            if data is None:  # Es que no se envió nada
                # Retornar error de no file
                log_message(
                    f"La data no puede ser null", func=self.get_data_from_request
                )
                return (
                    jsonify({"message": 'Bad Request: Parámetro "param" requerido'}),
                    HTTPStatus.BAD_REQUEST,
                )
                
            node, new_doc = wire.loads(data)
            new_doc: Document = new_doc
            node: ChordNodeReference = node
            doc_id = new_doc.id
            
            if not db.has_document(doc_id):
                log_message(f"No se tenia el documento {new_doc.title} , id: {doc_id} en la db por tanto se va a añadir ",func=self.re_update_document_like_replica_after_sync)
                db.insert_document(
                    new_doc, node.id, False
                )  # Se añade en la base de datos y decimos que ahora no es persistente, esperamos confirmación
                log_message(
                    f"Se inserto correctamente el documento {new_doc.id} que es dueño el nodo {node.id}",
                    func=self.re_update_document_like_replica_after_sync,
                )
                guid = self.data_replicate_gestor.add_document_to_the_queue(
                    new_doc, self._delete_document_replica_if_no_check_response
                )  # Añadir al gestor de eventos por si no es persistente que lo elimine

                log_message(
                    f"Listo para enviar respuesta al nodo {addr_from} del documento {doc_id} con guid {guid}",
                    func=self.re_update_document_like_replica_after_sync,
                )
                
                return Response(
                    wire.dumps((SAVE_DOC_WAITING_OK, guid)),
                    status=HTTPStatus.OK,
                )
            else: # Si está el documento en la db
                 # Tomar el documento ahora
                old_doc = db.get_document_by_id(doc_id)  # Tomar el nodo
                if old_doc is None:
                    raise Exception(
                        f"El documento con id {doc_id} no está en la db y deberia estar"
                    )

                
                if not old_doc.record.can_update(new_doc.record):
                    log_message(
                        f"El documento {doc_id} a update es mas viejo {new_doc.record} que el que se tenia {old_doc.record}",
                        func=self.re_update_document_like_replica_after_sync,
                    )
                    return Response(
                        wire.dumps((ERROR_THIS_IS_NOT_THE_LASTED_VERSION, doc_id)),
                        HTTPStatus.OK,
                    )
                old_owner = db.get_node_id_owner_by_doc_id(
                    doc_id
                )  # dueño de documento antes del update

                if not db.update_document(  # Actualizar el documento
                    doc_id, new_doc, node.id, True
                ):  # SI no se completo es pq no existia el documento como fila
                    raise Exception(
                        f"El documento con id {doc_id} no está en la db y deberia estar"
                    )
                guid = self.data_replicate_gestor.update_document(
                    new_doc, old_doc, old_owner, self._revoke_update_actions, 10
                )

                log_message(
                    f"Se guardo exitosamente el documento {doc_id} dueño {node.id} event {guid}",
                    func=self.re_update_document_like_replica_after_sync,
                )

                return Response(
                    wire.dumps((SAVE_DOC_WAITING_UPDATED, guid)), status=HTTPStatus.OK
                )
                
            
        except Exception as e:
            log_message(
                f"Ocurrio un error tratando de sincronizar despues de resincronizar en la replica Error: {e} \n{traceback.format_exc()}",
                func=self.re_update_document_like_replica_after_sync,
            )
    

    # Endpoint can_recive_update_documents
    def can_recive_update_documents(self):
        """
        Endpoints que dice si se puede recibir o no documentos
        True si es que Estoy con can_other_sync_data_with_me En true
        Sino espero 30 vueltas preguntando sino Lanzo error
        """
        try:
            addr_from = request.remote_addr
            time_ = 1
            for i in range(30):
                try:
                    time.sleep(i)
                    if not self.can_other_sync_data_with_me:
                        log_message(
                            f"En la iteración {i} no se a podido completar el pedido de {addr_from}",
                            func=self.can_recive_update_documents,
                        )
                        continue

                    log_message(
                        f"Se puede sincronizar los datos en la iteración {i} preguntado por el addr{ addr_from}",
                        func=self.can_recive_update_documents,
                    )
                    return Response("Puede sincronizar", status=HTTPStatus.OK)

                except Exception as e:
                    log_message(
                        f"Ocurrio un error tratando de responder si puedo recibir documentos de resincronización en la iteracion {i+1} Error:{e} \n {traceback.format_exc()}",
                        func=self.can_recive_update_documents,
                    )
                
            log_message(
                f"No se pudo completar en ninguna iteración la respuesta de si pueden sincronizar conmigo para el addr {addr_from} ",
                func=self.can_recive_update_documents,
            
            )
            return Response(
                "Error no se ha podido sincronizar", status=HTTPStatus.FORBIDDEN
            )

        except Exception as e:
            log_message(
                f"Ocurrio un error tratando de responder si puedo recibir documentos de resincronización de forma general Error:{e} \n {traceback.format_exc()}",
                func=self.can_recive_update_documents,
            )
            raise Exception(e)

    # EndPoint sync_keys_from_others
    def sync_keys_from_others(self):
        """
        Endpoint para en la resincronizacion recibir los documentos que ahora son mios

        """
        try:

            addr_from = request.remote_addr

            log_message(
                f"Se ha mandado a reinsertar un documento siendo yo el dueño actual de {addr_from} ",
                func=self.sync_keys_from_others,
            )

            data = self.get_data_from_request()  # Document
            if data is None:
                log_message(f"La data es None", func=self.sync_keys_from_others)

            tup: tuple[ChordNodeReference, Document] = wire.loads(data)
            node, document = tup
            doc_id = document.id
            log_message(f"El nodo {node} ha mandado a que me haga cargo del documento {document.title} texto: {document.text}",func=self.sync_keys_from_others)
            # Verificar si ya lo tengo en la db
            if db.has_document(
                doc_id
            ):  # Si esta en la base de datos comprobar que este es mas reciente o igual
                old_doc = db.get_document_by_id(doc_id)
                if not old_doc.record.can_update(
                    document.record
                ):  # Devolver que me ocupe de el
                    log_message(
                        f"El documento con id {doc_id} que se a enviado desde {node.id} es mas viejo: {document.record} que el que tengo en la db:{old_doc.record}",
                        func=self.sync_keys_from_others,
                    )
                    return (
                        jsonify(
                            {
                                f"message": f"El documento con id {doc_id} que se a enviado desde {node.id} es mas viejo: {document.record} que el que tengo en la db:{old_doc.record}"
                            }
                        ),
                        HTTPStatus.OK,
                    )
                ok_, nodes_list = self.Crud_action(
                    document, "save_document_like_replica", CrudCode.ReInsertSelf
                )
                if not ok_:
                    log_message(
                        f"No se pudo reinsertar correctamente el documento {doc_id} que viene del nodo {node.id} {addr_from} Se pudo insertar en {nodes_list}",
                        func=self.sync_keys_from_others,
                    )
                    return (
                        jsonify(
                            {
                                "message": f"No se pudo reinsertar correctamente el documento {doc_id} que viene del nodo {node.id} {addr_from} Se pudo insertar en {nodes_list}"
                            }
                        ),
                        HTTPStatus.EXPECTATION_FAILED,
                    )

                log_message(
                    f"Se pudo reinsertar correctamente el documento {doc_id} que viene del nodo {node.id} {addr_from} Se pudo insertar en {nodes_list}",
                    func=self.sync_keys_from_others,
                )
                return (
                    jsonify(
                        {
                            f"message": f"Se pudo reinsertar correctamente el documento {doc_id} que viene del nodo {node.id} {addr_from} Se pudo insertar en {nodes_list}"
                        }
                    ),
                    HTTPStatus.OK,
                )
            else:  # Si no esta el documento => que hay que insertarlo desde Cero
                log_message(
                    f"El documento {doc_id} enviado desde {node.id} {addr_from} No existe actualmente en la db => hay que insertarlo por primera vez",
                    func=self.sync_keys_from_others,
                )
                ok_, nodes_list = self.Crud_action(
                    document, "save_document_like_replica", CrudCode.Insert
                )
                if not ok_:  # Si no se completo satisfactoriamente
                    log_message(
                        f"No se pudo reinsertar correctamente el documento el cual se iba a insertar por primera vez {doc_id} que viene del nodo {node.id} {addr_from} Se pudo insertar en {nodes_list}",
                        func=self.sync_keys_from_others,
                    )
                    return (
                        jsonify(
                            {
                                "message": f"No se pudo reinsertar correctamente el documento el cual se iba a insertar por primera vez {doc_id} que viene del nodo {node.id} {addr_from} Se pudo insertar en {nodes_list}"
                            }
                        ),
                        HTTPStatus.EXPECTATION_FAILED,
                    )

                log_message(
                    f"Se pudo reinsertar correctamente el documento el cual se inserta acá por primera vez id: {doc_id} que viene del nodo {node.id} {addr_from} Se pudo insertar en {nodes_list}",
                    func=self.sync_keys_from_others,
                )
                return (
                    jsonify(
                        {
                            f"message": f"Se pudo reinsertar correctamente el documento el cual se inserta acá por primera vez id: {doc_id} que viene del nodo {node.id} {addr_from} Se pudo insertar en {nodes_list}"
                        }
                    ),
                    HTTPStatus.OK,
                )
        except Exception as e:
            log_message(
                f"Ocurrio un error en el endopoint de recibir los documentos en la resincronización  Error:{e} {traceback.format_exc()}",
                func=self.sync_keys_from_others,
            )
            raise Exception(e)

    def get_all_keys_mine_and_the_other(self) -> tuple[list[int], list[int]]:
        """
        Toma de la db todas las llaves, hace todos las filas como No Persistente y devuelve una tupla que tiene (Lista de las llaves que me pertenecen ahora, Lista de llaves que no Me pertenecen )

        Returns:
            tuple[list[int], list[int]]: (My_Keys,Other_Kyes)
        """

        log_message(
            f"Se va a revisar ahora cuales son las llaves que me pertenecen y cuales tengo que reinsertar"
        )
        my_keys: list[int] = []  # Las llaves que me pertenecen ahora
        other_owners_keys: list[int] = []  # Las llaves que le pertenecen a otro ahora
        # Tomar todas las llaves
        keys_lis: list[int] = db.get_all_docs_keys()
        # Hacer no persistente todo
        db.make_false_persist_all_rows()

        if self.i_am_alone:  # Es pq soy un unico nodo
            log_message(
                f"Estoy solo => que todas las llaves en mi db son mias",
                func=self.get_all_keys_mine_and_the_other,
            )

            return (keys_lis, [])  # Todas las llaves son mias

        for key in keys_lis:
            if self._inbetween(key, self.pred.id, self.id):  # Cuales son mis llaves
                my_keys.append(key)
            else:  # LLaves que son dueño otro nodo
                other_owners_keys.append(key)
        return (my_keys, other_owners_keys)

    def reinsert_my_keys(self, my_keys: list[int]) -> bool:
        # Mandar a reinsertar cada llave
        try:
            log_message(f'Tengo que reinsertar como mias las sgts llaves {my_keys}',func=self.reinsert_my_keys)
            with self.succ_list_lock:  # Se bloquea que ningun otro hilo pueda modificarlo
                for key in my_keys:
                    try:

                        document = db.get_document_by_id(key)
                        log_message(f'Se va a reinsertar en mis replicas el documento {document.id} {document.record} {document.text}',func=self.reinsert_my_keys)
                        ok_, replica = self.Crud_action(
                            document=document,
                          # sub_url= "save_document_like_replica",
                           sub_url="re_update_document_like_replica_after_sync",
                           crud_code= CrudCode.ReInsertSelf,
                        )  # El va a reinsertar el documento
                        a = self.succ_list
                        a += [self.ref]
                        if not (
                            ok_ and is_equal_list(a, replica)
                        ):  # Si hubo algun error haciendo la inserccion hubo un error por tanto se tiene que volver otra vez la operacion
                            log_message(
                                f"No se pudo reinsertar correctamente la llave {key} se tenia que reinsertar en {self.succ_list} y se reinserto en {replica}",
                                func=self.reinsert_my_keys,
                            )
                            return False
                        log_message(f'Se pudo reinsertar correctamenete el {document.id} {document.record} {document.text}',func=self.reinsert_my_keys)

                    except Exception as e:
                        log_message(
                            f"Ocurrio un error reinsertando las llave como mia {key }  Error:{e} \n {traceback.format_exc()}",
                            func=self.reinsert_my_keys,
                        )
                        return False
                    log_message(f'Se reinsertaron correctamente en mi las llaves {my_keys}',func=self.reinsert_my_keys)
                return True  # Se completo la reinserccion
        except Exception as e:
            log_message(f"Error reinsenrtando mis llaves", func=self.reinsert_my_keys)
            return False
    def can_send_to_others_reinsert_documents(self,node:ChordNodeReference,timeout:float=30)->bool:
        """
        
        Devuelve True o False si puedo enviar al nuevo dueño la data para que se haga cargo
        Args:
            node (ChordNodeReference): _description_
            timeout (float): tiempo maximo antes de lanzar excepcion default 30
        """
        try:
            log_message(f'El nodo {node} pregunta si está listo para yo enviarle su data que le pertenece',func=self.can_send_to_others_reinsert_documents)
            #can_recive_update_documents
            
            url = self.url_from_ip(node.ip)
            url = self.add_end_point_to_url(url,"can_recive_update_documents")

            log_message(
                f"Se va a enviar un mensaje a nodo {node.id} url:{url} para preguntarle por si ya puede recibir su nueva data ",
                func=self.send_file_to_node,
            )
            
            response=rq.get(url,timeout=timeout)
            response.raise_for_status()  # Verifica si hay errores HTTP
        
            
            if response.status_code==200:
                log_message(f'El nodo {node.id} esta listo para recibir su nueva data',func=self.can_send_to_others_reinsert_documents)
                return True
            
            log_message(f'Error: El nodo {node.id} no puede recibir su nueva data ',func=self.can_send_to_others_reinsert_documents)
            return False
        
        except rq.exceptions.Timeout as e:
            log_message(f'Ocurrio un error de timeout maximo {timeout} haciendo get al nodo {node.id} {node.ip} para saber si se puede resincronizar  ',func=self.can_send_to_others_reinsert_documents)   
            
        except Exception as e:
            log_message(f'Ocurrio un error tratando de esperar por enviar sus documentos al nodo {node}',self.can_send_to_others_reinsert_documents)
            return False
        
    
    
    
    def send_to_reinsert_others_documents(self, keys: list[id]) -> bool:
        """
        Envia a reinsertar los documentos que no son de mi propiedad, despues que tiene la aceptación si no es persistente
        el documento lo elimina

        Args:
            keys (list[id]): lista con los ids de documentos que no me pertenecen

        Returns:
            bool: True si se completo con exito  False si hubo algun problema o fallo enviar algun archivo

        """
        
        try:
            log_message(f'Se a mandar las sgts llaves a sus nuevos dueños {keys}',func=self.send_to_reinsert_others_documents)
            for key in keys:  # Iterar por las llaves

                if not self.is_stable:  # Si empece otra vez en elección retorno False
                    log_message(
                        f"Tratando de enviar la llave {key} a su dueño entramos en eleccion {self.in_election} es estable{self.is_stable}",
                        func=self.send_to_reinsert_others_documents,
                    )
                    return False
                owner = self.find_key_owner(key)  # Buscar el nodo dueño
                if (
                    owner.id == self.id
                ):  # Debe ser un error pq yo ya debo haber tomado todas mis llaves
                    log_message(
                        f"Error no puedo decir que envio a otro nodo a encargarse del documento {key} cuando yo soy el dueño {owner.id} {owner.ip}",
                        func=self.send_to_reinsert_others_documents,
                    )
                    raise Exception(
                        f"Error no puedo decir que envio a otro nodo a encargarse del documento {key} cuando yo soy el dueño {owner.id} {owner.ip}"
                    )

                document = db.get_document_by_id(key)
                if document is None:
                    log_message(
                        f"Error el documento con llave {key} es {type(document)} no puede ser None => que se elimino antes en la db ",
                        func=self.send_to_reinsert_others_documents,
                    )
                    raise Exception(
                        f"Error el documento con llave {key} es {type(document)} no puede ser None => que se elimino antes en la db "
                    )
                # Tratar de esperarr a que el pueda recibir la data
                
                if not self.can_send_to_others_reinsert_documents(owner):
                    raise Exception(f'El nodo {owner} no puede recibir su nueva data')
                
                
                
                response_: Response = self.send_file_to_node(
                    owner, "sync_keys_from_others", wire.dumps((self.ref, document))
                )
                if (
                    response_.status_code != 200
                ):  # Si no ocurrio un 200 hubo algun error lanzar exc
                    log_message(
                        f"Ocurrio un Error enviando al nodo {owner.id} {owner.ip} el documento {key} con fecha {document.record} codigo de estatus {response_.status_code}",
                        func=self.send_to_reinsert_others_documents,
                    )
                    raise Exception(
                        f"Ocurrio un Error enviando al nodo {owner.id} {owner.ip} el documento {key} con fecha {document.record} codigo de estatus {response_.status_code}"
                    )

                log_message(
                    f"El documento {key} fue correctamente enviado a su dueño {owner}",
                    func=self.send_to_reinsert_others_documents,
                )

                is_persistent = db.is_document_persistent(
                    key
                )  # Chequear si ya es persistente

                if is_persistent is None:
                    log_message(
                        f"Error revisando si el documento {document} es persistente en la db Este no existe en esta y deberia existir",
                        func=self.send_to_reinsert_others_documents,
                    )
                    raise Exception(
                        f"Error revisando si el documento {document} es persistente en la db Este no existe en esta y deberia existir"
                    )

                if (
                    not is_persistent
                ):  # => que yo no soy replica despues de la reinserción => que hay que eliminarlo
                    log_message(
                        f"El documento {key} no es persistente despues de enviarlo a su nuevo dueño {owner} por tanto => se va a  eliminar",
                        func=self.send_to_reinsert_others_documents,
                    )
                    db.delete_document_all(key)
                    log_message(
                        f"El documento {key} no es persistente despues de enviarlo a su nuevo dueño {owner} por tanto se acaba de eliminar",
                        func=self.send_to_reinsert_others_documents,
                    )

                log_message(
                    f"El documento {key} fue adecuadamente reinsertado",
                    func=self.send_to_reinsert_others_documents,
                )

            return True
        except Exception as e:
            log_message(
                f"Ocurrio un error tratando de enviar a los dueños actuales de las documentos sus respectivos documentos Error:{e} \n {traceback.format_exc()} ",
                func=self.send_to_reinsert_others_documents,
            )
            return False

    def sync_data(self, intent: int,time_:float=1):
        """
        Sincronizar mi data
        
        time_ Tiempo entre cada iteracion tiene que ser >0
        """

        for i in range(intent):
            try:
                time.sleep(time_)
                log_message(
                    f"Tratando de sincronizar la data despues de una eleccion intento {i+1}",
                    func=self.sync_data,
                )
                # Tomar las llaves que me pertenecen o no
                my_keys, other_keys = self.get_all_keys_mine_and_the_other()

                self.can_other_sync_data_with_me = True
                log_message(
                    f"Ya se puede recibir data para sincronizar", func=self.sync_data
                )
                
                # Esperar por el antecesort para sincronizar los datos
                log_message(f'Esperando por mi antecesor para sincronizar los datos',func=self.sync_data)
                if not self.can_sync_data():
                    log_message(f'No se puede mandar a sincronizar pq el antecesor no se sincronizo Soy el lider:{self.i_am_leader}',func=self.wait_to_sync_data)
                    continue

                # Reinsertar mis datos
                if not self.reinsert_my_keys(
                    my_keys
                ):  # Si no se puede reinsertar => que hay que volver a resincronizar
                    log_message(
                        f"Ocurrio un error reinsertando mis propias llaves {my_keys}",
                        func=self.sync_data,
                    )
                    continue

                if not self.send_to_reinsert_others_documents(
                   other_keys
                ):  # => Que hubo algun problema
                   log_message(
                       f"No se pudo enviar a los nuevos dueños de las llaves {other_keys} todas las llaves",
                       func=self.sync_data,
                   )
                   continue
            
                log_message(
                    f"Se completo la sincronización de la data", func=self.sync_data
                )
                return True
            except Exception as e:
                log_message(
                    f"Ocurrio un error resincronizando la data {e} \n {traceback.format_exc()}",
                    func=self.sync_data,
                )
            time.sleep(time_)
        log_message(
            f"En ninguno de los intentos se pudo sincronizar la data ",
            func=self.sync_data,
        )
        return False
    
    def can_sync_data(self)->bool:
        """
        Retorna True si ya puedo sincronizar la data
        Si soy el lider empiezo a sincronizar sino espero a que mi antecesor lo haga y este en True
        False si hubo algun error        

        Returns:
            bool: _description_
        """

        try:
            #time.sleep(30) Con esto funcionaba
            if self.i_am_leader: return True # Si soy el lider comienzo yo a sincronizar
            for i in range(180):
                time.sleep(0.5)
                if not self.is_stable:
                    log_message(f'La red no es estable por tanto voy a retornar falso',func=self.can_sync_data)
                    return False
                
                if self.pred.can_update_data(): return True
            log_message(f'El antecesor no sincronizo la data despues de los intentos se devuelve False',func=self.can_sync_data)
            
            return False
        except Exception as e:
            log_message(f'Ocurrio un problema esperando para saber si ya puedo sincronizar la data mia Error:{e} \n {traceback.format_exc()}',func=self.can_sync_data)
            return False
    def wait_to_sync_data(self,time_:float=0.5):
        """
        Una vez que se sabe que hay que sincronizar la data espera hasta que sea estable la red para mandar a sincrinizarla
        """
        
        try:
            while not (self.is_stable and self.succ_list_ok):
                time.sleep(time_)
            
            return self.sync_data(2)
                        
        except Exception as e:
            log_message(f'Ocurrion un error esperando que sea estable para sincrinizar la data, Error:{e} {traceback.format_exc()} ',func=self.wait_to_sync_data)
    def check_need_sync_store_data(self, time_: int = 0.1):
        """
        Este método chequea si se tiene que resincronizar los datos
        """
        # Si estoy en elección convoco a esto
        was_in_election = True  # Es el indicador para saber si estuve en eleccion y esperar a no estar en esta
        while True:
            try:
                time.sleep(time_)
                if (
                    was_in_election
                ) or not self.is_sync_data:  # Si estaba en eleccion, ahora no estoy en elección y la lista de sucesores esta ok o la data no está sincrinizada

                    # Mandar a resincronizar la data
                    self.is_sync_data = False
                    log_message(
                        f"Se va a enviar a sincronizar los datos",
                        func=self.check_need_sync_store_data,
                    )
                    
                    if not self.wait_to_sync_data():
                        log_message(
                            f"No se pudo sincronizar la data",
                            func=self.check_need_sync_store_data,
                        )
                        continue
                    else:  # => Se sincronizo correctamente
                        log_message(
                            f"Se sincronizaron los datos correctemente",
                            func=self.check_need_sync_store_data,
                        )
                        self.is_sync_data = True

                    was_in_election = False  # Establecer como false para que se vuelva a poder cambiar
                    # Aca poner que estoy ready en respecto a mi data
                was_in_election = (
                    self.in_election if not was_in_election else was_in_election
                )  # Actualizar si ahora estoy en elección

            except Exception as e:
                log_message(
                    f"Ocurrio un error chequeando si debo resincronizar los datos Error:{e} \n {traceback.format_exc()}",
                    func=self.check_need_sync_store_data,
                )
                # was_in_election=True # Por si acaso mandar a resincronizar

    def check_can_other_sync_data_with_me(self, time_: float = 0.1):
        """
        Chequea que cuando haya eleccion o este algo inestable en el nodo diga que no se puede sincronizar los datos

        """
        while True:
            try:
                time.sleep(time_)
                if self.in_election or not (self.is_stable and self.succ_list_ok) :
                    self.can_other_sync_data_with_me = False

            except Exception as e:
                log_message(
                    f"Ocurrio un error tratando de chequear que en caso de resincronización puedo recibir data, Error:{e} \n {traceback.format_exc()} ",
                    func=self.check_can_other_sync_data_with_me,
                )


if __name__ == "__main__":
    log_message("Hello from Sync Storage node")
    # time.sleep(10)
    ip = socket.gethostbyname(socket.gethostname())
    node = SyncStoreNode(ip, m=3)

    #node.start_threads()  # Iniciar los nodos
    node.start_node() # Iniciar el pipeline
    
    while True:
        pass
