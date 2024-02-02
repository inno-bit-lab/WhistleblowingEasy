FROM debian:12-slim

RUN apt-get update -q && \
    apt-get install -y wget lsb-release && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN wget https://raw.githubusercontent.com/inno-bit-lab/WhistleblowingEasy/main/scripts/install.sh -O install-globaleaks.sh
RUN chmod +x install-globaleaks.sh
RUN ./install-globaleaks.sh -y -n

RUN apt-get update -q && \
    apt-get install -y globaleaks && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

EXPOSE 8080
EXPOSE 8443

USER globaleaks

CMD ["/usr/bin/python3", "/usr/bin/globaleaks", "--working-path=/var/globaleaks/", "-n"]
