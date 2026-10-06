#!/usr/bin/env python3
"""Tests for the site traffic figures fetched from Cloudflare (site_traffic.py) and
their place in /api/stats."""

import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.pop('EAGLE_PASSWORD', None)

import app as monitor_app  # noqa: E402
import site_traffic  # noqa: E402

TOKEN = 'test-token-not-a-real-one'
NOW = datetime(2026, 10, 6, 5, 0, tzinfo=timezone.utc)


def day(date, requests, page_views, threats, uniques, status, countries, clients):
    return {
        'dimensions': {'date': date},
        'sum': {'requests': requests, 'pageViews': page_views, 'threats': threats,
                'responseStatusMap': [{'edgeResponseStatus': k, 'requests': v} for k, v in status.items()],
                'countryMap': [{'clientCountryName': k, 'requests': v} for k, v in countries.items()],
                'browserMap': [{'uaBrowserFamily': k, 'pageViews': v} for k, v in clients.items()]},
        'uniq': {'uniques': uniques},
    }


EDGE_ROWS = [
    day('2026-10-04', 1000, 100, 30, 200, {404: 600, 200: 400}, {'US': 700, 'FR': 300}, {'Curl': 60, 'Chrome': 40}),
    day('2026-10-05', 2000, 300, 50, 300, {404: 900, 200: 800, 301: 300}, {'US': 500, 'NL': 1500}, {'Chrome': 200, 'Unknown': 100}),
    day('2026-10-06', 100, 10, 0, 20, {200: 100}, {'CA': 100}, {'Chrome': 10}),  # today: a part day
]
BROWSER_DATA = {
    'byDay': [{'count': 20, 'sum': {'visits': 10}, 'dimensions': {'date': '2026-10-05'}},
              {'count': 10, 'sum': {'visits': 10}, 'dimensions': {'date': '2026-10-06'}}],
    'byReferrer': [{'count': 20, 'dimensions': {'refererHost': ''}},
                   {'count': 10, 'dimensions': {'refererHost': 'bing.com'}}],
    'byCountry': [{'count': 30, 'dimensions': {'countryName': 'CA'}}],
}


def reply(status=200, **body):
    response = MagicMock()
    response.status_code = status
    response.json.return_value = body
    return response


class FakeCloudflare:
    """Stands in for requests.request: answers the zone lookup and the two queries."""

    def __init__(self, edge=None, browsers=None, zones=None):
        self.edge = edge if edge is not None else reply(
            data={'viewer': {'zones': [{'httpRequests1dGroups': EDGE_ROWS}]}}, errors=None)
        self.browsers = browsers if browsers is not None else reply(
            data={'viewer': {'accounts': [BROWSER_DATA]}}, errors=None)
        self.zones = zones if zones is not None else reply(
            success=True, errors=[], result=[{'id': 'zone-1', 'account': {'id': 'account-1'}}])
        self.calls = []

    def __call__(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        if url.endswith('/zones'):
            return self.zones
        return self.edge if 'httpRequests1dGroups' in kwargs['json']['query'] else self.browsers


class TestSummaries(unittest.TestCase):
    def test_edge_totals(self):
        edge = site_traffic.summarize_edge(EDGE_ROWS, '2026-10-06')
        self.assertEqual(edge['requests'], 3100)
        self.assertEqual(edge['page_views'], 410)
        self.assertEqual(edge['blocked'], 80)
        self.assertEqual(edge['not_found'], 1500)
        self.assertEqual(edge['status'], [[404, 1500], [200, 1300], [301, 300]])
        self.assertEqual(edge['countries'], [['NL', 1500], ['US', 1200], ['FR', 300], ['CA', 100]])
        self.assertEqual(edge['clients'], [['Chrome', 250], ['Unknown', 100], ['Curl', 60]])

    def test_median_of_unique_ips_leaves_out_the_part_day(self):
        self.assertEqual(site_traffic.summarize_edge(EDGE_ROWS, '2026-10-06')['unique_ips_per_day'], 250)
        # With only today's rows there is nothing else to go by
        self.assertEqual(site_traffic.summarize_edge(EDGE_ROWS[2:], '2026-10-06')['unique_ips_per_day'], 20)

    def test_top_lists_stop_at_five(self):
        rows = [day('2026-10-05', 70, 0, 0, 1, {}, {c: n for n, c in enumerate('ABCDEFG', start=1)}, {})]
        self.assertEqual(site_traffic.summarize_edge(rows, '2026-10-06')['countries'],
                         [['G', 7], ['F', 6], ['E', 5], ['D', 4], ['C', 3]])

    def test_no_edge_rows(self):
        self.assertIsNone(site_traffic.summarize_edge([], '2026-10-06'))

    def test_browser_totals(self):
        browsers = site_traffic.summarize_browsers(**{
            'by_day': BROWSER_DATA['byDay'], 'by_referrer': BROWSER_DATA['byReferrer'],
            'by_country': BROWSER_DATA['byCountry']})
        self.assertEqual(browsers, {'page_loads': 30, 'visits': 20,
                                    'referrers': [['direct', 20], ['bing.com', 10]],
                                    'countries': [['CA', 30]]})


class TestFetch(unittest.TestCase):
    def fetch(self, fake):
        with patch.object(site_traffic.requests, 'request', fake):
            return site_traffic.fetch(TOKEN, 'linknode.com', ('zone-1', 'account-1'), NOW)

    def test_both_sources_over_thirty_days(self):
        fake = FakeCloudflare()
        summary = self.fetch(fake)
        self.assertEqual((summary['since'], summary['until']), ('2026-09-06', '2026-10-06'))
        self.assertEqual(summary['updated'], NOW.isoformat())
        self.assertEqual(summary['edge']['requests'], 3100)
        self.assertEqual(summary['browsers']['page_loads'], 30)
        edge_call, browser_call = fake.calls
        self.assertEqual(edge_call[2]['json']['variables'],
                         {'since': '2026-09-06', 'until': '2026-10-06', 'zone': 'zone-1'})
        self.assertEqual(browser_call[2]['json']['variables']['account'], 'account-1')
        self.assertEqual(browser_call[2]['json']['variables']['host'], 'linknode.com')
        self.assertEqual(edge_call[2]['headers'], {'Authorization': f'Bearer {TOKEN}'})

    def test_a_refused_source_is_none_and_the_other_still_arrives(self):
        refused = reply(data=None, errors=[{'message': 'not authorized for that account'}])
        with self.assertLogs(site_traffic.logger, 'WARNING') as logs:
            summary = self.fetch(FakeCloudflare(browsers=refused))
        self.assertEqual(summary['edge']['requests'], 3100)
        self.assertIsNone(summary['browsers'])
        self.assertIn('not authorized for that account', logs.output[0])
        self.assertNotIn(TOKEN, ''.join(logs.output))

    def test_a_failed_request_names_the_error_type_only(self):
        def broken(method, url, **kwargs):
            raise RuntimeError(f'connection failed, headers were {kwargs["headers"]}')
        with self.assertLogs(site_traffic.logger, 'WARNING') as logs:
            summary = self.fetch(broken)
        self.assertIsNone(summary['edge'])
        self.assertIsNone(summary['browsers'])
        self.assertIn('RuntimeError', logs.output[0])
        self.assertNotIn(TOKEN, ''.join(logs.output))

    def test_lookup_ids(self):
        fake = FakeCloudflare()
        with patch.object(site_traffic.requests, 'request', fake):
            self.assertEqual(site_traffic.lookup_ids(TOKEN, 'linknode.com'), ('zone-1', 'account-1'))
        self.assertEqual(fake.calls[0][2]['params'], {'name': 'linknode.com'})

    def test_lookup_refused_or_empty(self):
        for zones in (reply(403, success=False, errors=[{'message': 'Authentication error'}]),
                      reply(success=True, errors=[], result=[])):
            with patch.object(site_traffic.requests, 'request', FakeCloudflare(zones=zones)):
                with self.assertRaises(site_traffic.CloudflareError) as raised:
                    site_traffic.lookup_ids(TOKEN, 'linknode.com')
            self.assertNotIn(TOKEN, str(raised.exception))


class TestWiring(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.assertTrue(monitor_app.init_store(os.path.join(self.tmp, 'energy.db')))
        self.saved = (monitor_app.CLOUDFLARE_ANALYTICS, dict(monitor_app.site_traffic_state))
        monitor_app.site_traffic_state.update(ids=None, summary=None)
        self.client = monitor_app.app.test_client()

    def tearDown(self):
        monitor_app.CLOUDFLARE_ANALYTICS = self.saved[0]
        monitor_app.site_traffic_state.update(self.saved[1])
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_nothing_is_fetched_without_the_token(self):
        monitor_app.CLOUDFLARE_ANALYTICS = None
        fake = FakeCloudflare()
        with patch.object(site_traffic.requests, 'request', fake):
            monitor_app.refresh_site_traffic()
        self.assertEqual(fake.calls, [])
        self.assertIsNone(self.client.get('/api/stats').get_json()['site_traffic'])

    def test_refresh_publishes_the_figures_in_stats(self):
        monitor_app.CLOUDFLARE_ANALYTICS = TOKEN
        fake = FakeCloudflare()
        with patch.object(site_traffic.requests, 'request', fake):
            monitor_app.refresh_site_traffic()
            monitor_app.refresh_site_traffic()
        # The ids are looked up once, then kept
        self.assertEqual([url.rsplit('/', 1)[1] for _, url, _ in fake.calls],
                         ['zones', 'graphql', 'graphql', 'graphql', 'graphql'])
        body = self.client.get('/api/stats').get_json()
        self.assertEqual(body['site_traffic']['edge']['requests'], 3100)
        self.assertEqual(body['site_traffic']['browsers']['referrers'][0], ['direct', 20])
        self.assertNotIn(TOKEN, self.client.get('/api/stats').get_data(as_text=True))

    def test_a_failed_refresh_keeps_the_figures_already_held(self):
        monitor_app.CLOUDFLARE_ANALYTICS = TOKEN
        with patch.object(site_traffic.requests, 'request', FakeCloudflare()):
            monitor_app.refresh_site_traffic()
        refused = reply(403, data=None, errors=[{'message': 'Authentication error'}])
        with patch.object(site_traffic.requests, 'request', FakeCloudflare(edge=refused, browsers=refused)):
            monitor_app.refresh_site_traffic()
        self.assertEqual(monitor_app.site_traffic_state['summary']['edge']['requests'], 3100)

    def test_a_refused_lookup_is_logged_and_tried_again_next_time(self):
        monitor_app.CLOUDFLARE_ANALYTICS = TOKEN
        refused = reply(403, success=False, errors=[{'message': 'Authentication error'}])
        with patch.object(site_traffic.requests, 'request', FakeCloudflare(zones=refused)):
            with self.assertLogs(monitor_app.logger, 'WARNING') as logs:
                monitor_app.refresh_site_traffic()
        self.assertIn('Authentication error', logs.output[0])
        self.assertIsNone(monitor_app.site_traffic_state['ids'])
        self.assertIsNone(monitor_app.site_traffic_state['summary'])


if __name__ == '__main__':
    unittest.main()
