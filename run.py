"""Start the single-process Bolo Sahayak demo server."""

import uvicorn


if __name__ == "__main__":
    uvicorn.run("services.api.main:app", host="127.0.0.1", port=8000)
