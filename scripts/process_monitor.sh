#!/bin/bash
. ~/.profile
. ~/.bashrc
. ~/.common_wbe

source  $SCRIPTS_PATH/common_functions.sh

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

. $SCRIPTS_PATH/.common_node_wbe --node-name $NODE_NAME

MAINTENANCE_MODE=$(get_property MAINTENANCE_MODE)
NODE_STATUS=$(get_property NODE_STATUS)

if [ "$MAINTENANCE_MODE" = "Y" ]; then
    echo "Modalità manutenzione attiva. Lo script termina."
    exit 0
else
    # Se MAINTENANCE_MODE non esiste o non è impostato su "Y", assicurati che sia impostato su "N"
    set_property "MAINTENANCE_MODE" "N"
fi

if [ "$NODE_STATUS" = "WARN" ]; then
    echo "Modalità WARN attiva. controllo da quanto tempo"
    WARN_LAST_UPDATE=$(get_property WARN_LAST_UPDATE)
    WARN_LAST_UPDATE_SECONDS=$(date -d "$WARN_LAST_UPDATE" +%s)
    CURRENT_TIME_SECONDS=$(date +%s)
    # Calcola la differenza in secondi
    DIFF_SECONDS=$((CURRENT_TIME_SECONDS - WARN_LAST_UPDATE_SECONDS))
    # 3600 secondi in un'ora
    if [ "$DIFF_SECONDS" -gt 3600 ]; then
        echo "La differenza è maggiore di un'ora. Aggiornamento necessario."
        # Qui puoi aggiornare il valore della variabile o eseguire altre azioni
        # Ad esempio, aggiornare WARN_LAST_UPDATE con l'orario corrente
        WARN_LAST_UPDATE=$(date "+%Y-%m-%dT%H:%M:%S")
        set_property "WARN_LAST_UPDATE" "$WARN_LAST_UPDATE"
        echo "WARN_LAST_UPDATE aggiornato a: $WARN_LAST_UPDATE"
    else
        echo "La differenza è minore di un'ora. Nessun aggiornamento necessario."
        exit 0
    fi
else
    # Se MAINTENANCE_MODE non esiste o non è impostato su "Y", assicurati che sia impostato su "N"
    set_property "MAINTENANCE_MODE" "N"
fi

# Cerca il processo tramite il nome fornito
PID=$(get_pid)

# Controlla se il PID non è stato trovato
if [ -z "$PID" ]; then
    # Il processo non è in esecuzione, invia una email di notifica
    $SCRIPTS_PATH/send_mail.sh --subject "Processo non in esecuzione"  --body "Il processo per $NODE_NAME non e' in esecuzione. Tentativo di avvio in corso."

    set_property NODE_STATUS WARN
    WARN_LAST_UPDATE=$(date "+%Y-%m-%dT%H:%M:%S")
    set_property WARN_LAST_UPDATE "$WARN_LAST_UPDATE"
    echo "WARN_LAST_UPDATE aggiornato a: $WARN_LAST_UPDATE"

    # Prova ad avviare il processo
    $SCRIPTS_PATH/startup_node.sh --node-name $NODE_NAME

    # Attendi 60 secondi per dare tempo al processo di avviarsi
    sleep 60

    # Controlla nuovamente il PID del processo dopo il tentativo di avvio
    PID=$(get_pid)

    if [ -z "$PID" ]; then
        $SCRIPTS_PATH/send_mail.sh --subject "Impossibile avviare il processo"  --body "Non e' stato possibile avviare il processo per $NODE_NAME dopo il tentativo."
    else
        echo "Il processo è stato avviato correttamente. rimuovo il WARING"
        remove_property "NODE_STATUS"
    fi
else
    echo "Il processo è già in esecuzione."
fi
