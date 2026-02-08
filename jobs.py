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
        self.stats_file = os.path.join(os.path.dirname(jobs_file), "stats.json")
        self.status = {"current": None}
        self.next_job = None
        self.lock = threading.RLock()
        
        # Default factors: audio_duration * factor = runtime
        self.default_factors = {
            "transcribe": 0.08,
            "censor": 0.03,
            "full_workflow": 0.11
        }
        self.stats = {
            "transcribe": [],
            "censor": [],
            "full_workflow": []
        }
        
        self.load_status()
        self.load_stats()
        
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
        with self.lock:
            with open(self.jobs_file, "w") as f:
                json.dump(self.status, f, indent=2)

    def load_stats(self):
        if os.path.exists(self.stats_file):
            try:
                with open(self.stats_file, "r") as f:
                    self.stats.update(json.load(f))
            except:
                pass

    def save_stats(self):
        with self.lock:
            with open(self.stats_file, "w") as f:
                json.dump(self.stats, f, indent=2)

    def get_factor(self, job_type):
        with self.lock:
            history = self.stats.get(job_type, [])
            if not history:
                return self.default_factors.get(job_type, 0.1)
            return sum(history) / len(history)

    def record_run(self, job_type, duration, runtime):
        if not duration or duration <= 0: return
        factor = runtime / duration
        with self.lock:
            history = self.stats.setdefault(job_type, [])
            history.append(factor)
            if len(history) > 5:
                history.pop(0)
            self.save_stats()

    def enqueue(self, file_id, filename, job_type, input_path=None, output_path=None, base_no_ext=None, duration=None):
        with self.lock:
            if self.status["current"] or self.next_job:
                return False # Busy
            
            job = {
                "file_id": file_id,
                "filename": filename,
                "type": job_type,
                "input_path": input_path,
                "output_path": output_path,
                "base_no_ext": base_no_ext,
                "duration": duration
            }
            self.next_job = job
            return True

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
                    self.status["current"] = {**job, "started_at": time.time()}
                    self.save_status()
            
            if job:
                start_time = time.time()
                try:
                    self._run_job(job)
                    duration = job.get("duration")
                    if duration:
                        runtime = time.time() - start_time
                        self.record_run(job["type"], duration, runtime)
                        
                    with self.lock:
                        self.status["current"] = None
                        self.save_status()
                except Exception as e:
                    print(f"Job failed: {e}")
                    # In a single-job system, we just clear and wait
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

