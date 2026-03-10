import requests
from session import setup_naukri_session

print("Setting up session...")
session, headers = setup_naukri_session()
base_params = {
    "noOfResults": 20,
    "urlType": "search_by_keyword",
    "searchType": "adv",
    "pageNo": 1,
    "src": "jobsearchDesk",
    "keyword": "Ai Automation",
    "k": "Ai Automation"
}

suspect_params = {
    "freshness": "1",
    "wfhType": "3,4",
    "lid": "4114",
    "companyType": "213,215",
    "jt": "11,9",
    "experience": "2",
    "ctcFilter": "10to15"
}

url = 'https://www.naukri.com/jobapi/v3/search'
req_headers = {'appid': '109', 'systemid': 'Naukri', 'clientid': 'd3skt0p', 'nkparam': headers.get('nkparam')}

print("\nTesting all params...")
params = {**base_params, **suspect_params}
r = session.get(url, params=params, headers=req_headers)
print("All Params Status:", r.status_code)

if r.status_code == 400:
    print("\nTesting parameters one by one to find the culprit...")
    for key, val in suspect_params.items():
        test_params = {**base_params, key: val}
        r = session.get(url, params=test_params, headers=req_headers)
        print(f"Testing just {key}={val} -> Status: {r.status_code}")
else:
    print("Wait, it succeeded this time?!")

