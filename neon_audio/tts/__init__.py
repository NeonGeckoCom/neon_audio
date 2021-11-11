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


import os
import os.path

from os.path import expanduser, dirname, join
from json_database import JsonStorageXDG, JsonStorage
from neon_utils.configuration_utils import get_neon_lang_config, NGIConfig, get_neon_audio_config, get_neon_user_config
from ovos_plugin_manager.tts import load_tts_plugin
from neon_utils.logger import LOG
from ovos_plugin_manager.tts import TTS as _TTS, OVOSTTSFactory
from ovos_plugin_manager.templates.tts import PlaybackThread, TTSValidator
from ovos_utils.signal import check_for_signal, create_signal
from ovos_plugin_manager.language import OVOSLangDetectionFactory, OVOSLangTranslationFactory


def _get_requested_tts_languages(msg) -> list:
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
            tts_reqs.append({"speaker": speaker["name"],
                             "language": speaker["language"],
                             "gender": speaker["gender"],
                             "voice": speaker.get("voice")
                             })
            LOG.debug(f">>> speaker={speaker}")

        # If multiple profiles attached to message, get TTS for all
        elif profiles:
            LOG.info(f"Got profiles: {profiles}")
            for profile in profiles:
                username = profile.get("user", {}).get("username")
                lang_prefs = profile.get("speech") or dict()
                language = lang_prefs.get('tts_language') or 'en-us'
                second_lang = lang_prefs.get('secondary_tts_language') or language
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
            LOG.warning("No profile information with request")
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

    if not tts_reqs:
        LOG.warning(f"No tts requested; using default en-us")
        tts_reqs = [{"speaker": "Neon",
                     "language": "en-us",
                     "gender": "female"
                     }]

    LOG.debug(f"Got {len(tts_reqs)} TTS Voice Requests")
    return tts_reqs


class TTS(_TTS):

    def __init__(self, *args, **kwargs):
        super(TTS, self).__init__(*args, **kwargs)
        # TODO ovos-core now also has an internal concept of secondary languages
        # unify the config !
        self.language_config = get_neon_lang_config()
        self.lang = self.lang or self.language_config.get("user", "en-us")
        self.lang_detector = OVOSLangDetectionFactory.create(self.language_config)
        self.translator = OVOSLangTranslationFactory.create(self.language_config)

        # TODO should cache be handled directly in each individual plugin?
        #   would also allow to do it per engine which can be advantageous
        neon_cache_dir = NGIConfig("ngi_local_conf").get('dirVars', {}).get('cacheDir')
        if neon_cache_dir:
            self.cache_dir = expanduser(neon_cache_dir)
            self.cached_translations = JsonStorage(join(self.cache_dir, "tx_cache.json"))
        else:
            self.cached_translations = JsonStorageXDG("tx_cache.json", subfolder="neon")
            self.cache_dir = dirname(self.cached_translations.path)

    def _preprocess_sentence(self, sentence):
        # TODO this can be deleted, only here to keep the commented code around

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
        return [sentence]

    def _parse_message(self, message, **kwargs):
        tts_requested = _get_requested_tts_languages(message)
        LOG.debug(f"tts_requested={tts_requested}")
        sentence = message.data["text"]
        responses = {}
        for request in tts_requested:
            lang = request["language"]
            if lang in self.cached_translations:
                sentence = self.cached_translations[lang].get(sentence)
            elif lang.split("-")[0] != "en":  # TODO: Internal lang DM
                self.cached_translations[lang][sentence] = self.translator.translate(sentence, lang, "en")
                self.cached_translations.store()
                sentence = self.cached_translations[lang][sentence]
                request["translated"] = True
            wav_file, phonemes = self._get_tts(sentence, **kwargs)
            if not responses.get(lang):
                responses[lang] = {"sentence": sentence}
            if os.path.isfile(wav_file):  # Based on <speak> tags, this may not exist
                responses[lang][request["gender"]] = wav_file
        return responses

    def execute(self, sentence, ident=None, listen=False, **kwargs):
        """Convert sentence to speech, preprocessing out unsupported ssml

        The method caches results if possible using the hash of the
        sentence.

        Arguments:
            sentence: (str) Sentence to be spoken
            ident: (str) Id reference to current interaction
            listen: (bool) True if listen should be triggered at the end
                    of the utterance.
            kwargs: (dict) optional keyword arguments to be passed to TTS engine get_tts method
        """
        sentence = self.validate_ssml(sentence)
        self.handle_metric({"metric_type": "tts.ssml.validated"})
        create_signal("isSpeaking")

        message = kwargs.get("message")
        if message:
            message.data["text"] = sentence  # ssml validated now
            responses = self._parse_message(message, **kwargs)
            # TODO dedicated klat plugin
            if message.context.get("klat_data"):
                responses = self._parse_message(message, **kwargs)
                LOG.debug(f"responses={responses}")
                self.bus.emit(message.forward("klat.response",
                    {"responses": responses,
                     "speaker": message.data.get("speaker")}))
            # API Call
            # TODO dedicated handler
            elif message.msg_type in ["neon.get_tts"]:
                return self._parse_message(message, **kwargs)
            # on device usage
            else:
                for lang, data in responses.items():
                    kwargs["lang"] = lang
                    # calling execute is fine, the audio will be cached already
                    super().execute(data["sentence"], ident, listen, **kwargs)
            return



class TTSFactory(OVOSTTSFactory):

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
        config["lang"] = config.get("language", {}).get("user") or config.get("lang", "en-us")
        return super().create(config)

