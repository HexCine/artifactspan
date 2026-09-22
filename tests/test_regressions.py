import unittest
from artifactspan.core import analyze, exit_code, sarif


def upload(name):
    return {'uses': 'actions/upload-artifact@v4', 'with': {'name': name}}


def download(name):
    return {'uses': 'actions/download-artifact@v4', 'with': {'name': name}}


class RegressionTests(unittest.TestCase):
    def test_trimmed_names_still_collide(self):
        for padding in (' ', '\t', '\ufeff'):
            with self.subTest(padding=padding):
                result = analyze({'jobs': {'build': {'steps': [upload('bundle'), upload(padding + 'bundle' + padding)]}}})
                self.assertEqual([f['code'] for f in result['findings']], ['duplicate_upload'])

    def test_trimmed_download_resolves_producer(self):
        result = analyze({'jobs': {'build': {'steps': [upload('bundle'), download(' bundle ')]}}})
        self.assertEqual(exit_code(result), 0)
        self.assertEqual(len(result['edges']), 1)

    def test_empty_download_means_download_all(self):
        result = analyze({'jobs': {'build': {'steps': [download('  ')]}}})
        self.assertEqual(exit_code(result), 2)
        self.assertEqual(result['unknowns'][0]['code'], 'download_all_artifacts')

    def test_skipped_needs_propagates(self):
        result = analyze({'jobs': {'producer': {'if': False, 'steps': [upload('bundle')]},
                                  'middle': {'needs': 'producer', 'steps': []},
                                  'consumer': {'needs': 'middle', 'steps': [download('bundle')]}}})
        self.assertEqual(result['events'], [])
        self.assertEqual(exit_code(result), 0)

    def test_unknown_needs_propagates_uncertainty(self):
        result = analyze({'jobs': {'producer': {'if': 'inputs.enabled', 'steps': []},
                                  'consumer': {'needs': 'producer', 'steps': [download('bundle')]}}})
        self.assertEqual(exit_code(result), 2)

    def test_always_is_not_discarded_after_skipped_job(self):
        result = analyze({'jobs': {'producer': {'if': False, 'steps': []},
                                  'consumer': {'needs': 'producer', 'if': 'always()', 'steps': [download('bundle')]}}})
        self.assertEqual(len(result['events']), 1)
        self.assertEqual(exit_code(result), 2)

    def test_boolean_inputs_follow_toolkit(self):
        for value, expected in [(' true ', 0), ('TrUe', 2)]:
            with self.subTest(value=value):
                step = upload('bundle')
                step['with']['overwrite'] = value
                result = analyze({'jobs': {'build': {'steps': [upload('bundle'), step]}}})
                self.assertEqual(exit_code(result), expected)

    def test_sarif_absolute_windows_uri(self):
        result = analyze({'jobs': {'build': {'steps': [download('missing')]}}})
        document = sarif(result, 'C:\\repo\\build file.yml')
        uri = document['runs'][0]['results'][0]['locations'][0]['physicalLocation']['artifactLocation']['uri']
        self.assertEqual(uri, 'file:///C:/repo/build%20file.yml')

    def test_sarif_posix_unc_and_relative_uri(self):
        result = analyze({'jobs': {'build': {'steps': [download('missing')]}}})
        for path, expected in [('/repo/build file.yml', 'file:///repo/build%20file.yml'),
                               ('\\\\server\\share\\build file.yml', 'file://server/share/build%20file.yml'),
                               ('.github/workflows/build file.yml', '.github/workflows/build%20file.yml')]:
            with self.subTest(path=path):
                document = sarif(result, path)
                uri = document['runs'][0]['results'][0]['locations'][0]['physicalLocation']['artifactLocation']['uri']
                self.assertEqual(uri, expected)
