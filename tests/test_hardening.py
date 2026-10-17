"""Hardening ported from the video production graph (vpg): an anchored, write-ahead ledger, one durable unit per human
action, refusal of concurrent changes and of special files. Each test fails on the engine before the port."""

from __future__ import annotations

import json
import os
import signal
from contextlib import contextmanager
from pathlib import Path

import pytest

from pdg.cli import main
from pdg.engine import Engine, EngineError, ledger_health
from pdg.executors import ScriptedExecutor
from pdg.models import NodeStatus
from pdg.provenance import Ledger, LedgerBehind
from pdg.util import ConcurrentChange, NotRegularFile, read_json, sha256_file

from .conftest import copy_example

GATE = "n03_problem_definition"
LOOP_GATE = "n05_scope_success"   # rejecting it fires E10 back to n04_requirements


def _at_gate(tmp_path: Path, gate: str = GATE) -> tuple[Path, Engine]:
    """A real (non-dry-run) project whose scripted agents have run up to a human gate."""
    proj = copy_example(tmp_path / "p", dry_run=False)
    eng = Engine(proj, executor=ScriptedExecutor(proj / "fixtures"))
    eng.run(max_steps=100)
    if gate == LOOP_GATE:
        eng.decide(GATE, "approved", "Wei", "The job and the pain are right.")
        eng.run(max_steps=100)
    assert eng.rt(gate).status == NodeStatus.WAITING_HUMAN
    return proj, eng


def _ledger(proj: Path) -> Path:
    return proj / ".pdg" / "ledger.jsonl"


def _events(proj: Path, type_: str | None = None) -> list[dict]:
    return list(Ledger(_ledger(proj), read_only=True).events(type_))


def _runtime(proj: Path) -> dict:
    return read_json(proj / ".pdg" / "state.json")["runtime"]


@contextmanager
def _no_hang(seconds: int = 10):
    """Fail instead of hanging forever if an open blocks (a named pipe)."""
    def boom(*_):
        raise TimeoutError(f"blocked for {seconds}s")
    old = signal.signal(signal.SIGALRM, boom)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


# ------------------------------------------------------------------------------------------------ the ledger's anchor
def test_a_ledger_cut_short_at_its_end_is_refused_until_a_named_human_accepts_the_loss(tmp_path, capsys):
    proj, eng = _at_gate(tmp_path)
    recorded = _runtime(proj)["ledger_tail"][0]
    lines = _ledger(proj).read_text().splitlines(keepends=True)
    _ledger(proj).write_text("".join(lines[:-3]))                          # the last three events are gone
    assert Ledger(_ledger(proj), read_only=True).verify()[0]               # the chain alone cannot see it …
    ok, _, why = ledger_health(_ledger(proj), _runtime(proj))
    assert not ok and "ends before event" in why                           # … the anchor in the saved state can
    assert main(["ledger-verify", str(proj)]) == 1 and "BROKEN" in capsys.readouterr().out
    before = _ledger(proj).read_bytes()
    with pytest.raises(EngineError, match="accept-ledger-break"):
        Engine(proj)
    assert _ledger(proj).read_bytes() == before                            # refusing wrote nothing
    with pytest.raises(EngineError, match="named human"):
        Engine(proj, accept_ledger_break=("agent:orchestrator", "fine"))
    with pytest.raises(EngineError, match="reason"):
        Engine(proj, accept_ledger_break=("Wei", "  "))
    assert main(["accept-ledger-break", str(proj), "--actor", "Wei", "--reason", "no backup; checked by hand"]) == 0
    brk = _runtime(proj)["ledger_breaks"]
    assert len(brk) == 1 and brk[0]["actor"] == "Wei" and brk[0]["recorded_seq"] == recorded
    assert brk[0]["lost_after_seq"] == recorded - 3 and brk[0]["resumes_at_seq"] == recorded - 2   # what really survived
    assert [e["data"]["actor"] for e in _events(proj, "ledger_break_accepted")] == ["Wei"]
    capsys.readouterr()
    assert main(["ledger-verify", str(proj)]) == 0 and "break accepted by Wei" in capsys.readouterr().out
    again = Engine(proj, executor=ScriptedExecutor(proj / "fixtures"))     # the run continues …
    with pytest.raises(EngineError, match="no break to accept"):
        Engine(proj, accept_ledger_break=("Wei", "again"))
    again.decide(GATE, "approved", "Wei", "Right problem.")
    assert ledger_health(_ledger(proj), _runtime(proj))[0]                 # … and the break stays on the record
    assert "break accepted by Wei" in ledger_health(_ledger(proj), _runtime(proj))[2]


def test_a_replaced_ledger_is_refused_even_when_its_chain_is_valid(tmp_path):
    proj, eng = _at_gate(tmp_path)
    n = len(_events(proj))
    _ledger(proj).unlink()
    forged = Ledger(_ledger(proj))
    for i in range(n):                                                     # same length, different events
        forged.append("forged", i=i)
    assert Ledger(_ledger(proj), read_only=True).verify()[0]
    with pytest.raises(EngineError, match="rewritten"):
        Engine(proj)


def test_a_rollback_never_erases_an_accepted_ledger_break(tmp_path):
    proj, eng = _at_gate(tmp_path)
    lines = _ledger(proj).read_text().splitlines(keepends=True)
    _ledger(proj).write_text("".join(lines[:-2]))
    eng = Engine(proj, executor=ScriptedExecutor(proj / "fixtures"), accept_ledger_break=("Wei", "no backup"))
    first = eng.state.history.checkpoints[0].seq
    eng.rollback(first, "Wei")
    assert len(_runtime(proj)["ledger_breaks"]) == 1


# ------------------------------------------------------------------------------------------------ durable human actions
def test_a_decision_that_fails_midway_leaves_nothing_behind(tmp_path, monkeypatch):
    proj, eng = _at_gate(tmp_path, LOOP_GATE)
    state_before, ledger_before = (proj / ".pdg" / "state.json").read_bytes(), _ledger(proj).read_bytes()

    def crash(*a, **k):
        raise RuntimeError("the process died while the loop fired")

    monkeypatch.setattr(eng, "invalidate", crash)
    with pytest.raises(RuntimeError):
        eng.decide(LOOP_GATE, "rejected", "Wei", "Add a guardrail on wrong releases.")
    assert (proj / ".pdg" / "state.json").read_bytes() == state_before      # no half decision was saved …
    assert _ledger(proj).read_bytes() == ledger_before                      # … or ledgered
    assert eng.rt(LOOP_GATE).status == NodeStatus.WAITING_HUMAN              # and memory is back as it was
    monkeypatch.undo()
    eng.decide(LOOP_GATE, "rejected", "Wei", "Add a guardrail on wrong releases.")
    assert [e["data"]["decision"] for e in _events(proj, "decision") if e["data"]["node"] == LOOP_GATE] == ["rejected"]
    assert eng.rt("n04_requirements").status == NodeStatus.STALE             # the loop fired this time


def test_a_decision_whose_ledger_write_fails_is_saved_once_and_written_on_the_next_open(tmp_path, monkeypatch):
    proj, eng = _at_gate(tmp_path)

    def disk_full(self, text):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(Ledger, "_write", disk_full)
    with pytest.raises(LedgerBehind, match="don't repeat the action"):
        eng.decide(GATE, "approved", "Wei", "The job and the pain are right.")
    monkeypatch.undo()
    rt = _runtime(proj)
    assert rt["nodes"][GATE]["status"] == "PASSED" and rt["pending_ledger"]   # saved, with its events (write-ahead)
    assert not [e for e in _events(proj, "decision") if e["data"]["node"] == GATE]
    ok, _, why = ledger_health(_ledger(proj), rt)
    assert ok and "pending" in why                                          # behind, not broken
    with pytest.raises(LedgerBehind):
        eng.ledger.append("more")                                           # this engine stops appending
    reopened = Engine(proj, executor=ScriptedExecutor(proj / "fixtures"))
    assert reopened.recovered_ledger == len(rt["pending_ledger"])
    assert len([e for e in _events(proj, "decision") if e["data"]["node"] == GATE]) == 1
    assert Engine(proj).recovered_ledger == 0                               # recovery is idempotent
    reopened.run(max_steps=20)
    assert ledger_health(_ledger(proj), _runtime(proj))[0]
    assert len([e for e in _events(proj, "decision") if e["data"]["node"] == GATE]) == 1


def test_the_cli_says_a_saved_action_is_waiting_for_its_ledger(tmp_path, monkeypatch, capsys):
    proj, eng = _at_gate(tmp_path)
    monkeypatch.setattr(Ledger, "write_lines", lambda self, lines: (_ for _ in ()).throw(OSError(5, "I/O error")))
    code = main(["approve", str(proj), GATE, "--actor", "Wei", "--reason", "Right problem."])
    assert code == 4 and "saved, but the ledger is behind" in capsys.readouterr().out
    monkeypatch.undo()
    assert Engine(proj).recovered_ledger > 0


def test_a_decision_cites_its_own_ledger_event_even_with_feedback(tmp_path):
    proj, eng = _at_gate(tmp_path)
    eng.decide(GATE, "approved", "Wei", "Right problem.", feedback=["name the queue owner", "keep the wording plain"])
    d = eng.state.history.decisions[-1]
    seq = int(d.evidence[0].split(":")[1])
    cited = next(e for e in _events(proj) if e["seq"] == seq)
    assert cited["type"] == "decision" and cited["data"]["node"] == GATE


def test_a_rollback_that_cannot_save_puts_the_control_documents_back(tmp_path, monkeypatch):
    proj, eng = _at_gate(tmp_path)
    eng.decide(GATE, "approved", "Wei", "Right problem.")
    eng.run(max_steps=100)
    first = eng.state.history.checkpoints[0].seq                           # before any control document was written
    live = {p.name: p.read_bytes() for p in (proj / "controls").glob("*.md")}
    state_before = (proj / ".pdg" / "state.json").read_bytes()

    def no_save():
        raise OSError(30, "Read-only file system")

    monkeypatch.setattr(eng, "_write_state", no_save)
    with pytest.raises(OSError):
        eng.rollback(first, "Wei")
    assert {p.name: p.read_bytes() for p in (proj / "controls").glob("*.md")} == live
    assert (proj / ".pdg" / "state.json").read_bytes() == state_before
    assert not eng.controls.drift()


# ------------------------------------------------------------------------------------------------ concurrent changes
def test_a_second_engine_on_the_same_run_cannot_overwrite_the_first(tmp_path):
    proj, a = _at_gate(tmp_path)
    b = Engine(proj, executor=ScriptedExecutor(proj / "fixtures"))         # e.g. a process that skipped the lock
    b.decide(GATE, "approved", "Wei", "Right problem.")
    state_after_b, ledger_after_b = (proj / ".pdg" / "state.json").read_bytes(), _ledger(proj).read_bytes()
    with pytest.raises(ConcurrentChange):
        a.decide(GATE, "rejected", "Wei", "Wrong problem.")                # a's view of the state is stale
    with pytest.raises(ConcurrentChange):
        a.ledger.append("probe")                                            # and so is its view of the ledger
    assert (proj / ".pdg" / "state.json").read_bytes() == state_after_b    # b's decision survives …
    assert _ledger(proj).read_bytes() == ledger_after_b                     # … and nothing of a's was written
    assert [e["data"]["decision"] for e in _events(proj, "decision")] == ["approved"]


def test_a_ledger_changed_behind_an_open_ledger_is_not_appended_to(tmp_path):
    path = tmp_path / "ledger.jsonl"
    led = Ledger(path)
    led.append("event", i=1)
    with path.open("a") as f:
        f.write('{"seq": 2, "half')                                        # another writer, cut short
    with pytest.raises(ConcurrentChange):
        led.append("event", i=2)
    again = Ledger(path)                                                    # reopening sets the fragment aside …
    again.append("event", i=2)
    ok, n, _ = again.verify()
    assert ok and n == 2 and list(tmp_path.glob("ledger.jsonl.torn-*"))   # … and the chain continues


# ------------------------------------------------------------------------------------------------ special files
def test_special_files_are_refused_instead_of_hanging(tmp_path, capsys):
    proj, eng = _at_gate(tmp_path)
    ledger = _ledger(proj)
    ledger.unlink()
    os.mkfifo(ledger)
    with _no_hang():
        with pytest.raises(NotRegularFile):
            Engine(proj)
        with pytest.raises(NotRegularFile):
            sha256_file(ledger)
        assert main(["ledger-verify", str(proj)]) in (1, 4)
    state = proj / ".pdg" / "state.json"
    state.unlink()
    os.mkfifo(state)
    with _no_hang():
        assert main(["status", str(proj)]) == 4
    assert "not a regular file" in capsys.readouterr().out


def test_a_lock_file_that_is_not_a_regular_file_is_refused_instead_of_hanging(tmp_path, capsys):
    proj, eng = _at_gate(tmp_path)
    lock = proj / ".pdg" / "lock"
    lock.unlink(missing_ok=True)
    os.mkfifo(lock)
    with _no_hang():
        assert main(["approve", str(proj), GATE, "--actor", "Wei", "--reason", "Right problem."]) == 4
    assert "not a regular file" in capsys.readouterr().out
    assert not [e for e in _events(proj, "decision") if e["data"]["node"] == GATE]


def test_the_release_check_refuses_a_ledger_that_lost_its_end(tmp_path, fast_browser):
    from pdg.context import NodeContext
    from pdg.gating import release_verify
    proj = copy_example(tmp_path / "p")
    eng = Engine(proj)
    eng.run(max_steps=400)
    assert eng.state.runtime.status.value == "RUN_PASS"
    node = eng.node("n18_final_verification")
    work = tmp_path / "recheck"
    work.mkdir()
    assert not release_verify(NodeContext(eng, node, 99, work, "t", "")).errors
    lines = _ledger(proj).read_text().splitlines(keepends=True)
    _ledger(proj).write_text("".join(lines[:-5]))                          # cut while the engine is open
    (tmp_path / "recheck2").mkdir()
    res = release_verify(NodeContext(eng, node, 100, tmp_path / "recheck2", "t", ""))
    assert any("ledger verifies" in e and "ends before event" in e for e in res.errors)


def test_a_damaged_ledger_line_is_reported_not_a_crash(tmp_path, capsys):
    from pdg.report import write_report
    proj, eng = _at_gate(tmp_path)
    lines = _ledger(proj).read_text().splitlines(keepends=True)
    lines[3] = "this is not json\n"
    _ledger(proj).write_text("".join(lines))
    assert main(["ledger-verify", str(proj)]) == 1
    assert "not a valid event" in capsys.readouterr().out
    html = write_report(proj).read_text()
    assert "BROKEN" in html and "not a valid event" in html


def test_a_lost_tail_with_a_pending_action_can_be_accepted_and_the_action_is_rechained(tmp_path, monkeypatch):
    """N5a: the last human action was saved but its events were not written, and the ledger's end was also cut. The
    pending events no longer continue the ledger; only an accepted break lets the run continue, and the action's
    events are written again after it, exactly once."""
    proj, eng = _at_gate(tmp_path)
    monkeypatch.setattr(Ledger, "_write", lambda self, text: (_ for _ in ()).throw(OSError(28, "No space left")))
    with pytest.raises(LedgerBehind):
        eng.decide(GATE, "approved", "Wei", "Right problem.")
    monkeypatch.undo()
    pending = len(_runtime(proj)["pending_ledger"])
    lines = _ledger(proj).read_text().splitlines(keepends=True)
    _ledger(proj).write_text("".join(lines[:-2]))
    with pytest.raises(EngineError, match="accept-ledger-break"):
        Engine(proj)
    Engine(proj, accept_ledger_break=("Wei", "disk failure; no backup"))
    brk = _runtime(proj)["ledger_breaks"][0]
    assert brk["rechained"] == pending and brk["lost_after_seq"] == len(lines) - 2
    decisions = [e for e in _events(proj, "decision") if e["data"]["node"] == GATE]
    assert len(decisions) == 1 and "rechained_from_seq" in decisions[0]["data"]
    cited = [d for d in read_json(proj / ".pdg" / "state.json")["history"]["decisions"] if d["node"] == GATE]
    assert cited[-1]["evidence"] == [f"ledger:{decisions[0]['seq']}"]                 # it cites the re-chained event
    ok, _, why = ledger_health(_ledger(proj), _runtime(proj))
    assert ok and "written again after the break" in why


def test_a_damaged_chain_cannot_be_accepted_as_a_lost_tail(tmp_path):
    """N5b: accepting lost events cannot repair a damaged middle line, so the engine refuses and says to restore."""
    proj, eng = _at_gate(tmp_path)
    lines = _ledger(proj).read_text().splitlines(keepends=True)
    lines[3] = "this is not an event\n"
    _ledger(proj).write_text("".join(lines))
    for accept in (None, ("Wei", "no backup")):
        with pytest.raises(EngineError, match="restore .pdg/ledger.jsonl from a backup"):
            Engine(proj, accept_ledger_break=accept)
    assert not _runtime(proj)["ledger_breaks"]


def test_an_unwritable_ledger_at_open_is_refused_cleanly_not_a_traceback(tmp_path, monkeypatch, capsys):
    proj, eng = _at_gate(tmp_path)
    monkeypatch.setattr(Ledger, "_write", lambda self, text: (_ for _ in ()).throw(OSError(28, "No space left")))
    with pytest.raises(LedgerBehind):
        eng.decide(GATE, "approved", "Wei", "Right problem.")
    monkeypatch.undo()
    _ledger(proj).chmod(0o444)
    try:
        assert main(["run", str(proj)]) == 4
    finally:
        _ledger(proj).chmod(0o644)
    assert "could not read or write" in capsys.readouterr().out
    assert Engine(proj).recovered_ledger > 0                                          # once writable, it catches up


def test_a_ledger_stamp_rides_on_every_event_without_overriding_its_own_fields(tmp_path):
    from pdg.provenance import Ledger
    led = Ledger(tmp_path / "ledger.jsonl")
    led.stamp = {"grant": "DL-004", "grantor": "Wei"}
    a = led.append("decision", node="n03", grant="DL-009")
    led.stamp = {}
    b = led.append("note", text="after")
    assert a["data"] == {"node": "n03", "grant": "DL-009", "grantor": "Wei"}
    assert "grantor" not in b["data"]
    assert led.verify()[0]
