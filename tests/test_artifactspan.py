from contextlib import redirect_stdout, redirect_stderr
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from artifactspan.core import InputError, Unknown, analyze, expand_matrix, read_workflow, render, sarif, exit_code
from artifactspan.cli import main


def upload(name='build', **inputs):
    return {'uses': 'actions/upload-artifact@v4', 'with': {'name': name, 'path': 'dist', **inputs}}


def download(name='build', **inputs):
    return {'uses': 'actions/download-artifact@v4', 'with': {'name': name, **inputs}}


def job(*steps, needs=None, matrix=None):
    value = {'runs-on': 'ubuntu-latest', 'steps': list(steps)}
    if needs is not None:
        value['needs'] = needs
    if matrix is not None:
        value['strategy'] = {'matrix': matrix}
    return value


class MatrixTests(unittest.TestCase):
    def test_product(self):
        self.assertEqual(len(expand_matrix({'os': ['linux', 'windows'], 'py': [311, 314]})), 4)

    def test_include_does_not_merge_into_added_combinations(self):
        matrix = {'fruit': ['apple', 'pear'], 'animal': ['cat', 'dog'], 'include': [
            {'color': 'green'}, {'color': 'pink', 'animal': 'cat'}, {'fruit': 'apple', 'shape': 'circle'},
            {'fruit': 'banana'}, {'fruit': 'banana', 'animal': 'cat'}]}
        result = expand_matrix(matrix)
        self.assertEqual(len(result), 6)
        self.assertEqual(result[0], {'fruit': 'apple', 'animal': 'cat', 'color': 'pink', 'shape': 'circle'})
        self.assertEqual(result[-2:], [{'fruit': 'banana'}, {'fruit': 'banana', 'animal': 'cat'}])

    def test_exclude_then_include_reintroduces(self):
        result = expand_matrix({'os': ['linux', 'windows'], 'exclude': [{'os': 'windows'}], 'include': [{'os': 'windows', 'extra': 'yes'}]})
        self.assertEqual(result, [{'os': 'linux'}, {'os': 'windows', 'extra': 'yes'}])

    def test_include_only(self):
        self.assertEqual(expand_matrix({'include': [{'x': 1}, {'x': 2}]}), [{'x': 1}, {'x': 2}])

    def test_bool_not_numeric(self):
        self.assertEqual(expand_matrix({'x': [True, 1], 'exclude': [{'x': True}]}), [{'x': 1}])

    def test_dynamic_and_bounds(self):
        for matrix in ('${{ fromJSON(needs.setup.outputs.matrix) }}', {'x': '${{ inputs.list }}'}):
            with self.assertRaises(Unknown):
                expand_matrix(matrix)
        with self.assertRaises(InputError):
            expand_matrix({'x': list(range(257))})

    def test_render_nested_matrix_and_shared_run_symbols(self):
        value = render('build-${{ matrix.target.os }}-${{ github.run_id }}-${{ github.job }}', {'target': {'os': 'linux'}}, 'build')
        self.assertEqual(value, 'build-linux-__ARTIFACTSPAN_RUN_ID__-build')

    def test_unknown_expressions_never_evaluated(self):
        for text in ('${{ secrets.TOKEN }}', '${{ format("x") }}', '${{ matrix.absent }}', '${{ matrix.x'):
            with self.subTest(text=text), self.assertRaises(Unknown):
                render(text, {}, 'test')

    def test_numeric_coercion_not_guessed(self):
        for value in (1.0, 2**60):
            with self.subTest(value=value), self.assertRaises(Unknown):
                render('${{ matrix.x }}', {'x': value}, 'test')


class FlowTests(unittest.TestCase):
    def report(self, **jobs):
        return analyze({'jobs': jobs})

    def codes(self, report):
        return [finding['code'] for finding in report['findings']]

    def test_safe_matrix_producers_consumed_after_needs(self):
        report = self.report(build=job(upload('dist-${{ matrix.os }}'), matrix={'os': ['linux', 'windows']}),
                             consume=job(download('dist-linux'), download('dist-windows'), needs='build'))
        self.assertEqual(exit_code(report), 0)
        self.assertEqual(len(report['events']), 4)
        self.assertEqual(len(report['edges']), 2)

    def test_constant_matrix_name_collides(self):
        report = self.report(build=job(upload('dist'), matrix={'os': ['linux', 'windows']}))
        self.assertIn('duplicate_upload', self.codes(report))
        self.assertEqual(report['findings'][0]['sites'][1]['matrix'], {'os': 'windows'})

    def test_duplicate_upload_is_not_fixed_by_max_parallel_one(self):
        config = job(upload(), matrix={'os': ['linux', 'windows']})
        config['strategy']['max-parallel'] = 1
        self.assertIn('duplicate_upload', self.codes(self.report(build=config)))

    def test_default_upload_name(self):
        step = {'uses': 'actions/upload-artifact@v4', 'with': {'path': 'dist'}}
        report = self.report(build=job(step, copy.deepcopy(step)))
        self.assertEqual(report['findings'][0]['artifact'], 'artifact')

    def test_missing_producer(self):
        self.assertIn('missing_producer', self.codes(self.report(build=job(download('typo')))))

    def test_matching_producer_without_needs(self):
        self.assertIn('producer_not_ordered', self.codes(self.report(build=job(upload()), consume=job(download()))))

    def test_transitive_needs(self):
        report = self.report(build=job(upload()), gate=job({'run': 'echo gate'}, needs='build'), consume=job(download(), needs='gate'))
        self.assertEqual(exit_code(report), 0)

    def test_same_job_step_order(self):
        self.assertEqual(exit_code(self.report(build=job(upload(), download()))), 0)
        self.assertIn('producer_not_ordered', self.codes(self.report(build=job(download(), upload()))))

    def test_cross_matrix_leg_is_not_an_ordering_edge(self):
        config = job(upload('${{ matrix.os }}'), download('linux'), matrix={'os': ['linux', 'windows']})
        report = self.report(build=config)
        self.assertIn('producer_not_ordered', self.codes(report))

    def test_sequential_overwrite_allowed(self):
        self.assertEqual(exit_code(self.report(build=job(upload(), upload(overwrite=True), download()))), 0)

    def test_concurrent_overwrite_is_a_race(self):
        report = self.report(build=job(upload(overwrite=True), matrix={'os': ['linux', 'windows']}))
        self.assertIn('concurrent_overwrite', self.codes(report))

    def test_writer_can_race_reader_even_when_writers_are_ordered(self):
        report = self.report(initial=job(upload()), replace=job(upload(overwrite=True), needs='initial'), read=job(download(), needs='initial'))
        self.assertIn('overwrite_during_download', self.codes(report))

    def test_order_reader_before_overwrite_is_safe(self):
        report = self.report(initial=job(upload()), read=job(download(), needs='initial'), replace=job(upload(overwrite=True), needs='read'))
        self.assertEqual(exit_code(report), 0)

    def test_slash_from_matrix_rejected(self):
        report = self.report(build=job(upload('reports-${{ matrix.shard }}'), matrix={'shard': ['1/5', '2/5']}))
        self.assertEqual(self.codes(report), ['invalid_artifact_name', 'invalid_artifact_name'])

    def test_excluded_leg_no_collision(self):
        report = self.report(build=job(upload(), matrix={'os': ['linux', 'windows'], 'exclude': [{'os': 'windows'}]}))
        self.assertEqual(exit_code(report), 0)

    def test_dynamic_matrix_prevents_false_missing_producer(self):
        report = self.report(build=job(upload(), matrix='${{ fromJSON(inputs.matrix) }}'), read=job(download(), needs='build'))
        self.assertEqual(exit_code(report), 2)
        self.assertNotIn('missing_producer', self.codes(report))

    def test_mutually_exclusive_conditions_are_unknown_not_duplicate(self):
        a, b = upload(), upload()
        a['if'], b['if'] = "github.ref == 'a'", "github.ref != 'a'"
        report = self.report(build=job(a, b))
        self.assertNotIn('duplicate_upload', self.codes(report))
        self.assertEqual(exit_code(report), 2)

    def test_false_condition_is_skipped(self):
        disabled = upload()
        disabled['if'] = False
        self.assertEqual(exit_code(self.report(build=job(upload(), disabled))), 0)

    def test_conditional_producer_cannot_be_a_guarantee(self):
        producer = upload()
        producer['if'] = 'always()'
        report = self.report(build=job(producer), read=job(download(), needs='build'))
        self.assertEqual(exit_code(report), 2)

    def test_unverified_sha_and_explicit_assumption(self):
        step = upload()
        step['uses'] = 'actions/upload-artifact@' + 'a' * 40
        config = {'jobs': {'build': job(step)}}
        self.assertEqual(exit_code(analyze(config)), 2)
        self.assertEqual(exit_code(analyze(config, modern_refs=[step['uses']])), 0)

    def test_old_and_unknown_future_versions_are_unknown(self):
        for ref in ('v3', 'v100', 'main'):
            step = upload()
            step['uses'] = 'actions/upload-artifact@' + ref
            self.assertEqual(exit_code(self.report(build=job(step))), 2)

    def test_external_pattern_id_and_all_downloads_unknown(self):
        steps = [download(pattern='*'), download(**{'run-id': '123'}), download(**{'artifact-ids': '1'}),
                 {'uses': 'actions/download-artifact@v4'}]
        for step in steps:
            with self.subTest(step=step):
                self.assertEqual(exit_code(self.report(read=job(step))), 2)

    def test_nonarchived_upload_is_unknown(self):
        self.assertEqual(exit_code(self.report(build=job(upload(archive=False)))), 2)

    def test_local_action_and_reusable_workflow_are_explicit(self):
        report = self.report(call={'uses': './.github/workflows/other.yml'}, local=job({'uses': './action'}), read=job(download()))
        self.assertEqual(exit_code(report), 2)
        self.assertEqual(report['findings'], [])

    def test_invalid_dependency_graph(self):
        for config in ({'a': job(needs='a')}, {'a': job(needs='missing')}):
            with self.assertRaises(InputError):
                analyze({'jobs': config})

    def test_report_is_json_serializable_and_sarif_has_locations(self):
        report = self.report(build=job(download()))
        json.dumps(report)
        data = sarif(report, '.github/workflows/test file.yml')
        location = data['runs'][0]['results'][0]['locations'][0]['physicalLocation']
        self.assertIn('%20', location['artifactLocation']['uri'])
        self.assertEqual(location['region']['startLine'], 1)


class InputTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'workflow.yml'

    def write(self, text):
        self.path.write_text(text, encoding='utf-8')
        return read_workflow(self.path)

    def test_on_key_and_step_lines(self):
        data = self.write('on: push\njobs:\n  build:\n    steps:\n      - uses: actions/upload-artifact@v4\n        with:\n          name: bad/name\n          path: dist\n')
        self.assertIn('on', data)
        self.assertEqual(analyze(data)['findings'][0]['sites'][0]['line'], 5)

    def test_duplicate_yaml_keys_rejected(self):
        with self.assertRaises(InputError):
            self.write('jobs:\n  a: {steps: []}\n  a: {steps: []}\n')

    def test_yaml_aliases_and_objects_rejected(self):
        for text in ('jobs: &x {a: {steps: []}}\nother: *x', 'jobs: !!python/object/apply:os.system [echo unsafe]'):
            with self.subTest(text=text), self.assertRaises(InputError):
                self.write(text)

    def test_yaml_date_cannot_leak_into_unserializable_report(self):
        data = self.write('jobs:\n  a:\n    strategy:\n      matrix:\n        include:\n          - day: 2026-09-21\n    steps:\n      - uses: actions/upload-artifact@v4\n        with: {name: build, path: dist}\n')
        with self.assertRaises(InputError):
            analyze(data)

    def test_cli_exit_contract_and_json(self):
        for steps, expected in (([upload()], 0), ([download()], 1), ([upload('${{ env.NAME }}')], 2)):
            self.path.write_text(json.dumps({'jobs': {'build': job(*steps)}}))
            with redirect_stdout(io.StringIO()) as out, redirect_stderr(io.StringIO()) as err:
                code = main([str(self.path), '--format', 'json'])
            self.assertEqual(code, expected)
            self.assertEqual(json.loads(out.getvalue())['schema_version'], 1)
        self.path.write_text('broken: [')
        with redirect_stdout(io.StringIO()) as out, redirect_stderr(io.StringIO()) as err:
            self.assertEqual(main([str(self.path), '--format', 'json']), 2)
        self.assertIn('error', json.loads(err.getvalue()))


if __name__ == '__main__':
    unittest.main()
