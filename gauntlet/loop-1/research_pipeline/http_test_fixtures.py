"""In-memory urllib responses with explicit endpoint status for offline tests."""
import io


def response_bytes(raw, status=200):
    response = io.BytesIO(raw)
    response.status = status
    return response
