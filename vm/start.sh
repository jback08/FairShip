#!/bin/bash
SCRIPT_NAME=$0
echo $BASH_SOURCE
[[ -z "SCRIPT_NAME" || "$SCRIPT_NAME" == "bash" ]] && SCRIPT_NAME=$BASH_SOURCE
BASEDIR=$(echo $(cd $(dirname "$SCRIPT_NAME")/.. && pwd -P))
source $BASEDIR/vm/_common.sh

if [ "$1" = "diag" ] ; then
    echo "=== DIAGNOSTIC ==="
    uname -a
    top -l 1 | head
    sw_vers -productVersion 
    which vagrant
    vagrant --version
    which docker
    docker --version
    cat /etc/resolv.conf
    df -h
    netstat -nr
    ifconfig -a
    nslookup cdn-registry-1.docker.io
    # traceroute -q 2 -m 25 cdn-registry-1.docker.io
    ping -c 3 cdn-registry-1.docker.io
    curl https://cdn-registry-1.docker.io/
    echo
    echo "=== END OF DIAGNOSTIC ==="
    cd $BASEDIR/diag
    vagrant up --provider=docker
    exit
fi

if [ "$SYSTEM" = "Darwin" ] ; then
    source $BASEDIR/vm/_start_boot2docker.sh
elif [ "$SYSTEM" = "Linux" ] ; then
   docker pull $IMAGE
else
    export VAGRANT_CWD=$BASEDIR
    export VAGRANT_DOTFILE_PATH=$BASEDIR
    vagrant up --provider=docker
fi

