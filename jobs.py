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
        self.status = {"current": None, "queue": []}
        self.lock = threading.Lock()
        self.load_status()
        
        # Start background worker
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()

    def load_status(self):
        if os.path.exists(self.jobs_file):
            try:
                with open(self.jobs_file, "r") as f:
                    self.status = json.load(f)
                    # If current was running when we crashed/restarted, move it back to queue or mark as failed
                    if self.status.get("current"):
                        self.status["queue"].insert(0, self.status["current"])
                        self.status["current"] = None
            except:
                pass

    def save_status(self):
        with open(self.jobs_file, "w") as f:
            json.dump(self.status, f, indent=2)

    def enqueue(self, file_id, filename, job_type, input_path=None, output_path=None, base_no_ext=None):
        job = {
            "id": str(uuid.uuid4()),
            "file_id": file_id,
            "filename": filename,
            "type": job_type,
            "input_path": input_path,
            "output_path": output_path,
            "base_no_ext": base_no_ext,
            "status": "queued",
            "progress": 0,
            "enqueued_at": time.time()
        }
        with self.lock:
            # Check if identical job already in queue or running
            if self.status["current"] and self.status["current"]["file_id"] == file_id and self.status["current"]["type"] == job_type:
                return self.status["current"]["id"]
            
            for q_job in self.status["queue"]:
                if q_job["file_id"] == file_id and q_job["type"] == job_type:
                    return q_job["id"]

            self.status["queue"].append(job)
            self.save_status()
        return job["id"]

    def get_status(self):
        with self.lock:
            return self.status

    def _worker_loop(self):
        while True:
            job = None
            with self.lock:
                if self.status["queue"]:
                    job = self.status["queue"].pop(0)
                    self.status["current"] = {**job, "status": "running", "started_at": time.time()}
                    self.save_status()
            
            if job:
                try:
                    self._run_job(job)
                    with self.lock:
                        # Job success: clear it so next one can start
                        self.status["current"] = None
                        self.save_status()
                except Exception as e:
                    print(f"Job failed: {e}")
                    with self.lock:
                        # Mark as failed in current for a bit so UI can show it?
                        # Or just clear it. Let's keep it for 5s then clear.
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
        elif job_type == "prepare":
             self.censor_app.calculate_matches_with_cache(
                job["base_no_ext"], self.global_blocklist, self.global_allowlist
            )
             self.censor_app.calculate_vocab_with_cache(job["base_no_ext"])
