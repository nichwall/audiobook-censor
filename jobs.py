import hashlib
import json
import os
import threading
import time
from typing import Dict, List, Optional

from file_mapping import update_file_metadata

import notifications

_lock = threading.RLock()
_censor_app = None
_transcript_dir = ""
_global_blocklist = ""
_global_allowlist = ""
_current_job: Optional[Dict] = None
_next_job: Optional[Dict] = None
_worker_started = False
_stats_file: Optional[str] = None

_default_factors: Dict[str, Dict[str, float]] = {
    "transcribe": {"default": 0.08},
    "censor": {"default": 0.03},
    "full_workflow": {"default": 0.11}
}
_stats: Dict[str, Dict[str, List[float]]] = {
    "transcribe": {},
    "censor": {},
    "full_workflow": {}
}


def _load_stats() -> None:
    if not _stats_file:
        return
    try:
        if os.path.exists(_stats_file):
            with open(_stats_file, "r") as f:
                data = json.load(f)
            for job_type, buckets in data.items():
                if job_type not in _stats:
                    _stats[job_type] = {}
                for ext, values in buckets.items():
                    if isinstance(values, list):
                        _stats[job_type][ext] = [float(v) for v in values]
    except Exception:
        pass


def _save_stats() -> None:
    if not _stats_file:
        return
    os.makedirs(os.path.dirname(_stats_file), exist_ok=True)
    with open(_stats_file, "w") as f:
        json.dump(_stats, f, indent=2)


def init_job_worker(
    censor_app,
    transcript_dir: str,
    global_blocklist: str,
    global_allowlist: str,
    stats_file: Optional[str] = None
) -> None:
    global _censor_app, _transcript_dir, _global_blocklist, _global_allowlist, _worker_started, _stats_file
    _censor_app = censor_app
    _transcript_dir = transcript_dir
    _global_blocklist = global_blocklist
    _global_allowlist = global_allowlist
    if stats_file:
        _stats_file = stats_file
    _load_stats()
    if not _worker_started:
        threading.Thread(target=_worker_loop, daemon=True).start()
        _worker_started = True


def enqueue_job(
    file_id: str,
    filename: str,
    job_type: str,
    input_path: str,
    base_no_ext: str,
    output_path: Optional[str] = None,
    duration: Optional[int] = None
) -> bool:
    global _next_job
    with _lock:
        if _current_job or _next_job:
            return False
        extension = os.path.splitext(filename)[1].lower()
        _next_job = {
            "file_id": file_id,
            "filename": filename,
            "type": job_type,
            "input_path": input_path,
            "output_path": output_path,
            "base_no_ext": base_no_ext,
            "duration": duration,
            "extension": extension
        }
        return True


def get_status() -> Dict[str, Optional[Dict]]:
    with _lock:
        return {"current": dict(_current_job) if _current_job else None}


def get_factor(job_type: str, extension: Optional[str] = None) -> float:
    with _lock:
        history = _stats.get(job_type, {})
        key = (extension or "default").lower()
        bucket = history.get(key)
        if bucket:
            return sum(bucket) / len(bucket)
        default_bucket = history.get("default")
        if default_bucket:
            return sum(default_bucket) / len(default_bucket)
        return _default_factors.get(job_type, {}).get(key, _default_factors.get(job_type, {}).get("default", 0.1))


def record_run(job_type: str, duration: int, runtime: float, extension: Optional[str] = None) -> None:
    if not duration or duration <= 0:
        return
    factor = runtime / duration
    key = (extension or "default").lower()
    with _lock:
        history = _stats.setdefault(job_type, {})
        bucket = history.setdefault(key, [])
        bucket.append(factor)
        if len(bucket) > 5:
            bucket.pop(0)
        _save_stats()


def _worker_loop() -> None:
    global _current_job, _next_job
    while True:
        job = None
        with _lock:
            if _next_job:
                job = _next_job
                _next_job = None
                started_at = time.time()
                job = {**job, "started_at": started_at}
                _current_job = job
                notifications.emit_job_update(job["file_id"], build_job_payload(job, "started"))
        if job:
            start_time = time.time()
            try:
                _run_job(job)
                duration = job.get("duration")
                if duration:
                    record_run(job["type"], duration, time.time() - start_time, job.get("extension"))
            except Exception as e:
                print(f"Job failed: {e}")
                time.sleep(5)
            finally:
                notifications.emit_job_update(job["file_id"], build_job_payload(job, "completed"))
                with _lock:
                    _current_job = None
        else:
            time.sleep(1)


def build_job_payload(job: Dict, status: str) -> Dict:
    duration = job.get("duration") or 0
    extension = job.get("extension")
    factor = get_factor(job["type"], extension)
    started_at = job.get("started_at")
    est_end = None
    if started_at is not None:
        est_end = started_at + (duration * factor)
    return {
        "type": job["type"],
        "status": status,
        "duration": duration,
        "started_at": started_at,
        "calculated_est_end_at": est_end
    }


def _run_job(job: Dict) -> None:
    job_type = job["type"]
    base_no_ext = job["base_no_ext"]
    file_id = job["file_id"]
    input_path = job["input_path"]
    output_path = job.get("output_path")

    if job_type in ("transcribe", "full_workflow"):
        _censor_app.transcribe(input_path, base_no_ext)
        update_file_metadata(file_id, {"transcribed": True})
        notifications.emit_metadata_updates([file_id])

    if job_type in ("censor", "full_workflow") and output_path:
        overrides_path = os.path.join(_transcript_dir, base_no_ext + "_overrides.json")
        overrides = {}
        if os.path.exists(overrides_path):
            with open(overrides_path, "r") as f:
                overrides = json.load(f)

        final_intervals = _censor_app.calculate_matches_with_cache(
            base_no_ext, _global_blocklist, _global_allowlist
        )
        final_intervals = _censor_app.apply_overrides(final_intervals, overrides)

        _censor_app.generate_censored_audio(
            input_path, final_intervals, output_path
        )

        def get_h(path: str) -> str:
            if not os.path.exists(path):
                return ""
            with open(path, "rb") as f:
                return hashlib.md5(f.read()).hexdigest()

        meta = {
            "blocklist_hash": get_h(_global_blocklist),
            "allowlist_hash": get_h(_global_allowlist),
            "overrides_hash": get_h(overrides_path),
            "censored_at": time.time(),
            "censored": True,
            "transcribed": True,
            "is_out_of_date": False
        }
        update_file_metadata(file_id, meta)
        notifications.emit_metadata_updates([file_id])
