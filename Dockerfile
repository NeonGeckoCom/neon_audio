FROM python:3.8-slim

LABEL vendor=neon.ai \
    ai.neon.name="neon-audio"

ENV NEON_CONFIG_PATH /config

RUN  apt-get update && \
     apt-get install -y \
     curl \
     gpg

RUN  curl https://forslund.github.io/mycroft-desktop-repo/mycroft-desktop.gpg.key | \
     gpg --no-default-keyring --keyring gnupg-ring:/etc/apt/trusted.gpg.d/mycroft-desktop.gpg --import - && \
     chmod a+r /etc/apt/trusted.gpg.d/mycroft-desktop.gpg && \
     echo "deb http://forslund.github.io/mycroft-desktop-repo bionic main" \
     > /etc/apt/sources.list.d/mycroft-mimic.list

RUN apt-get update && \
    apt-get install -y \
    alsa-utils \
    libasound2-plugins \
    pulseaudio-utils \
    sox \
    vlc \
    ffmpeg \
    mimic \
    gcc \
    g++ \
    libsndfile1 \
    espeak \
    espeak-ng \
    git  # TODO: Only for testing plugins

ADD . /neon_audio
WORKDIR /neon_audio

RUN pip install wheel && \
    pip install .[docker]

COPY docker_overlay/ /
RUN chmod ugo+x /root/run.sh

CMD ["/root/run.sh"]