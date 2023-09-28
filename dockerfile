# Use the official multi-platform Ubuntu base image
FROM ubuntu:20.04

# Set environment variables
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_RUN_PORT=5000

# Install necessary packages
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    tor \
    proxychains4 \
    curl \
    sudo \
    lolcat \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy your application code to the container
COPY . /app

# Install Python dependencies
RUN pip3 install -r requirements.txt

# Expose the port
EXPOSE 5000

# Start Tor service and run Flask
CMD /bin/sh -c "echo 'socks5 127.0.0.1 9050' >> /etc/proxychains4.conf && \
    echo 'SocksPort 9050' > /etc/tor/torrc && \
    echo 'CookieAuthentication 1' >> /etc/tor/torrc && \
    echo 'HiddenServiceDir /var/lib/tor/hidden_service/' >> /etc/tor/torrc && \
    echo 'HiddenServicePort 80 127.0.0.1:5000' >> /etc/tor/torrc && \
    echo 'HiddenServiceVersion 3' >> /etc/tor/torrc && \
    echo 'HiddenServiceMaxStreams 100' >> /etc/tor/torrc && \
    echo 'CircuitBuildTimeout 10' >> /etc/tor/torrc && \
    echo 'KeepalivePeriod 60 seconds' >> /etc/tor/torrc && \
    echo 'Log notice file /var/log/tor/notices.log' >> /etc/tor/torrc && \
    service tor start && python3 app.py"