# CUPS Print Management Gateway

This is a CUPS backend script that acts as a gateway for print jobs. Before releasing a job to a printer, it sends a POST request with job metadata to a specified API endpoint. The job is only printed if the API returns a 200 OK response.

This is useful for print accounting, policy enforcement, or "follow-me" printing systems.

## Features

- Intercepts print jobs from CUPS.
- Notifies a web service about new print jobs (user, job title, etc.).
- Releases jobs to the physical printer only upon successful API confirmation.
- Works with any real CUPS backend (e.g., `socket`, `ipp`, `lpd`).

## Prerequisites

- A running CUPS server on a Linux machine.
- Python 3.6+
- `pip` for installing Python packages.

## Installation

1.  **Install Python dependencies:**

    This script requires the `requests` library to make HTTP calls.

    ```bash
    pip3 install requests
    ```

2.  **Install the backend script:**

    The script (`main.py`) needs to be copied into the CUPS backend directory and made executable. We'll name it `printmanager`.

    ```bash
    sudo cp main.py /usr/lib/cups/backend/printmanager
    sudo chown root:root /usr/lib/cups/backend/printmanager
    sudo chmod 755 /usr/lib/cups/backend/printmanager
    ```
    *Note: The CUPS backend directory might vary. On some systems it could be `/usr/local/lib/cups/backend/`.*

3.  **Configure the script:**

    Open `/usr/lib/cups/backend/printmanager` with a text editor and change the `API_ENDPOINT` variable to point to your server.

    ```python
    API_ENDPOINT = "https://your-api.example.com/print-hook"
    ```

4.  **Restart CUPS:**

    For CUPS to recognize the new backend, you must restart it.

    ```bash
    sudo systemctl restart cups
    ```

## CUPS Printer Configuration

Now, you need to configure a CUPS printer queue to use this `printmanager` backend.

1.  Open the CUPS web interface (usually `http://localhost:631`).
2.  Go to `Administration` -> `Add Printer`. You may be prompted for admin credentials.
3.  Choose a printer under `Discovered Network Printers` or select `Other Network Printers` and choose the real protocol for your printer (e.g., `AppSocket/HP JetDirect` for `socket`). This helps you find the correct URI for the next step. **Do not complete adding the printer here.** Just note the device URI (e.g., `socket://192.168.1.123`).
4.  Go back and instead of selecting a discovered printer, select `Other Network Printers`.
5.  In the `Connection` text box, enter a URI in the following format:
    `printmanager:<real_printer_uri>`

    Replace `<real_printer_uri>` with the actual URI of your printer.

    **Examples:**
    - For a network printer using the JetDirect/RAW protocol:
      `printmanager:socket://192.168.1.100:9100`
    - For an IPP printer:
      `printmanager:ipp://192.168.1.101/ipp/print`
    - For a USB printer:
      `printmanager:usb://HP/LaserJet%20P2055dn?serial=XYZ123`

6.  Click `Continue`.
7.  Give the printer a name (e.g., `Managed-Office-Printer`), description, and location.
8.  Select the make and model for your printer to assign the correct PPD (driver).
9.  Finish adding the printer.

Now, any job sent to this new printer queue will be processed by the `printmanager` script.

## Getting the LDAP User

The script receives the username from CUPS as the second command-line argument. For CUPS to know the user who submitted the job (especially from Windows clients via Samba or IPP), you may need to configure authentication in CUPS.

In `cupsd.conf`, you might need to set `DefaultAuthType Basic` or configure Kerberos/LDAP authentication. This is an advanced topic specific to your network environment. When correctly configured, CUPS will pass the authenticated username to the backend script.

## Troubleshooting

Logs from the script are written to the CUPS error log. You can check it for `INFO` and `ERROR` messages from the script.

```bash
sudo tail -f /var/log/cups/error_log
```
Set `LogLevel debug` in `/etc/cups/cupsd.conf` for more verbose output from CUPS. Remember to restart CUPS after changing its configuration.
