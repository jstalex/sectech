import html, json, sys
from pathlib import Path
source = Path(sys.argv[1])
x = json.loads(source.read_text())
rows = ''.join('<tr>'+''.join('<td>'+html.escape(str(a.get(k, '')))+'</td>' for k in ['check_id', 'resource', 'check_name'])+'</tr>' for a in x['results']['failed_checks'])
source.with_suffix('.html').write_text('<!doctype html><meta charset="utf-8"><title>Checkov</title><h1>Checkov</h1><p>'+html.escape(json.dumps(x['summary']))+'</p><table border="1"><tr><th>ID</th><th>Resource</th><th>Problem</th></tr>'+rows+'</table>')
