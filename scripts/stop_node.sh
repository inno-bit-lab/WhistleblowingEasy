#!/bin/bash

# Funzione di utilit� per mostrare l'uso dello script
usage() {
    echo "Usage: $0 --node-name NAME"
    exit 1
}

# Controllo se almeno un parametro � stato fornito
if [ "$#" -ne 2 ] || [ "$1" != "--node-name" ]; then
    usage
fi

NODE_NAME="$2" # Assegna il valore del nome del nodo alla variabile

# Cerca il processo tramite il nome fornito
PID=$(ps aux | grep "python bin/globaleaks -n --working-path=" | grep $NODE_NAME | grep -v grep | awk '{print $2}')

# Se il processo esiste, prova a terminarlo con SIGTERM
if [ ! -z "$PID" ]; then
    echo "Trovato il processo $NODE_NAME con PID $PID. Invio SIGTERM..."
    kill -15 $PID

    # Aspetta 60 secondi
    sleep 60

    # Controlla di nuovo se il processo esiste ancora
    PID=$(ps aux | grep "python bin/globaleaks -n --working-path=" | grep $NODE_NAME | grep -v grep | awk '{print $2}')
    if [ ! -z "$PID" ]; then
        echo "Il processo $NODE_NAME con PID $PID esiste ancora. Invio SIGKILL..."
        kill -9 $PID
    else
        echo "Il processo $NODE_NAME � stato terminato con successo."
    fi
else
    echo "Nessun processo trovato con nome $NODE_NAME."
fi
