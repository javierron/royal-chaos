#!/bin/bash
chaosorca experiment start --name ttorrent-ubuntu --pid-name "java -jar ttorrent-2.0-client.jar -u 4000 -d 4000 -o output -s 60 ubuntu-18.04.2-desktop-amd64.iso.torrent" --start-cmd "$PWD/run.sh" --stop-cmd "$PWD/stop.sh"
