import argparse
import json
from pathlib import Path
import sys
from . import __version__
from .core import InputError, analyze, exit_code, read_workflow, sarif


def main(argv=None):
    parser = argparse.ArgumentParser(description='Preflight direct GitHub Actions artifact names and producer/consumer ordering.')
    parser.add_argument('workflow', type=Path)
    parser.add_argument('--version', action='version', version=__version__)
    parser.add_argument('--format', choices=('text', 'json', 'sarif'), default='text')
    parser.add_argument('--modern-ref', action='append', default=[], metavar='EXACT_USES',
                        help='Assert a reviewed SHA/custom ref uses v4+ immutable artifact semantics (repeatable).')
    args = parser.parse_args(argv)
    try:
        report = analyze(read_workflow(args.workflow), modern_refs=args.modern_ref)
    except (OSError, ValueError, RecursionError) as exc:
        message = str(exc) if isinstance(exc, InputError) else type(exc).__name__ + ': cannot analyze input.'
        print(json.dumps({'schema_version': 1, 'tool': 'artifactspan', 'error': message}) if args.format != 'text' else message, file=sys.stderr)
        return 2
    if args.format == 'json':
        print(json.dumps(report, indent=2, ensure_ascii=True))
    elif args.format == 'sarif':
        print(json.dumps(sarif(report, args.workflow.as_posix()), indent=2, ensure_ascii=True))
    else:
        print(f"artifactspan: {len(report['events'])} expanded steps, {len(report['findings'])} findings, {len(report['unknowns'])} unknowns")
        for item in report['findings']:
            print(json.dumps(item, ensure_ascii=True))
        for item in report['unknowns']:
            print('UNKNOWN ' + json.dumps(item, ensure_ascii=True))
    return exit_code(report)
