#!/bin/bash

read -p "Are you sure? (y/N):" input

if ! [[ "$input" =~ y ]]
then
	exit 0
fi


rm -f peer*/rtun.log
rm -f peer*/router.log
rm -f peer*/topology.log
rm -f peer*/receive.log
rm -f peer*/messages.log
rm -f peer*/stderr.out
