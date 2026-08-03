# Pond-mode fullscreen environment: a painterly marshland, reflective blue water,
# layered storm clouds, natural raindrops, expanding ripples, distant trees, and swallows.
SKY_POND_SOURCE = """
float pondHash21(vec2 p) {
    p = fract(p * vec2(123.34, 345.45));
    p += dot(p, p + 34.345);
    return fract(p.x * p.y);
}

float pondNoise(vec2 p) {
    vec2 cell = floor(p);
    vec2 local = fract(p);
    local = local * local * (3.0 - 2.0 * local);

    return mix(
        mix(pondHash21(cell), pondHash21(cell + vec2(1.0, 0.0)), local.x),
        mix(pondHash21(cell + vec2(0.0, 1.0)), pondHash21(cell + vec2(1.0, 1.0)), local.x),
        local.y
    );
}

float pondFbm(vec2 p) {
    float value = 0.0;
    float amplitude = 0.5;
    for (int octave = 0; octave < 5; ++octave) {
        value += pondNoise(p) * amplitude;
        p = p * 2.03 + vec2(17.3, 9.2);
        amplitude *= 0.5;
    }
    return value;
}

vec3 renderPondDayMoon(vec2 uv, vec3 color) {
    // Reuse Fire Plasma's phase data, but render the moon as a restrained
    // daylight/overcast disc rather than a prominent nighttime light source.
    vec2 moonPosition = vec2(-0.62, 0.57);
    float moonRadius = 0.082;
    vec2 moonLocal = (uv - moonPosition) / moonRadius;
    float moonDistance = length(moonLocal);

    if (moonDistance > 1.0) {
        return color;
    }

    float moonEdge = 1.0 - smoothstep(0.94, 1.0, moonDistance);
    float moonZ = sqrt(max(0.0, 1.0 - dot(moonLocal, moonLocal)));
    vec3 moonNormal = normalize(vec3(moonLocal, moonZ));

    float phaseAngle = (
        uMoonIsWaning > 0.5 ? -1.0 : 1.0
    ) * 3.14159 * (1.0 - uMoonIllumed);
    vec3 moonLightDirection = normalize(vec3(
        sin(phaseAngle),
        0.08,
        cos(phaseAngle)
    ));
    float phaseLight = max(0.0, dot(moonNormal, moonLightDirection));
    float illuminated = smoothstep(0.0, 0.10, phaseLight);

    float maria = pondFbm(moonLocal * 8.5 + vec2(13.2, 4.8));
    float craters = pondNoise(floor(moonLocal * 24.0 + vec2(9.0, 7.0)));
    vec3 moonColor = vec3(0.67, 0.71, 0.68);
    moonColor *= 0.88 + maria * 0.16 - craters * 0.05;

    // The low opacity lets storm-cloud cover and the blue-grey daytime sky
    // dominate, like a moon only barely visible through thin cloud.
    float daylightMoon = moonEdge * (0.035 + illuminated * 0.105);
    return mix(color, moonColor, daylightMoon);
}

float pondMusicRippleHeight(vec2 position) {
    float height = 0.0;

    for (int index = 0; index < 8; ++index) {
        vec4 ripple = uPondRipples[index];
        if (ripple.w <= 0.0 || ripple.z <= 0.0 || ripple.z > 2.15) {
            continue;
        }

        // The pond is viewed obliquely, so depth is visually compressed. Apply
        // subtle noise to the distance field so each impact expands like a real,
        // irregular disturbance rather than as a mathematically perfect ring.
        vec2 delta = position - ripple.xy;
        delta.x *= uAspect;
        delta.y *= 2.35;
        float distance = length(delta);
        float surfaceNoise = pondNoise(
            position * vec2(17.0 * uAspect, 31.0)
            + ripple.xy * 23.0
        ) - 0.5;
        float radius = ripple.z * (0.52 + surfaceNoise * 0.035);
        float wavefront = distance - radius + surfaceNoise * 0.018;

        // Keep the disturbance tightly grouped around its expanding wavefront.
        // The rapid age fade makes every impact read as a fresh stone or drop,
        // rather than leaving broad, long-lived sinusoidal surface pressure.
        float envelope = exp(-wavefront * wavefront * 68.0)
            * exp(-ripple.z * 1.85)
            * (1.0 - smoothstep(1.50, 2.15, ripple.z));
        float irregularity = 0.90 + 0.10 * sin(
            atan(delta.y, delta.x) * 7.0 + ripple.z * 5.0 + surfaceNoise * 8.0
        );
        height += sin(wavefront * 68.0 - ripple.z * 11.0 + surfaceNoise * 3.0)
            * envelope
            * irregularity
            * ripple.w
            * 0.040;
    }

    return height;
}

float pondTreeLayer(vec2 uv, float horizon, float scale, float darkness) {
    // Wind is carried primarily by the music envelope, but remains in gentle
    // motion between hits. Each depth layer receives a distinct phase and a
    // slow secondary wave so the distant forest never sways as a rigid wall.
    float treeMusicEnergy = clamp(
        uReactBass * 0.58 + uReactMid * 0.32 + uReactTreble * 0.10,
        0.0,
        1.5
    );
    float treeSwayStrength = 0.0025 + treeMusicEnergy * 0.0105;
    float layerPhase = scale * 0.371;
    float treeSway = (
        sin(uTime * (0.72 + treeMusicEnergy * 0.22) + uv.x * 4.2 + layerPhase)
        + sin(uTime * 0.31 - uv.x * 9.1 + layerPhase * 2.7) * 0.38
    ) * treeSwayStrength;
    float canopyX = uv.x + treeSway;

    // A dense unbroken woodland silhouette. High-frequency canopy variation
    // suggests hundreds of overlapping trees disappearing into wet horizon haze.
    float canopyHeight = 0.12
        + pondFbm(vec2(canopyX * scale * 0.45, 2.7 + scale)) * 0.20
        + pondNoise(vec2(floor(canopyX * scale * 2.0), scale)) * 0.065;
    float canopyLine = horizon + canopyHeight;
    float treeMask = smoothstep(
        canopyLine + 0.018,
        canopyLine - 0.020,
        uv.y
    ) * smoothstep(horizon - 0.10, horizon + 0.025, uv.y);

    float foliage = pondFbm(
        vec2(canopyX * scale * 3.2, uv.y * 38.0 + scale * 4.0)
    );
    float crownBreaks = smoothstep(0.18, 0.74, foliage + 0.18);
    return treeMask * mix(0.72, 1.0, crownBreaks) * darkness;
}

vec3 renderPondSky(vec2 vPos, vec3 baseColor) {
    vec2 uv = vec2(vPos.x * uAspect, vPos.y);

    float bass = clamp(uReactBass, 0.0, 1.5);
    float mid = clamp(uReactMid, 0.0, 1.5);
    float treble = clamp(uReactTreble, 0.0, 1.5);
    float rainEnergy = clamp(0.25 * bass + 0.35 * mid + 0.65 * treble, 0.0, 1.5);

    // Overcast blue-grey sky with softly layered, wind-driven storm clouds.
    float skyGradient = smoothstep(-0.10, 1.0, vPos.y);
    vec3 stormHorizon = vec3(0.16, 0.27, 0.39);
    vec3 stormZenith = vec3(0.035, 0.075, 0.14);
    vec3 color = mix(stormHorizon, stormZenith, skyGradient);

    vec2 cloudUv = vec2(uv.x * 0.58 - uTime * 0.018, uv.y * 1.45);
    float cloudMass = pondFbm(cloudUv * 1.55 + vec2(0.0, 5.0));
    float cloudDetail = pondFbm(cloudUv * 4.2 - vec2(uTime * 0.012, 0.0));
    float cloudMask = smoothstep(0.42, 0.74, cloudMass + cloudDetail * 0.28);
    float cloudFalloff = smoothstep(-0.18, 0.76, vPos.y);
    vec3 cloudColor = mix(vec3(0.055, 0.085, 0.13), vec3(0.27, 0.34, 0.41), cloudDetail);
    color = mix(color, cloudColor, cloudMask * cloudFalloff * 0.82);

    // A faint phase-aware daytime moon is visible through the overcast sky.
    color = renderPondDayMoon(uv, color);

    // Several soft woodland layers dissolve together at the wet horizon. A
    // watercolor-like haze prevents a hard cut between trees and marsh grass.
    float horizon = -0.10 + pondFbm(vec2(uv.x * 1.8, 2.0)) * 0.055;
    float farTrees = pondTreeLayer(uv, horizon + 0.025, 27.0, 0.40);
    float middleTrees = pondTreeLayer(uv + vec2(0.071, 0.0), horizon - 0.005, 18.0, 0.63);
    float nearTrees = pondTreeLayer(uv + vec2(0.137, 0.0), horizon - 0.040, 12.0, 0.82);
    float distantWoodland = max(farTrees, middleTrees);
    vec3 distantTreelineColor = mix(
        vec3(0.075, 0.12, 0.13),
        vec3(0.026, 0.095, 0.062),
        middleTrees
    );
    color = mix(color, distantTreelineColor, distantWoodland);

    // Bright, sparse will-o'-wisps sit in the depth gap immediately behind the
    // foreground canopy. The near trees are composited afterwards, which dims
    // and partially hides them like intervening leaves without erasing them.
    float wispMusicEnergy = clamp(
        bass * 0.48 + mid * 0.36 + treble * 0.46,
        0.0,
        1.5
    );
    float swampLights = 0.0;
    for (int wispIndex = 0; wispIndex < 23; ++wispIndex) {
        float wispSeed = pondHash21(vec2(float(wispIndex), 47.31));
        float wispSeed2 = pondHash21(vec2(float(wispIndex), 91.73));
        float wispX = mix(-0.88, 0.88, wispSeed);
        float wispY = horizon - 0.030 + wispSeed2 * 0.110;
        float drift = sin(
            uTime * (0.28 + wispSeed2 * 0.30) + wispSeed * 18.0
        ) * 0.016;
        vec2 wispDelta = vPos - vec2(wispX + drift, wispY);
        wispDelta.x *= uAspect;
        float wispDistance = length(wispDelta);
        float individualPulse = 0.58 + 0.42 * sin(
            uTime * (1.05 + wispSeed * 1.45) + wispSeed2 * 21.0
        );
        // Keep a dim resting glow, but let analyzed musical energy drive a
        // pronounced bloom on beats and sustained passages.
        float musicPulse = 0.24 + wispMusicEnergy * 1.95;
        float core = 1.0 - smoothstep(0.0032, 0.0080, wispDistance);
        float innerGlow = 1.0 - smoothstep(0.010, 0.026, wispDistance);
        float halo = 1.0 - smoothstep(0.025, 0.062, wispDistance);
        swampLights += (core * 2.4 + innerGlow * 0.72 + halo * 0.15)
            * individualPulse * musicPulse;
    }
    color += vec3(0.34, 0.95, 0.43) * swampLights * 0.72;

    vec3 nearTreelineColor = vec3(0.018, 0.070, 0.045);
    color = mix(color, nearTreelineColor, nearTrees);
    float woodland = max(distantWoodland, nearTrees);

    float horizonSmudge = smoothstep(
        0.16,
        0.0,
        abs(vPos.y - horizon + (pondFbm(uv * 8.0) - 0.5) * 0.10)
    );
    vec3 wetHaze = vec3(0.075, 0.13, 0.115);
    color = mix(color, wetHaze, horizonSmudge * (0.16 + woodland * 0.22));

    // The pond keeps its original broad, lowered elliptical silhouette, but its
    // edge is now defined by one coherent, low-frequency shoreline field. The
    // small angular warp forms coves and headlands without creating concentric
    // bands or an obviously procedural scalloped outline.
    float pondCenterY = horizon - 0.63;
    vec2 pondScale = vec2(1.30, 0.64);
    vec2 pondLocal = vec2(
        vPos.x / pondScale.x,
        (vPos.y - pondCenterY) / pondScale.y
    );
    float shoreAngle = atan(pondLocal.y, pondLocal.x);
    float broadShore = pondNoise(vec2(shoreAngle * 1.15, 4.7)) - 0.5;
    float coveShore = pondNoise(vec2(shoreAngle * 3.85, 12.3)) - 0.5;
    float shoreDrift = pondFbm(vec2(
        shoreAngle * 0.82 + 6.3,
        3.1
    )) - 0.5;
    float shorelineRadius = 1.0
        + broadShore * 0.090
        + coveShore * 0.028
        + shoreDrift * 0.022;
    float pondRadialDistance = length(pondLocal);
    float shoreDistance = pondRadialDistance - shorelineRadius;

    // Negative values are inside the pond. Keep the transition narrow enough
    // to retain a readable shoreline while anti-aliasing the full boundary.
    float pondMask = 1.0 - smoothstep(-0.012, 0.024, shoreDistance);
    float shoreInterior = smoothstep(-0.250, -0.012, shoreDistance);

    // The land below the horizon is a single marsh field. It is deliberately
    // established before water is composited so the shore can reveal wet soil
    // and submerged sediment naturally rather than painting separate rings.
    float belowHorizon = smoothstep(
        horizon + 0.075,
        horizon - 0.085,
        vPos.y + (pondFbm(uv * 7.0) - 0.5) * 0.055
    );

    float grassNoise = pondFbm(vec2(uv.x * 16.0, vPos.y * 24.0));
    float grassBlades = smoothstep(
        0.70,
        0.92,
        pondNoise(vec2(floor(uv.x * 145.0), floor(vPos.y * 72.0)))
    );
    vec3 marshGround = mix(
        vec3(0.035, 0.075, 0.040),
        vec3(0.10, 0.20, 0.075),
        grassNoise
    );
    marshGround *= 0.72 + 0.28 * smoothstep(-1.0, horizon, vPos.y);
    marshGround += vec3(0.025, 0.055, 0.018) * grassBlades;

    // Wet earth appears only in a narrow band immediately outside the water.
    // This follows the exact same signed edge as the water, avoiding the old
    // mismatched opacity and soil transitions.
    float bankTexture = pondFbm(uv * vec2(15.0, 19.0));
    vec3 wetBank = mix(
        vec3(0.040, 0.075, 0.038),
        vec3(0.115, 0.120, 0.055),
        bankTexture
    );
    float bankWetness = smoothstep(0.125, 0.008, shoreDistance);
    marshGround = mix(marshGround, wetBank, bankWetness * 0.56);

    // Sparse, broken rushes root on the outside of the bank. Their placement
    // is constrained to the signed shoreline strip rather than forming a full
    // decorative ring around the pond.
    float rushSeed = pondNoise(vec2(
        floor(uv.x * 96.0),
        floor(vPos.y * 54.0)
    ));
    float rushes = smoothstep(0.855, 0.945, rushSeed)
        * smoothstep(0.135, 0.015, shoreDistance)
        * smoothstep(-0.018, 0.018, shoreDistance);
    marshGround = mix(marshGround, vec3(0.022, 0.100, 0.040), rushes * 0.34);

    // Reflective water combines small wind waves with real-time radial waves
    // from simultaneous music hits. Sampling nearby heights yields a moving
    // surface normal, so overlapping rings visibly interfere in the reflections.
    float depth = clamp((horizon - vPos.y) / 0.95, 0.0, 1.0);
    float waveA = sin(uv.x * 15.0 + uTime * (1.3 + mid * 1.8));
    float waveB = sin(uv.x * 29.0 - uTime * (1.8 + treble * 2.4) + vPos.y * 13.0);
    vec2 waterFlow = vec2(
        uv.x * 6.0 + uTime * 0.18,
        vPos.y * 10.0 - uTime * 0.11
    );
    float waterNoise = pondFbm(waterFlow);
    float rippleHeight = pondMusicRippleHeight(vPos);
    float rippleHeightX = pondMusicRippleHeight(vPos + vec2(0.006, 0.0));
    float rippleHeightY = pondMusicRippleHeight(vPos + vec2(0.0, 0.006));
    vec2 rippleSlope = vec2(
        rippleHeightX - rippleHeight,
        rippleHeightY - rippleHeight
    ) / 0.006;
    vec3 rippleNormal = normalize(vec3(
        -rippleSlope.x * 3.2,
        -rippleSlope.y * 3.2,
        1.0
    ));
    vec3 waterLightDirection = normalize(vec3(-0.35, 0.58, 0.74));
    float rippleSpecular = pow(
        max(0.0, dot(rippleNormal, waterLightDirection)),
        18.0
    );
    float rippleCrest = smoothstep(0.010, 0.032, abs(rippleHeight));
    float waterLight = 0.52 + waveA * 0.10 + waveB * 0.055
        + waterNoise * 0.15 + rippleHeight * 2.1;

    vec3 shallowWater = vec3(0.045, 0.27, 0.40);
    vec3 deepWater = vec3(0.008, 0.070, 0.145);
    vec3 water = mix(shallowWater, deepWater, depth);
    water *= 0.72 + waterLight * 0.55;

    // The shallow zone lives inside the same shoreline field. Sediment becomes
    // visible gradually in the final quarter of the pond rather than fading the
    // complete water mask before the actual edge is reached.
    vec3 submergedBottom = mix(
        vec3(0.060, 0.115, 0.070),
        vec3(0.20, 0.20, 0.115),
        bankTexture
    );
    water = mix(
        water,
        submergedBottom * (0.76 + waterLight * 0.24),
        shoreInterior * 0.66
    );
    water += vec3(0.22, 0.46, 0.58) * rippleSpecular * 0.14;
    water += vec3(0.06, 0.20, 0.29) * rippleCrest * 0.10;

    // Flowing cloud and treeline reflections drift continuously across the
    // surface, with wave displacement breaking them into natural moving streaks.
    vec2 reflectionFlow = vec2(
        uv.x * 10.0 + waveA * 0.28 + uTime * 0.075,
        vPos.y * 14.0 + waveB * 0.20 - uTime * 0.16
    );
    float reflectionNoise = pondFbm(reflectionFlow);
    float reflection = smoothstep(0.46, 0.76, reflectionNoise)
        * smoothstep(horizon, horizon - 0.65, vPos.y);
    water = mix(water, vec3(0.14, 0.30, 0.33), reflection * 0.18);

    color = mix(color, marshGround, belowHorizon);
    color = mix(color, water, pondMask);

    // Three independently seeded depth layers of long, fine rain shafts. The
    // anisotropic distance test produces continuous slanted drops rather than
    // a tiled grid of dashed vertical marks.
    float rainStreak = 0.0;
    for (int layer = 0; layer < 3; ++layer) {
        float layerFloat = float(layer);
        float density = 17.0 + layerFloat * 13.0;
        vec2 rainCell = floor(vec2(
            uv.x * density + vPos.y * (1.45 + layerFloat * 0.22),
            vPos.y * (8.0 + layerFloat * 2.7)
        ));
        float rainSeed = pondHash21(rainCell + vec2(31.7 * layerFloat, 13.1));
        float fall = fract(
            uTime * (1.8 + layerFloat * 0.55 + rainEnergy * 2.6)
            + rainSeed * 23.0
        );
        vec2 rainLocal = fract(vec2(
            uv.x * density + vPos.y * (1.45 + layerFloat * 0.22) + rainSeed,
            vPos.y * (8.0 + layerFloat * 2.7) + fall
        )) - 0.5;

        float rainLength = 0.22 + rainSeed * 0.30;
        float rainWidth = 0.0022 + rainSeed * 0.0022;
        float shaftDistance = abs(rainLocal.x + rainLocal.y * 0.105);
        float shaft = smoothstep(rainWidth, 0.0, shaftDistance)
            * smoothstep(rainLength, rainLength * 0.12, abs(rainLocal.y));
        rainStreak += shaft * (0.50 - layerFloat * 0.10);
    }
    float rainVisible = 0.18 + smoothstep(0.05, 1.0, rainEnergy) * 0.58;
    color += vec3(0.42, 0.63, 0.76) * rainStreak * rainVisible;

    // Small distant flocking-screen-saver bird icons. The CPU boids simulation
    // supplies their positions and headings; music events steer the flock as one.
    for (int bird = 0; bird < 14; ++bird) {
        vec4 birdData = uPondBirds[bird];
        vec2 birdLocal = vPos - birdData.xy;
        float headingCos = cos(birdData.z);
        float headingSin = sin(birdData.z);
        birdLocal = mat2(
            headingCos, headingSin,
            -headingSin, headingCos
        ) * birdLocal;

        // Tiny, distant profile icons: their movement is the focus, rather than
        // oversized detailed bird geometry.
        float wingLift = sin(birdData.w) * 0.002;
        float leftWing = smoothstep(
            0.0020,
            0.00055,
            abs(birdLocal.y - (abs(birdLocal.x + 0.006) * 0.38 + wingLift))
        ) * smoothstep(0.018, 0.003, abs(birdLocal.x + 0.006));
        float rightWing = smoothstep(
            0.0020,
            0.00055,
            abs(birdLocal.y - (abs(birdLocal.x - 0.006) * 0.38 - wingLift))
        ) * smoothstep(0.018, 0.003, abs(birdLocal.x - 0.006));
        float body = smoothstep(
            0.0030,
            0.0008,
            length((birdLocal - vec2(0.002, 0.0)) * vec2(1.55, 0.80))
        );
        float tail = smoothstep(
            0.0018,
            0.0005,
            abs(abs(birdLocal.y) - (-birdLocal.x - 0.004) * 0.35)
        ) * smoothstep(0.015, 0.002, -birdLocal.x);
        float swallow = max(body, max(leftWing, max(rightWing, tail)));
        color = mix(color, vec3(0.008, 0.014, 0.020), swallow * 0.88);
    }

    // A turbulent vortex rooted in the distant grassy bank. Each leaf follows
    // a perturbed vortex orbit with different angular velocity, radial drift,
    // and vertical lift, producing a chaotic gust rather than a rigid spiral.
    if (uPondLeafVortex.y > 0.0) {
        float vortexAge = 4.5 - uPondLeafVortex.y;
        float leafFade = (1.0 - smoothstep(
            3.80, 4.50, uPondLeafVortex.y
        )) * smoothstep(0.0, 0.42, uPondLeafVortex.y);

        for (int leafIndex = 0; leafIndex < 42; ++leafIndex) {
            float seed = pondHash21(vec2(float(leafIndex), 18.37));
            float seed2 = pondHash21(vec2(float(leafIndex), 73.91));
            float cycle = fract(vortexAge * (0.16 + seed * 0.11) + seed2);
            float lift = mix(-0.20, 0.48, cycle);
            float baseRadius = mix(0.06, 0.32, seed);
            float turbulence = sin(
                vortexAge * (5.0 + seed * 6.0) + seed2 * 19.0
            ) * 0.045;
            float radius = baseRadius * (1.0 - cycle * 0.58) + turbulence;
            float angularVelocity = 4.2 + 5.8 / max(radius * 5.0, 0.35);
            float angle = seed * 6.2831853
                + vortexAge * angularVelocity
                + sin(vortexAge * 3.7 + seed * 27.0) * 0.48;
            vec2 leafCenter = vec2(
                uPondLeafVortex.x
                    + cos(angle) * radius / uAspect,
                lift + sin(angle * 1.6 + vortexAge * 2.0) * radius * 0.20
            );
            vec2 leafLocal = vPos - leafCenter;
            float tilt = angle + sin(vortexAge * 7.0 + seed * 31.0) * 0.65;
            leafLocal = mat2(
                cos(tilt), -sin(tilt),
                sin(tilt), cos(tilt)
            ) * leafLocal;
            float leaf = 1.0 - smoothstep(
                0.68, 1.08, length(leafLocal / vec2(0.0065, 0.0032))
            );
            vec3 leafColor = mix(
                vec3(0.12, 0.035, 0.006),
                vec3(0.38, 0.12, 0.015),
                seed
            );
            color = mix(color, leafColor, leaf * leafFade * 0.90);
        }
    }

    // The strike ends at the far horizon. Rendering it before the foreground
    // canopy mask makes the treeline naturally occlude its lower branches.
    if (uPondLightning > 0.0) {
        float flashAge = 0.55 - uPondLightning;
        float strikeX = -0.42 + sin(floor(uTime * 19.0) * 7.3) * 0.48;
        // Terminate the strike inside the distant canopy, where the layered
        // treeline masks its lower branches.
        float boltEndY = horizon + 0.12;
        float boltRange = 0.92 - boltEndY;
        float progress = clamp((0.92 - vPos.y) / boltRange, 0.0, 1.0);
        float centerX = strikeX + progress * 0.045
            + sin(progress * 19.0 + 0.8) * 0.015
            + sin(progress * 47.0 + 2.1) * 0.006;
        float boltPath = step(boltEndY, vPos.y) * step(vPos.y, 0.92);
        float trunk = (
            1.0 - smoothstep(0.0008, 0.006, abs(vPos.x - centerX))
        ) * boltPath;
        float branch = (
            1.0 - smoothstep(
                0.0006,
                0.0032,
                abs(vPos.x - (centerX - 0.075 * progress))
            )
        ) * smoothstep(0.42, 0.47, progress)
          * (1.0 - smoothstep(0.63, 0.68, progress));
        float boltCore = max(trunk, branch) * exp(-flashAge * 22.0);

        // Keep the forked strike in the open distant sky, then crop it well
        // above the foreground woodland. This makes it appear to disappear
        // behind the front treeline without allowing it to render over it.
        boltCore *= smoothstep(0.08, 0.14, vPos.y);
        float thunderGlow = exp(-flashAge * 4.3) * 0.16;
        color += vec3(0.30, 0.42, 0.56) * thunderGlow;
        color += vec3(0.80, 0.93, 1.0) * boltCore * 2.8;
    }

    // A compact trout jumps between two nearby points in the pond. The fish is
    // modeled as a filled body with a forked tail, not intersecting line strokes.
    if (uPondTrout.w > 0.5) {
        float fishTime = uPondTrout.y;
        float jumpDuration = 1.08;
        float jumpProgress = clamp(fishTime / jumpDuration, 0.0, 1.0);
        float startX = uPondTrout.x;
        float landingX = startX + uPondTrout.z * 0.30;
        float fishHeight = -0.80 + 0.48 * 4.0
            * jumpProgress * (1.0 - jumpProgress);
        vec2 fishCenter = vec2(
            mix(startX, landingX, jumpProgress),
            fishHeight
        );
        vec2 fishLocal = vPos - fishCenter;
        fishLocal.x *= uPondTrout.z;

        // Align the trout's profile with its ballistic trajectory: nose-up on
        // ascent, level at the apex, and nose-down as it returns to the pond.
        float fishPitch = atan(6.4 * (1.0 - 2.0 * jumpProgress));
        float pitchCos = cos(fishPitch);
        float pitchSin = sin(fishPitch);
        fishLocal = mat2(
            pitchCos, -pitchSin,
            pitchSin, pitchCos
        ) * fishLocal;

        float bodyCurve = 0.012 * (
            1.0 - fishLocal.x * fishLocal.x / 0.0025
        );
        float fishBody = 1.0 - smoothstep(
            0.72,
            1.04,
            length(vec2(
                fishLocal.x / 0.050,
                (fishLocal.y - bodyCurve) / 0.013
            ))
        );
        float head = 1.0 - smoothstep(
            0.72,
            1.06,
            length(
                (fishLocal - vec2(0.043, bodyCurve))
                / vec2(0.014, 0.012)
            )
        );

        // Bounded fin lobes form a compact forked tail. This avoids the
        // unbounded line-distance tests that previously produced long streaks.
        float tailUpper = 1.0 - smoothstep(
            0.72,
            1.08,
            length(
                (fishLocal - vec2(-0.057, 0.011))
                / vec2(0.017, 0.006)
            )
        );
        float tailLower = 1.0 - smoothstep(
            0.72,
            1.08,
            length(
                (fishLocal - vec2(-0.057, -0.011))
                / vec2(0.017, 0.006)
            )
        );
        float tail = max(tailUpper, tailLower);
        float trout = max(fishBody, max(head, tail))
            * (1.0 - smoothstep(1.00, 1.08, fishTime));

        vec3 troutColor = mix(
            vec3(0.10, 0.22, 0.17),
            vec3(0.70, 0.38, 0.12),
            smoothstep(-0.010, 0.010, fishLocal.y - bodyCurve)
        );
        color = mix(color, troutColor, trout);

        float splashAge = max(0.0, fishTime - 0.95);
        float splashDistance = length(
            (vPos - vec2(landingX, -0.80)) * vec2(uAspect, 2.25)
        );
        float crown = 1.0 - smoothstep(
            0.0010,
            0.0060,
            abs(splashDistance - (0.018 + splashAge * 0.085))
        );
        crown *= smoothstep(-0.80, -0.66, vPos.y) * exp(-splashAge * 4.5);
        float ring = 1.0 - smoothstep(
            0.0010,
            0.0070,
            abs(splashDistance - splashAge * 0.28)
        );
        ring *= exp(-splashAge * 2.6);
        color += vec3(0.42, 0.68, 0.78) * (crown * 0.66 + ring * 0.36);
    }

    // Thunderclap illumination is composited last so the complete sky, pond,
    // treeline, and rain briefly flash even though those layers replace the
    // initial background color during rendering.
    if (uPondLightning > 0.0) {
        float flashAge = 0.55 - uPondLightning;
        float skyFlash = exp(-flashAge * 6.5) * 0.52;
        color += vec3(0.58, 0.72, 0.88) * skyFlash;
    }

    return color;
}
"""
