import os
import json
import threading
import queue
import uuid
import sys
import contextlib
import io
import subprocess
import time
import random
from flask import Flask, render_template, request, jsonify, Response, send_file
from werkzeug.utils import secure_filename
from datetime import datetime
from PyPDF2 import PdfReader

# Import our scraper components
from scraper import NaukriScraper
from utils import save_to_json, save_to_csv, flatten_job_for_csv
from apply_jobs import get_edge_driver, apply_to_job

app = Flask(__name__)
app.config['OUTPUT_FOLDER'] = os.path.dirname(os.path.abspath(__name__))

# Ensure templates and static folders exist
os.makedirs(os.path.join(app.config['OUTPUT_FOLDER'], 'naukri_scraper', 'templates'), exist_ok=True)
os.makedirs(os.path.join(app.config['OUTPUT_FOLDER'], 'naukri_scraper', 'static'), exist_ok=True)

# Global dictionary to track scraping tasks
tasks = {}

class QueueWriter(io.TextIOBase):
    """A custom file-like object that writes stdout/stderr to a queue for SSE streaming"""
    def __init__(self, q, original_stream):
        self.q = q
        self.orig = original_stream

    def write(self, message):
        try:
            self.orig.write(message)
        except UnicodeEncodeError:
            self.orig.write(message.encode('ascii', 'replace').decode('ascii'))
        self.orig.flush()
        if message:
            self.q.put(message)
        return len(message)

    def flush(self):
        self.orig.flush()

def get_applied_jobs_path():
    data_dir = os.path.join(app.config['OUTPUT_FOLDER'], 'data')
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, 'applied_jobs.json')

def load_applied_jobs():
    path = get_applied_jobs_path()
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []

def save_applied_job(job_id):
    jobs = load_applied_jobs()
    if job_id not in jobs:
        jobs.append(job_id)
        with open(get_applied_jobs_path(), 'w', encoding='utf-8') as f:
            json.dump(jobs, f, indent=4)


def run_scrape_task(task_id, params, cv_text=None):
    """Runs the scraper in a background thread and redirects logs to the queue"""
    q = tasks[task_id]['queue']
    
    # Store the original streams
    orig_stdout = sys.stdout
    orig_stderr = sys.stderr
    
    # Redirect streams to our queue in this thread
    sys.stdout = QueueWriter(q, orig_stdout)
    sys.stderr = QueueWriter(q, orig_stderr)
    
    try:
        print(f"[INFO] Starting scraping task {task_id}")
        if cv_text:
            print("[INFO] User provided a CV. AI Relevance Scoring enabled.")
            
        keyword = params.get('keyword', '')
        # Hard limit scrap count to 499 to prevent excessive memory/requests
        max_jobs = min(499, int(params.get('max_jobs', 100)))
        fetch_details = str(params.get('fetch_details', 'false')).lower() == 'true'
        output_name = params.get('output_name', f'naukri_jobs_{task_id[:6]}')
        
        # Build filters
        filters = {}
        for key, val in params.items():
            if key not in ['keyword', 'max_jobs', 'fetch_details', 'output_name', 'other_cities'] and val:
                # If it is a string containing commas, split it. If already a list from checkboxes, keep it.
                if key in ['workMode', 'salaryRange', 'cities', 'department', 'companyType', 'roleCategory', 'industry', 'postedBy', 'topCompanies', 'ugCourse', 'pgCourse', 'stipend', 'duration']:
                    if isinstance(val, str):
                        filters[key] = [x.strip() for x in val.split(',')]
                    elif isinstance(val, list):
                        filters[key] = val
                else:
                    filters[key] = val

        start = datetime.now()
        scraper = NaukriScraper()
        
        if fetch_details:
            jobs = scraper.run_detailed_mode(keyword, max_jobs, filters, cv_text=cv_text)
        else:
            jobs = scraper.run_search_mode(keyword, max_jobs, filters, cv_text=cv_text)

        elapsed = (datetime.now() - start).total_seconds()
        print(f"\n[SUMMARY] Scraped {len(jobs)} jobs in {elapsed:.1f}s")
        
        if not jobs:
            print("[WARN] No jobs collected.")
            tasks[task_id]['status'] = 'completed'
            return

        json_path = save_to_json(jobs, output_name)
        print(f"[SAVED] JSON -> {json_path}")
        
        flat_jobs = [flatten_job_for_csv(j) for j in jobs]
        csv_path = save_to_csv(flat_jobs, output_name)
        print(f"[SAVED] CSV  -> {csv_path}")

        tasks[task_id]['status'] = 'completed'
        tasks[task_id]['files'] = {
            'json': f"{output_name}.json",
            'csv': f"{output_name}.csv"
        }
        
    except Exception as e:
        print(f"[ERROR] Scrape failed: {str(e)}", file=sys.stderr)
        tasks[task_id]['status'] = 'error'
        
    finally:
        # Restore standard output streams
        sys.stdout = orig_stdout
        sys.stderr = orig_stderr
        q.put("===END_OF_STREAM===")


def deduct_one_credit(user_id):
    import urllib.request
    import json
    req_data = json.dumps({"userId": user_id, "creditsToDeduct": 1}).encode('utf-8')
    try:
        req = urllib.request.Request("http://localhost:3000/api/naukri-credits", data=req_data, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req) as response:
            resp_data = json.loads(response.read().decode())
            return resp_data.get('success', False)
    except Exception as e:
        print(f"[WARN] Failed to deduct credit for user {user_id}: {e}")
        return False


def run_apply_task(task_id, job_ids, context_filename=None, params=None):
    """Runs the apply job in a background thread and redirects logs to the queue"""
    q = tasks[task_id]['queue']
    if params is None:
        params = {}
    
    # Store the original streams
    orig_stdout = sys.stdout
    orig_stderr = sys.stderr
    
    # Redirect streams to our queue in this thread
    sys.stdout = QueueWriter(q, orig_stdout)
    sys.stderr = QueueWriter(q, orig_stderr)
    
    user_id = params.get('user_id')
    is_q_run = params.get('is_questionnaire_run', False)
    
    try:
        print(f"[INFO] Starting Apply Task {task_id}")
        print(f"[INFO] Looking for {len(job_ids)} jobs to apply to.")
        
        # Load the scraped jobs to get job details
        jobs = []
        if context_filename:
            try:
                filepath = os.path.join(app.config['OUTPUT_FOLDER'], 'data', context_filename)
                with open(filepath, 'r', encoding='utf-8') as f:
                    jobs = json.load(f)
            except Exception as e:
                print(f"[ERROR] Could not read context file {context_filename}: {e}", file=sys.stderr)
        else:
            print("[WARN] No context filename provided. Falling back to default output.json/naukri_jobs.json if exists")
            # fallback loading
        
        driver = get_edge_driver()
        if not driver:
            print("[ERROR] Could not connect to Microsoft Edge (make sure it's running with debugging port 9222!)")
            tasks[task_id]['status'] = 'error'
            return
            
        print("[SUCCESS] Successfully connected to Microsoft Edge!")
        
        # We find ALL jobs the user selected, then we handle applied ones individually so the UI knows.
        selected_jobs = [j for j in jobs if j.get('jobId') in job_ids]
        applied_jobs = load_applied_jobs()
        
        for idx, job in enumerate(selected_jobs):
            # Check if applied already
            if job.get('jobId') in applied_jobs:
                job_status = "Already Applied"
                print(f"[INFO] Skipping {job.get('companyName')} - Already applied locally.")
            else:
                # Check for generic user pause before interacting with the next job
                if tasks[task_id].get('user_paused'):
                    print("===USER_PAUSED===")
                    tasks[task_id]['pause_toggle'].wait() # Block until resume clears this
                    tasks[task_id]['pause_toggle'].clear() # Reset for next pause
                    print("[INFO] Resuming application run...")

                # Clean up extra tabs before applying to next job (helps prevent getting stuck)
                try:
                    if len(driver.window_handles) > 1:
                        print("[INFO] Cleaning up extra tabs...")
                        for handle in driver.window_handles[1:]:
                            driver.switch_to.window(handle)
                            driver.close()
                    driver.switch_to.window(driver.window_handles[0])
                except Exception as e:
                    print(f"[WARN] Tab cleanup issue: {e}")
                    
                job_status = apply_to_job(driver, job)
            
            # ==== DEDUCT CREDIT CONDITIONALLY ====
            # If the application succeeded, or it hit a questionnaire for the FIRST time
            # We skip deduction if it was a company site, already applied, navigation failed, etc.
            # We also skip deduction if this is a follow-up Questionnaire Run (they paid previously).
            chargeable_statuses = ["Success", "Questionnaire Detected", "Success (Manual)"]
            
            should_deduct = False
            if user_id and not is_q_run:
                # If any chargeable status matches, we flag to deduct.
                if any(cs in job_status for cs in chargeable_statuses):
                    should_deduct = True
            
            if should_deduct:
                success_deduct = deduct_one_credit(user_id)
                if not success_deduct:
                    print("[WARN] Could not deduct credit for this job! You might be out of credits.")
                    # We might halt or just warn. Let's halt if they have 0 credits.
                    # Since we applied already, the current status is what it is, but we break next loop
                    pass
            # =====================================

            # Emit structured JSON payload for frontend table shifting
            ui_msg = json.dumps({
                "type": "job_status",
                "jobId": job.get("jobId"),
                "status": job_status,
                "jdURL": job.get("jdURL"),
                "companyName": job.get("companyName"),
                "title": job.get("title")
            })
            print(f"|||{ui_msg}|||")
            
            if "Success" in job_status or job_status == "Already Applied":
                save_applied_job(job.get('jobId'))
                
            # If the job had a questionnaire and we were explicitly told it was a questionnaire run
            # we pause here for the user to complete it
            if job_status == "Questionnaire Detected":
                if is_q_run:
                    print("[WARN] Stopping automation because manual intervention is required for a questionnaire.")
                    print("===PAUSED===")
                    tasks[task_id]['pause_event'].clear() # Ensure it's cleared before waiting
                    
                    print("[INFO] Waiting for you to complete it manually. You can click 'Resume' or I will auto-detect when finished...")
                    # Loop and poll every 2 seconds instead of indefinite block
                    while not tasks[task_id]['pause_event'].is_set():
                        try:
                            # Auto-detect check based on Naukri confirmation page
                            if "Apply Confirmation" in driver.title or "Applied to" in driver.page_source:
                                print("[INFO] Auto-detected successful manual application!")
                                tasks[task_id]['pause_event'].set()
                                break
                        except Exception:
                            # Browser closed intentionally or navigating heavily
                            pass
                        
                        # Wait 2 seconds then check again, unless event is set by Resume button
                        tasks[task_id]['pause_event'].wait(2.0)
                        
                    print(f"[INFO] Resuming automation after manual intervention...")
                    # By resuming, we assume the user successfully applied manually
                    job_status = "Success (Manual)"
                    save_applied_job(job.get('jobId'))
                    
                    # Refire success to UI so it gets recorded in this session!
                    ui_msg2 = json.dumps({
                        "type": "job_status",
                        "jobId": job.get("jobId"),
                        "status": job_status,
                        "jdURL": job.get("jdURL"),
                        "companyName": job.get("companyName"),
                        "title": job.get("title")
                    })
                    print(f"|||{ui_msg2}|||")
                
            if idx < len(selected_jobs) - 1:
                wait_time = random.uniform(2, 4)
                print(f"[INFO] Waiting {wait_time:.1f} seconds before next job...")
                time.sleep(wait_time)
                    
        print("\n[SUMMARY] Finished application attempt run.")
        tasks[task_id]['status'] = 'completed'
        
    except Exception as e:
        print(f"[ERROR] Apply failed: {str(e)}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        tasks[task_id]['status'] = 'error'
        
    finally:
        if 'driver' in locals() and driver:
            try:
                for handle in driver.window_handles:
                    driver.switch_to.window(handle)
                    driver.close()
                driver.quit()
                print("[INFO] Closed Microsoft Edge.")
            except:
                pass
        # Restore standard output streams
        sys.stdout = orig_stdout
        sys.stderr = orig_stderr
        q.put("===END_OF_STREAM===")


@app.route('/')
def index():
    userId = request.args.get('userId', '')
    credits = request.args.get('credits', '0')
    return render_template('index.html', userId=userId, credits=credits)


@app.route('/api/scrape', methods=['POST'])
def start_scrape():
    # Convert form to dict where multiple values (checkboxes) remain as lists
    params = request.form.to_dict(flat=False)
    
    # Flatten single-item lists for convenience, except for known array fields
    array_fields = ['workMode', 'cities', 'department', 'companyType', 'roleCategory',
                    'industry', 'postedBy', 'topCompanies', 'ugCourse', 'pgCourse',
                    'stipend', 'duration', 'salaryRange']
    
    flat_params = {}
    for key, val in params.items():
        if key in array_fields:
            flat_params[key] = val
        else:
            flat_params[key] = val[0] if isinstance(val, list) and len(val) > 0 else ''
    
    # Handle experience range slider → pass as single "experience" value (Naukri uses min)
    exp_min = flat_params.pop('experienceMin', '0') or '0'
    exp_max = flat_params.pop('experienceMax', '30') or '30'
    try:
        exp_min_int = int(exp_min)
        exp_max_int = int(exp_max)
        # Only set experience filter if the user changed from defaults (0 and 30)
        if not (exp_min_int == 0 and exp_max_int == 30):
            flat_params['experience'] = str(exp_min_int)
            flat_params['experienceMax'] = str(exp_max_int)
    except ValueError:
        pass
        
    # Handle the "other_cities" manual input by appending to the cities array
    if flat_params.get('other_cities'):
        other_cities = [c.strip() for c in flat_params['other_cities'].split(',') if c.strip()]
        if 'cities' not in flat_params:
            flat_params['cities'] = []
        elif not isinstance(flat_params['cities'], list):
            flat_params['cities'] = [flat_params['cities']]
        flat_params['cities'].extend(other_cities)
    
    flat_params.pop('other_cities', None) # Remove so it doesn't get sent to API
        
    # Handle File Upload for CV Scoring
    cv_text = None
    if 'cv_file' in request.files:
        file = request.files['cv_file']
        if file and file.filename != '':
            try:
                reader = PdfReader(file)
                cv_text = " ".join(page.extract_text() for page in reader.pages if page.extract_text())
            except Exception as e:
                print(f"[WARN] Error extracting text from CV: {e}", file=sys.stderr)

    task_id = str(uuid.uuid4())
    
    tasks[task_id] = {
        'status': 'running',
        'queue': queue.Queue(),
        'files': {}
    }
    
    # Run in background thread
    thread = threading.Thread(target=run_scrape_task, args=(task_id, flat_params, cv_text))
    thread.daemon = True
    thread.start()
    
    return jsonify({"task_id": task_id})


@app.route('/api/logs/<task_id>')
def stream_logs(task_id):
    if task_id not in tasks:
        return jsonify({"error": "Task not found"}), 404
        
    def generate():
        q = tasks[task_id]['queue']
        while True:
            try:
                # Block for up to 1 second
                msg = q.get(timeout=1.0)
                if msg == "===END_OF_STREAM===":
                    yield "event: end\ndata: STREAM_DONE\n\n"
                    break
                # Properly format the SSE data
                yield f"data: {msg}\n\n"
            except queue.Empty:
                yield ": heartbeat\n\n"
                
    return Response(generate(), mimetype='text/event-stream')


@app.route('/api/status/<task_id>')
def check_status(task_id):
    if task_id not in tasks:
        return jsonify({"error": "Task not found"}), 404
    return jsonify({
        "status": tasks[task_id]['status'],
        "files": tasks.get(task_id, {}).get('files', {})
    })


@app.route('/api/download/<filename>')
def download_file(filename):
    safe_filename = secure_filename(filename)
    filepath = os.path.join(app.config['OUTPUT_FOLDER'], 'data', safe_filename)
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True)
    return jsonify({"error": "File not found"}), 404


@app.route('/api/open_edge', methods=['POST'])
def open_edge():
    try:
        # Common locations for Microsoft Edge on Windows
        edge_paths = [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
        ]
        
        # Find the first path that exists
        edge_path = next((p for p in edge_paths if os.path.exists(p)), "msedge.exe")
        
        # We start Edge detached using the command shell
        # 'start ""' ensures the quoted path isn't treated as a window title
        cmd = f'start "" "{edge_path}" --remote-debugging-port=9222 --user-data-dir="C:\\edge_debug"'
        subprocess.Popen(cmd, shell=True)
        
        return jsonify({"status": "success", "message": "Edge launched with debugging enabled."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/applied_jobs', methods=['GET'])
def get_applied_jobs():
    return jsonify(load_applied_jobs())


@app.route('/api/start_apply', methods=['POST'])
def start_apply():
    data = request.json
    job_ids = data.get('job_ids', [])
    context_filename = data.get('context_filename', '')
    is_questionnaire_run = data.get('is_questionnaire_run', False)
    user_id = data.get('userId', '')
    
    if not job_ids:
        return jsonify({"error": "No job IDs provided"}), 400

    task_id = str(uuid.uuid4())
    
    if not user_id:
        return jsonify({"error": "Unauthorized. Missing user ID for credit deduction."}), 401
    
    tasks[task_id] = {
        'status': 'running',
        'queue': queue.Queue(),
        'files': {},
        'pause_event': threading.Event(),
        'pause_toggle': threading.Event(),
        'user_paused': False
    }
    
    params = {
        'is_questionnaire_run': is_questionnaire_run,
        'user_id': user_id
    }
    
    # Run in background thread
    thread = threading.Thread(target=run_apply_task, args=(task_id, job_ids, context_filename, params))
    thread.daemon = True
    thread.start()
    
    return jsonify({"task_id": task_id})


@app.route('/api/resume_apply/<task_id>', methods=['POST'])
def resume_apply(task_id):
    if task_id not in tasks:
        return jsonify({"error": "Task not found"}), 404
        
    # Clear user pause if it was set
    if tasks[task_id].get('user_paused'):
        tasks[task_id]['user_paused'] = False
        tasks[task_id]['pause_toggle'].set()
        
    # Unblock the questionnaire intervention thread if it was blocked
    tasks[task_id]['pause_event'].set()
    return jsonify({"status": "resumed"})

@app.route('/api/pause_apply/<task_id>', methods=['POST'])
def pause_apply(task_id):
    if task_id not in tasks:
        return jsonify({"error": "Task not found"}), 404
        
    # Request the thread to pause before the next job
    tasks[task_id]['user_paused'] = True
    return jsonify({"status": "pausing"})


if __name__ == '__main__':
    app.run(debug=True, port=5001, use_reloader=True)
