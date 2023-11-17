# NEON AI (TM) SOFTWARE, Software Development Kit & Application Framework
# All trademark and other rights reserved by their respective owners
# Copyright 2008-2022 Neongecko.com Inc.
# Contributors: Daniel McKnight, Guy Daniels, Elon Gasper, Richard Leeds,
# Regina Bloomstine, Casimiro Ferreira, Andrii Pernatii, Kirill Hrymailo
# BSD-3 License
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
# 3. Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from this
#    software without specific prior written permission.
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
# THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
# PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
# CONTRIBUTORS  BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA,
# OR PROFITS;  OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
# LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
# NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE,  EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
from time import time

import ovos_audio.tts
import ovos_plugin_manager.templates.tts

from threading import Event
from ovos_utils.log import LOG, log_deprecation
from neon_audio.tts import TTSFactory
from neon_utils.messagebus_utils import get_messagebus
from neon_utils.metrics_utils import Stopwatch
from ovos_audio.service import PlaybackService

ovos_audio.tts.TTSFactory = TTSFactory
ovos_audio.service.TTSFactory = TTSFactory


def on_ready():
    LOG.info('Playback service is ready.')


def on_stopping():
    LOG.info('Playback service is shutting down...')


def on_error(e='Unknown'):
    LOG.error('Playback service failed to launch ({}).'.format(repr(e)))


def on_alive():
    LOG.debug("Playback service alive")


def on_started():
    LOG.debug("Playback service started")


class NeonPlaybackService(PlaybackService):
    def __init__(self, ready_hook=on_ready, error_hook=on_error,
                 stopping_hook=on_stopping, alive_hook=on_alive,
                 started_hook=on_started, watchdog=lambda: None,
                 audio_config=None, daemonic=False, bus=None,
                 disable_ocp=False):
        """
        Creates a Speech service thread
        :param ready_hook: function callback when service is ready
        :param error_hook: function callback to handle uncaught exceptions
        :param stopping_hook: function callback when service is stopping
        :param alive_hook: function callback when service is alive
        :param started_hook: function callback when service is started
        :param audio_config: global core configuration override
        :param daemonic: if True, run this thread as a daemon
        :param bus: Connected MessageBusClient
        :param disable_ocp: if True, disable OVOS Common Play service
        """
        if audio_config:
            LOG.info("Updating global config with passed config")
            from neon_audio.utils import patch_config
            patch_config(audio_config)
        bus = bus or get_messagebus()
        # Override all the previously loaded signal methods
        from neon_utils.signal_utils import init_signal_handlers, \
            init_signal_bus
        init_signal_bus(bus)
        init_signal_handlers()
        from neon_utils.signal_utils import create_signal, check_for_signal
        ovos_audio.service.check_for_signal = check_for_signal
        ovos_plugin_manager.templates.tts.check_for_signal = check_for_signal
        ovos_plugin_manager.templates.tts.create_signal = create_signal

        from neon_audio.tts.neon import NeonPlaybackThread
        ovos_audio.service.PlaybackThread = NeonPlaybackThread
        PlaybackService.__init__(self, ready_hook, error_hook, stopping_hook,
                                 alive_hook, started_hook, watchdog, bus,
                                 disable_ocp)
        LOG.debug(f'Initialized tts={self._tts_hash} | '
                  f'fallback={self._fallback_tts_hash}')
        create_signal("neon_speak_api")   # Create signal so skills use API
        self._playback_timeout = 120
        self.daemon = daemonic

    def handle_speak(self, message):
        message.context.setdefault('destination', [])
        if isinstance(message.context['destination'], str):
            message.context['destination'] = [message.context['destination']]
        if "audio" not in message.context['destination']:
            log_deprecation("Adding audio to destination context", "2.0.0")
            message.context['destination'].append('audio')

        audio_finished = Event()

        message.context.setdefault("timing", dict())
        message.context["timing"].setdefault("speech_start", time())

        if message.context.get('ident'):
            log_deprecation("ident context is deprecated. Use `session`",
                            "2.0.0")
            if not message.context.get('session'):
                LOG.info("No session context. Adding session from ident.")

        speak_id = message.data.get('speak_ident') or \
            message.context.get('ident') or message.data.get('ident')
        message.context['speak_ident'] = speak_id
        if not speak_id:
            LOG.warning(f"`speak_ident` data missing: {message.data}")

        def handle_finished(_):
            audio_finished.set()

        # If we have an identifier, add a callback to wait for playback
        if speak_id:
            self.bus.once(speak_id, handle_finished)
        else:
            audio_finished.set()

        PlaybackService.handle_speak(self, message)
        if not audio_finished.wait(self._playback_timeout):
            LOG.warning(f"Playback not completed for {speak_id} within "
                        f"{self._playback_timeout} seconds")
            self.bus.remove(speak_id, handle_finished)
        elif speak_id:
            LOG.debug(f"Playback completed for: {speak_id}")

    def handle_get_tts(self, message):
        """
        Handle a request to get TTS only
        :param message: Message associated with request
        """
        text = message.data.get("text")
        ident = message.context.get("ident") or "neon.get_tts.response"
        LOG.info(f"Handling TTS request: {ident}")
        if not message.data.get("speaker"):
            LOG.info(f"No speaker data with request, "
                     f"core defaults will be used.")
        message.context.setdefault('timing', dict())
        if text:
            stopwatch = Stopwatch("api_get_tts", allow_reporting=True,
                                  bus=self.bus)
            if not isinstance(text, str):
                message.context['timing']['response_sent'] = time()
                self.bus.emit(message.reply(
                    ident, data={"error": f"text is not a str: {text}"}))
                return
            try:
                with stopwatch:
                    responses = self.tts.get_multiple_tts(message)
                message.context['timing']['get_tts'] = stopwatch.time
                LOG.debug(f"Emitting response: {responses}")
                message.context['timing']['response_sent'] = time()
                self.bus.emit(message.reply(ident, data=responses))
            except Exception as e:
                LOG.exception(e)
                message.context['timing']['response_sent'] = time()
                self.bus.emit(message.reply(ident, data={"error": repr(e)}))
        else:
            message.context['timing']['response_sent'] = time()
            self.bus.emit(message.reply(ident,
                                        data={"error": "No text provided."}))

    def init_messagebus(self):
        self.bus.on('neon.get_tts', self.handle_get_tts)
        PlaybackService.init_messagebus(self)
