# syntax=docker/dockerfile:1
FROM stable:latest
WORKDIR /app
RUN apt install -y python3 python3-pip openvpn
RUN mkdir -p /dev/net && \
    mknod /dev/net/tun c 10 200 && \
    chmod 600 /dev/net/tun
RUN openvpn --genkey --secret static.key
COPY rtun-routing/ .
COPY torpy-rtun-fork/ torpy-rtun-fork/ 
RUN pip3 install -r requirements.txt
ENV PYTHONPATH=/app/torpy-rtun-fork/
CMD ["/root/peer/startserver.sh"]
EXPOSE 80
