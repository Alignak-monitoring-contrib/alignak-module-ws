#!/bin/sh

# -----
# Run this script on the alignak1 VM to check the WS - PATCH /host
# -----

# Extra cUrl arguments
ARGUMENTS=
# Default is normal
VERBOSE_MODE="0"
# Alignak backend URI
ALIGNAK="http://127.0.0.1:7773/ws"
# Alignak host information
HOST_NAME="test_host"
HOST_TEMPLATE=""
HOST_REALM=""
# Alignak backend username
USERNAME="admin"
# Alignak backend password
PASSWORD="ipm-France2017"

usage() {
    cat << END

Usage: $0 [-H|--help] [-a|--alignak] [-u|--username] [-p|--password]

 -H (--help)            display this message
 -v (--verbose)         verbose mode
 -a (--alignak)         Alignak WS URI (default is ${ALIGNAK})
 -h (--host_name)       Host name (default is ${HOST_NAME})
 -t (--host_template)   Host creation (only...) template (default is ${HOST_TEMPLATE})
 -r (--host_realm)      Host creation (only...) realm (default is ${HOST_REALM})
 -u (--username)        WS username (default is ${USERNAME})
 -p (--password)        WS password (default is ${PASSWORD})

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
    -t|--host_template)
    shift
    HOST_TEMPLATE="$1"
    shift
    ;;
    -r|--host_realm)
    shift
    HOST_REALM="$1"
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

# Patch an host heartbeat
TS=`date +"%s"`
heartbeat_data() {
  cat <<EOF
{
    "name": "$HOST_NAME",
    "active_checks_enabled": false,
    "passive_checks_enabled": true,
    "template": {
        "alias": "$HOST_NAME",
        "_realm": "simulation",
        "_sub_realm": false,
        "_templates": ["$HOST_TEMPLATE"]
    }
}
EOF
}
if [ "$VERBOSE_MODE" = "1" ]; then
    echo "Posted data: $(heartbeat_data)"
fi
curl -X PATCH -H "Content-Type: application/json" --user "${TOKEN}:" -d "$(heartbeat_data)" "${ALIGNAK}/host" $ARGUMENTS

#{"_status": "OK", "_feedback": {"active_checks_enabled": false, "freshness_threshold": 1200, "passive_checks_enabled": true, "check_interval": 60, "retry_interval": 0, "name": "test_host_fred"}}

# Patch an host heartbeat+livestate
TS=`date +"%s"`
livestate_data() {
  cat <<EOF
{
    "name": "$HOST_NAME",
    "active_checks_enabled": false,
    "passive_checks_enabled": true,
    "template": {
        "alias": "$HOST_NAME",
        "_realm": "simulation",
        "_sub_realm": false,
        "_templates": ["$HOST_TEMPLATE"]
    },
    "livestate": [{
        "timestamp": "$TS",
        "state": "up",
        "output": "Simulated host output...",
        "long_output": "Simulated host long output...",
        "perf_data": "Uptime=696"
    }]
}
EOF
}
if [ "$VERBOSE_MODE" = "1" ]; then
    echo "Posted data: $(livestate_data)"
fi
curl -X PATCH -H "Content-Type: application/json" --user "${TOKEN}:" -d "$(livestate_data)" "${ALIGNAK}/host" $ARGUMENTS

#{"_status": "OK", "_feedback": {"active_checks_enabled": false, "freshness_threshold": 1200, "passive_checks_enabled": true, "check_interval": 60, "retry_interval": 0, "name": "test_host_fred"}}

# Patch an host heartbeat+variables+livestate
TS=`date +"%s"`
livestate_variables_data() {
  cat <<EOF
{
    "name": "$HOST_NAME",
    "active_checks_enabled": false,
    "passive_checks_enabled": true,
    "template": {
        "alias": "$HOST_NAME",
        "_realm": "simulation",
        "_sub_realm": false,
        "_templates": ["$HOST_TEMPLATE"]
    },
    "variables": {
        "first_name": "Fred",
        "Last name": "Mohier",
        "packages": [
            {"id": "identifier", "name": "Package 2", "other": 1},
            {"id": "identifier", "name": "Package 1", "other": 1}
        ]
    },
    "livestate": [{
        "timestamp": "$TS",
        "state": "up",
        "output": "Simulated host output...",
        "long_output": "Simulated host long output...",
        "perf_data": "Uptime=696"
    }]
}
EOF
}
if [ "$VERBOSE_MODE" = "1" ]; then
    echo "Posted data: $(livestate_variables_data)"
fi
curl -X PATCH -H "Content-Type: application/json" --user "${TOKEN}:" -d "$(livestate_variables_data)" "${ALIGNAK}/host" $ARGUMENTS

# Patch an host heartbeat+variables+livestate+services
TS=`date +"%s"`
livestate_variables_services_data() {
  cat <<EOF
{
    "name": "$HOST_NAME",
    "active_checks_enabled": false,
    "passive_checks_enabled": true,
    "template": {
        "alias": "$HOST_NAME",
        "_realm": "simulation",
        "_sub_realm": false,
        "_templates": ["$HOST_TEMPLATE"]
    },
    "variables": {
        "first_name": "Fred",
        "Last name": "Mohier",
        "packages": [
            {"id": "identifier", "name": "Package 2", "other": 1},
            {"id": "identifier", "name": "Package 1", "other": 1}
        ]
    },
    "livestate": [{
        "timestamp": "$TS",
        "state": "up",
        "output": "Simulated host output...",
        "long_output": "Simulated host long output...",
        "perf_data": "Uptime=696"
    }],
    "services":[{
        "name": "test_service",
        "livestate": [{
            "timestamp": "$TS",
            "state": "ok",
            "output": "Output check ...",
            "long_output": "Long output...","perf_data": "counter=1"
        },{
            "timestamp": "$TS",
            "state": "ok",
            "output": "Output check ...",
            "long_output": "Long output...","perf_data": "counter=2"
        }]
    }]
}
EOF
}
if [ "$VERBOSE_MODE" = "1" ]; then
    echo "Posted data: $(livestate_variables_services_data)"
fi
curl -X PATCH -H "Content-Type: application/json" --user "${TOKEN}:" -d "$(livestate_variables_services_data)" "${ALIGNAK}/host" $ARGUMENTS


