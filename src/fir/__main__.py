from __future__ import annotations
import argparse
import json
import sys

def draft(text: str) -> int:
    from fir.orchestrator.graph import build_slice_graph, run_text, to_decision
    from fir.statute import registry
    from fir.statute.ipc_bns_map import IpcBnsMap
    from fir.translate import default_translator
    graph = build_slice_graph(classifier=registry.load(), ipc_map=IpcBnsMap.load(), translator=default_translator())
    state = run_text(graph, text)
    print(json.dumps({'decision': to_decision(state).model_dump(mode='json'), 'record': state.get('fir_record'), 'if1_text': state.get('if1_text'), 'errors': state.get('errors', [])}, ensure_ascii=False, indent=2))
    return 0 if not state.get('errors') else 1

def check() -> int:
    from fir.serving.app import capabilities
    print(json.dumps(capabilities().model_dump(), indent=2))
    return 0

def main(argv: list[str] | None=None) -> int:
    parser = argparse.ArgumentParser(prog='tn-fir')
    commands = parser.add_subparsers(dest='command', required=True)
    draft_command = commands.add_parser('draft')
    draft_command.add_argument('text', nargs='?')
    commands.add_parser('check')
    args = parser.parse_args(argv)
    if args.command == 'check':
        return check()
    text = args.text or sys.stdin.read()
    if not text.strip():
        parser.error('A complaint is required')
    return draft(text.strip())
if __name__ == '__main__':
    raise SystemExit(main())
