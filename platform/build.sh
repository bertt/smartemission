#!/bin/bash
#
# This build all assets (mainly Docker images) for SmartEmission Data Platform
# You must first have installed Docker, or better have run bootstrap.sh
#
# Just van den Broecke - 2016
#

script_name=${0##*/}
script_dir=${0%/*}

DOCKER_HOME=${script_dir}/../docker
DOCKERS="apache2 geoserver sos52n postgis stetl"

for DOCK in ${DOCKERS}
do
  pushd ${DOCKER_HOME}/${DOCK}
  ./build.sh
  popd
done

echo "READY: now run ./init-databases.sh to create and init all databases (use with CARE as it DELETES all existing data!)"
