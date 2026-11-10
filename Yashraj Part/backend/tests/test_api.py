"""Integration and HTTP boundary tests for the FastAPI Turing Machine Simulator API."""

import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


@pytest.fixture
def valid_machine_payload() -> dict:
    return {
        "machine": {
            "states": [
                {"id": "q0", "name": "Start"},
                {"id": "q_halt", "name": "Halt"},
            ],
            "input_alphabet": ["0", "1"],
            "tape_alphabet": ["0", "1", "□"],
            "blank_symbol": "□",
            "start_state": "q0",
            "final_states": ["q_halt"],
            "transitions": [
                {"from_state": "q0", "read": "0", "to_state": "q0", "write": "0", "move": "R"},
                {"from_state": "q0", "read": "1", "to_state": "q0", "write": "1", "move": "R"},
                {"from_state": "q0", "read": "□", "to_state": "q_halt", "write": "□", "move": "R"},
            ],
        },
        "input": "101",
        "step_limit": 50,
    }


class TestHealthEndpoint:
    """Verifies service health check."""

    def test_health_check_returns_ok(self):
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestSimulateEndpointSuccess:
    """Verifies successful simulation execution through the REST API."""

    def test_successful_simulation_response_structure(self, valid_machine_payload):
        response = client.post("/api/simulate", json=valid_machine_payload)
        assert response.status_code == 200
        data = response.json()

        assert "halted_within_limit" in data
        assert data["halted_within_limit"] is True
        assert data["stop_reason"] == "final_state"
        assert data["steps"] == 4
        assert "initial" in data
        assert data["initial"]["state"] == "q0"
        assert data["initial"]["head"] == 0
        assert len(data["initial"]["cells"]) == 3
        assert "trace" in data
        assert len(data["trace"]) == 4


class TestSimulateEndpointValidationErrors:
    """Verifies robust validation error responses (HTTP 422)."""

    def test_invalid_machine_symbol_outside_tape_alphabet(self, valid_machine_payload):
        # Change transition write symbol to 'X' which is not in tape_alphabet
        valid_machine_payload["machine"]["transitions"][0]["write"] = "X"
        response = client.post("/api/simulate", json=valid_machine_payload)
        assert response.status_code == 422
        assert "tape_alphabet" in response.text

    def test_final_state_outgoing_transition_rejected(self, valid_machine_payload):
        # Add an outgoing transition from q_halt
        valid_machine_payload["machine"]["transitions"].append(
            {"from_state": "q_halt", "read": "0", "to_state": "q0", "write": "0", "move": "R"}
        )
        response = client.post("/api/simulate", json=valid_machine_payload)
        assert response.status_code == 422
        assert "Final states must have no outgoing transitions" in response.text

    def test_duplicate_transition_key_rejected(self, valid_machine_payload):
        # Add duplicate rule for (q0, '0')
        valid_machine_payload["machine"]["transitions"].append(
            {"from_state": "q0", "read": "0", "to_state": "q0", "write": "1", "move": "L"}
        )
        response = client.post("/api/simulate", json=valid_machine_payload)
        assert response.status_code == 422
        assert "Non-deterministic machine" in response.text

    def test_invalid_input_symbol_rejected(self, valid_machine_payload):
        # Input contains 'A' which is not in input_alphabet
        valid_machine_payload["input"] = "10A1"
        response = client.post("/api/simulate", json=valid_machine_payload)
        assert response.status_code == 422
        assert "input_alphabet" in response.text

    @pytest.mark.parametrize("invalid_limit", [-1, 1001, 25.5, True, "50"])
    def test_invalid_step_limit_rejected(self, valid_machine_payload, invalid_limit):
        valid_machine_payload["step_limit"] = invalid_limit
        response = client.post("/api/simulate", json=valid_machine_payload)
        assert response.status_code == 422

    def test_step_limit_zero_accepted_via_api(self, valid_machine_payload):
        valid_machine_payload["step_limit"] = 0
        response = client.post("/api/simulate", json=valid_machine_payload)
        assert response.status_code == 200
        data = response.json()
        assert data["steps"] == 0
        assert data["stop_reason"] == "step_limit"
        assert data["halted_within_limit"] is False

    def test_malformed_json_payload_rejected(self):
        response = client.post(
            "/api/simulate",
            content=b"{invalid json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422


class TestApiProtectionsAndCORS:
    """Verifies security limits (413 body size) and CORS configuration."""

    def test_oversized_request_content_length_rejected(self):
        # Create payload larger than 256 KiB (262,144 bytes)
        oversized_bytes = b"A" * 270000
        response = client.post(
            "/api/simulate",
            content=oversized_bytes,
            headers={"Content-Length": str(len(oversized_bytes))},
        )
        assert response.status_code == 413
        assert "Request body exceeds maximum permitted size" in response.json()["detail"]

    def test_oversized_request_streamed_rejected(self):
        oversized_bytes = b"A" * 270000
        # Send without content-length header to trigger streamed byte tracking
        response = client.post(
            "/api/simulate",
            content=oversized_bytes,
            headers={"Transfer-Encoding": "chunked"},
        )
        assert response.status_code == 413

    def test_cors_headers_present(self):
        response = client.options(
            "/api/simulate",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == "*"
