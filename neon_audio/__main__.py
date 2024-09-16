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
from neon_utils.log_utils import init_log
from neon_utils.process_utils import start_malloc, snapshot_malloc, print_malloc
from neon_utils.signal_utils import init_signal_bus, \
    init_signal_handlers, check_for_signal
from ovos_utils import wait_for_exit_signal
from ovos_utils.log import LOG
from ovos_config.locale import setup_locale
from ovos_utils.process_utils import reset_sigint_handler, PIDLock as Lock

from neon_audio.service import NeonPlaybackService


def main(*args, **kwargs):
    if kwargs.get("config"):
        LOG.warning("Found `config` kwarg, but expect `audio_config`")
        kwargs["audio_config"] = kwargs.pop("config")
    if kwargs.get("audio_config"):
        LOG.warning("Passed configuration should be written to disk before"
                    "module launch")
    init_log(log_name="audio")
    malloc_running = start_malloc(stack_depth=4)
    bus = get_messagebus()
    kwargs["bus"] = bus

    init_signal_bus(bus)
    init_signal_handlers()

    reset_sigint_handler()
    check_for_signal("isSpeaking")
    Lock("audio")
    setup_locale()
    try:
        service = NeonPlaybackService(*args, **kwargs)
        LOG.info("Service init completed")
        service.start()
        wait_for_exit_signal()
    except Exception as e:
        LOG.exception(e)
        service = None
    if malloc_running:
        try:
            print_malloc(snapshot_malloc())
        except Exception as e:
            LOG.error(e)
    if service:
        service.shutdown()


def deprecated_entrypoint():
    from ovos_utils.log import log_deprecation
    log_deprecation("Use `neon-audio run` in place of "
                    "`neon_audio_client`", "2.0.0")
    main()


if __name__ == '__main__':
    main()
