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

import sys
import time

from os.path import abspath, dirname
from threading import Lock

from mycroft_bus_client import Message
from neon_utils.configuration_utils import get_neon_audio_config
from neon_utils.logger import LOG
from ovos_plugin_manager import find_plugins

from neon_audio.services import RemoteAudioBackend

from mycroft.util.monotonic_event import MonotonicEvent
from mycroft.audio.audioservice import setup_service, load_services


MINUTES = 60  # Seconds in a minute

MAINMODULE = '__init__'
sys.path.append(abspath(dirname(__file__)))


def load_plugins(config, bus):
    """Load installed audioservice plugins.

    Arguments:
        config: configuration dict for the audio backends.
        bus: Mycroft messagebus

    Returns:
        List of started services
    """
    plugin_services = []
    plugins = find_plugins('mycroft.plugin.audioservice')
    for plug in plugins:
        service = setup_service(plug, config, bus)
        if service:
            plugin_services += service
    return plugin_services


class AudioService:
    """ Audio Service class.
        Handles playback of audio and selecting proper backend for the uri
        to be played.
    """

    def __init__(self, bus, config=None):
        """
            Args:
                bus: Mycroft messagebus
        """
        self.bus = bus
        config = config or get_neon_audio_config()
        self.config = config.get("Audio") or config
        self.service_lock = Lock()

        self.default = None
        self.service = []
        self.current = None
        self.play_start_time = 0
        self.volume_is_low = False

        self._loaded = MonotonicEvent()
        self.load_services()

    def load_services(self):
        """Method for loading services.

        Sets up the global service, default and registers the event handlers
        for the subsystem.
        """
        services = load_services(self.config, self.bus)
        # Sort services so local services are checked first
        local = [s for s in services if not isinstance(s, RemoteAudioBackend)]
        remote = [s for s in services if isinstance(s, RemoteAudioBackend)]
        self.service = local + remote

        # Register end of track callback
        for s in self.service:
            s.set_track_start_callback(self.track_start)

        # Find default backend
        default_name = self.config.get('default-backend', '')
        LOG.info('Finding default backend...')
        for s in self.service:
            if s.name == default_name:
                self.default = s
                LOG.info('Found ' + self.default.name)
                break
        else:
            self.default = None
            LOG.info('no default found')

        # Setup event handlers
        self.bus.on('mycroft.audio.service.play', self._play)
        self.bus.on('mycroft.audio.service.queue', self._queue)
        self.bus.on('mycroft.audio.service.pause', self._pause)
        self.bus.on('mycroft.audio.service.resume', self._resume)
        self.bus.on('mycroft.audio.service.stop', self._stop)
        self.bus.on('mycroft.audio.service.next', self._next)
        self.bus.on('mycroft.audio.service.prev', self._prev)
        self.bus.on('mycroft.audio.service.track_info', self._track_info)
        self.bus.on('mycroft.audio.service.list_backends', self._list_backends)
        self.bus.on('mycroft.audio.service.seek_forward', self._seek_forward)
        self.bus.on('mycroft.audio.service.seek_backward', self._seek_backward)
        self.bus.on('recognizer_loop:audio_output_start', self._lower_volume)
        self.bus.on('recognizer_loop:record_begin', self._lower_volume)
        self.bus.on('recognizer_loop:audio_output_end', self._restore_volume)
        self.bus.on('recognizer_loop:record_end',
                    self._restore_volume_after_record)

        self._loaded.set()  # Report services loaded

    def wait_for_load(self, timeout=3 * MINUTES):
        """Wait for services to be loaded.

        Arguments:
            timeout (float): Seconds to wait (default 3 minutes)
        Returns:
            (bool) True if loading completed within timeout, else False.
        """
        return self._loaded.wait(timeout)

    def track_start(self, track):
        """Callback method called from the services to indicate start of
        playback of a track or end of playlist.
        """
        if track:
            # Inform about the track about to start.
            LOG.debug('New track coming up!')
            self.bus.emit(Message('mycroft.audio.playing_track',
                                  data={'track': track}))
        else:
            # If no track is about to start last track of the queue has been
            # played.
            LOG.debug('End of playlist!')
            self.bus.emit(Message('mycroft.audio.queue_end'))

    def _pause(self, _=None):
        """
            Handler for mycroft.audio.service.pause. Pauses the current audio
            service.
        """
        if self.current:
            self.current.pause()

    def _resume(self, _=None):
        """
            Handler for mycroft.audio.service.resume.
        """
        if self.current:
            self.current.resume()

    def _next(self, _=None):
        """
            Handler for mycroft.audio.service.next. Skips current track and
            starts playing the next.
        """
        if self.current:
            self.current.next()

    def _prev(self, _=None):
        """
            Handler for mycroft.audio.service.prev. Starts playing the previous
            track.
        """
        if self.current:
            self.current.previous()

    def _perform_stop(self):
        """Stop audioservice if active."""
        if self.current:
            name = self.current.name
            if self.current.stop():
                self.bus.emit(Message("mycroft.stop.handled",
                                      {"by": "audio:" + name}))

        self.current = None

    def _stop(self, _=None):
        """
            Handler for mycroft.stop. Stops any playing service.
        """
        if time.monotonic() - self.play_start_time > 1:
            LOG.debug('stopping all playing services')
            with self.service_lock:
                self._perform_stop()
        LOG.info('END Stop')

    def _lower_volume(self, _=None):
        """
            Is triggered when mycroft starts to speak and reduces the volume.
        """
        if self.current:
            LOG.debug('lowering volume')
            self.current.lower_volume()
            self.volume_is_low = True

    def _restore_volume(self, _=None):
        """Triggered when mycroft is done speaking and restores the volume."""
        current = self.current
        if current:
            LOG.debug('restoring volume')
            self.volume_is_low = False
            current.restore_volume()

    def _restore_volume_after_record(self, _=None):
        """
            Restores the volume when Mycroft is done recording.
            If no utterance detected, restore immediately.
            If no response is made in reasonable time, then also restore.
        """
        def restore_volume():
            LOG.debug('restoring volume')
            self.current.restore_volume()

        if self.current:
            self.bus.on('recognizer_loop:speech.recognition.unknown',
                        restore_volume)
            speak_msg_detected = self.bus.wait_for_message('speak',
                                                           timeout=8.0)
            if not speak_msg_detected:
                restore_volume()
            self.bus.remove('recognizer_loop:speech.recognition.unknown',
                            restore_volume)
        else:
            LOG.debug("No audio service to restore volume of")

    def play(self, tracks, prefered_service, repeat=False):
        """
            play starts playing the audio on the prefered service if it
            supports the uri. If not the next best backend is found.

            Args:
                tracks: list of tracks to play.
                repeat: should the playlist repeat
                prefered_service: indecates the service the user prefer to play
                                  the tracks.
        """
        self._perform_stop()

        if isinstance(tracks[0], str):
            uri_type = tracks[0].split(':')[0]
        else:
            uri_type = tracks[0][0].split(':')[0]

        # check if user requested a particular service
        if prefered_service and uri_type in prefered_service.supported_uris():
            selected_service = prefered_service
        # check if default supports the uri
        elif self.default and uri_type in self.default.supported_uris():
            LOG.debug("Using default backend ({})".format(self.default.name))
            selected_service = self.default
        else:  # Check if any other service can play the media
            LOG.debug("Searching the services")
            for s in self.service:
                if uri_type in s.supported_uris():
                    LOG.debug("Service {} supports URI {}".format(s, uri_type))
                    selected_service = s
                    break
            else:
                LOG.info('No service found for uri_type: ' + uri_type)
                return
        if not selected_service.supports_mime_hints:
            tracks = [t[0] if isinstance(t, list) else t for t in tracks]
        selected_service.clear_list()
        selected_service.add_list(tracks)
        selected_service.play(repeat)
        self.current = selected_service
        self.play_start_time = time.monotonic()

    def _queue(self, message):
        if self.current:
            with self.service_lock:
                tracks = message.data['tracks']
                self.current.add_list(tracks)
        else:
            self._play(message)

    def _play(self, message):
        """
            Handler for mycroft.audio.service.play. Starts playback of a
            tracklist. Also  determines if the user requested a special
            service.

            Args:
                message: message bus message, not used but required
        """
        with self.service_lock:
            tracks = message.data['tracks']
            repeat = message.data.get('repeat', False)
            # Find if the user wants to use a specific backend
            for s in self.service:
                if ('utterance' in message.data and
                        s.name in message.data['utterance']):
                    prefered_service = s
                    LOG.debug(s.name + ' would be prefered')
                    break
            else:
                prefered_service = None
            self.play(tracks, prefered_service, repeat)
            time.sleep(0.5)

    def _track_info(self, _):
        """
            Returns track info on the message bus.
        """
        if self.current:
            track_info = self.current.track_info()
        else:
            track_info = {}
        self.bus.emit(Message('mycroft.audio.service.track_info_reply',
                              data=track_info))

    def _list_backends(self, message):
        """ Return a dict of available backends. """
        data = {}
        for s in self.service:
            info = {
                'supported_uris': s.supported_uris(),
                'default': s == self.default,
                'remote': isinstance(s, RemoteAudioBackend)
            }
            data[s.name] = info
        self.bus.emit(message.response(data))

    def _seek_forward(self, message):
        """
            Handle message bus command to skip X seconds

            Args:
                message: message bus message
        """
        seconds = message.data.get("seconds", 1)
        if self.current:
            self.current.seek_forward(seconds)

    def _seek_backward(self, message):
        """
            Handle message bus command to rewind X seconds

            Args:
                message: message bus message
        """
        seconds = message.data.get("seconds", 1)
        if self.current:
            self.current.seek_backward(seconds)

    def shutdown(self):
        for s in self.service:
            try:
                LOG.info('shutting down ' + s.name)
                s.shutdown()
            except Exception as e:
                LOG.error('shutdown of ' + s.name + ' failed: ' + repr(e))

        # remove listeners
        self.bus.remove('mycroft.audio.service.play', self._play)
        self.bus.remove('mycroft.audio.service.queue', self._queue)
        self.bus.remove('mycroft.audio.service.pause', self._pause)
        self.bus.remove('mycroft.audio.service.resume', self._resume)
        self.bus.remove('mycroft.audio.service.stop', self._stop)
        self.bus.remove('mycroft.audio.service.next', self._next)
        self.bus.remove('mycroft.audio.service.prev', self._prev)
        self.bus.remove('mycroft.audio.service.track_info', self._track_info)
        self.bus.remove('mycroft.audio.service.seek_forward',
                        self._seek_forward)
        self.bus.remove('mycroft.audio.service.seek_backward',
                        self._seek_backward)
        self.bus.remove('recognizer_loop:audio_output_start',
                        self._lower_volume)
        self.bus.remove('recognizer_loop:record_begin', self._lower_volume)
        self.bus.remove('recognizer_loop:audio_output_end',
                        self._restore_volume)
        self.bus.remove('recognizer_loop:record_end',
                        self._restore_volume_after_record)
