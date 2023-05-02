#!/bin/bash

echo Start tests...

for i in 1 2 3 4 5
do
	DATE=`date '+%Y%m%d%H%M%S'`
	FOLDER=/home/vboxuser/Git/imt4905/experiments/tests/5_peers_latency_${DATE}

	echo Start test $i : $DATE


	rm -f peer*/rtun.log
	rm -f peer*/router.log
	rm -f peer*/topology.log
	rm -f peer*/receive.log
	rm -f peer*/messages.log
	rm -f peer*/routed.log
	rm -f peer*/stderr.out
	rm -f peer*/sent.log

	for PEER in peer1 peer5
	do
		cd $PEER
		./startserver.sh > stderr.out &
		cd ..
	done

	echo Wait for test to end...
	sleep 600
	echo Kill processes
	pkill startserver.sh
	pkill python3
	
	echo Copy logs...
	mkdir $FOLDER
	for PEER in peer1 peer5
	do
		cp -r $PEER $FOLDER
	done
done

echo Finished tests 
