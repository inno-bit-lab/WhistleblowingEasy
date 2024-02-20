#!/bin/bash

# Inizializza la variabile NODE_NAME vuota
NODE_NAME=""

# Analizza gli argomenti della riga di comando
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --node-name) NODE_NAME="$2"; shift ;;
        *) echo "Opzione non riconosciuta: $1" >&2; exit 1 ;;
    esac
    shift
done

# Verifica che NODE_NAME sia stato fornito
if [ -z "$NODE_NAME" ]; then
    echo "Errore: Il parametro --node-name è obbligatorio."
    exit 1
fi

# Valori di default
. ~/.common_wbe

. $SCRIPTS_PATH/common_wbe.sh --node-name node1

# Verifica l'esistenza del file di configurazione
if [ ! -f "$CONFIG_FILE" ]; then
    echo "File di configurazione $CONFIG_FILE non trovato."
    exit 1
fi

# Leggi le variabili di configurazione dal file
source "$CONFIG_FILE"

# Verifica che le variabili siano state caricate correttamente
if [ -z "$WORKING_PATH" ] || [ -z "$HTTP_PORT" ] || [ -z "$HTTPS_PORT" ]; then
    echo "Errore nella lettura delle variabili di configurazione."
    exit 1
fi

# Sposta nella directory backend
cd "$NODE_PATH/backend" || exit

# Attiva l'ambiente virtuale Python
source env/bin/activate

# Installa le dipendenze
pip3 install -r requirements.txt

# Avvia il processo in background e reindirizza l'output
bin/globaleaks -n --working-path="$WORKING_PATH"  2>&1 &
#--http-port "$HTTP_PORT" --https-port "$HTTPS_PORT"
echo "Processo avviato con successo."
