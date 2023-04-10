#!/bin/bash

read -p "Are you sure? (y/N):" input

if ! [[ "$input" =~ y ]]
then
	exit 0
fi


rm -f peer{5,6,7,8}/rtun.log
rm -f peer{5,6,7,8}/router.log
rm -f peer{5,6,7,8}/topology.log
rm -f peer{5,6,7,8}/receive.log
rm -f peer{5,6,7,8}/messages.log
rm -f peer{5,6,7,8}/routed.log
rm -f peer{5,6,7,8}/stderr.out
