import json
import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection
import requests
from requests_aws4auth import AWS4Auth
import inflection as inflection

# OpenSearch
REGION = 'us-east-1'
HOST = 'search-photos-eyf22mfhlythiyjql3ocffb6hi.us-east-1.es.amazonaws.com'
INDEX = 'photos'


def send_to_lex(text):
    lex_client = boto3.client('lexv2-runtime')
    try:
        response = lex_client.recognize_text(
            botId='ZVLC5ED2YZ', # MODIFY HERE
            botAliasId='TSTALIASID', # MODIFY HERE
            localeId='en_US',
            sessionId='Search_LF2',
            text=text
        )
    except Exception as e:
        print(f'failed to send to lex: {e}')
        return []
    
    labels = []
    try:
        slots = response['interpretations'][0]['intent']['slots']
        for key, value in slots.items():
            if value is not None:
                labels.append(inflection.singularize(value['value']['interpretedValue']))
    except Exception as e:
        print(f'failed to get labels: {e}')
    print(f'labels are {labels}')
    return labels


def search_open_search(labels):
    def get_awsauth(region, service):
        cred = boto3.Session().get_credentials()
        return AWS4Auth(
            cred.access_key,
            cred.secret_key,
            region,
            service,
            session_token=cred.token
        )

    query = {
        "size": 3,
        "query": {
            "bool": {
                "should": []
            }
        }
    }
    for label in labels:
        query['query']['bool']['should'].append({
            "match": {
                "labels": label
            }
        })
    
    opensearch_client = OpenSearch(
        hosts = [{'host': HOST, 'port': 443}],
        http_auth = get_awsauth(REGION, 'es'),
        use_ssl = True,
        verify_certs = True,
        connection_class = RequestsHttpConnection
    )
    try:
        response = opensearch_client.search(
            index='photos',
            body=query
        )
        hits = response['hits']['hits']
        img_list = []
        for element in hits:
            objectKey = element['_source']['objectKey']
            bucket = element['_source']['bucket']
            image_url = f'https://{bucket}.s3.amazonaws.com/{objectKey}'
            img_list.append(image_url)
        return img_list
    except Exception as e:
        print(f'failed to search from OpenSearch: {e}')


def lambda_handler(event, context):
    print('Hello')
    print(f'eventss is {event}')
    q = event['queryStringParameters']['q']
    print(f'q is {q}')
    labels = send_to_lex(q)
    if not labels:
       return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': '*',
            },
            'body': json.dumps({'results': "No Results found"})
        }
    img_list = search_open_search(labels)
    if not img_list:
       return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': '*',
            },
            'body': json.dumps({'results': "No Results found"})
        }
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': '*',
        },
        'body': json.dumps({'results': img_list})
    }
