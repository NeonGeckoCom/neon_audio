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
from time import sleep, time

import os
import sys
import unittest

from multiprocessing import Process

from mycroft_bus_client import MessageBusClient, Message
from neon_utils.configuration_utils import get_neon_audio_config
from mycroft.messagebus.service.__main__ import main as messagebus_service

sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
from neon_audio.__main__ import main as neon_audio_main

TEST_CONFIG = get_neon_audio_config()
TEST_CONFIG["tts"] = TEST_CONFIG.get("tts", {})  # TODO: Depreciate with neon_utils update DM
TEST_CONFIG["tts"]["module"] = "amazon_polly"
TEST_CONFIG["tts"]["mozilla_remote"] = {"api_url": "http://64.34.186.120:5002"}
# TODO: Also export URL for testing DM


class TestAPIMethods(unittest.TestCase):
    bus_thread = None
    audio_thread = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.bus_thread = Process(target=messagebus_service, daemon=False)
        cls.audio_thread = Process(target=neon_audio_main, args=(TEST_CONFIG,), daemon=False)
        cls.bus_thread.start()
        cls.audio_thread.start()
        cls.bus = MessageBusClient()
        cls.bus.run_in_thread()
        while not cls.bus.started_running:
            sleep(1)
        sleep(15)

    @classmethod
    def tearDownClass(cls) -> None:
        super(TestAPIMethods, cls).tearDownClass()
        cls.bus_thread.terminate()
        cls.audio_thread.terminate()

    def test_get_tts_no_sentence(self):
        context = {"client": "tester",
                   "ident": "123",
                   "user": "TestRunner"}
        stt_resp = self.bus.wait_for_response(Message("neon.get_tts", {}, context), context["ident"])
        self.assertEqual(stt_resp.context, context)
        self.assertIsInstance(stt_resp.data.get("error"), str)
        self.assertEqual(stt_resp.data["error"], "No text provided.")

    def test_get_tts_invalid_type(self):
        context = {"client": "tester",
                   "ident": "1234",
                   "user": "TestRunner"}
        stt_resp = self.bus.wait_for_response(Message("neon.get_tts", {"text": 123}, context),
                                              context["ident"], timeout=60)
        self.assertEqual(stt_resp.context, context)
        self.assertTrue(stt_resp.data.get("error").startswith("text is not a str:"))

    def test_get_tts_valid_default(self):
        text = "This is a test"
        context = {"client": "tester",
                   "ident": time(),
                   "user": "TestRunner"}
        stt_resp = self.bus.wait_for_response(Message("neon.get_tts", {"text": text}, context),
                                              context["ident"], timeout=60)
        self.assertEqual(stt_resp.context, context)
        responses = stt_resp.data
        self.assertIsInstance(responses, dict)
        self.assertEqual(len(responses), 1)
        resp = list(responses.values())[0]
        self.assertIsInstance(resp, dict)
        self.assertEqual(resp.get("sentence"), text)

    def test_get_tts_valid_speaker(self):
        pass


if __name__ == '__main__':
    unittest.main()
