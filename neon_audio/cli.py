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

import click
import sys

from os import environ
from typing import List
from click_default_group import DefaultGroup
from neon_utils.packaging_utils import get_package_version_spec
from ovos_config.config import Configuration
from ovos_utils.log import LOG, log_deprecation

environ.setdefault("OVOS_CONFIG_BASE_FOLDER", "neon")
environ.setdefault("OVOS_CONFIG_FILENAME", "neon.yaml")


@click.group("neon-audio", cls=DefaultGroup,
             no_args_is_help=True, invoke_without_command=True,
             help="Neon Audio Commands\n\n"
                  "See also: neon COMMAND --help")
@click.option("--version", "-v", is_flag=True, required=False,
              help="Print the current version")
def neon_audio_cli(version: bool = False):
    if version:
        click.echo(f"neon_audio version "
                   f"{get_package_version_spec('neon_audio')}")

@neon_audio_cli.command(help="Start Neon Audio module")
@click.option("--module", "-m", default=None,
              help="TTS Plugin to configure")
@click.option("--package", "-p", default=None,
              help="TTS package spec to install")
@click.option("--force-install", "-f", default=False, is_flag=True,
              help="Force pip installation of configured module")
def run(module, package, force_install):
    from neon_audio.__main__ import main
    if force_install or module or package:
        try:
            install_plugin(module, package, force_install)
        except Exception as e:
            click.echo(f"Failed to install plugin: {e}")
    if module:
        audio_config = Configuration()
        if module != audio_config["tts"]["module"]:
            LOG.warning(f"Requested a module to install ({module}), but config "
                        f"specifies {audio_config['tts']['module']}."
                        f"{audio_config['tts']['module']} will be loaded. "
                        f"Configuration can be modified at "
                        f"{audio_config.xdg_configs[0]}")
    click.echo("Starting Audio Client")
    main()
    click.echo("Audio Client Shutdown")

@neon_audio_cli.command(help="Install a TTS Plugin")
@click.option("--module", "-m", default=None,
              help="TTS Plugin to configure")
@click.option("--package", "-p", default=None,
              help="TTS package spec to install")
@click.option("--force-install", "-f", default=False, is_flag=True,
              help="Force pip installation of configured module")
def install_plugin(module, package, force_install):
    from neon_audio.utils import install_tts_plugin
    log_deprecation("`install-plugin` replaced by `install-dependencies`", "2.0.0")
    audio_config = Configuration()

    if force_install and not (package or module):
        click.echo("Installing TTS plugin from configuration")
        module = module or audio_config["tts"]["module"]
        package = package or audio_config["tts"].get("package_spec")

    if module:
        install_tts_plugin(package or module)
        if not module:
            click.echo("Plugin specified without module")


@neon_audio_cli.command(help="Install neon-audio module dependencies from config & cli")
@click.option("--package", "-p", default=[], multiple=True,
              help="Additional package to install (can be repeated)")
def install_dependencies(package: List[str]):
    from neon_utils.packaging_utils import install_packages_from_pip
    from neon_audio.utils import build_extra_dependency_list
    config = Configuration()
    dependencies = build_extra_dependency_list(config, list(package))
    result = install_packages_from_pip("neon-audio", dependencies)
    LOG.info(f"pip exit code: {result}")
    sys.exit(result)

@neon_audio_cli.command(help="Install a TTS Plugin")
@click.option("--plugin", "-p", default=None,
              help="TTS module to init")
def init_plugin(plugin):
    from neon_audio.utils import init_tts_plugin
    plugin = plugin or Configuration()["tts"]["module"]
    init_tts_plugin(plugin)