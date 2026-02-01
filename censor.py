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
# Mask creation: generate FLAC with tone where profanity occurs
# ---------------------------------------------------------------------

def create_mask_audio(
    mask_flac_path,
    duration_sec,
    intervals,
    sample_rate=8000
):
    """
    Creates a FLAC mask audio file with tone during censor intervals
    and silence elsewhere.

    mask_flac_path : output .flac file
    duration_sec   : total duration of audio
    intervals      : list of (start, end) tuples in seconds
    sample_rate    : low rate is fine (default 8 kHz)
    """

    print(f"→ Creating mask audio (FLAC): {mask_flac_path}")

    import math
    import tempfile
    import os
    import struct
    import subprocess

    channels = 1
    sampwidth = 2  # 16-bit PCM
    amplitude = 28000
    frequency = 1000  # Hz

    num_samples = int(duration_sec * sample_rate)
    pcm_bytes = bytearray(num_samples * sampwidth)

    # Fill intervals with tone
    for start, end in intervals:
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
        os.remove(raw_path)

    print("→ Mask audio created.")

def apply_audio_mask(input_audio, mask_audio, output_audio):
    print(f"→ Combining {input_audio} and {mask_audio} into {output_audio} with ducking.")

    # Use sidechaincompress to duck the main audio

    # Convert to opus if output file is opus
    if (output_audio.lower().endswith(".opus")):
        run([
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
        run([
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

    input_audio_basename = os.path.basename(input_audio)
    input_audio_ext = input_audio_basename.rsplit(".", 1)[1]

    transcript = os.path.join("transcripts", input_audio_basename.rsplit(".", 1)[0] + "_timestamps.json")
    mask_flac = "mask.flac"
    #output_file = os.path.join(output_dir, input_audio_basename.rsplit(".", 1)[0] + "_censored." + input_audio_ext)
    output_file = os.path.join(output_dir, input_audio_basename.rsplit(".", 1)[0] + "_censored." + "opus")

    transcription_start_time = time.time()
    # First transcribe with whisper-cpp
    duration_sec = transcribe(input_audio, transcript)
    transcription_end_time = time.time()

    # Second, parse the JSON output to get word timestamps
    words = parse_json(transcript)

    # Third, figure out the when to mute based on the timestamps from gentle
    blocklist = load_blocklist(blocklist_file)

    # Compute mute intervals
    intervals = merge_intervals(determine_intervals(words, blocklist))

    print("\nMute intervals:")
    for s, e in intervals:
        print(f"  {s:.2f} → {e:.2f}")

    mask_create_start_time = time.time()
    # ️Build mask FLAC
    create_mask_audio(mask_flac, duration_sec, intervals)
    mask_create_end_time = time.time()

    mask_apply_start_time = time.time()
    apply_audio_mask(input_audio, mask_flac, output_file)
    mask_apply_end_time = time.time()

    print("\n🎉 Done! Output saved as:", output_file)

    print("\nTiming Summary:")
    print(f"  Transcription time:    {transcription_end_time - transcription_start_time:.2f} seconds")
    print(f"  Mask creation time:    {mask_create_end_time - mask_create_start_time:.2f} seconds")
    print(f"  Mask application time: {mask_apply_end_time - mask_apply_start_time:.2f} seconds")
    print()
    print(f"  Audiobook duration:    {duration_sec:.2f} seconds")
    print(f"  Total processing time: {mask_apply_end_time - transcription_start_time:.2f} seconds")


if __name__ == "__main__":
    main()

