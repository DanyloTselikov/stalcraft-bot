import os, requests
from dotenv import load_dotenv

load_dotenv('.env')
region = os.getenv('REGION', 'eu')
limit = os.getenv('PRICE_LIMIT', '50000')
print('Регион:', region, '| Порог цены/шт:', limit)

headers = {
    'Client-Id': os.getenv('SC_CLIENT_ID'), 
    'Client-Secret': os.getenv('SC_CLIENT_SECRET')
}

r = requests.get(
    f'https://eapi.stalcraft.net/{region}/auction/y3nmw/lots', 
    headers=headers,
    params={'limit': 10, 'sort': 'buyout_price', 'order': 'asc'}, 
    timeout=30
)

print('Регион:', region, '| Статус:', r.status_code)

if r.status_code == 200:
    data = r.json()
    print('Всего лотов:', data.get('total'))
    for lot in data.get('lots', []):
        amount = lot.get('amount', 1) or 1
        buyout = lot.get('buyoutPrice', 0)
        per = buyout / amount if buyout else 0
        print(f"{amount}шт | выкуп {buyout} | {per:.0f}/шт | ставка {lot.get('currentPrice')}")
else:
    print(r.text[:300])
