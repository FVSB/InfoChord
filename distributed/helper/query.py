import heapq
import threading
from shared.logger import log_message
from helper.docs import EmbeddingDocument
from typing import Callable
from helper.utils import get_guid,ThreadingSet
import numpy as np
import heapq
import threading

class DocsClassification:
    def __init__(self, id: int, title: str, snippet: str, score: float) -> None:
        self.id:int = id
        self.title:str = title
        self.snippet:str = snippet
        self.score:float = score

    def __lt__(self, other:'DocsClassification'):
        # Invertir la comparación para que el heapq funcione como un max-heap
        return self.score > other.score

class MaxHeap:
    def __init__(self):
        self.heap = []
        #self.lock = threading.RLock()

    def push(self, item: DocsClassification):
        #with self.lock:
            heapq.heappush(self.heap, item)

    def pop(self) -> DocsClassification:
        #with self.lock:
            return heapq.heappop(self.heap)

    def top(self) -> DocsClassification:
        #with self.lock:
            return self.heap[0]

    def __len__(self):
        #with self.lock:
            return len(self.heap)
    
    def is_empty(self) -> bool:
        #with self.lock:
            return len(self.heap) == 0


class QueryHandle:
    def __init__(self,guid:str,
                 query_embedding_list:list[np.array],
                 posibles_extensions:list[str],
                 func_score_embedding:Callable[[np.array,np.array],float],
                 max_results:int,
                 min_score:float=0) -> None:
        self.query_embedding_list:list[np.array]=query_embedding_list
        self.posibles_extensions:list[str]=posibles_extensions
        self.guid:str=guid
        self.posible_docs:MaxHeap=MaxHeap()
        self.func_score_embedding:Callable[[np.array,np.array],float]=func_score_embedding
        self.min_score:float=min_score
        self.max_results:int=max_results
        
        self.is_stable_response_:bool=True
        """
        Esto se hace para en caso de que la red halla sido inestable en algun momento de la consulta
        se pone en false para esperar nuevamente a las estabilidad
        para volver a preguntar
        """
        
    def is_stable_response(self)->bool:
        return self.is_stable_response_
    
    def db_is_not_stable(self):
        """
        Si en algun momento la red es inestable 
        se llama a este metodo para que haga que la query sea anulada
        """
        self.is_stable_response_=False
    def _get_best_embeddings_compare_score(self,save_embedding_list:list[np.array],save_chunks_text:list[str])->tuple[float , str]:
        """
        Dado el embedding de la query , el embeding de un documento y este divido por los mismos chunks que el embedding
        Devuelve el mejor escore entre todos los chunks y el chunks mas representativo
        Args:
            
            save_embedding_list (list[np.array]): _description_
            save_chunks_text (list[str]): _description_

        Returns:
            tuple[float , str]: _description_
        """
        
        best_score:float=0
        best_chunk:str=""
        
        for chunk_query_embedding in self.query_embedding_list:
            for i in range(len(save_embedding_list)):
                chunk_embedding=save_embedding_list[i]
                chunk_text=save_chunks_text[i]
                score=self.func_score_embedding(chunk_query_embedding,chunk_embedding)
                if score>best_score:
                    best_score=score
                    best_chunk=chunk_text
                    
        return best_score,best_chunk
    
    def add_document(self,doc:EmbeddingDocument):
        """
        Dado un documento lo añade al clasificador

        Args:
            doc (EmbeddingDocument): _description_
        """
        
        if doc is None:
            log_message(f"Aca hay un objeto None y no deberia ser",func=self.add_document)
        
        if doc.record.is_delete:
            log_message(f"El documento {doc.id} esta eliminado",func=self.add_document)
            return
        
        title_embedding=doc.embedding_title_list
        # Hallar el score con respecto al titulo
        title_score,_=self._get_best_embeddings_compare_score(doc.embedding_title_list,[doc.title for _ in range(len(doc.embedding_title_list))])
        # Hallar con respecto al texto y buscar el mejor fragmento
        
        text_score,text_chunk=self._get_best_embeddings_compare_score(doc.embedding_list,doc.text_chunks)
        
        # El score es 1.5 del titulo mas el del texto entre dos
        global_score=((title_score*1.5)+text_score)/2
        
        self._add_posible(id=doc.id,title=doc.title,snippet=text_chunk,score=global_score)
        
        
    def _add_posible(self,id: int, title: str, snippet: str, score: float)->bool:
        """
        Crea un añade al heap de maximos una nueva clasificacion del documento 
        True si el score es mayor que el minimo permitido
        False si es menor que el minimo permitido
        Args:
            id (int): id documento
            title (str): titulo documento
            snippet (str): chunk mas representativo
            score (float): score global

        Returns:
            bool: _description_
        """
        if score<self.min_score:
            return False
        doc_class=DocsClassification(id=id,title=title,snippet=snippet,score=score)
        self.posible_docs.push(doc_class)
        return True
    
    
    def get_results(self)->dict:
        """
        Retorna los n primeros mejores documentos
        En caso de ver menos de n como maximo devolvera hasta donde pueda
        Esto es para devolver al cliente
        Returns:
            list[dict]: _description_
        """
        lis:list[dict]=[]
        for i in range(self.max_results):
            if self.posible_docs.is_empty():
                break
            result=self.posible_docs.pop()
            result
            lis.append({"id":result.id,"title":result.title,"snipet":result.snippet,"score":result.score})
            
        return lis

class QueryGestor:
    """
    Clase gestora de las querys 
    """
    def __init__(self,func_score_embedding:Callable[[np.array,np.array],float],func_get_embedding_list:Callable[[str],tuple[list[np.array],list[str]]]) -> None:
        self.func_score_embedding:Callable[[np.array,np.array],float]=func_score_embedding
        """
        Es el comparador de embeddings
        """
        self.func_get_embedding_list:Callable[[str],tuple[list[np.array],list[str]]]=func_get_embedding_list
        """
        Recibe el texto y devuelve una lista de np.array con los embeddings y ademas si correspondiente chunk en texto
        
        Funcion que recibe el texto y devuelve una lista de array de numpy con los embeddings
        devuelve lista que tiene en cada indice los embeddings dd los chunks y los pedazos del embedding
        
        """
        self.query_admi:ThreadingSet=ThreadingSet()
        """
        Set resistente ante hilos para saber cuales peticiones estoy tratando ahora 
        """
        
    
    def create_embedding(self,text:str)->tuple[list, list[str]]:
        """
        Dado un str devuelve una lista de np.array donde son los embeddings en chunks del texto
        ademas de una lista de los chunks de la misma

        Args:
            text (str): _description_

        Returns:
            tuple[list, list[str]]: lista de np.array con los embeddings y lista de str con los chunks por donde se
            cortaron los embeddings
        """
        return self.func_get_embedding_list(text)
    
    def make_new_query(self,query:str,posibles_extensions:list[str],min_score:float,max_results:int):
        query_embedding_list,_=self.func_get_embedding_list(query)
        query_handle=QueryHandle(guid=get_guid(),
                           query_embedding_list=query_embedding_list,
                           posibles_extensions=posibles_extensions,
                           func_score_embedding=self.func_score_embedding,
                           min_score=min_score,
                           max_results=max_results
                           )
        self.query_admi.add_item(query_handle.guid) # Añadir al set para que cuando me llegue la propuesta la vuelva a enviar para atras
        return query_handle
    
    def can_process_this_query(self,query_handle:QueryHandle)->bool:
        """
        Dice si puedo o no procesar la handle 
        True si soy no al que comunicaron False si lo soy
        Args:
            query_handle (QueryHandle): _description_

        Returns:
            bool: _description_
        """
        if not query_handle.is_stable_response():
            return False
        return not self.query_admi.contains_item(query_handle.guid)

    def end_query(self,query_handle:QueryHandle)->bool:
        """
         Cuando se va a devolver al cliente se elimina del set para ahorrar memoria

        Args:
            query_handle (QueryHandle): _description_

        Returns:
            bool:True si se elimino, False si no existia
        """
        return self.query_admi.delete_if_exits_item(query_handle.guid)

