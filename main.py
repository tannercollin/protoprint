#!/usr/bin/env python3

import logging
DEBUG = False
logging.basicConfig(
        filename='/tmp/protoprint.log', encoding='utf-8',
        format='[%(asctime)s] %(levelname)s %(funcName)s - %(message)s',
        level=logging.DEBUG if DEBUG else logging.INFO)

import sys
import os
import json
from urllib import request, error
import subprocess
import tempfile

# The API endpoint to notify about a new print job.
# This server should return a 200 OK status to allow the print job.
API_ENDPOINT = ""


def approve_job():
    """Instructs CUPS that the job is successful."""
    sys.exit(0)


def retry_job():
    """Instructs CUPS to retry the job later."""
    sys.exit(1)


def cancel_job():
    """Instructs CUPS to cancel the job."""
    sys.exit(4)


def main():
    """
    CUPS backend script to control print job release via an API call.
    """
    # CUPS calls backends with 0 args for discovery, or 5/6 for a print job.
    # We only care about print jobs.
    if len(sys.argv) < 6:
        approve_job()

    job_id = sys.argv[1]
    user = sys.argv[2]
    title = sys.argv[3]
    copies = sys.argv[4]
    options = sys.argv[5]
    job_file = sys.argv[6] if len(sys.argv) == 7 else None

    logging.info(
        f"New print job received:\n"
        f"  Job ID:  {job_id}\n"
        f"  User:    {user}\n"
        f"  Title:   {title}\n"
        f"  Copies:  {copies}\n"
        f"  Options: {options}"
    )

    # The device URI for this backend must be in the format:
    # printmanager:/<real_backend_uri>
    # e.g., printmanager:socket://192.168.1.123:9100
    device_uri = os.environ.get("DEVICE_URI")
    if not device_uri or not device_uri.startswith("printmanager:"):
        logging.error("Invalid DEVICE_URI. Expected 'printmanager:/<real_uri>'.")
        retry_job()

    real_printer_uri = device_uri[len("printmanager:"):]
    if not real_printer_uri:
        logging.error("Real printer URI is missing from DEVICE_URI.")
        retry_job()

    # Prepare data for the API POST request
    payload = {
        'job_id': job_id,
        'user': user,
        'title': title,
        'printer': os.environ.get("PRINTER", "unknown"),
        'copies': copies,
    }

    if not API_ENDPOINT:
        logging.info("API_ENDPOINT is not set. Skipping API call and releasing job directly.")
    else:
        logging.info(f"Processing job {job_id} for user {user}. Notifying API.")

        try:
            data = json.dumps(payload).encode('utf-8')
            req = request.Request(API_ENDPOINT, data=data, headers={'Content-Type': 'application/json'})
            with request.urlopen(req, timeout=30) as response:
                if response.status == 200:
                    logging.info(f"API approval received for job {job_id}. Releasing to printer.")
                else:
                    response_text = response.read().decode('utf-8', 'ignore')
                    logging.error(f"API call failed with status {response.status}. Job will not be printed.")
                    logging.error(f"Response: {response_text}")
                    cancel_job()
        except error.URLError as e:
            logging.error(f"API request failed: {e}")
            retry_job()

    # API call was successful, now release the job to the real printer.
    try:
        scheme = real_printer_uri.split(':', 1)[0]
    except IndexError:
        logging.error(f"Could not determine scheme from real printer URI: {real_printer_uri}")
        retry_job()

    backend_path = f"/usr/lib/cups/backend/{scheme}"
    if not os.path.exists(backend_path) or not os.access(backend_path, os.X_OK):
        logging.error(f"CUPS backend for scheme '{scheme}' not found or not executable at {backend_path}.")
        retry_job()

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
            logging.info(f"Job {job_id} successfully sent to printer.")
            approve_job()
        else:
            logging.error(f"Real backend '{scheme}' failed with exit code {result.returncode}.")
            retry_job()
    finally:
        # Clean up the temporary file if we created one
        if temp_job_file:
            os.unlink(temp_job_file)

if __name__ == "__main__":
    main()
