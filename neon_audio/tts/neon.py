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

import hashlib
import inspect
import os

from os.path import dirname
from json_database import JsonStorageXDG
from ovos_bus_client.message import Message
from ovos_plugin_manager.language import OVOSLangDetectionFactory,\
    OVOSLangTranslationFactory
from ovos_plugin_manager.templates.tts import TTS
from ovos_utils.enclosure.api import EnclosureAPI

from neon_utils.file_utils import encode_file_to_base64_string
from neon_utils.message_utils import resolve_message
from neon_utils.metrics_utils import Stopwatch
from neon_utils.signal_utils import create_signal, check_for_signal,\
    init_signal_bus
from ovos_utils.log import LOG, log_deprecation
from ovos_audio.playback import PlaybackThread
from ovos_config.config import Configuration


def get_requested_tts_languages(msg) -> list:
    """
    Builds a list of the requested TTS for a given spoken response
    :param msg: Message associated with request
    :return: List of TTS dict data
    """
    profiles = msg.context.get("user_profiles") or \
        msg.context.get("nick_profiles")
    tts_name = "Neon"
    default_gender = "female"
    tts_reqs = []
    # Get all of our language parameters
    try:
        # If speaker data is present, use it
        if msg.data.get("speaker"):
            speaker = msg.data.get("speaker")
            tts_reqs.append({"speaker": speaker.get("name", "Neon"),
                             "language": speaker.get("language",
                                                     msg.data.get("lang")),
                             "gender": speaker.get("gender", default_gender),
                             "voice": speaker.get("voice")
                             })
            LOG.info(f">>> speaker={speaker}")

        # If multiple profiles attached to message, get TTS for all
        elif profiles:
            LOG.debug(f"Got profiles: {profiles}")
            for profile in profiles:
                username = profile.get("user", {}).get("username")
                lang_prefs = profile.get("speech") or dict()
                language = lang_prefs.get('tts_language') or 'en-us'
                second_lang = lang_prefs.get('secondary_tts_language') or \
                    language
                gender = lang_prefs.get('tts_gender') or default_gender
                LOG.debug(f"{username} requesting {gender} {language}")
                primary = {"speaker": tts_name,
                           "language": language,
                           "gender": gender,
                           "voice": None
                           }
                if second_lang != language:
                    second_gender = \
                        lang_prefs.get("secondary_tts_gender") or \
                        gender
                    secondary = {"speaker": tts_name,
                                 "language": second_lang,
                                 "gender": second_gender,
                                 "voice": None
                                 }
                else:
                    secondary = None
                if primary not in tts_reqs:
                    tts_reqs.append(primary)
                if secondary and secondary not in tts_reqs:
                    tts_reqs.append(secondary)

        # General non-server response, use yml configuration
        else:
            log_deprecation("speaker data or profile context required", "2.0.0")
            from neon_utils.configuration_utils import get_neon_user_config
            user_config = get_neon_user_config()["speech"]
            tts_reqs.append({"speaker": tts_name,
                             "language": user_config["tts_language"],
                             "gender": user_config["tts_gender"],
                             "voice": user_config["neon_voice"]
                             })
            if user_config["secondary_tts_language"] and \
                    user_config["secondary_tts_language"] != \
                    user_config["tts_language"]:
                tts_reqs.append(
                    {"speaker": tts_name,
                     "language": user_config["secondary_tts_language"],
                     "gender": user_config["secondary_tts_gender"] or
                        default_gender,
                     "voice": user_config["secondary_neon_voice"]
                     })
    except Exception as x:
        LOG.error(x)

    LOG.debug(f"Got {len(tts_reqs)} TTS Voice Requests")
    return tts_reqs


class NeonPlaybackThread(PlaybackThread):
    def __init__(self, queue, bus=None):
        LOG.info("Initializing NeonPlaybackThread")
        PlaybackThread.__init__(self, queue, bus=bus)

    def begin_audio(self, message=None):
        # TODO: Mark signals for deprecation
        check_for_signal("isSpeaking")
        create_signal("isSpeaking")
        PlaybackThread.begin_audio(self, message)

    def end_audio(self, listen, message=None):
        PlaybackThread.end_audio(self, listen, message)
        # TODO: Mark signals for deprecation
        check_for_signal("isSpeaking")

    def _play(self):
        ident = self._now_playing[3]
        if not ident and len(self._now_playing) >= 5 and \
                isinstance(self._now_playing[4], Message):
            LOG.debug("Handling new style playback")
            ident = self._now_playing[4].context.get('ident') or \
                self._now_playing[4].context.get('session',
                                                 {}).get('session_id')
        super()._play()
        LOG.info(f"Played {ident}")
        self.bus.emit(Message(ident))


class WrappedTTS(TTS):
    def __new__(cls, base_engine, *args, **kwargs):
        base_engine._stopwatch = Stopwatch("get_tts")
        base_engine.execute = cls.execute
        base_engine.get_multiple_tts = cls.get_multiple_tts
        # TODO: Below method is only to bridge compatibility
        base_engine._get_tts = cls._get_tts
        base_engine._init_playback = cls._init_playback
        return cls._init_neon(base_engine, *args, **kwargs)

    @staticmethod
    def _init_neon(base_engine, *args, **kwargs):
        """ called after the __init__ method to inject neon-core properties
        into the selected TTS engine """
        base_engine = base_engine(*args, **kwargs)

        language_config = Configuration().get("language") or dict()

        base_engine.keys = {}

        base_engine.language_config = language_config
        base_engine.lang = base_engine.lang or language_config.get("user",
                                                                   "en-us")
        try:
            if language_config.get('detection_module'):
                # Prevent loading a detector if not configured
                base_engine.lang_detector = \
                    OVOSLangDetectionFactory.create(language_config)
            if language_config.get('translation_module'):
                base_engine.translator = \
                    OVOSLangTranslationFactory.create(language_config)
        except ValueError as e:
            LOG.error(e)
            base_engine.lang_detector = None
            base_engine.translator = None

        cached_translations = JsonStorageXDG("tx_cache.json", subfolder="neon")
        cache_dir = dirname(cached_translations.path)

        os.makedirs(cache_dir, exist_ok=True)
        base_engine.cache_dir = cache_dir
        base_engine.cached_translations = cached_translations
        return base_engine

    def _init_playback(self, playback_thread: NeonPlaybackThread = None):
        # shutdown any previous thread
        if TTS.playback:
            TTS.playback.shutdown()
        if not isinstance(playback_thread, NeonPlaybackThread):
            LOG.exception("Received invalid playback_thread")
            playback_thread = None
        init_signal_bus(self.bus)
        TTS.playback = playback_thread or NeonPlaybackThread(TTS.queue)
        TTS.playback.set_bus(self.bus)
        TTS.playback.attach_tts(self)
        if not TTS.playback.enclosure:
            TTS.playback.enclosure = EnclosureAPI(self.bus)
        if not TTS.playback.is_running:
            TTS.playback.start()

    def _get_tts(self, sentence: str, request: dict = None, **kwargs):
        # TODO: Signature should be made to match ovos-audio
        if any([x in inspect.signature(self.get_tts).parameters
                for x in {"speaker", "wav_file"}]):
            LOG.info(f"Legacy Neon TTS signature found ({self.__class__.__name__})")
            key = str(hashlib.md5(
                sentence.encode('utf-8', 'ignore')).hexdigest())
            file = kwargs.get("wav_file") or \
                os.path.join(self.cache_dir, "tts", self.tts_name,
                             request["language"], request["gender"],
                             key + '.' + self.audio_ext)
            os.makedirs(dirname(file), exist_ok=True)
            if os.path.isfile(file):
                LOG.info(f"Using cached TTS audio")
                return file, None
            plugin_kwargs = dict()
            if "speaker" in inspect.signature(self.get_tts).parameters:
                plugin_kwargs['speaker'] = request
            if "wav_file" in inspect.signature(self.get_tts).parameters:
                plugin_kwargs['wav_file'] = file
            if "output_file" in inspect.signature(self.get_tts).parameters:
                plugin_kwargs['output_file'] = file

            return self.get_tts(sentence, **plugin_kwargs)
        else:
            # TODO: Handle language, gender, voice kwargs here
            return self.get_tts(sentence, **kwargs)

    def get_multiple_tts(self, message, **kwargs) -> dict:
        """
        Get tts responses based on message context
        """
        tts_requested = get_requested_tts_languages(message)
        LOG.debug(f"tts_requested={tts_requested}")
        sentence = message.data["text"]
        sentence = self.validate_ssml(sentence)
        skill_lang = message.data.get('lang') or self.lang
        LOG.debug(f"utterance_lang={skill_lang}")
        responses = {}
        for request in tts_requested:
            tts_lang = kwargs["lang"] = request["language"]
            # Check if requested tts lang matches internal (text) lang
            # TODO: `self.lang` should come from the incoming message
            if tts_lang.split("-")[0] != skill_lang.split("-")[0]:
                self.cached_translations.setdefault(tts_lang, {})

                tx_sentence = self.cached_translations[tts_lang].get(sentence)
                if not tx_sentence:
                    tx_sentence = self.translator.translate(sentence, tts_lang,
                                                            skill_lang)
                    self.cached_translations[tts_lang][sentence] = tx_sentence
                    self.cached_translations.store()
                LOG.info(f"Got translated sentence: {tx_sentence}")
            else:
                tx_sentence = sentence
            wav_file, phonemes = self._get_tts(tx_sentence, request, **kwargs)

            # If this is the first response, populate translation and phonemes
            responses.setdefault(tts_lang, {"sentence": tx_sentence,
                                            "translated": tx_sentence != sentence,
                                            "phonemes": phonemes,
                                            "genders": list()})

            # Append the generated audio from this request
            if os.path.isfile(wav_file):
                responses[tts_lang][request["gender"]] = wav_file
                responses[tts_lang]["genders"].append(request["gender"])
                # If this is a remote request, encode audio in the response
                if message.context.get("klat_data") or \
                        message.msg_type == "neon.get_tts":
                    responses[tts_lang].setdefault("audio", {})
                    responses[tts_lang]["audio"][request["gender"]] = \
                        encode_file_to_base64_string(wav_file)
                    LOG.debug(f"Got {tts_lang} {request['gender']} response")
            else:
                raise RuntimeError(f"No audio generated for request: {request}")
        return responses

    @resolve_message
    def execute(self, sentence: str, ident: str = None, listen: bool = False,
                message: Message = None, **kwargs):
        """Convert sentence to speech, preprocessing out unsupported ssml

        The method caches results if possible using the hash of the
        sentence.

        Arguments:
            sentence: (str) Sentence to be spoken
            ident: (str) Id reference to current interaction
            listen: (bool) True if listen should be triggered at the end
                    of the utterance.
            message: (Message) Message associated with request
            kwargs: (dict) optional keyword arguments to be passed to
            TTS engine get_tts method
        """
        if message:
            # Make sure to set the speaking signal now
            if not message.context.get("klat_data"):
                create_signal("isSpeaking")
            # TODO: Should sentence and ident be added to message context? DM
            message.data["text"] = sentence
            with self._stopwatch:
                responses = self.get_multiple_tts(message, **kwargs)
            message.context.setdefault('timing', dict())
            message.context['timing']['get_tts'] = self._stopwatch.time
            LOG.debug(f"responses={responses}")

            ident = message.data.get('speak_ident') or ident

            # TODO dedicated klat handler/plugin
            if "klat_data" in message.context:
                LOG.info("Sending klat.response")
                self.bus.emit(
                    message.forward("klat.response",
                                    {"responses": responses,
                                     "speaker": message.data.get("speaker")}))
                self.bus.emit(Message(ident))
            else:
                # Local user has multiple configured languages (or genders)
                for r in responses.values():
                    # get audio for selected voice gender
                    for gender in r["genders"]:
                        wav_file = r[gender]
                        # get mouth movement data
                        vis = self.viseme(r["phonemes"]) if r["phonemes"] \
                            else None
                        # queue for playback
                        self.queue.put((wav_file, vis, listen, ident, message))
                        self.handle_metric({"metric_type": "tts.queued"})
        else:
            LOG.warning(f'no Message associated with TTS request: {ident}')
            assert isinstance(self, TTS)
            create_signal("isSpeaking")
            TTS.execute(self, sentence, ident, listen, **kwargs)
