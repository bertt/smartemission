#!/bin/bash
#
# Run the InfluxDB from https://hub.docker.com/_/influxdb/.
#

LOG_DIR="/var/smartem/log/influxdb"
DATA_DIR="/var/smartem/data/influxdb"
NAME="influxdb"
IMAGE="influxdb:1.1.1"

sudo mkdir -p ${DATA_DIR}
sudo mkdir -p ${LOG_DIR}

script_dir=${0%/*}
pushd ${script_dir}
script_dir=$PWD
popd

VOL_MAP="-v ${DATA_DIR}:/var/lib/influxdb -v ${LOG_DIR}:/var/log/influxdb -v ${script_dir}/config/influxdb.conf:/etc/influxdb/influxdb.conf:ro"

# 8083 is admin, 8086 API
PORT_MAP="-p 8083:8083 -p 8086:8086"

# Stop and remove possibly old containers
sudo docker stop ${NAME} > /dev/null 2>&1
sudo docker rm ${NAME} > /dev/null 2>&1

# Finally run, keeping DB-data, config and logs on the host
sudo docker run --restart=always --name ${NAME} ${PORT_MAP} ${VOL_MAP} -d -t ${IMAGE} -config /etc/influxdb/influxdb.conf

# generate conf: docker run --rm influxdb influxd config > influxdb.conf
# create db: curl -G http://localhost:8086/query --data-urlencode "q=CREATE DATABASE mydb"