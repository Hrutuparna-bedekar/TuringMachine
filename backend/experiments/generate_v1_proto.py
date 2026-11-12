import random
import json
from pathlib import Path

from backend.app.schemas import TuringMachine
from backend.app.simulator import simulate

from backend.experiments.machine_generators import (
    generate_random_machine,
    generate_scan_machine,
    generate_loop_machine,
)

BUDGETS = [50, 200, 1000]


def create_record(machine_id, input_text, result):
    record = {
        "machine_id": machine_id,
        "input": input_text,
        "executed_steps": result.steps,
        "halt_step": result.steps if result.halted_within_limit else None,
        "stop_reason": result.stop_reason
    }

    for budget in BUDGETS:
        record[f"halt_by_{budget}"] = int(
            result.halted_within_limit and result.steps <= budget
        )

    return record

def main():


    # Test our reusable function
    path = Path("examples/scan-to-blank.json")
    data = json.loads(path.read_text(encoding="utf-8"))

    machine = TuringMachine.model_validate(data["machine"])

    result = simulate(
        machine,
        data["input"],
        step_limit=1000,
        trace_limit=10
    )

    record = create_record("M001", data["input"], result)

    print("Generated record:")
    print(json.dumps(record, indent=4))



    print("\nGenerating multiple machine-input records:")

    inputs = ["", "0", "1", "101", "111"]
    records = []
    machines = []


    rng = random.Random(2026)
    state_counts = [rng.randint(3, 15) for _ in range(5)]
    density_rng = random.Random(2027)
    densities = [
        round(density_rng.uniform(0.2, 1.0), 2)
        for _ in range(5)
    ]

    print("Generated densities:", densities)
    print("Generated state counts:", state_counts)

    for i in range(5):
        random_machine = generate_random_machine(
            seed=100 + i,
            num_states=state_counts[i],
            rule_density=densities[i]
        )


        machines.append({
            "machine_id": f"M{i+2:03d}",
            "family": "random_rule_tables",
            "lineage_id": f"random_{100+i}",
            "seed": 100 + i,
            "machine": random_machine.model_dump(mode="json")
        })


        for input_text in inputs:
            result = simulate(
                random_machine,
                input_text,
                step_limit=1000,
                trace_limit=10
            )

            record = create_record(
                machine_id=f"M{i+2:03d}",
                input_text=input_text,
                result=result
            )

            records.append(record)

    print("Total records generated:", len(records))
    print("Unique machine-input pairs:", len({
        (r["machine_id"], r["input"]) for r in records
    }))

    for budget in BUDGETS:
        positive = sum(r[f"halt_by_{budget}"] for r in records)
        negative = len(records) - positive

        print(
            f"Budget {budget}: "
            f"Positive={positive}, Negative={negative}"
        )


    output_dir = Path("data/generated/pilot_small")
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / "runs.jsonl"

    with output_file.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record) + "\n")

    print(f"\nSaved {len(records)} records to {output_file}")

    print("Machine definitions collected:", len(machines))


    machines_file = output_dir / "machines.jsonl"

    with machines_file.open("w", encoding="utf-8") as file:
        for machine_record in machines:
            file.write(json.dumps(machine_record) + "\n")

    print(f"Saved {len(machines)} machines to {machines_file}")


    print("\nTesting different machine sizes:")

    for num_states in [3, 5, 8, 10]:
        test_machine = generate_random_machine(
            seed=42,
            num_states=num_states
        )

        result = simulate(
            test_machine,
            input_text="101",
            step_limit=1000,
            trace_limit=10
        )

        print(
            f"States: {len(test_machine.states)} | "
            f"Transitions: {len(test_machine.transitions)} | "
            f"Steps: {result.steps} | "
            f"Reason: {result.stop_reason}"
        )


    print("\nTesting different transition densities:")

    for density in [0.2, 0.5, 0.8, 1.0]:
        test_machine = generate_random_machine(
            seed=42,
            num_states=8,
            rule_density=density
        )

        possible_rules = (
            (len(test_machine.states) - len(test_machine.final_states))
            * len(test_machine.tape_alphabet)
        )

        actual_density = len(test_machine.transitions) / possible_rules

        result = simulate(
            test_machine,
            input_text="101",
            step_limit=1000,
            trace_limit=10
        )

        print(
            f"Requested density: {density:.1f} | "
            f"Actual density: {actual_density:.2f} | "
            f"Rules: {len(test_machine.transitions)} | "
            f"Steps: {result.steps} | "
            f"Reason: {result.stop_reason}"
        )


    from collections import Counter

    print("\nCurrent dataset diagnostics:")

    stop_counts = Counter(
        record["stop_reason"]
        for record in records
    )

    print("Stop reasons:", dict(stop_counts))

    halt_steps = [
        record["halt_step"]
        for record in records
        if record["halt_step"] is not None
    ]

    print("Longest actual halt:", max(halt_steps, default=None))
    print("Shortest actual halt:", min(halt_steps, default=None))

    scan_machine = generate_scan_machine()

    scan_result = simulate(
        scan_machine,
        input_text="1" * 50,
        step_limit=1000,
        trace_limit=10
    )

    scan_record = create_record("SCAN001", "1" * 50, scan_result)

    print("\nNew scan generator test:")
    print("Steps:", scan_record["executed_steps"])
    print("Labels:", [scan_record[f"halt_by_{b}"] for b in BUDGETS])


    print("\nTesting scan machine with different input lengths:")

    for length in [10, 49, 50, 51, 199, 200, 201, 500]:
        input_text = "1" * length

        result = simulate(
            scan_machine,
            input_text,
            step_limit=1000,
            trace_limit=10
        )

        record = create_record("SCAN001", input_text, result)

        labels = [record[f"halt_by_{b}"] for b in BUDGETS]

        print(
            f"Input length: {length} | "
            f"Halt step: {record['halt_step']} | "
            f"Labels: {labels}"
        )


    # Save the scan machine definition
    scan_machine_record = {
        "machine_id": "SCAN001",
        "family": "scan_to_blank",
        "lineage_id": "scan_v1",
        "seed": None,
        "machine": scan_machine.model_dump(mode="json")
    }

    with machines_file.open("a", encoding="utf-8") as file:
        file.write(json.dumps(scan_machine_record) + "\n")


    # Generate and save five scan-machine runs
    scan_inputs = [10, 49, 50, 200, 500]

    with output_file.open("a", encoding="utf-8") as file:
        for length in scan_inputs:
            input_text = "1" * length

            result = simulate(
                scan_machine,
                input_text,
                step_limit=1000,
                trace_limit=10
            )

            record = create_record("SCAN001", input_text, result)
            file.write(json.dumps(record) + "\n")

    print("\nScan family added successfully!")
    print("Total machines: 6")
    print("Total dataset records: 30")

    loop_machine = generate_loop_machine()
    loop_input = json.loads(
        Path("examples/loop.json").read_text(encoding="utf-8")
    )["input"]

    loop_result = simulate(
        loop_machine,
        input_text=loop_input,
        step_limit=1000,
        trace_limit=10
    )

    loop_record = create_record(
        "LOOP001",
        loop_input,
        loop_result
    )

    print("\nLong-running machine test:")
    print("Steps:", loop_record["executed_steps"])
    print("Stop reason:", loop_record["stop_reason"])
    print("Labels:", [loop_record[f"halt_by_{b}"] for b in BUDGETS])


    loop_machine_record = {
        "machine_id": "LOOP001",
        "family": "long_running",
        "lineage_id": "loop_v1",
        "seed": None,
        "machine": loop_machine.model_dump(mode="json")
    }

    with machines_file.open("a", encoding="utf-8") as file:
        file.write(json.dumps(loop_machine_record) + "\n")

    with output_file.open("a", encoding="utf-8") as file:
        file.write(json.dumps(loop_record) + "\n")

    print("\nLong-running example saved!")

if __name__ == "__main__":
    main()