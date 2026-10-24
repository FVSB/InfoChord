from infochord_protocol import codec as wire


from chord.distributed_data_base import *
from helper.utils import CrudCode
from helper.docs import EmbeddingDocument
from helper.embeddings import create_embedding,cosine_similarity
from helper.query import DocsClassification, QueryHandle,QueryGestor
from helper.document_gestor import DocumentProgressTracker
from typing import Callable




        
    

class DistributedSearcher(DistributedDataBase):
    def setup_routes(self):
        super().setup_routes()
        app.add_url_rule(
            "/query",
            view_func=self.query,
            methods=["GET"],
        )# Metodo para hacer una query
        app.add_url_rule(
            "/progress_document",
            view_func=self.progress_document,
            methods=["GET"],
            
        )#Funcion para conocer el progreso despues de insertar o actualizar un documento
        app.add_url_rule(
            "/process_query_handle",
            view_func=self._process_query_handle,
            methods=["POST"],
        )# Metodo para hacer una query
        
        
        
    def create_document(self,guid:str,title: str, text: str, max_value: int = 16) -> Document:
        """
        crea el embeeding document apartir del titulo y texto

        Args:
            title (str): _description_
            text (str): _description_
            max_value (int, optional): _description_. Defaults to 16.

        Returns:
            Document: _description_
        """
        log_message(f"Se llamo al metodo de create document ",func=self.create_document)
        embedding_text_list,chunks_text=self.query_gestor.create_embedding(text)
        log_message(f"Se creo correctamente el embedding del documento {title} con guid {guid}",func=self.create_document)
        self.document_tracker_gestor.update_progress(guid=guid,porcent=0.25)
        embedding_title_list,_=self.query_gestor.create_embedding(title)
        log_message(f"Se creo correctamente el embedding del titulo de {title} con guid {guid}",func=self.create_document)
        self.document_tracker_gestor.update_progress(guid=guid,porcent=0.95)
        return EmbeddingDocument(title=title,text=text,max_value=max_value,embedding_text_list=embedding_text_list,embedding_title_list=embedding_title_list,text_chunks=chunks_text)

    def _process_to_save_document(self, guid: str, name: str, doc_to_save: str, sub_url: str, crud_code: CrudCode):
        #Crear el tracker para ese documento
        log_message(f"Inicializar track para el documento {name} con guid{guid}",func=self._process_to_save_document)
        self.document_tracker_gestor.init_track(guid=guid)
        log_message(f"Se inicializo track para el documento {name} con guid{guid}",func=self._process_to_save_document)
        super()._process_to_save_document(guid, name, doc_to_save, sub_url, crud_code)
    
    def _create_and_save_document(self, guid: str, name: str, doc_to_save: str, sub_url: str, crud_code: CrudCode):
        try:
            ok_crud, nodes_save = super()._create_and_save_document(guid, name, doc_to_save, sub_url, crud_code)
        except Exception as exc:
            self.document_tracker_gestor.error_track(guid=guid, error_mg="Document processing failed; check provider and nodes")
            log_message(f"Document processing failed: {type(exc).__name__}", func=self._create_and_save_document)
            return False, []
        # Añadir esto para utilzar el track de por donde va.
        
        if ok_crud:
            self.document_tracker_gestor.end_track(guid=guid,end_msg=f"Se guardo satisfactoriamente en los nodos {nodes_save}")
            log_message(f"Se guardo correctamente el documento {name} con guid {guid} en los nodos {nodes_save}",func=self._create_and_save_document)
        else:
            self.document_tracker_gestor.error_track(guid=guid,error_mg=f"Ocurrio un error tratando de guardar {guid} se guardo en {nodes_save}")
            log_message(f"Hubo un error guardando el documento {name} con guid {guid} en los nodos {nodes_save}",func=self._create_and_save_document)
        return ok_crud,nodes_save
    def __init__(self, ip: str,query_gestor:QueryGestor, port: int = 8001, flask_port: int = 8000, m: int = 160):
        super().__init__(ip, port, flask_port, m)
        
        self.query_gestor:QueryGestor=query_gestor
        """
        Clase factory para los handles de las querys
        """
        
        self.document_tracker_gestor:DocumentProgressTracker=DocumentProgressTracker(time_to_delete=10)
        """
        Gestor que se encarga para saber como va el proceso de subir un documento
        """
        
    def return_query_helper(self,query_handle:QueryHandle):
        """
        Helper para dado un query handle envie la respuesta a mi predecesor 

        Args:
            query_handle (QueryHandle): _description_

        Returns:
            _type_: _description_
        """
        #return jsonify({"file":obj_to_bytes(query_handle)}),HTTPStatus.OK
        return Response(wire.dumps(query_handle), content_type="application/json"), HTTPStatus.OK
    
    def call_succ_to_process_query(self,query_handle:QueryHandle)->QueryHandle:
        try:
            # Llamar al sucesor y decirle lo que hay 
            response=self.send_file_to_node(node=self.succ,
                                   data=obj_to_bytes(query_handle),
                                   sub_url="process_query_handle",
                                   timeout=10
                                   )

            if response.status_code!=200:
                log_message(f"Hubo un error tratando de comunicar con el sucesor para que resolviera su parte de la query por tanto voy a finalizar query",func=self.call_succ_to_process_query)
                query_handle.db_is_not_stable()
                return query_handle
            #response_json=response.json()
            #file_content=response_json['file']
            #new_query_handle:QueryHandle=wire.loads(file_content)
            new_query_handle:QueryHandle=wire.loads(response.text)
            log_message(f"Mi sucesor me envio el query handle de {new_query_handle.guid} Es activo {new_query_handle.is_stable_response()}",func=self.call_succ_to_process_query)
            return new_query_handle
        except Exception as e:
            log_message(f"Ocurrio un error tratando de hacer que el sucesor procese la query Error:{e} \n {traceback.format_exc()}",func=self.call_succ_to_process_query)
            query_handle.db_is_not_stable()
            return query_handle
    def _process_query_handle(self):
        """
        Es un end_point
        Metodo al que llamar cuando recibo una peticion  de mi predecesor
        Si me llega a mi por mi predecesor y yo soy el dueño no lo voy a procesar

        Args:
            

        Returns:
            _type_: _description_
        """
       
        try:
            addr_from = request.remote_addr  # La direccion desde donde se envia la petición
            
            log_message(f"Se a recibido una peticion de procesar una query desde {addr_from}")
            data=self.get_data_from_request()
            
            query_handle:QueryHandle=wire.loads(data)
            
            log_message(f"Se va a procesar la query {query_handle.guid} desde la ip {addr_from}",func=self._process_query_handle)
                    
            if not self.is_db_stable():# Si la db no es estable devuelvo la query sin procesarla
                query_handle.db_is_not_stable()
                #return query_handle
                return self.return_query_helper(query_handle)
            if not self.query_gestor.can_process_this_query(query_handle):
                return self.return_query_helper(query_handle)

            #query_handle=self.pred.process_query(query_handle)
            query_handle=self.call_succ_to_process_query(query_handle=query_handle)
            if not self.is_db_stable():# Si la db no es estable devuelvo la query sin procesarla
                query_handle.db_is_not_stable()
                return self.return_query_helper(query_handle)

            #return self.resolve_query(query_handle)
            return self.return_query_helper(self.resolve_query(query_handle))
        except Exception as e:
            log_message(f"Error processing query: {type(e).__name__}", func=self._process_query_handle)
            raise Exception(e)
    def resolve_query(self,query_handle:QueryHandle)->QueryHandle:
        """
        Dada el query_handle y las posibles extensiones los añade al queryhandle

        Args:
            query_handle (QueryHandle): _description_
            posibles_extensions (list[str]): _description_

        Returns:
            QueryHandle: _description_
        """
        log_message(f"Las posibles extensiones de la query son {query_handle.posibles_extensions}",func=self.resolve_query)
        docs:list[EmbeddingDocument]=db.get_all_documents_by_extension(query_handle.posibles_extensions,self.id)
        
        for doc in docs:
            query_handle.add_document(doc)
        
        return query_handle
            
        
    
    def process_query_like_owner(self,
                                 query:str,
                                 posibles_extensions:list[str],
                                 max_results:int,
                                 min_score:float,
                                 i:int=0
                                 ):
        query_handle=self.query_gestor.make_new_query(query=query,
                                                      posibles_extensions=posibles_extensions,
                                                      min_score=min_score,
                                                      max_results=max_results
                                                      )
        if i>len(self.succ_list):# Si se ha llegado a mas de 5 respuestas fallidas se devuelve vacia la query y con que hubo un error
            
            log_message(f"Se ha superado el maximo numero de intentos en la query {query } por tanto se devuelve vacia y que no es estable",func=self.process_query_like_owner)
            query_handle.db_is_not_stable()
            return query_handle
        
        self.wait_for_stability()
        log_message(f"Se a mandado a realizar una consulta donde yo soy el dueño de la query {query}",func=self.process_query_like_owner)
        
        #query_handle=self.pred.process_query(query_handle)# Primero mando a que se procesen
        query_handle=self.call_succ_to_process_query(query_handle=query_handle)#Primero mando a mi sucesores a que lo hagan
        
        if not self.is_db_stable():# Si no es estable se anula la query
            log_message(f"Como la db es inestable aunque se halla procesado de los demas la query vuelvo a mandar a procesarla",func=self.process_query_like_owner)
            self.query_gestor.end_query(query_handle)
            return self.process_query_like_owner(query=query,
                                                 posibles_extensions=posibles_extensions,
                                                 max_results=max_results,
                                                 min_score=min_score,
                                                 i=i)
            
        if not query_handle.is_stable_response():# Si no es estable la respuesta se anula la query
            log_message(f"Se va a volver a procesar la respuesta pq la respuesta de la query {query} con guid: {query_handle.guid} en la iteracion {i}",func=self.process_query_like_owner)
            self.query_gestor.end_query(query_handle)
            return self.process_query_like_owner(query=query,
                                                 posibles_extensions=posibles_extensions,
                                                 max_results=max_results,
                                                 min_score=min_score,
                                                 i=i+1)
        query_handle=self.resolve_query(query_handle)
        return query_handle
    def query(self):# Endpoint para hacer una query
        addr_from = request.remote_addr  # La direccion desde donde se envia la petición

        
        
        log_message(
            f"Se a recibido una petición de GET para el para resolver una query desde la direccion: {addr_from}",
            func=self.query,
        )
        try:
            query:str=str(request.args.get("query",""))
            try:
                max_results = int(request.args.get("max_results", 20))
                min_score = float(request.args.get("min_score", 0))
            except ValueError:
                return jsonify(message="Invalid numeric query parameters"), 400
            posibles_extensions:list[str]=request.args.getlist("extensions")
            import math
            if not query.strip() or len(query) > 10000 or not 1 <= max_results <= 100 or not math.isfinite(min_score):
                return jsonify(message='Invalid query, max_results or min_score'), 400

            
            self.wait_for_stability()
            
            log_message(f"Se quiere realiza una query {query}  a las extensiones {posibles_extensions}",func=self.query)
            
            
            query_handle=self.process_query_like_owner(query=query,
                                                       posibles_extensions=posibles_extensions,
                                                       max_results=max_results,
                                                       min_score=min_score,
                                                       )
            if not query_handle.is_stable_response():# Si la query no pudo ser satisfecha por algun error que se reconecte
                log_message(f"La query desde {addr_from} no se pudo llevar a cabo se pide que se reconect",func=self.query)
                return jsonify({"message":"Repeat_Again"}),HTTPStatus.TOO_MANY_REQUESTS
            
            
            results=query_handle.get_results()
            log_message(f"La query fue satisfactoria del addr: {addr_from}",func=self.query)
            return jsonify({"results":results}),HTTPStatus.OK
        
        except Exception as e:
            log_message(f"A ocurrido un error en la peticion del addr: {addr_from} Error:{e} \n {traceback.format_exc()}",func=self.query)
            return jsonify({"message":"A ocurrido un error en la peticion"}),500
        

    def progress_document(self):
        """
        Endpoint para conocer el progreso de un documento
        """
        addr_from = request.remote_addr  # La direccion desde donde se envia la petición

        log_message(f"Se a recibido una petición de GET para el para conocer el progreso en guardar o actualizar un documento desde la direccion: {addr_from}",
            func=self.progress_document)
        
        try:
            guid:str=str(request.args.get("guid",""))
            if not self.document_tracker_gestor.contains_guid(guid=guid):
                return (jsonify({"message":f"El guid {guid} no se encuentra disponible"}),HTTPStatus.NOT_FOUND)
            tracker=self.document_tracker_gestor.get_progress(guid)
            
            return(jsonify({"message":tracker.message,"porcent":tracker.progress_porcent,"is_error":tracker.is_error,"is_finish":tracker.is_finish}),HTTPStatus.OK)
        except Exception as e:
            log_message(f"A ocurrido un error en la peticion del addr{addr_from} para conocer el estado de un documento Error:{e} \n {traceback.format_exc()}",func=self.progress_document)
            return jsonify({"message":"A ocurrido un error en la peticion"}),500
if __name__ == "__main__":
    log_message("Hello from Distribued Seacher node")
    ip = socket.gethostbyname(socket.gethostname())
    query_gestor=QueryGestor(func_get_embedding_list=create_embedding,func_score_embedding=cosine_similarity)
    node = DistributedSearcher(ip, m=3,query_gestor=query_gestor)
    node.start_node()  # Iniciar el pipeline

    while True:
        pass
