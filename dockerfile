# Use the official multi-platform Ubuntu base image
FROM ubuntu:20.04

# Set environment variables
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_RUN_PORT=5000

# Install necessary packages
RUN apt-get update && apt-get install -y \
    apt-utils \
    python3 \
    python3-pip \
    tor \
    proxychains4 \
    curl \
    nikto \
    unzip \
    whois \
    jq \
    wget \
    chromium-browser

RUN rm -rf /var/lib/apt/lists/*
# Set the working directory
WORKDIR /app

# Copying web-{front-back}end to docker 
COPY . /app
# Copying config files
COPY torrc  /etc/tor/
COPY proxychains4.conf  /etc/

# Install Python dependencies 
RUN pip3 install -r requirements.txt

WORKDIR /tmp
# Installing tools
RUN wget https://github.com/epi052/feroxbuster/releases/download/v2.10.0/x86_64-linux-feroxbuster.zip
RUN unzip x86_64-linux-feroxbuster.zip
RUN mv feroxbuster /usr/bin/
RUN chmod +x /usr/bin/feroxbuster
RUN rm x86_64-linux-feroxbuster.zip

RUN wget https://github.com/michenriksen/aquatone/releases/download/v1.7.0/aquatone_linux_amd64_1.7.0.zip
RUN unzip aquatone_linux_amd64_1.7.0.zip
RUN mv aquatone /usr/bin/
RUN chmod +x /usr/bin/aquatone
RUN rm LICENSE.txt README.md aquatone_linux_amd64_1.7.0.zip

WORKDIR /app

# Expose the port
EXPOSE 5000

ENTRYPOINT service tor start && python3 app.py
