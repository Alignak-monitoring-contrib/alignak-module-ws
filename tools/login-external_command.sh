#!/bin/sh

# -----
# Run this script on the alignak1 VM to check the WS - POST /command
# -----

# Extra cUrl arguments
ARGUMENTS=
# Default is normal
VERBOSE_MODE="0"
# Alignak backend URI
ALIGNAK="http://127.0.0.1:7773/ws"
# Alignak host information
HOST_NAME=""
SERVICE_NAME=""
# External command
COMMAND="test"
PARAMETERS=""
# Alignak backend username
USERNAME="admin"
# Alignak backend password
PASSWORD="ipm-France2017"

usage() {
    cat << END

Usage: $0 [-H|--help] [-a|--alignak] [-u|--username] [-p|--password]

 -H (--help)                display this message
 -v (--verbose)             verbose mode
 -a (--alignak)             Alignak WS URI (default is ${ALIGNAK})
 -h (--host_name)           Host name (default is ${HOST_NAME})
 -s (--service_name)        Service name (default is ${SERVICE_NAME})
 -c (--command)             External command (default is ${COMMAND})
 -e (--extra-parameters)    External command parameters (default is ${PARAMETERS})
 -u (--username)            WS username (default is ${USERNAME})
 -p (--password)            WS password (default is ${PASSWORD})

END
}

for i in "$@"
do
case $i in
    -H|--help)
    usage >&1
    exit 0
    ;;
    -v|--verbose)
    VERBOSE_MODE="1"
    shift
    ;;
    -a|--alignak)
    shift
    ALIGNAK="$1"
    shift
    ;;
    -h|--host_name)
    shift
    HOST_NAME="$1"
    shift
    ;;
    -s|--service_name)
    shift
    SERVICE_NAME="$1"
    shift
    ;;
    -c|--command)
    shift
    COMMAND="$1"
    shift
    ;;
    -e|--extra-parameters)
    shift
    PARAMETERS="$1"
    shift
    ;;
    -u|--username)
    shift
    USERNAME="$1"
    shift
    ;;
    -p|--password)
    shift
    PASSWORD="$1"
    shift
    ;;
esac
done


# Login and create an environment variable TOKEN with the user WS token
login_data() {
  cat <<EOF
{
  "username":"$USERNAME","password":"$PASSWORD"
}
EOF
}

TOKEN=`curl -k "${ALIGNAK}/login" -X POST -H 'Content-Type: application/json' -d "$(login_data)" | python2.7 -c "import sys, json ; print json.load ( sys.stdin ) ['_result'][0]"`

#{"_status": "OK", "_result": ["1522151800026-aa365092-9fc5-4d9e-b111-84e37b1f5467"]}
if [ "$VERBOSE_MODE" = "1" ]; then
    echo "User token: ${TOKEN}"

    ARGUMENTS="--verbose -w @curl_format.txt"
fi

# Send the external command
TS=`date +"%s"`
command_data() {
if [ "$HOST_NAME" = "" ]; then
  cat <<EOF
{
    "command": "$COMMAND",
    "parameters": "$PARAMETERS"
}
EOF
else
if [ "$SERVICE_NAME" = "" ]; then
  cat <<EOF
{
    "command": "$COMMAND",
    "host": "$HOST_NAME",
    "parameters": "$PARAMETERS"
}
EOF
else
  cat <<EOF
{
    "command": "$COMMAND",
    "host": "$HOST_NAME",
    "service": "$SERVICE_NAME",
    "parameters": "$PARAMETERS"
}
EOF
fi
fi
}

if [ "$VERBOSE_MODE" = "1" ]; then
    echo "Posted command: $(command_data)"
fi

curl -X POST -H "Content-Type: application/json" --user "${TOKEN}:" -d "$(command_data)" "${ALIGNAK}/command" $ARGUMENTS
