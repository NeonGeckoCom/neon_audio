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

from time import time

import os
import sys
import unittest

from multiprocessing import Process

from mycroft_bus_client import MessageBusClient, Message
from neon_utils.configuration_utils import get_neon_audio_config
from neon_messagebus.service import NeonBusService

sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
from neon_audio.__main__ import main as neon_audio_main

TEST_CONFIG = get_neon_audio_config()
TEST_CONFIG["tts"]["module"] = "mozilla_remote"
TEST_CONFIG["tts"]["mozilla_remote"] = {"api_url": os.environ.get("TTS_URL")}


class TestAPIMethods(unittest.TestCase):
    bus_thread = None
    audio_thread = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.bus_thread = NeonBusService(daemonic=True)
        cls.audio_thread = Process(target=neon_audio_main, kwargs={"config": TEST_CONFIG}, daemon=False)
        cls.bus_thread.start()
        cls.audio_thread.start()
        cls.bus = MessageBusClient()
        cls.bus.run_in_thread()
        cls.bus.connected_event.wait(30)
        alive = False
        while not alive:
            message = cls.bus.wait_for_response(Message("mycroft.audio.is_ready"))
            if message:
                alive = message.data.get("status")

    @classmethod
    def tearDownClass(cls) -> None:
        super(TestAPIMethods, cls).tearDownClass()
        cls.bus_thread.shutdown()
        cls.audio_thread.terminate()

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
        tts_resp = self.bus.wait_for_response(Message("neon.get_tts", {"text": text}, context),
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
