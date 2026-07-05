# audio_analyzer.py
import sys
import os
import json
import subprocess
import numpy as np
import scipy.signal

COLORS_KEYS = [
    "strontium_red",
    "barium_green",
    "copper_blue",
    "sodium_gold",
    "calcium_orange",
    "potassium_purple",
    "magnesium_white"
]

def get_panning(t_sec, fs, y_left, y_right, window_duration=0.1):
    """Calculates local stereo panning index from -1.0 (hard left) to 1.0 (hard right)."""
    half_len = int(window_duration * fs / 2)
    center_idx = int(t_sec * fs)
    start_idx = max(0, center_idx - half_len)
    end_idx = min(len(y_left), center_idx + half_len)
    
    if start_idx >= end_idx:
        return 0.0
        
    l_chunk = y_left[start_idx:end_idx]
    r_chunk = y_right[start_idx:end_idx]
    
    l_sum = np.sum(l_chunk**2)
    r_sum = np.sum(r_chunk**2)
    
    denom = l_sum + r_sum
    if denom < 1e-5:
        return 0.0
        
    return (r_sum - l_sum) / denom

def get_spectrum_color(t_sec, t, mag, bass_bins, mid_bins, high_bins, palette_override=None):
    """Uses localized spectrum energy balances to map colors (bass=blue/purple, treble=red/orange/white)."""
    idx = np.argmin(np.abs(t - t_sec))
    frame_mag = mag[:, idx]
    
    bass_energy = np.sum(frame_mag[bass_bins]) if np.any(bass_bins) else 0.0
    mid_energy = np.sum(frame_mag[mid_bins]) if np.any(mid_bins) else 0.0
    high_energy = np.sum(frame_mag[high_bins]) if np.any(high_bins) else 0.0
    
    total = bass_energy + mid_energy + high_energy
    if total < 1e-5:
        bass_ratio, mid_ratio, high_ratio = 0.33, 0.33, 0.34
    else:
        bass_ratio = bass_energy / total
        mid_ratio = mid_energy / total
        high_ratio = high_energy / total
        
    bass_colors = ["copper_blue", "potassium_purple"]
    high_colors = ["strontium_red", "calcium_orange", "magnesium_white"]
    mid_colors = ["barium_green", "sodium_gold"]
    
    if palette_override:
        b_colors = [c for c in bass_colors if c in palette_override] or palette_override
        m_colors = [c for c in mid_colors if c in palette_override] or palette_override
        h_colors = [c for c in high_colors if c in palette_override] or palette_override
    else:
        b_colors, m_colors, h_colors = bass_colors, mid_colors, high_colors
        
    r = np.random.uniform(0, 1)
    if r < bass_ratio:
        return str(np.random.choice(b_colors))
    elif r < bass_ratio + mid_ratio:
        return str(np.random.choice(m_colors))
    else:
        return str(np.random.choice(h_colors))

def analyze_audio(mp3_path, color_hints=None):
    """
    Decodes an audio file to stereo via ffmpeg and performs Short-Time Fourier Transform (STFT).
    Partitions the track into continuous sections (Quiet/Medium/Loud) using a smoothed RMS envelope.
    Applies Adaptive Relative Thresholding for robust peak detection during quiet sections.
    Safely terminates launches before the track finishes to prevent post-music explosions.
    """
    if not os.path.exists(mp3_path):
        raise FileNotFoundError(f"Audio file not found: {mp3_path}")
        
    print(f"Decoding {mp3_path} using FFmpeg subprocess stream...")
    
    # 1. Decode audio to raw float32 PCM stereo at 22050 Hz
    cmd = ['/home/sumner/bin/ffmpeg', '-y', '-i', mp3_path, '-f', 'f32le', '-ac', '2', '-ar', '22050', '-']
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = p.communicate()
    
    if p.returncode != 0:
        err_msg = stderr.decode('utf-8', errors='ignore')[-300:]
        raise RuntimeError(f"FFmpeg decoding failed: {err_msg}")
        
    y_stereo = np.frombuffer(stdout, dtype=np.float32)
    # Separate interleaved stereo channels
    y_stereo = y_stereo.reshape(-1, 2)
    y_left = y_stereo[:, 0]
    y_right = y_stereo[:, 1]
    
    # Calculate mono mixdown for spectral and legacy structural analysis
    y = (y_left + y_right) / 2.0
    fs = 22050
    duration = len(y) / fs
    print(f"Decoded {len(y)} samples (stereo). Duration: {duration:.2f} seconds.")
    
    # 2. Short-Time Fourier Transform (STFT) analysis
    hop_length = 512
    n_fft = 1024
    
    # Calculate STFT matrix
    f, t, Zxx = scipy.signal.stft(y, fs=fs, nperseg=n_fft, noverlap=n_fft - hop_length)
    mag = np.abs(Zxx)  # Amplitude spectrum
    
    # 3. Extract Spectral Band Energy Envelopes
    bass_bins = (f >= 20) & (f <= 180)
    mid_bins = (f >= 200) & (f <= 2000)
    high_bins = (f >= 2000) & (f <= 8000)
    
    bass_env = np.sum(mag[bass_bins, :], axis=0) if np.any(bass_bins) else np.zeros(mag.shape[1])
    mid_env = np.sum(mag[mid_bins, :], axis=0) if np.any(mid_bins) else np.zeros(mag.shape[1])
    high_env = np.sum(mag[high_bins, :], axis=0) if np.any(high_bins) else np.zeros(mag.shape[1])
    
    # 4. Compute Volume Profile (RMS envelope)
    num_chunks = len(y) // hop_length
    truncated_y = y[:num_chunks * hop_length]
    rms = np.sqrt(np.mean(truncated_y.reshape(-1, hop_length)**2, axis=1))
    
    # Align size of all arrays
    min_len = min(len(t), len(rms))
    t = t[:min_len]
    bass_env = bass_env[:min_len]
    mid_env = mid_env[:min_len]
    high_env = high_env[:min_len]
    rms = rms[:min_len]
    
    # Normalize envelopes
    def norm(env):
        mx = np.max(env)
        return env / mx if mx > 0 else env
        
    bass_norm = norm(bass_env)
    mid_norm = norm(mid_env)
    high_norm = norm(high_env)
    rms_norm = norm(rms)
    
    # 5. Beat / Tempo Detection (BPM estimation)
    onset_strength = np.diff(mid_norm)
    onset_strength = np.clip(onset_strength, 0, None)
    
    fps_audio = fs / hop_length  # ~43.07 frames per second
    min_lag = int(fps_audio * 60 / 180)  # 180 BPM
    max_lag = int(fps_audio * 60 / 60)   # 60 BPM
    
    acf = np.correlate(onset_strength, onset_strength, mode='full')
    acf = acf[len(acf)//2:]
    
    search_range = acf[min_lag:max_lag]
    best_lag_offset = np.argmax(search_range) if len(search_range) > 0 else 0
    best_lag = min_lag + best_lag_offset
    
    bpm = 60.0 * fps_audio / best_lag if best_lag > 0 else 120.0
    print(f"Estimated Track BPM: {bpm:.1f}")
    
    # 6. Automatic Audio End-Time Detection (Safety Cutoff)
    # Scan backward from the end to find where music actually stops
    audio_end_time = duration
    for i in range(len(rms) - 1, -1, -1):
        if rms[i] > 0.015:
            audio_end_time = float(t[i])
            break
            
    safety_cutoff = audio_end_time - 2.5
    print(f"Detected music end: {audio_end_time:.2f}s. Safety launch cutoff: {safety_cutoff:.2f}s.")
    
    # 7. Structural Song Partitioning
    # Smooth RMS envelope heavily using 6-second window standard deviation Gaussian filter
    from scipy.ndimage import gaussian_filter1d
    sigma = int(6.0 * fps_audio)
    rms_smooth = gaussian_filter1d(rms, sigma)
    rms_smooth_norm = norm(rms_smooth)
    
    # Group frames into raw QUIET, MEDIUM, LOUD classes
    raw_classes = []
    for val in rms_smooth_norm:
        if val < 0.58:
            raw_classes.append("QUIET")
        elif val >= 0.72:
            raw_classes.append("LOUD")
        else:
            raw_classes.append("MEDIUM")
            
    # Stabilize segment transitions using a 4-second sliding majority vote
    window_size = int(4.0 * fps_audio)
    if window_size % 2 == 0:
        window_size += 1
        
    smoothed_classes = []
    for i in range(len(t)):
        start_idx = max(0, i - window_size // 2)
        end_idx = min(len(t), i + window_size // 2 + 1)
        votes = raw_classes[start_idx:end_idx]
        majority = max(set(votes), key=votes.count)
        smoothed_classes.append(majority)
        
    # Generate Section Change Events
    events = []
    last_class = None
    for i in range(len(t)):
        t_sec = float(t[i])
        if t_sec > safety_cutoff:
            continue
        c = smoothed_classes[i]
        if c != last_class:
            if c == "QUIET":
                name = "Piccolo & Woodwind Trio"
            elif c == "LOUD":
                if t_sec < 15.0:
                    name = "Festive Patriotic Opening"
                elif t_sec > 160.0:
                    name = "Grandioso Finale (Full Band)"
                else:
                    name = "Brass Climax / Break Strain"
            else:
                name = "Moderate March Strain"
                
            events.append({
                "time": round(t_sec, 3),
                "type": "section",
                "name": name,
                "category": c
            })
            last_class = c
            
    # 8. Adaptive/Relative Peak Detection Thresholds
    # Scale peak threshold heights dynamically according to the local volume envelope
    bass_thresholds = np.clip(0.50 * rms_smooth_norm, 0.15, 0.42)
    mid_thresholds = np.clip(0.55 * rms_smooth_norm, 0.16, 0.45)
    high_thresholds = np.clip(0.45 * rms_smooth_norm, 0.12, 0.35)
    
    bass_peaks, _ = scipy.signal.find_peaks(bass_norm, height=bass_thresholds, distance=int(0.50 * fps_audio))
    high_peaks, _ = scipy.signal.find_peaks(high_norm, height=high_thresholds, distance=int(0.35 * fps_audio))
    mid_peaks, _ = scipy.signal.find_peaks(mid_norm, height=mid_thresholds, distance=int(0.45 * fps_audio))
    climax_peaks, _ = scipy.signal.find_peaks(rms_norm, height=0.68, distance=int(15.0 * fps_audio))
    
    # 9. Dynamic Choreography & Artistic Palettes Mapping
    # Setup section palettes
    quiet_colors = ["magnesium_white", "copper_blue", "potassium_purple"]
    medium_colors = ["magnesium_white", "copper_blue", "sodium_gold", "calcium_orange"]
    loud_colors = ["strontium_red", "magnesium_white", "copper_blue", "barium_green"]
    
    if color_hints:
        valid_hints = [c for c in color_hints if c in COLORS_KEYS]
        if valid_hints:
            q_palette = [c for c in quiet_colors if c in valid_hints] or valid_hints
            m_palette = [c for c in medium_colors if c in valid_hints] or valid_hints
            l_palette = [c for c in loud_colors if c in valid_hints] or valid_hints
        else:
            q_palette, m_palette, l_palette = quiet_colors, medium_colors, loud_colors
    else:
        q_palette, m_palette, l_palette = quiet_colors, medium_colors, loud_colors
        
    # Trigger major choreographed routines at RMS climax peaks (LOUD sections only)
    routines = ["American Flag", "Liberty Bell", "Statue of Liberty", "Flower Bouquet", "The Dragon"]
    routine_idx = 0
    climax_times = []
    
    for cp in climax_peaks:
        t_sec = float(t[cp])
        if t_sec > safety_cutoff:
            continue
        if smoothed_classes[cp] != "LOUD":
            continue
            
        climax_times.append(t_sec)
        events.append({
            "time": round(t_sec, 3),
            "type": "routine",
            "name": routines[routine_idx % len(routines)]
        })
        routine_idx += 1
        
    def is_near_climax(t_sec):
        for ct in climax_times:
            if abs(t_sec - ct) < 2.0:
                return True
        return False
        
    # Add shells from Bass, Mid, and High bands based on local active section characteristics
    # Bass peaks -> Heavy ground breakers and large shells
    for bp in bass_peaks:
        t_sec = float(t[bp])
        if t_sec > safety_cutoff or is_near_climax(t_sec):
            continue
        if any(abs(t_sec - ev["time"]) < 0.12 for ev in events):
            continue
            
        sect_cat = smoothed_classes[bp]
        if sect_cat == "QUIET":
            shell_types = [2, 5]  # Willow, Waterfall (delicate/quiet)
            palette = q_palette
        elif sect_cat == "MEDIUM":
            shell_types = [0, 1, 3, 4, 10, 18]  # Moderate shells
            palette = m_palette
        else:
            shell_types = [0, 2, 7, 8, 11, 12, 13]  # Full heavy shells
            palette = l_palette
            
        # Use stereo imaging for horizontal placement (x_offset)
        panning = get_panning(t_sec, fs, y_left, y_right)
        max_x = 9.0
        panned_x = panning * max_x
        rand_x = np.random.uniform(-max_x, max_x)
        x_offset = 0.8 * panned_x + 0.2 * rand_x
        
        # Use spectrum analysis to inform colors
        color = get_spectrum_color(t_sec, t, mag, bass_bins, mid_bins, high_bins, palette_override=palette)
        sec_color = get_spectrum_color(t_sec, t, mag, bass_bins, mid_bins, high_bins, palette_override=palette)
        
        events.append({
            "time": round(t_sec, 3),
            "type": "firework",
            "fw_type": int(np.random.choice(shell_types)),
            "color": color,
            "secondary_color": sec_color,
            "x_offset": float(x_offset)
        })
        
    # High peaks -> Crackling time rain, spiders, tourbillons, bees
    for hp in high_peaks:
        t_sec = float(t[hp])
        if t_sec > safety_cutoff or is_near_climax(t_sec):
            continue
        if any(abs(t_sec - ev["time"]) < 0.20 for ev in events):
            continue
            
        sect_cat = smoothed_classes[hp]
        if sect_cat == "QUIET":
            shell_types = [6, 14, 15, 17]  # Delicate highs: Swarm, Spider, Time Rain, Tourbillon
            palette = q_palette
        elif sect_cat == "MEDIUM":
            shell_types = [6, 15, 17]
            palette = m_palette
        else:
            shell_types = [6, 14, 15, 17]
            palette = l_palette
            
        # Use stereo imaging for horizontal placement (x_offset)
        panning = get_panning(t_sec, fs, y_left, y_right)
        max_x = 11.0
        panned_x = panning * max_x
        rand_x = np.random.uniform(-max_x, max_x)
        x_offset = 0.8 * panned_x + 0.2 * rand_x
        
        # Use spectrum analysis to inform colors
        color = get_spectrum_color(t_sec, t, mag, bass_bins, mid_bins, high_bins, palette_override=palette)
        sec_color = get_spectrum_color(t_sec, t, mag, bass_bins, mid_bins, high_bins, palette_override=palette)
        
        events.append({
            "time": round(t_sec, 3),
            "type": "firework",
            "fw_type": int(np.random.choice(shell_types)),
            "color": color,
            "secondary_color": sec_color,
            "x_offset": float(x_offset)
        })
        
    # Mid peaks -> Regular colorful peonies, ghost rings, pistils, farfalles
    for mp in mid_peaks:
        t_sec = float(t[mp])
        if t_sec > safety_cutoff or is_near_climax(t_sec):
            continue
        if any(abs(t_sec - ev["time"]) < 0.25 for ev in events):
            continue
            
        sect_cat = smoothed_classes[mp]
        if sect_cat == "QUIET":
            shell_types = [16]  # Farfalle (butterflies, extremely quiet & graceful)
            palette = q_palette
        elif sect_cat == "MEDIUM":
            shell_types = [1, 3, 9, 10, 16, 18]
            palette = m_palette
        else:
            shell_types = [1, 3, 4, 9, 10, 16, 18]
            palette = l_palette
            
        # Use stereo imaging for horizontal placement (x_offset)
        panning = get_panning(t_sec, fs, y_left, y_right)
        max_x = 10.0
        panned_x = panning * max_x
        rand_x = np.random.uniform(-max_x, max_x)
        x_offset = 0.8 * panned_x + 0.2 * rand_x
        
        # Use spectrum analysis to inform colors
        color = get_spectrum_color(t_sec, t, mag, bass_bins, mid_bins, high_bins, palette_override=palette)
        sec_color = get_spectrum_color(t_sec, t, mag, bass_bins, mid_bins, high_bins, palette_override=palette)
        
        events.append({
            "time": round(t_sec, 3),
            "type": "firework",
            "fw_type": int(np.random.choice(shell_types)),
            "color": color,
            "secondary_color": sec_color,
            "x_offset": float(x_offset)
        })
        
    # Sort events chronologically
    events.sort(key=lambda x: x["time"])
    
    script_data = {
        "metadata": {
            "music_file": mp3_path,
            "color_hints": color_hints if color_hints else [],
            "duration": round(duration, 2),
            "bpm": round(bpm, 1),
            "total_events": len(events)
        },
        "events": events
    }
    
    return script_data

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python audio_analyzer.py <input_mp3_path> <output_json_path> [--colors col1 col2 ...]")
        sys.exit(1)
        
    input_mp3 = sys.argv[1]
    output_json = sys.argv[2]
    
    colors_arg = None
    if "--colors" in sys.argv:
        color_idx = sys.argv.index("--colors")
        colors_arg = sys.argv[color_idx + 1:]
        
    try:
        script = analyze_audio(input_mp3, colors_arg)
        with open(output_json, 'w') as f:
            json.dump(script, f, indent=2)
        print(f"Successfully generated choreographed script at: {output_json}")
        print(f"Contains {len(script['events'])} synchronized launches.")
    except Exception as e:
        print(f"Choreography generation failed: {e}")
        sys.exit(1)
