import sys
from session import setup_naukri_session

try:
    session, headers = setup_naukri_session()
    r = session.get(
        'https://www.naukri.com/jobapi/v3/search', 
        params={'keyword':'software developer'}, 
        headers={'appid':'109', 'systemid':'Naukri', 'clientid':'d3skt0p', 'nkparam':headers.get('nkparam')}, 
        timeout=15
    )
    data = r.json()
    for f in data.get('clusters', []):
        if f.get('filterName') == 'Company type':
            print('Company Types:')
            for c in f.get('categoryList', []):
                print(f"ID: {c['id']} - {c['label']}")
            break
except Exception as e:
    print('Error:', e)
