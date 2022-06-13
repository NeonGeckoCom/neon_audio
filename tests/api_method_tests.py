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

from time import time

import os
import sys
import unittest

from mycroft_bus_client import MessageBusClient, Message
from neon_utils.configuration_utils import init_config_dir
from neon_messagebus.service import NeonBusService

from mycroft.configuration import Configuration

sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
from neon_audio.service import NeonPlaybackService
from neon_audio.utils import use_neon_audio


class TestAPIMethods(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        test_config_dir = os.path.join(os.path.dirname(__file__), "config")
        os.makedirs(test_config_dir, exist_ok=True)
        os.environ["XDG_CONFIG_HOME"] = test_config_dir
        use_neon_audio(init_config_dir)()

        test_config = Configuration()
        test_config["tts"]["module"] = "mozilla_remote"
        test_config["tts"]["mozilla_remote"] = \
            {"api_url": os.environ.get("TTS_URL") or "https://mtts.2022.us"}
        assert test_config["tts"]["module"] == "mozilla_remote"

        cls.messagebus = NeonBusService(debug=True, daemonic=True)
        cls.messagebus.start()
        cls.audio_service = NeonPlaybackService(audio_config=test_config,
                                                daemonic=True)
        cls.audio_service.start()
        cls.bus = MessageBusClient()
        cls.bus.run_in_thread()
        if not cls.bus.connected_event.wait(30):
            raise TimeoutError("Bus not connected after 60 seconds")
        alive = False
        timeout = time() + 120
        while not alive and time() < timeout:
            message = cls.bus.wait_for_response(Message("mycroft.audio.is_ready"))
            if message:
                alive = message.data.get("status")
        if not alive:
            raise TimeoutError("Speech module not ready after 120 seconds")

    @classmethod
    def tearDownClass(cls) -> None:
        super(TestAPIMethods, cls).tearDownClass()
        cls.messagebus.shutdown()
        cls.audio_service.shutdown()

    def test_get_tts_no_sentence(self):
        context = {"client": "tester",
                   "ident": "123",
                   "user": "TestRunner"}
        tts_resp = self.bus.wait_for_response(Message("neon.get_tts", {}, context), context["ident"])
        self.assertEqual(tts_resp.context, context)
        self.assertIsInstance(tts_resp.data.get("error"), str)
        self.assertEqual(tts_resp.data["error"], "No text provided.")

    def test_get_tts_invalid_type(self):
        context = {"client": "tester",
                   "ident": "1234",
                   "user": "TestRunner"}
        tts_resp = self.bus.wait_for_response(Message("neon.get_tts", {"text": 123}, context),
                                              context["ident"], timeout=60)
        self.assertEqual(tts_resp.context, context)
        self.assertTrue(tts_resp.data.get("error").startswith("text is not a str:"))

    def test_get_tts_valid_default(self):
        text = "This is a test"
        context = {"client": "tester",
                   "ident": str(time()),
                   "user": "TestRunner"}
        tts_resp = self.bus.wait_for_response(Message("neon.get_tts",
                                                      {"text": text}, context),
                                              context["ident"], timeout=60)
        self.assertEqual(tts_resp.context, context)
        responses = tts_resp.data
        self.assertIsInstance(responses, dict)
        print(responses)
        self.assertEqual(len(responses), 1)
        resp = list(responses.values())[0]
        self.assertIsInstance(resp, dict)
        self.assertEqual(resp.get("sentence"), text)

    # TODO: Test with multiple languages
    def test_get_tts_valid_speaker(self):
        pass


if __name__ == '__main__':
    unittest.main()
