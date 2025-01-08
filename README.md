# solar-ev-charger
photovoltaics surplus control script e.g. for Raspberry PI

## How to install on a Raspberry Pi:

```
python3 -m venv penv
source penv/bin/activate
pip install -r requirements.txt
```

### Create config file
Copy `config.template.json` to `config.json` and insert your credentials etc.

### Configure cron job to run every 15 minutes, e.g. from 09:00 to 17:00:
`crontab -e`
```
*/15 9-17 * * * PYTHONPATH=/path/to/solar-ev-charger /path/to/solar-ev-charger/penv/bin/python /path/to/solar-ev-charger/main.py
```

### Launch webservice:
```
/path/to/solar-ev-charger/penv/bin/uvicorn webservice:app --host 0.0.0.0 --port 8000 --app-dir /path/to/solar-ev-charger
```

### Create systemd service for webservice:
```
TODO
```

## Development

Start webservice with this command, it will automatically reload on code changes:
```
penv/bin/uvicorn webservice:app --reload --host 0.0.0.0 --port 8000
```