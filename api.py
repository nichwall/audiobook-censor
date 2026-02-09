from fastapi import FastAPI, UploadFile, File, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import os
import glob
import shutil
import json
import uuid
from typing import List, Dict, Optional

from censor import AudiobookCensor
from jobs import JobManager

app = FastAPI()

# Allow CORS for local development and Docker internal traffic
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "http://127.0.0.1"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response

# Constants
INPUT_DIR = "input"
OUTPUT_DIR = "output"
TRANSCRIPT_DIR = "transcripts"
GLOBAL_BLOCKLIST = "blocklist.txt"
GLOBAL_ALLOWLIST = "allowlist.txt"
MAPPING_FILE = "file_mapping.json"
JOBS_FILE = "jobs.json"

censor_app = AudiobookCensor(INPUT_DIR, OUTPUT_DIR, TRANSCRIPT_DIR)
job_manager = JobManager(JOBS_FILE, censor_app, TRANSCRIPT_DIR, GLOBAL_BLOCKLIST, GLOBAL_ALLOWLIST)

def load_mapping():
    if os.path.exists(MAPPING_FILE):
        with open(MAPPING_FILE, "r") as f:
            return json.load(f)
    return {"path_to_id": {}, "id_to_path": {}}

def save_mapping(mapping):
    with open(MAPPING_FILE, "w") as f:
        json.dump(mapping, f, indent=2)

def get_file_path(file_id: str, mapping: dict):
    # Strict ID validation (UUID-ish)
    if not all(c in "0123456789abcdef- " for c in file_id.lower()):
         raise HTTPException(status_code=400, detail="Invalid character in file ID")

    path = mapping["id_to_path"].get(file_id)
    if not path:
        raise HTTPException(status_code=404, detail="Invalid file ID")
    
    # Path sanitization: ensure no directory traversal
    path = os.path.normpath(path)
    if path.startswith("..") or os.path.isabs(path):
        raise HTTPException(status_code=403, detail="Illegal path traversal attempt")

    full_path = os.path.abspath(os.path.join(INPUT_DIR, path))
    if not full_path.startswith(os.path.abspath(INPUT_DIR)):
         raise HTTPException(status_code=403, detail="Access denied")
    return path

class FileStatus(BaseModel):
    id: str
    filename: str
    duration: Optional[int] = 0
    transcribed: bool
    censored: bool
    is_out_of_date: bool = False
    est_transcribe_duration: int = 0
    est_censor_duration: int = 0

class OverrideUpdate(BaseModel):
    start_time: float
    allow: bool

class ListUpdate(BaseModel):
    content: str
    
import hashlib

def get_file_hash(path):
    if not os.path.exists(path):
        return ""
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()

def get_censor_metadata_path(base_no_ext):
    return os.path.join(TRANSCRIPT_DIR, base_no_ext + "_censor_meta.json")

@app.get("/api/files", response_model=List[FileStatus])
def list_files():
    mapping = load_mapping()
    path_to_id = mapping["path_to_id"]
    id_to_path = mapping["id_to_path"]
    
    files = []
    # Supporting mp3, opus, flac, wav, m4a
    extensions = ["*.mp3", "*.opus", "*.flac", "*.wav", "*.m4a"]
    audio_files = []
    
    # Recursive search
    for ext in extensions:
        pattern = os.path.join(INPUT_DIR, "**", ext)
        audio_files.extend(glob.glob(pattern, recursive=True))
    
    # Get current global config hashes
    current_block_hash = get_file_hash(GLOBAL_BLOCKLIST)
    current_allow_hash = get_file_hash(GLOBAL_ALLOWLIST)

    updated = False
    for fpath in audio_files:
        rel_path = os.path.relpath(fpath, INPUT_DIR)
        
        # Ensure UUID exists
        if rel_path not in path_to_id:
            new_id = str(uuid.uuid4())
            path_to_id[rel_path] = new_id
            id_to_path[new_id] = rel_path
            updated = True
        
        file_id = path_to_id[rel_path]
        base_no_ext = rel_path.rsplit(".", 1)[0]
        
        # Check transcript
        transcript_path = censor_app.transcript_path(base_no_ext)
        is_transcribed = os.path.exists(transcript_path)
        
        # Check output
        output_path = os.path.join(OUTPUT_DIR, base_no_ext + "_censored.opus")
        is_censored = os.path.exists(output_path)
        censored_at = os.path.getmtime(output_path) if is_censored else None
        
        # Check overrides hash
        overrides_path = os.path.join(TRANSCRIPT_DIR, base_no_ext + "_overrides.json")
        current_overrides_hash = get_file_hash(overrides_path)
            
        is_out_of_date = False
        if is_censored:
            meta_path = get_censor_metadata_path(base_no_ext)
            if os.path.exists(meta_path):
                with open(meta_path, "r") as f:
                    meta = json.load(f)
                if (meta.get("blocklist_hash") != current_block_hash or 
                    meta.get("allowlist_hash") != current_allow_hash or
                    meta.get("overrides_hash") != current_overrides_hash):
                    is_out_of_date = True
            else:
                # No metadata means we don't know, so assume it might be old (fallback to timestamp if needed, but let's encourage a re-run)
                is_out_of_date = True

        try:
             duration = censor_app.get_audio_duration(fpath)
        except:
             duration = 0

        files.append(FileStatus(
            id=file_id,
            filename=rel_path,
            duration=duration,
            transcribed=is_transcribed,
            censored=is_censored,
            is_out_of_date=is_out_of_date,
            est_transcribe_duration=int(duration * job_manager.get_factor("transcribe")),
            est_censor_duration=int(duration * job_manager.get_factor("censor"))
        ))
    
    if updated:
        save_mapping(mapping)
        
    files.sort(key=lambda x: x.filename)
    return files

@app.post("/api/files/{id}/transcribe")
def transcribe_file(id: str):
    mapping = load_mapping()
    filename = get_file_path(id, mapping)
    fpath = os.path.join(INPUT_DIR, filename)
    base_no_ext = filename.rsplit(".", 1)[0]
    
    try:
        duration = censor_app.get_audio_duration(fpath)
    except:
        duration = None
        
    success = job_manager.enqueue(id, filename, "transcribe", input_path=fpath, base_no_ext=base_no_ext, duration=int(duration or 0))
    if not success:
        raise HTTPException(status_code=429, detail="Server is currently busy with another task")
    return {"status": "success", "message": "Transcription started"}

@app.post("/api/files/{id}/workflow")
def run_full_workflow(id: str):
    mapping = load_mapping()
    filename = get_file_path(id, mapping)
    fpath = os.path.join(INPUT_DIR, filename)
    base_no_ext = filename.rsplit(".", 1)[0]
    output_file = os.path.join(OUTPUT_DIR, base_no_ext + "_censored.opus")
    
    try:
        duration = censor_app.get_audio_duration(fpath)
    except:
        duration = None
        
    success = job_manager.enqueue(id, filename, "full_workflow", input_path=fpath, output_path=output_file, base_no_ext=base_no_ext, duration=int(duration or 0))
    if not success:
        raise HTTPException(status_code=429, detail="Server is currently busy with another task")
    return {"status": "success", "message": "Full workflow started"}

@app.get("/api/files/{id}/transcript")
def get_transcript_for_ui(id: str):
    mapping = load_mapping()
    filename = get_file_path(id, mapping)
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
    final_intervals = censor_app.calculate_matches_with_cache(base_no_ext, GLOBAL_BLOCKLIST, GLOBAL_ALLOWLIST)
    final_intervals = censor_app.apply_overrides(final_intervals, overrides)
    
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
            "original_match": not is_allowed
        }
        
        if phrase_str not in response_groups:
            response_groups[phrase_str] = []
        response_groups[phrase_str].append(item)
        
    groups_list = []
    for phrase, items in response_groups.items():
        groups_list.append({
            "phrase": phrase,
            "count": len(items),
            "matches": items
        })
    groups_list.sort(key=lambda x: x["phrase"])
    return {"groups": groups_list}

@app.get("/api/files/{id}/search")
def search_words(id: str, q: str = ""):
    mapping = load_mapping()
    filename = get_file_path(id, mapping)
    base_no_ext = filename.rsplit(".", 1)[0]
    data = censor_app.calculate_vocab_with_cache(base_no_ext)
    if not data:
         raise HTTPException(status_code=404, detail="Transcription not found")
         
    q = q.strip().lower()
    if not q:
        return []
    query_words = q.split()
    if not query_words:
        return []
        
    index = data["index"]
    words_list = data["words"]
    first_q_word = query_words[0]
    
    if len(query_words) > 1:
        starter_words = [first_q_word] if first_q_word in index else []
    else:
        starter_words = [w for w in index.keys() if w.startswith(first_q_word)]
        
    results = []
    max_results = 500
    for starter_word in starter_words:
        if len(results) >= max_results: break
        for start_idx in index[starter_word]:
            if len(results) >= max_results: break
            if start_idx + len(query_words) > len(words_list): continue
                
            match = True
            actual_phrase = []
            for i in range(len(query_words)):
                q_word = query_words[i]
                a_word = words_list[start_idx + i]["word"]
                if i == len(query_words) - 1:
                    if not a_word.startswith(q_word):
                        match = False
                        break
                else:
                    if a_word != q_word:
                        match = False
                        break
                actual_phrase.append(a_word)
            
            if match:
                prefix_words = []
                if start_idx > 1: prefix_words.append(words_list[start_idx-2]["word"])
                if start_idx > 0: prefix_words.append(words_list[start_idx-1]["word"])
                suffix_words = []
                last_match_idx = start_idx + len(query_words) - 1
                if last_match_idx + 1 < len(words_list): suffix_words.append(words_list[last_match_idx+1]["word"])
                if last_match_idx + 2 < len(words_list): suffix_words.append(words_list[last_match_idx+2]["word"])
                results.append({
                    "start": words_list[start_idx]["start"],
                    "word": " ".join(actual_phrase),
                    "prefix": " ".join(prefix_words),
                    "suffix": " ".join(suffix_words)
                })
    return results

@app.post("/api/files/{id}/censor")
def censor_file(id: str):
    mapping = load_mapping()
    filename = get_file_path(id, mapping)
    fpath = os.path.join(INPUT_DIR, filename)
    base_no_ext = filename.rsplit(".", 1)[0]
    output_file = os.path.join(OUTPUT_DIR, base_no_ext + "_censored.opus")
    
    try:
        duration = censor_app.get_audio_duration(fpath)
    except:
        duration = None

    success = job_manager.enqueue(id, filename, "censor", input_path=fpath, output_path=output_file, base_no_ext=base_no_ext, duration=int(duration or 0))
    if not success:
        raise HTTPException(status_code=429, detail="Server is currently busy with another task")
    return {"status": "success", "message": "Censoring started"}

@app.get("/api/jobs/status")
def get_jobs_status():
    st = job_manager.get_status().copy()
    if st.get("current"):
        # Strip internal fields for the frontend
        public_fields = ["file_id", "filename", "type", "duration", "started_at"]
        clean_job = {k: v for k, v in st["current"].items() if k in public_fields}
        
        # Calculate estimate on the backend
        duration = clean_job.get("duration", 0)
        started_at = clean_job.get("started_at", 0)
        factor = job_manager.get_factor(clean_job["type"])
        clean_job["calculated_est_end_at"] = started_at + (duration * factor)
        
        st["current"] = clean_job
    return st

@app.post("/api/files/{id}/overrides/bulk")
def update_overrides_bulk(id: str, data: dict):
    mapping = load_mapping()
    filename = get_file_path(id, mapping)
    base_no_ext = filename.rsplit(".", 1)[0]
    overrides_path = os.path.join(TRANSCRIPT_DIR, base_no_ext + "_overrides.json")
    os.makedirs(os.path.dirname(overrides_path), exist_ok=True)
    overrides = {}
    if os.path.exists(overrides_path):
        with open(overrides_path, "r") as f:
            overrides = json.load(f)
    for item in data.get("overrides", []):
        overrides[str(item["start_time"])] = item["allow"]
    with open(overrides_path, "w") as f:
        json.dump(overrides, f)
    return {"status": "success"}

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

@app.post("/api/files/{id}/overrides")
def update_overrides(id: str, override: OverrideUpdate):
    mapping = load_mapping()
    filename = get_file_path(id, mapping)
    base_no_ext = filename.rsplit(".", 1)[0]
    overrides_path = os.path.join(TRANSCRIPT_DIR, base_no_ext + "_overrides.json")
    os.makedirs(os.path.dirname(overrides_path), exist_ok=True)
    overrides = {}
    if os.path.exists(overrides_path):
        with open(overrides_path, "r") as f:
            overrides = json.load(f)
    overrides[str(override.start_time)] = override.allow
    with open(overrides_path, "w") as f:
        json.dump(overrides, f, indent=2)
    return {"status": "success"}

def read_list_file(path):
    if not os.path.exists(path): return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def write_list_file(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
