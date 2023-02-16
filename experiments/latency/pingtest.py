import json
import pingparsing
import time

ping_parser = pingparsing.PingParsing()
transmitter = pingparsing.PingTransmitter()
transmitter.destination = "167.179.99.77"
transmitter.count = 3

while True:
    result = transmitter.ping()

    with open('pingtest.out', 'a') as fh:
        s = str(time.time()) +";"+ transmitter.destination +";"+ str(round(ping_parser.parse(result).as_dict()['rtt_avg']))+"\n"
        fh.write(s)

    time.sleep(15)
