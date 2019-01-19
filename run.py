from __future__ import print_function # Python 2/3 compatibility
import uuid
import random
import string
import time
import json
import boto3
import argparse
from boto3.dynamodb.conditions import Key, Attr

parser = argparse.ArgumentParser(description='Test DynamoDB query API speed.')



parser.add_argument('--table', type=str, default='query_testing_table',
                     help='dynamodb table to use for testing')

parser.add_argument('--num-items-to-query', type=int, default=5000,
                     help='number of items to query per API call')

#if seed is omitted, no new items will be created
parser.add_argument('--seed', type=int,
                     help='number of items to put into test table')

parser.add_argument('--columns', type=str,
                     help='valid values are "one" or "many"')

parser.add_argument('--region', type=str, default='us-east-1',
      help='Region name for auth and endpoint construction')
      
parser.add_argument('--endpoint', type=str,
      help='Override endpoint')

parser.add_argument('--rounds', type=int, default = 1000,
      help='Number of rounds')

args = parser.parse_args()

# if seed is present, then --columns is required. columns determines whether we have one big columns (144 chars) or 24 smaller columns (6 chars each)
if args.seed != None and args.columns == None:
    raise Exception('If you specify --columns, you must also specify --seed parameter')
elif args.seed == None and args.columns != None:
    raise Exception('If you specify --seed, you must also specify --columns parameter')

# for tracing w/ xray in Lambda (assuming you've packaged the sdk or imported via Lambda layer)
#from aws_xray_sdk.core import xray_recorder
#from aws_xray_sdk.core import patch
## patches boto3 to use xray
#patch(['boto3'])

# some calls use the resource, some use the client
boto_args = {'service_name': 'dynamodb'}
boto_args['region_name'] = args.region
if not args.endpoint:
    boto_args['endpoint_url'] = 'https://dynamodb.{}.amazonaws.com'.format(boto_args['region_name'])
else:
    boto_args['endpoint_url'] = args.endpoint

ddb_resource = boto3.resource(**boto_args)
ddb_client = boto3.client(**boto_args)

total_query_count_all_queries = 0
total_elapsed_time_all_queries = 0

# --------------------------------------------------------------------------------------------
def main():
      
    tableName = args.table
    tableResource = ddb_resource.Table(tableName)
    
    # arbitrary hash key which is used to seed our data; the seed script will also assign a random UUID as the sort key to each item
    hash_id = '1000'

    # number of items to add to DDB table
    items_to_seed = args.seed
    
    # if calling test_query_time, this is the number of items per query and total # of items to retrieve; i.e. a value of 50 and 200 would make 4 calls of 50 items each (4x50 = 200)
    num_items_to_query = args.num_items_to_query
    
    # Create DynamoDB table
    #TODO - add error handling if table already exists
    create_ddb_table(tableName)
    
    # if seed is given (should be an int), then empty any existing table contents and re-seed table
    if args.seed != None:
      # Empty contents of table
      delete_all_items_in_table(tableResource)
    
      #Use this to seed DynamoDB table
      seed_ddb_table(tableResource, hash_id, items_to_seed, args.columns)
    
    # use this to test query read time
    @time_it
    def run_test():
        for x in range(args.rounds):
          print('-' * 30)
          test_query_time(tableResource, hash_id, num_items_to_query)
    run_test()
    # use this to test scan read time
    #test_scan_time(table, hash_id, 1,200)
    
    return {
      'statusCode': 200,
      'body': json.dumps('Done!')
    }

# --------------------------------------------------------------------------------------------
def time_it(func):
    time_it.active = 0
    def tt(*args, **kwargs):
        print_slugs = dict()
        time_it.active += 1
        t0 = time.time()
        print_slugs['tabs'] = '\t' * (time_it.active)
        print_slugs['name'] = func.__name__
        print("{tabs}Executing '{name}'".format(**print_slugs))
        res = func(*args, **kwargs)
        print_slugs['time'] = (time.time() - t0) * 1000
        print("{tabs}Function '{name}' execution time: {time:.1f}ms".format(**print_slugs))
        time_it.active += -1
        return res
    return tt
# --------------------------------------------------------------------------------------------

def ddb_table_exists(tableName):
    try:
      response = ddb_client.describe_table(TableName=tableName)
      return True
    except ddb_client.exceptions.ResourceNotFoundException:
      pass
    return False

# --------------------------------------------------------------------------------------------
def create_ddb_table(tableName):
    
    if ddb_table_exists(tableName):
      print('DynamoDB table ' + tableName + ' already exists, skipping table creation.')
    
    else:  
      print('Creating DynamoDB table ' + tableName + '...')
      
      response = ddb_client.create_table(
        AttributeDefinitions=[
          {
            'AttributeName': 'hash_id',
            'AttributeType': 'S'
          },
          {
            'AttributeName': 'sort_id',
            'AttributeType': 'S'
          },
        ],
        TableName=tableName,
        KeySchema=[
          {
            'AttributeName': 'hash_id',
            'KeyType': 'HASH'
          },
          {
            'AttributeName': 'sort_id',
            'KeyType': 'RANGE'
          },
        ],
        BillingMode='PROVISIONED',
        ProvisionedThroughput={
          'ReadCapacityUnits': 100,
          'WriteCapacityUnits': 100
        },
      )
      
      print('Table created.')
      
# --------------------------------------------------------------------------------------------
def delete_all_items_in_table(table):
    count = 0
    scanned_items = []
    print('Scanning for items to delete...')  
    
    response = table.scan(
      ProjectionExpression='#hash, #sort',
      ExpressionAttributeNames={
        '#hash': 'hash_id', 
        '#sort': 'sort_id'
      }
    )
    scanned_items = response['Items']
    while 'LastEvaluatedKey' in response:
      response = table.scan(
          ExclusiveStartKey=response['LastEvaluatedKey'],
          ProjectionExpression='#hash, #sort',
          ExpressionAttributeNames={
            '#hash': 'hash_id', 
            '#sort': 'sort_id'
        }
      )
      scanned_items = scanned_items + response['Items']
        

        
    print('Deleting items...')
    with table.batch_writer() as batch:
      print('Deleting batch of items...')
      for each in scanned_items:
        count += 1
        batch.delete_item(Key=each)
    print(str(count) + ' items deleted.')
    
# --------------------------------------------------------------------------------------------
def seed_ddb_table(table, hash_id, item_count, columns):
    
    print('Seeding ddb table...')
    
    write_count = 0
    
    if columns == 'one':
    
      with table.batch_writer() as batch:
          
        for i in range(item_count):
            
          new_sort_id = str(uuid.uuid4())
          
          batch.put_item(Item={
            'hash_id': hash_id,
            'sort_id': new_sort_id,
            'field1': '\0'.join([id_generator(6)] * 24)
          }
        )
        
        write_count +=1
    
    elif columns == 'many':
      
      with table.batch_writer() as batch:
          
        for i in range(item_count):
            
          new_sort_id = str(uuid.uuid4())
          
          batch.put_item(Item={
            'hash_id': hash_id,
            'sort_id': new_sort_id,
            'field1': id_generator(6),
            'field2': id_generator(6),
            'field3': id_generator(6),
            'field4': id_generator(6),
            'field5': id_generator(6),
            'field6': id_generator(6),
            'field7': id_generator(6),
            'field8': id_generator(6),
            'field9': id_generator(6),
            'field10': id_generator(6),
            'field11': id_generator(6),
            'field12': id_generator(6),
            'field13': id_generator(6),
            'field14': id_generator(6),
            'field15': id_generator(6),
            'field16': id_generator(6),
            'field17': id_generator(6),
            'field18': id_generator(6),
            'field19': id_generator(6),
            'field20': id_generator(6),
            'field21': id_generator(6),
            'field22': id_generator(6),
            'field23': id_generator(6),
            'field24': id_generator(6)
          }
        )
        
        write_count +=1
    else:
      print('unkown table attributes parameter "' + tableAttributes + '", unable to seed table.')
    
      

    print("Batch writing complete. Wrote " + str(item_count) + " total new items.")

# --------------------------------------------------------------------------------------------
# generate random string
def id_generator(size=6, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))

# --------------------------------------------------------------------------------------------
@time_it
def test_query_time(table, hash_id, num_items_to_query):
    global total_query_count_all_queries
    
    item_count = 0
    query_count = 0
    @time_it
    def query_it(limit = num_items_to_query, exclusive_start_key = None):
        nonlocal query_count, item_count
        query_args = {
            'KeyConditionExpression': Key('hash_id').eq(hash_id),
            'Limit': limit,
        }
        if exclusive_start_key:
            query_args['ExclusiveStartKey'] = exclusive_start_key
        response =  table.query(**query_args)
        query_count += 1
        item_count += response['Count']
        return response
    response = query_it()
    
    while ('LastEvaluatedKey' in response and item_count < num_items_to_query):
      remaining_items_to_query = num_items_to_query - item_count
      incremental_start = time.time()
      response = query_it(remaining_items_to_query, response['LastEvaluatedKey'])

    # if we choose to run multiple queries in a loop, this tracks grand totals
    total_query_count_all_queries += query_count
    print("Retrieved row count:{}, Number of Query: {}".format(item_count, query_count))

    #print('Current query of ' + str(min(total_item_count, num_items_to_query)) + ' items took ' + str(query_count) + ' API calls and took ' + str(total_elapsed_time) + ', avg time across all API calls is:' + str(average_response_all_queries))

# --------------------------------------------------------------------------------------------
def _get_ddb_table_session(tableName):
      dynamodb = boto3.resource('dynamodb')
      table = dynamodb.Table(tableName)
      return table
        
if __name__ == '__main__':
      main()
