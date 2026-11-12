
import json

from backend.app.schemas import TuringMachine
from backend.app.simulator import simulate

with open("examples/scan-to-blank.json", "r", encoding="utf-8") as file:
    data = json.load(file)

print("Example loaded successfully!")
print("Available fields:", list(data.keys()))


machine = TuringMachine.model_validate(data["machine"])

result = simulate(
    machine=machine,
    input_text=data["input"],
    step_limit=1000,
    trace_limit=10
)

print("Input:", repr(data["input"]))
print("Halted:", result.halted_within_limit)
print("Stop reason:", result.stop_reason)
print("Steps executed:", result.steps)
print("Trace events recorded:", len(result.trace))


budgets = [50, 200, 1000]

for budget in budgets:
    label = int(
        result.halted_within_limit and result.steps <= budget
    )
    print(f"Halt by {budget}: {label}")


record = {
    "machine_id": "M001",
    "input": data["input"],
    "halt_step": result.steps if result.halted_within_limit else None,
    "stop_reason": result.stop_reason,
    "halt_by_50": int(result.halted_within_limit and result.steps <= 50),
    "halt_by_200": int(result.halted_within_limit and result.steps <= 200),
    "halt_by_1000": int(result.halted_within_limit and result.steps <= 1000),
}

print("\nFirst dataset record:")
print(json.dumps(record, indent=4))


from pathlib import Path

output_dir = Path("data/generated/smoke")
output_dir.mkdir(parents=True, exist_ok=True)

output_file = output_dir / "runs.jsonl"

print(f"\nDataset saved to: {output_file}")


inputs = ["", "0", "1", "101", "111"]

print("\nTesting multiple inputs:")

for input_text in inputs:
    output = simulate(
        machine,
        input_text,
        step_limit=1000,
        trace_limit=10
    )

    print(
        f"Input: {input_text!r}, "
        f"Steps: {output.steps}, "
        f"Reason: {output.stop_reason}"
    )


records = []

for input_text in inputs:
    output = simulate(
        machine,
        input_text,
        step_limit=1000,
        trace_limit=10
    )

    new_record = {
        "machine_id": "M001",
        "input": input_text,
        "halt_step": output.steps if output.halted_within_limit else None,
        "stop_reason": output.stop_reason,
        "halt_by_50": int(output.halted_within_limit and output.steps <= 50),
        "halt_by_200": int(output.halted_within_limit and output.steps <= 200),
        "halt_by_1000": int(output.halted_within_limit and output.steps <= 1000)
    }

    records.append(new_record)

with output_file.open("w", encoding="utf-8") as file:
    for item in records:
        file.write(json.dumps(item) + "\n")

print(f"\nSuccessfully saved {len(records)} dataset records!")


with open("examples/loop.json", "r", encoding="utf-8") as file:
    loop_data = json.load(file)

loop_machine = TuringMachine.model_validate(loop_data["machine"])

loop_result = simulate(
    loop_machine,
    input_text=loop_data["input"],
    step_limit=1000,
    trace_limit=10
)

print("\nLoop machine result:")
print("Halted:", loop_result.halted_within_limit)
print("Stop reason:", loop_result.stop_reason)
print("Steps executed:", loop_result.steps)

for budget in [50, 200, 1000]:
    label = int(
        loop_result.halted_within_limit
        and loop_result.steps <= budget
    )
    print(f"Halt by {budget}: {label}")


loop_record = {
    "machine_id": "M002",
    "input": loop_data["input"],
    "halt_step": (
        loop_result.steps
        if loop_result.halted_within_limit
        else None
    ),
    "stop_reason": loop_result.stop_reason,
    "halt_by_50": int(
        loop_result.halted_within_limit and loop_result.steps <= 50
    ),
    "halt_by_200": int(
        loop_result.halted_within_limit and loop_result.steps <= 200
    ),
    "halt_by_1000": int(
        loop_result.halted_within_limit and loop_result.steps <= 1000
    )
}

with output_file.open("a", encoding="utf-8") as file:
    file.write(json.dumps(loop_record) + "\n")

print("\nLoop record added successfully!")


import random


def generate_random_machine(seed):
    rng = random.Random(seed)

    state_ids = ["q0", "q1", "q2", "q3"]
    symbols = ["0", "1", "□"]

    transitions = []

    for state in state_ids[:-1]:
        for symbol in symbols:
            if rng.random() < 0.8:
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
        "final_states": ["q3"],
        "transitions": transitions
    }

    return TuringMachine.model_validate(machine_data)

random_machine = generate_random_machine(42)

print("\nGenerated random machine:")
print(random_machine.model_dump_json(indent=2))


random_result = simulate(
    random_machine,
    input_text="101",
    step_limit=1000,
    trace_limit=10
)

print("\nRandom machine simulation:")
print("Halted:", random_result.halted_within_limit)
print("Stop reason:", random_result.stop_reason)
print("Steps:", random_result.steps)
print("Trace length:", len(random_result.trace))


print("\nGenerating 10 random machines:")

for machine_number in range(10):
    generated_machine = generate_random_machine(
        seed=100 + machine_number
    )

    result = simulate(
        generated_machine,
        input_text="101",
        step_limit=1000,
        trace_limit=10
    )

    print(
        f"M{machine_number + 3:03d} | "
        f"Steps: {result.steps} | "
        f"Reason: {result.stop_reason}"
    )


print("\nTesting 50 machine-input pairs:")

new_records = []

for i in range(10):
    machine = generate_random_machine(seed=100 + i)

    for input_text in ["", "0", "1", "101", "111"]:
        result = simulate(
            machine,
            input_text,
            step_limit=1000,
            trace_limit=10
        )

        new_records.append({
            "machine_id": f"M{i+3:03d}",
            "input": input_text,
            "steps": result.steps,
            "stop_reason": result.stop_reason,
            "halt_by_50": int(result.halted_within_limit and result.steps <= 50),
            "halt_by_200": int(result.halted_within_limit and result.steps <= 200),
            "halt_by_1000": int(result.halted_within_limit and result.steps <= 1000)
        })

print("Total examples:", len(new_records))
print("Maximum steps:", max(r["steps"] for r in new_records))

for budget in [50, 200, 1000]:
    positives = sum(r[f"halt_by_{budget}"] for r in new_records)
    negatives = len(new_records) - positives

    print(f"Budget {budget}: Positive={positives}, Negative={negatives}")


from collections import Counter

print("\nDataset diagnostics:")

reasons = Counter(
    r["stop_reason"] for r in new_records
)

print("Stop reasons:", dict(reasons))

print("\nPairs reaching step limit:")

for r in new_records:
    if r["stop_reason"] == "step_limit":
        print(r["machine_id"], repr(r["input"]))

halt_steps = [
    r["steps"]
    for r in new_records
    if r["stop_reason"] != "step_limit"
]

print("\nLongest observed halt:", max(halt_steps, default=None))


print("\nTesting delayed halts:")

scan_machine = TuringMachine.model_validate(data["machine"])

delayed_records = []

for length in [49, 50, 199, 200, 500]:
    input_text = "1" * length

    output = simulate(
        scan_machine,
        input_text,
        step_limit=1000,
        trace_limit=10
    )

    record = {
        "machine_id": "M001",
        "input": input_text,
        "halt_step": output.steps if output.halted_within_limit else None,
        "stop_reason": output.stop_reason,
        "halt_by_50": int(output.halted_within_limit and output.steps <= 50),
        "halt_by_200": int(output.halted_within_limit and output.steps <= 200),
        "halt_by_1000": int(output.halted_within_limit and output.steps <= 1000)
    }

    delayed_records.append(record)

    print(
        f"Length: {length} | "
        f"Steps: {output.steps} | "
        f"Labels: {[record['halt_by_50'], record['halt_by_200'], record['halt_by_1000']]}"
    )

with output_file.open("a", encoding="utf-8") as file:
    for record in delayed_records:
        file.write(json.dumps(record) + "\n")

print(f"\nSaved {len(delayed_records)} delayed-halting records!")
