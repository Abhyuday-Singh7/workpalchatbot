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

