import numpy as np


class SpaceInvadersModeMixin:
    """Infinite, music-clocked Space Invaders scene rendered from point-sprite pixels."""

    # Original retro-futurist creatures. Each species has three unique walk
    # frames rather than reproducing any historical Space Invaders sprite.
    _INVADER_SPRITES = (
        (
            (
                "0001100000",
                "0011110000",
                "0110011000",
                "1111111100",
                "1101101100",
                "0111111000",
                "0010010000",
                "0100001000",
                "1000000100",
            ),
            (
                "0001100000",
                "0011110000",
                "0110011000",
                "1111111100",
                "1101101100",
                "0111111000",
                "0101101000",
                "1000000100",
                "0100001000",
            ),
            (
                "0001100000",
                "0011110000",
                "0110011000",
                "1111111100",
                "1101101100",
                "0111111000",
                "0010010000",
                "1001001000",
                "0010000100",
            ),
        ),
        (
            (
                "0010010000",
                "0001100000",
                "0111111000",
                "1101101100",
                "1111111100",
                "0111111000",
                "0010010000",
                "0100001000",
                "1000000100",
            ),
            (
                "0100001000",
                "0010010000",
                "0001100000",
                "0111111000",
                "1101101100",
                "1111111100",
                "0111111000",
                "0010010000",
                "0101101000",
            ),
            (
                "0001100000",
                "0010010000",
                "0111111000",
                "1101101100",
                "1111111100",
                "0111111000",
                "0010010000",
                "1001001000",
                "0010000100",
            ),
        ),
        (
            (
                "0001100000",
                "0011110000",
                "0111111000",
                "1101101100",
                "1111111100",
                "1011110100",
                "0011110000",
                "0100001000",
                "1000000100",
            ),
            (
                "0011110000",
                "0111111000",
                "1101101100",
                "1111111100",
                "1011110100",
                "0011110000",
                "0101101000",
                "1000000100",
                "0100001000",
            ),
            (
                "0001100000",
                "0011110000",
                "0111111000",
                "1101101100",
                "1111111100",
                "1011110100",
                "0011110000",
                "1001001000",
                "0010000100",
            ),
        ),
        (
            (
                "0001000000",
                "0011100000",
                "0110110000",
                "1111111000",
                "1011011000",
                "1111111000",
                "0101100000",
                "1000010000",
                "0100001000",
            ),
            (
                "0000100000",
                "0001110000",
                "0011011000",
                "0111111100",
                "1101101100",
                "1111111000",
                "0101100000",
                "0010000100",
                "1000000010",
            ),
            (
                "0001000000",
                "0011100000",
                "0110110000",
                "1111111000",
                "1011011000",
                "1111111000",
                "0010010000",
                "0100001000",
                "1000000100",
            ),
        ),
        (
            (
                "0001100000",
                "0011110000",
                "0111111000",
                "1101011100",
                "1111111100",
                "0111111000",
                "0011110000",
                "0100101000",
                "1000000100",
            ),
            (
                "0001100000",
                "0011110000",
                "0111111000",
                "1101011100",
                "1111111100",
                "0111111000",
                "0011110000",
                "1001000100",
                "0100001000",
            ),
            (
                "0001100000",
                "0011110000",
                "0111111000",
                "1101011100",
                "1111111100",
                "0111111000",
                "0011110000",
                "0101010000",
                "0010000100",
            ),
        ),
        (
            (
                "0001100000",
                "0011110000",
                "0111111000",
                "1101101100",
                "1111111100",
                "0111111000",
                "1011110100",
                "0100001000",
                "1000000100",
            ),
            (
                "0001100000",
                "0011110000",
                "0111111000",
                "1101101100",
                "1111111100",
                "0111111000",
                "0101101000",
                "1000000100",
                "0100001000",
            ),
            (
                "0001100000",
                "0011110000",
                "0111111000",
                "1101101100",
                "1111111100",
                "0111111000",
                "1001000100",
                "0010001000",
                "0100000100",
            ),
        ),
    )

    _DEFENDER_SPRITE = (
        "00000100000",
        "00001110000",
        "00011111000",
        "00111111100",
        "01111111110",
        "11100100111",
    )

    _MOTHERSHIP_SPRITE = (
        "000111111000",
        "011111111110",
        "111001100111",
        "111111111111",
        "001001001000",
    )

    def init_space_invaders_mode(self):
        self.invader_rows = 6
        self.invader_cols = 11
        self.invader_alive = np.ones(
            (self.invader_rows, self.invader_cols), dtype=np.bool_
        )
        self.invader_types = np.repeat(
            np.arange(self.invader_rows, dtype=np.int8)[:, np.newaxis]
            % len(self._INVADER_SPRITES),
            self.invader_cols,
            axis=1,
        )
        self.invader_next_restock_type = 0
        self.invader_offset_x = 0.0
        self.invader_offset_y = 5.8
        self.invader_direction = 1.0
        self.invader_step_timer = 0.0
        self.invader_step_interval = 0.92
        self.invader_last_step_beat = int(np.floor(self.tempo_phase))
        self.invader_animation_frame = 0
        self.invader_march_flash = 0.0
        self.invader_swap_routine_beats_remaining = 0
        self.invader_swap_phase = 0
        self.invader_swap_vertical = False
        self.invader_swap_animations = []
        self.invader_scene_time = 0.0
        self.invader_glow_timer = 0.0

        self.invader_defender_x = 0.0
        self.invader_defender_target_x = 0.0
        self.invader_shot_timer = 0.0
        self.invader_bullets = []
        self.invader_enemy_bullets = []
        self.invader_bombs = []
        self.invader_explosions = []

        self.invader_shields = np.ones((4, 7, 11), dtype=np.bool_)
        self.invader_shields_visible = True
        self.invader_reseed_timer = 0.0
        self.invader_mothership = None
        self.invader_pending_top_row = None
        self.invader_next_drop_col = 0
        self.invader_dropping_aliens = []
        self.invader_rare = None

        self.invader_moon_pos = np.column_stack(
            (
                np.random.uniform(-10.5, 10.5, 260),
                -4.9 + np.random.uniform(-0.28, 0.36, 260),
                np.random.uniform(-0.05, 0.05, 260),
            )
        ).astype(np.float32)
        self.invader_moon_size = np.random.uniform(1.4, 4.8, 260).astype(np.float32)
        self.invader_vent_x = np.array([-7.3, -2.8, 2.4, 7.1], dtype=np.float32)
        self.invader_vent_smoke = []

        star_count = 180
        self.invader_star_pos = np.column_stack(
            (
                np.random.uniform(-10.0, 10.0, star_count),
                np.random.uniform(-5.0, 9.0, star_count),
                np.random.uniform(-0.1, 0.1, star_count),
            )
        ).astype(np.float32)
        self.invader_star_phase = np.random.uniform(
            0.0, 2.0 * np.pi, star_count
        ).astype(np.float32)
        self.invader_star_size = np.random.uniform(
            0.8, 2.2, star_count
        ).astype(np.float32)

    def on_space_invaders_bpm_changed(self, previous_bpm, bpm, *, reset_tempo=False):
        """Realign the march scheduler when the active track tempo changes."""
        if not hasattr(self, "invader_last_step_beat"):
            return

        self.invader_last_step_beat = int(np.floor(self.tempo_phase))
        self.invader_step_timer = 0.0
        if reset_tempo or bpm != previous_bpm:
            self.invader_march_flash = max(self.invader_march_flash, 0.25)

    def _reset_invader_formation(self):
        """Restore the formation after it reaches the defender."""
        self.invader_alive[:] = True
        self.invader_offset_x = 0.0
        self.invader_offset_y = 5.8
        self.invader_direction *= -1.0
        self.invader_defender_x = 0.0
        self.invader_defender_target_x = 0.0
        self.invader_bullets.clear()
        self.invader_enemy_bullets.clear()
        self.invader_bombs.clear()
        self.invader_shields[:] = True
        self.invader_shields_visible = True
        self.invader_mothership = None
        self.invader_pending_top_row = None
        self.invader_next_drop_col = 0
        self.invader_dropping_aliens.clear()
        self.invader_swap_routine_beats_remaining = 0
        self.invader_swap_vertical = False
        self.invader_swap_animations.clear()

    def _begin_pairwise_invader_swap(self, beat_interval, vertical=False):
        """Swap adjacent row or column cells, moving aliens through empty neighbors."""
        if self.invader_swap_animations:
            return

        start_index = self.invader_swap_phase % 2
        animations = []
        if vertical:
            pair_origins = (
                ((top_row, col), (top_row + 1, col))
                for col in range(self.invader_cols)
                for top_row in range(start_index, self.invader_rows - 1, 2)
            )
        else:
            pair_origins = (
                ((row, left_col), (row, left_col + 1))
                for row in range(self.invader_rows)
                for left_col in range(start_index, self.invader_cols - 1, 2)
            )

        for first_cell, second_cell in pair_origins:
            moving_aliens = []
            for source_cell, target_cell in (
                (first_cell, second_cell),
                (second_cell, first_cell),
            ):
                source_row, source_col = source_cell
                target_row, target_col = target_cell
                if not self.invader_alive[source_row, source_col]:
                    continue
                moving_aliens.append(
                    {
                        "source": self._invader_position(source_row, source_col),
                        "target": self._invader_position(target_row, target_col),
                        "target_row": target_row,
                        "target_col": target_col,
                        "type": int(self.invader_types[source_row, source_col]),
                    }
                )

            if not moving_aliens:
                continue

            first_row, first_col = first_cell
            second_row, second_col = second_cell
            self.invader_alive[first_row, first_col] = False
            self.invader_alive[second_row, second_col] = False
            animations.extend(moving_aliens)

        if animations:
            self.invader_swap_animations = [
                {
                    "aliens": animations,
                    "age": 0.0,
                    "duration": max(0.08, beat_interval * 0.78),
                }
            ]
            self.invader_swap_phase += 1
            self.invader_march_flash = 1.0

    def _update_pairwise_invader_swaps(self, dt):
        """Animate swaps and commit each alien to its new grid cell on arrival."""
        remaining_animations = []
        for animation in self.invader_swap_animations:
            animation["age"] += dt
            if animation["age"] < animation["duration"]:
                remaining_animations.append(animation)
                continue

            for alien in animation["aliens"]:
                row = alien["target_row"]
                col = alien["target_col"]
                self.invader_types[row, col] = alien["type"]
                self.invader_alive[row, col] = True

        self.invader_swap_animations = remaining_animations

    def _send_mothership(self, restock_row):
        """Send a carrier across the playfield in a random direction to seed a row."""
        travel_direction = 1.0 if np.random.random() < 0.5 else -1.0
        self.invader_pending_top_row = restock_row
        self.invader_next_drop_col = (
            0 if travel_direction > 0.0 else self.invader_cols - 1
        )
        self.invader_mothership = {
            "x": -11.5 if travel_direction > 0.0 else 11.5,
            "velocity": travel_direction * 1.875,
            "direction": travel_direction,
            "type": int(restock_row[self.invader_next_drop_col]),
        }

    def _invader_step(self):
        alive_positions = np.argwhere(self.invader_alive)
        if not len(alive_positions):
            self._invader_begin_reseed()
            return

        alive_cols = alive_positions[:, 1]
        left_edge = self.invader_offset_x + (alive_cols.min() - 5) * 1.18
        right_edge = self.invader_offset_x + (alive_cols.max() - 5) * 1.18
        if right_edge >= 8.0 or left_edge <= -8.0:
            self.invader_direction *= -1.0
            self.invader_offset_y -= 0.21

            # A descending formation sheds its bottom row. The mothership refills
            # the new top row with the next species in a repeating five-alien cycle.
            restock_type = self.invader_next_restock_type
            restock_row = np.full(
                self.invader_cols,
                restock_type,
                dtype=np.int8,
            )
            self.invader_alive[1:] = self.invader_alive[:-1]
            self.invader_types[1:] = self.invader_types[:-1]
            self.invader_alive[0] = False
            self.invader_types[0] = restock_row

            if self.invader_mothership is None:
                self.invader_next_restock_type = (
                    self.invader_next_restock_type + 1
                ) % len(self._INVADER_SPRITES)
                self._send_mothership(restock_row)

            if self.invader_offset_y < 3.3:
                self.invader_shields_visible = False

            remaining_aliens = np.argwhere(self.invader_alive)
            if len(remaining_aliens):
                lowest_row = int(remaining_aliens[:, 0].max())
                lowest_y = self.invader_offset_y - lowest_row * 0.92
                if lowest_y <= -3.4:
                    self._reset_invader_formation()
                    return

        self.invader_offset_x += self.invader_direction * 0.21
        self.invader_animation_frame = (self.invader_animation_frame + 1) % 3
        self.invader_march_flash = 1.0
        self.invader_defender_target_x = np.clip(
            self.invader_offset_x * 0.55
            + np.sin(self.get_sim_time() * 0.35) * 4.5,
            -8.0,
            8.0,
        )

        beat_strength = max(self.react_bass, self.react_mid, self.react_treble)
        fire_probability = min(0.48, 0.07 + beat_strength * 0.24)
        if np.random.random() < fire_probability:
            lowest_by_column = []
            for col in range(self.invader_cols):
                rows = np.flatnonzero(self.invader_alive[:, col])
                if len(rows):
                    lowest_by_column.append((rows.max(), col))
            if lowest_by_column:
                row, col = lowest_by_column[np.random.randint(len(lowest_by_column))]
                self._invader_fire_enemy_bullet(row, col)

    def _invader_position(self, row, col):
        return np.array(
            [
                self.invader_offset_x + (col - 5) * 1.18,
                self.invader_offset_y - row * 0.92,
                0.0,
            ],
            dtype=np.float32,
        )

    def _invader_fire_enemy_bullet(self, row, col, speed=2.6):
        self.invader_enemy_bullets.append(
            {
                "pos": self._invader_position(row, col),
                "velocity": np.array([0.0, -speed, 0.0], dtype=np.float32),
                "life": 2.8,
            }
        )

    def _trigger_defender_reset(self):
        """Perform the dramatic, explicitly scripted defender-hit reset."""
        self.invader_supernova_timer = 1.4
        self.invader_explosions.append(
            {
                "pos": np.array(
                    [self.invader_defender_x, -4.20, 0.0], dtype=np.float32
                ),
                "life": 1.0,
                "max_life": 1.0,
                "color": np.array([1.0, 0.20, 0.05, 1.0], dtype=np.float32),
            }
        )
        self._reset_invader_formation()

    def _invader_defender_fire(self):
        self.invader_bullets.append(
            {
                "pos": np.array([self.invader_defender_x, -4.05, 0.0], dtype=np.float32),
                "velocity": np.array([0.0, 1.7, 0.0], dtype=np.float32),
                "life": 10.0,
            }
        )

    def _invader_hit_shield(self, position):
        """Damage and stop a projectile that reaches an occupied shield cell."""
        if not self.invader_shields_visible:
            return False

        x, y = position[:2]
        if y < -2.95 or y > -2.15:
            return False

        shield_index = int(np.round((x + 6.2) / 4.15))
        if shield_index < 0 or shield_index >= len(self.invader_shields):
            return False

        shield_x = -6.2 + shield_index * 4.15
        col = int(np.round((x - shield_x) / 0.10 + 5.0))
        row = int(np.round(6.0 - (y + 2.85) / 0.10))
        if row < 0 or row >= 7 or col < 0 or col >= 11:
            return False
        if row < 2 and (col < 2 or col > 8):
            return False
        if not self.invader_shields[shield_index, row, col]:
            return False

        row_start = max(0, row - 1)
        row_end = min(7, row + 2)
        col_start = max(0, col - 1)
        col_end = min(11, col + 2)
        self.invader_shields[
            shield_index,
            row_start:row_end,
            col_start:col_end,
        ] = False
        return True

    def _invader_destroy(self, row, col):
        if not self.invader_alive[row, col]:
            return

        self.invader_alive[row, col] = False
        position = self._invader_position(row, col)
        self.invader_explosions.append(
            {
                "pos": position,
                "life": 0.45,
                "max_life": 0.45,
                "color": np.array([1.0, 0.55, 0.08, 1.0], dtype=np.float32),
            }
        )

        if not np.any(self.invader_alive):
            self._invader_begin_reseed()

    def _invader_begin_reseed(self):
        """Send the mothership to repopulate an empty formation one alien at a time."""
        if self.invader_mothership is not None or self.invader_pending_top_row is not None:
            return

        self.invader_alive[:] = False
        restock_type = self.invader_next_restock_type
        restock_row = np.full(
            self.invader_cols,
            restock_type,
            dtype=np.int8,
        )
        self.invader_types[0] = restock_row
        self.invader_next_restock_type = (
            self.invader_next_restock_type + 1
        ) % len(self._INVADER_SPRITES)
        self._send_mothership(restock_row)

    def on_measure_downbeat(self, bar_index):
        # Feature 8: Bar-aligned shield pulses every 4 bars
        if bar_index % 4 == 0:
            self.invader_glow_timer = 0.85

    def update_space_invaders(self, dt):
        self.invader_scene_time += dt

        # Visual Vacuum: retro freeze frame
        if getattr(self, 'visual_vacuum_timer', 0.0) > 0.0:
            return

        # Anticipatory implosion: invaders consolidate toward center formation
        if getattr(self, 'drop_anticipation_timer', 0.0) > 0.0:
            is_global = getattr(self, 'drop_anticipation_is_global', False)
            intensity = getattr(self, 'drop_anticipation_intensity', 1.0 if is_global else 0.35)
            self.invader_offset_x += (0.0 - self.invader_offset_x) * min(1.0, dt * (2.0 * intensity))
            self.invader_march_flash = max(self.invader_march_flash, 0.4 * intensity)

        self._update_pairwise_invader_swaps(dt)
        self.invader_march_flash = max(0.0, self.invader_march_flash - dt * 5.5)
        if self.invader_glow_timer > 0.0:
            self.invader_glow_timer = max(0.0, self.invader_glow_timer - dt)

        bpm = max(40.0, min(240.0, self.script_bpm))
        beat_interval = 60.0 / bpm

        # tempo_phase advances once per musical beat. Advance precisely on every
        # beat so the arcade march follows the full track BPM.
        current_beat = int(np.floor(self.tempo_phase))
        if current_beat > self.invader_last_step_beat:
            self.invader_last_step_beat = current_beat
            if self.invader_swap_routine_beats_remaining > 0:
                self._begin_pairwise_invader_swap(
                    beat_interval,
                    vertical=self.invader_swap_vertical,
                )
                self.invader_swap_routine_beats_remaining -= 1
            else:
                self._invader_step()

        self.invader_defender_x += (
            self.invader_defender_target_x - self.invader_defender_x
        ) * min(1.0, dt * 1.5)
        self.invader_shot_timer -= dt
        # The defender may only fire after its previous shot has either struck an
        # alien or travelled fully off-screen. This deliberately slows the battle.
        if (
            self.invader_shot_timer <= 0.0
            and not self.invader_bullets
            and np.any(self.invader_alive)
        ):
            self._invader_defender_fire()
            self.invader_shot_timer = max(0.24, beat_interval * 0.55)

        remaining_bullets = []
        for bullet in self.invader_bullets:
            bullet["pos"] += bullet["velocity"] * dt
            bullet["life"] -= dt
            if bullet["life"] <= 0.0 or self._invader_hit_shield(bullet["pos"]):
                continue

            hit = False
            for row, col in np.argwhere(self.invader_alive):
                if np.linalg.norm(
                    bullet["pos"][:2] - self._invader_position(row, col)[:2]
                ) < 0.54:
                    self._invader_destroy(row, col)
                    hit = True
                    break

            if hit:
                # A successful shot still has a short tactical recovery before
                # the defender can launch its next single projectile.
                self.invader_shot_timer = max(
                    self.invader_shot_timer,
                    beat_interval * 0.9,
                )
            else:
                remaining_bullets.append(bullet)
        self.invader_bullets = remaining_bullets

        remaining_enemy_bullets = []
        for bullet in self.invader_enemy_bullets:
            bullet["pos"] += bullet["velocity"] * dt
            bullet["life"] -= dt
            if self._invader_hit_shield(bullet["pos"]):
                continue

            # Routine-created reset shots are the only enemy projectiles allowed
            # to strike the defender. Ordinary alien fire expires above the ship.
            if bullet.get("reset_shot", False):
                if (
                    bullet["pos"][1] <= -3.85
                    and abs(bullet["pos"][0] - self.invader_defender_x) < 0.55
                ):
                    self._trigger_defender_reset()
                    continue
            elif bullet["pos"][1] <= -3.3:
                continue

            if bullet["life"] > 0.0 and bullet["pos"][1] >= -4.4:
                remaining_enemy_bullets.append(bullet)
        self.invader_enemy_bullets = remaining_enemy_bullets

        remaining_bombs = []
        for bomb in self.invader_bombs:
            bomb["pos"] += bomb["velocity"] * dt
            bomb["velocity"][1] -= 1.9 * dt
            bomb["life"] -= dt
            if bomb["life"] <= 0.0:
                continue
            if self._invader_hit_shield(bomb["pos"]):
                continue

            target_y = bomb.get("target_y", -4.4)
            if bomb["pos"][1] <= target_y:
                self.invader_explosions.append(
                    {
                        "pos": np.array(
                            [bomb["target_x"], target_y, 0.0],
                            dtype=np.float32,
                        ),
                        "life": 1.0,
                        "max_life": 1.0,
                        "color": np.array(
                            [1.0, 0.26, 0.04, 1.0],
                            dtype=np.float32,
                        ),
                    }
                )
                continue

            if bomb["pos"][1] >= -4.4:
                remaining_bombs.append(bomb)
        self.invader_bombs = remaining_bombs

        remaining_explosions = []
        for explosion in self.invader_explosions:
            explosion["life"] -= dt
            if explosion["life"] > 0.0:
                remaining_explosions.append(explosion)
        self.invader_explosions = remaining_explosions

        if self.invader_mothership is not None:
            mothership = self.invader_mothership
            mothership["x"] += mothership["velocity"] * dt

            # The ship releases a single alien as it passes each top-row column.
            # Every passenger falls from the ship and only becomes a grid alien
            # after reaching its assigned top-row position.
            travel_direction = mothership["direction"]
            while (
                self.invader_pending_top_row is not None
                and 0 <= self.invader_next_drop_col < self.invader_cols
                and (
                    (
                        travel_direction > 0.0
                        and mothership["x"]
                        >= self._invader_position(0, self.invader_next_drop_col)[0]
                    )
                    or (
                        travel_direction < 0.0
                        and mothership["x"]
                        <= self._invader_position(0, self.invader_next_drop_col)[0]
                    )
                )
            ):
                col = self.invader_next_drop_col
                self.invader_dropping_aliens.append(
                    {
                        "col": col,
                        "type": int(self.invader_pending_top_row[col]),
                        "pos": np.array(
                            [mothership["x"], 7.55, 0.0], dtype=np.float32
                        ),
                    }
                )
                self.invader_next_drop_col += int(travel_direction)

            ship_has_exited = (
                travel_direction > 0.0 and mothership["x"] >= 11.5
            ) or (
                travel_direction < 0.0 and mothership["x"] <= -11.5
            )
            if ship_has_exited:
                self.invader_mothership = None
                self.invader_pending_top_row = None

        if self.invader_march_flash > 0.0:
            music_energy = np.clip(
                max(self.react_bass, self.react_mid, self.react_treble),
                0.0,
                1.5,
            )
            vent_count = 1 + int(music_energy * 4.0)
            for _ in range(vent_count):
                puff_life = np.random.uniform(3.2, 5.0)
                vent_x = np.random.choice(self.invader_vent_x)
                self.invader_vent_smoke.append(
                    {
                        "pos": np.array(
                            [vent_x + np.random.uniform(-0.16, 0.16), -4.55, 0.0],
                            dtype=np.float32,
                        ),
                        "velocity": np.array(
                            [
                                np.random.uniform(-0.08, 0.08),
                                np.random.uniform(0.12, 0.24) * (1.0 + music_energy * 0.35),
                                0.0,
                            ],
                            dtype=np.float32,
                        ),
                        "life": puff_life,
                        "max_life": puff_life,
                        "size": np.random.uniform(14.0, 22.0) * (1.0 + music_energy * 0.25),
                    }
                )

        remaining_smoke = []
        for puff in self.invader_vent_smoke:
            puff["pos"] += puff["velocity"] * dt
            puff["life"] -= dt
            puff["size"] += dt * 3.0
            if puff["life"] > 0.0:
                remaining_smoke.append(puff)
        self.invader_vent_smoke = remaining_smoke

        remaining_drops = []
        for drop in self.invader_dropping_aliens:
            target = self._invader_position(0, drop["col"])
            drop["pos"][0] += (target[0] - drop["pos"][0]) * min(1.0, dt * 5.0)
            drop["pos"][1] -= 1.55 * dt

            if drop["pos"][1] <= target[1]:
                self.invader_types[0, drop["col"]] = drop["type"]
                self.invader_alive[0, drop["col"]] = True
            else:
                remaining_drops.append(drop)
        self.invader_dropping_aliens = remaining_drops

        if self.invader_rare is not None:
            rarity = self.invader_rare
            rarity["life"] -= dt
            rarity["pos"] += rarity["velocity"] * dt
            if rarity["type"] == "UFO":
                rarity["pos"][1] += np.sin(self.get_sim_time() * 3.5) * dt * 0.3
            if rarity["life"] <= 0.0 or abs(rarity["pos"][0]) > 12.0:
                self.invader_rare = None

    @staticmethod
    def _append_sprite(
        positions,
        colors,
        sizes,
        sprite,
        center,
        pixel_size,
        color,
        point_size,
        frame_offset=0.0,
        pixel_density=1,
    ):
        height = len(sprite)
        width = len(sprite[0])
        subpixel_size = pixel_size / pixel_density
        subpoint_size = point_size / pixel_density

        for y, line in enumerate(sprite):
            for x, pixel in enumerate(line):
                if pixel != "1":
                    continue
                for sub_y in range(pixel_density):
                    for sub_x in range(pixel_density):
                        positions.append(
                            [
                                center[0]
                                + (x - (width - 1) * 0.5) * pixel_size
                                + (sub_x - (pixel_density - 1) * 0.5) * subpixel_size
                                + frame_offset,
                                center[1]
                                + ((height - 1) * 0.5 - y) * pixel_size
                                + ((pixel_density - 1) * 0.5 - sub_y) * subpixel_size,
                                center[2],
                            ]
                        )
                        colors.append(color)
                        sizes.append(subpoint_size)

    @staticmethod
    def _append_digital_digit(positions, colors, sizes, digit, center, color):
        """Append a crisp, high-resolution seven-segment arcade digit."""
        # Segment order is top, upper-right, lower-right, bottom, lower-left,
        # upper-left, middle. These are standard decimal seven-segment glyphs.
        segments = (
            "1111110", "0110000", "1101101", "1111001", "0110011",
            "1011011", "1011111", "1110000", "1111111", "1111011",
        )
        segment_pixels = (
            ((-2, 3), (-1, 3), (0, 3), (1, 3), (2, 3)),
            ((2, 2), (2, 1), (2, 0)),
            ((2, -1), (2, -2), (2, -3)),
            ((-2, -3), (-1, -3), (0, -3), (1, -3), (2, -3)),
            ((-2, -1), (-2, -2), (-2, -3)),
            ((-2, 2), (-2, 1), (-2, 0)),
            ((-2, 0), (-1, 0), (0, 0), (1, 0), (2, 0)),
        )
        for enabled, segment in zip(segments[digit], segment_pixels):
            if enabled != "1":
                continue
            for x, y in segment:
                positions.append(
                    [center[0] + x * 0.065, center[1] + y * 0.065, 0.0]
                )
                colors.append(color)
                sizes.append(3.6)

    def render_space_invaders(self):
        positions = []
        colors = []
        sizes = []
        reactivity = self.opt_particle_reactivity / 10.0
        beat = np.clip(
            max(self.react_bass, self.react_mid, self.react_treble), 0.0, 1.5
        )
        star_pulse = 1.0 + reactivity * beat * 1.5

        local_bands = self.sample_spatial_audio_space_invaders(self.invader_star_pos)
        for index, star_pos in enumerate(self.invader_star_pos):
            regional_energy = float(np.max(local_bands[index]))
            twinkle = 0.32 + 0.68 * (
                0.5
                + 0.5
                * np.sin(
                    self.get_sim_time() * (0.7 + index % 5 * 0.15)
                    + self.invader_star_phase[index]
                )
            )
            alpha = np.clip(
                twinkle * (0.20 + regional_energy * reactivity * 0.95),
                0.04,
                1.0,
            )
            positions.append(star_pos)
            colors.append([0.55, 0.78, 1.0, alpha])
            sizes.append(self.invader_star_size[index] * star_pulse)

        march_strobe = 0.42 + 0.58 * self.invader_march_flash
        for moon_pos, moon_size in zip(self.invader_moon_pos, self.invader_moon_size):
            positions.append(moon_pos)
            colors.append([0.20, 0.24, 0.34, 0.30])
            sizes.append(-moon_size)

        for vent_x in self.invader_vent_x:
            positions.append([vent_x, -4.52, 0.0])
            colors.append([0.30, 0.34, 0.40, 0.35])
            sizes.append(-7.5)

        smoke_pulse = np.clip(
            0.65 + max(self.react_bass, self.react_mid, self.react_treble) * 0.45,
            0.0,
            1.0,
        )
        for puff in self.invader_vent_smoke:
            life_fraction = puff["life"] / puff["max_life"]
            positions.append(puff["pos"])
            colors.append([0.38, 0.43, 0.52, 0.28 * life_fraction * smoke_pulse])
            sizes.append(-puff["size"] * (1.0 + (1.0 - life_fraction) * 0.45))

        glow_beat_pulse = 0.5 + 0.5 * np.sin(self.tempo_phase * 2.0 * np.pi)
        pulse = np.clip(
            self.invader_glow_timer * (0.55 + 0.45 * glow_beat_pulse),
            0.0,
            1.0,
        )
        alien_colors = (
            [0.20, 1.0, 0.42, 1.0],
            [0.95, 0.32, 0.86, 1.0],
            [1.0, 0.56, 0.16, 1.0],
            [0.28, 0.72, 1.0, 1.0],
            [0.62, 0.45, 1.0, 1.0],
            [1.0, 0.24, 0.18, 1.0],
        )
        alive_cells = np.argwhere(self.invader_alive)
        alive_centers = np.asarray(
            [self._invader_position(row, col) for row, col in alive_cells],
            dtype=np.float32,
        ).reshape(-1, 3)
        alien_local_bands = self.sample_spatial_audio_space_invaders(alive_centers)

        for alien_index, (row, col) in enumerate(alive_cells):
            center = alive_centers[alien_index]
            alien_type = self.invader_types[row, col]

            # Mirror Synaesthesia's vertical spectral layout: bass activates
            # the low formation, mids the center, and treble the upper formation.
            height = np.clip((center[1] - 0.5) / 7.5, 0.0, 1.0)
            bass_weight = (1.0 - height) ** 2
            treble_weight = height ** 2
            mid_weight = 1.0 - bass_weight - treble_weight
            local_bands = alien_local_bands[alien_index]
            regional_energy = (
                bass_weight * local_bands[0]
                + mid_weight * local_bands[1]
                + treble_weight * local_bands[2]
            )
            global_energy = (
                bass_weight * self.react_bass
                + mid_weight * self.react_mid
                + treble_weight * self.react_treble
            )
            stereo_weight = 1.0 + 0.25 * (
                np.clip(center[0] / 10.0, -1.0, 1.0)
                * self.current_stereo_panning
            )
            # Each row is weighted toward the Synaesthesia band occupying its
            # vertical region: low rows answer bass, middle rows answer mids, and
            # upper rows answer treble. The resulting travelling phase produces a
            # clearly visible musical wave across the formation on every hit.
            row_energy = (
                bass_weight * self.react_bass
                + mid_weight * self.react_mid
                + treble_weight * self.react_treble
            )
            row_energy += regional_energy * 0.75
            wave_phase = (
                self.get_sim_time() * (5.0 + row_energy * 7.0)
                - col * 0.72
                + row * 1.15
            )
            wave_amplitude = 0.0175 + min(1.0, row_energy) * 0.12
            center = center.copy()
            center[1] += np.sin(wave_phase) * wave_amplitude
            center[0] += np.cos(wave_phase) * wave_amplitude * 0.24

            feature_pulse = np.clip(
                0.18
                + (regional_energy + global_energy * 0.18)
                * (0.35 + reactivity * 1.65)
                * stereo_weight
                * 2.0,
                0.0,
                1.0,
            )
            color = list(alien_colors[alien_type])
            if pulse > 0.0:
                color[:3] = [
                    channel + (1.0 - channel) * pulse
                    for channel in color[:3]
                ]
            sprite = self._INVADER_SPRITES[alien_type][self.invader_animation_frame]
            self._append_sprite(
                positions,
                colors,
                sizes,
                sprite,
                center,
                0.078,
                color,
                5.0 + pulse * 12.0,
                pixel_density=2,
            )

            # Fine animated facial details make the higher-resolution creatures
            # readable even while their chunky silhouettes march in formation.
            eye_color = [0.82, 1.0, 1.0, feature_pulse]
            mouth_color = [1.0, 0.20 + 0.65 * feature_pulse, 0.04, feature_pulse]
            antenna_color = [1.0, 0.82, 0.24, feature_pulse]
            feature_size = 1.8 + feature_pulse * (2.0 + reactivity * 0.8)

            positions.extend(
                (
                    [center[0] - 0.14, center[1] + 0.10, 0.01],
                    [center[0] + 0.14, center[1] + 0.10, 0.01],
                    [center[0] - 0.24, center[1] + 0.42, 0.01],
                    [center[0] + 0.24, center[1] + 0.42, 0.01],
                    [center[0], center[1] - 0.10, 0.01],
                )
            )
            colors.extend(
                (
                    eye_color,
                    eye_color,
                    antenna_color,
                    antenna_color,
                    mouth_color,
                )
            )
            sizes.extend(
                (
                    feature_size,
                    feature_size,
                    feature_size * 0.8,
                    feature_size * 0.8,
                    feature_size * 1.25,
                )
            )

        for animation in self.invader_swap_animations:
            progress = min(1.0, animation["age"] / animation["duration"])
            eased_progress = progress * progress * (3.0 - 2.0 * progress)
            for alien in animation["aliens"]:
                center = (
                    alien["source"]
                    + (alien["target"] - alien["source"]) * eased_progress
                ).copy()
                center[1] += np.sin(progress * np.pi) * 0.22
                alien_type = alien["type"]
                self._append_sprite(
                    positions,
                    colors,
                    sizes,
                    self._INVADER_SPRITES[alien_type][self.invader_animation_frame],
                    center,
                    0.078,
                    alien_colors[alien_type],
                    4.8,
                    pixel_density=2,
                )

        # Let the defender's individual pixels carry a travelling beat wave rather
        # than flashing together. The pixel geometry itself remains perfectly steady.
        defender_center = np.array(
            [self.invader_defender_x, -4.20, 0.0], dtype=np.float32
        )
        defender_height = len(self._DEFENDER_SPRITE)
        defender_width = len(self._DEFENDER_SPRITE[0])
        for sprite_y, line in enumerate(self._DEFENDER_SPRITE):
            for sprite_x, pixel in enumerate(line):
                if pixel != "1":
                    continue
                wave = 0.5 + 0.5 * np.sin(
                    self.tempo_phase * 2.0 * np.pi
                    - sprite_x * 0.85
                    + sprite_y * 0.45
                )
                pixel_position = sprite_x / max(1, defender_width - 1)
                frequency_energy = np.clip(
                    (1.0 - pixel_position) * self.react_bass
                    + (1.0 - abs(pixel_position - 0.5) * 2.0) * self.react_mid
                    + pixel_position * self.react_treble,
                    0.0,
                    1.0,
                )
                # At rest, every pixel stays fully bright. Each frequency band
                # sends a pronounced, independently phased dark wave across the
                # defender, so bass/mid/treble passages visibly travel differently.
                ripple_strength = 0.78 * frequency_energy
                alpha = 1.0 - ripple_strength * wave
                positions.append(
                    [
                        defender_center[0] + (sprite_x - (defender_width - 1) * 0.5) * 0.092,
                        defender_center[1] + ((defender_height - 1) * 0.5 - sprite_y) * 0.092,
                        0.0,
                    ]
                )
                colors.append([0.34, 0.95, 1.0, alpha])
                sizes.append(4.2)

        if self.invader_shields_visible:
            for shield_index in range(4):
                shield_x = -6.2 + shield_index * 4.15
                for row in range(7):
                    for col in range(11):
                        if not self.invader_shields[shield_index, row, col]:
                            continue
                        if row < 2 and (col < 2 or col > 8):
                            continue
                        wave = 0.5 + 0.5 * np.sin(
                            self.tempo_phase * 2.0 * np.pi
                            - col * 0.58
                            + row * 0.38
                            + shield_index * 0.72
                        )
                        pixel_position = col / 10.0
                        frequency_energy = np.clip(
                            (1.0 - pixel_position) * self.react_bass
                            + (1.0 - abs(pixel_position - 0.5) * 2.0) * self.react_mid
                            + pixel_position * self.react_treble,
                            0.0,
                            1.0,
                        )
                        positions.append(
                            [shield_x + (col - 5) * 0.10, -2.85 + (6 - row) * 0.10, 0.0]
                        )
                        # Shields are solid at rest. Active frequency bands drive
                        # a strong, travelling per-pixel dark wave rather than a
                        # subtle uniform transparency change.
                        ripple_strength = 0.82 * frequency_energy
                        colors.append(
                            [
                                0.18,
                                0.92,
                                0.54,
                                1.0 - ripple_strength * wave,
                            ]
                        )
                        sizes.append(3.0)

        # High-resolution elapsed-time display in the lower-right corner.
        elapsed_seconds = int(self.invader_scene_time)
        minutes, seconds = divmod(elapsed_seconds, 60)
        timer_text = f"{minutes:02d}{seconds:02d}"
        timer_x_positions = (7.45, 8.05, 8.85, 9.45)
        for digit_char, timer_x in zip(timer_text, timer_x_positions):
            self._append_digital_digit(
                positions,
                colors,
                sizes,
                int(digit_char),
                np.array([timer_x, -4.26, 0.0], dtype=np.float32),
                [0.35, 1.0, 0.66, 1.0],
            )
        for colon_y in (-0.13, 0.13):
            positions.append([8.45, -4.26 + colon_y, 0.0])
            colors.append([0.35, 1.0, 0.66, 1.0])
            sizes.append(3.6)

        # Three reserve defender lives in the lower-left corner use the same
        # travelling-pixel wave as the active ship.
        for life_index in range(3):
            life_center_x = -8.85 + life_index * 0.70
            for sprite_y, line in enumerate(self._DEFENDER_SPRITE):
                for sprite_x, pixel in enumerate(line):
                    if pixel != "1":
                        continue
                    wave = 0.5 + 0.5 * np.sin(
                        self.tempo_phase * 2.0 * np.pi
                        - sprite_x * 0.85
                        + sprite_y * 0.45
                        + life_index * 1.1
                    )
                    pixel_position = sprite_x / max(1, defender_width - 1)
                    frequency_energy = np.clip(
                        (1.0 - pixel_position) * self.react_bass
                        + (1.0 - abs(pixel_position - 0.5) * 2.0) * self.react_mid
                        + pixel_position * self.react_treble,
                        0.0,
                        1.0,
                    )
                    positions.append(
                        [
                            life_center_x + (sprite_x - (defender_width - 1) * 0.5) * 0.052,
                            -4.30 + ((defender_height - 1) * 0.5 - sprite_y) * 0.052,
                            0.0,
                        ]
                    )
                    # Reserve ships mirror the prominent band-distributed ripple
                    # of the active defender while remaining fully lit in silence.
                    ripple_strength = 0.78 * frequency_energy
                    colors.append(
                        [
                            0.34,
                            0.95,
                            1.0,
                            1.0 - ripple_strength * wave,
                        ]
                    )
                    sizes.append(2.6)

        for bullet in self.invader_bullets:
            positions.append(bullet["pos"])
            colors.append([0.95, 1.0, 1.0, 1.0])
            sizes.append(6.0)
        for bullet in self.invader_enemy_bullets:
            positions.append(bullet["pos"])
            colors.append([1.0, 0.25, 0.12, 1.0])
            sizes.append(5.5)
        for bomb in self.invader_bombs:
            positions.append(bomb["pos"])
            colors.append([1.0, 0.58, 0.06, 1.0])
            sizes.append(12.0)
        for explosion in self.invader_explosions:
            life = explosion["life"] / explosion["max_life"]
            for angle in np.linspace(0.0, 2.0 * np.pi, 12, endpoint=False):
                positions.append(
                    explosion["pos"]
                    + np.array(
                        [np.cos(angle), np.sin(angle), 0.0],
                        dtype=np.float32,
                    )
                    * (1.0 - life)
                    * 0.7
                )
                colors.append([1.0, 0.50 + life * 0.4, 0.08, life])
                sizes.append(7.0)

        for drop in self.invader_dropping_aliens:
            drop_color = list(alien_colors[drop["type"]])
            self._append_sprite(
                positions,
                colors,
                sizes,
                self._INVADER_SPRITES[drop["type"]][self.invader_animation_frame],
                drop["pos"],
                0.078,
                drop_color,
                4.0,
                pixel_density=2,
            )

        if self.invader_mothership is not None:
            self._append_sprite(
                positions,
                colors,
                sizes,
                self._MOTHERSHIP_SPRITE,
                np.array([self.invader_mothership["x"], 8.0, 0.0], dtype=np.float32),
                0.11,
                [1.0, 0.22, 0.42, 1.0],
                5.5,
            )

        if self.invader_rare is not None:
            rarity = self.invader_rare
            if rarity["type"] == "UFO":
                self._append_sprite(
                    positions,
                    colors,
                    sizes,
                    self._MOTHERSHIP_SPRITE,
                    rarity["pos"],
                    0.08,
                    [0.28, 1.0, 0.85, 0.88],
                    4.5,
                )
            else:
                positions.append(rarity["pos"])
                colors.append([1.0, 0.92, 0.58, 1.0])
                sizes.append(13.0)
                for trail_index in range(1, 9):
                    positions.append(
                        rarity["pos"]
                        - rarity["velocity"] * trail_index * 0.045
                    )
                    colors.append([0.45, 0.75, 1.0, 1.0 - trail_index / 9.0])
                    sizes.append(8.0 - trail_index * 0.55)

        return (
            np.asarray(positions, dtype=np.float32).reshape(-1, 3),
            np.asarray(colors, dtype=np.float32).reshape(-1, 4),
            np.asarray(sizes, dtype=np.float32),
            np.zeros((0, 3), dtype=np.float32),
            np.zeros((0, 4), dtype=np.float32),
        )

    def sample_spatial_audio_space_invaders(self, positions):
        """Sample the shared 8x5 music field using the Space Invaders playfield."""
        zones = self.spatial_audio_zones
        rows, cols = zones.shape[:2]
        x = np.clip((positions[:, 0] + 10.0) / 20.0, 0.0, 1.0) * (cols - 1)
        y = np.clip((positions[:, 1] + 5.0) / 14.0, 0.0, 1.0) * (rows - 1)
        x0 = np.floor(x).astype(np.intp)
        y0 = np.floor(y).astype(np.intp)
        x1 = np.minimum(x0 + 1, cols - 1)
        y1 = np.minimum(y0 + 1, rows - 1)
        fx = (x - x0)[:, np.newaxis]
        fy = (y - y0)[:, np.newaxis]
        bottom = zones[y0, x0] * (1.0 - fx) + zones[y0, x1] * fx
        top = zones[y1, x0] * (1.0 - fx) + zones[y1, x1] * fx
        return bottom * (1.0 - fy) + top * fy

    def spawn_rarity_space_invaders(self, rarity_type):
        if rarity_type == "UFO":
            direction = 1.0 if np.random.random() < 0.5 else -1.0
            self.invader_rare = {
                "type": "UFO",
                "pos": np.array([-11.0 * direction, 6.8, 0.0], dtype=np.float32),
                "velocity": np.array([direction * 1.55, 0.0, 0.0], dtype=np.float32),
                "life": 7.5,
            }
        elif rarity_type == "SHOOTING_STAR":
            direction = 1.0 if np.random.random() < 0.5 else -1.0
            self.invader_rare = {
                "type": "SHOOTING_STAR",
                "pos": np.array([-10.5 * direction, 8.8, 0.0], dtype=np.float32),
                "velocity": np.array([direction * 3.5, -1.55, 0.0], dtype=np.float32),
                "life": 3.2,
            }

    def trigger_climax_space_invaders(self, routine_name):
        alive = np.argwhere(self.invader_alive)
        if routine_name == "Alien Barrage":
            for row, col in alive:
                self._invader_fire_enemy_bullet(row, col, speed=3.2)
        elif routine_name in ("Pairwise Swap", "Vertical Pairwise Swap"):
            self.invader_swap_routine_beats_remaining = 8
            self.invader_swap_phase = 0
            self.invader_swap_vertical = routine_name == "Vertical Pairwise Swap"
            self.invader_march_flash = 1.0
        elif routine_name == "Side Bomb":
            target_x = -8.15 if np.random.random() < 0.5 else 8.45
            self.invader_bombs.append(
                {
                    "pos": np.array([target_x, 7.4, 0.0], dtype=np.float32),
                    "velocity": np.array([0.0, -3.2, 0.0], dtype=np.float32),
                    "target_x": target_x,
                    "target_y": -4.18,
                    "life": 4.0,
                }
            )
        elif routine_name == "Alien Glow":
            self.invader_glow_timer = 1.35
        elif routine_name == "Defender Reset":
            alive = np.argwhere(self.invader_alive)
            if len(alive):
                row, col = alive[np.argmax(alive[:, 0])]
                origin = self._invader_position(row, col)
                target = np.array(
                    [self.invader_defender_x, -4.20, 0.0], dtype=np.float32
                )
                direction = target - origin
                direction /= max(np.linalg.norm(direction), 1e-6)
                self.invader_enemy_bullets.append(
                    {
                        "pos": origin,
                        "velocity": direction * 3.2,
                        "life": 5.0,
                        "reset_shot": True,
                    }
                )
