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

import os
import shutil
import sys
import unittest

from time import time
from os.path import join, dirname
from threading import Event
from mock import Mock
from mycroft_bus_client import Message
from ovos_plugin_manager.templates.tts import PlaybackThread
from ovos_utils.messagebus import FakeBus

from neon_utils.signal_utils import check_for_signal
from neon_utils.configuration_utils import _get_neon_local_config

sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
from neon_audio.tts import WrappedTTS

sys.path.append(os.path.dirname(os.path.realpath(__file__)))
from test_objects import DummyTTS, DummyTTSValidator


class TTSBaseClassTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.test_cache_dir = join(dirname(__file__), "test_cache")
        cls.test_conf_dir = join(dirname(__file__), "config")
        os.makedirs(cls.test_conf_dir, exist_ok=True)
        os.environ["NEON_CONFIG_PATH"] = cls.test_conf_dir
        config = _get_neon_local_config()
        config["dirVars"]["cacheDir"] = cls.test_cache_dir
        config.write_changes()
        cls.config = {"key": "val"}
        cls.lang = "en-us"
        cls.tts = WrappedTTS(DummyTTS, cls.lang, cls.config)
        bus = FakeBus()
        bus.connected_event = Event()
        bus.connected_event.set()
        cls.tts.init(bus)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tts.shutdown()
        if os.path.exists(cls.test_cache_dir):
            shutil.rmtree(cls.test_cache_dir)
        if os.path.exists(cls.test_conf_dir):
            shutil.rmtree(cls.test_conf_dir)
        os.environ.pop("NEON_CONFIG_PATH")

    def test_class_init(self):
        from ovos_plugin_manager.templates.tts import TTS
        # self.assertIsInstance(self.tts, WrappedTTS)
        self.assertIsInstance(self.tts, TTS)
        self.assertIsInstance(self.tts.bus, FakeBus)
        self.assertIsInstance(self.tts.language_config, dict)
        # TODO: Fix import errors in unit tests
        # self.assertIsNotNone(self.tts.lang_detector)
        # self.assertIsNotNone(self.tts.translator)
        self.assertEqual(self.tts.lang, self.lang)

        self.assertEqual(self.tts.config, self.config)
        self.assertIsInstance(self.tts.validator, DummyTTSValidator)
        self.assertFalse(self.tts.phonetic_spelling)
        self.assertEqual(self.tts.ssml_tags, ["speak"])

        self.assertEqual(self.tts.voice, "default")
        self.assertTrue(self.tts.queue.empty())
        self.assertIsInstance(self.tts.playback, PlaybackThread)

        self.assertIsInstance(self.tts.spellings, dict)
        self.assertEqual(self.tts.tts_name, "DummyTTS")
        self.assertIsInstance(self.tts.keys, dict)

        self.assertTrue(os.path.isdir(self.tts.cache_dir))
        # self.assertTrue(os.path.isfile(self.tts.translation_cache))
        self.assertIsInstance(self.tts.cached_translations, dict)

    def test_modify_tag(self):
        # TODO: Legacy
        self.assertEqual("test", self.tts.modify_tag("test"))

    def test_validate_ssml(self):
        # TODO: Legacy
        valid_tag_string = "<speak>hello</speak>"
        extra_tags_string = "<speak>hello</br></speak>"

        self.assertEqual(valid_tag_string, self.tts.validate_ssml(valid_tag_string))
        self.assertEqual(valid_tag_string, self.tts.validate_ssml(extra_tags_string))

    def test_preprocess_sentence(self):
        # TODO: Legacy
        sentence = "this is a test"
        self.assertEqual(self.tts._preprocess_sentence(sentence), [sentence])

    def test_execute(self):
        sentence = "testing"
        ident = time()
        default_execute = self.tts._execute
        self.tts._execute = Mock()
        self.tts.execute(sentence, ident)
        self.assertTrue(check_for_signal("isSpeaking"))
        self.tts._execute.assert_called_once_with(sentence, ident, False)
        self.tts._execute = default_execute

        default_get_multiple_tts = self.tts.get_multiple_tts
        self.tts.get_multiple_tts = Mock(return_value=dict())
        message = Message("test")
        self.tts.execute(sentence, ident, message=message)
        self.tts.get_multiple_tts.assert_called_once_with(message)
        self.tts.get_multiple_tts = default_get_multiple_tts

    def test_get_multiple_tts(self):
        # TODO
        pass

    def test_viseme(self):
        # TODO: Legacy
        self.assertIsNone(self.tts.viseme(""))

    def test_validator_valid(self):
        self.assertTrue(self.tts.validator.validate_lang())
        self.assertTrue(self.tts.validator.validate_dependencies())
        self.assertTrue(self.tts.validator.validate_connection())

    def test_validator_invalid(self):
        tts = DummyTTS("es", {})

        with self.assertRaises(Exception):
            tts.validator.validate()

        tts.shutdown()

    def test_get_tts(self):
        test_file_path = join(dirname(__file__), "test.wav")
        file, phonemes = self.tts._get_tts("test", wav_file=test_file_path,
                                           speaker={})
        self.assertEqual(file, test_file_path)
        self.assertIsNone(phonemes)


class TTSUtilTests(unittest.TestCase):
    def test_install_tts_plugin(self):
        from neon_audio.utils import install_tts_plugin
        self.assertTrue(install_tts_plugin("coqui"))
        self.assertTrue(install_tts_plugin("neon-tts-plugin-coqui"))
        self.assertFalse(install_tts_plugin("neon-tts-plugin-invalid"))

    def test_patch_config(self):
        import json
        from neon_audio.utils import use_neon_audio
        from neon_utils.configuration_utils import init_config_dir
        test_config_dir = os.path.join(os.path.dirname(__file__), "config")
        os.makedirs(test_config_dir, exist_ok=True)
        os.environ["XDG_CONFIG_HOME"] = test_config_dir
        use_neon_audio(init_config_dir)()

        with open(join(test_config_dir, "OpenVoiceOS", 'ovos.conf')) as f:
            ovos_conf = json.load(f)
        self.assertEqual(ovos_conf['submodule_mappings']['neon_audio'],
                         "neon_core")
        self.assertIsInstance(ovos_conf['module_overrides']['neon_core'], dict)

        from neon_audio.utils import patch_config
        import yaml
        test_config = {"new_key": {'val': True}}
        patch_config(test_config)
        conf_file = os.path.join(test_config_dir, 'neon',
                                 'neon.yaml')
        self.assertTrue(os.path.isfile(conf_file))
        with open(conf_file) as f:
            config = yaml.safe_load(f)

        self.assertTrue(config['new_key']['val'])
        shutil.rmtree(test_config_dir)
        os.environ.pop("XDG_CONFIG_HOME")


if __name__ == '__main__':
    unittest.main()
