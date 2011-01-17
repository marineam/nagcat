#!/bin/bash

DIR=./ssl
DAYS="-days 7305"
CAcert=$DIR/ca.cert
CAkey=$DIR/ca.key
CAreq=$DIR/ca.req

usage() {
    echo "$0 [-newca|-newcert name]"
}

case "$1" in
    -newca)
        set -e
        mkdir -p $DIR
        openssl genrsa -out $CAkey 2048
        openssl req -new -key $CAkey -out $CAreq
        openssl x509 -req $DAYS -extensions v3_ca \
            -signkey $CAkey -in $CAreq -out $CAcert
        rm -f $CAreq
        ;;
    -newcert)
        if [ -z "$2" ]; then
            usage
            exit 1
        fi
        set -e
        openssl genrsa -out $DIR/$2.key 2048
        openssl req -new -key $DIR/$2.key -out $DIR/$2.req
        openssl x509 -req $DAYS -extensions v3_req \
            -CA $CAcert -CAkey $CAkey -CAcreateserial \
            -in $DIR/$2.req -out $DIR/$2.cert
        cat $DIR/$2.key $DIR/$2.cert > $DIR/$2.pem
        rm -f $DIR/$2.req
        ;;
    *)
        usage
        ;;
esac
