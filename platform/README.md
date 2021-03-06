# Smart Emission Data Platform

Global resources to bootstrap, build, initialize, run and maintain the 
entire Smart Emission Data Platform.

Documentation for the Smartemission Data Platform can be found at: http://smartplatform.readthedocs.org

On a clean Ubuntu Linux system the whole platform can be up and running within 15 minutes.
The entire platform will run as a System service from `/etc/init.d/smartem` thus surviving reboots.

"Running" the Platform entails running the Docker images, scheduling regular tasks (cron) for ETL and backup.
All is controlled using the systemd standard Linux service "smartem".

## Installation

From this dir do as `root`: 

    ./bootstrap.sh - makes empty Ubuntu system ready for Docker and Platform
    ./build.sh  - builds all Docker images
    ./init-databases.sh  - initializes all (ETL) databases
    ./install.sh  - installs system service "smartem"

Then use the standard Linux "service" commands:

    service smartem status
    service smarted stop
    service smartem start
    etc

Also `/etc/init.d/smartem start| stop | status` should work.

Test Databases once in order to test ETL (NB the `postgis` Docker container needs to be running!)
	
	# test ETL using .sh scripts
	./last.sh
	./harvester.sh
	./refiner.sh
	./extractor.sh
			
## Administration

All dynamic data (config, databases, logfiles) is kept outside the Docker images. Most under `/var/smartem`.

An admin web-interface (see `services/web/site/adm`) is present at `/adm`.
Create the file `htpasswd` once under `/opt/geonovum/smartem/git/services/web/config/admin` 
using the command `htpasswd`. 
