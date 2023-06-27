FROM python:3.8-slim as base

LABEL vendor=neon.ai \
    ai.neon.name="neon-audio"

ENV OVOS_CONFIG_BASE_FOLDER neon
ENV OVOS_CONFIG_FILENAME neon.yaml

RUN  apt-get update && \
     apt-get install -y \
     curl \
     gpg

RUN  curl https://forslund.github.io/mycroft-desktop-repo/mycroft-desktop.gpg.key | \
     gpg --no-default-keyring --keyring gnupg-ring:/etc/apt/trusted.gpg.d/mycroft-desktop.gpg --import - && \
     chmod a+r /etc/apt/trusted.gpg.d/mycroft-desktop.gpg && \
     echo "deb http://forslund.github.io/mycroft-desktop-repo bionic main" \
     > /etc/apt/sources.list.d/mycroft-mimic.list

RUN apt update && \
    apt install -y \
    alsa-utils \
    libasound2-plugins \
    pulseaudio-utils \
    sox \
    libsox-fmt-mp3 \
    vlc \
    ffmpeg \
    mimic \
    gcc \
    g++ \
    libsndfile1 \
    espeak-ng \
    git  # Added to handle installing plugins from git

ADD . /neon_audio
WORKDIR /neon_audio

RUN pip install wheel && \
    pip install .[docker] --extra-index-url https://download.pytorch.org/whl/cpu

COPY docker_overlay/ /
RUN chmod ugo+x /root/run.sh

RUN neon-audio install-plugin -f

CMD ["/root/run.sh"]

FROM base as default_model
RUN neon-audio init-plugin