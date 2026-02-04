#!/usr/bin/env python3
import os
import struct
import subprocess
import wave
import sys
import csv
import time
import json
import math
import tempfile
from datetime import timedelta

# ---------------------------------------------------------------------
# AudiobookCensor Class
# ---------------------------------------------------------------------

class AudiobookCensor:
    def __init__(self, input_dir="input", output_dir="output", transcript_dir="transcripts"):
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.transcript_dir = transcript_dir
        
        os.makedirs(self.input_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.transcript_dir, exist_ok=True)

    def run_cmd(self, cmd):
        print("→", " ".join(cmd))
        subprocess.run(cmd, check=True)

    def load_list(self, path):
        if not os.path.exists(path):
            return set()
        with open(path, "r", encoding="utf-8") as f:
            return {w.strip().lower() for w in f if w.strip()}

    def parse_json(self, json_path):
        words = []
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            for monologue in data.get("monologues", []):
                for term in monologue.get("terms", []):
                    if (term["type"] == "WORD"):
                        words.append({
                            "word": term["text"].lower().strip(),
                            "start": term["start"],
                            "end": term["end"],
                        })
        return words

    def determine_intervals(self, words, blocklist, padding=0.03):
        intervals = []
        
        # Build a sequence of word texts for phrase matching
        word_sequence = [w["word"] for w in words]
        
        for i, _ in enumerate(words):
            # Check all phrases in blocklist
            for phrase in blocklist:
                phrase_words = phrase.split()
                phrase_len = len(phrase_words)
                
                # Check if phrase matches starting at position i
                if i + phrase_len <= len(word_sequence):
                    previous_words = word_sequence[i-3:i] if i >= 3 else word_sequence[0:i]
                    after_words = word_sequence[i+phrase_len:i+phrase_len+3] if i + phrase_len + 3 <= len(word_sequence) else word_sequence[i+phrase_len:len(word_sequence)]

                    if word_sequence[i:i+phrase_len] == phrase_words:
                        # Found a match, compute interval from first to last word
                        start = max(0, words[i]["start"] - padding)
                        end = words[i + phrase_len - 1]["end"] + padding
                        intervals.append((start, end, phrase_words, previous_words, after_words))
                        break  # Don't add multiple intervals for same word
        
        intervals.sort()
        return intervals

    def apply_whitelist(self, blocked_intervals, allowed_intervals):
        final_intervals = []
        for b_start, b_end, phrase_words, previous_words, after_words in blocked_intervals:
            overlap = False
            for a_start, a_end, a_phrase, a_prev, a_after in allowed_intervals:
                if not (b_end < a_start or b_start > a_end):
                    overlap = True
                    final_intervals.append((b_start, b_end, True, a_phrase, a_prev, a_after))
                    break
            
            if not overlap:
                final_intervals.append((b_start, b_end, False, phrase_words, previous_words, after_words))

        return final_intervals
    
    def apply_overrides(self, intervals, overrides):
        """
        overrides: dict mapping "start_time" (str/float) to boolean (True=Allow, False=Block)
        """
        updated_intervals = []
        for start, end, is_allowed, phrase, prev, after in intervals:
            matched_override = None
            for o_start, action in overrides.items():
                if abs(float(o_start) - start) < 0.01:
                    matched_override = action
                    break
            
            if matched_override is not None:
                updated_intervals.append((start, end, matched_override, phrase, prev, after))
            else:
                updated_intervals.append((start, end, is_allowed, phrase, prev, after))
                
        return updated_intervals

    def get_audio_duration(self, filename):
        probe = subprocess.check_output([
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            filename
        ])
        return float(probe.strip())

    def transcript_path(self, basename):
         return os.path.join(self.transcript_dir, basename + "_timestamps.json")

    def matches_path(self, basename):
         return os.path.join(self.transcript_dir, basename + "_matches.json")

    def calculate_matches_with_cache(self, basename_no_ext, blocklist_path, allowlist_path):
        transcript_path = self.transcript_path(basename_no_ext)
        matches_path = self.matches_path(basename_no_ext)
        
        # Check if cache is valid
        is_cache_valid = False
        if os.path.exists(matches_path) and os.path.exists(transcript_path):
            t_mtime = os.path.getmtime(transcript_path)
            b_mtime = os.path.getmtime(blocklist_path) if os.path.exists(blocklist_path) else 0
            a_mtime = os.path.getmtime(allowlist_path) if os.path.exists(allowlist_path) else 0
            m_mtime = os.path.getmtime(matches_path)
            
            if m_mtime > t_mtime and m_mtime > b_mtime and m_mtime > a_mtime:
                is_cache_valid = True
                
        if is_cache_valid:
            try:
                with open(matches_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data
            except:
                pass # Fallback to recompute
        
        # Recompute
        if not os.path.exists(transcript_path):
             return []

        words = self.parse_json(transcript_path)
        blocklist = self.load_list(blocklist_path)
        whitelist = self.load_list(allowlist_path)

        raw_block = self.determine_intervals(words, blocklist)
        raw_allow = self.determine_intervals(words, whitelist)

        final_intervals = self.apply_whitelist(raw_block, raw_allow)
        
        # Save to cache
        with open(matches_path, "w", encoding="utf-8") as f:
            json.dump(final_intervals, f, indent=1)
            
        return final_intervals

    def transcribe(self, input_path):
        basename = os.path.basename(input_path).rsplit(".", 1)[0]
        output_json = self.transcript_path(basename)
        
        startTime = time.time()
        print(f"→ Transcribing {input_path} with vosk...")

        self.run_cmd([
            "vosk-transcriber", "-i", input_path, "-t", "json", "-o", output_json
        ])

        self.cleanup_transcript(output_json)

        print(f"→ Transcription completed in {time.time() - startTime:.2f} seconds.")
        return output_json

    def cleanup_transcript(self, filename):
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)

        data.pop("text", None)
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=1)

    def create_mask_audio(self, mask_flac_path, duration_sec, intervals, sample_rate=8000):
        print(f"→ Creating mask audio (FLAC): {mask_flac_path}")

        channels = 1
        sampwidth = 2  # 16-bit PCM
        amplitude = 28000
        frequency = 1000  # Hz

        num_samples = int(duration_sec * sample_rate)
        pcm_bytes = bytearray(num_samples * sampwidth)

        # Fill intervals with tone
        for start, end, is_allowed, *_ in intervals:
            if not is_allowed:
                s_idx = int(start * sample_rate)
                e_idx = int(end * sample_rate)
                e_idx = min(e_idx, num_samples)

                for i in range(s_idx, e_idx):
                    t = i / sample_rate
                    value = int(amplitude * math.sin(2 * math.pi * frequency * t))
                    struct.pack_into("<h", pcm_bytes, i * sampwidth, value)

        # Write raw PCM to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".raw") as raw:
            raw.write(pcm_bytes)
            raw_path = raw.name

        try:
            # Encode to FLAC
            subprocess.run([
                "ffmpeg", "-y",
                "-hide_banner",
                "-loglevel", "warning",
                "-f", "s16le",
                "-ar", str(sample_rate),
                "-ac", str(channels),
                "-i", raw_path,
                "-c:a", "flac",
                "-compression_level", "8",
                mask_flac_path
            ], check=True)
        finally:
            if os.path.exists(raw_path):
                os.remove(raw_path)

        print("→ Mask audio created.")

    def apply_audio_mask(self, input_audio, mask_audio, output_audio):
        print(f"→ Combining {input_audio} and {mask_audio} into {output_audio} with ducking.")

        # Use sidechaincompress to duck the main audio

        # Convert to opus if output file is opus
        if (output_audio.lower().endswith(".opus")):
            self.run_cmd([
                "ffmpeg", "-y",
                "-hide_banner",
                "-loglevel", "warning",
                "-i", input_audio,
                "-i", mask_audio,
                "-filter_complex",
                "[0:a][1:a]sidechaincompress=threshold=0.001:ratio=20:attack=1:release=3[outa]",
                "-map", "[outa]",
                "-c:a", "libopus",
                "-b:a", "32k",
                "-compression_level", "10",
                "-frame_duration", "60",
                "-application", "voip",
                "-ac", "1",
                output_audio
            ])
        else:
            self.run_cmd([
                "ffmpeg", "-y",
                "-hide_banner",
                "-loglevel", "warning",
                "-i", input_audio,
                "-i", mask_audio,
                "-filter_complex",
                "[0:a][1:a]sidechaincompress=threshold=0.001:ratio=20:attack=1:release=3[outa]",
                "-map", "[outa]",
                output_audio
            ])

        print("→ Combined audio created.")

    def censor(self, input_audio, blocklist_path, allowlist_path="allowlist.txt", overrides=None):
        if overrides is None:
            overrides = {}

        input_audio_basename = os.path.basename(input_audio)
        basename_no_ext = input_audio_basename.rsplit(".", 1)[0]
        
        transcript = self.transcript_path(basename_no_ext)
        output_file = os.path.join(self.output_dir, basename_no_ext + "_censored.opus")
        mask_flac = "mask.flac" # Keep temporary mask in current dir or move to temp

        # Check for transcript
        if not os.path.exists(transcript):
            self.transcribe(input_audio)
        
        duration_sec = self.get_audio_duration(input_audio)
        
        final_intervals = self.calculate_matches_with_cache(basename_no_ext, blocklist_path, allowlist_path)
        
        # Apply overrides
        final_intervals = self.apply_overrides(final_intervals, overrides)

        print("\nMute intervals:")
        for s, e, is_good, phrase_words, previous_words, after_words in final_intervals:
            RED = "\033[91m"
            GREEN = "\033[92m"
            RESET = "\033[0m"
            if is_good:
                print(f"  {s:.2f} → {e:.2f} : {' '.join(previous_words)} {GREEN}{' '.join(phrase_words)}{RESET} {' '.join(after_words)}")
            else:
                print(f"  {s:.2f} → {e:.2f} : {' '.join(previous_words)} {RED}{' '.join(phrase_words)}{RESET} {' '.join(after_words)}")

        self.create_mask_audio(mask_flac, duration_sec, final_intervals)
        self.apply_audio_mask(input_audio, mask_flac, output_file)
        
        if os.path.exists(mask_flac):
            os.remove(mask_flac)
            
        return output_file


# ---------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------

def main():
    if len(sys.argv) < 4:
        print("Usage: python3 censor.py <input_audio> <blocklist.txt> <output_dir>")
        sys.exit(1)

    input_audio = sys.argv[1]
    blocklist_file = sys.argv[2]
    output_dir = sys.argv[3]
    
    # Existing script expected inputs to be paths.
    # We will assume input_audio is a path.
    # If the user ran from current dir, they might pass inputs relative to CWD.
    
    # We institute the Censor class
    # For CLI use, we might default the internal dirs to where the script is or just use the passed args.
    # The original script put transcripts in "transcripts/".
    
    app = AudiobookCensor(
        input_dir=os.path.dirname(input_audio) if os.path.dirname(input_audio) else ".",
        output_dir=output_dir,
        transcript_dir="transcripts"
    )
    
    app.censor(input_audio, blocklist_file)

if __name__ == "__main__":
    main()

