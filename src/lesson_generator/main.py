"""Command line entry point: python -m lesson_generator.main --topic ..."""
import argparse
from .graph.workflow import run_workflow

def main(argv=None):
    parser = argparse.ArgumentParser(description="Generate and quality-check a beginner lesson")
    parser.add_argument("--topic", required=True)
    parser.add_argument("--output-dir", default="outputs")
    parser.add_argument("--demo-failure", action="store_true", help="Inject a known false claim into the first draft")
    args = parser.parse_args(argv)
    try:
        result = run_workflow(args.topic, output_dir=args.output_dir, demo_failure=args.demo_failure)
    except Exception as exc:
        parser.exit(2, f"Workflow failed: {type(exc).__name__}: {exc}\n")
    print(f"Attempts: {result.get('attempt', 0)}")
    report = result.get("evaluation")
    print(f"Status: {report.overall_status if report else 'FAIL'}")
    print(f"Outcome: {result.get('status', 'failed')}")
    print(f"Outputs: Available at{result.get('output_dir', args.output_dir)} directory")
    if result.get("status") == "rejected":
        print("The lesson did not meet the quality threshold.")
    return 0 if result.get("status") == "approved" else 1

if __name__ == "__main__":
    raise SystemExit(main())
