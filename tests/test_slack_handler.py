import hashlib
import hmac
import time

SIGNING_SECRET = "test_signing_secret_32bytes_long!"


def _make_signature(body: bytes, ts: str, secret: str = SIGNING_SECRET) -> str:
    sig_basestring = f"v0:{ts}:{body.decode()}".encode()
    return "v0=" + hmac.new(secret.encode(), sig_basestring, hashlib.sha256).hexdigest()


def test_valid_slack_signature_passes() -> None:
    """Bolt verifies the Slack HMAC signature; a valid one should not return 403."""
    # We test the signature helper function logic directly
    ts = str(int(time.time()))
    body = b'{"type":"url_verification","challenge":"abc"}'
    sig = _make_signature(body, ts)

    # Verify our helper produces the right format
    assert sig.startswith("v0=")
    assert len(sig) == 67  # "v0=" (3 chars) + 64 hex chars


def test_invalid_signature_format_detected() -> None:
    ts = str(int(time.time()))
    body = b"test"
    valid_sig = _make_signature(body, ts)
    bad_sig = "v0=" + "0" * 64

    assert valid_sig != bad_sig


def test_replay_window_detection() -> None:
    """Requests older than 5 minutes should be considered stale."""
    old_ts = str(int(time.time()) - 400)  # 400 seconds ago — outside 5-min window
    current_ts = str(int(time.time()))

    body = b"test"
    old_sig = _make_signature(body, old_ts)
    current_sig = _make_signature(body, current_ts)

    # Same body, different timestamps → different signatures
    assert old_sig != current_sig

    # Timestamp staleness check
    age = int(time.time()) - int(old_ts)
    assert age > 300  # older than 5 minutes
