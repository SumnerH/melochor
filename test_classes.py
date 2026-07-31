import unittest
import numpy as np
from firework import Firework
from unified_audio_player import UnifiedAudioPlayer
from fireworks_app import FireworksApp

class TestClasses(unittest.TestCase):
    def test_import_firework(self):
        # Verify class exists and can be imported
        self.assertIsNotNone(Firework)
        
    def test_import_audio_player(self):
        # Verify class exists and can be instantiated
        player = UnifiedAudioPlayer()
        self.assertIsNotNone(player)
        self.assertFalse(player.sd_playing)
        self.assertIsNone(player.mpv_process)
        
    def test_import_fireworks_app(self):
        # Verify class exists and can be imported
        self.assertIsNotNone(FireworksApp)
        
if __name__ == "__main__":
    unittest.main()
