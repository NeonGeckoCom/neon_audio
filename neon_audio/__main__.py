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

from neon_utils.messagebus_utils import get_messagebus
from neon_utils.configuration_utils import get_neon_device_type,\
    init_config_dir
from neon_utils.logger import LOG

from neon_audio import speech
from neon_audio.audioservice import AudioService
from neon_utils.signal_utils import check_for_signal
from mycroft.util.process_utils import ProcessStatus, StatusCallbackMap
from mycroft.util import reset_sigint_handler, wait_for_exit_signal


def on_ready():
    LOG.info('Audio service is ready.')


def on_error(e='Unknown'):
    LOG.error('Audio service failed to launch ({}).'.format(repr(e)))


def on_stopping():
    LOG.info('Audio service is shutting down...')


def main(ready_hook=on_ready, error_hook=on_error, stopping_hook=on_stopping, config: dict = None):
    """
     Main function. Run when file is invoked.
     :param ready_hook: Optional function to call when service is ready
     :param error_hook: Optional function to call when service encounters an error
     :param stopping_hook: Optional function to call when service is stopping
     :param config: dict configuration containing keys: ['tts', 'Audio', 'language']
    """
    init_config_dir()
    reset_sigint_handler()
    check_for_signal("isSpeaking")
    # whitelist = ['mycroft.audio.service']
    bus = get_messagebus()
    callbacks = StatusCallbackMap(on_ready=ready_hook, on_error=error_hook,
                                  on_stopping=stopping_hook)
    status = ProcessStatus('audio', bus, callbacks)
    try:
        speech.init(bus, config)

        from neon_utils.signal_utils import init_signal_bus, init_signal_handlers
        init_signal_bus(bus)
        init_signal_handlers()

        # Connect audio service instance to message bus
        if get_neon_device_type() == 'server':
            audio = None
        else:
            audio = AudioService(bus, config)  # Connect audio service instance to message bus

        status.set_started()
    except Exception as e:
        LOG.error(e)
        status.set_error(e)
    else:
        if not audio or audio.wait_for_load() and len(audio.service) > 0:
            # If at least one service exists, report ready
            status.set_ready()
            wait_for_exit_signal()
            status.set_stopping()
        else:
            status.set_error('No audio services loaded')

        speech.shutdown()
        if audio:
            audio.shutdown()


if __name__ == '__main__':
    main()
