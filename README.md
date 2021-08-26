# Neon Audio
Audio Module for Neon Core. This module can be treated as a replacement for the
[mycroft-core](https://github.com/MycroftAI/mycroft-core) speech module. This module handles input text, performs TTS, 
and optionally returns the audio or plays it back locally.

## Neon Enhancements
`neon-audio` extends `mycroft-audio` with the following added functionality:
* Support for translated output languages
* Support for multiple language spoken responses (multiple users and/or multi-language users)
* Messagebus API listeners to handle outside requests for TTS
* Arbitrary configuration supported by passing at module init

## Compatibility
Mycroft TTS plugins are compatible with `neon-speech`.

## Running in Docker
The included `Dockerfile` may be used to build a docker container for the neon_audio module. The below command may be used
to start the container.

```
docker run -d \
--network=host \
-v ~/.local/share/neon:/home/neon/.local/share/neon:rw \
-v ~/.config/neon:/home/neon/.config/neon:rw \
-v ~/.local/share/tts:/home/neon/.local/share/tts \
-v ~/.config/pulse/cookie:/home/mycroft/.config/pulse/cookie:ro \
-v ${XDG_RUNTIME_DIR}/pulse:${XDG_RUNTIME_DIR}/pulse:ro \
--device=/dev/snd:/dev/snd \
-e PULSE_SERVER=unix:${XDG_RUNTIME_DIR}/pulse/native \
-e PULSE_COOKIE=/home/neon/.config/pulse/cookie \
neon_audio

```