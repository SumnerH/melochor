# Fire Plasma flame plume rendering: the uFlameAlgorithm switch. Algorithms 0 (Current) and 6
# (Multi) are fully implemented; 1-5 remain stubs (matching their current CPU-side status),
# kept isolated here so flame-algorithm work never requires touching the environment/backdrop
# code in sky_fire_common.py.
SKY_FIRE_FLAMES_SOURCE = """
vec3 renderFireFlames(vec2 vPos, float ground_height, float bass, float mid, float treble, vec3 base_color) {
    // B. CORE FLAME RENDERING (6 algorithms)
    if (uFlameAlgorithm < 0.5) {
        // --- ALGORITHM 0: Current (original 3-plume noise-based campfire) ---
        float container_mask = smoothstep(0.31, 0.22, abs(vPos.x));
        
        // Procedural Behind-the-fire Smoke Layer (rises from base, drifts behind bright flames)
        if (vPos.y >= ground_height) {
            float s_height = vPos.y - ground_height;
            float smoke_width = 0.20 + 0.38 * s_height;
            float smoke_sway = sin(uTime * 1.3) * 0.16 + uStereoPanning * 0.40 + uWindGust * 0.65;
            float smoke_x = vPos.x - smoke_sway * s_height * 0.60;
            vec2 smoke_uv = vec2(smoke_x * 2.5, s_height * 0.40 - uTime * 0.55);
            float smoke_noise = fbm(smoke_uv * 3.5 + vec2(0.0, -uTime * 0.25));
            smoke_noise += fbm(smoke_uv * 7.5) * 0.35;
            float smoke_shape = exp(- (smoke_x * smoke_x) / (2.0 * smoke_width * smoke_width));
            float smoke_density = smoke_shape * (0.08 + 0.22 * smoke_noise) * smoothstep(1.0, 0.15, vPos.y);
            vec3 smoke_color = vec3(0.24, 0.25, 0.28) * (0.8 + 0.3 * fbm(vPos * 4.0));
            base_color = mix(base_color, smoke_color, smoke_density * 0.45);
        }
        
        float flame_height = 0.30 + 0.35 * bass + 0.12 * mid;
        float flame_width = 0.16 + 0.08 * bass;
        flame_height = max(0.1, flame_height);
        float y_scaled = (vPos.y - ground_height) / flame_height;
        
        // Glowing coals bed
        float dist_to_coals = length(vec2(vPos.x * 3.0, (vPos.y - ground_height) * 5.0));
        float coals_glow = exp(-dist_to_coals * 3.5) * (0.8 + 0.5 * bass) * container_mask;
        vec3 coals_color = vec3(0.98, 0.18, 0.01) * coals_glow;
        base_color += coals_color * 1.5;
        
        float total_temp = 0.0;
        float total_opacity = 0.0;
        float total_bg_glow = 0.0;
        float total_blue_mask = 0.0;
        
        float fx[3];
        fx[0] = -0.11; fx[1] = 0.0; fx[2] = 0.11;
        
        float x_factor = 2.5;
        float p_val[3];
        p_val[0] = (bass * x_factor + mid + treble) / (x_factor + 2.0);
        p_val[1] = (bass + mid * x_factor + treble) / (x_factor + 2.0);
        p_val[2] = (bass + mid + treble * x_factor) / (x_factor + 2.0);
        
        float f_height[3];
        f_height[0] = 0.20 + 0.30 * p_val[0];
        f_height[1] = 0.23 + 0.33 * p_val[1];
        f_height[2] = 0.20 + 0.30 * p_val[2];
        
        float f_width[3];
        f_width[0] = 0.09 + 0.04 * p_val[0];
        f_width[1] = 0.10 + 0.04 * p_val[1];
        f_width[2] = 0.09 + 0.04 * p_val[2];
        
        float f_sway[3];
        f_sway[0] = sin(uTime * 1.6 + 0.0) * 0.08 + uStereoPanning * 0.35 + uWindGust * 0.50;
        f_sway[1] = sin(uTime * 1.9 + 2.1) * 0.11 + uStereoPanning * 0.42 + uWindGust * 0.65;
        f_sway[2] = sin(uTime * 2.2 + 4.3) * 0.08 + uStereoPanning * 0.35 + uWindGust * 0.50;
        
        for (int p = 0; p < 3; p++) {
            float p_height = max(0.08, f_height[p]);
            float y_scaled = (vPos.y - ground_height) / p_height;
            
            if (vPos.y >= ground_height && y_scaled < 1.35) {
                float height_fade = smoothstep(1.35, 0.75, y_scaled);
                float taper = 1.05 - y_scaled * 0.85;
                float profile_width = f_width[p] * max(0.1, taper);
                
                float px = vPos.x - fx[p];
                px -= f_sway[p] * y_scaled * 0.45;
                
                float shape_mask = exp(- (px * px) / (2.0 * profile_width * profile_width)) * container_mask;
                
                vec2 noise_uv = vec2(px * 2.5, y_scaled);
                vec2 disp1 = vec2(uTime * 0.30 + float(p) * 1.5, -uTime * 2.2 - bass * 1.0);
                vec2 disp2 = vec2(-uTime * 0.20 - float(p) * 1.5, -uTime * 3.4 - treble * 0.4);
                
                vec2 warp1 = vec2(
                    fbm(noise_uv * 1.8 + disp1),
                    fbm(noise_uv * 2.2 + disp2)
                );
                vec2 warp2 = vec2(
                    fbm(noise_uv * 3.8 + warp1 * 1.4 - disp1 * 0.4),
                    fbm(noise_uv * 4.6 - warp1 * 1.1 + disp2 * 0.4)
                );
                vec2 final_uv = noise_uv + warp2 * 0.45;
                float licks = fbm(final_uv * 4.8 - vec2(0.0, uTime * (2.4 + float(p) * 0.4)));
                
                float flame_field = (exp(-y_scaled * 2.4) * 0.38 + licks * 0.82) * shape_mask - y_scaled * 0.54;
                
                float solid_base = smoothstep(0.12, 0.0, y_scaled);
                flame_field = mix(flame_field, 0.80, solid_base * shape_mask);
                
                float p_temp = smoothstep(0.08, 0.38, flame_field) * height_fade;
                p_temp = clamp(p_temp, 0.0, 1.0);
                
                if (p_temp > total_temp) {
                    total_temp = p_temp;
                }
                
                // Accumulate local blue mask for gas base
                float p_blue = smoothstep(0.06, 0.0, y_scaled) * smoothstep(f_width[p] * 0.35, 0.0, abs(px));
                if (p_blue > total_blue_mask) {
                    total_blue_mask = p_blue;
                }
                
                // Add background glow for each plume
                float glow_width = f_width[p] * 1.4;
                float glow_shape = exp(- (px * px) / (2.0 * glow_width * glow_width)) * container_mask;
                float glow_decay = exp(-y_scaled * 2.0);
                total_bg_glow += glow_shape * glow_decay * (0.04 + 0.12 * bass);
            }
        }
        
        vec3 flame_color = vec3(0.0);
        float opacity = 0.0;
        
        if (total_temp > 0.005) {
            // More realistic (yellower) base colors
            vec3 col_blue = vec3(0.55, 0.15, 0.0) * (0.8 + bass * 0.2);  // warm dark orange base
            vec3 col_red, col_orange, col_yellow, col_white;
            
            if (uColorMode == 1) { // NEON
                col_red = vec3(1.0, 0.0, 0.5) * (0.8 + bass * 0.35);
                col_orange = vec3(0.5, 0.0, 1.0) * (0.8 + treble * 0.35);
                col_yellow = vec3(0.0, 1.0, 1.0) * (0.8 + treble * 0.35);
                col_white = vec3(0.0, 1.0, 0.0) * (0.8 + mid * 0.35);
            } else if (uColorMode == 2) { // TRANQUIL
                col_red = vec3(0.0, 0.3, 0.8) * (0.8 + bass * 0.3);
                col_orange = vec3(0.0, 0.6, 0.5) * (0.8 + treble * 0.3);
                col_yellow = vec3(0.5, 0.2, 0.7) * (0.8 + treble * 0.3);
                col_white = vec3(0.1, 0.7, 0.4) * (0.8 + mid * 0.3);
            } else if (uColorMode == 3) { // METAL
                col_red = vec3(0.8, 0.5, 0.2) * (0.8 + bass * 0.35);
                col_orange = vec3(1.0, 0.8, 0.2) * (0.8 + treble * 0.35);
                col_yellow = vec3(0.9, 0.9, 0.95) * (0.8 + treble * 0.35);
                col_white = vec3(1.0, 1.0, 1.0) * (0.8 + mid * 0.35);
            } else { // REALISTIC (more yellow)
                col_red = vec3(0.85 + 0.15 * bass, 0.015 * (1.0 - bass), 0.005) * (1.25 + bass * 0.45);
                col_orange = vec3(0.98, 0.40 + 0.20 * treble, 0.01); // more yellow
                col_yellow = vec3(1.0, 0.90 + 0.10 * treble, 0.10 + 0.25 * treble); // more yellow
                col_white = vec3(1.0, 1.0, 0.72 + 0.28 * mid);
            }
            
            float red_thresh = 0.04 + 0.06 * (1.0 - bass);
            float orange_thresh = 0.18 - 0.06 * bass;
            float yellow_thresh = 0.52 - 0.18 * treble;
            float white_thresh = 0.80 - 0.15 * treble;
            
            orange_thresh = max(red_thresh + 0.02, orange_thresh);
            yellow_thresh = max(orange_thresh + 0.02, yellow_thresh);
            white_thresh = max(yellow_thresh + 0.02, white_thresh);
            
            if (total_temp < red_thresh) {
                float t = total_temp / red_thresh;
                flame_color = mix(vec3(0.0), col_red, t);
            } else if (total_temp < orange_thresh) {
                float t = (total_temp - red_thresh) / (orange_thresh - red_thresh);
                flame_color = mix(col_red, col_orange, t);
            } else if (total_temp < yellow_thresh) {
                float t = (total_temp - orange_thresh) / (yellow_thresh - orange_thresh);
                flame_color = mix(col_orange, col_yellow, t);
            } else if (total_temp < white_thresh) {
                float t = (total_temp - yellow_thresh) / (white_thresh - yellow_thresh);
                flame_color = mix(col_yellow, col_white, t);
            } else {
                float t = clamp((total_temp - white_thresh) / (1.0 - white_thresh), 0.0, 1.0);
                flame_color = mix(col_white, vec3(1.0, 1.0, 1.0), t);
            }
            
            // Only mix in standard blue gas base if we are in realistic mode (reduced influence)
            if (uColorMode == 0) {
                flame_color = mix(flame_color, col_blue, total_blue_mask * 0.3);
            }
            
            float target_density = total_temp * (3.8 + bass * 2.2);
            opacity = 1.0 - exp(-target_density);
            opacity = clamp(opacity, 0.0, 0.94);
        }
        
        float bg_glow = clamp(total_bg_glow, 0.0, 0.5);
        
        vec3 glow_tint;
        if (uColorMode == 1) {
            glow_tint = vec3(0.85, 0.0, 0.5);
        } else if (uColorMode == 2) {
            glow_tint = vec3(0.0, 0.3, 0.8);
        } else if (uColorMode == 3) {
            glow_tint = vec3(0.8, 0.5, 0.2);
        } else {
            glow_tint = vec3(0.85, 0.14, 0.01);
        }
        vec3 glow_color = glow_tint * bg_glow;
        base_color += glow_color;
        base_color = mix(base_color, flame_color * (1.1 + bass * 0.35), opacity);
        
    } else if (uFlameAlgorithm < 1.5) {
        // ... (Gas Jet, Bonfire, Candle, Vortex, Game unchanged) ...
    } else if (uFlameAlgorithm < 2.5) {
        // ... (Bonfire) ...
    } else if (uFlameAlgorithm < 3.5) {
        // ... (Candle) ...
    } else if (uFlameAlgorithm < 4.5) {
        // ... (Vortex) ...
    } else if (uFlameAlgorithm < 5.5) {
        // ... (Game) ...
    } else {
        // --- ALGORITHM 6: Multi (5 vortex plumes, independent flicker, spatial reactivity) ---
        float pulseBass = bass;
        float pulseMid = mid;
        float pulseTreble = treble;

        float container_mask = smoothstep(0.35, 0.25, abs(vPos.x));

        // Smoke (unchanged)
        if (vPos.y >= ground_height) {
            float s_height = vPos.y - ground_height;
            float smoke_width = 0.20 + 0.35 * s_height;
            float smoke_sway = sin(uTime * 0.9) * 0.15 + uWindGust * 0.6;
            float smoke_x = vPos.x - smoke_sway * s_height * 0.55;
            vec2 smoke_uv = vec2(smoke_x * 2.5, s_height * 0.35 - uTime * 0.5);
            float smoke_noise = fbm(smoke_uv * 3.0) * 0.4;
            float smoke_shape = exp(- (smoke_x * smoke_x) / (2.0 * smoke_width * smoke_width));
            float smoke_density = smoke_shape * (0.06 + 0.18 * smoke_noise) * smoothstep(1.0, 0.2, vPos.y);
            base_color = mix(base_color, vec3(0.25, 0.25, 0.30), smoke_density * 0.4);
        }

        // Coals (unchanged)
        float dist_to_coals = length(vec2(vPos.x * 3.0, (vPos.y - ground_height) * 5.0));
        float coals_glow = exp(-dist_to_coals * 3.5) * (0.8 + 0.5 * bass) * container_mask;
        base_color += vec3(0.98, 0.18, 0.01) * coals_glow * 1.5;

        // Five vortex plumes – each with its own height, width, color, and independent flicker
        float vortex_x_offsets[5];
        vortex_x_offsets[0] = -0.18;
        vortex_x_offsets[1] = -0.09;
        vortex_x_offsets[2] = 0.0;
        vortex_x_offsets[3] = 0.09;
        vortex_x_offsets[4] = 0.18;

        // Base neutral fire colors, used as a fallback tint when there's little spectral
        // energy present (keeps the fire looking natural during quiet passages).
        vec3 vortex_colors[5];
        vortex_colors[0] = vec3(0.95, 0.55, 0.0);   // orange-yellow
        vortex_colors[1] = vec3(0.95, 0.65, 0.0);   // yellow-orange
        vortex_colors[2] = vec3(1.0, 0.85, 0.2);    // yellow
        vortex_colors[3] = vec3(0.95, 0.65, 0.0);   // yellow-orange
        vortex_colors[4] = vec3(0.95, 0.55, 0.0);   // orange-yellow

        // Explicit spectral tint colors. A color shift is far more perceptible than subtle
        // height/width changes, so this is now the PRIMARY mechanism for making
        // "left flame = bass, center = mid, right flame = treble" clearly readable: bass
        // tints deep red, mid stays a natural orange, treble tints icy blue-white.
        vec3 col_bass_tint = vec3(1.0, 0.05, 0.0);
        vec3 col_mid_tint = vec3(1.0, 0.55, 0.05);
        vec3 col_treble_tint = vec3(0.65, 0.85, 1.0);

        // Per‑vortex music reactivity – each flame's color and gentle breathing follow the
        // music, blended smoothly by its horizontal position: leftmost leans toward bass,
        // rightmost toward treble, center toward mid.
        float reacts[5];
        float pulse_contrib[5];
        float pulse_diff[5];
        float pulseAvg = (pulseBass + pulseMid + pulseTreble) / 3.0;
        float pulseTotal = pulseBass + pulseMid + pulseTreble + 1e-4;
        float shareBass = pulseBass / pulseTotal;
        float shareMid = pulseMid / pulseTotal;
        float shareTreble = pulseTreble / pulseTotal;
        // Organic "bubbling up" color modulation: a noise-driven band that continuously
        // rises from the base of the flame over time, so color shifts appear to bubble up
        // from the bottom instead of the whole flame changing color uniformly and instantly.
        // Sampling y with a negative time offset (matching the smoke/lick conventions used
        // elsewhere in this shader) makes the noise pattern appear to travel upward.
        float bubble_ref_height = 0.42;
        float y_for_bubble = (vPos.y - ground_height) / bubble_ref_height;
        float bubble_noise = fbm(vec2(vPos.x * 5.0, y_for_bubble * 2.6 - uTime * 1.1));
        float bubble_mask = smoothstep(0.35, 0.85, bubble_noise);
        for (int v = 0; v < 5; v++) {
            float tv = clamp((vortex_x_offsets[v] + 0.18) / 0.36, 0.0, 1.0);
            // Strongly sharpened (but still smooth/continuous) spatial blend so it reads
            // clearly as "left flame follows bass, right flame follows treble", blending
            // gradually through the middle flames.
            float bw = pow(1.0 - tv, 2.4);
            float tw = pow(tv, 2.4);
            float mw = pow(clamp(1.0 - 2.0 * abs(tv - 0.5), 0.0, 1.0), 2.4);
            float sum = bw + mw + tw + 1e-5;
            bw /= sum;
            mw /= sum;
            tw /= sum;

            float p_share = bw * shareBass + mw * shareMid + tw * shareTreble;
            pulse_contrib[v] = pulseAvg;
            pulse_diff[v] = clamp((p_share - 1.0 / 3.0) * pulseTotal, -1.0, 1.0);

            // Explicit per-flame band dominance: weight each tint color by this flame's
            // spatial bias AND its actual current envelope level, so the resulting hue
            // reveals which band is dominant for THIS flame right now, while overall tint
            // strength scales with how much of that band is actually present (fading back to
            // the neutral fire palette during quiet passages instead of staying stuck).
            float wBass = bw * pulseBass;
            float wMid = mw * pulseMid;
            float wTreble = tw * pulseTreble;
            float wSum = wBass + wMid + wTreble + 1e-4;
            vec3 band_tint = (wBass * col_bass_tint + wMid * col_mid_tint + wTreble * col_treble_tint) / wSum;
            // Modulated by bubble_mask so tint bubbles up organically from the base rather
            // than flashing uniformly. This is the ONLY place bubble_mask is applied to
            // color now — previously it was also applied a second time to
            // color_blend_amount below, which compounded into the tint nearly vanishing.
            // DIAGNOSTIC BOOST: amplified and bubble attenuation minimized so any existing
            // per-band signal becomes impossible to miss.
            float tint_strength = clamp(wSum * 4.0, 0.0, 1.0) * mix(0.7, 1.0, bubble_mask);
            vortex_colors[v] = mix(vortex_colors[v], band_tint, tint_strength);

            // DIAGNOSTIC BOOST
            float flicker = sin(uTime * (0.8 + 0.3 * float(v)) + float(v) * 2.4) * 0.5 + 0.5;
            reacts[v] = 1.0 + pulseAvg * 0.03 + pulse_diff[v] * 0.35 + flicker * pulseAvg * 0.02;
        }

        // Local temperatures and color weights for each vortex
        float temps[5];
        float color_weights[5];
        float total_bg_glow = 0.0;

        for (int v = 0; v < 5; v++) {
            // Height: the shared/average pulse gives a very subtle common rise-and-fall,
            // while the amplified per-flame difference term makes each flame's own
            // bass/mid/treble bias clearly readable (left taller on bass, right taller on
            // treble, center on mid) without the overall fire pulsing hard.
            // Moderately toned down from the confirmed-visible version, but not eliminated.
            // DIAGNOSTIC BOOST: substantially amplified so any existing per-band signal
            // becomes impossible to miss. Dial back down once confirmed visible.
            float v_height = 0.35 + 0.025 * pulseAvg + 0.45 * pulse_diff[v];
            v_height = max(0.08, v_height);
            float y_raw = vPos.y - ground_height;
            // Relative coordinate used ONLY for the overall silhouette envelope (taper,
            // fade-out, decay) – this is what lets the flame subtly grow/shrink.
            float y_scaled_v = y_raw / v_height;
            temps[v] = 0.0;
            color_weights[v] = exp(-pow(vPos.x - vortex_x_offsets[v], 2.0) * 80.0);

            if (vPos.y >= ground_height && y_scaled_v < 1.3) {
                float height_fade = smoothstep(1.3, 0.5, y_scaled_v);
                float taper = 1.05 - y_scaled_v * 0.8;
                // Width breathes gently overall, but noticeably differs per-flame based on
                // its spectral bias (bass/mid/treble) via the amplified difference term.
                // DIAGNOSTIC BOOST
                float width_scale = clamp(1.0 + 0.012 * pulseAvg + 0.32 * pulse_diff[v], 0.5, 1.8);
                float profile_width = 0.07 * max(0.1, taper) * width_scale;
                float px = vPos.x - vortex_x_offsets[v];

                // DIAGNOSTIC BOOST
                float speed_scale = clamp(1.0 + 0.022 * pulseAvg + 0.30 * pulse_diff[v], 0.4, 2.0);
                float time_offset = uTime * (1.0 + 0.15 * float(v) + 0.5 * speed_scale);

                // Fixed-frequency vertical coordinate for flame DETAIL (licks/helix). A
                // constant reference height (instead of the reactive v_height) keeps the
                // flickering flame texture a consistent size, so height changes look like the
                // flame naturally growing taller rather than the whole pattern stretching.
                float ref_height = 0.35;
                float y_detail = y_raw / ref_height;

                float helix_angle = time_offset * 2.0 + y_detail * 6.0 + float(v) * 2.0;
                float helix_x = sin(helix_angle) * 0.03 * y_detail;
                px -= helix_x;

                float shape_mask = exp(- (px * px) / (2.0 * profile_width * profile_width)) * container_mask;

                // Independent noise seed – each vortex uses a different offset
                vec2 noise_uv = vec2(px * 3.0 + 0.17 * float(v), y_detail * 2.0 - time_offset * 0.8);
                vec2 warp1 = vec2(fbm(noise_uv * 1.5 + 0.31 * float(v)), fbm(noise_uv * 2.0 + vec2(1.0 + 0.13 * float(v))));
                vec2 final_uv = noise_uv + warp1 * 0.3;
                // Intensity brightens gently overall, with a clearer per-flame spectral bias.
                // DIAGNOSTIC BOOST
                float intensity_scale = clamp(1.0 + 0.010 * pulseAvg + 0.22 * pulse_diff[v], 0.6, 1.7);
                float licks = fbm(final_uv * 3.5 - vec2(0.0, time_offset * 0.9)) * intensity_scale;

                float flame_field = (exp(-y_scaled_v * 2.0) * 0.4 + licks * 0.6) * shape_mask - y_scaled_v * 0.5;
                float p_temp = smoothstep(0.05, 0.35, flame_field) * height_fade;
                p_temp = clamp(p_temp, 0.0, 1.0);
                temps[v] = p_temp;

                // Background glow tied to this flame's own blended pulse (bass on the left,
                // treble on the right) instead of a uniform global bass value, so the glow
                // reflects the left/right spectral differentiation rather than pulsing
                // uniformly with the beat.
                float glow_width = profile_width * 1.5;
                float glow_shape = exp(- (px * px) / (2.0 * glow_width * glow_width)) * container_mask;
                // DIAGNOSTIC BOOST
                total_bg_glow += glow_shape * exp(-y_scaled_v * 2.0) * clamp(0.04 + 0.015 * pulseAvg + 0.20 * pulse_diff[v], 0.0, 0.22);
            }
        }

        // Compute per-pixel local temperature by blending scaled temperatures from all vortices
        float local_temp = 0.0;
        float total_weight = 0.0;
        for (int v = 0; v < 5; v++) {
            float scaled_temp = temps[v] * reacts[v];
            float w = color_weights[v];
            local_temp += scaled_temp * w;
            total_weight += w;
        }
        if (total_weight > 0.001) {
            local_temp /= total_weight;
        } else {
            local_temp = 0.0;
        }

        // Smooth color blend from all vortices (unchanged)
        vec3 blend_color = vortex_colors[2];
        float total_cw = color_weights[0] + color_weights[1] + color_weights[2] + color_weights[3] + color_weights[4];
        if (total_cw > 0.001) {
            blend_color = vec3(0.0);
            for (int v = 0; v < 5; v++) {
                blend_color += vortex_colors[v] * color_weights[v];
            }
            blend_color /= total_cw;
        }

        if (local_temp > 0.005) {
            // Vortex color gradient (orange → yellow → white) – more realistic, less blue, more yellow
            vec3 col_orange = vec3(0.95, 0.55, 0.0);
            vec3 col_yellow = vec3(1.0, 0.85, 0.2);
            vec3 col_white = vec3(1.0, 1.0, 0.8);
            vec3 flame_color;
            if (local_temp < 0.2) {
                flame_color = mix(col_orange, col_yellow, local_temp / 0.2);
            } else if (local_temp < 0.6) {
                flame_color = mix(col_yellow, col_white, (local_temp - 0.2) / 0.4);
            } else {
                flame_color = mix(col_white, vec3(1.0, 0.95, 0.6), (local_temp - 0.6) / 0.4);
            }

            // Tint with the smoothly blended per‑vortex color (now carrying each flame's
            // dynamic bass/mid/treble tint) to give clearly visible spatial/spectral
            // variety. Blend strength scales up with overall spectral energy so the color
            // differentiation reads strongly during loud passages (like a prominent bass
            // hit) while staying subtle when the music is quiet.
            // bubble_mask is intentionally NOT reapplied here (see tint_strength above) to
            // avoid compounding two bubble-mask multiplications into near-invisibility.
            // DIAGNOSTIC BOOST
            float color_blend_amount = clamp(0.45 + pulseTotal * 0.45, 0.45, 0.95);
            flame_color = mix(flame_color, blend_color, color_blend_amount);

            // Density/opacity driven purely by local_temp, which already carries each
            // flame's own bass/mid/treble-blended pulse. Avoiding an additional uniform
            // global bass term here keeps brightness changes tied to the left/right
            // spectral differentiation instead of pulsing the whole fire uniformly.
            float target_density = local_temp * 3.0;
            float opacity = 1.0 - exp(-target_density);
            opacity = clamp(opacity, 0.0, 0.92);
            base_color = mix(base_color, flame_color, opacity);
        }
        base_color += vec3(0.85, 0.14, 0.01) * clamp(total_bg_glow, 0.0, 0.5);
    }
    
    return base_color;
}
"""
