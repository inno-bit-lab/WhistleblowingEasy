#!/bin/bash

# Valori di default
BASE_PATH=$HOME
GIT_HUB_URL="https://github.com/inno-bit-lab/WhistleblowingEasy.git"

# Definisco i path
APP_PATH="${APP_PATH:-$BASE_PATH/app/wbe}"
REPOS_PATH="${REPOS_PATH:-$APP_PATH/repos}"

# Print values
echo "APP PATH: $APP_PATH"
echo "REPOS PATH: $REPOS_PATH"

#Creo cartella app e repos
mkdir -p $REPOS_PATH

#mi sposto in repos
cd $REPOS_PATH

# Controlla se GIT_HUB_URL è vuota
if [ -z "$GIT_HUB_URL" ]; then
    echo "La variabile GIT_HUB_URL è vuota. Impostare l'URL del repository GitHub."
    exit 1
fi

# Esegui il comando git clone
echo "Clonazione del repository da $GIT_HUB_URL..."
git clone $GIT_HUB_URL

# Controlla se il comando git clone ha avuto successo
if [ $? -eq 0 ]; then
    echo "Clonazione completata con successo."
else
    echo "Errore durante la clonazione del repository."
    exit 1
fi

