import json
from pathlib import Path
import random

from backend.app.schemas import TuringMachine

def generate_random_machine(seed, num_states=4, rule_density=0.8):
    rng = random.Random(seed)

    state_ids = [f"q{i}" for i in range(num_states)]
    symbols = ["0", "1", "□"]

    transitions = []

    for state in state_ids[:-1]:
        for symbol in symbols:
            if rng.random() < rule_density:
                rule = {
                    "from_state": state,
                    "read": symbol,
                    "to_state": rng.choice(state_ids),
                    "write": rng.choice(symbols),
                    "move": rng.choice(["L", "R"])
                }
                transitions.append(rule)

    machine_data = {
        "states": [
            {"id": state, "name": state}
            for state in state_ids
        ],
        "input_alphabet": ["0", "1"],
        "tape_alphabet": symbols,
        "blank_symbol": "□",
        "start_state": "q0",
        "final_states": [state_ids[-1]],
        "transitions": transitions
    }

    return TuringMachine.model_validate(machine_data)
def generate_scan_machine():
    machine_data = {
        "states": [
            {"id": "q0", "name": "Scanning"},
            {"id": "q1", "name": "Final"}
        ],
        "input_alphabet": ["0", "1"],
        "tape_alphabet": ["0", "1", "□"],
        "blank_symbol": "□",
        "start_state": "q0",
        "final_states": ["q1"],
        "transitions": [
            {
                "from_state": "q0",
                "read": "0",
                "to_state": "q0",
                "write": "0",
                "move": "R"
            },
            {
                "from_state": "q0",
                "read": "1",
                "to_state": "q0",
                "write": "1",
                "move": "R"
            },
            {
                "from_state": "q0",
                "read": "□",
                "to_state": "q1",
                "write": "□",
                "move": "R"
            }
        ]
    }

    return TuringMachine.model_validate(machine_data)

def generate_loop_machine():
    path = Path("examples/loop.json")
    data = json.loads(path.read_text(encoding="utf-8"))

    return TuringMachine.model_validate(data["machine"])

