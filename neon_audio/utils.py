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

from tempfile import mkstemp
from neon_utils.logger import LOG
from neon_utils.packaging_utils import get_package_dependencies


def _plugin_to_package(plugin: str) -> str:
    """
    Get a PyPI spec for a known plugin entrypoint
    :param plugin: plugin spec (i.e. config['tts']['module'])
    :returns: package name associated with `plugin` or `plugin`
    """
    known_plugins = {
        "neon-tts-plugin-glados": "neon-tts-plugin-glados",
        "neon_tts_mimic": "neon-tts-plugin-mimic",
        "amazon_polly": "neon-tts-plugin-polly",
        "coqui": "neon-tts-plugin-coqui",
        "neon-tts-plugin-larynx-server": "neon-tts-plugin-larynx-server",
        "mozilla_local": "neon-tts-plugin-mozilla-local",
        "mozilla_remote": "neon-tts-plugin-mozilla-remote"
    }
    return known_plugins.get(plugin) or plugin


def install_tts_plugin(plugin: str) -> bool:
    """
    Install a tts plugin using pip
    :param plugin: entrypoint of plugin to install
    :returns: True if the plugin installation is successful
    """
    import pip
    _, tmp_file = mkstemp()
    with open(tmp_file, 'w') as f:
        constraints = '\n'.join(get_package_dependencies("neon-audio"))
        f.write(constraints)
        LOG.info(f"Constraints={constraints}")
    LOG.info(f"Requested installation of plugin: {plugin}")
    returned = pip.main(['install', _plugin_to_package(plugin), "-c", tmp_file])
    LOG.info(f"pip status: {returned}")
    return returned == 0