"""Documentation source order, partial retries and preservation of reader-owned notes."""
import json
import tempfile
import unittest
from bs4 import BeautifulSoup
from pathlib import Path
from unittest.mock import patch

from textfold import build, docsite, ladder, llm, notes, pipeline, store


class DocumentationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data = patch.object(store, 'DATA', Path(self.tmp.name))
        self.data.start()
        self.addCleanup(self.data.stop)
        self.root = 'https://example.org/docs/'
        self.calls = []
        self.failed = False
        self.words = 'Read this source passage with its exact wording.'
        self.pages = {
            self.root: '<aside class="hidden lg:block"><nav><a href="/docs/">Start</a><button aria-controls="group">Concepts</button><div id="group"><a href="/docs/second/">Second</a></div><a href="/blog/">Blog</a><a href="/docs/#anchor">Same page</a></nav></aside><article><h1>Start</h1><p>' + self.words + '</p><h2 id="code">Code</h2><pre><code>print("hello")</code></pre><p><a href="/docs/second/">Next</a></p></article>',
            self.root + 'second/': '<article><h1>Second</h1><p>Second original passage.</p></article>',
        }
        def get(url):
            self.calls.append(url)
            if self.failed and url.endswith('second/'):
                raise OSError('temporary failure')
            return self.pages[url].encode(), url, 'utf-8'
        self.get = patch.object(docsite.webpage, '_get', side_effect=get)
        self.get.start()
        self.addCleanup(self.get.stop)

    def test_directory_order_hierarchy_and_fragment_identity(self):
        plan, _ = docsite.directory(self.root + '#anchor')
        self.assertEqual([c['url'] for c in plan['chapters']], [self.root, self.root + 'second/'])
        self.assertEqual(plan['chapters'][1]['path'], ['Concepts'])

    def test_readable_partial_retry_and_repeat(self):
        self.failed = True
        result = docsite.import_set(self.root)
        pid = result['paper']
        doc = store.parsed(pid)
        self.assertTrue(result['readable'])
        self.assertEqual(result['documentation']['chapters'][1]['status'], 'failed')
        self.assertIn('print', (store.pdir(pid) / 'source.html').read_text())
        self.assertIn('/static/webmcp.js', build.page(store.assemble(pid), app=True))
        before = (store.pdir(pid) / 'source.html').read_bytes()
        self.calls.clear()
        self.assertTrue(docsite.import_set(self.root + '#other')['reused'])
        self.assertEqual(self.calls, [])
        self.assertEqual((store.pdir(pid) / 'source.html').read_bytes(), before)
        self.failed = False
        self.calls.clear()
        result = docsite.import_set(pid=pid, mode='retry')
        self.assertEqual(self.calls, [self.root + 'second/'])
        self.assertTrue(all(c['status'] == 'ready' for c in result['documentation']['chapters']))
        doc = store.parsed(pid)
        units = [(docsite.text_of(doc, u), docsite.source_of(doc, u)) for u in doc['units']]
        self.assertIn((self.words, self.root), units)
        self.assertIn(('Second original passage.', self.root + 'second/'), units)
        self.assertIn('href="#page-2-', (store.pdir(pid) / 'source.html').read_text())

    def test_update_preserves_and_reports_unresolved_notes(self):
        pid = docsite.import_set(self.root)['paper']
        doc = store.parsed(pid)
        uid = next(u for u in doc['units'] if docsite.text_of(doc, u) == self.words)
        notes.put(pid, {'id': 'n-test', 'text': 'Reader note', 'kind': 'note', 'anchor': {
            'unit': uid, 'section': doc['units'][uid]['chunk'], 'lang': 'en', 'tokens': [0, 2], 'quote': {'exact': self.words}}})
        self.pages[self.root] = self.pages[self.root].replace('<p>' + self.words, '<p>A newly inserted paragraph.</p><p>' + self.words)
        result = docsite.import_set(pid=pid, mode='update')
        saved = notes.read(pid)['notes'][0]
        self.assertEqual(saved['text'], 'Reader note')
        self.assertEqual(docsite.text_of(store.parsed(pid), saved['anchor']['unit']), self.words)
        self.assertEqual(result['documentation']['unresolved_annotations'], [])
        self.pages[self.root] = self.pages[self.root].replace(self.words, self.words + ' Added source context.')
        docsite.import_set(pid=pid, mode='update')
        saved = notes.read(pid)['notes'][0]
        self.assertIsNotNone(saved['anchor']['tokens'])
        self.assertTrue(saved['anchor']['sents'])
        self.pages[self.root] = self.pages[self.root].replace(self.words, 'A different replacement.')
        result = docsite.import_set(pid=pid, mode='update')
        saved = notes.read(pid)['notes'][0]
        self.assertIsNone(saved['anchor']['unit'])
        self.assertTrue(saved['anchor']['unresolved'])
        self.assertEqual(saved['anchor']['quote']['exact'], self.words)
        self.assertEqual(result['documentation']['unresolved_annotations'], ['n-test'])

    def test_update_archives_changed_layers_but_keeps_identical_source(self):
        pid = docsite.import_set(self.root)['paper']
        layer = {'version': 'fixture', 'units': {}, 'chunks': {}, 'edges': []}
        store.write(pid, 'en', layer)
        before = (store.pdir(pid) / 'layers/en.json').read_bytes()
        docsite.import_set(pid=pid, mode='update')
        self.assertEqual((store.pdir(pid) / 'layers/en.json').read_bytes(), before)
        self.pages[self.root] = self.pages[self.root].replace(self.words, self.words + ' Changed.')
        docsite.import_set(pid=pid, mode='update')
        self.assertFalse((store.pdir(pid) / 'layers/en.json').exists())
        self.assertEqual((store.pdir(pid) / 'previous/layers/en.json').read_bytes(), before)

    def test_update_moves_saved_answer_citations_and_retains_missing_sources(self):
        pid = docsite.import_set(self.root)['paper']
        doc = store.parsed(pid)
        uid = next(u for u in doc['units'] if docsite.text_of(doc, u) == self.words)
        other = next(u for u in doc['units'] if docsite.text_of(doc, u) == 'Second original passage.')
        notes.put(pid, {'id': 'n-answer', 'kind': 'ask', 'anchor': {'on': 'paper'},
                        'thread': [{'q': 'Why?', 'a': f'Answer [[{uid}]][[{other}]][[?]][[!12]]', 'cites': [uid, other]}]})
        self.pages[self.root] = self.pages[self.root].replace('<p>' + self.words, '<p>Inserted first.</p><p>' + self.words)
        docsite.import_set(pid=pid, mode='update')
        saved = notes.read(pid)['notes'][0]['thread'][0]
        updated = store.parsed(pid)
        self.assertNotEqual(saved['cites'][0], uid)
        self.assertEqual([docsite.text_of(updated, u) for u in saved['cites']], [self.words, 'Second original passage.'])
        self.assertEqual(saved['a'], f"Answer [[{saved['cites'][0]}]][[{saved['cites'][1]}]][[?]][[!12]]")
        self.pages[self.root] = self.pages[self.root].replace(self.words, 'Unrelated replacement.')
        result = docsite.import_set(pid=pid, mode='update')
        saved = notes.read(pid)['notes'][0]['thread'][0]
        self.assertTrue(saved['cites'][0].startswith('!'))
        self.assertIn('[[' + saved['cites'][0] + ']]', saved['a'])
        self.assertEqual(saved['unresolved_cites'][0]['text'], self.words)
        self.assertEqual(result['documentation']['unresolved_annotations'], ['n-answer'])
        self.pages[self.root] = self.pages[self.root].replace('Unrelated replacement.', self.words)
        docsite.import_set(pid=pid, mode='update')
        saved = notes.read(pid)['notes'][0]['thread'][0]
        self.assertEqual(docsite.text_of(store.parsed(pid), saved['cites'][0]), self.words)
        self.assertNotIn('unresolved_cites', saved)

    def test_update_duplicate_quote_is_unresolved_without_unique_context(self):
        self.pages[self.root] = self.pages[self.root].replace(self.words, 'source passage')
        pid = docsite.import_set(self.root)['paper']
        doc = store.parsed(pid)
        uid = next(u for u in doc['units'] if docsite.text_of(doc, u) == 'source passage')
        notes.put(pid, {'id': 'n-repeat', 'anchor': {'unit': uid, 'quote': {'exact': 'source passage'}, 'tokens': [0, 1]}})
        self.pages[self.root] = self.pages[self.root].replace('source passage', 'A source passage replaces another source passage.')
        result = docsite.import_set(pid=pid, mode='update')
        saved = notes.read(pid)['notes'][0]['anchor']
        self.assertIsNone(saved['unit'])
        self.assertTrue(saved['unresolved'])
        self.assertEqual(saved['quote']['exact'], 'source passage')
        self.assertEqual(result['documentation']['unresolved_annotations'], ['n-repeat'])

    def test_update_does_not_retarget_citation_to_identical_words_on_another_page(self):
        self.pages[self.root + 'second/'] = self.pages[self.root + 'second/'].replace('Second original passage.', self.words)
        pid = docsite.import_set(self.root)['paper']
        doc = store.parsed(pid)
        uid = next(u for u in doc['units'] if docsite.text_of(doc, u) == self.words and docsite.source_of(doc, u) == self.root)
        notes.put(pid, {'id': 'n-source', 'anchor': {'on': 'paper'},
                       'ask': {'q': 'Source?', 'a': f'Source [[{uid}]]', 'cites': [uid]}})
        self.pages[self.root] = self.pages[self.root].replace(self.words, 'Replacement on the original page.')
        result = docsite.import_set(pid=pid, mode='update')
        turn = notes.read(pid)['notes'][0]['ask']
        self.assertEqual(turn['cites'], ['!' + uid])
        self.assertEqual(turn['a'], f'Source [[!{uid}]]')
        self.assertEqual(turn['unresolved_cites'][0]['source_url'], self.root)
        self.assertEqual(result['documentation']['unresolved_annotations'], ['n-source'])

    def test_update_quote_context_selects_second_occurrence(self):
        self.pages[self.root] = self.pages[self.root].replace(self.words, 'another source passage ends here.')
        pid = docsite.import_set(self.root)['paper']
        doc = store.parsed(pid)
        uid = next(u for u in doc['units'] if docsite.text_of(doc, u) == 'another source passage ends here.')
        notes.put(pid, {'id': 'n-context', 'anchor': {'unit': uid, 'tokens': [1, 2],
                    'quote': {'exact': 'source passage', 'prefix': 'another ', 'suffix': ' ends here.'}}})
        self.pages[self.root] = self.pages[self.root].replace('another source passage ends here.', 'A source passage replaces another source passage ends here.')
        result = docsite.import_set(pid=pid, mode='update')
        saved = notes.read(pid)['notes'][0]['anchor']
        updated = store.parsed(pid)
        text = docsite.text_of(updated, saved['unit'])
        spans = notes._spans(updated['units'][saved['unit']]['toks'], updated['atoms'])[1]
        self.assertEqual(spans[saved['tokens'][0]][0], text.rindex('source passage'))
        self.assertEqual(result['documentation']['unresolved_annotations'], [])

    def test_original_language_generation_uses_no_translation(self):
        self.pages[self.root] = self.pages[self.root].replace(self.words, '原文内容保持原来的语言。')
        pid = docsite.import_set(self.root)['paper']
        doc = store.parsed(pid)
        chunk = next(c for c in doc['chunks'] if c['units'])
        prompt = ladder.prompt_for(doc, chunk)
        self.assertNotIn('English sentence', prompt)
        self.assertIn('original language', prompt)
        self.assertIn('Do not translate', llm.system_for(doc['meta']))
        with patch.object(pipeline.ladder, 'build'), patch.object(pipeline.links, 'build'), patch.object(pipeline.translate, 'build') as translate:
            pipeline.generate(pid, 'zh', {'kind': 'api', 'id': 'test', 'model': 'test'})
        translate.assert_not_called()
        self.assertTrue(store.read(pid, 'en'))
        self.assertEqual(store.languages(pid), [])

    def test_all_pages_failed_can_be_retried(self):
        with patch.object(docsite, '_body', side_effect=ValueError('temporarily unreadable')):
            result = docsite.import_set(self.root)
        self.assertFalse(result['readable'])
        self.assertEqual(len(result['documentation']['chapters']), 2)
        self.assertFalse(docsite.import_set(self.root)['readable'])
        retry = docsite.import_set(pid=result['paper'], mode='retry')
        self.assertTrue(retry['readable'])
        self.assertTrue(all(c['status'] == 'ready' for c in retry['documentation']['chapters']))

    def test_generated_chinese_ladder_round_trip(self):
        self.pages = {self.root: '<nav><a href="/docs/">原文</a></nav><article><h1>原文</h1><p>保持原文的语言。后一句支持前一句。</p></article>'}
        pid = docsite.import_set(self.root)['paper']
        calls = []
        def respond(prompt, schema, cfg, cache, force=False, **kwargs):
            calls.append((prompt, kwargs['system']))
            out = {'links': []} if 'links' in schema['properties'] else {
                'section': {'takeaway': '保持原文语言', 'topic': '原文语言', 'equations': []},
                'units': [{'id': 'U0', 'role': 'claim', 'takeaway': '保持原文语言', 'topic': '原文语言', 'reason': '后一句提供支持', 'evidence': [0]}]}
            return {'out': out, 'cost': 0}, False
        with patch.object(llm, 'call', side_effect=respond), patch.object(pipeline.translate, 'build') as translate:
            pipeline.generate(pid, 'en', {'kind': 'api', 'id': 'test', 'model': 'test'})
        translate.assert_not_called()
        saved = json.dumps(store.read(pid, 'en'), ensure_ascii=False)
        self.assertIn('原', saved)
        self.assertEqual(len(calls), 2)
        self.assertTrue(all('Do not translate' in system for _, system in calls))

    def test_reader_chapter_keeps_global_anchors_and_full_export(self):
        pid = docsite.import_set(self.root)['paper']
        whole = store.assemble(pid)
        second = docsite.reader_document(whole, 'page-2')
        self.assertEqual(second['meta']['active_chapter'], 'page-2')
        self.assertEqual(len(second['meta']['documentation_chapters']), 2)
        self.assertTrue(all(docsite.source_of(second, u) == self.root + 'second/' for u in second['units']))
        uid = next(u for u in whole['units'] if docsite.text_of(whole, u) == 'Second original passage.')
        self.assertIn(uid, second['units'])
        self.assertEqual(second['meta']['document_unit_chapters'][uid], 'page-2')
        html = build.page(second, app=True)
        self.assertIn('documentation-chapter', html)
        payload = json.loads(BeautifulSoup(html, 'lxml').find(id='paper-data').string)
        self.assertEqual(docsite.text_of(payload, uid), 'Second original passage.')
        exported = build.page(whole)
        payload = json.loads(BeautifulSoup(exported, 'lxml').find(id='paper-data').string)
        texts = [docsite.text_of(payload, u) for u in payload['units']]
        self.assertIn(self.words, texts)
        self.assertIn('Second original passage.', texts)


if __name__ == '__main__':
    unittest.main()
