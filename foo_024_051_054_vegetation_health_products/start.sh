#!/bin/sh

#Change the NAME variable with the name of your script
NAME=vegetation_health_products
LOG=${LOG:-udp://localhost}

docker build -t $NAME --build-arg NAME=$NAME .
docker run --log-driver=syslog --log-opt syslog-address=$LOG --log-opt tag=$NAME --env-file .env -v $(pwd)/data:/opt/$NAME/data --rm $NAME python main.py
