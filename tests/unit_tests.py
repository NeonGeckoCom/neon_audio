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
import shutil
import sys
import unittest

from mock import Mock
from ovos_utils.messagebus import FakeBus

from neon_utils import is_speaking

sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
from neon_audio.tts import *

sys.path.append(os.path.dirname(os.path.realpath(__file__)))
from test_objects import DummyTTS, DummyTTSValidator


class TTSBaseClassTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.test_cache_dir = join(dirname(__file__), "test_cache")
        cls.test_conf_dir = join(dirname(__file__), "config")
        os.environ["NEON_CONFIG_PATH"] = cls.test_conf_dir
        config = get_neon_local_config()
        config["dirVars"]["cacheDir"] = cls.test_cache_dir
        config.write_changes()
        cls.config = dict()
        cls.lang = "en-us"
        cls.tts = DummyTTS(cls.lang, cls.config)
        cls.tts.init(FakeBus())

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tts.shutdown()
        if os.path.exists(cls.test_cache_dir):
            shutil.rmtree(cls.test_cache_dir)
        if os.path.exists(cls.test_conf_dir):
            shutil.rmtree(cls.test_conf_dir)
        os.environ.pop("NEON_CONFIG_PATH")

    def test_class_init(self):
        self.assertIsInstance(self.tts.bus, FakeBus)
        self.assertIsInstance(self.tts.language_config, dict)
        self.assertIsNotNone(self.tts.lang_detector)
        self.assertIsNotNone(self.tts.translator)
        self.assertEqual(self.tts.lang, self.lang)

        self.assertEqual(self.tts.config, self.config)
        self.assertIsInstance(self.tts.validator, DummyTTSValidator)
        self.assertFalse(self.tts.phonetic_spelling)
        self.assertEqual(self.tts.ssml_tags, ["speak"])

        self.assertIsNone(self.tts.voice)
        self.assertTrue(self.tts.queue.empty())
        self.assertIsInstance(self.tts.playback, PlaybackThread)

        self.assertIsInstance(self.tts.spellings, dict)
        self.assertEqual(self.tts.tts_name, "DummyTTS")
        self.assertIsInstance(self.tts.keys, dict)

        self.assertTrue(os.path.isdir(self.tts.cache_dir))
        self.assertTrue(os.path.isfile(self.tts.translation_cache))
        self.assertIsInstance(self.tts.cached_translations, dict)

    def test_load_spellings(self):
        # TODO: Init a tts object and test load of phonetic_spellings.txt
        pass

    def test_begin_audio(self):
        # TODO: bus listener and test call
        pass

    def test_end_audio(self):
        # TODO: bus listener and test call
        pass

    def test_modify_tag(self):
        self.assertEqual("test", self.tts.modify_tag("test"))

    def test_validate_ssml(self):
        valid_tag_string = "<speak>hello</speak>"
        extra_tags_string = "<speak>hello</br></speak>"

        self.assertEqual(valid_tag_string, self.tts.validate_ssml(valid_tag_string))
        self.assertEqual(valid_tag_string, self.tts.validate_ssml(extra_tags_string))

    def test_preprocess_sentence(self):
        sentence = "this is a test"
        self.assertEqual(self.tts._preprocess_sentence(sentence), [sentence])

    def test_execute(self):
        sentence = "testing"
        ident = time()
        default_execute = self.tts._execute
        self.tts._execute = Mock()
        self.tts.execute(sentence, ident)
        self.assertTrue(is_speaking())
        self.tts._execute.assert_called_once_with(sentence, ident, False, None)
        self.tts._execute = default_execute

        # TODO: Test tts._execute

    def test_viseme(self):
        self.assertIsNone(self.tts.viseme(""))

    def test_clear_cache(self):
        # TODO: Update method and add tests
        pass

    def test_save_phonemes(self):
        # TODO
        pass

    def test_load_phonemes(self):
        # TODO
        pass



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
        file, phonemes = self.tts.get_tts("test", "file_path", speaker={})
        self.assertEqual(file, "file_path")
        self.assertIsNone(phonemes)


# TODO: TTSValidator, TTSFactory, PlaybackThread tests DM

if __name__ == '__main__':
    unittest.main()