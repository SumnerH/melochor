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

def analyze_audio(mp3_path, color_hints=None):
    """
    Decodes an MP3 file via ffmpeg and performs Short-Time Fourier Transform (STFT)
    to separate Low (Bass), Mid (Melody), and High (Treble) bands. Finds major peaks
    and maps them elegantly to choreographed firework launches and routines.
    """
    if not os.path.exists(mp3_path):
        raise FileNotFoundError(f"Audio file not found: {mp3_path}")
        
    print(f"Decoding {mp3_path} using FFmpeg subprocess stream...")
    
    # 1. Decode MP3 to raw float32 PCM mono at 22050 Hz via stdout pipe
    cmd = ['/home/sumner/bin/ffmpeg', '-y', '-i', mp3_path, '-f', 'f32le', '-ac', '1', '-ar', '22050', '-']
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = p.communicate()
    
    if p.returncode != 0:
        err_msg = stderr.decode('utf-8', errors='ignore')[-300:]
        raise RuntimeError(f"FFmpeg decoding failed: {err_msg}")
        
    y = np.frombuffer(stdout, dtype=np.float32)
    fs = 22050
    duration = len(y) / fs
    print(f"Decoded {len(y)} samples. Duration: {duration:.2f} seconds.")
    
    # 2. Short-Time Fourier Transform (STFT) analysis
    hop_length = 512
    n_fft = 1024
    
    # Calculate STFT matrix
    f, t, Zxx = scipy.signal.stft(y, fs=fs, nperseg=n_fft, noverlap=n_fft - hop_length)
    mag = np.abs(Zxx)  # Amplitude spectrum
    
    # 3. Extract Spectral Band Energy Envelopes
    # Bass / Kick band (20Hz - 180Hz)
    bass_bins = (f >= 20) & (f <= 180)
    # Mid / Vocal / Melodic band (200Hz - 2000Hz)
    mid_bins = (f >= 200) & (f <= 2000)
    # Treble / Hi-hat / Sparkle band (2000Hz - 8000Hz)
    high_bins = (f >= 2000) & (f <= 8000)
    
    bass_env = np.sum(mag[bass_bins, :], axis=0) if np.any(bass_bins) else np.zeros(mag.shape[1])
    mid_env = np.sum(mag[mid_bins, :], axis=0) if np.any(mid_bins) else np.zeros(mag.shape[1])
    high_env = np.sum(mag[high_bins, :], axis=0) if np.any(high_bins) else np.zeros(mag.shape[1])
    
    # 4. Compute Volume Profile (RMS envelope)
    # Compute chunk-wise RMS amplitude
    num_chunks = len(y) // hop_length
    truncated_y = y[:num_chunks * hop_length]
    rms = np.sqrt(np.mean(truncated_y.reshape(-1, hop_length)**2, axis=1))
    
    # Align time, envelopes, and RMS sizes
    min_len = min(len(t), len(rms))
    t = t[:min_len]
    bass_env = bass_env[:min_len]
    mid_env = mid_env[:min_len]
    high_env = high_env[:min_len]
    rms = rms[:min_len]
    
    # Normalize envelopes to [0.0, 1.0] for stable thresholding
    def norm(env):
        mx = np.max(env)
        return env / mx if mx > 0 else env
        
    bass_norm = norm(bass_env)
    mid_norm = norm(mid_env)
    high_norm = norm(high_env)
    rms_norm = norm(rms)
    
    # 5. Beat / Tempo Detection (BPM estimation)
    # Compute onset strength (derivative of normalized mid-band energy)
    onset_strength = np.diff(mid_norm)
    onset_strength = np.clip(onset_strength, 0, None)  # Half-wave rectify
    
    # Autocorrelation of onset strength for lags corresponding to 60-180 BPM
    fps_audio = fs / hop_length  # ~43.07 frames per second
    min_lag = int(fps_audio * 60 / 180)  # 180 BPM
    max_lag = int(fps_audio * 60 / 60)   # 60 BPM
    
    acf = np.correlate(onset_strength, onset_strength, mode='full')
    acf = acf[len(acf)//2:]  # Keep positive lags
    
    search_range = acf[min_lag:max_lag]
    best_lag_offset = np.argmax(search_range) if len(search_range) > 0 else 0
    best_lag = min_lag + best_lag_offset
    
    bpm = 60.0 * fps_audio / best_lag if best_lag > 0 else 120.0
    print(f"Estimated Track BPM: {bpm:.1f} (Optimal lag: {best_lag} frames)")
    
    # 6. Peak-Detection-Based Choreography Generation
    # Bass: Downbeats / Heavy Kicks (minimum distance of ~0.50s between shells)
    bass_peaks, _ = scipy.signal.find_peaks(bass_norm, height=0.40, distance=int(0.50 * fps_audio))
    
    # Highs: Sparkles / Crackles (minimum distance of ~0.35s between shells)
    high_peaks, _ = scipy.signal.find_peaks(high_norm, height=0.32, distance=int(0.35 * fps_audio))
    
    # Mids: Melodies / Snares (minimum distance of ~0.45s between shells)
    mid_peaks, _ = scipy.signal.find_peaks(mid_norm, height=0.42, distance=int(0.45 * fps_audio))
    
    # Climaxes: Major peaks in RMS volume to trigger Scheduled Choreographed Routines.
    # Spaced at least 15.0s apart to keep them special and distinct.
    climax_peaks, _ = scipy.signal.find_peaks(rms_norm, height=0.68, distance=int(15.0 * fps_audio))
    
    events = []
    
    # Set up artistic color hints
    palette = COLORS_KEYS
    if color_hints:
        valid_hints = [c for c in color_hints if c in COLORS_KEYS]
        if valid_hints:
            palette = valid_hints
            
    print(f"Applied Color Palette constraints: {palette}")
    
    # Trigger major choreographed routines at RMS climax peaks
    routines = ["American Flag", "Liberty Bell", "Statue of Liberty", "Flower Bouquet", "The Dragon"]
    routine_idx = 0
    climax_times = []
    
    for cp in climax_peaks:
        t_sec = float(t[cp])
        climax_times.append(t_sec)
        events.append({
            "time": round(t_sec, 3),
            "type": "routine",
            "name": routines[routine_idx % len(routines)]
        })
        routine_idx += 1
        
    def is_near_climax(t_sec):
        # Silence standard individual shells for 2.0s around high-production routines to avoid clutter
        for ct in climax_times:
            if abs(t_sec - ct) < 2.0:
                return True
        return False
        
    # Bass peaks -> Heavy ground breakers and large shells
    bass_shell_types = [0, 2, 7, 8, 11, 12, 13]  # Peony, Willow, Saturn, Crossette, Dahlia, Diadem, Palm
    for bp in bass_peaks:
        t_sec = float(t[bp])
        if is_near_climax(t_sec):
            continue
        # Avoid duplicate overlapping events on the exact same frame
        if any(abs(t_sec - ev["time"]) < 0.12 for ev in events):
            continue
            
        events.append({
            "time": round(t_sec, 3),
            "type": "firework",
            "fw_type": int(np.random.choice(bass_shell_types)),
            "color": str(np.random.choice(palette)),
            "secondary_color": str(np.random.choice(palette)),
            "x_offset": float(np.random.uniform(-9.0, 9.0))
        })
        
    # High peaks -> Crackling time rain, spiders, tourbillons, bees
    high_shell_types = [6, 14, 15, 17]  # Swarm/Bees, Spider, Time Rain, Tourbillon
    for hp in high_peaks:
        t_sec = float(t[hp])
        if is_near_climax(t_sec):
            continue
        if any(abs(t_sec - ev["time"]) < 0.20 for ev in events):
            continue
            
        events.append({
            "time": round(t_sec, 3),
            "type": "firework",
            "fw_type": int(np.random.choice(high_shell_types)),
            "color": str(np.random.choice(palette)),
            "secondary_color": str(np.random.choice(palette)),
            "x_offset": float(np.random.uniform(-11.0, 11.0))
        })
        
    # Mid peaks -> Regular colorful peonies, ghost rings, pistils, farfalles
    mid_shell_types = [1, 3, 4, 9, 10, 16, 18]  # Chrysanthemum, Ghost Ring, Pistil, Rainbow, Multi-Stage Ring, Farfalle, Break Ring
    for mp in mid_peaks:
        t_sec = float(t[mp])
        if is_near_climax(t_sec):
            continue
        if any(abs(t_sec - ev["time"]) < 0.25 for ev in events):
            continue
            
        events.append({
            "time": round(t_sec, 3),
            "type": "firework",
            "fw_type": int(np.random.choice(mid_shell_types)),
            "color": str(np.random.choice(palette)),
            "secondary_color": str(np.random.choice(palette)),
            "x_offset": float(np.random.uniform(-10.0, 10.0))
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
