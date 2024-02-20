#!/bin/bash

# Imposta la variabile BASE_PATH e definisce APP_PATH di conseguenza
BASE_PATH="$HOME"
APP_PATH="$BASE_PATH/app/wbe"

# Valori di default per i parametri mancanti
DEFAULT_HTTP_PORT=8080
DEFAULT_HTTPS_PORT=8443

# Parsing degli argomenti passati allo script
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --node-name) NODE_NAME="$2"; shift ;;
        --working-path) WORKING_PATH="$2"; shift ;;
        --http-port) HTTP_PORT="$2"; shift ;;
        --https-port) HTTPS_PORT="$2"; shift ;;
        *) echo "Opzione non riconosciuta: $1" >&2; exit 1 ;;
    esac
    shift
done

# Controllo che il --node-name sia stato fornito
if [[ -z "$NODE_NAME" ]]; then
    echo "Errore: Il parametro --node-name è obbligatorio." >&2
    exit 1
fi

# Applica i valori di default se necessario
WORKING_PATH="${WORKING_PATH:-$APP_PATH/$NODE_NAME/appdata}"
HTTP_PORT="${HTTP_PORT:-$DEFAULT_HTTP_PORT}"
HTTPS_PORT="${HTTPS_PORT:-$DEFAULT_HTTPS_PORT}"

# Crea la directory WORKING_PATH se non esiste
if [[ ! -d "$WORKING_PATH" ]]; then
    echo "Creazione della directory $WORKING_PATH..."
    mkdir -p "$WORKING_PATH"
fi

# Copia le directory client e backend
cp -r "$APP_PATH/repos/WhistleblowingEasy/client" "$APP_PATH/$NODE_NAME/"
cp -r "$APP_PATH/repos/WhistleblowingEasy/backend" "$APP_PATH/$NODE_NAME/"

# Si sposta nella directory client e esegue i comandi richiesti
cd "$APP_PATH/$NODE_NAME/client" || exit
npm install -g grunt-cli
npm install -d
grunt copy:sources

# Controllo se i comandi sono stati eseguiti con successo
if [[ $? -ne 0 ]]; then
    echo "Errore durante la configurazione del client." >&2
    exit 1
fi

# Si sposta nella directory backend e esegue i comandi richiesti
cd ../backend || exit
python3 -m venv env
source env/bin/activate
export PATH="$APP_PATH/$NODE_NAME/backend/env/bin:$APP_PATH/$NODE_NAME/backend/bin:$PATH"
pip3 install -r requirements.txt

# Controllo se i comandi sono stati eseguiti con successo
if [[ $? -ne 0 ]]; then
    echo "Errore durante la configurazione del backend." >&2
    exit 1
fi

# Salvataggio delle variabili di configurazione in un file node.conf
CONFIG_FILE="$APP_PATH/$NODE_NAME/node.conf"
echo "Salvataggio della configurazione in $CONFIG_FILE..."

# Crea o sovrascrive il file di configurazione con le variabili attuali
echo "NODE_NAME=$NODE_NAME" > "$CONFIG_FILE"
echo "WORKING_PATH=$WORKING_PATH" >> "$CONFIG_FILE"
echo "HTTP_PORT=$HTTP_PORT" >> "$CONFIG_FILE"
echo "HTTPS_PORT=$HTTPS_PORT" >> "$CONFIG_FILE"

# Verifica se il file di configurazione è stato creato con successo
if [[ -f "$CONFIG_FILE" ]]; then
    echo "Configurazione salvata con successo in $CONFIG_FILE."
else
    echo "Errore nel salvataggio della configurazione in $CONFIG_FILE." >&2
    exit 1
fi



echo "Configurazione completata con successo."
