"""Traffic figures for the site, from Cloudflare's analytics API.

Two sources, both over the last 30 days:

    edge      every request Cloudflare received for the zone (httpRequests1dGroups).
              Mostly bots and scanners.
    browsers  page loads reported by Cloudflare's Web Analytics beacon, which only real
              browsers run (rumPageloadEventsAdaptiveGroups). Cloudflare samples these to
              about 10% after a week, so small counts are estimates.

The page cannot hold a token, so the ingest service fetches the figures hourly with the
CLOUDFLARE_ANALYTICS token (a Fly secret) and publishes the summary in /api/stats as
`site_traffic`. Nothing here logs or returns the token.
"""

import logging
import statistics
from datetime import datetime, timedelta, timezone

import requests

logger = logging.getLogger(__name__)

API = 'https://api.cloudflare.com/client/v4'
DAYS = 30
TOP = 5
TIMEOUT = 20

EDGE_QUERY = """
query($zone: String!, $since: Date!, $until: Date!) {
  viewer { zones(filter: {zoneTag: $zone}) {
    httpRequests1dGroups(limit: 40, orderBy: [date_ASC], filter: {date_geq: $since, date_leq: $until}) {
      dimensions { date }
      sum { requests pageViews threats
            responseStatusMap { edgeResponseStatus requests }
            countryMap { clientCountryName requests }
            browserMap { uaBrowserFamily pageViews } }
      uniq { uniques }
    } } } }
"""

BROWSER_QUERY = """
query($account: String!, $since: Date!, $until: Date!, $host: String!, $top: Int!) {
  viewer { accounts(filter: {accountTag: $account}) {
    byDay: rumPageloadEventsAdaptiveGroups(limit: 40, orderBy: [date_ASC],
        filter: {date_geq: $since, date_leq: $until, requestHost: $host, bot: 0}) {
      count sum { visits } dimensions { date } }
    byReferrer: rumPageloadEventsAdaptiveGroups(limit: $top, orderBy: [count_DESC],
        filter: {date_geq: $since, date_leq: $until, requestHost: $host, bot: 0}) {
      count dimensions { refererHost } }
    byCountry: rumPageloadEventsAdaptiveGroups(limit: $top, orderBy: [count_DESC],
        filter: {date_geq: $since, date_leq: $until, requestHost: $host, bot: 0}) {
      count dimensions { countryName } }
  } } }
"""


class CloudflareError(Exception):
    """A request Cloudflare refused, or that did not complete."""


def _call(method, path, token, **kwargs):
    """The decoded reply. The error text names the path and Cloudflare's reason only."""
    try:
        response = requests.request(method, API + path, timeout=TIMEOUT,
                                    headers={'Authorization': f'Bearer {token}'}, **kwargs)
        body = response.json()
    except Exception as e:
        raise CloudflareError(f'{path}: {type(e).__name__}') from None
    errors = body.get('errors') or []
    if response.status_code != 200 or errors:
        reason = '; '.join(str(error.get('message', ''))[:120] for error in errors) or 'no reason given'
        raise CloudflareError(f'{path}: HTTP {response.status_code}, {reason}')
    return body


def lookup_ids(token, host):
    """(zone id, account id) for `host`. The token needs to be able to read the zone."""
    zones = _call('GET', '/zones', token, params={'name': host}).get('result') or []
    if not zones:
        raise CloudflareError(f'/zones: the token cannot see a zone named {host}')
    return zones[0]['id'], zones[0]['account']['id']


def _top(counts, n=TOP):
    """[[key, count]] for the n largest, largest first."""
    return [[key, count] for key, count in
            sorted(counts.items(), key=lambda item: (-item[1], str(item[0])))[:n]]


def summarize_edge(groups, today):
    """Totals over the daily rows of httpRequests1dGroups. `today` (YYYY-MM-DD) is a part
    day, so it is left out of the per-day median."""
    if not groups:
        return None
    status, countries, clients = {}, {}, {}
    for group in groups:
        for row in group['sum']['responseStatusMap']:
            status[row['edgeResponseStatus']] = status.get(row['edgeResponseStatus'], 0) + row['requests']
        for row in group['sum']['countryMap']:
            countries[row['clientCountryName']] = countries.get(row['clientCountryName'], 0) + row['requests']
        for row in group['sum']['browserMap']:
            clients[row['uaBrowserFamily']] = clients.get(row['uaBrowserFamily'], 0) + row['pageViews']
    whole_days = [g['uniq']['uniques'] for g in groups if g['dimensions']['date'] != today]
    return {
        'requests': sum(g['sum']['requests'] for g in groups),
        'not_found': status.get(404, 0),
        'blocked': sum(g['sum']['threats'] for g in groups),
        'page_views': sum(g['sum']['pageViews'] for g in groups),
        'unique_ips_per_day': round(statistics.median(whole_days or [g['uniq']['uniques'] for g in groups])),
        'status': _top(status),
        'countries': _top(countries),
        'clients': _top(clients),
    }


def summarize_browsers(by_day, by_referrer, by_country):
    """Totals over the Web Analytics rows. An empty referrer is a direct visit."""
    return {
        'page_loads': sum(row['count'] for row in by_day),
        'visits': sum(row['sum']['visits'] for row in by_day),
        'referrers': [[row['dimensions']['refererHost'] or 'direct', row['count']] for row in by_referrer],
        'countries': [[row['dimensions']['countryName'] or 'unknown', row['count']] for row in by_country],
    }


def fetch(token, host, ids, now=None):
    """The summary for /api/stats. Each source is asked for on its own: one that fails
    is None, with the reason logged."""
    now = now or datetime.now(timezone.utc)
    until = now.date()
    since = until - timedelta(days=DAYS)
    zone_id, account_id = ids
    dates = {'since': since.isoformat(), 'until': until.isoformat()}
    summary = {'since': dates['since'], 'until': dates['until'], 'updated': now.isoformat(),
               'edge': None, 'browsers': None}

    try:
        body = _call('POST', '/graphql', token,
                     json={'query': EDGE_QUERY, 'variables': dict(dates, zone=zone_id)})
        zones = body['data']['viewer']['zones']
        summary['edge'] = summarize_edge(zones[0]['httpRequests1dGroups'] if zones else [], dates['until'])
    except (CloudflareError, KeyError, TypeError) as e:
        logger.warning(f'Site traffic, edge figures not fetched: {e!r}')

    try:
        body = _call('POST', '/graphql', token, json={
            'query': BROWSER_QUERY,
            'variables': dict(dates, account=account_id, host=host, top=TOP)})
        accounts = body['data']['viewer']['accounts']
        if accounts:
            summary['browsers'] = summarize_browsers(
                accounts[0]['byDay'], accounts[0]['byReferrer'], accounts[0]['byCountry'])
    except (CloudflareError, KeyError, TypeError) as e:
        logger.warning(f'Site traffic, browser figures not fetched: {e!r}')

    return summary
