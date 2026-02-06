from fastapi import FastAPI, UploadFile, File, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import os
import glob
import shutil
import json
from typing import List, Dict, Optional

from censor import AudiobookCensor

app = FastAPI()

# Allow CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Constants
INPUT_DIR = "input"
OUTPUT_DIR = "output"
TRANSCRIPT_DIR = "transcripts"
GLOBAL_BLOCKLIST = "blocklist.txt"
GLOBAL_ALLOWLIST = "allowlist.txt"

censor_app = AudiobookCensor(INPUT_DIR, OUTPUT_DIR, TRANSCRIPT_DIR)

class FileStatus(BaseModel):
    filename: str
    size_bytes: int
    duration: Optional[float] = None
    transcribed: bool
    censored: bool
    censored_at: Optional[float] = None # Timestamp
    is_out_of_date: bool = False

class OverrideUpdate(BaseModel):
    start_time: float
    allow: bool

class ListUpdate(BaseModel):
    content: str
    
@app.get("/api/files", response_model=List[FileStatus])
def list_files():
    files = []
    # Supporting mp3, opus, flac, wav
    extensions = ["*.mp3", "*.opus", "*.flac", "*.wav", "*.m4a"]
    audio_files = []
    for ext in extensions:
        audio_files.extend(glob.glob(os.path.join(INPUT_DIR, ext)))
    
    # Get global config mtimes
    global_mtime = 0
    if os.path.exists(GLOBAL_BLOCKLIST):
        global_mtime = max(global_mtime, os.path.getmtime(GLOBAL_BLOCKLIST))
    if os.path.exists(GLOBAL_ALLOWLIST):
        global_mtime = max(global_mtime, os.path.getmtime(GLOBAL_ALLOWLIST))

    for fpath in audio_files:
        basename = os.path.basename(fpath)
        base_no_ext = basename.rsplit(".", 1)[0]
        
        # Check transcript
        transcript_path = censor_app.transcript_path(base_no_ext)
        is_transcribed = os.path.exists(transcript_path)
        
        # Check output
        # censor.py outputs to .opus by default now
        output_path = os.path.join(OUTPUT_DIR, base_no_ext + "_censored.opus")
        is_censored = os.path.exists(output_path)
        censored_at = os.path.getmtime(output_path) if is_censored else None
        
        # Check overrides
        overrides_path = os.path.join(TRANSCRIPT_DIR, base_no_ext + "_overrides.json")
        overrides_mtime = 0
        if os.path.exists(overrides_path):
            overrides_mtime = os.path.getmtime(overrides_path)
            
        is_out_of_date = False
        if is_censored:
            # If configuration changed AFTER censoring
            last_config_change = max(global_mtime, overrides_mtime)
            if censored_at < last_config_change:
                is_out_of_date = True

        try:
            duration = censor_app.get_audio_duration(fpath)
        except:
            duration = None

        files.append(FileStatus(
            filename=basename,
            size_bytes=os.path.getsize(fpath),
            duration=duration,
            transcribed=is_transcribed,
            censored=is_censored,
            censored_at=censored_at,
            is_out_of_date=is_out_of_date
        ))
    
    # Sort by filename
    files.sort(key=lambda x: x.filename)
    return files

@app.post("/api/files/{filename}/transcribe")
def transcribe_file(filename: str):
    fpath = os.path.join(INPUT_DIR, filename)
    if not os.path.exists(fpath):
        raise HTTPException(status_code=404, detail="File not found")
    
    # Run in background ideally, but for now blocking is fine as per instructions (simple API)
    censor_app.transcribe(fpath)
    return {"status": "success", "message": "Transcription complete"}

@app.get("/api/files/{filename}/transcript")
def get_transcript_for_ui(filename: str):
    """
    Returns the transcript words + whether they are blocked or allowed based on current rules.
    This helps the UI visualize what is being filtered.
    """
    base_no_ext = filename.rsplit(".", 1)[0]
    transcript_path = censor_app.transcript_path(base_no_ext)
    
    if not os.path.exists(transcript_path):
         raise HTTPException(status_code=404, detail="Transcription not found")
         
    # Overrides
    overrides_path = os.path.join(TRANSCRIPT_DIR, base_no_ext + "_overrides.json")
    overrides = {}
    if os.path.exists(overrides_path):
        with open(overrides_path, "r") as f:
            overrides = json.load(f)

    # Calculate intervals to know what is blocked
    # This logic matches censor.py exactly and uses caching
    final_intervals = censor_app.calculate_matches_with_cache(base_no_ext, GLOBAL_BLOCKLIST, GLOBAL_ALLOWLIST)
    
    final_intervals = censor_app.apply_overrides(final_intervals, overrides)
    
    # We want to map this back to "ranges" for the UI.
    # The UI wants a list of "FilterAction" items.
    # We will return the list of intervals suitable for display.
    
    response_groups = {}
    
    for s, e, is_allowed, phrase, prev, after in final_intervals:
        phrase_str = " ".join(phrase)
        item = {
            "start": s,
            "end": e,
            "is_allowed": is_allowed,
            "phrase": phrase_str,
            "prefix": " ".join(prev),
            "suffix": " ".join(after),
            "context": " ".join(prev) + " " + phrase_str + " " + " ".join(after),
            "original_match": not is_allowed # Initially blocked by blocklist
        }
        
        if phrase_str not in response_groups:
            response_groups[phrase_str] = []
        response_groups[phrase_str].append(item)
        
    # Convert to list
    groups_list = []
    for phrase, items in response_groups.items():
        groups_list.append({
            "phrase": phrase,
            "count": len(items),
            "matches": items
        })
    groups_list.sort(key=lambda x: x["phrase"])
        
    return {"groups": groups_list}

@app.post("/api/files/{filename}/censor")
def censor_file(filename: str):
    fpath = os.path.join(INPUT_DIR, filename)
    if not os.path.exists(fpath):
        raise HTTPException(status_code=404, detail="File not found")
        
    base_no_ext = filename.rsplit(".", 1)[0]
    overrides_path = os.path.join(TRANSCRIPT_DIR, base_no_ext + "_overrides.json")
    overrides = {}
    if os.path.exists(overrides_path):
        with open(overrides_path, "r") as f:
            overrides = json.load(f)

    # Clean overrides keys to strict strings? JSON load does that.
    # The censor function expects start time as key (which we fuzzy match? No we fuzzy match in updated code).
    
    censor_app.censor(fpath, GLOBAL_BLOCKLIST, GLOBAL_ALLOWLIST, overrides)
    return {"status": "success", "message": "Censoring complete"}

@app.get("/api/config/global")
def get_global_config():
    return {
        "blocklist": read_list_file(GLOBAL_BLOCKLIST),
        "allowlist": read_list_file(GLOBAL_ALLOWLIST)
    }

@app.post("/api/config/global")
def update_global_config(config: dict = Body(...)):
    if "blocklist" in config:
        write_list_file(GLOBAL_BLOCKLIST, config["blocklist"])
    if "allowlist" in config:
        write_list_file(GLOBAL_ALLOWLIST, config["allowlist"])
    return {"status": "success"}

@app.post("/api/files/{filename}/overrides")
def update_overrides(filename: str, override: OverrideUpdate):
    base_no_ext = filename.rsplit(".", 1)[0]
    overrides_path = os.path.join(TRANSCRIPT_DIR, base_no_ext + "_overrides.json")
    
    overrides = {}
    if os.path.exists(overrides_path):
        with open(overrides_path, "r") as f:
            overrides = json.load(f)
            
    # Key is string representation of float
    key = str(override.start_time)
    overrides[key] = override.allow
    
    with open(overrides_path, "w") as f:
        json.dump(overrides, f, indent=2)
        
    return {"status": "success"}

def read_list_file(path):
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def write_list_file(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
