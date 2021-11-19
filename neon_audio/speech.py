# NEON AI (TM) SOFTWARE, Software Development Kit & Application Development System
# All trademark and other rights reserved by their respective owners
# Copyright 2008-2021 Neongecko.com Inc.
#
# Redistribution and use in source and binary forms, with or without modification, are permitted provided that the
# following conditions are met:
# 1. Redistributions of source code must retain the above copyright notice, this list of conditions
#    and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions
#    and the following disclaimer in the documentation and/or other materials provided with the distribution.
# 3. Neither the name of the copyright holder nor the names of its contributors may be used to endorse or promote
#    products derived from this software without specific prior written permission.

# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES,
# INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE
# USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import time
from threading import Lock
from typing import Optional

from mycroft.tts.remote_tts import RemoteTTSTimeoutException
from mycroft_bus_client import Message, MessageBusClient
from neon_utils.configuration_utils import NGIConfig, get_neon_audio_config
from ovos_plugin_manager.tts import TTS
from ovos_utils.log import LOG
from ovos_utils.signal import check_for_signal

from neon_audio.tts import TTSFactory

try:
    from ovos_tts_plugin_mimic import MimicTTSPlugin
except ImportError:
    MimicTTSPlugin = None
from mycroft.metrics import report_timing, Stopwatch

bus: Optional[MessageBusClient] = None  # Mycroft messagebus connection
config: Optional[NGIConfig] = None
tts: Optional[TTS] = None
mimic_fallback_obj: Optional[TTS] = None
tts_hash = None
lock = Lock()
speak_muted = False

_last_stop_signal = 0


def handle_get_tts(message):
    """
    Handle a request to get TTS only
    :param message: Message associated with request
    """
    global tts
    text = message.data.get("text")
    ident = message.context.get("ident") or "neon.get_tts.response"
    if not message.data.get("speaker"):
        LOG.warning(f"No speaker data with request, core defaults will be used.")
    if text:
        if not isinstance(text, str):
            bus.emit(message.reply(ident, data={"error": f"text is not a str: {text}"}))
            return
        try:
            responses = tts._get_multiple_tts(message)
            # TODO: Consider including audio bytes here in case path is inaccessible DM
            # responses = {lang: {sentence: text, male: Optional[path], female: Optional[path}}
            bus.emit(message.reply(ident, data=responses))
        except Exception as e:
            LOG.error(e)
            bus.emit(message.reply(ident, data={"error": repr(e)}))
    else:
        bus.emit(message.reply(ident, data={"error": "No text provided."}))


def handle_speak(message):
    """Handle "speak" message

    Parse sentences and invoke text to speech service.
    """
    # Configuration.set_config_update_handlers(bus)
    global _last_stop_signal

    # if the message is targeted and audio is not the target don't
    # don't synthezise speech
    message.context = message.context or {}
    if message.context.get('destination') and not \
            ('debug_cli' in message.context['destination'] or
             'audio' in message.context['destination']):
        LOG.warning("speak message not targeted at audio module")
        # return

    # Get conversation ID
    message.context['ident'] = message.context.get("ident", "unknown")

    with lock:
        stopwatch = Stopwatch()
        stopwatch.start()
        utterance = message.data['utterance']
        mute_and_speak(utterance, message)
        stopwatch.stop()
    report_timing(message.context['ident'], 'speech', stopwatch,
                  {'utterance': utterance, 'tts': tts.__class__.__name__})


def mute_and_speak(utterance, message):
    """Mute mic and start speaking the utterance using selected tts backend.

    Arguments:
        utterance:  The sentence to be spoken
        message:    Message associated with request
    """
    global tts_hash, speak_muted, tts
    LOG.info("Speak: " + utterance)
    if speak_muted:
        LOG.warning("Tried to speak, but TTS is muted!")
        return

    listen = message.data.get('expect_response', False)

    # update TTS object if configuration has changed
    if tts_hash != hash(str(config.get('tts', ''))):
        # Stop tts playback thread
        tts.playback.stop()
        tts.playback.join()
        # Create new tts instance
        tts = TTSFactory.create(config)
        tts.init(bus)
        tts_hash = hash(str(config.get('tts', '')))

    try:
        tts.execute(utterance, message.context['ident'], listen, message)
    except RemoteTTSTimeoutException as e:

        mimic_fallback_tts(utterance, message.context['ident'], message)
    except Exception as e:
        LOG.error(e)
        if MimicTTSPlugin:
            try:
                mimic_fallback_tts(utterance, message.context['ident'], message)
                return
            except Exception as e2:
                LOG.error(e2)
        LOG.error('TTS execution failed ({})'.format(repr(e)))


def _get_mimic_fallback():
    """Lazily initializes the fallback TTS if needed."""
    global mimic_fallback_obj
    if not mimic_fallback_obj:
        config = get_neon_audio_config()
        tts_config = config.get('tts', {}).get("mimic", {})
        lang = config.get("lang", "en-us")
        tts = MimicTTSPlugin(lang, tts_config)
        tts.validator.validate()
        tts.init(bus)
        mimic_fallback_obj = tts

    return mimic_fallback_obj


def mimic_fallback_tts(utterance, ident, listen):
    """Speak utterance using fallback TTS if connection is lost.

    Args:
        utterance (str): sentence to speak
        ident (str): interaction id for metrics
        listen (bool): True if interaction should end with mycroft listening
    """
    fallback_tts = _get_mimic_fallback()
    LOG.debug("Mimic fallback, utterance : " + str(utterance))
    fallback_tts.execute(utterance, ident, listen)


def handle_stop(_):
    """Handle stop message.

    Shutdown any speech.
    """
    global _last_stop_signal
    if check_for_signal("isSpeaking", -1):
        _last_stop_signal = time.time()
        tts.playback.clear()  # Clear here to get instant stop
        bus.emit(Message("mycroft.stop.handled", {"by": "TTS"}))


def init(messagebus, conf=None):
    """Start speech related handlers.

    Arguments:
        messagebus: Connection to the Mycroft messagebus
        conf: configuration override
    """

    global bus
    global tts
    global tts_hash
    global config

    bus = messagebus
    # Configuration.set_config_update_handlers(bus)
    # config = Configuration.get()
    config = conf or get_neon_audio_config()
    bus.on('mycroft.stop', handle_stop)
    bus.on('mycroft.audio.speech.stop', handle_stop)
    bus.on('speak', handle_speak)

    # API Methods
    bus.on("neon.get_tts", handle_get_tts)

    tts = TTSFactory.create(config)
    tts.init(bus)
    tts_hash = hash(str(config.get('tts', '')))


def shutdown():
    """Shutdown the audio service cleanly.

    Stop any playing audio and make sure threads are joined correctly.
    """
    if tts:
        tts.playback.stop()
        tts.playback.join()
    if mimic_fallback_obj:
        mimic_fallback_obj.playback.stop()
        mimic_fallback_obj.playback.join()
