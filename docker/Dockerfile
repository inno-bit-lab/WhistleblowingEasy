FROM debian:12-slim

RUN apt-get update -q && \
    apt-get dist-upgrade -y && \
    apt-get install -y apt-utils wget lsb-release && \
    wget https://raw.githubusercontent.com/inno-bit-lab/WhistleblowingEasy/main/scripts/install.sh && \
    chmod +x install-globaleaks.sh && \
    ./install-globaleaks.sh -y -n && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

EXPOSE 8080 8443

USER globaleaks

CMD ["/usr/bin/python3", "/usr/bin/globaleaks", "--working-path=/var/globaleaks/", "-n"]
