#!/bin/bash

get_property() {
    local PROPERTY="$1"
    local CONFIG_FILE="$NODE_PATH/node.conf"
    grep "^$PROPERTY=" "$CONFIG_FILE" | cut -d'=' -f2
}

set_property() {
    local PROPERTY="$1"
    local VALUE="$2"
    local CONFIG_FILE="$NODE_PATH/node.conf"
    if grep -q "^$PROPERTY=" "$CONFIG_FILE"; then
        sed -i "s/^$PROPERTY=.*/$PROPERTY=$VALUE/" "$CONFIG_FILE"
    else
        echo "$PROPERTY=$VALUE" >> "$CONFIG_FILE"
    fi
}

remove_property() {
    local PROPERTY="$1"
    local CONFIG_FILE="$NODE_PATH/node.conf"
    sed -i "/^$PROPERTY=/d" "$CONFIG_FILE"
}

get_pid() {
    ps aux | grep "python bin/globaleaks -n --working-path=" | grep $NODE_NAME | grep -v grep | awk '{print $2}'
}
