import unittest
import numpy as np
from meshes import (
    make_rocky_planet,
    make_3d_asteroid,
    make_solid_squid,
    make_solid_seahorse,
    make_solid_manta,
    make_solid_fish,
    make_solid_bird,
    make_solid_butterfly
)

class TestMeshes(unittest.TestCase):
    def test_make_rocky_planet(self):
        center = np.array([0.0, 0.0, 0.0], dtype=np.float32)
        vertices, colors = make_rocky_planet(center, 2.3, 0.5, "JUPITER")
        
        self.assertIsInstance(vertices, list)
        self.assertIsInstance(colors, list)
        self.assertEqual(len(vertices), len(colors))
        self.assertGreater(len(vertices), 0)
        
        for v in vertices:
            self.assertEqual(len(v), 3)
        for c in colors:
            self.assertEqual(len(c), 4)
            self.assertTrue(all(0.0 <= channel <= 1.0 for channel in c))

    def test_make_3d_asteroid(self):
        center = np.array([1.0, -1.0, 2.0], dtype=np.float32)
        vertices, colors = make_3d_asteroid(center, 1.5, 1.2)
        
        self.assertIsInstance(vertices, list)
        self.assertIsInstance(colors, list)
        self.assertEqual(len(vertices), len(colors))
        self.assertGreater(len(vertices), 0)
        
        for v in vertices:
            self.assertEqual(len(v), 3)
        for c in colors:
            self.assertEqual(len(c), 4)
            self.assertTrue(all(0.0 <= channel <= 1.0 for channel in c))

    def test_make_solid_squid(self):
        center = np.array([0.0, 0.0, 0.0], dtype=np.float32)
        direction = np.array([0.0, 1.0, 0.0], dtype=np.float32)
        vertices, colors = make_solid_squid(center, direction, 0.5, 0.1, 0.2, 0.3)
        
        self.assertIsInstance(vertices, list)
        self.assertIsInstance(colors, list)
        self.assertEqual(len(vertices), len(colors))
        self.assertGreater(len(vertices), 0)
        
        for v in vertices:
            self.assertEqual(len(v), 3)
        for c in colors:
            self.assertEqual(len(c), 4)
            self.assertTrue(all(0.0 <= channel <= 1.0 for channel in c))

    def test_make_solid_seahorse(self):
        center = np.array([0.0, 0.0, 0.0], dtype=np.float32)
        vertices, colors = make_solid_seahorse(center, 0.5)
        
        self.assertIsInstance(vertices, list)
        self.assertIsInstance(colors, list)
        self.assertEqual(len(vertices), len(colors))
        self.assertGreater(len(vertices), 0)
        
        for v in vertices:
            self.assertEqual(len(v), 3)
        for c in colors:
            self.assertEqual(len(c), 4)
            self.assertTrue(all(0.0 <= channel <= 1.0 for channel in c))

    def test_make_solid_manta(self):
        center = np.array([0.0, 0.0, 0.0], dtype=np.float32)
        direction = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        vertices, colors = make_solid_manta(center, direction, 0.5)
        
        self.assertIsInstance(vertices, list)
        self.assertIsInstance(colors, list)
        self.assertEqual(len(vertices), len(colors))
        self.assertGreater(len(vertices), 0)
        
        for v in vertices:
            self.assertEqual(len(v), 3)
        for c in colors:
            self.assertEqual(len(c), 4)
            self.assertTrue(all(0.0 <= channel <= 1.0 for channel in c))

    def test_make_solid_fish(self):
        center = np.array([0.0, 0.0, 0.0], dtype=np.float32)
        direction = np.array([0.0, 0.0, 1.0], dtype=np.float32)
        color = [0.1, 0.8, 0.2, 1.0]
        vertices, colors = make_solid_fish(center, direction, 0.5, color)
        
        self.assertIsInstance(vertices, list)
        self.assertIsInstance(colors, list)
        self.assertEqual(len(vertices), len(colors))
        self.assertGreater(len(vertices), 0)
        
        for v in vertices:
            self.assertEqual(len(v), 3)
        for c in colors:
            self.assertEqual(len(c), 4)
            self.assertTrue(all(0.0 <= channel <= 1.0 for channel in c))

    def test_make_solid_bird(self):
        center = np.array([0.0, 0.0, 0.0], dtype=np.float32)
        direction = np.array([1.0, 1.0, 0.0], dtype=np.float32)
        vertices, colors = make_solid_bird(center, direction, 0.5)
        
        self.assertIsInstance(vertices, list)
        self.assertIsInstance(colors, list)
        self.assertEqual(len(vertices), len(colors))
        self.assertGreater(len(vertices), 0)
        
        for v in vertices:
            self.assertEqual(len(v), 3)
        for c in colors:
            self.assertEqual(len(c), 4)
            self.assertTrue(all(0.0 <= channel <= 1.0 for channel in c))

    def test_make_solid_butterfly(self):
        center = np.array([0.0, 0.0, 0.0], dtype=np.float32)
        direction = np.array([0.0, 1.0, 1.0], dtype=np.float32)
        vertices, colors = make_solid_butterfly(center, direction, 0.5)
        
        self.assertIsInstance(vertices, list)
        self.assertIsInstance(colors, list)
        self.assertEqual(len(vertices), len(colors))
        self.assertGreater(len(vertices), 0)
        
        for v in vertices:
            self.assertEqual(len(v), 3)
        for c in colors:
            self.assertEqual(len(c), 4)
            self.assertTrue(all(0.0 <= channel <= 1.0 for channel in c))

if __name__ == "__main__":
    unittest.main()
