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

import mycroft.audio.tts

from neon_utils.logger import LOG
from neon_audio.tts import TTSFactory
mycroft.audio.tts.TTSFactory = TTSFactory

from mycroft.audio.service import PlaybackService
from ovos_config.config import Configuration


def on_ready():
    LOG.info('Speech service is ready.')


def on_stopping():
    LOG.info('Speech service is shutting down...')


def on_error(e='Unknown'):
    LOG.error('Speech service failed to launch ({}).'.format(repr(e)))


def on_alive():
    LOG.debug("Speech service alive")


def on_started():
    LOG.debug("Speech service started")


class NeonPlaybackService(PlaybackService):
    def __init__(self, ready_hook=on_ready, error_hook=on_error,
                 stopping_hook=on_stopping, alive_hook=on_alive,
                 started_hook=on_started, watchdog=lambda: None,
                 audio_config=None, daemonic=False, bus=None):
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
        """
        if audio_config:
            LOG.info("Updating global config with passed config")
            from neon_audio.utils import patch_config
            patch_config(audio_config)
        PlaybackService.__init__(self, ready_hook, error_hook, stopping_hook,
                                 alive_hook, started_hook, watchdog, bus)
        assert self.config == Configuration()
        self.setDaemon(daemonic)
        from neon_utils.signal_utils import init_signal_handlers, \
            init_signal_bus
        init_signal_bus(self.bus)
        init_signal_handlers()

    def handle_get_tts(self, message):
        """
        Handle a request to get TTS only
        :param message: Message associated with request
        """
        text = message.data.get("text")
        ident = message.context.get("ident") or "neon.get_tts.response"
        LOG.info(f"Handling TTS request: {ident}")
        if not message.data.get("speaker"):
            LOG.warning(f"No speaker data with request, "
                        f"core defaults will be used.")
        if text:
            if not isinstance(text, str):
                self.bus.emit(message.reply(
                    ident, data={"error": f"text is not a str: {text}"}))
                return
            try:
                responses = self.tts.get_multiple_tts(message)
                self.bus.emit(message.reply(ident, data=responses))
            except Exception as e:
                LOG.exception(e)
                self.bus.emit(message.reply(ident, data={"error": repr(e)}))
        else:
            self.bus.emit(message.reply(ident,
                                        data={"error": "No text provided."}))

    def init_messagebus(self):
        self.bus.on('neon.get_tts', self.handle_get_tts)
        super().init_messagebus()
