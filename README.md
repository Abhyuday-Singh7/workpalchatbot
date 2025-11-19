# WorkPal Backend

This backend implements the core storage and execution layer for the WorkPal
central bot and department bots as described in your architecture.

## Features

- Department setup and file layout under `data/{department}`.
- Upload and extract department instruction PDFs/TXT into `department_rules`.
- Upload and register department Excel databases used for real read/write.
- Upload and store central company rules in `central_rules`.
- Execute structured operation intents against Excel (`READ/INSERT/UPDATE/DELETE`)
  and fetch rule text for `TEMPLATE/WORKFLOW`.

## Quick start

1. Create and activate a virtual environment.
2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Run the API server:

   ```bash
   uvicorn app.main:app --reload
   ```

4. Open the interactive docs at:

   - Swagger UI: http://127.0.0.1:8000/docs

## Core endpoints

- `POST /departments/setup` – initialize selected department folders.
- `POST /departments/{department}/upload-rules` – upload department instruction PDF/TXT.
- `POST /departments/{department}/upload-excel` – upload department Excel database.
- `POST /central-rules/upload` – upload company rule PDF/TXT.
- `GET  /central-rules` – fetch central rules for a user.
- `POST /intent/execute` – execute an operation intent (used by the WorkPal bot).

## SMTP setup (sending emails)

To enable outgoing email (used for `SEND_EMAIL` intents), set SMTP configuration in your environment or a `.env` file. For Gmail you should create an App Password (recommended) and use it as `SMTP_SENDER_PASSWORD`.

Required environment variables:

- `SMTP_SENDER_EMAIL` — the sender address (e.g. `noreply@yourdomain.com` or your Gmail address).
- `SMTP_SENDER_PASSWORD` — the SMTP password (Gmail App Password or SMTP credential).
- `SMTP_SERVER` — SMTP host (default: `smtp.gmail.com`).
- `SMTP_PORT` — SMTP port (default: `465` for SSL).

Quick Gmail setup:

1. Enable 2-Step Verification on your Google account.
2. Create an App Password for `Mail` and `Other` (or the device you choose).
3. Use the generated App Password as `SMTP_SENDER_PASSWORD`.
4. Set `SMTP_SENDER_EMAIL` to your Gmail address.

Troubleshooting tips:

- If sending fails, check logs — the service retries up to 3 times with exponential backoff and logs detailed errors.
- If you receive `InvalidFileException` when uploading Excel files, ensure the file is a valid `.xlsx`/`.xlsm`/`.xltx`/`.xltm` and not corrupted. Try opening and re-saving in Excel to repair.
- Ensure `OPENROUTER_API_KEY` or your configured LLM provider keys are set when using LLM features.

## Using this with WorkPal (the bot)

The LLM-based WorkPal bot should:

- Load `department_rules.rule_text` and `central_rules.rule_text` via these APIs.
- Decide if an operation is allowed or needs approval.
- Construct an `INTENT` object that matches the strict format you defined.
- Call `POST /intent/execute` to perform Excel operations or fetch templates/workflows.

In this chat environment, I will act as the WorkPal bot logic layer,
using the same INTENT format and authority rules you provided. You can
now upload or describe your rules/Excel structure, and then ask me to
perform operations; I will respond with the proper INTENT and/or
natural language result, keeping behavior aligned with this backend.

