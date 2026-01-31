#!/usr/bin/env python3
import os
import struct
import subprocess
import wave
import sys
import csv
import time

from datetime import timedelta

# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def run(cmd):
    print("→", " ".join(cmd))
    subprocess.run(cmd, check=True)

def load_blocklist(path):
    with open(path, "r", encoding="utf-8") as f:
        return {w.strip().lower() for w in f if w.strip()}

def parse_json(json_path):
    import json

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


def determine_intervals(words, blocklist, padding=0.03):
    intervals = []
    for w in words:
        if w["word"] in blocklist:
            start = max(0, w["start"] - padding)
            end = w["end"] + padding
            intervals.append((start, end))
    intervals.sort()
    return intervals

def merge_intervals(intervals):
    if not intervals:
        return []

    merged = [list(intervals[0])]
    for start, end in intervals[1:]:
        if start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return merged

def transcribe(input, output_json):
    startTime = time.time()
    print(f"→ Transcribing {input} with vosk...")

    run([
        "vosk-transcriber", "-i", input, "-t", "json", "-o", output_json
    ])

    # Return the length of the file for creation of silence mask
    probe = subprocess.check_output([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        input
    ])

    print(f"→ Transcription completed in {time.time() - startTime:.2f} seconds.")

    return float(probe.strip())

# ---------------------------------------------------------------------
# Mask creation: generate WAV with tone where profanity occurs
# ---------------------------------------------------------------------

def create_mask_wav(mask_path, duration_sec, intervals, sample_rate=16000):
    print(f"→ Creating mask WAV: {mask_path}")

    # PCM parameters
    channels = 1
    sampwidth = 2  # 16-bit PCM
    num_samples = int(duration_sec * sample_rate)

    # Tone parameters (this doesn't matter much — it's never heard)
    amplitude = 30000  # loud enough to trigger compressor
    frequency = 1000   # 1 kHz tone

    with wave.open(mask_path, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sampwidth)
        wf.setframerate(sample_rate)

        # Create a list for fast writing
        mask_bytes = bytearray(num_samples * sampwidth)

        # Fill intervals with tone
        import math
        
        for start, end in intervals:
            s_idx = int(start * sample_rate)
            e_idx = int(end * sample_rate)
            e_idx = min(e_idx, num_samples)

            for i in range(s_idx, e_idx):
                t = i / sample_rate
                value = int(amplitude * math.sin(2 * math.pi * frequency * t))
                struct.pack_into("<h", mask_bytes, i * sampwidth, value)

        wf.writeframes(mask_bytes)

    print("→ Mask track created.")

def combine_mask_wav(input_wav, mask_wav, output_wav):
    print(f"→ Combining {input_wav} and {mask_wav} into {output_wav} with ducking.")

    # Use sidechaincompress to duck the main audio

    # Convert back to opus if original file was opus
    if (output_wav.lower().endswith(".opus")):
        run([
            "ffmpeg", "-y",
            "-hide_banner",
            "-loglevel", "warning",
            "-i", input_wav,
            "-i", mask_wav,
            "-filter_complex",
            "[0:a][1:a]sidechaincompress=threshold=0.001:ratio=20:attack=1:release=3[outa]",
            "-map", "[outa]",
            "-c:a", "libopus",
            "-b:a", "32k",
            "-compression_level", "10",
            "-frame_duration", "60",
            "-application", "voip",
            "-ac", "1",
            output_wav
        ])
    else:
        run([
            "ffmpeg", "-y",
            "-hide_banner",
            "-loglevel", "warning",
            "-i", input_wav,
            "-i", mask_wav,
            "-filter_complex",
            "[0:a][1:a]sidechaincompress=threshold=0.001:ratio=20:attack=1:release=3[outa]",
            "-map", "[outa]",
            output_wav
        ])

    print("→ Combined audio created.")

# ---------------------------------------------------------------------
# MAIN PIPELINE
# ---------------------------------------------------------------------

def main():
    if len(sys.argv) < 4:
        print("Usage: python3 censor.py <input_audio> <blocklist.txt> <output_dir>")
        sys.exit(1)

    input_audio = sys.argv[1]
    blocklist_file = sys.argv[2]
    output_dir = sys.argv[3]

    transcript = "timestamps.json"
    mask_wav = "mask.wav"
    output_file = os.path.join(output_dir, os.path.basename(input_audio).rsplit(".", 1)[0] + "_censored." + input_audio.rsplit(".", 1)[1])

    # First transcribe with whisper-cpp
    duration_sec = transcribe(input_audio, transcript)

    # Second, parse the JSON output to get word timestamps
    words = parse_json(transcript)

    # Third, figure out the when to mute based on the timestamps from gentle
    blocklist = load_blocklist(blocklist_file)

    # Compute mute intervals
    intervals = merge_intervals(determine_intervals(words, blocklist))

    print("\nMute intervals:")
    for s, e in intervals:
        print(f"  {s:.2f} → {e:.2f}")

    # ️Build mask WAV
    create_mask_wav(mask_wav, duration_sec, intervals)

    combine_mask_wav(input_audio, mask_wav, output_file)

    print("\n🎉 Done! Output saved as:", output_file)


if __name__ == "__main__":
    main()

