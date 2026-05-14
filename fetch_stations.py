import os
import requests
import json
from dotenv import load_dotenv

load_dotenv('e:/SangKien/phan-mem-quan-ly-cv/.env')
api_key = os.environ.get('VRAIN_API_KEY')

if not api_key:
    print('VRAIN_API_KEY not found in .env')
else:
    try:
        response = requests.get('https://kttv-open.vrain.vn/v1/stations', headers={'x-api-key': api_key})
        data = response.json()
        stations = data if isinstance(data, list) else data.get('Data', [])
        
        with open('stations_output.txt', 'w', encoding='utf-8') as f:
            if stations:
                f.write('Keys of first station object:\n')
                f.write(json.dumps(list(stations[0].keys())))
                f.write('\n\nAll stations:\n')
                f.write(json.dumps(stations, indent=2, ensure_ascii=False))
            
    except Exception as e:
        print(f'Error: {e}')
