FROM python:3.8

LABEL vendor=neon.ai \
    ai.neon.name="neon-audio"

ADD . /neon_audio
WORKDIR /neon_audio


RUN curl https://forslund.github.io/mycroft-desktop-repo/mycroft-desktop.gpg.key | \
  apt-key add - 2>/dev/null && \
  echo "deb http://forslund.github.io/mycroft-desktop-repo bionic main" \
  > /etc/apt/sources.list.d/mycroft-mimic.list && \
  apt-get update && \
  apt-get install -y alsa-utils libasound2-plugins pulseaudio-utils mimic sox vlc && \
  pip install wheel && \
  pip install .[docker]

RUN useradd -ms /bin/bash neon
USER neon

COPY docker_overlay/asoundrc /home/neon/.asoundrc
COPY docker_overlay/mycroft.conf /home/neon/.mycroft/mycroft.conf

RUN mkdir -p /home/neon/.config/pulse && \
    mkdir -p /home/neon/.config/neon && \
    mkdir -p /home/neon/.local/share/neon && \
    rm -rf ~/.cache

CMD ["neon_audio_client"]