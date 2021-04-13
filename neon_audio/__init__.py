# Copyright 2017 Mycroft AI Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import time
from ovos_utils.signal import check_for_signal, create_signal
from neon_utils.configuration_utils import get_neon_local_config


IPC_PATH = get_neon_local_config().get("dirVars", {}).get("ipcDir", "/tmp/neon/ipc")
CONFIG = {"ipc_path": IPC_PATH}


def is_speaking():
    """Determine if Text to Speech is occurring

    Returns:
        bool: True while still speaking
    """
    return check_for_signal("isSpeaking", -1, CONFIG)


def wait_while_speaking():
    """Pause as long as Text to Speech is still happening

    Pause while Text to Speech is still happening.  This always pauses
    briefly to ensure that any preceeding request to speak has time to
    begin.
    """
    # TODO: Better method using messages or signals here DM
    time.sleep(0.3)  # Wait briefly in for any queued speech to begin
    while is_speaking():
        time.sleep(0.1)


def stop_speaking():
    # TODO: Less hacky approach to this once Audio Manager is implemented
    # Skills should only be able to stop speech they've initiated
    from mycroft_bus_client.send_func import send
    create_signal('stoppingTTS')
    send('mycroft.audio.speech.stop')

    # Block until stopped
    while check_for_signal("isSpeaking", -1, CONFIG):
        time.sleep(0.25)

    # This consumes the signal
    check_for_signal('stoppingTTS', CONFIG)
