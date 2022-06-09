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

from neon_utils.messagebus_utils import get_messagebus
from neon_utils.configuration_utils import init_config_dir
from neon_utils.logger import LOG

from mycroft.lock import Lock
from mycroft.configuration import setup_locale


def on_ready():
    LOG.info('Audio service is ready.')


def on_error(e='Unknown'):
    LOG.error('Audio service failed to launch ({}).'.format(repr(e)))


def on_stopping():
    LOG.info('Audio service is shutting down...')


def on_alive():
    pass


def on_started():
    pass


def main(*args, **kwargs):
    init_config_dir()
    bus = get_messagebus()

    from neon_utils.signal_utils import init_signal_bus, \
        init_signal_handlers, check_for_signal
    init_signal_bus(bus)
    init_signal_handlers()

    from neon_audio.service import NeonSpeechService
    from mycroft.util import reset_sigint_handler, wait_for_exit_signal

    reset_sigint_handler()
    check_for_signal("isSpeaking")
    Lock("audio")
    setup_locale()
    service = NeonSpeechService(*args, **kwargs)
    service.start()
    wait_for_exit_signal()
    service.shutdown()


if __name__ == '__main__':
    main()
