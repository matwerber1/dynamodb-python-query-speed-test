from __future__ import print_function # Python 2/3 compatibility
import uuid
import random
import string
import time
import json
import boto3
import sys
import argparse
from boto3.dynamodb.conditions import Key, Attr

parser = argparse.ArgumentParser(description='Test DynamoDB query API speed.')
args = None
ddb_resource = None
ddb_client = None

# bind raw_input to input for backwards compatibility w/ Python 2
try:
    input = raw_input
except NameError:
    pass


def configure_parser():

    global parser
    global args

    parser.add_argument(
        '--table',
        type=str,
        default='query_testing_table',
        help='dynamodb table to use for testing'
    )

    parser.add_argument(
        '--schema',
        type=str,
        default='schemas/long.schema'
    )

    parser.add_argument(
        '--seed',
        type=int,
        default=5000,
        help='number of items to write to table'
    )

    parser.add_argument(
        '--query',
        type=int,
        default=2500,
        help='number of items to query per API call'
    )

    parser.add_argument(
        '--region',
        type=str,
        default='us-east-1',
        help='Region name for auth and endpoint construction'
    )

    parser.add_argument(
        '--endpoint',
        type=str,
        help='Override endpoint'
    )

    parser.add_argument(
        '--rounds',
        type=int,
        default = 20,
        help='Number of rounds'
    )

    parser.add_argument(
        '--skip-seed',
        action='store_true'
    )

    parser.add_argument(
        '--mode',
        type=str,
        default='PAY_PER_REQUEST',
        help="Table capacity mode = 'PAY_PER_REQUEST' or 'PROVISIONED')"
    )

    parser.add_argument(
        '--rcu',
        type=int,
        default=200,
        help='Read capacity units (RCUs) (only for provisioned capacity mode)'
    )

    parser.add_argument(
        '--wcu',
        type=int,
        default=100,
        help='Write capacity units (WCUs) (only for provisioned capacity mode)'
    )

    args = parser.parse_args()


def configure_boto3():

    global ddb_resource
    global ddb_client

    boto_args = {'service_name': 'dynamodb'}
    boto_args['region_name'] = args.region

    if not args.endpoint:
        boto_args['endpoint_url'] = 'https://dynamodb.{}.amazonaws.com'.format(boto_args['region_name'])
    else:
        boto_args['endpoint_url'] = args.endpoint

    ddb_resource = boto3.resource(**boto_args)
    ddb_client = boto3.client(**boto_args)


def ask_user(prompt):

    check = str(input("{} ? (Y/N): ".format(prompt))).lower().strip()

    try:
        if check[0] == 'y':
            return True
        elif check[0] == 'n':
            return False
        else:
            print('Invalid Input')
            return ask_user()

    except Exception as error:
        print("Please enter valid inputs")
        print(error)
        return ask_user(prompt)


def execute_query_rounds(tableName, rounds, query_items, hash_id):

    tableResource = ddb_resource.Table(tableName)
    do_evaluate_next_keys = True

    if query_items == 0:
        # If query_items = 0, this means we actually want to query as many items
        # as possible in a single query. So, we set an arbitrarily large query
        # value with the assumption that, regardless of item size, we will hit
        # the 1 MB max result before we actually read 99999999999 items.
        query_items = 999999999
        do_evaluate_next_keys = False
        print("Running {} rounds, only 1 query per ".format(rounds)
            + "round, retrieving as many items as possible per query (up to 999999999 items)..."
        )
    else:
        print("Running {} rounds of {} items per query...\n".format(
            rounds, query_items)
        )

    d = {
        'query_count': 0,
        'item_count': 0,
        'consumed_capacity': 0,
        'elapsed_time': 0,
        'total_bytes': 0
    }

    for x in range(args.rounds):
        print('-' * 80)
        print('ROUND {}:'.format(x+1))
        response = execute_query_round(
            tableResource,
            hash_id,
            query_items,
            do_evaluate_next_keys
        )

        d['query_count'] += response['query_count']
        d['item_count'] += response['item_count']
        d['consumed_capacity'] += response['consumed_capacity']
        d['elapsed_time'] += response['elapsed_time']
        d['total_bytes'] += response['total_bytes']
        avg_time_per_item = d['elapsed_time'] / d['item_count']

    print('-' * 80 + '\n')
    print('GRAND TOTALS:')
    print('\tItems queried: {}'.format(d['item_count']))
    print('\tElapsed time: {:.1f} ms'.format(d['elapsed_time']))
    print('\tAvg. time per item: {:.3f} ms'.format(avg_time_per_item))


    print('-' * 80)


def execute_query_round(
                            table,
                            hash_id,
                            num_items_to_query,
                            do_evaluate_next_keys
                        ):
    d = {
        'query_count': 0,
        'item_count': 0,
        'remaining_count': num_items_to_query,
        'consumed_capacity': 0,
        'exclusive_start_key': None,
        'elapsed_time': 0,
        'total_bytes': 0
    }

    done = False
    
    while (not done):
        response = run_single_query(
            table,
            hash_id, 
            d['remaining_count'],
            d['exclusive_start_key']
        )

        capacity = response['ConsumedCapacity']['CapacityUnits']
        d['query_count'] += 1
        d['item_count'] += response['Count']
        d['remaining_count'] -= response['Count']
        d['consumed_capacity'] += capacity
        d['elapsed_time'] += response['elapsed_time']
        d['total_bytes'] += response['item_bytes']

        print('    Retrieved {} items with {} RCU in {:.1f} ms, size is ~{:,.1f} MB'
            .format(
                response['Count'],
                capacity,
                response['elapsed_time'],
                response['item_bytes']/1000000
            )
        )
        
        if (response['Count'] == 0):
            print('Unexpected error: query returned 0 results!')
            done = True
        elif (d['remaining_count'] <= 0):
            done = True
        else:
            done = False

    print('Total items: {}, queries: {},  RCUs: {}, time: {:.1f} ms, size: ~{:,.1f} MB'.format(
        d['item_count'],
        d['query_count'],
        d['consumed_capacity'],
        d['elapsed_time'],
        d['total_bytes']/1000000
    ))

    return d

def run_single_query(table, hash_id, limit, exclusive_start_key=None):
    
    query_args = {
        'KeyConditionExpression': Key('hash_id').eq(hash_id),
        'Limit': limit,
        'ReturnConsumedCapacity': 'TOTAL'
    }

    if exclusive_start_key and exclusive_start_key != None:
        query_args['ExclusiveStartKey'] = exclusive_start_key

    start_time = time.time()
    response =  table.query(**query_args)
    response['elapsed_time'] = (time.time() - start_time) * 1000
    response['item_bytes'] = get_query_response_size(response['Items'])
    return response


def utf8len(s):
    return len(s.encode('utf-8'))


def get_query_response_size(items):
    
    # https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/CapacityUnitCalculations.html
    item_bytes = 0

    for item in items:
        for key in item:
            item_bytes += len(key)
            item_bytes += utf8len(item[key])

    return item_bytes


def table_exists(tableName):
    try:
      response = ddb_client.describe_table(TableName=tableName)
      return True
    except ddb_client.exceptions.ResourceNotFoundException:
      pass
    return False


def create_table(tableName, mode, rcu, wcu):

    create_parameters = {
        'AttributeDefinitions': [
            {
                'AttributeName': 'hash_id',
                'AttributeType': 'S'
            },
            {
                'AttributeName': 'sort_id',
              'AttributeType': 'S'
            },
        ],
        'TableName': tableName,
        'KeySchema': [
            {
                'AttributeName': 'hash_id',
                'KeyType': 'HASH'
            },
            {
                'AttributeName': 'sort_id',
                'KeyType': 'RANGE'
            },
        ],
    }

    if (mode == 'PAY_PER_REQUEST'):
        print('Creating DynamoDB table "{}" with on-demand capacity...'
            .format(
                tableName
            )
        )
        create_parameters['BillingMode'] = 'PAY_PER_REQUEST'
    elif (mode == 'provisioned'):
        print('Creating DynamoDB table "{}" with provisioned capacity '
            .format(
                tableName
            )
            + ' of {} RCU and {} WCU'.format(rcu, wcu)
        )
        create_parameters['BillingMode'] = 'PROVISIONED'
        create_parameters['ProvisionedThroughput'] = {
            'ReadCapacityUnits': rcu,
            'WriteCapacityUnits': wcu
        }
    else:
        print('ERROR - Unrecognized capacity mode "{}", program ended!'.format(
            mode
        ))


    response = ddb_client.create_table(**create_parameters)

    table_status = 'CREATING'

    while (table_status != 'ACTIVE'):
        print('Table is {}, waiting for it to become ACTIVE...'.format(
                table_status)
        )
        response = ddb_client.describe_table(TableName=tableName)
        table_status = response['Table']['TableStatus']
        time.sleep(5)
      
    print('DynamoDB table is now active.')


def create_table_if_not_exists(tableName, mode, rcu, wcu):

    if table_exists(tableName):
        
        print('DynamoDB table "{}" already exists...'.format(tableName))

        update_table_capacity_mode(tableName, mode, rcu, wcu)

        if (args.skip_seed == True):
            print('Skipping delete of existing items...')
        else:
            print('WARNING - Proceeding will delete all exisiting data!' )
            if (ask_user('OK to proceed?') == True):
                delete_all_items_in_table(tableName)
            else:
                print('Program execution stopped.')
                sys.exit()

    else:
        create_table(tableName, mode, rcu, wcu)


def update_table_capacity_mode(tableName, new_mode, new_rcu, new_wcu):

    response = ddb_client.describe_table(TableName=tableName)

    current_mode = response['Table']['BillingModeSummary']['BillingMode']
    current_rcu = response['Table']['ProvisionedThroughput']['ReadCapacityUnits']
    current_wcu = response['Table']['ProvisionedThroughput']['WriteCapacityUnits']

    updateTable = True

    parameters = {
        'TableName': tableName,
        'BillingMode': new_mode
    }

    if (
        (current_mode != new_mode and new_mode == 'PROVISIONED')
            or (
                current_mode == new_mode and new_mode == 'PROVISIONED'
                and (new_rcu != current_rcu or new_wcu != current_wcu)
            )
    ):
        if current_rcu != new_rcu or current_wcu != new_wcu:

            print('Changing table to PROVISIONED capacity of {} RCU and {} WCU...'
                .format(new_rcu, new_wcu)
            )

            parameters['ProvisionedThroughput'] = {
                'ReadCapacityUnits': new_rcu,
                'WriteCapacityUnits': new_wcu
            }

    elif current_mode != new_mode and new_mode == 'PAY_PER_REQUEST':
        print('Changing to PAY_PER_REQUEST capacity mode...')

    else:
        updateTable = False

    if updateTable:
        response = ddb_client.update_table(**parameters)
        table_status = 'UPDATING'
        while (table_status != 'ACTIVE'):
            print('Table is {}, waiting for it to become ACTIVE...'.format(
                    table_status)
            )
            response = ddb_client.describe_table(TableName=tableName)
            table_status = response['Table']['TableStatus']
            time.sleep(5)
        
        print('DynamoDB table is now active.')


def delete_all_items_in_table(table):

    count = 0
    scanned_items = []
    tableResource = ddb_resource.Table(table)
    
    print('Scanning for items to delete...')
    response = tableResource.scan(
        ProjectionExpression='#hash, #sort',
        ExpressionAttributeNames={
            '#hash': 'hash_id',
            '#sort': 'sort_id'
        }
    )
    scanned_items = response['Items']

    while 'LastEvaluatedKey' in response:
        response = tableResource.scan(
            ExclusiveStartKey=response['LastEvaluatedKey'],
            ProjectionExpression='#hash, #sort',
            ExpressionAttributeNames={
                '#hash': 'hash_id',
                '#sort': 'sort_id'
            }
        )
        scanned_items = scanned_items + response['Items']

    print('Deleting items...')
    with tableResource.batch_writer() as batch:
        for each in scanned_items:
            count += 1
            batch.delete_item(Key=each)

    print(str(count) + ' items deleted.')


def getSchemaFromFile(schemaFile):

    file = open(schemaFile, 'r')
    lines = file.read().splitlines() 
    schema = {}

    for line in lines:
        fieldName, fieldLength = line.split(',', 2)
        schema[fieldName] = int(fieldLength)

    return schema


def getRandomItemFromSchema(hash_id, sort_id, schema):
    
    item = {
        'hash_id': hash_id,
        'sort_id': sort_id
    }

    for fieldName in schema:
        item[fieldName] = id_generator(schema[fieldName])

    return item


def seed_table(table, schemaFile, hash_id, item_count):

    if (args.skip_seed == True):
        print('Skipping seed of table...')
    else:
        print('Seeding ddb table...')
        write_count = 0
        tableResource = ddb_resource.Table(table)
        schema = getSchemaFromFile(schemaFile)

        with tableResource.batch_writer() as batch:
            for i in range(item_count):
                write_count +=1
                sort_id = str(write_count)
                item = getRandomItemFromSchema(hash_id, sort_id, schema)
                batch.put_item(Item=item)    
        
        print("Wrote " + str(item_count) + " items to table.")


def id_generator(size=6, chars=string.ascii_uppercase + string.digits):

    return ''.join(random.choice(chars) for _ in range(size))


def _get_ddb_table_session(tableName):

      dynamodb = boto3.resource('dynamodb')
      table = dynamodb.Table(tableName)
      return table


def main():

    # We arbitrarily put everything under the same hash ID
    # to make our program logic easier. 
    hash_id = "1000"

    configure_parser()
    configure_boto3()
    create_table_if_not_exists(
        args.table,
        args.mode,
        args.rcu,
        args.wcu
    )
    seed_table(args.table, args.schema, hash_id, args.seed)    
    execute_query_rounds(args.table, args.rounds, args.query, hash_id)
    print('Done!')


if __name__ == '__main__':
      main()
