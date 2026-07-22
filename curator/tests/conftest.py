"""Shared test fixtures for curator tests."""
import struct


def write_minimal_aiff(path: str) -> None:
    """Write a minimal but valid AIFF file (silent, 0 sample frames).

    Python's stdlib `aifc` module (which used to make this trivial) was
    removed in 3.13, so this hand-builds the two mandatory chunks
    (COMM + SSND) mutagen needs to recognize the file as AIFF.
    """
    comm_data = struct.pack(">hlh", 1, 0, 8) + bytes(
        [0x40, 0x0E, 0xAC, 0x44, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
    )  # 1 channel, 0 frames, 8-bit, ~44100Hz (80-bit extended float)
    comm_chunk = b"COMM" + struct.pack(">I", len(comm_data)) + comm_data

    ssnd_data = struct.pack(">II", 0, 0)
    ssnd_chunk = b"SSND" + struct.pack(">I", len(ssnd_data)) + ssnd_data

    form_data = b"AIFF" + comm_chunk + ssnd_chunk
    with open(path, "wb") as f:
        f.write(b"FORM" + struct.pack(">I", len(form_data)) + form_data)


def write_minimal_wav(path: str) -> None:
    """Write a minimal but valid (silent) WAV file using the stdlib `wave` module."""
    import wave

    w = wave.open(path, "wb")
    try:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"")
    finally:
        w.close()
