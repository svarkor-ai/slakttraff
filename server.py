"""Entry point for the vm106 portfolio host: run the app on 0.0.0.0:$PORT.

On vm106 the app directory is read-only (the unit runs with ProtectSystem=strict), so the
default SQLite path under data/ cannot be opened. systemd gives the unit a writable
StateDirectory and exports it as $STATE_DIRECTORY; when present, and no explicit
SLAKTTRAFF_DATABASE_URL is set, the database lives there (same convention as hotell).
Local runs are unchanged: no STATE_DIRECTORY -> data/slakttraff.db.
"""
import os

import uvicorn

if __name__ == "__main__":
    state_dir = os.environ.get("STATE_DIRECTORY", "").split(":")[0]
    if state_dir and "SLAKTTRAFF_DATABASE_URL" not in os.environ:
        os.environ["SLAKTTRAFF_DATABASE_URL"] = f"sqlite:///{os.path.join(state_dir, 'slakttraff.db')}"
    port = int(os.environ.get("PORT", "8120"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=False)
