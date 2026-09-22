"""Bounded preflight of direct artifact actions, not a workflow execution engine."""
from collections import defaultdict
from dataclasses import dataclass, asdict
import itertools
import json
import math
from pathlib import Path, PureWindowsPath
import re
import yaml
from . import __version__

# ECMAScript String.trim(), used by @actions/core.getInput (not Python's
# broader str.isspace set). Keep BOM and exclude U+0085/control separators.
INPUT_WHITESPACE = '\t\n\v\f\r \u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000\ufeff'


def boolean_input(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        value = value.strip(INPUT_WHITESPACE)
        if value in ('true', 'True', 'TRUE'):
            return True
        if value in ('false', 'False', 'FALSE'):
            return False
    return None


class InputError(ValueError):
    pass


class Unknown(ValueError):
    pass


class MarkedMap(dict):
    line = 1


class Loader(yaml.SafeLoader):
    # YAML 1.1 treats the workflow key "on" as a boolean; GitHub does not.
    yaml_implicit_resolvers = {
        key: [(tag, regex) for tag, regex in resolvers if tag != 'tag:yaml.org,2002:bool']
        for key, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
    }


Loader.add_implicit_resolver('tag:yaml.org,2002:bool', re.compile(r'^(?:true|false|True|False|TRUE|FALSE)$'), list('tTfF'))


def _mapping(loader, node):
    result = MarkedMap()
    result.line = node.start_mark.line + 1
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=True)
        if not isinstance(key, str) or key in result:
            raise InputError(f'Duplicate or non-string YAML key at line {key_node.start_mark.line + 1}.')
        result[key] = loader.construct_object(value_node, deep=True)
    return result


Loader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def read_workflow(path):
    with Path(path).open('rb') as stream:
        raw = stream.read(2 * 1024 * 1024 + 1)
    if len(raw) > 2 * 1024 * 1024:
        raise InputError('Workflow exceeds 2 MiB.')
    try:
        depth = nodes = 0
        for event in yaml.parse(raw):
            nodes += 1
            if isinstance(event, yaml.events.AliasEvent):
                raise InputError('YAML aliases are unsupported; expand anchors before analysis.')
            if isinstance(event, (yaml.events.SequenceStartEvent, yaml.events.MappingStartEvent)):
                depth += 1
            if isinstance(event, (yaml.events.SequenceEndEvent, yaml.events.MappingEndEvent)):
                depth -= 1
            if nodes > 50000 or depth > 50:
                raise InputError('YAML nesting/node limit exceeded.')
        data = yaml.load(raw, Loader=Loader)
    except yaml.YAMLError as exc:
        mark = getattr(exc, 'problem_mark', None)
        raise InputError('Invalid or unsupported YAML' + (f' at line {mark.line + 1}.' if mark else '.')) from exc
    if not isinstance(data, dict) or not isinstance(data.get('jobs'), dict) or not data['jobs']:
        raise InputError('A workflow must contain a nonempty jobs mapping.')
    return data


def _equal(a, b):
    # bool and int must not compare equal as they do in Python.
    return type(a) is type(b) and a == b


def expand_matrix(matrix):
    if matrix is None:
        return [{}]
    if not isinstance(matrix, dict):
        raise Unknown('dynamic_matrix')
    def check_value(value):
        if isinstance(value, dict):
            for child in value.values():
                check_value(child)
        elif isinstance(value, list):
            for child in value:
                check_value(child)
        elif value is not None and not isinstance(value, (str, bool, int, float)):
            raise InputError('Matrix values must be JSON-compatible; quote YAML dates.')
        elif isinstance(value, float) and not math.isfinite(value):
            raise InputError('Matrix numbers must be finite.')
    check_value(matrix)
    axes = {key: values for key, values in matrix.items() if key not in ('include', 'exclude')}
    for key, values in axes.items():
        if not isinstance(values, list) or not values:
            raise Unknown('dynamic_or_empty_matrix_axis')
        for value in values:
            if not isinstance(value, (str, int, float, bool, dict)) or isinstance(value, float) and not math.isfinite(value):
                raise InputError('Unsupported matrix axis value.')
    if math.prod(len(v) for v in axes.values()) > 256:
        raise InputError('Matrix exceeds 256 combinations.')
    include, exclude = matrix.get('include', []), matrix.get('exclude', [])
    if any(not isinstance(value, list) or any(not isinstance(item, dict) for item in value) for value in (include, exclude)):
        raise Unknown('dynamic_matrix_include_or_exclude')
    if not axes:
        if exclude:
            raise InputError('Exclude requires matrix axes.')
        if not include:
            raise InputError('Empty matrix has no combinations.')
        if len(include) > 256:
            raise InputError('Matrix exceeds 256 combinations.')
        return [dict(item) for item in include]
    originals = [dict(zip(axes, values)) for values in itertools.product(*axes.values())]
    originals = [row for row in originals if not any(all(k in row and _equal(row[k], v) for k, v in item.items()) for item in exclude)]
    expanded = [dict(row) for row in originals]
    additions = []
    for item in include:
        applied = False
        for original, row in zip(originals, expanded):
            if all(k not in original or _equal(original[k], v) for k, v in item.items()):
                row.update(item)
                applied = True
        if not applied:
            additions.append(dict(item))
    expanded += additions
    if len(expanded) > 256:
        raise InputError('Matrix exceeds 256 combinations after include.')
    return expanded


def render(value, matrix, job):
    if not isinstance(value, (str, int, float, bool)):
        raise Unknown('non_scalar_artifact_input')
    if isinstance(value, float) or isinstance(value, int) and abs(value) > 2**53 - 1:
        raise Unknown('unsupported_numeric_coercion')
    value = str(value).lower() if isinstance(value, bool) else str(value)
    if '__ARTIFACTSPAN_' in value:
        raise Unknown('reserved_symbol_in_input')

    def replace(match):
        expression = match.group(1).strip()
        if expression in ('github.run_id', 'github.run_number', 'github.run_attempt'):
            return '__ARTIFACTSPAN_' + expression.split('.')[1].upper() + '__'
        if expression == 'github.job':
            return job
        if not re.fullmatch(r'matrix\.[A-Za-z_][\w-]*(?:\.[A-Za-z_][\w-]*)*', expression):
            raise Unknown('dynamic_expression')
        node = matrix
        for part in expression.split('.')[1:]:
            if not isinstance(node, dict) or part not in node:
                raise Unknown('missing_matrix_property')
            node = node[part]
        if not isinstance(node, (str, int, float, bool)):
            raise Unknown('non_scalar_matrix_property')
        if isinstance(node, float) or isinstance(node, int) and abs(node) > 2**53 - 1:
            raise Unknown('unsupported_numeric_coercion')
        if isinstance(node, float) and not math.isfinite(node):
            raise InputError('Matrix number must be finite.')
        # Refuse indirect expressions inside a matrix string; no recursive eval.
        result = str(node).lower() if isinstance(node, bool) else str(node)
        if '${{' in result or '__ARTIFACTSPAN_' in result:
            raise Unknown('dynamic_matrix_value')
        return result

    result = re.sub(r'\$\{\{(.*?)\}\}', replace, value, flags=re.DOTALL)
    if '${{' in result:
        raise Unknown('unclosed_expression')
    return result


def condition(value):
    if value is None:
        return True
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        token = value.strip()
        if token.startswith('${{') and token.endswith('}}'):
            token = token[3:-2].strip()
        if token in ('true', 'success()'):
            return True
        if token == 'false':
            return False
    return None


@dataclass
class Event:
    job: str
    leg: int
    step: int
    line: int
    matrix: dict
    kind: str
    name: str
    conditional: bool
    overwrite: bool = False

    def site(self):
        return {'job': self.job, 'leg': self.leg, 'step': self.step, 'line': self.line, 'matrix': self.matrix}


def analyze(data, *, modern_refs=()):
    jobs = data['jobs']
    if len(jobs) > 256:
        raise InputError('More than 256 jobs.')
    ancestors, dependencies, visiting = {}, {}, set()

    def parents(job_id):
        if job_id in ancestors:
            return ancestors[job_id]
        if job_id in visiting:
            raise InputError('Cycle in job dependencies.')
        if job_id not in jobs or not isinstance(jobs[job_id], dict):
            raise InputError('Missing/invalid job in needs graph.')
        visiting.add(job_id)
        needs = jobs[job_id].get('needs', [])
        needs = [needs] if isinstance(needs, str) else needs
        if not isinstance(needs, list) or any(not isinstance(n, str) for n in needs):
            raise InputError('needs must be a literal job ID or list.')
        dependencies[job_id] = needs
        result = set()
        for needed in needs:
            result.add(needed)
            result.update(parents(needed))
        visiting.remove(job_id)
        ancestors[job_id] = result
        return result

    for job_id in jobs:
        parents(job_id)
    conditions = {}

    def effective_condition(job_id):
        if job_id in conditions:
            return conditions[job_id]
        value = condition(jobs[job_id].get('if'))
        if value is True:
            upstream = [effective_condition(parent) for parent in dependencies[job_id]]
            if any(item is False for item in upstream):
                value = False
            elif any(item is None for item in upstream):
                value = None
        conditions[job_id] = value
        return value

    events, findings, unknowns = [], [], []
    opaque_producers = False

    def unknown(code, job, step=0, line=1):
        item = {'code': code, 'job': job, 'step': step, 'line': line}
        if item not in unknowns:
            unknowns.append(item)

    for job_id, job in jobs.items():
        job_condition = effective_condition(job_id)
        if job_condition is False:
            continue
        if 'uses' in job:
            unknown('reusable_workflow', job_id, line=getattr(job, 'line', 1))
            opaque_producers = True
            continue
        steps = job.get('steps', [])
        if not isinstance(steps, list) or any(not isinstance(s, dict) for s in steps) or len(steps) > 500:
            raise InputError('steps must contain at most 500 mappings.')
        relevant = []
        for index, step in enumerate(steps, 1):
            uses = step.get('uses', '')
            if not isinstance(uses, str):
                raise InputError('uses must be a string.')
            if condition(step.get('if')) is False:
                continue
            if uses.startswith('./'):
                unknown('local_composite_action', job_id, index, getattr(step, 'line', 1))
                opaque_producers = True
            if uses.startswith(('actions/upload-artifact', 'actions/download-artifact')):
                relevant.append((index, step, uses))
        if not relevant:
            continue
        strategy = job.get('strategy', {})
        if not isinstance(strategy, dict):
            raise InputError('strategy must be a mapping.')
        try:
            legs = expand_matrix(strategy.get('matrix'))
        except Unknown as exc:
            unknown(str(exc), job_id, line=getattr(strategy, 'line', 1))
            opaque_producers = True
            continue
        for index, step, uses in relevant:
            line = getattr(step, 'line', 1)
            action, separator, ref = uses.partition('@')
            if action not in ('actions/upload-artifact', 'actions/download-artifact') or not separator:
                unknown('unsupported_artifact_action', job_id, index, line)
                opaque_producers = True
                continue
            match = re.fullmatch(r'v(\d+)(?:\.\d+){0,2}', ref)
            maximum = 7 if action.endswith('upload-artifact') else 8
            if uses not in modern_refs and (not match or not 4 <= int(match.group(1)) <= maximum):
                unknown('unverified_action_ref', job_id, index, line)
                opaque_producers = True
                continue
            inputs = step.get('with', {})
            if not isinstance(inputs, dict):
                raise InputError('with must be a mapping.')
            upload = action.endswith('upload-artifact')
            kind = 'upload' if upload else 'download'
            if not upload and any(k in inputs for k in ('repository', 'run-id', 'artifact-ids', 'pattern')):
                unknown('external_id_or_pattern_download', job_id, index, line)
                continue
            if not upload and 'name' not in inputs:
                unknown('download_all_artifacts', job_id, index, line)
                continue
            if upload and boolean_input(inputs.get('archive', True)) is not True:
                unknown('unarchived_upload_name', job_id, index, line)
                opaque_producers = True
                continue
            overwrite = boolean_input(inputs.get('overwrite', False))
            if upload and overwrite is None:
                unknown('dynamic_overwrite', job_id, index, line)
                opaque_producers = True
                continue
            for leg, matrix in enumerate(legs, 1):
                try:
                    name = render(inputs.get('name', 'artifact'), matrix, job_id).strip(INPUT_WHITESPACE)
                except Unknown as exc:
                    unknown(str(exc), job_id, index, line)
                    if upload:
                        opaque_producers = True
                    continue
                if not upload and not name:
                    unknown('download_all_artifacts', job_id, index, line)
                    continue
                event = Event(job_id, leg, index, line, matrix, kind, name,
                              job_condition is None or condition(step.get('if')) is None,
                              overwrite is True)
                events.append(event)
                if not name or any(ord(c) < 32 or c in '"<>|:*?\\/\r\n' for c in name):
                    findings.append({'code': 'invalid_artifact_name', 'artifact': name, 'sites': [event.site()],
                                     'message': 'Artifact name is empty or contains a forbidden character.'})
                if len(events) > 2048:
                    raise InputError('More than 2048 expanded artifact steps.')

    def precedes(a, b):
        return a.job in ancestors[b.job] or (a.job == b.job and a.leg == b.leg and a.step < b.step)

    producers = defaultdict(list)
    for event in events:
        if event.kind == 'upload':
            producers[event.name].append(event)
    comparisons = 0
    for name, uploads in sorted(producers.items()):
        for left, right in itertools.combinations(uploads, 2):
            comparisons += 1
            if comparisons > 100000:
                raise InputError('Too many artifact pairs; split the workflow analysis.')
            if left.conditional or right.conditional:
                unknown('conditional_upload_collision', right.job, right.step, right.line)
                continue
            first, second = (left, right) if precedes(left, right) else (right, left)
            ordered = precedes(first, second)
            if ordered and second.overwrite:
                continue
            code = 'concurrent_overwrite' if not ordered and (left.overwrite or right.overwrite) else 'duplicate_upload'
            findings.append({'code': code, 'artifact': name, 'sites': [left.site(), right.site()],
                             'message': 'Multiple upload instances share one artifact name; use a distinct name per producer.' if code == 'duplicate_upload' else 'Unordered producers may delete/replace each other despite overwrite=true.'})
    edges = []
    for download in (event for event in events if event.kind == 'download'):
        matches = producers.get(download.name, [])
        prior = [upload for upload in matches if precedes(upload, download)]
        for upload in prior:
            edges.append({'artifact': download.name, 'producer': upload.site(), 'consumer': download.site()})
        if not prior:
            if opaque_producers:
                unknown('producer_not_resolved', download.job, download.step, download.line)
            elif download.conditional or any(upload.conditional for upload in matches):
                unknown('conditional_producer_order', download.job, download.step, download.line)
            else:
                code = 'missing_producer' if not matches else 'producer_not_ordered'
                findings.append({'code': code, 'artifact': download.name, 'sites': [download.site()] + [u.site() for u in matches],
                                 'message': 'No direct upload with this name exists in the modeled workflow.' if not matches else 'No matching producer precedes this download; add needs or move the download after the upload.'})
        elif all(upload.conditional for upload in prior):
            unknown('conditional_producer', download.job, download.step, download.line)
        for upload in matches:
            if upload.overwrite and not precedes(upload, download) and not precedes(download, upload):
                if upload.conditional or download.conditional:
                    unknown('conditional_overwrite_race', download.job, download.step, download.line)
                else:
                    findings.append({'code': 'overwrite_during_download', 'artifact': download.name,
                                     'sites': [upload.site(), download.site()],
                                     'message': 'A concurrent overwrite can replace/delete this artifact while it is being downloaded.'})
    return {'schema_version': 1, 'tool': 'artifactspan', 'complete': not unknowns,
            'scope': 'direct artifact actions, successful jobs, one workflow run attempt',
            'modern_refs': sorted(set(modern_refs)), 'events': [asdict(event) for event in events],
            'edges': edges, 'findings': findings, 'unknowns': unknowns}


def exit_code(report):
    # Unknowns cannot turn into a false green. JSON still contains known findings.
    return 2 if report['unknowns'] else 1 if report['findings'] else 0


def sarif(report, filename):
    from urllib.parse import quote
    filename = str(filename)
    windows = PureWindowsPath(filename)
    if windows.is_absolute():
        prefix = 'file:' if windows.drive.startswith('\\\\') else 'file:///'
        uri = prefix + quote(windows.as_posix(), safe='/:')
    elif filename.startswith('/'):
        uri = 'file://' + quote(filename, safe='/')
    else:
        uri = quote(filename.replace('\\', '/'), safe='/')
    results = []
    for issue in report['findings']:
        results.append({'ruleId': issue['code'], 'level': 'error', 'message': {'text': issue['message']},
                        'locations': [{'physicalLocation': {'artifactLocation': {'uri': uri},
                                                           'region': {'startLine': site['line']}}} for site in issue['sites']]})
    for issue in report['unknowns']:
        results.append({'ruleId': 'analysis_incomplete', 'level': 'warning', 'message': {'text': issue['code']},
                        'locations': [{'physicalLocation': {'artifactLocation': {'uri': uri},
                                                           'region': {'startLine': issue['line']}}}]})
    return {'version': '2.1.0', '$schema': 'https://json.schemastore.org/sarif-2.1.0.json',
            'runs': [{'tool': {'driver': {'name': 'artifactspan', 'version': __version__}},
                      'results': results, 'invocations': [{'executionSuccessful': not report['unknowns']}]}]}
