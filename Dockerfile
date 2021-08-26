FROM python:3.8

ADD . /neon_audio
WORKDIR /neon_audio


RUN curl https://forslund.github.io/mycroft-desktop-repo/mycroft-desktop.gpg.key | \
  apt-key add - 2>/dev/null && \
  echo "deb http://forslund.github.io/mycroft-desktop-repo bionic main" \
  > /etc/apt/sources.list.d/mycroft-mimic.list && \
  apt-get update && \
  apt-get install -y alsa-utils libasound2-plugins mpg123 pulseaudio-utils mimic vlc && \
  pip install \
    wheel \
    . \
    git+https://github.com/neongeckocom/neon-tts-plugin-mozilla_local \
    git+https://github.com/neongeckocom/neon-tts-plugin-mozilla_remote

RUN useradd -ms /bin/bash neon
USER neon

COPY docker_overlay/asoundrc /home/neon/.asoundrc
COPY docker_overlay/mycroft.conf /home/neon/.mycroft/mycroft.conf

RUN mkdir -p /home/neon/.config/pulse && \
  pip install \
    pychromecast==3.2.2 \
    python-vlc==1.1.2 \
    git+https://github.com/JarbasAl/py_mplayer.git && \
  rm -rf ~/.cache

CMD ["neon_audio_client"]