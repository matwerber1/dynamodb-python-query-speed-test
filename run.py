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

# Examples:
#
# Create table and seed it
# python run.py --table dynamodb-speed-test-one --seed 10000 --columns one --region us-east-2 --rounds 5
#
# Query a table that already exists
# python run.py --table dynamodb-speed-test-one --region us-east-2 --rounds 5

parser.add_argument('--table', type=str, default='query_testing_table',
                     help='dynamodb table to use for testing')


# If num-items-to-query is zero, we will instead try to query as many items as
# possible that can fit within a single query result
parser.add_argument('--num-items-to-query', type=int, default=5000,
                     help='number of items to query per API call')

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

# if seed is present, then --columns is required. columns determines whether we
# have one big columns (144 chars) or 24 smaller columns (6 chars each)
if args.seed != None and args.columns == None:
    raise Exception('If you specify --seed, you must also specify --columns parameter')
elif args.seed == None and args.columns != None:
    raise Exception('If you specify --columns, you must also specify --seed parameter')

boto_args = {'service_name': 'dynamodb'}
boto_args['region_name'] = args.region

if not args.endpoint:
    boto_args['endpoint_url'] = 'https://dynamodb.{}.amazonaws.com'.format(boto_args['region_name'])
else:
    boto_args['endpoint_url'] = args.endpoint

ddb_resource = boto3.resource(**boto_args)
ddb_client = boto3.client(**boto_args)


def main():

    tableName      = args.table
    tableResource  = ddb_resource.Table(tableName)
    items_to_seed  = args.seed
    hash_id        = "1000"                            # arbitrary hash key which is used to seed our data; the seed script will also assign a random UUID as the sort key to each item
    num_items_to_query = args.num_items_to_query
    rounds = args.rounds
    do_evaluate_next_keys = True

    create_ddb_table(tableName)

    if args.seed != None:
      delete_all_items_in_table(tableResource)
      seed_ddb_table(tableResource, hash_id, items_to_seed, args.columns)

    if num_items_to_query == 0:
        # We want to retrieve as many items as possible in a 
        # single query. 99999999 should be sufficiently large
        # to handle that
        num_items_to_query = 999999999
        do_evaluate_next_keys = False
        print("Running {} rounds, only 1 query per round, retrieving as many items as possible per query...".format(rounds))
    else:
        print("Running {} rounds of {} items per query...".format(rounds, num_items_to_query))



    @time_it
    def run_test():
        for x in range(args.rounds):
          print('-' * 30)
          test_query_time(tableResource, hash_id, num_items_to_query, do_evaluate_next_keys)
    run_test()

    print('Done!')


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


def ddb_table_exists(tableName):
    try:
      response = ddb_client.describe_table(TableName=tableName)
      return True
    except ddb_client.exceptions.ResourceNotFoundException:
      pass
    return False


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

      table_status = 'CREATING'

      while (table_status == 'CREATING'):
        print('Table is {}, waiting for it to become ACTIVE...'.format(table_status))
        response = ddb_client.describe_table(TableName=tableName)
        table_status = response['Table']['TableStatus']
        time.sleep(5)
      
      print('DynamoDB table is now active.')


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
      for each in scanned_items:
        count += 1
        batch.delete_item(Key=each)

    print(str(count) + ' items deleted.')


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


def id_generator(size=6, chars=string.ascii_uppercase + string.digits):

    return ''.join(random.choice(chars) for _ in range(size))


@time_it
def test_query_time(table, hash_id, num_items_to_query, do_evaluate_next_keys):

    remaining_items_to_query = num_items_to_query
    d = {'query_count': 0, 'item_count': 0}

    @time_it
    def query_it(limit = num_items_to_query, exclusive_start_key = None):
  
        query_args = {
            'KeyConditionExpression': Key('hash_id').eq(hash_id),
            'Limit': limit,
        }

        if exclusive_start_key:
            query_args['ExclusiveStartKey'] = exclusive_start_key
        response =  table.query(**query_args)

        d['query_count'] += 1
        d['item_count'] += response['Count']
        print('            Items retrieved: {}'.format(response['Count']))
        d['LastEvaluatedKey'] = response['LastEvaluatedKey']

        return d

    response = query_it()

    while (do_evaluate_next_keys and 'LastEvaluatedKey' in response and d['item_count']  < remaining_items_to_query):
      remaining_items_to_query = num_items_to_query - d['item_count'] 
      incremental_start = time.time()
      response = query_it(remaining_items_to_query, response['LastEvaluatedKey'])

    print("Total retrieved row count:{}, Total number of Queries: {}".format(d['item_count'], d['query_count']))

def _get_ddb_table_session(tableName):

      dynamodb = boto3.resource('dynamodb')
      table = dynamodb.Table(tableName)
      return table

if __name__ == '__main__':
      main()
