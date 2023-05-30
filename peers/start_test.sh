#!/bin/bash

echo Start tests...

for i in 1 2
do
	DATE=`date '+%Y%m%d%H%M%S'`
	FOLDER=../experiments/tests/8_peers_30_s3min2_randfail_noswitch_lsa_${DATE}

	echo Start test $i : $DATE

	rm -f peer*/*.log
	rm -f peer*/*.csv
	rm -f peer*/*.out

	for PEER in peer1 peer2 peer3 peer4 peer5 peer6 peer7 peer8
	do
		cd $PEER
		echo Starting peer $PEER
		./startserver.sh > stderr.out &
		cd ..
	done

	echo Wait for test to end...
	sleep 1800
	echo Kill processes
	pkill startserver.sh
	pkill python3
	
	echo Copy logs...
	mkdir -p $FOLDER
	for PEER in peer1 peer2 peer3 peer4 peer5 peer6 peer7 peer8
	do
		cp -r $PEER $FOLDER
	done
done

echo Finished tests 
