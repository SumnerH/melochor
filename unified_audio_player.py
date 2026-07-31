import os
import sys
import time
import subprocess
import threading
import shutil

class UnifiedAudioPlayer:
    def __init__(self):
        import threading
        self.mpv_process = None
        self.player_type = None # 'mpv' or 'sounddevice'
        self.start_time = 0.0
        self.audio_path = None
        self.sd_playing = False
        self.sd_duration = 0.0
        
        self.sd_stream = None
        self.sd_data = None
        self.sd_fs = 0
        self.sd_current_frame = 0
        self.sd_lock = threading.Lock()
        
    def play(self, filepath):
        self.stop()
        self.audio_path = filepath
        
        # 1. Try playing with MPV
        import shutil
        has_mpv = shutil.which("mpv") or os.path.exists("/usr/bin/mpv")
        if has_mpv:
            try:
                cmd = ["mpv" if shutil.which("mpv") else "/usr/bin/mpv", "--no-video", "--volume=100", filepath]
                creationflags = 0x08000000 if sys.platform == 'win32' else 0
                self.mpv_process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creationflags)
                self.player_type = 'mpv'
                self.start_time = time.time()
                print(f"Started playback of {filepath} using MPV subprocess.")
                return True
            except Exception as e:
                print(f"Failed to start mpv playback, falling back to sounddevice: {e}")
                
        # 2. Fall back to sounddevice + soundfile/audioread
        try:
            print(f"Decoding {filepath} for sounddevice playback...")
            import audio_analyzer
            data, fs = audio_analyzer.decode_audio(filepath)
            
            import sounddevice as sd
            
            with self.sd_lock:
                self.sd_data = data
                self.sd_fs = fs
                self.sd_current_frame = 0
                self.sd_duration = len(data) / fs
                
                # Ensure the data shape is 2D (num_frames, channels)
                if self.sd_data.ndim == 1:
                    self.sd_data = self.sd_data[:, np.newaxis]
                channels = self.sd_data.shape[1]
                
                def callback(outdata, frames, time_info, status):
                    if status:
                        pass
                    
                    # Compute remaining frames
                    rem = len(self.sd_data) - self.sd_current_frame
                    if rem <= 0:
                        outdata.fill(0)
                        raise sd.CallbackStop()
                        
                    chunk_size = min(frames, rem)
                    # Fill the output buffer
                    outdata[:chunk_size] = self.sd_data[self.sd_current_frame:self.sd_current_frame + chunk_size]
                    if chunk_size < frames:
                        outdata[chunk_size:].fill(0)
                        
                    self.sd_current_frame += chunk_size
                    
                    if self.sd_current_frame >= len(self.sd_data):
                        raise sd.CallbackStop()
                
                # Create and start the stream
                self.sd_stream = sd.OutputStream(
                    samplerate=fs,
                    channels=channels,
                    dtype='float32',
                    callback=callback
                )
                self.sd_stream.start()
                
                self.player_type = 'sounddevice'
                self.start_time = time.time()
                self.sd_playing = True
                
            print(f"Started playback of {filepath} using sounddevice backend with frame-counting callback.")
            return True
        except Exception as e:
            print(f"Failed to play audio with sounddevice: {e}")
            return False
            
    def stop(self):
        if self.player_type == 'mpv':
            if self.mpv_process:
                try:
                    self.mpv_process.terminate()
                    self.mpv_process.wait(timeout=1.0)
                except Exception:
                    try:
                        self.mpv_process.kill()
                    except Exception:
                        pass
                self.mpv_process = None
        elif self.player_type == 'sounddevice':
            with self.sd_lock:
                if self.sd_stream:
                    try:
                        self.sd_stream.stop()
                        self.sd_stream.close()
                    except Exception:
                        pass
                    self.sd_stream = None
                self.sd_playing = False
                self.sd_data = None
                self.sd_current_frame = 0
                self.sd_fs = 0
        self.player_type = None
        self.start_time = 0.0
        
    def is_playing(self):
        if self.player_type == 'mpv':
            return self.mpv_process is not None and self.mpv_process.poll() is None
        elif self.player_type == 'sounddevice':
            with self.sd_lock:
                if self.sd_stream and self.sd_stream.active:
                    return True
                self.sd_playing = False
                return False
        return False

    def get_elapsed_time(self):
        if self.player_type == 'mpv' and self.start_time > 0.0:
            return time.time() - self.start_time
        elif self.player_type == 'sounddevice':
            if self.sd_fs > 0:
                return self.sd_current_frame / self.sd_fs
            return 0.0
        return 0.0
