#!/usr/bin/env python3
"""Read-only direct-camera verification of exceptions from a NetBox core ARP audit."""
import argparse
import ast
import csv
import json
import re
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from playwright.sync_api import sync_playwright
from common import get_camera_credentials

ROOT = Path(__file__).resolve().parent
INVENTORY = Path('/Users/oleg/Library/CloudStorage/OneDrive-NorfolkPublicSchools/ISE_in_Teams/inventory')


def mac_key(value):
    return re.sub('[^0-9a-f]', '', value.lower())


def compare_inventory(report, inventory_root=INVENTORY):
    by_ip = {}
    for path in inventory_root.glob('[0-9][0-9][0-9]/camera_data.csv'):
        with path.open(encoding='utf-8-sig', newline='') as stream:
            for row in csv.DictReader(stream):
                cleaned = {key:(value or '').strip() for key,value in row.items()}
                by_ip.setdefault(cleaned['ip_address'], []).append(cleaned)
    for result in report['results']:
        sources = by_ip.get(result['ip'], [])
        result['source_csv_rows'] = sources
        if result['outcome'] != 'identity_verified' or len(sources) != 1:
            continue
        source = sources[0]
        live = result['live_inventory']
        result['csv_inventory_differences'] = {
            field:{'csv':source.get(field,''), 'live':live[field]}
            for field in ('mac_address','serial_number','part_number','firmware_version')
            if (mac_key(source.get(field,'')) != mac_key(live[field]) if field == 'mac_address'
                else source.get(field,'').strip() != live[field].strip())}
    from collections import Counter
    report['summary'] = dict(Counter(r['outcome'] for r in report['results']))
    report['summary']['previously_unseen_identity_verified'] = sum(
        r['category']=='active_absent_from_arp' and r['outcome']=='identity_verified'
        and r.get('inventory_mac_matches') is True for r in report['results'])
    report['summary']['additional_arp_identity_verified'] = sum(
        r['category']=='additional_arp_mac' and r['outcome']=='identity_verified'
        and r.get('arp_mac_matches') is True for r in report['results'])


def write_readable(report, path):
    lines = ['Direct Avigilon camera discrepancy audit', '',
             'Read-only HTTP/HTTPS checks and authenticated camera inventory collection.',
             'No CSV files, NetBox objects, or camera configuration were changed.', '',
             json.dumps(report['summary'], indent=2), '']
    for result in sorted(report['results'],key=lambda r:(r['category'],r['ip'])):
        live = result.get('live_inventory', {})
        lines.append(f"{result['category']} | {result['name']} | {result['ip']} | {result['outcome']}")
        if live:
            lines.append('  Live: '+', '.join(f'{k}: {v}' for k,v in live.items()))
        if 'inventory_mac_matches' in result:
            lines.append(f"  Inventory MAC match: {result['inventory_mac_matches']}; ARP MAC match: {result['arp_mac_matches']}")
        if 'icmp_reply' in result:
            lines.append(f"  ICMP reply: {result['icmp_reply']}")
        for key,values in result.get('csv_inventory_differences',{}).items():
            lines.append(f"  CSV difference {key}: {values['csv'] or '<missing>'} -> {values['live']}")
        lines.append('')
    path.with_suffix('.txt').write_text('\n'.join(lines)+'\n')


def check(target, username, password):
    result = {**target, 'checked_at': datetime.now(timezone.utc).isoformat(), 'reachable_ports': []}
    for port in (80, 443):
        try:
            with socket.create_connection((target['ip'], port), timeout=4):
                result['reachable_ports'].append(port)
        except OSError:
            pass
    if not result['reachable_ports']:
        result['outcome'] = 'web_unreachable'
        return result
    # Extract only the two inventory helpers; importing the original module would
    # run its interactive collection and overwrite the source CSV.
    tree = ast.parse((ROOT/'inventory_cameras.py').read_text())
    helpers = ast.Module(body=[node for node in tree.body if isinstance(node, ast.FunctionDef)
                              and node.name in ('try_login', 'safe_text')], type_ignores=[])
    namespace = {'USERNAME': username, 'PASSWORD': password,
                 'print': lambda *args, **kwargs: None}
    exec(compile(helpers, str(ROOT/'inventory_cameras.py'), 'exec'), namespace)
    result['attempts'] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            for port in result['reachable_ports']:
                base = f"{'http' if port == 80 else 'https'}://{target['ip']}"
                context = browser.new_context(http_credentials={'username':username,'password':password},
                                              ignore_https_errors=True)
                page = context.new_page()
                page.set_default_timeout(3500)
                page.set_default_navigation_timeout(12000)
                try:
                    response = page.goto(base, wait_until='domcontentloaded')
                    result['http_status'] = response.status if response else None
                    namespace['try_login'](page, target['ip'])
                    page.goto(base+'/web/about.shtml', wait_until='domcontentloaded')
                    page.wait_for_timeout(1800)
                    fields = {key: namespace['safe_text'](page.locator(selector)) for key,selector in {
                        'part_number':'#text-partNumber','serial_number':'#text-serialNumber',
                        'firmware_version':'#text-firmwareVersion','mac_address':'#text-macAddress'}.items()}
                    result['live_inventory'] = fields
                    if len(mac_key(fields['mac_address'])) == 12 and fields['serial_number']:
                        result['outcome'] = 'identity_verified'
                        result['inventory_mac_matches'] = (mac_key(fields['mac_address']) == mac_key(target.get('expected_mac',''))
                                                           if target.get('expected_mac') else None)
                        result['arp_mac_matches'] = (mac_key(fields['mac_address']) == mac_key(target.get('arp_mac',''))
                                                    if target.get('arp_mac') else None)
                        break
                    login_visible = any(page.locator(selector).is_visible() for selector in
                                        ('#input-username','#textfield_username'))
                    result['attempts'].append({'scheme':base.split(':')[0],
                                               'reason':'login_required' if login_visible else 'inventory_fields_unavailable',
                                               'title':page.title()})
                except Exception as exc:
                    # Avoid credentials in URLs or framework debug output.
                    result['attempts'].append({'scheme':base.split(':')[0], 'reason':type(exc).__name__})
                finally:
                    context.close()
            result.setdefault('outcome', 'web_responded_identity_unconfirmed')
        finally:
            browser.close()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arp-audit', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=3, choices=range(1,5))
    parser.add_argument('--inventory-root', type=Path, default=INVENTORY)
    args = parser.parse_args()
    username,password = get_camera_credentials()
    audit = json.loads(args.arp_audit.read_text())
    targets = {r['csv_ip']:{'ip':r['csv_ip'], 'name':r['name'], 'site':r['site'],
                           'category':'active_absent_from_arp','expected_mac':r['mac']}
               for r in audit['unseen'] if r['status']=='active'}
    for row in audit['unimported_arp_macs']:
        for observation in row['observations']:
            ip = observation['ip']
            sources = row.get('csv_rows_by_observed_ip',{}).get(ip,[])
            targets[ip] = {'ip':ip,'site':observation['site'], 'category':'additional_arp_mac',
                           'arp_mac':row['mac'], 'csv_rows':sources,
                           'name':sources[0]['hostname'] if sources else '<no CSV row>',
                           'expected_mac':sources[0]['csv_mac'] if sources else ''}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    path = args.output_dir/('camera_direct_audit_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.json')
    report = {'started_at':datetime.now(timezone.utc).isoformat(), 'source_arp_audit':str(args.arp_audit),
              'method':'Avigilon inventory login and about-page selectors; HTTP/HTTPS reachability',
              'read_only':True, 'complete':False, 'results':[]}
    def save():
        path.write_text(json.dumps(report,indent=2)+'\n')
    save()
    print('Audit:',path,flush=True)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(check,t,username,password):t for t in targets.values()}
        for future in as_completed(futures):
            try:
                result = future.result()
            except Exception as exc:
                result = {**futures[future], 'outcome':'audit_error','error_type':type(exc).__name__}
            report['results'].append(result)
            save()
            print(result['ip'],result['outcome'],flush=True)
    from collections import Counter
    report.update(complete=True, finished_at=datetime.now(timezone.utc).isoformat(),
                  summary=dict(Counter(r['outcome'] for r in report['results'])))
    compare_inventory(report, args.inventory_root)
    save()
    write_readable(report, path)
    print(json.dumps(report['summary']),flush=True)


if __name__ == '__main__':
    main()
