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