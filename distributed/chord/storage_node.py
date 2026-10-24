from infochord_protocol import codec as wire
from chord.chord_leader import *
from flask import Flask, request, jsonify, Response, abort, redirect, url_for
import socket
from helper.docs import *
from helper.utils import *
from helper.document_gestor import DataReplicatedGestor
import helper.db as db
from enum import Enum
from urllib.parse import urlencode
import requests as rq
from http import HTTPStatus


app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = wire.MAX_MESSAGE_BYTES


@app.before_request
def validate_wire_request():
    if request.method == "POST":
        if request.mimetype != "application/json":
            return jsonify(message="Protocol v1 requires application/json"), 415
        try:
            value = wire.loads(request.get_data())
            if request.path in ("/upload", "/update"):
                if not isinstance(value, tuple) or len(value) != 2 or not all(isinstance(x, str) for x in value):
                    raise wire.ProtocolError("Expected (title, text)")
                if not value[0].strip() or len(value[0]) > 1024 or not value[1].strip():
                    raise wire.ProtocolError("Non-empty title and text required")
            if request.path == "/delete_file" and (not isinstance(value, str) or not value.strip()):
                raise wire.ProtocolError("Non-empty title required")
        except wire.ProtocolError as exc:
            return jsonify(message=str(exc)), 400


@app.errorhandler(TimeoutError)
def operation_timed_out(_error):
    return jsonify(message="Cluster not ready before operation deadline"), 503
app.logger.disabled = (
    True  # Desactivar el  logguer de flask para que no haya conflicto con el mio
)
log = logging.getLogger("werkzeug")
log.disabled = True  # Desactivar los otros posibles logguers que no sea el mio


class StoreNode(Leader):
    """
    Tiene la logica de guardar documentos y mandar a actualizar en sus replicas pero no tiene de resincronizacion de estas cuando se cae

    Args:
        Leader (_type_): _description_
    """
    
    
    def __init__(self, ip: str, port: int = 8001, flask_port: int = 8000, m: int = 160):
        super().__init__(ip, port, m)
        self.flask_port: int = flask_port
        self.data_replicate_gestor: DataReplicatedGestor = DataReplicatedGestor()
        #self.setup_routes()
        
    def start_node(self):
        super().start_node()
        log_message(f'Inicializar el servidor de Flask',func=self.start_node)
        self.start_flask_storange_server()
        log_message(f'Inicializado el nodo',func=self.start_node)
    def start_flask_storange_server(self):
        self.setup_routes()
        log_message(f'Inicializar el hilo de del servidor de flask',func=self.start_flask_storange_server)
        threading.Thread(
            target=lambda: app.run(host=self.ip, port=self.flask_port,threaded=True), daemon=True 
        ).start()  # Iniciar servidor por el puerto 8000  # Si da problemas poner los hilos en False
        
    
    def setup_routes(self):
        app.add_url_rule("/health/live", endpoint="health_live", view_func=lambda: jsonify(status="live", protocol=wire.VERSION))
        app.add_url_rule("/health/ready", view_func=self.health_ready)
        # Registrar la ruta y vincularla al método de instancia
        app.add_url_rule("/upload", view_func=self.upload_file, methods=["POST"])
        app.add_url_rule(
            "/get_document_by_name", view_func=self.get_file_by_name, methods=["GET"]
        )
        app.add_url_rule(
            "/update", view_func=self.update_file, methods=["POST"]
        )  # Actualizar
        app.add_url_rule(
            "/save_document_like_replica",
            view_func=self.save_document_like_replica,
            methods=["POST"],
        )  # Endpoint para guardar los documentos en las replicas
        app.add_url_rule(
            "/update_document_like_replica",
            view_func=self.update_document_like_replica,
            methods=["POST"],
        )  # Endpoint  para actualizar data de los documento que se guarda como replica
        app.add_url_rule(
            "/persist_insert_document",
            view_func=self.persist_insert_document,
            methods=["POST"],
        )  # Esto es para recibir la confirmación que se haga persistente

        app.add_url_rule(
            "/delete_file",
            view_func=self.delete_file,
            methods=["POST"],
        )  # Esto es para eliminar un archivo

    def health_ready(self):
        try:
            with db.engine.connect() as connection:
                connection.exec_driver_sql("SELECT 1")
            ready = self.is_db_stable()
            return jsonify(status="ready" if ready else "stabilizing", protocol=wire.VERSION), 200 if ready else 503
        except Exception:
            return jsonify(status="unavailable", protocol=wire.VERSION), 503

    def start_threads(self):
        """Inicia todos los hilos

        Returns:
            _type_: _description_
        """

        super().start_threads()
        #threading.Thread(
        #    target=lambda: app.run(host=self.ip, port=self.flask_port), daemon=True
        #).start()  # Iniciar servidor por el puerto 8000

        #############################################
        #                                           #
        #    Handles para el tema de las replicas   #
        #                                           #
        ##############################################

    def _delete_document_replica_if_no_check_response(
        self, document_id: int, event_guid: str
    ):
        """
        Es el método que llama el gestor de replicas cuando se tiene que ejecutar el evento

        Args:
            document_id (int): Id del documento en cuestión con respecto al evento
            event_guid (str): Guid del evento en cuestion
        """
        try:
            # Chequear que el documento exista antes de eliminarlo
            if not db.has_document(
                document_id
            ):  # Si ya no existe pues no se puede eliminar
                log_message(
                    f"El documento con id {document_id} no existe en la base de datos por lo cual no se puede eliminar",
                    func=self._delete_document_replica_if_no_check_response,
                )
                return
            if db.is_document_persistent(
                document_id
            ):  # Si el documento es persistente => que ya se recibió la confirmación
                log_message(
                    f"El documento {document_id} es persistente en la db con el guid {event_guid} por lo cual no se va a eliminar",
                    func=self._delete_document_replica_if_no_check_response,
                )
                return
            log_message(
                f"El documento con id {document_id}  y guid {event_guid} no es persistente en la base de datos => se va a eliminar totalmente la columna",
                func=self._delete_document_replica_if_no_check_response,
            )
            db.delete_document_all(document_id)
            log_message(
                f"Se eliminó la fila del documento id {document_id} con el evento {event_guid}",
                func=self._delete_document_replica_if_no_check_response,
            )

        except Exception as e:
            log_message(
                f"Ocurrio un error al tratar de efectuar el evento del documento {document_id} con guid: {event_guid}",
                func=self._delete_document_replica_if_no_check_response,
            )

    def _revoke_update_actions(
        self, document_id: int, event_guid: str, old_document: Document, old_owner: int
    ):
        """
        Este metodo es el que se ejecuta en el execute
        Verifica si el documento no existe o el cambio ya fue persistente
        En caso de no ser persistente se devuelve al estado anterior

        Args:
            document_id (int): _description_
            event_guid (str): _description_
            old_document (Document): _description_
            old_owner:int El anterior dueño del nodo si es el mismo se pone aun asi
        """
        try:
            log_message(
                f"Se Empezo a ejecutar el revoke update del documento {document_id} y evento {event_guid}",
                func=self._revoke_update_actions,
            )
            if not db.has_document(document_id):
                log_message(f"Fue eliminado antes la fila del documento {document_id}")
                return
            if db.is_document_persistent(
                document_id
            ):  # Chequea que si ya es persistente no se continua
                log_message(
                    f"El documento {document_id } del evento {event_guid} ya es persistente",
                    func=self._revoke_update_actions,
                )
                return
            log_message(
                f"El documento {document_id} del evento {event_guid} y antiguo dueño {old_owner} no es persistente por tanto se devuelve a su estado original ",
                func=self._revoke_update_actions,
            )
            db.update_document(document_id, old_document, old_owner, False)
            db.persist_document(document_id)
            log_message(
                f"El documento {document_id} del evento {event_guid} con dueño {old_document} fue devuelto a su cambios como antes del update",
                func=self._revoke_update_actions,
            )

        except Exception as e:
            log_message(
                f"Ocurrio un error tratando de efectuar el evento de revocar el update del documento con id {document_id} y guid {event_guid}",
                func=self._revoke_update_actions,
            )

        #################################
        #                               #
        #            UTILS              #
        #                               #
        #################################

    def url_from_ip(self, ip: str):
        """Dado una ip devuelve su url de flask correspondiente

        Args:
            ip (str): la ip

        Raises:
            Exception: Si la ip no es un str

        Returns:
            str: Devuelve la url para el nodo en flask que sale por el puerto 8000
        """
        if not isinstance(ip, str):
            log_message(
                f"La ip debe ser un str no un {type(ip)}, {ip}", func=self.url_from_ip
            )
            raise Exception(f"El ip debe ser un str no un {type(ip)}, {ip}")
        return f"http://{ip}:{self.flask_port}"

    def add_end_point_to_url(self, url: str, end_point: str) -> str:

        return f"{url}/{end_point}"

        ###############################
        #                             #
        #       Save like replica     #
        #                             #
        ###############################

    # EndPoint SaveDocumentReplica
    def save_document_like_replica(self):
        """
        End Point para guardar documento siendo una réplica
        """
        try:
            addr_from = request.remote_addr
            log_message(
                f"Se a mandado a guardar un archivo como replica que envio el addr: {addr_from} ",
                func=self.save_document_like_replica,
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

            node, doc = wire.loads(data)
            doc: Document = doc
            node: ChordNodeReference = node

            # Si es mas antiguo que el que yo tenia lanzo exepcion y le envio 400

            # Chequear que no hay mas ninguno en la db
            doc_id = doc.id
            if db.has_document(doc_id):
                log_message(
                    f"Ya se tiene guardado el documento {doc.title} con id {doc_id}",
                    func=self.save_document_like_replica,
                )
                if db.update_document(
                    doc_id, doc, node.id
                ):  # Retornar que se hizo el cambio exitosamente
                    log_message(
                        f"Se realizo el cambio del documento {doc.id} con titulo {doc.title} del que es dueño el nodo {node.id}",
                        func=self.save_document_like_replica,
                    )
                    guid = self.data_replicate_gestor.add_document_to_the_queue(
                        doc, self._delete_document_replica_if_no_check_response
                    )  # Añadir al gestor de eventos por si no es persistente que lo elimine

                    return Response(
                        wire.dumps((SAVE_DOC_WAITING_OK, guid)),
                        status=HTTPStatus.OK,
                    )
                else:
                    log_message(
                        f"Hubo un error tratando de actualizar el documento con id {doc_id} de dueño {node.id}",
                        func=self.save_document_like_replica,
                    )
            else:  # Es que no existe el documento en la base de datos
                db.insert_document(
                    doc, node.id, False
                )  # Se añade en la base de datos y decimos que ahora no es persistente, esperamos confirmación
                log_message(
                    f"Se inserto correctamente el documento {doc.id} que es dueño el nodo {node.id}",
                    func=self.save_document_like_replica,
                )
                guid = self.data_replicate_gestor.add_document_to_the_queue(
                    doc, self._delete_document_replica_if_no_check_response
                )  # Añadir al gestor de eventos por si no es persistente que lo elimine

                log_message(
                    f"Listo para enviar respuesta al nodo {addr_from} del documento {doc_id} con guid {guid}",
                    func=self.save_document_like_replica,
                )

                return Response(
                    wire.dumps((SAVE_DOC_WAITING_OK, guid)),
                    status=HTTPStatus.OK,
                )
        except Exception as e:
            log_message(
                f"Hubo un problema tratando de salvar el documento como replica Error:{e} \n {traceback.format_exc()}",
                func=self.save_document_like_replica,
            )
        # Endpoint update_document_like_replica

    def update_document_like_replica(self):
        try:
            addr_from = request.remote_addr
            log_message(
                f"Se a mandado actualizar un archivo como replica que envio el addr: {addr_from} ",
                func=self.update_document_like_replica,
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
            if not db.has_document(doc_id):  # Si no está en la db Lanzar exepcion
                log_message(
                    f"Error el documento {doc_id} que envio el nodo {node.id} no se puede actualizar pq no existe en esta replica ",
                    func=self.update_document_like_replica,
                )
                return Response(
                    wire.dumps((ERROR_NO_EXIST_DOC_IN_THIS_REPLICA, doc_id)),
                    status=HTTPStatus.NOT_FOUND,
                )

            # Tomar el documento ahora
            old_doc = db.get_document_by_id(doc_id)  # Tomar el nodo
            if old_doc is None:
                raise Exception(
                    f"El documento con id {doc_id} no está en la db y deberia estar"
                )

            if not old_doc.record.can_update(new_doc.record):
                log_message(
                    f"El documento {doc_id} a update es mas viejo {new_doc.record} que el que se tenia {old_doc.record}",
                    func=self.update_document_like_replica,
                )
                return Response(
                    wire.dumps((ERROR_THIS_IS_NOT_THE_LASTED_VERSION, doc_id)),
                    HTTPStatus.NOT_ACCEPTABLE,
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
                func=self.update_document_like_replica,
            )

            return Response(
                wire.dumps((SAVE_DOC_WAITING_UPDATED, guid)), status=HTTPStatus.OK
            )
        except Exception as e:
            log_message(
                f"Ocurrio un error tratando de upgradear en la replica Error: {e} \n{traceback.format_exc()}",
                func=self.update_document_like_replica,
            )
            raise Exception(e)

    def persist_insert_document(self):
        """Endpoint post para que confirmen si se realizo exitosamente la inserccion siendo yo una replica"""
        try:
            addr_from = request.remote_addr
            log_message(
                f"Se a mandado a confirmar la insercción de un archivo como replica que envio el addr: {addr_from} ",
                func=self.persist_insert_document,
            )
            data = self.get_data_from_request()
            document_id, guid = wire.loads(data)  # La data recibida
            # Chequear que el documento está en nuestro sistema
            if not db.has_document(
                document_id
            ):  # Si no esta en la db se envia un 404 que no está en la base de datos
                log_message(
                    f"El documento {document_id} no se encuentra en la base de datos por tanto no se puede confirmar nada de el",
                    func=self.persist_insert_document,
                )
                return Response(
                    "No esta el documento en la base de datos",
                    status=HTTPStatus.NOT_FOUND,
                )

            db.persist_document(document_id)
            self.data_replicate_gestor.confirm_guid(guid)
            log_message(f'Fue aceptado el guid {guid}',func=self.persist_insert_document)
            log_message(
                f"Se pudo hacer persistente el documento guardado como replica {document_id} con guid {guid} al nodo {addr_from}",
                func=self.persist_insert_document,
            )
            return Response(
                f"Se hizo persistente con exito el documento {document_id} con guid {guid}",
                status=HTTPStatus.OK,
            )

        except Exception as e:
            log_message(
                f"Hubo un error tratando de hacer persistente un documento siendo yo la replica del documento {document_id} con guid {guid} la informacion viene de {addr_from} Error:{e} \n {traceback.format_exc()}",
                func=self.persist_insert_document,
            )

        ##################################
        #                                #
        #       I´m owner of the data    #
        #                                #
        ##################################

    def get_data_from_request(self) -> bytes:
        """
            Retorna los bytes con lo que envio el cliente

        Returns:
            bytes: _description_
        """
        # El cliente manda (Nombre archivo, archivo)
        try:
            return request.get_data()
        except Exception as e:
            log_message(f"Hubo un error tratando de sacar la data del request Error:{e} \n {traceback.format_exc()}",func=self.get_data_from_request)
            raise Exception(e)

    def send_file_to_node(
        self, node: ChordNodeReference, sub_url: str, data: bytes,timeout:float=10
    ) -> rq.Response:
        """
         Dado un nodo la suburl del metodo post a enviar y los bytes envia una informaión a un nodo

        Args:
            node (ChordNodeReference): _description_
            sub_url (str): _description_
            data (bytes): _description_
            timeout(float): cant de segundos maximos de espera default 10
        Raises:
            Exception: _description_

        Returns:
            Response: _description_
        """
        try:

            url = self.url_from_ip(node.ip)
            url = self.add_end_point_to_url(url, sub_url)

            log_message(
                f"Se va a enviar un mensaje a nodo {node.id} url:{url}",
                func=self.send_file_to_node,
            )
            response = rq.post(url, data=data, headers={"Content-Type": "application/json"}, timeout=timeout)
            response.raise_for_status()  # Levanta una excepción para códigos de estado HTTP 4xx/5xx
            return response
           
        except rq.exceptions.Timeout:
            log_message(f"Se excedió el tiempo de espera de conexion {timeout } con el nodo {node} en la suburl {sub_url}", func=self.send_file_to_node)
        
        except Exception as e:
            log_message(
                f"Hubo una exepción enviando un mensaje al nodo {node.id} con la url {url} Error:{e} \n {traceback.format_exc()}",
                func=self.send_file_to_node,
            )
            raise Exception(e)

    def save_in_my_replicas(
        self, document: Document, succ_list: list[ChordNodeReference], sub_url: str
    ) -> tuple[list[str], bool]:
        """
        Manda a guardar en las replicas el documento

        Args:
            document (Document): _description_
            succ_list (list[ChordNodeReference]): _description_
            sub_url: (str): El / donde se desea guardar

        Returns:
            tuple[list[str],bool]: Devuelve una lista con los guids de cada archivo en cada replica y el bool es si fue exitosa en todas
        """
        try:
            log_message(
                f"Se va a enviar a guardar el documento {document.id} en las replicas {succ_list}"
            )
            lis: list[str] = []
            for replica in succ_list:
                if replica.id == self.id:
                    continue  # Nunca me mando a guardar como replica a mi mismo
                data = wire.dumps((self.ref, document))
                log_message(
                    f"Se va a enviar a guarda en la replica {replica.id} el documento {document.id} a guardar el documento",
                    func=self.save_in_my_replicas,
                )
                response = self.send_file_to_node(replica, sub_url, data)  # Enviar data
                if response.status_code != 200:
                    log_message(
                        f"Enviando a guardadar a la replica {replica.id} el archivo {document.id} no se ha recibido 200 se recibio {response.status_code}"
                    )
                    return ([], False)
                log_message(
                    f"Se guardo exitosamente el documento {document.id} en la replica {replica.id}",
                    func=self.save_in_my_replicas,
                )

                data = response.content  # Tomar la respuesta
                code, guid = wire.loads(data)  # Tomar los datos
                log_message(
                    f"Guardado el archivo {document.id} en la replica {replica.id} con guid {guid}",
                    func=self.save_in_my_replicas,
                )
                lis.append(guid)
            log_message(
                f"Se guardó satisfactoriamente en mi replicas el documento {document.id}",
                func=self.save_in_my_replicas,
            )
            return (lis, True)
        except Exception as e:
            log_message(
                f"Ocurrio un error guardando en las replicas el documento {document.id} Error:{e} \n {traceback.format_exc()} ",
                func=self.save_in_my_replicas,
            )
            return ([], False)

    def confirmation_crud_in_my_replicas(
        self,
        replicas_lis: list[ChordNodeReference],
        guid_list: list[str],
        document_id: int,
        ok_replicas: list[ChordNodeReference],
    ) -> list[ChordNodeReference]:
        """
        Confirma que se insertó correctamente el documento, confirma a las replicas
        devuelve una lista con las replicas que confirmaron que estuvo todo ok

        Args:
            replicas_lis (list[ChordNodeReference]): _description_
            guid_list (list[str]): _description_
            document_id (int): _description_

        Returns:
            list[ChordNodeReference]: _description_
        """

        lis: list[ChordNodeReference] = []
        try:
            for replica, guid in zip(replicas_lis, guid_list):
                try:
                    log_message(
                        f"Se va a  mandar a confirmar en las replica {replica.id} el documento {document_id} con guid {guid}"
                    )
                    response = self.send_file_to_node(
                        replica,
                        "persist_insert_document",
                        wire.dumps((document_id, guid)),
                    )
                    if response.status_code != 200:
                        log_message(
                            f"Ocurrio un error tratando de aceptar en la replica {replica.id} el documento {document_id} con guid {guid}",
                            func=self.confirmation_crud_in_my_replicas,
                        )
                    else:  # Si se completo exitosamente añadir a la lista de exitoso
                        log_message(f'Ocurrio exitosa la confirmación a la replica {replica.id} el documento {document_id} y guid {guid}')
                        lis.append(replica)
                        ok_replicas.append(
                            replica
                        )  # Se añade a la lista que se pasa como referencia la cual va tomando cuales nodos si fueron exitosos
                except Exception as e:
                    log_message(
                        f"Ocurrio un problema enviando confirmacion del documento {document_id} con guid {guid} a la replica {replica.id}",
                        func=self.confirmation_crud_in_my_replicas,
                    )

        except Exception as e:
            log_message(
                f"Ocurrio un problema mandando a confirmar la inserccion del documento {document_id} ",
                func=self.confirmation_crud_in_my_replicas,
            )

        return lis

    def Crud_action(
        self, document: Document, sub_url: str, crud_code: CrudCode
    ) -> tuple[bool, list[ChordNodeReference]]:
        """
         Realiza la transacción atomica de guardar un documento en los nodos replica

        Args:
            document (Document): _description_
            sub_url (str): Es la ruta a guardar por ejemplo "save_document_like_replica"  para insertar desde el inicio un archivo
            crud_code (CrudCode): Dice si se quiere insertar, update, delete el documento
        Returns:
            tuple[bool,list[ChordNodeReference]]: True si se guardo correctamente en todos los nodos, [Devuelve en que nodos en los que está el documento] ,False ocurrio un error
            En la lista de nodos devuelve en cuales esta guardada la información, si está vacia => que no se guardo el dato si se llego a informar alguna replica esta las eliminará
        """
        to_return: list[ChordNodeReference] = []
        try:
            name = document.title

            succ_list = self.succ_list

            # Primero llamar a mis nodos replicas para que traten de guardar la información
            log_message(
                f"Llamando a mis replicas para que me guarden el archivo {document.id}",
                func=self.Crud_action,
            )

            lis_guid, ok_ = self.save_in_my_replicas(
                document, succ_list, sub_url
            )  # Lista con guid de las replicas para confirmar además del bool de si se completó todo con éxito

            if not ok_:  # Chequear que se haya guardado en mis replicas
                log_message(
                    f"No se pudo guardar el documento {document.id} las replicas ",
                    func=self.Crud_action,
                )
                return (False, to_return)
            log_message(
                f"El documento {document.id}, titulo {document.title} se guardó exitosamente en las replicas",
                func=self.Crud_action,
            )
            if crud_code == CrudCode.Insert:  # Insertar acá el documento

                if not db.insert_document(
                    document, self.id, True
                ):  # Se trata de insertar un documento en la base de datos Ademas se hace persistente
                    log_message(
                        f"Error al tratar de insertar el documento {document.id} {document.title} ",
                        func=self.Crud_action,
                    )
                    raise Exception(
                        f"Error al tratar de insertar el documento {document.id} {document.title} "
                    )
                log_message(
                    f"El archivo con nombre {name} se a guardado correctamente en la base de datos",
                    func=self.Crud_action,
                )

            else:  # Se quiere actualizar o eliminar (Poner en None la data del documento) el documento

                if not db.update_document(document.id, document, self.id, False):
                    raise Exception(
                        f"No se puede actualizar un documento si no existe la fila de este {document.id} {document.title}"
                    )
                db.persist_document(document.id)
                log_message(
                    f"Se actualizaron los cambios del documento {document.id} {document.title}",
                    func=self.Crud_action,
                )
            # Como hasta acá se pudo añadir en mi db
            to_return.append(self.ref)  # Añado mi referencia

            # Mandar a confirmar a las replicas
            lis_ok_replicaton = self.confirmation_crud_in_my_replicas(
                succ_list, lis_guid, document.id, to_return
            )

            log_message(
                f"Se guardó exitosamente el archivo {document.id} en este nodo {self.id}y en las replicas {lis_ok_replicaton}",
                func=self.Crud_action,
            )

            return (True, to_return)
        except Exception as e:
            log_message(
                f"Ocurrio un Error en Crud Action con codigo {crud_code} el documento {document.id} {document.title} a la sub_url {sub_url} Error:{e} \n {traceback.format_exc()}"
            )
            return (False, to_return)
    def create_document(self,guid:str,title:str,text:str,max_value:int=16)->Document:
        """
        Funcion que crea un documento

        Args:
            title (str): _description_
            text (str): _description_
            max_value (int, optional): _description_. Defaults to 16.

        Returns:
            Document: _description_
        """
        return Document(title=title,text=text,max_value=max_value)
    def redirect_request(self,name:str,hash_name:int):
        """
        Este metodo se encarga de saber si hay que redireccionar a otro nodo el request
        Si devuelve algo diferente de None devolver, None es que soy yo el dueño
        Args:
            name (str): nombre del archivo
            hash_name (int): id_ del archivo

        Returns:
            tuple[Any, Literal[HTTPStatus.MOVED_PERMANENTLY]] | None: _description_
        """
        node_owner=self.find_key_owner(hash_name)
        log_message(
                f"El nodo que debe tener el documento con nombre {name} y llave {hash_name} es el nodo {node_owner.id}",
                func=self.redirect_request
            )
        if node_owner.id!=self.id:# Es que no soy el duenno y tengo que redirigir
            log_message(f"Yo no soy el dueño del archivo {name} con id {hash_name} el dueño es {node_owner.id}",func=self.redirect_request)
            return (
                jsonify({"message": f'Se va a redirigir al nodo {node_owner.id} ip:{node_owner.ip}','ip':node_owner.ip}),
                HTTPStatus.MOVED_PERMANENTLY,
            )
        return None
    
    def get_request(self,func_to_do_if_i_owner):
        """
        Se encarga de ls peticiones de upload y update

        Args:
            func_to_do_if_i_owner (_type_): funcion que se hace si soy el dueño

        Returns:
            _type_: _description_
        """
        addr_from = request.remote_addr
        log_message(
            f"Se a mandado a tratar un archivo que envio el addr: {addr_from} ",
            func=self.get_request,
        )
        # Nombre del archivo , str con el archivo
        doc_to_save = self.get_data_from_request()  # Tomar los bytes de la data

        if doc_to_save is None:  # Es que no se envió nada
            # Retornar error de no file
            return (
                jsonify({"message": 'Bad Request: Parámetro "param" requerido'}),
                HTTPStatus.BAD_REQUEST,
            )

        name, doc_to_save = wire.loads(doc_to_save)
        log_message(f"La data es {name}{doc_to_save}", func=self.get_request)

        log_message(f"El archivo tiene nombre {name}", func=self.get_request)
        hash_name = getShaRepr(name)  # Hashear el nombre dado que esta sera la llave
        # Saber si hay que mandar a redireccionar
        redirection=self.redirect_request(name,hash_name)
        if redirection is not None:
            log_message(f"Se va a redirigir la peticion del archivo {name} del add: {addr_from}",func=self.get_request)
            return redirection
        return func_to_do_if_i_owner(guid=get_guid(),hash_name=hash_name,name=name,doc_to_save=doc_to_save)
    
    def _create_and_save_document(self,guid:str,name:str,doc_to_save:str,sub_url:str,crud_code:CrudCode):
        """
        Handle necesario para despues utilizarlo para decirle al cliente si se subió correctamente el documento
        """
        log_message(f"Se mando a crear y salvar el documento {name} con guid {guid} ",func=self._create_and_save_document)
        ok_crud, nodes_save = self.Crud_action(
                #Document(name, doc_to_save),
                self.create_document(guid=guid,title=name, text=doc_to_save),
                sub_url,
                crud_code=crud_code,
            )
        log_message(f"Se guardo correctmanete el documento {name} {ok_crud} en los nodos {nodes_save}")
        if not ok_crud:
             log_message(
                    f"Ocurrio un error tratando de insertar el documento con {name} y data {doc_to_save} e id{getShaRepr(name)} se guardo correctamente en los nodos {nodes_save}",
                    func=self._process_to_save_document,
                )
        return ok_crud,nodes_save
    
    def _process_to_save_document_thread(self,guid:str,name:str,doc_to_save:str,sub_url:str,crud_code:CrudCode):
        """
        Es el hilo que llama el metodo analogo
        De este es el que hay que heredar despues
        """
        try:
            log_message(f"Se va mandar a guardar el documento {name}",func=self._process_to_save_document)
            ok_crud,nodes_save=self._create_and_save_document(guid=guid, name=name,doc_to_save=doc_to_save,sub_url=sub_url,crud_code=crud_code)
            if ok_crud:
                 log_message(f'Se procesó el documento {name} con guid {guid} y suburl{sub_url} con resultado {ok_crud} en los nodos {nodes_save}',func=self._process_to_save_document)
            else:
                 log_message(f'Ocurrio un error procesando el documento {name} con guid {guid} y suburl{sub_url} con resultado {ok_crud} en los nodos {nodes_save}',func=self._process_to_save_document)
        except Exception as e:
            log_message(f"Error tratando de iniciar el hilo para salvar el documento {name} con guid {guid} Error: {e} \n {traceback.format_exc()}",func=self._process_to_save_document_thread)

    def _process_to_save_document(self,guid:str,name:str,doc_to_save:str,sub_url:str,crud_code:CrudCode):
        """
        Aca se manda el guid que se le dio al cliente como de procesamiento y el nombre del archivo y el archivo
        para añadirlo a la cola de espera.
        """
        try:
            log_message(f"Voy a mandar a crear el hilo para el documento {name} con guid {guid}",func=self._process_to_save_document)
            args=(guid,name,doc_to_save,sub_url,crud_code)
            threading.Thread(target=self._process_to_save_document_thread,args=args,daemon=True).start()
            log_message(f"Se creo correctamente el hilo para el documento {name} con guid {guid}",func=self._process_to_save_document)
        except Exception as e:
            log_message(f"Error tratando de guardar el documento {name} con guid {guid} Error:{e} \n {traceback.format_exc()}",func=self._process_to_save_document)   
    
   
    
    # EndPoint get_file_by_name
    def get_file_by_name(self):
        """
        Es el endpoint para devuelver un documento dado su nombre  el endpoint es "get_document_by_name"
        """
        addr_from = request.remote_addr  # La direccion desde donde se envia la petición

        log_message(
            f"Se a recibido una petición de GET para el para devolver un documento desde la dirección {addr_from}",
            func=self.get_file_by_name,
        )
        try:
            name = str(request.args.get("name", None))
            start = int(
                request.args.get("start", 1)
            )  # Paquete por donde empezar la descarga

            if name is None:  # Debe enviar al menor un nombre de archivo
                log_message(
                    f"Se envio a pedir el documento {name}, desde el paquete {start}",
                    func=self.get_file_by_name,
                )
                return jsonify(
                    {"message": "Se esperaba que el nombre no fuera None"}, 400
                )

            # Verificar que yo soy el dueño de ese id
            key = getShaRepr(name)
            node = self.find_key_owner(key)
            log_message(
                f"El nodo que debe tener el documento con nombre {name} y llave {key} es el nodo {node.id}",
                func=self.get_file_by_name
            )
            if node.id != self.id:  # Redirecciono al nodo que es dueño de la llave
                red_ip = self.url_from_ip(node.ip)
                log_message(
                    f"Se va a rederigir al nodo con id {node.id} para realizar la busqueda del archivo {name} con el start {start}",
                    func=self.get_file_by_name,
                )
                url = self.add_end_point_to_url(red_ip, "get_document_by_name")
                params = {"name": name, "start": start}
                url = f"{url}?{urlencode(params)}"
                log_message(
                    f"La url para redireccionar la peticion del documento {name} con llave {key} es {url}",
                    func=self.get_file_by_name,
                )
                return redirect(url)

            doc = db.get_document_by_id(getShaRepr(name))

            if doc is None:  # Si es None es pq no está en la DB
                log_message(
                    f"El documento con nombre {name} no se encuentra en la base de datos",
                    func=self.get_file_by_name,
                )
                return jsonify(
                    {
                        "message": f"El documento con nombre {name} no se encuentra en la base de datos"
                    },
                    
                ),409

            log_message(
                f"Se a recuperado exitosamente el documento {doc.title} dado que se habia pedido el {name} desde el paquete {start}",
                func=self.get_file_by_name,
            )

            if doc.record.is_delete:
                return jsonify(message='Document deleted'), 404
            return Response(wire.dumps(doc.text), content_type='application/json')
        except Exception as e:
            log_message(
                f" A ocurrido un error {e} tratando de dar en el endpoint de devulver un archivo por nombre {traceback.format_exc()}",
                func=self.get_file_by_name,
            )
            
            
            
            
            
            
    def _upload_file(self,guid:str,hash_name:str,name:str,doc_to_save:Document):
        """
        Logica interna para guardar un documento en este nodo

        Args:
            hash_name (str): id del documento
            name (str): nombre del documento
            doc_to_save (Document): documento

        Returns: Response
            
        """
        # Mandar a guardar en la base de datos

        # Comprobar que no esta en la base de datos

        doc = db.get_document_by_id(hash_name)
        log_message(f"El tipo de doc es {type(doc)}", func=self.upload_file)
        if doc is not None:
            log_message(
                f"El documento con nombre {name} ya estaba guardado ",
                func=self.upload_file,
            )
            return (
                jsonify(
                    {"message": f"Conflict: El archivo {name} ya existe en el servidor"}
                ),
                409,
            )

        # Guardar en la base de datos
        try:
        
            log_message(f"Mandando a procesar el documento {name}",func=self._upload_file)
            self._process_to_save_document(guid=guid,name=name,doc_to_save=doc_to_save,sub_url="save_document_like_replica",crud_code=CrudCode.Insert)
            log_message(f"Se llamo el metodo para el documento {name } se va a mandar el guid {guid} ",func=self._upload_file)
            return (jsonify({"guid":guid}),HTTPStatus.OK)

        except Exception as e:
            log_message(
                f" Hubo un error tratando de guardar el archivo {name} \n {e} \n {traceback.format_exc()}",
                func=self.upload_file,
            )

            return (
                jsonify(
                    {"message": f"Ocurrio un problema guardando el documento {name}"}
                ),
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )
            
    
        
    # Endpoint upload_file
    def upload_file(self):
        """
         Endpoint upload_file

        Returns:
            _type_: _description_
        """
        return self.get_request(self._upload_file)
                
            
            
            
            
            
    def _update_file(self,guid:str,hash_name:str,name:str,doc_to_save:Document):
               # Comprobar que está en la base de datos
        if not db.has_document(hash_name):  # Mandar error de que no se envió nada
            return (
                jsonify(
                    {
                        "message": f"El archivo {name} no se encuentra en la base de datos"
                    }
                ),
                HTTPStatus.BAD_REQUEST,
            )

        # Actualizar
        log_message(
            f"Se va a tratar de actualizar el documento {name}", func=self.update_file
        )
        try:
            log_message(f"Mandando a procesar el documento para actualizar {name}",func=self._update_file)
            self._process_to_save_document(guid=guid,name=name,doc_to_save=doc_to_save,sub_url="update_document_like_replica",crud_code=CrudCode.Update)
            
            log_message(f"Se llamo el metodo de salvar los cambios desde actualizar documentos para el documento {name } se va a mandar el guid {guid} ",func=self._update_file)
            return (jsonify({"guid":guid}),HTTPStatus.OK)
            
        
        except Exception as e:
            log_message(
                f"Hubo un problema tratanto de actualizar el archivo {name} Error:{e} \n {traceback.format_exc()}",
                func=self.update_file,
            )
            return (
                jsonify(
                    {"message": f"Ocurrio un problema actualizando el documento {name}"}
                ),
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    def update_file(self):
        """
        End point de guardar los archivos de flask

        Returns:
            _type_: _description_
        """
        return self.get_request(self._update_file)
    
    
    def _delete_file(self,doc_id:int,doc_name:str):
        """
        Metodo para eliminar en el nodo el documento, Nota solo se eliminan los bytes no el contenido

        Args:
            doc_id (int): _description_
            doc_name (str): _description_

        Returns:
            _type_: _description_
        """
        
        # Comprobar que está en la base de datos
        if not db.has_document(doc_id):  # Mandar error de que no se envió nada
            return (
                jsonify(
                    {
                        "message": f"El archivo {doc_name} no se encuentra en la base de datos"
                    }
                ),
                HTTPStatus.BAD_REQUEST,
            )
        log_message(
            f"Mandando a eliminar {doc_name} : {doc_id} de mi db y mis replicas",
            func=self.delete_file,
        )
        document=db.get_document_by_id(doc_id)
        
        # Comprobar que el documento no este ya eliminado
        
        try:
            
            if document.record.is_delete:
                log_message(f"El documento {doc_name} esta ya eliminado",func=self._delete_file)
                return jsonify({"message":f"El documento {doc_name} esta ya eliminado"}),HTTPStatus.OK
            
            document.delete()
            ok_crud, nodes_save = self.Crud_action(
                document=document,
                sub_url="update_document_like_replica",
                crud_code=CrudCode.Delete,
            )
            if (
                not ok_crud
            ):  # Si no se pudo eliminar correctamente
                log_message(
                    f"No se pudo eliminar el documento {document.id} se pudo guardar el cambio en los nodos {nodes_save}",
                    func=self.update_file,
                )
            else:
                log_message(
                    f"Se eliminó el documento {doc_name}", func=self.update_file
                )
                return (
                    jsonify(
                        {"message": f"Se actualizó eliminó el documento {doc_name} "}
                    ),
                    HTTPStatus.OK,
                )
        except Exception as e:
            log_message(
                f"Hubo un problema tratanto de eliminar el archivo {doc_name} Error:{e} \n {traceback.format_exc()}",
                func="_delete_file",
            )
            return (
                jsonify(
                    {"message": f"Ocurrio un problema eliminar el documento {doc_name}"}
                ),
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )
        
    def delete_file(self):
        addr_from = request.remote_addr
        try:
            log_message(
                f"Se a mandado a eliminar un archivo que envio el addr: {addr_from} ",
                func=self.delete_file,
            )
            # Nombre del archivo , str con el archivo
            data = self.get_data_from_request()  # Tomar los bytes de la data

            if data is None:  # Es que no se envió nada
                # Retornar error de no file
                log_message(f"No llega data desde el addr{addr_from}",func=self.delete_file)
                return (
                    jsonify({"message": 'Bad Request: Parámetro "param" requerido'}),
                    HTTPStatus.BAD_REQUEST,
                )
            doc_name: str = wire.loads(data)
            
            log_message(f"El documento a eliminar es {doc_name} de tipo {type(doc_name)}",func=self.delete_file)
            doc_id = getShaRepr(doc_name)

            redirection=self.redirect_request(name=doc_name,hash_name=doc_id)
            if redirection is not None:
                log_message(f"Se va a redireccionar la peticion de eliminar el archivo {doc_name} con id: {doc_id}",func=self.delete_file)
                return redirection
            log_message(
                f"Se ha enviado a eliminar el documento {doc_name} con id {doc_id} ",
                func=self.delete_file,
            )

            return self._delete_file(doc_id=doc_id,doc_name=doc_name)
        except Exception as e:
            log_message(f'Huboi un problema eliminando un archivo Error: {e} \n {traceback.format_exc()}',func=self.delete_file)

if __name__ == "__main__":
    print("Hello from Storage node")
    # time.sleep(10)
    ip = socket.gethostbyname(socket.gethostname())
    node = StoreNode(ip, m=3)

    #node.start_threads()  # Iniciar los nodos
    node.start_node() # Iniciar el pipeline
    while True:
        pass
