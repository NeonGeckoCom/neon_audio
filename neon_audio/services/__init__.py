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
from abc import ABCMeta, abstractmethod


class AudioBackend(metaclass=ABCMeta):
    """
        Base class for all audio backend implementations.

        Args:
            config: configuration dict for the instance
            bus:    Mycroft messagebus emitter
    """

    def __init__(self, config, bus):
        self._track_start_callback = None
        self.supports_mime_hints = False

    @abstractmethod
    def supported_uris(self):
        """
            Returns: list of supported uri types.
        """
        pass

    @abstractmethod
    def clear_list(self):
        """
            Clear playlist
        """
        pass

    @abstractmethod
    def add_list(self, tracks):
        """
            Add tracks to backend's playlist.

            Args:
                tracks: list of tracks.
        """
        pass

    @abstractmethod
    def play(self, repeat=False):
        """
            Start playback.

            Args:
                repeat: Repeat playlist, defaults to False
        """
        pass

    @abstractmethod
    def stop(self):
        """
            Stop playback.

            Returns: (bool) True if playback was stopped, otherwise False
        """
        pass

    def set_track_start_callback(self, callback_func):
        """
            Register callback on track start, should be called as each track
            in a playlist is started.
        """
        self._track_start_callback = callback_func

    def pause(self):
        """
            Pause playback.
        """
        pass

    def resume(self):
        """
            Resume paused playback.
        """
        pass

    def next(self):
        """
            Skip to next track in playlist.
        """
        pass

    def previous(self):
        """
            Skip to previous track in playlist.
        """
        pass

    def lower_volume(self):
        """
            Lower volume.
        """
        pass

    def restore_volume(self):
        """
            Restore normal volume.
        """
        pass

    def seek_forward(self, seconds=1):
        """
            Skip X seconds

            Args:
                seconds (int): number of seconds to seek, if negative rewind
        """
        pass

    def seek_backward(self, seconds=1):
        """
            Rewind X seconds

            Args:
                seconds (int): number of seconds to seek, if negative rewind
        """
        pass

    def track_info(self):
        """
            Fetch info about current playing track.

            Returns:
                Dict with track info.
        """
        ret = {}
        ret['artist'] = ''
        ret['album'] = ''
        return ret

    def shutdown(self):
        """ Perform clean shutdown """
        self.stop()


class RemoteAudioBackend(AudioBackend):
    """ Base class for remote audio backends.

        These may be things like Chromecasts, mopidy servers, etc.
    """
    pass
