import unittest
from unittest.mock import Mock, patch

from igris_os.evaluation.local_benchmark import LocalProgrammingBenchmark, run_inference_benchmark
from igris_os.ai.ollama import ModelReply


class InferenceBenchmarkTests(unittest.TestCase):
    def test_invalid_generated_syntax_is_recorded_as_failure(self):
        client = Mock()
        client.generate_json.return_value = ModelReply(True, '{"code":"def broken(:"}', 'model')
        self.assertFalse(LocalProgrammingBenchmark.check_generated_python(client, 'model').passed)

    def test_generated_import_is_rejected_before_execution(self):
        client = Mock()
        client.generate_json.return_value = ModelReply(True, '{"code":"import os"}', 'model')
        with patch('igris_os.evaluation.local_benchmark.EngineeringWorkflow') as workflow:
            result = LocalProgrammingBenchmark.check_generated_python(client, 'model')
        self.assertFalse(result.passed)
        workflow.assert_not_called()

    def test_remote_endpoint_is_rejected_before_any_request(self):
        with patch('requests.post') as post:
            with self.assertRaises(ValueError):
                run_inference_benchmark('https://example.com', 'model', 'openai')
        post.assert_not_called()

    def test_equivalent_output_limits_and_recorded_results(self):
        response = Mock()
        response.json.return_value = {'choices': [{'message': {'content': 'Respuesta'},
                                                  'finish_reason': 'stop'}],
                                     'usage': {'completion_tokens': 5}}
        with patch('requests.post', return_value=response) as post:
            result = run_inference_benchmark('http://127.0.0.1:8080/v1', 'model', 'openai', rounds=1)
        self.assertEqual(post.call_args.args[0], 'http://127.0.0.1:8080/v1/chat/completions')
        self.assertEqual(post.call_args.kwargs['json']['max_tokens'], 256)
        self.assertTrue(result['results'][0]['complete'])
        self.assertEqual(result['results'][0]['tokens'], 5)


if __name__ == '__main__':
    unittest.main()