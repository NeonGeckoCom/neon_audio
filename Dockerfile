FROM python:3.8-slim as base

LABEL vendor=neon.ai \
    ai.neon.name="neon-audio"

ENV NEON_CONFIG_PATH /config

RUN apt-get update && \
    apt-get install -y \
    alsa-utils \
    libasound2-plugins \
    pulseaudio-utils \
    sox \
    libsox-fmt-mp3 \
    vlc \
    ffmpeg \
    gcc \
    g++ \
    libsndfile1 \
    espeak-ng \
    git  # Added to handle installing plugins from git

RUN apt-get update && \
    apt-get install -y \
    curl \
    gpg

RUN curl https://forslund.github.io/mycroft-desktop-repo/mycroft-desktop.gpg.key | \
    gpg --no-default-keyring --keyring gnupg-ring:/etc/apt/trusted.gpg.d/mycroft-desktop.gpg --import - && \
    chmod a+r /etc/apt/trusted.gpg.d/mycroft-desktop.gpg && \
    echo "deb https://forslund.github.io/mycroft-desktop-repo bionic main" \
    > /etc/apt/sources.list.d/mycroft-mimic.list

# TODO: This is a patch, not a fix; if gpg keys are not updated, build mimic from source
RUN apt update -o Acquire::AllowInsecureRepositories=true
RUN apt -o Acquire::AllowInsecureRepositories=true install -y --allow-unauthenticated \
    mimic

ADD . /neon_audio
WORKDIR /neon_audio

RUN pip install wheel && \
    pip install .[docker]

COPY docker_overlay/ /
RUN chmod ugo+x /root/run.sh

RUN neon-audio install-plugin -f

CMD ["/root/run.sh"]

FROM base as default_model
RUN neon-audio init-plugin