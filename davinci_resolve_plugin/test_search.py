#!/usr/bin/env python3
"""Test semantic search API directly."""

import boto3
import requests

# Authenticate
cognito = boto3.client('cognito-idp', region_name='us-east-1')
response = cognito.initiate_auth(
    AuthFlow='USER_PASSWORD_AUTH',
    ClientId='20ed2pfv92mr5j6l274heoocj8',
    AuthParameters={
        'USERNAME': 'fleandro@jw.org',
        'PASSWORD': 'Password-456',
    }
)
token = response['AuthenticationResult']['IdToken']

# Test semantic search
headers = {'Authorization': f'Bearer {token}'}

print("\n--- SEMANTIC SEARCH for 'cat' ---")
url = 'https://dtjiv80feeke7.cloudfront.net/v1/search?q=cat&semantic=true&pageSize=50'
print(f'URL: {url}')
r = requests.get(url, headers=headers)
data = r.json()

print(f'Status: {data.get("status")}')
if 'data' in data and data['data']:
    results = data['data'].get('results', [])
    metadata = data['data'].get('searchMetadata', {})
    print(f'Total results: {metadata.get("totalResults", len(results))}')
    print(f'Results returned: {len(results)}')
    for i, res in enumerate(results[:5]):
        storage = res.get('DigitalSourceAsset', {}).get('MainRepresentation', {}).get('StorageInfo', {})
        name = storage.get('fullPath', 'unknown')
        score = res.get('score', 'n/a')
        print(f'  {i+1}. {name} (score: {score})')

print("\n--- KEYWORD SEARCH for 'cat' ---")
url = 'https://dtjiv80feeke7.cloudfront.net/v1/search?q=cat&semantic=false&pageSize=50'
print(f'URL: {url}')
r = requests.get(url, headers=headers)
data = r.json()

print(f'Status: {data.get("status")}')
if 'data' in data and data['data']:
    results = data['data'].get('results', [])
    metadata = data['data'].get('searchMetadata', {})
    print(f'Total results: {metadata.get("totalResults", len(results))}')
    print(f'Results returned: {len(results)}')
    for i, res in enumerate(results[:5]):
        storage = res.get('DigitalSourceAsset', {}).get('MainRepresentation', {}).get('StorageInfo', {})
        name = storage.get('fullPath', 'unknown')
        score = res.get('score', 'n/a')
        print(f'  {i+1}. {name} (score: {score})')

print("\n--- BROWSE ALL (wildcard) ---")
url = 'https://dtjiv80feekte7.cloudfront.net/v1/search?q=*&semantic=false&pageSize=50'
print(f'URL: {url}')
r = requests.get(url, headers=headers)
data = r.json()

print(f'Status: {data.get("status")}')
if 'data' in data and data['data']:
    results = data['data'].get('results', [])
    metadata = data['data'].get('searchMetadata', {})
    print(f'Total results: {metadata.get("totalResults", len(results))}')
else:
    print(f'Response: {data.get("status")} - {data.get("message", "")}')
