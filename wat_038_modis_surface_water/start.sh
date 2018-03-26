#!/bin/sh

#Change the NAME variable with the name of your script
NAME=$(basename $(pwd))
LOG=${LOG:-udp://localhost}

docker build -t $NAME --build-arg NAME=$NAME .
docker run --log-driver=syslog --log-opt syslog-address=$LOG --log-opt tag=$NAME \
  -v $(pwd)/data:/opt/$NAME/data \
  -v $(pwd)/mosaics:/opt/$NAME/mosaics \
  --env-file .env --rm $NAME
