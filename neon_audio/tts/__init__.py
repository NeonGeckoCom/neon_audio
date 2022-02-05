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

import pickle
import hashlib
import os
import random
import re
import os.path

from copy import deepcopy
from abc import ABCMeta, abstractmethod
from threading import Thread
from time import time
from queue import Queue, Empty
from os.path import dirname, exists, isdir, join

from neon_utils.configuration_utils import get_neon_lang_config, get_neon_audio_config,\
    get_neon_user_config, get_neon_local_config
from mycroft_bus_client import Message
from ovos_plugin_manager.tts import load_tts_plugin
from neon_utils.logger import LOG
from neon_utils.metrics_utils import Stopwatch
from ovos_utils import resolve_resource_file

from neon_utils.signal_utils import create_signal, check_for_signal

try:
    from neon_core.language import DetectorFactory, TranslatorFactory
except ImportError:
    LOG.error("Language Detector and Translator not available")
    DetectorFactory, TranslatorFactory = None, None

from mycroft.util import play_wav, play_mp3, get_cache_directory, curate_cache


_TTS_ENV = deepcopy(os.environ)
_TTS_ENV['PULSE_PROP'] = 'media.role=phone'

_IPC_DIR = get_neon_local_config()["dirVars"]["ipcDir"]

EMPTY_PLAYBACK_QUEUE_TUPLE = (None, None, None, None, None)


class PlaybackThread(Thread):
    """Thread class for playing back tts audio and sending
    viseme data to enclosure.
    """

    def __init__(self, queue, config=None):
        super(PlaybackThread, self).__init__()
        self.tts = None
        self.queue = queue
        self._terminated = False
        self._processing_queue = False
        self.enclosure = None
        self.p = None
        # Check if the tts shall have a ducking role set
        config = config or get_neon_audio_config()
        if config.get('tts', {}).get('pulse_duck'):
            self.pulse_env = _TTS_ENV
        else:
            self.pulse_env = None

    def init(self, tts):
        self.tts = tts

    def clear_queue(self):
        """Remove all pending playbacks."""
        while not self.queue.empty():
            self.queue.get()
        try:
            self.p.terminate()
        except Exception as e:
            LOG.error(e)

    def run(self):
        """Thread main loop. Get audio and extra data from queue and play.

        The queue messages is a tuple containing
        snd_type: 'mp3' or 'wav' telling the loop what format the data is in
        data: path to temporary audio data
        videmes: list of visemes to display while playing
        listen: if listening should be triggered at the end of the sentence.

        Playback of audio is started and the visemes are sent over the bus
        the loop then wait for the playback process to finish before starting
        checking the next position in queue.

        If the queue is empty the tts.end_audio() is called possibly triggering
        listening.
        """
        while not self._terminated:
            listen = False
            ident = None
            try:
                (snd_type, data, visemes, ident, listen) = self.queue.get(timeout=2)
                self.blink(0.5)
                if not self._processing_queue:
                    self._processing_queue = True
                    self.tts.begin_audio(ident)

                stopwatch = Stopwatch()
                with stopwatch:
                    if snd_type == 'wav':
                        self.p = play_wav(data, environment=self.pulse_env)
                    elif snd_type == 'mp3':
                        self.p = play_mp3(data, environment=self.pulse_env)
                    if visemes:
                        self.show_visemes(visemes)
                    if self.p:
                        self.p.communicate()
                        self.p.wait()
                # report_timing(ident, 'speech_playback', stopwatch)

                if self.queue.empty():
                    self.tts.end_audio(listen, ident)
                    self._processing_queue = False
                self.blink(0.2)
            except Empty:
                pass
            except Exception as e:
                LOG.exception(e)
                if self._processing_queue:
                    self.tts.end_audio(listen, ident)
                    self._processing_queue = False

    def show_visemes(self, pairs):
        """Send viseme data to enclosure

        Arguments:
            pairs(list): Visime and timing pair

        Returns:
            True if button has been pressed.
        """
        if self.enclosure:
            self.enclosure.mouth_viseme(time(), pairs)

    def clear(self):
        """Clear all pending actions for the TTS playback thread."""
        self.clear_queue()

    def blink(self, rate=1.0):
        """Blink mycroft's eyes"""
        if self.enclosure and random.random() < rate:
            self.enclosure.eyes_blink("b")

    def stop(self):
        """Stop thread"""
        self._terminated = True
        self.clear_queue()


class TTS(metaclass=ABCMeta):
    """TTS abstract class to be implemented by all TTS engines.

    It aggregates the minimum required parameters and exposes
    ``execute(sentence)`` and ``validate_ssml(sentence)`` functions.

    Arguments:
        lang (str):
        config (dict): Configuration for this specific tts engine
        validator (TTSValidator): Used to verify proper installation
        phonetic_spelling (bool): Whether to spell certain words phonetically
        ssml_tags (list): Supported ssml properties. Ex. ['speak', 'prosody']
    """

    def __init__(self, lang, config, validator, audio_ext='wav',
                 phonetic_spelling=True, ssml_tags=None):
        super(TTS, self).__init__()
        self.bus = None  # initalized in "init" step

        self.language_config = get_neon_lang_config()
        self.lang_detector = DetectorFactory.create() if DetectorFactory else None
        self.translator = TranslatorFactory.create() if DetectorFactory else None
        self.lang = lang or self.language_config.get("user", "en-us")

        self.config = config
        self.validator = validator
        self.phonetic_spelling = phonetic_spelling
        self.audio_ext = audio_ext
        self.ssml_tags = ssml_tags or []

        self.voice = config.get("voice")
        self.filename = '/tmp/tts.wav'  # TODO: Is this deprecated? DM
        # self.enclosure = None
        random.seed()
        self.queue = Queue()
        self.playback = PlaybackThread(self.queue, config)
        self.playback.start()
        self.clear_cache()
        self.spellings = self.load_spellings()
        self.tts_name = type(self).__name__
        self.keys = {}

        self.cache_dir = os.path.expanduser(get_neon_local_config()['dirVars']
                                            .get('cacheDir') or "~/.cache/neon")
        os.makedirs(self.cache_dir, exist_ok=True)

        self.translation_cache = os.path.join(self.cache_dir, 'lang_dict.txt')
        if not os.path.isfile(self.translation_cache):
            open(self.translation_cache, 'wb+').close()
        with open(self.translation_cache, 'rb') as cached_utterances:
            try:
                self.cached_translations = pickle.load(cached_utterances)
            except EOFError:
                self.cached_translations = {}
                LOG.info("Cache file exists, but it's empty so far")

    def shutdown(self):
        self.playback.stop()
        self.playback.join()

    def load_spellings(self):
        """Load phonetic spellings of words as dictionary"""
        path = join('text', self.lang.lower(), 'phonetic_spellings.txt')
        spellings_file = resolve_resource_file(path)
        if not spellings_file:
            return {}
        try:
            with open(spellings_file) as f:
                lines = filter(bool, f.read().split('\n'))
            lines = [i.split(':') for i in lines]
            return {key.strip(): value.strip() for key, value in lines}
        except ValueError:
            LOG.exception('Failed to load phonetic spellings.')
            return {}

    def begin_audio(self, ident=None):
        """Helper function for child classes to call in execute()"""
        # Create signals informing start of speech
        self.bus.emit(Message("recognizer_loop:audio_output_start", context={"ident": ident}))

    def end_audio(self, listen=False, ident=None):
        """Helper function for child classes to call in execute().

        Sends the recognizer_loop:audio_output_end message (indicating
        that speaking is done for the moment) as well as trigger listening
        if it has been requested. It also checks if cache directory needs
        cleaning to free up disk space.

        Arguments:
            listen (bool): indication if listening trigger should be sent.
            ident (str): Identifier of the input utterance associated with the response
        """

        self.bus.emit(Message("recognizer_loop:audio_output_end", context={"ident": ident}))
        if listen:
            self.bus.emit(Message('mycroft.mic.listen'))
        # Clean the cache as needed
        # TODO: Check self cache path DM
        cache_dir = get_cache_directory("tts/" + self.tts_name)
        curate_cache(cache_dir, min_free_percent=100)

        # This check will clear the "signal"
        check_for_signal("isSpeaking")

    def init(self, bus):
        """Performs initial setup of TTS object.

        Arguments:
            bus:    Mycroft messagebus connection
        """
        self.bus = bus
        self.playback.init(self)

    def get_tts(self, sentence, wav_file, request=None):
        """Abstract method that a tts implementation needs to implement.

        Should get data from tts.

        Arguments:
            sentence(str): Sentence to synthesize
            wav_file(str): output file
            request(dict): Dict of tts request data

        Returns:
            tuple: (wav_file, phoneme)
        """
        pass

    def modify_tag(self, tag):
        """Override to modify each supported ssml tag"""
        return tag

    @staticmethod
    def remove_ssml(text):
        return re.sub('<[^>]*>', '', text).replace('  ', ' ')

    def validate_ssml(self, utterance):
        """Check if engine supports ssml, if not remove all tags.

        Remove unsupported / invalid tags

        Arguments:
            utterance(str): Sentence to validate

        Returns:
            validated_sentence (str)
        """
        # if ssml is not supported by TTS engine remove all tags
        if not self.ssml_tags:
            return self.remove_ssml(utterance)

        # find ssml tags in string
        tags = re.findall('<[^>]*>', utterance)

        for tag in tags:
            if any(supported in tag for supported in self.ssml_tags):
                utterance = utterance.replace(tag, self.modify_tag(tag))
            else:
                # remove unsupported tag
                utterance = utterance.replace(tag, "")

        # return text with supported ssml tags only
        return utterance.replace("  ", " ")

    def _preprocess_sentence(self, sentence):
        """Default preprocessing is no preprocessing.

        This method can be overridden to create chunks suitable to the
        TTS engine in question.

        Arguments:
            sentence (str): sentence to preprocess

        Returns:
            list: list of sentence parts
        """
        return [sentence]

    def execute(self, sentence, ident=None, listen=False, message=None):
        """Convert sentence to speech, preprocessing out unsupported ssml

            The method caches results if possible using the hash of the
            sentence.

            Arguments:
                sentence:   Sentence to be spoken
                ident:      Id reference to current interaction
                listen:     True if listen should be triggered at the end
                            of the utterance.
                message:    Message associated with request
        """
        # TODO: dig_for_message here for general compat. DM
        sentence = self.validate_ssml(sentence)

        # multi lang support
        # NOTE this is kinda optional because skills will translate
        # However speak messages might be sent directly to bus
        # this is here to cover that use case

        # # check for user specified language
        # if message and hasattr(message, "user_data"):
        #     user_lang = message.user_data.get("lang") or self.language_config["user"]
        # else:
        #     user_lang = self.language_config["user"]
        #
        # detected_lang = self.lang_detector.detect(sentence)
        # LOG.debug("Detected language: {lang}".format(lang=detected_lang))
        # if detected_lang != user_lang.split("-")[0]:
        #     sentence = self.translator.translate(sentence, user_lang)
        create_signal("isSpeaking")

        try:
            return self._execute(sentence, ident, listen, message)
        except Exception:
            # If an error occurs end the audio sequence through an empty entry
            self.queue.put(EMPTY_PLAYBACK_QUEUE_TUPLE)
            # Re-raise to allow the Exception to be handled externally as well.
            raise

    def _execute(self, sentence: str, ident: str, listen: bool, message: Message):
        def _get_requested_tts_languages(msg) -> list:
            """
            Builds a list of the requested TTS for a given spoken response
            :param msg: Message associated with request
            :return: List of TTS dict data
            """
            profiles = msg.context.get("nick_profiles")
            tts_name = "Neon"

            tts_reqs = []
            # Get all of our language parameters
            try:
                # If speaker data is present, use it
                if msg.data.get("speaker"):
                    speaker = msg.data.get("speaker")
                    tts_reqs.append({"speaker": speaker["name"],
                                     "language": speaker["language"],
                                     "gender": speaker["gender"],
                                     "voice": speaker.get("voice")
                                     })
                    LOG.debug(f">>> speaker={speaker}")

                # If multiple profiles attached to message, get TTS for all of them
                elif profiles:
                    LOG.info(f"Got profiles: {profiles}")
                    for nickname in profiles:
                        chat_user = profiles.get(nickname, None)
                        user_lang = chat_user.get("speech", chat_user)
                        language = user_lang.get('tts_language', 'en-us')
                        gender = user_lang.get('tts_gender', 'female')
                        LOG.debug(f"{nickname} requesting {gender} {language}")
                        data = {"speaker": tts_name,
                                "language": language,
                                "gender": gender,
                                "voice": None
                                }
                        if data not in tts_reqs:
                            tts_reqs.append(data)

                # General non-server response, use yml configuration
                else:
                    user_config = get_neon_user_config()["speech"]

                    tts_reqs.append({"speaker": tts_name,
                                     "language": user_config["tts_language"],
                                     "gender": user_config["tts_gender"],
                                     "voice": user_config["neon_voice"]
                                     })

                    if user_config["secondary_tts_language"] and \
                            user_config["secondary_tts_language"] != user_config["tts_language"]:
                        tts_reqs.append({"speaker": tts_name,
                                         "language": user_config["secondary_tts_language"],
                                         "gender": user_config["secondary_tts_gender"],
                                         "voice": user_config["secondary_neon_voice"]
                                         })
            except Exception as x:
                LOG.error(x)

            if not tts_reqs:
                LOG.warning(f"No tts requested; using default en-us")
                tts_reqs = [{"speaker": "Neon",
                             "language": "en-us",
                             "gender": "female"
                             }]

            # TODO: Associate voice with cache here somehow? (would be a per-TTS engine set) DM
            LOG.debug(f"Got {len(tts_reqs)} TTS Voice Requests")
            return tts_reqs

        def _update_pickle():
            with open(self.translation_cache, 'wb+') as cached_utterances:
                pickle.dump(self.cached_translations, cached_utterances)

        if self.phonetic_spelling:
            for word in re.findall(r"[\w']+", sentence):
                if word.lower() in self.spellings:
                    sentence = sentence.replace(word,
                                                self.spellings[word.lower()])

        chunks = self._preprocess_sentence(sentence)
        # Apply the listen flag to the last chunk, set the rest to False
        chunks = [(chunks[i], listen if i == len(chunks) - 1 else False)
                  for i in range(len(chunks))]

        for sentence, l in chunks:
            key = str(hashlib.md5(
                sentence.encode('utf-8', 'ignore')).hexdigest())
            phonemes = None
            response_audio_files = []
            tts_requested = _get_requested_tts_languages(message)
            LOG.debug(f"tts_requested={tts_requested}")

            # Go through all the audio we need and see if it is in the cache
            responses = {}
            for request in tts_requested:
                # TODO: This is the cache dir that should be used everywhere DM
                file = os.path.join(self.cache_dir, "tts", self.tts_name,
                                    request["language"], request["gender"], key + '.' + self.audio_ext)
                lang = request["language"]
                translated_sentence = None
                try:
                    # Handle any missing cache directories
                    if not exists(os.path.dirname(file)):
                        os.makedirs(os.path.dirname(file), exist_ok=True)

                    # Get cached text response
                    if os.path.exists(file):
                        LOG.debug(f">>>{lang}{key} in cache<<<")
                        phonemes = self.load_phonemes(key)
                        LOG.debug(phonemes)

                        # Get cached translation (remove audio if no corresponding translation)
                        if f"{lang}{key}" in self.cached_translations:
                            translated_sentence = self.cached_translations[f"{lang}{key}"]
                        else:
                            LOG.error("cache error! Removing audio file")
                            os.remove(file)

                    # If no file cached or cache error was encountered, get tts
                    if not translated_sentence:
                        LOG.debug(f"{lang}{key} not cached")
                        if not lang.split("-", 1)[0] == "en" and self.translator:  # TODO: Internal lang DM
                            translated_sentence = self.translator.translate(sentence, lang, "en")
                            LOG.info(translated_sentence)
                        else:
                            translated_sentence = sentence
                        file, phonemes = self.get_tts(translated_sentence, file, request)
                        # Update cache for next time
                        self.cached_translations[f"{lang}{key}"] = translated_sentence
                        LOG.debug(f">>>Cache Updated! ({file})<<<")
                        _update_pickle()
                except Exception as e:
                    # Remove audio file if any exception occurs, this forces re-translation/cache next time
                    LOG.error(e)
                    if os.path.exists(file):
                        os.remove(file)

                if not responses.get(lang):
                    responses[lang] = {"sentence": translated_sentence}
                if os.path.isfile(file):  # Based on <speak> tags, this may not exist
                    responses[lang][request["gender"]] = file
                    response_audio_files.append(file)

            # Server execution - send mycroft's speech (wav file) over to the chat_server
            if message.context.get("klat_data"):
                LOG.debug(f"responses={responses}")
                self.bus.emit(message.forward("klat.response", {"responses": responses,
                                                                "speaker": message.data.get("speaker")}))
                # self.bus.wait_for_response
            # API Call
            elif message.msg_type in ["neon.get_tts"]:
                return responses
            # Non-server execution
            else:
                if response_audio_files:
                    vis = self.viseme(phonemes) if phonemes else phonemes
                    for response in response_audio_files:
                        self.queue.put((self.audio_ext, str(response), vis, ident, listen))
                else:
                    check_for_signal("isSpeaking", config={"ipc_path": _IPC_DIR})

    def viseme(self, phonemes):
        """Create visemes from phonemes. Needs to be implemented for all
            tts backends.

            Arguments:
                phonemes(str): String with phoneme data
        """
        return None

    @staticmethod
    def clear_cache():
        # TODO: This should probably only clear this plugin's cache DM
        """Remove all cached files."""
        if not os.path.exists(get_cache_directory('tts')):
            return
        for d in os.listdir(get_cache_directory("tts")):
            dir_path = os.path.join(get_cache_directory("tts"), d)
            if os.path.isdir(dir_path):
                for f in os.listdir(dir_path):
                    file_path = os.path.join(dir_path, f)
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
            # If no sub-folders are present, check if it is a file & clear it
            elif os.path.isfile(dir_path):
                os.unlink(dir_path)

    def save_phonemes(self, key, phonemes):
        """Cache phonemes

        Arguments:
            key:        Hash key for the sentence
            phonemes:   phoneme string to save
        """
        # TODO: Should this be deprecated? DM
        cache_dir = get_cache_directory("tts/" + self.tts_name)
        pho_file = os.path.join(cache_dir, key + ".pho")
        try:
            with open(pho_file, "w") as cachefile:
                cachefile.write(phonemes)
        except Exception as e:
            LOG.error(e)
            LOG.exception("Failed to write {} to cache".format(pho_file))
            pass

    def load_phonemes(self, key):
        """Load phonemes from cache file.

        Arguments:
            key:    Key identifying phoneme cache
        """
        pho_file = os.path.join(
            get_cache_directory("tts/" + self.tts_name),
            key + ".pho")
        if os.path.exists(pho_file):
            try:
                with open(pho_file, "r") as cachefile:
                    phonemes = cachefile.read().strip()
                return phonemes
            except Exception as e:
                LOG.error(e)
                LOG.debug("Failed to read .PHO from cache")
        return None

    def __del__(self):
        self.shutdown()


class TTSValidator(metaclass=ABCMeta):
    """TTS Validator abstract class to be implemented by all TTS engines.

    It exposes and implements ``validate(tts)`` function as a template to
    validate the TTS engines.
    """

    def __init__(self, tts):
        self.tts = tts

    def validate(self):
        self.validate_dependencies()
        self.validate_instance()
        self.validate_filename()
        self.validate_lang()
        self.validate_connection()

    def validate_dependencies(self):
        pass

    def validate_instance(self):
        clazz = self.get_tts_class()
        if not isinstance(self.tts, clazz):
            raise AttributeError('tts must be instance of ' + clazz.__name__)

    def validate_filename(self):
        filename = self.tts.filename
        if not (filename and filename.endswith('.wav')):
            raise AttributeError('file: %s must be in .wav format!' % filename)

        dir_path = dirname(filename)
        if not (exists(dir_path) and isdir(dir_path)):
            raise AttributeError('filename: %s is not valid!' % filename)

    @abstractmethod
    def validate_lang(self):
        pass

    @abstractmethod
    def validate_connection(self):
        pass

    @abstractmethod
    def get_tts_class(self):
        pass


class TTSFactory:

    CLASSES = {}

    @staticmethod
    def create(config=None):
        """Factory method to create a TTS engine based on configuration.

        The configuration file ``mycroft.conf`` contains a ``tts`` section with
        the name of a TTS module to be read by this method.

        "tts": {
            "module": <engine_name>
        }
        """
        config = config or get_neon_audio_config()
        lang = config.get("language", {}).get("user") or config.get("lang", "en-us")
        tts_module = config.get('tts', {}).get('module', 'mimic')
        tts_config = config.get('tts', {}).get(tts_module, {})
        tts_lang = tts_config.get('lang', lang)
        try:
            if tts_module in TTSFactory.CLASSES:
                clazz = TTSFactory.CLASSES[tts_module]
            else:
                clazz = load_tts_plugin(tts_module)
                LOG.info('Loaded plugin {}'.format(tts_module))
            if clazz is None:
                raise ValueError('TTS module not found')

            tts = clazz(tts_lang, tts_config)
            tts.validator.validate()
        except Exception as e:
            LOG.error(e)
            # Fallback to mimic if an error occurs while loading.
            if tts_module != 'mimic':
                LOG.exception('The selected TTS backend couldn\'t be loaded. '
                              'Falling back to Mimic')
                clazz = TTSFactory.CLASSES.get('mimic')
                tts = clazz(tts_lang, tts_config)
                tts.validator.validate()
            else:
                LOG.exception('The TTS could not be loaded.')
                raise

        return tts
