# audiobook-censor

This is a simple Python script that transcribes audio files using vosk and then performs word level filtering, specifically for profanity. The Python scripts can be used manually or through the included web frontend.

This started out as a request from friends who wanted a vid-angel-like experience for audiobooks. I would run my scripts manually, and then wanted a nice web interface to simplify the process. I will not be providing online support for this repository, but may continue to update it as I notice small pain points.

This process is *not* 100% accurate and will not catch all words, but catches a lot of things.

FYI, the frontend was entirely written by AI, so use at your own risk. The original backend was also modified as a result of this to make it function better with the frontend.

## AI Disclaimer

This started out as a collection of scripts I wrote to perform this same task, but then vibe-coded a front end just to give myself pretty buttons. As I've found little changes I want to make, I have been using coding agents to do all of the work and I have not reviewed the code beyond a cursory inspection.

It does not include any authentication. I only use it through a read-only mount to my media files over my local network.

Use at your own risk.

## General usage

Put audio files into the `input/` folder. Once an audio file is transcribed, the transcription will stick around because the input audio file will not change. If you change the input file and keep it with the same name, you need to manually clear out the transcription logs in `transcripts/`. Masked (censored) files are written to `output/`.

Every time the allowlist or blocklist is updated, or any individual words are overridden, the "censored" status is cleared to indicate it needs to be ran again for the audio file.

This tool keeps track of the runtime of the most recent transcription and censor runs to better calculate "estimated time to perform this task". For example, my desktop transcribes at about 16x speed and masks the output file at about 40x speed, but this would be different for other hardware.
