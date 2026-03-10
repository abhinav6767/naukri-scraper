import os
import json
import threading
import queue
import uuid
import sys
import contextlib
import io
from flask import Flask, render_template, request, jsonify, Response, send_file
from werkzeug.utils import secure_filename
from datetime import datetime
from PyPDF2 import PdfReader

# Import our scraper components
from scraper import NaukriScraper
from utils import save_to_json, save_to_csv, flatten_job_for_csv

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
        self.orig.write(message)
        self.orig.flush()
        if message:
            self.q.put(message)
        return len(message)

    def flush(self):
        self.orig.flush()


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
        max_jobs = int(params.get('max_jobs', 100))
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


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/scrape', methods=['POST'])
def start_scrape():
    # Convert form to dict where multiple values (checkboxes) remain as lists
    params = request.form.to_dict(flat=False)
    
    # Flatten single-item lists for convenience, except for known array fields
    array_fields = ['workMode', 'cities', 'department', 'companyType', 'roleCategory', 'industry', 'postedBy', 'topCompanies', 'ugCourse', 'pgCourse', 'stipend', 'duration']
    
    flat_params = {}
    for key, val in params.items():
        if key in array_fields:
            flat_params[key] = val
        else:
            flat_params[key] = val[0] if isinstance(val, list) and len(val) > 0 else ''
            
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
    filepath = os.path.join(app.config['OUTPUT_FOLDER'], safe_filename)
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True)
    return jsonify({"error": "File not found"}), 404


if __name__ == '__main__':
    app.run(debug=True, port=5001, use_reloader=False)
