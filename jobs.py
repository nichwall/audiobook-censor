import os
import json
import threading
import time
import uuid

class JobManager:
    def __init__(self, jobs_file, censor_app, transcript_dir, global_blocklist, global_allowlist):
        self.jobs_file = jobs_file
        self.censor_app = censor_app
        self.transcript_dir = transcript_dir
        self.global_blocklist = global_blocklist
        self.global_allowlist = global_allowlist
        self.status = {"current": None}
        self.next_job = None
        self.lock = threading.Lock()
        self.load_status()
        
        # Start background worker
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()

    def load_status(self):
        if os.path.exists(self.jobs_file):
            try:
                with open(self.jobs_file, "r") as f:
                    data = json.load(f)
                    # We only care about current. If it was running, we'll mark it as None 
                    # since we don't persist enough to resume perfectly without the full job object
                    self.status = {"current": None}
            except:
                pass

    def save_status(self):
        with open(self.jobs_file, "w") as f:
            json.dump(self.status, f, indent=2)

    def enqueue(self, file_id, filename, job_type, input_path=None, output_path=None, base_no_ext=None, duration=None):
        with self.lock:
            if self.status["current"] or self.next_job:
                return None # Busy
            
            job = {
                "id": str(uuid.uuid4()),
                "file_id": file_id,
                "filename": filename,
                "type": job_type,
                "input_path": input_path,
                "output_path": output_path,
                "base_no_ext": base_no_ext,
                "duration": duration,
                "status": "queued",
                "progress": 0,
                "enqueued_at": time.time()
            }
            self.next_job = job
            return job["id"]

    def get_status(self):
        with self.lock:
            return self.status

    def _worker_loop(self):
        while True:
            job = None
            with self.lock:
                if self.next_job:
                    job = self.next_job
                    self.next_job = None
                    self.status["current"] = {**job, "status": "running", "started_at": time.time()}
                    self.save_status()
            
            if job:
                try:
                    self._run_job(job)
                    with self.lock:
                        self.status["current"] = None
                        self.save_status()
                except Exception as e:
                    print(f"Job failed: {e}")
                    with self.lock:
                        if self.status["current"]:
                            self.status["current"]["status"] = "failed"
                            self.status["current"]["error"] = str(e)
                            self.save_status()
                    time.sleep(5)
                    with self.lock:
                        self.status["current"] = None
                        self.save_status()
            else:
                time.sleep(1)

    def _run_job(self, job):
        job_type = job["type"]
        
        if job_type == "transcribe":
            self.censor_app.transcribe(job["input_path"], job["base_no_ext"])
        elif job_type == "censor":
            self._do_censor(job)
        elif job_type == "full_workflow":
            # 1. Transcribe
            self.censor_app.transcribe(job["input_path"], job["base_no_ext"])
            # 2. Censor
            self._do_censor(job)
        elif job_type == "prepare":
             self.censor_app.calculate_matches_with_cache(
                job["base_no_ext"], self.global_blocklist, self.global_allowlist
            )
             self.censor_app.calculate_vocab_with_cache(job["base_no_ext"])

    def _do_censor(self, job):
        overrides_path = os.path.join(self.transcript_dir, job["base_no_ext"] + "_overrides.json")
        overrides = {}
        if os.path.exists(overrides_path):
            with open(overrides_path, "r") as f:
                overrides = json.load(f)
        
        final_intervals = self.censor_app.calculate_matches_with_cache(
            job["base_no_ext"], self.global_blocklist, self.global_allowlist
        )
        final_intervals = self.censor_app.apply_overrides(final_intervals, overrides)
        
        self.censor_app.generate_censored_audio(
            job["input_path"], final_intervals, job["output_path"]
        )
        
        # Save metadata hashes
        import hashlib
        def get_h(p):
            if not os.path.exists(p): return ""
            with open(p, "rb") as f: return hashlib.md5(f.read()).hexdigest()
        
        meta = {
            "blocklist_hash": get_h(self.global_blocklist),
            "allowlist_hash": get_h(self.global_allowlist),
            "overrides_hash": get_h(overrides_path),
            "censored_at": time.time()
        }
        meta_path = os.path.join(self.transcript_dir, job["base_no_ext"] + "_censor_meta.json")
        with open(meta_path, "w") as f:
            json.dump(meta, f, indent=2)

