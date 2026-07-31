
RARITY_INTERVAL = 60.0

# Vibrant emission spectra colors corresponding to real-world metal salts
COLORS = {
    "strontium_red": (1.0, 0.15, 0.1, 1.0),
    "barium_green": (0.1, 1.0, 0.25, 1.0),
    "copper_blue": (0.15, 0.45, 1.0, 1.0),
    "sodium_gold": (1.0, 0.65, 0.05, 1.0),
    "calcium_orange": (1.0, 0.35, 0.05, 1.0),
    "potassium_purple": (0.85, 0.1, 1.0, 1.0),
    "magnesium_white": (0.95, 0.95, 1.0, 1.0)
}

COLOR_LIST = list(COLORS.values())

# Curated Color Palettes for the Optional Color Modes
NEON_PALETTE = [
    (1.0, 0.0, 0.5, 1.0),   # Neon Pink
    (0.0, 1.0, 1.0, 1.0),   # Neon Cyan
    (0.5, 0.0, 1.0, 1.0),   # Neon Purple
    (1.0, 1.0, 0.0, 1.0),   # Neon Yellow
    (0.0, 1.0, 0.0, 1.0)    # Neon Green
]

TRANQUIL_PALETTE = [
    (0.0, 0.3, 0.8, 1.0),   # Deep Blue
    (0.0, 0.6, 0.5, 1.0),   # Calming Teal
    (0.1, 0.7, 0.4, 1.0),   # Soft Emerald Green
    (0.5, 0.2, 0.7, 1.0),   # Lavender/Lilac
    (0.3, 0.4, 0.9, 1.0)    # Periwinkle Blue
]

METAL_PALETTE = [
    (0.9, 0.9, 0.95, 1.0),  # Bright Silver
    (1.0, 0.8, 0.2, 1.0),   # Radiant Gold
    (0.8, 0.5, 0.2, 1.0),   # Warm Bronze
    (0.7, 0.7, 0.75, 1.0),  # Slate Platinum
    (0.85, 0.65, 0.35, 1.0) # Burnished Brass
]

SUPPORTED_ROUTINES = {
    "FIREWORKS": [
        "American Flag", "Liberty Bell", "Statue of Liberty",
        "Flower Bouquet", "The Dragon", "Supernova", "Shooting Star"
    ],
    "TUNNEL Wormhole": [
        "Lightning Flash", "Supernova", "Shooting Star"
    ],
    "UNDERWATER Lava": [
        "Supernova", "Shooting Star"
    ],
    "MANDALA Sacred": [
        "Peace Symbol", "Halo Effect", "Supernova", "Shooting Star"
    ],
    "SYNAESTHESIA Classic": [
        "Star Burst"
    ],
    "FIRE Plasma": [
        "Flame Flare", "Flame Wave", "Treble Spark Shower", "Fire Eruption", "Lightning Strike", "Supernova", "Shooting Star"
    ]
}

