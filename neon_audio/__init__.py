# NEON AI (TM) SOFTWARE, Software Development Kit & Application Framework
# All trademark and other rights reserved by their respective owners
# Copyright 2008-2025 Neongecko.com Inc.
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

# Patching deprecation warnings
# TODO: Deprecate after migration to ovos-workshop 1.0+ requirement
import ovos_workshop.resource_files
from ovos_utils.bracket_expansion import expand_template
ovos_workshop.resource_files.expand_options = expand_template

# ovos-utils 0.8.5 removed `ovos_utils.signal`, which ovos-audio 0.x imports at
# module scope. Register a compat module backed by `neon_utils.signal_utils`
# before anything imports `ovos_audio`.
# TODO: Remove after migration to ovos-audio 1.2+ requirement
from importlib.util import find_spec

if find_spec("ovos_utils.signal") is None:
    import sys
    from types import ModuleType
    import ovos_utils

    def _check_for_signal(signal_name, sec_lifetime=0, *_, **__):
        from neon_utils.signal_utils import check_for_signal
        return check_for_signal(signal_name, sec_lifetime)

    def _create_signal(signal_name, *_, **__):
        from neon_utils.signal_utils import create_signal
        return create_signal(signal_name)

    _signal_compat = ModuleType("ovos_utils.signal")
    _signal_compat.check_for_signal = _check_for_signal
    _signal_compat.create_signal = _create_signal

    sys.modules["ovos_utils.signal"] = _signal_compat
    ovos_utils.signal = _signal_compat
