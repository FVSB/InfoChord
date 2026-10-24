# Operation codes

EMPTYBIT = b""
FIND_SUCCESSOR = 1
FIND_PREDECESSOR = 2
# FIND_SUCCESSOR_WITHOUT_PREDECESSOR=10 # Busca el nodo que tiene sucesor y no predecesor el cual es el nodo "0 " por lo cual el nodo de mayor rango de la red debe buscarlo
GET_SUCCESSOR = 3
GET_PREDECESSOR = 4
NOTIFY = 5
CHECK_PREDECESSOR = 6
CLOSEST_PRECEDING_FINGER = 7
STORE_KEY = 8
RETRIEVE_KEY = 9
JOIN = 10
STORE_KEY_CLIENT = 11
FIND_KEY_OWNER = 12
RETRIEVE_KEY_CLIENT = 13
ELECTION = 14
ELECTION_WINNER = 15
STORE_KEY_SERVER = 16


# Sobre los protocolos con respecto a los mensajes dueño data, replica
SAVE_DOC_WAITING_OK = 17
SAVE_DOC_WAITING_UPDATED = 18
ERROR_NO_EXIST_DOC_IN_THIS_REPLICA = (
    19  # Dice que error pq no existe esa fila en esa replica
)
ERROR_THIS_IS_NOT_THE_LASTED_VERSION=20


CAN_YOU_TAKE_YOUR_NEW_KEYS=21 # Es para enviar al chord_node_reference si se puede hacer cargo ya de las que ahora son suyas

CHECK_NETWORK_STABILITY=22 # En chord Lider chequea que mi predecesor sea estable
CHECK_IN_ELECTION=23 # EN ChordLider chequea si el predecesor está en elección
IS_DATA_SYNC=24 # En distributed_data_base dicta si el tengo mi data actualizada
IS_DB_STABLE=25 # Es para el lider y dice True O False si la db es estable para el CRUD o no 
CAN_UPDATE_DATA=26 #Aca dice si ya sincronize los datos que tenia a sus nuevos duennos
PROCESS_QUERY=27 # Aca es para que mi sucesor procese tb la query
FIND_NODES=28
GET_LEADER=29
PING=30 #Aca chequeo que estoy vivo
I_AM_LEADER=31# Dice si soy el lider o no