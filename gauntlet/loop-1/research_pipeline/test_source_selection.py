"""Source selection uses available extractive evidence before extra paid fetches.

The incident fixture preserves URL equality, tiers, discovery ordering and text
lengths only. URLs and prose below are synthetic; no live provider is contacted.
"""
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import research_orchestrator as R


class SourceSelectionTest(unittest.TestCase):
    def test_available_text_wins_over_dual_discovery_within_the_same_tier(self):
        urls = [f'https://data.worldbank.org/synthetic-{i}' for i in range(3)]
        discovery = [{'url': u, 'title': 'Synthetic source',
                      'text': 'x' * (143 if i == 0 else 500)}
                     for i, u in enumerate(urls)]
        planner = mock.Mock()
        planner.json_call.return_value = {
            'queries': ['Exampleland Synthetic indicator'], 'likely_publishers': []}
        ambiguous = R.V.VendorTransportAmbiguous(
            vendor='jina', model='', pass_name='research', detail='synthetic',
            max_tokens=22096, input_tokens=0, output_tokens=22096)
        with mock.patch.object(R, 'MAX_PAGES', 2), \
             mock.patch.object(R.V, 'exa_search', return_value=discovery), \
             mock.patch.object(R.V, 'perplexity_citations', return_value={
                 'citations': urls[:1], 'lead_prose': '', 'error': ''}), \
             mock.patch.object(R.V, 'exa_contents', return_value='x' * 143) as contents, \
             mock.patch.object(R.V, 'jina_fetch', side_effect=ambiguous) as reader:
            pack, *_ = R.retrieve(
                {'id': '4.2', 'name': 'Synthetic indicator', 'open_question': ''},
                'Exampleland', planner, object(), log=lambda _: None)
        self.assertEqual([p['url'] for p in pack], urls[1:])
        contents.assert_not_called()
        reader.assert_not_called()

    def test_readable_lower_tier_does_not_displace_higher_tier_citation(self):
        higher = 'https://data.worldbank.org/synthetic-short'
        lower = 'https://example.test/synthetic-readable'
        planner = mock.Mock()
        planner.json_call.return_value = {
            'queries': ['Exampleland Synthetic indicator'], 'likely_publishers': []}
        discovery = [{'url': higher, 'title': '', 'text': 'x' * 143},
                     {'url': lower, 'title': '', 'text': 'x' * 500}]
        ambiguous = R.V.VendorTransportAmbiguous(
            vendor='jina', model='', pass_name='research', detail='synthetic',
            max_tokens=22096, input_tokens=0, output_tokens=22096)
        with mock.patch.object(R, 'MAX_PAGES', 1), \
             mock.patch.object(R.V, 'exa_search', return_value=discovery), \
             mock.patch.object(R.V, 'perplexity_citations', return_value={
                 'citations': [], 'lead_prose': '', 'error': ''}), \
             mock.patch.object(R.V, 'exa_contents', return_value='x' * 143), \
             mock.patch.object(R.V, 'jina_fetch', side_effect=ambiguous) as reader:
            with self.assertRaises(R.V.VendorTransportAmbiguous):
                R.retrieve({'id': '4.2', 'name': 'Synthetic indicator', 'open_question': ''},
                           'Exampleland', planner, object(), log=lambda _: None)
        self.assertEqual(reader.call_args.args[0], higher)
        self.assertEqual(reader.call_count, 1)

    def test_dual_discovery_still_breaks_ties_between_readable_sources(self):
        urls = [f'https://data.worldbank.org/synthetic-{i}' for i in range(2)]
        planner = mock.Mock()
        planner.json_call.return_value = {
            'queries': ['Exampleland Synthetic indicator'], 'likely_publishers': []}
        with mock.patch.object(R, 'MAX_PAGES', 1), \
             mock.patch.object(R.V, 'exa_search', return_value=[
                 {'url': u, 'title': '', 'text': 'x' * 500} for u in urls]), \
             mock.patch.object(R.V, 'perplexity_citations', return_value={
                 'citations': urls[1:], 'lead_prose': 'Not extractive evidence', 'error': ''}), \
             mock.patch.object(R.V, 'exa_contents', side_effect=AssertionError('unexpected fetch')):
            pack, *_ = R.retrieve(
                {'id': '4.2', 'name': 'Synthetic indicator', 'open_question': ''},
                'Exampleland', planner, object(), log=lambda _: None)
        self.assertEqual([p['url'] for p in pack], urls[1:])
        self.assertEqual(pack[0]['surfaced_by'], 'exa, perplexity')
        self.assertEqual(pack[0]['text'], 'x' * 500)

    def test_incident_row_uses_available_same_tier_sources_without_reader(self):
        with (Path(__file__).parent / 'fixtures/incidents/d7e280c6_sources.json').open() as f:
            fixture = json.load(f)
        sources = {s['id']: s for rows in fixture['searches'] for s in rows}
        sources.update({s['id']: s for s in fixture['citations'] if s['id'] not in sources})
        tiers = {f'https://source-{i}.example.test/': s['tier'] for i, s in sources.items()}
        def page(s):
            return {'url': f"https://source-{s['id']}.example.test/",
                    'title': 'Synthetic source', 'text': 'x' * s['chars']}
        spec = {'id': '4.2', 'name': 'Synthetic indicator', 'open_question': ''}
        query_names = ['synthetic query 0', 'synthetic query 1', 'synthetic query 2',
                       'Exampleland Synthetic indicator']
        searches = {q: [page(s) for s in rows]
                    for q, rows in zip(query_names, fixture['searches'])}
        planner = mock.Mock()
        planner.json_call.return_value = {'queries': query_names[:3], 'likely_publishers': []}
        failed_url = f"https://source-{fixture['failed_source_id']}.example.test/"
        def respond(request, **kwargs):
            if request.full_url == 'https://r.jina.ai/' + failed_url:
                raise TimeoutError('synthetic transport outcome unavailable')
            if request.full_url == 'https://api.exa.ai/contents':
                url = json.loads(request.data)['urls'][0]
                chars = fixture['contents_chars'] if url == failed_url else 500
                body = {'statuses': [{'id': url, 'status': 'success'}],
                        'results': [{'id': url, 'url': url, 'text': 'x' * chars}],
                        'costDollars': {'total': 0.001}}
            else:
                body = {'data': {'content': 'Synthetic evidence. ' * 30,
                                 'usage': {'tokens': 100}}}
            response = io.BytesIO(json.dumps(body).encode())
            response.status = 200
            return response
        with tempfile.TemporaryDirectory() as directory:
            ledger = R.V.Ledger(ceiling=200, label='synthetic-selection')
            ledger.attach(os.path.join(directory, 'spend.json'))
            with mock.patch.dict(os.environ, {'EXA_API_KEY': 'synthetic-key',
                                              'JINA_API_KEY': 'synthetic-key'}), \
                 mock.patch.object(R.V, 'tier_for_url', side_effect=lambda url, *_: tiers[url]), \
                 mock.patch.object(R.V, 'exa_search', side_effect=lambda q, *_a, **_k: searches[q]), \
                 mock.patch.object(R.V, 'perplexity_citations', return_value={
                     'citations': [page(s)['url'] for s in fixture['citations']],
                     'lead_prose': '', 'error': ''}), \
                 mock.patch.object(R.V.urllib.request, 'urlopen', side_effect=respond) as transport:
                pack, *_ = R.retrieve(spec, 'Exampleland', planner, ledger, log=lambda _: None)
            self.assertEqual(len(pack), R.MAX_PAGES)
            self.assertNotIn(failed_url, [p['url'] for p in pack])
            self.assertTrue(all(p['retrieval_provider'] == 'exa' for p in pack))
            self.assertEqual([p['tier'] for p in pack].count('T3'), 2)
            self.assertEqual([p['tier'] for p in pack].count('T5'), 1)
            transport.assert_not_called()
            self.assertEqual(ledger.spent(), 0)
            self.assertEqual(ledger.calls, [])


if __name__ == '__main__':
    unittest.main()
