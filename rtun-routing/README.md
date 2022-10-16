
```
usage: rtun.py [-h] [-r RELAY] [-g GUARD] [-l] [-c] [-k COOKIE] [-p] [-t TUNNEL_NAME] [-n NAMESPACE] [-i ID]
               [-d DID] [-x]

optional arguments:
  -h, --help            show this help message and exit
  -r RELAY, --relay RELAY
                        relay to be used as rendezvous point
  -g GUARD, --guard GUARD
                        optional router to be used as guard node
  -l, --listen          create the rendezvous point an wait
  -c, --connect         connect to an already 
                        established rendezvous point
  -k COOKIE, --cookie COOKIE
                        a 20 byte rendezvous cookie
  -p, --pairwise        select relay automatically 
                        using the pairwise algorithm
  -t TUNNEL_NAME, --tunnel_name TUNNEL_NAME
                        name of the tunnel, default is 
                        the two peers name concatenated
  -n NAMESPACE, --namespace NAMESPACE
                        secret key used to differentiate
                        between different nets
  -i ID, --id ID        id of our own client(used for 
                        addressing and port allocation)
  -d DID, --did DID     destination id
  -x, --dummy           do not connect, only test
```
