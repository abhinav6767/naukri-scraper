import requests
from session import setup_naukri_session

session, headers = setup_naukri_session()
params = {
    "noOfResults": 20,
    "urlType": "search_by_keyword",
    "searchType": "adv",
    "pageNo": 1,
    "src": "jobsearchDesk",
    "keyword": "Ai Automation",
    "k": "Ai Automation",
    "freshness": "1",
    "wfhType": "3,4",
    "lid": "4114",
    "companyType": "213,215",
    "jt": "11,9",
    "experience": "2",
    "ctcFilter": "10to15"
}

r = session.get(
    'https://www.naukri.com/jobapi/v3/search',
    params=params,
    headers={'appid': '109', 'systemid': 'Naukri', 'clientid': 'd3skt0p', 'nkparam': headers.get('nkparam')}
)
print("Status:", r.status_code)
print("Response:", r.text)
