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

    def test_shaders_package(self):
        # Verify shaders package can be imported and exports expected constants and helper functions
        import shaders
        self.assertIsNotNone(shaders.SKY_VERTEX_SHADER)
        self.assertIsNotNone(shaders.SKY_FRAGMENT_SHADER)
        self.assertIsNotNone(shaders.LINE_VERTEX_SHADER)
        self.assertIsNotNone(shaders.LINE_FRAGMENT_SHADER)
        self.assertIsNotNone(shaders.PARTICLE_VERTEX_SHADER)
        self.assertIsNotNone(shaders.PARTICLE_FRAGMENT_SHADER)
        self.assertIsNotNone(shaders.compile_shader)
        self.assertIsNotNone(shaders.create_program)
        
if __name__ == "__main__":
    unittest.main()
