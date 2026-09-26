"""Entry point for the vm106 portfolio host: run the app on 0.0.0.0:$PORT."""
import os

import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8119"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=False)
