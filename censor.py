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

def check_gentle():
    try:
        response = subprocess.check_output([
            "curl", "-s", "http://localhost:8765/transcriptions"
        ]).decode("utf-8").strip()
        if "html" not in response:
            print("→ Gentle server is not running. Start it by running `docker run --network=\"host\" -P lowerquality/gentle` in another terminal.")
            sys.exit(1)
    except subprocess.CalledProcessError:
        print("→ Gentle server is not running. Start it by running `docker run --network=\"host\" -P lowerquality/gentle` in another terminal.")
        sys.exit(1)

def parse_srt_timestamp(t):
    h, m, s = t.split(":")
    s, ms = s.split(",")
    return timedelta(
        hours=int(h), minutes=int(m), seconds=int(s), milliseconds=int(ms)
    ).total_seconds()

def load_blocklist(path):
    with open(path, "r", encoding="utf-8") as f:
        return {w.strip().lower() for w in f if w.strip()}

def parse_srt_words(path):
    words = []
    block = []

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if not line:
                if len(block) == 3:
                    _, timerange, text = block
                    start, end = timerange.split(" --> ")
                    words.append({
                        "word": text.lower(),
                        "start": parse_srt_timestamp(start),
                        "end": parse_srt_timestamp(end),
                    })
                block = []
            else:
                block.append(line)

    return words

def parse_gentle_csv(csv_path):
    """
    Returns list of dicts:
    [{ "word": str, "start": float, "end": float }, ...]
    """
    words = []

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) != 4:
                continue

            orig_word, detected_word, start, end = row

            if detected_word == "<unk>":
                continue

            try:
                words.append({
                    "word": orig_word.lower().strip(),
                    "start": float(start),
                    "end": float(end),
                })
            except ValueError:
                continue

    return words

def parse_gentle_json(json_path):
    import json

    words = []

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        for w in data.get("words", []):
            if not w.get("case") == "success":
                continue
            words.append({
                "word": w["word"].lower().strip(),
                "start": w["start"],
                "end": w["end"],
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

def transcribe_with_whisper(input, output_txt):
    startTime = time.time()
    print(f"→ Transcribing {input} with whisper-cpp…")

    # Check if this is a WAV file
    if (input.lower().endswith(".wav")):
        wav_input = input
    else:
        # Convert to WAV
        run([
            "ffmpeg", "-y",
            "-i", input,
            "-ar", "48000", "-ac", "1",
            "temp_transcribe_input.wav"
        ])
        wav_input = "temp_transcribe_input.wav"

    # Run transcription, output to text file
    run([
        "./build/bin/whisper-cli",
        "-np", # disable extra prints
        "-f", wav_input,
        #"-m", "models/ggml-medium.en.bin",
        "-m", "models/ggml-tiny.bin",
        "-otxt",
        "-of", output_txt
    ])

    # Return the length of the file for creation of silence mask
    probe = subprocess.check_output([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        wav_input
    ])

    print(f"→ Transcription completed in {time.time() - startTime:.2f} seconds.")

    return float(probe.strip())

def transcribe_with_gentle(input_wav, transcript_txt, output_json):
    startTime = time.time()
    print(f"→ Aligning with Gentle…")

    # Run gentle server and send request, and save JSON response to file
    run(["curl",
         "-F", f"audio=@{input_wav}",
         "-F", f"transcript=@{transcript_txt}",
         "http://localhost:8765/transcriptions?async=false",
         "-o", output_json])

    print(f"→ Gentle alignment completed in {time.time() - startTime:.2f} seconds.")

    return parse_gentle_json(output_json)

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

    # Precompute silence buffer
    silence_frame = struct.pack("<h", 0)

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
    run([
        "ffmpeg", "-y",
        "-hide_banner",
        "-loglevel", "warning",
        "-i", input_wav,
        "-i", mask_wav,
        "-filter_complex",
        "[0:a][1:a]sidechaincompress=threshold=0.001:ratio=20:attack=1:release=3[outa]",
        "-map", "[outa]",
        "combined_temp.wav"
    ])

    # Convert back to opus if original file was opus
    if (output_wav.lower().endswith(".opus")):
        run([
            "ffmpeg", "-y",
            "-hide_banner",
            "-loglevel", "warning",
            "-i", "combined_temp.wav",
            "-c:a", "libopus",
            "-b:a", "32k",
            "-compression_level", "10",
            "-frame_duration", "60",
            "-application", "voip",
            "-ac", "1",
            output_wav
        ])
    else:
        os.rename("combined_temp.wav", output_wav)

    print("→ Combined audio created.")

# ---------------------------------------------------------------------
# MAIN PIPELINE
# ---------------------------------------------------------------------

def main():
    if len(sys.argv) < 4:
        print("Usage: python3 censor_with_mask.py <input_audio> <blocklist.txt> <output_audio>")
        sys.exit(1)

    check_gentle()

    input_audio = sys.argv[1]
    blocklist_file = sys.argv[2]
    output_audio = sys.argv[3]

    transcript = "timestamps"
    aligned_csv = "align.csv"
    mask_wav = "mask.wav"

    # First transcribe with whisper-cpp
    duration_sec = transcribe_with_whisper(input_audio, transcript)

    # Then, use the input audio and transcript to create timestamps with gentle
    words = transcribe_with_gentle(input_audio, transcript + ".txt", "gentle_output.json")

    # Third, figure out the when to mute based on the timestamps from gentle
    blocklist = load_blocklist(blocklist_file)
    #words = parse_gentle_csv(aligned_csv)

    # Compute mute intervals
    intervals = merge_intervals(determine_intervals(words, blocklist))

    print("\nMute intervals:")
    for s, e in intervals:
        print(f"  {s:.2f} → {e:.2f}")

    # ️Build mask WAV
    create_mask_wav(mask_wav, duration_sec, intervals)

    combine_mask_wav(input_audio, mask_wav, output_audio)

    print("\n🎉 Done! Output saved as:", output_audio)


if __name__ == "__main__":
    main()

