#!/usr/bin/env python3

import sys
import os
import requests
import subprocess
import tempfile

# The API endpoint to notify about a new print job.
# This server should return a 200 OK status to allow the print job.
API_ENDPOINT = "https://example.com/print-job-hook"

def log_error(message):
    """Logs an error message to stderr."""
    sys.stderr.write(f"ERROR: {message}\n")

def log_info(message):
    """Logs an info message to stderr."""
    sys.stderr.write(f"INFO: {message}\n")

def main():
    """
    CUPS backend script to control print job release via an API call.
    """
    # CUPS calls backends with 0 args for discovery, or 5/6 for a print job.
    # We only care about print jobs.
    if len(sys.argv) < 6:
        sys.exit(0)

    job_id = sys.argv[1]
    user = sys.argv[2]
    title = sys.argv[3]
    copies = sys.argv[4]
    options = sys.argv[5]
    job_file = sys.argv[6] if len(sys.argv) == 7 else None

    # The device URI for this backend must be in the format:
    # printmanager:/<real_backend_uri>
    # e.g., printmanager:socket://192.168.1.123:9100
    device_uri = os.environ.get("DEVICE_URI")
    if not device_uri or not device_uri.startswith("printmanager:"):
        log_error("Invalid DEVICE_URI. Expected 'printmanager:/<real_uri>'.")
        sys.exit(1)

    real_printer_uri = device_uri[len("printmanager:"):]
    if not real_printer_uri:
        log_error("Real printer URI is missing from DEVICE_URI.")
        sys.exit(1)

    # Prepare data for the API POST request
    payload = {
        'job_id': job_id,
        'user': user,
        'title': title,
        'printer': os.environ.get("PRINTER", "unknown"),
        'copies': copies,
    }

    log_info(f"Processing job {job_id} for user {user}. Notifying API.")

    try:
        response = requests.post(API_ENDPOINT, json=payload, timeout=30)
    except requests.exceptions.RequestException as e:
        log_error(f"API request failed: {e}")
        # Exit 1 tells CUPS to retry the job later.
        sys.exit(1)

    if response.status_code == 200:
        log_info(f"API approval received for job {job_id}. Releasing to printer.")
    else:
        log_error(f"API call failed with status {response.status_code}. Job will not be printed.")
        log_error(f"Response: {response.text}")
        # Exit 1 tells CUPS to retry the job later.
        sys.exit(1)

    # API call was successful, now release the job to the real printer.
    try:
        scheme = real_printer_uri.split(':', 1)[0]
    except IndexError:
        log_error(f"Could not determine scheme from real printer URI: {real_printer_uri}")
        sys.exit(1)

    backend_path = f"/usr/lib/cups/backend/{scheme}"
    if not os.path.exists(backend_path) or not os.access(backend_path, os.X_OK):
        log_error(f"CUPS backend for scheme '{scheme}' not found or not executable at {backend_path}.")
        sys.exit(1)

    # The print job data is on stdin if no file is given.
    # We must pass it to the real backend.
    # Using a temporary file ensures the data is read before we execute the next process.
    temp_job_file = None
    if not job_file:
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(sys.stdin.buffer.read())
            job_file = tmp.name
            temp_job_file = job_file

    # Set up environment and arguments for the real backend
    backend_env = os.environ.copy()
    backend_env["DEVICE_URI"] = real_printer_uri
    backend_args = [backend_path, job_id, user, title, copies, options, job_file]

    try:
        # Execute the real backend to perform the printing
        result = subprocess.run(backend_args, env=backend_env, check=False)
        if result.returncode == 0:
            log_info(f"Job {job_id} successfully sent to printer.")
            # Exit 0 for success
            sys.exit(0)
        else:
            log_error(f"Real backend '{scheme}' failed with exit code {result.returncode}.")
            # Exit 1 for failure
            sys.exit(1)
    finally:
        # Clean up the temporary file if we created one
        if temp_job_file:
            os.unlink(temp_job_file)

if __name__ == "__main__":
    main()
