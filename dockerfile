# Use the official Kali Linux base image
FROM kalilinux/kali-rolling

# Set the timezone 
ENV TZ=America/New_York

# Set environment variables
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_RUN_PORT=5000

ENV PATH="/root/.local/bin:$PATH"

# Install tzdata and configure the timezone
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Install necessary packages
RUN apt-get update && apt-get install -y \
    apt-utils \
    python3 \
    python3-pip \
    tor \
    proxychains4 \
    curl \
    unzip \
    whois \
    jq \
    wget \
    chromium \
    chromium-driver \
    gowitness

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Set the working directory
WORKDIR /app

COPY . /app

# Copying config files
COPY torrc /etc/tor/
COPY proxychains4.conf /etc/

# Install Python dependencies via uv
RUN uv pip install -r requirements.txt --system

WORKDIR /tmp

# Installing feroxbuster
RUN wget https://github.com/epi052/feroxbuster/releases/download/v2.10.0/x86_64-linux-feroxbuster.zip
RUN unzip x86_64-linux-feroxbuster.zip
RUN mv feroxbuster /usr/bin/
RUN chmod +x /usr/bin/feroxbuster
RUN rm x86_64-linux-feroxbuster.zip

RUN service tor start
RUN chmod 644 /run/tor/control.authcookie

WORKDIR /app

# Expose the port
EXPOSE 5000

ENTRYPOINT service tor restart && python3 app.py