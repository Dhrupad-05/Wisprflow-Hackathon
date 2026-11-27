"""Phase 2 voice polish: barge-in, adaptive VAD, and live partial transcripts."""

import threading
from pathlib import Path

import pytest
import uvicorn
from fastapi.testclient import TestClient

from services.api.main import app

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def phase2_server():
    config = uvicorn.Config(app, host="127.0.0.1", port=8769, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(50):
        if server.started:
            break
        threading.Event().wait(0.1)
    if not server.started:
        pytest.fail("phase 2 server did not start")
    yield "http://127.0.0.1:8769"
    server.should_exit = True
    thread.join(timeout=5)


def test_barge_gate_ignores_grace_and_needs_sustained_speech(page, phase2_server):
    page.goto(phase2_server + "/")
    result = page.evaluate(
        """
        async () => {
          const { BargeInMonitor } = await import('/packages/voice/bargein.js');
          let now = 0;
          const monitor = new BargeInMonitor({ clock: () => now });
          monitor.arm();
          const grace = monitor.feed(0.9);
          now = 450;
          const blocks = [];
          for (const at of [450, 470, 520, 560]) {
            now = at;
            blocks.push(monitor.feed(0.25).interrupt);
          }
          now = 600;
          const repeat = monitor.feed(0.25).interrupt;
          monitor.disarm();
          const disarmed = monitor.feed(0.9).interrupt;
          return { gate: grace.gate, graceInterrupt: grace.interrupt, blocks, repeat, disarmed };
        }
        """
    )
    assert result == {
        "gate": "grace",
        "graceInterrupt": False,
        "blocks": [False, False, False, True],
        "repeat": False,
        "disarmed": False,
    }


def test_vad_adapts_to_room_noise_and_gates_short_sounds(page, phase2_server):
    page.goto(phase2_server + "/")
    result = page.evaluate(
        """
        async () => {
          const { VoiceActivityDetector } = await import('/packages/voice/vad.js');
          let now = 0;
          const vad = new VoiceActivityDetector({ clock: () => now });
          const base = vad.dynamicThreshold();
          for (let index = 0; index < 300; index += 1) {
            now += 20;
            vad.feed(0.012);
          }
          const raised = vad.dynamicThreshold();
          const fanSpoke = vad.spoke;
          const roomLevelStarted = vad.feed(0.025, now += 20).started;
          const speech = [];
          for (const level of [0.2, 0.2, 0.2]) {
            now += 20;
            speech.push(vad.feed(level).started);
          }

          let short = 0;
          const gated = new VoiceActivityDetector({ minSpeechMs: 150, clock: () => short });
          const early = [gated.feed(0.2).started];
          short = 40; early.push(gated.feed(0.2).started);
          short = 120; early.push(gated.feed(0.2).started);
          short = 200; early.push(gated.feed(0.2).started);
          return {
            base: Math.round(base * 1000),
            raised: Math.round(raised * 1000),
            fanSpoke,
            roomLevelStarted,
            speechStarted: speech.includes(true),
            early,
            finalStarted: early.at(-1)
          };
        }
        """
    )
    assert result["base"] == 18
    assert result["raised"] > result["base"]
    assert result["fanSpoke"] is False
    assert result["roomLevelStarted"] is False
    assert result["speechStarted"] is True
    assert result["early"] == [False, False, False, True]


def test_endpointing_partial_does_not_arm_and_edit_is_what_sends(page, phase2_server):
    page.goto(phase2_server + "/")
    result = page.evaluate(
        """
        async () => {
          const { EndpointingEngine } = await import('/packages/voice/endpointing.js');
          let now = 0;
          const timers = [];
          const ended = [];
          const engine = new EndpointingEngine({
            clock: () => now,
            setTimer: (fn, ms) => { timers.push({ fn, ms }); return timers.length; },
            clearTimer: () => {},
            onEnd: (value) => ended.push(value)
          });
          engine.begin({ fieldType: 'amount' });
          engine.partial('paanch');
          const partialArmed = timers.length;
          engine.update('paanch hazaar');
          const firstWait = timers.at(-1).ms;
          engine.extend(5000);
          const extended = timers.at(-1).ms;
          engine.partial('paanch hazaar rupaye');
          engine.finish('tap');
          return { partialArmed, firstWait, extended, sent: ended.at(-1) };
        }
        """
    )
    assert result == {
        "partialArmed": 0,
        "firstWait": 2500,
        "extended": 5000,
        "sent": {"text": "paanch hazaar rupaye", "reason": "tap", "elapsed": 0},
    }


def test_phase2_wiring_is_present_and_served():
    app_js = (ROOT / "apps/web/app.js").read_text(encoding="utf-8")
    html = (ROOT / "apps/web/index.html").read_text(encoding="utf-8")
    css = (ROOT / "apps/web/styles.css").read_text(encoding="utf-8")
    assert "BargeInMonitor" in app_js
    assert "startBargeMonitor" in app_js
    assert "adoptBargeMonitor" in app_js
    assert "stopSpeaking" in app_js
    assert "updatePartial" in app_js
    assert 'id="live"' in html
    assert 'id="barge-in"' in html
    assert ".live-input" in css

    response = TestClient(app).get("/packages/voice/bargein.js")
    assert response.status_code == 200
    assert "BargeInMonitor" in response.text
