import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

# Test servers must not download or load a Whisper model during the suite;
# the adapter tests inject a fake model instead.
os.environ.setdefault("WHISPER_PRELOAD", "0")
os.environ.setdefault("WHISPER_ENABLED", "0")
# A local .env must not hide the new default from the suite.
os.environ.setdefault("STT_ORDER", "wispr_api,whisper_local,xai_stt,web_speech,text")
