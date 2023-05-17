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

import tracemalloc

from neon_utils.messagebus_utils import get_messagebus
from neon_utils.configuration_utils import init_config_dir
from neon_utils.log_utils import init_log
from ovos_utils import wait_for_exit_signal
from ovos_utils.log import LOG
from ovos_config.locale import setup_locale
from ovos_utils.process_utils import reset_sigint_handler, PIDLock as Lock


def main(*args, **kwargs):
    if kwargs.get("config"):
        LOG.warning("Found `config` kwarg, but expect `audio_config`")
        kwargs["audio_config"] = kwargs.pop("config")

    init_config_dir()
    from ovos_config.config import Configuration
    debug = False
    if Configuration().get('debug'):
        debug = True
        LOG.info(f"Debug enabled; starting tracemalloc")
        tracemalloc.start()

    init_log(log_name="audio")
    bus = get_messagebus()
    kwargs["bus"] = bus
    from neon_utils.signal_utils import init_signal_bus, \
        init_signal_handlers, check_for_signal
    init_signal_bus(bus)
    init_signal_handlers()

    from neon_audio.service import NeonPlaybackService

    reset_sigint_handler()
    check_for_signal("isSpeaking")
    Lock("audio")
    setup_locale()
    service = NeonPlaybackService(*args, **kwargs)
    service.start()
    wait_for_exit_signal()
    if debug:
        memory_snapshot = tracemalloc.take_snapshot()
        display_top(memory_snapshot)
    service.shutdown()


# TODO: Move to utils
def display_top(snapshot, key_type='lineno', limit=10):
    import linecache
    snapshot = snapshot.filter_traces((
        tracemalloc.Filter(False, "<frozen importlib._bootstrap>"),
        tracemalloc.Filter(False, "<unknown>"),
    ))
    top_stats = snapshot.statistics(key_type)

    LOG.info(f"Top {limit} lines")
    for index, stat in enumerate(top_stats[:limit], 1):
        frame = stat.traceback[0]
        LOG.info(f"#{index}: {frame.filename}:{frame.lineno}: "
                 f"{stat.size / 1024} KiB")
        line = linecache.getline(frame.filename, frame.lineno).strip()
        if line:
            LOG.info(f'    {line}')

    other = top_stats[limit:]
    if other:
        size = sum(stat.size for stat in other)
        LOG.info("%s other: %.1f KiB" % (len(other), size / 1024))
    total = sum(stat.size for stat in top_stats)
    LOG.info("Total allocated size: %.1f KiB" % (total / 1024))


if __name__ == '__main__':
    main()
