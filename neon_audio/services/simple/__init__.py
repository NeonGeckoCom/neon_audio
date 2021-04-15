# NEON AI (TM) SOFTWARE, Software Development Kit & Application Development System
#
# Copyright 2008-2021 Neongecko.com Inc. | All Rights Reserved
#
# Notice of License - Duplicating this Notice of License near the start of any file containing
# a derivative of this software is a condition of license for this software.
# Friendly Licensing:
# No charge, open source royalty free use of the Neon AI software source and object is offered for
# educational users, noncommercial enthusiasts, Public Benefit Corporations (and LLCs) and
# Social Purpose Corporations (and LLCs). Developers can contact developers@neon.ai
# For commercial licensing, distribution of derivative works or redistribution please contact licenses@neon.ai
# Distributed on an "AS IS” basis without warranties or conditions of any kind, either express or implied.
# Trademarks of Neongecko: Neon AI(TM), Neon Assist (TM), Neon Communicator(TM), Klat(TM)
# Authors: Guy Daniels, Daniel McKnight, Regina Bloomstine, Elon Gasper, Richard Leeds
#
# Specialized conversational reconveyance options from Conversation Processing Intelligence Corp.
# US Patents 2008-2021: US7424516, US20140161250, US20140177813, US8638908, US8068604, US8553852, US10530923, US10530924
# China Patent: CN102017585  -  Europe Patent: EU2156652  -  Patents Pending
#
# This software is an enhanced derivation of the Mycroft Project which is licensed under the
# Apache software Foundation software license 2.0 https://www.apache.org/licenses/LICENSE-2.0
# Changes Copyright 2008-2021 Neongecko.com Inc. | All Rights Reserved
#
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
import signal
import mimetypes
import re
from requests import Session
from time import sleep

from neon_audio.services import AudioBackend
from mycroft_bus_client import Message
from neon_utils.logger import LOG

from mycroft.util import play_mp3, play_ogg, play_wav


def find_mime(path):
    mime = None
    if path.startswith('http'):
        response = Session().head(path, allow_redirects=True)
        if 200 <= response.status_code < 300:
            mime = response.headers['content-type']
    if not mime:
        mime = mimetypes.guess_type(path)[0]
    # Remove any http address arguments
    if not mime:
        mime = mimetypes.guess_type(re.sub(r'\?.*$', '', path))[0]

    if mime:
        return mime.split('/')
    else:
        return None, None


class SimpleAudioService(AudioBackend):
    """
        Simple Audio backend for both mpg123 and the ogg123 player.
        This one is rather limited and only implements basic usage.
    """

    def __init__(self, config, bus, name='simple'):
        super().__init__(config, bus)
        self.config = config
        self.process = None
        self.bus = bus
        self.name = name
        self._stop_signal = False
        self._is_playing = False
        self._paused = False
        self.tracks = []
        self.index = 0
        self.supports_mime_hints = True
        mimetypes.init()

        self.bus.on('SimpleAudioServicePlay', self._play)

    def supported_uris(self):
        return ['file', 'http']

    def clear_list(self):
        self.tracks = []

    def add_list(self, tracks):
        self.tracks += tracks
        LOG.info("Track list is " + str(tracks))

    def _play(self, message):
        """ Implementation specific async method to handle playback.
            This allows mpg123 service to use the "next method as well
            as basic play/stop.
        """
        LOG.info('SimpleAudioService._play')

        # Stop any existing audio playback
        self._stop_running_process()

        repeat = message.data.get('repeat', False)
        self._is_playing = True
        self._paused = False
        if isinstance(self.tracks[self.index], list):
            track = self.tracks[self.index][0]
            mime = self.tracks[self.index][1]
            mime = mime.split('/')
        else:  # Assume string
            track = self.tracks[self.index]
            mime = find_mime(track)
        LOG.debug('Mime info: {}'.format(mime))

        # Indicate to audio service which track is being played
        if self._track_start_callback:
            self._track_start_callback(track)

        # Replace file:// uri's with normal paths
        track = track.replace('file://', '')
        try:
            if 'mpeg' in mime[1]:
                self.process = play_mp3(track)
            elif 'ogg' in mime[1]:
                self.process = play_ogg(track)
            elif 'wav' in mime[1]:
                self.process = play_wav(track)
            else:
                # If no mime info could be determined guess mp3
                self.process = play_mp3(track)
        except FileNotFoundError as e:
            LOG.error('Couldn\'t play audio, {}'.format(repr(e)))
            self.process = None
        except Exception as e:
            LOG.exception(repr(e))
            self.process = None

        # Wait for completion or stop request
        while self._is_process_running() and not self._stop_signal:
            sleep(0.25)

        if self._stop_signal:
            self._stop_running_process()
            self._is_playing = False
            self._paused = False
            return
        else:
            self.process = None

        # if there are more tracks available play next
        self.index += 1
        if self.index < len(self.tracks) or repeat:
            if self.index >= len(self.tracks):
                self.index = 0
            self.bus.emit(Message('SimpleAudioServicePlay',
                                  {'repeat': repeat}))
        else:
            self._is_playing = False
            self._paused = False

    def play(self, repeat=False):
        LOG.info('Call SimpleAudioServicePlay')
        self.index = 0
        self.bus.emit(Message('SimpleAudioServicePlay', {'repeat': repeat}))

    def stop(self):
        LOG.info('SimpleAudioServiceStop')
        self._stop_signal = True
        while self._is_playing:
            sleep(0.1)
        self._stop_signal = False

    def _pause(self):
        """ Pauses playback if possible.

            Returns: (bool) New paused status:
        """
        if self.process:
            # Suspend the playback process
            self.process.send_signal(signal.SIGSTOP)
            return True  # After pause the service is paused
        else:
            return False

    def pause(self):
        if not self._paused:
            self._paused = self._pause()

    def _resume(self):
        """ Resumes playback if possible.

            Returns: (bool) New paused status:
        """
        if self.process:
            # Resume the playback process
            self.process.send_signal(signal.SIGCONT)
            return False  # After resume the service is no longer paused
        else:
            return True

    def resume(self):
        if self._paused:
            # Resume the playback process
            self._paused = self._resume()

    def next(self):
        # Terminate process to continue to next
        self._stop_running_process()

    def previous(self):
        pass

    def lower_volume(self):
        if not self._paused:
            self._pause()  # poor-man's ducking

    def restore_volume(self):
        if not self._paused:
            self._resume()  # poor-man's unducking

    def _is_process_running(self):
        return self.process and self.process.poll() is None

    def _stop_running_process(self):
        if self._is_process_running():
            if self._paused:
                # The child process must be "unpaused" in order to be stopped
                self._resume()
            self.process.terminate()
            countdown = 10
            while self._is_process_running() and countdown > 0:
                sleep(0.1)
                countdown -= 1

            if self._is_process_running():
                # Failed to shutdown when asked nicely.  Force the issue.
                LOG.debug("Killing currently playing audio...")
                self.process.kill()
        self.process = None


def load_service(base_config, bus):
    backends = base_config.get('backends', [])
    services = [(b, backends[b]) for b in backends
                if backends[b]['type'] == 'simple' and
                backends[b].get('active', True)]
    instances = [SimpleAudioService(s[1], bus, s[0]) for s in services]
    return instances
