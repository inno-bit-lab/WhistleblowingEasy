#!/bin/bash

usage() {
    echo "Usage: $0 --subject Subject --body Body"
    exit 1
}

# Inizializza le variabili per subject e body
SUBJECT=""
BODY=""

# Analizza gli argomenti della riga di comando
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --subject) SUBJECT="$2"; shift ;; # Trova --subject e imposta il valore successivo
        --body) BODY="$2"; shift ;; # Trova --body e imposta il valore successivo
        *) echo "Opzione non riconosciuta: $1" ;; # Gestisce gli argomenti non riconosciuti
    esac
    shift # Passa all'argomento successivo
done

# Controlla se sia subject che body sono stati forniti
if [[ -z "$SUBJECT" ]] || [[ -z "$BODY" ]]; then
    usage
fi

#DIST_LIST="g.maldarelli@innobitlab.it,a.addante@innobitlab.it"
DIST_LIST="g.maldarelli@innobitlab.it"
echo -e "Subject: [WBE-MONITOR] $SUBJECT\n\n$BODY" | msmtp $DIST_LIST