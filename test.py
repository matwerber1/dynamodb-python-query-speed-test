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
parser.add_argument('-table', type=str,required=True,help='dynamodb table to use for testing')
parser.add_argument('-query', type=int,required=True, help='number of items to query per API call')
parser.add_argument('-seed', type=int, help='number of items to put into test table')
parser.add_argument('-columns', type=str, help='valid values are "one" or "many"')
args = parser.parse_args()

if args.seed != None and args.columns == None:
	print('If you specify -columns, you must also specify -seed parameter')
elif args.seed == None and args.columns != None:
	print('If you specify -seed, you must also specify -columns parameter')

# some calls use the resource, some use the client
ddb_resource = boto3.resource('dynamodb')
ddb_client = boto3.client('dynamodb')

# start the main execution
main()

# --------------------------------------------------------------------------------------------
def main():

	tableName      = args.table
	tableResource  = ddb_resource.Table(tableName)
	items_to_seed  = args.seed
	hash_id        = "1000"                            # arbitrary hash key which is used to seed our data; the seed script will also assign a random UUID as the sort key to each item
	items_to_query = args.query

	create_ddb_table(tableName)

	if args.seed != None:
		delete_all_items_in_table(tableResource)
		seed_ddb_table(tableResource, hash_id, items_to_seed, args.columns)

	for x in range(1000):
		test_query_time(tableResource, hash_id, items_to_query)

	print('Done.')

# --------------------------------------------------------------------------------------------
def ddb_table_exists(tableName):
	try:
		response = ddb_client.describe_table(TableName=tableName)
		return True
	except ddb_client.exceptions.ResourceNotFoundException:
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
		  BillingMode='PAY_PER_REQUEST'
		)

	print('Table created.')

# --------------------------------------------------------------------------------------------
def delete_all_items_in_table(table):

	print('Scanning for items to delete...')

	scan = table.scan(
		ProjectionExpression='#hash, #sort',
		ExpressionAttributeNames={
		  '#hash': 'hash_id',
		  '#sort': 'sort_id'
		}
	)

	count = 0

	print('Deleting items...')

	with table.batch_writer() as batch:
		for each in scan['Items']:
			count += 1
			batch.delete_item(Key=each)

	print(str(count) + ' items deleted.')

# --------------------------------------------------------------------------------------------
def seed_ddb_table(table, hash_id, item_count, columns):

	print('Preparing to seed ddb table...')

	write_count = 0

	if columns == 'one':
		with table.batch_writer() as batch:
			for i in range(item_count):
				new_sort_id = str(uuid.uuid4())

				batch.put_item(
					Item={
						'hash_id': hash_id,
						'sort_id': new_sort_id,
						'field1': id_generator(144)
					}
				)
				write_count +=1

	elif columns == 'many':
		with table.batch_writer() as batch:
			for i in range(item_count):
				new_sort_id = str(uuid.uuid4())

				batch.put_item(
					Item={
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
		print('unkown table attributes parameter "' + columns + '", unable to seed table.')

	print("Batch writing complete. Wrote " + str(item_count) + " total new items.")

# --------------------------------------------------------------------------------------------
# generate random string
def id_generator(size=6, chars=string.ascii_uppercase + string.digits):
	return ''.join(random.choice(chars) for _ in range(size))

# --------------------------------------------------------------------------------------------
def test_query_time(table, hash_id, items_to_query):

	start        = time.time()
	elapsed_time = 0
	item_count   = 0
	api_count    = 0

	response = table.query(
		KeyConditionExpression=Key('hash_id').eq(hash_id),
		Limit=items_to_query
	)

	elapsed_time = time.time() - start
	item_count   += response['Count']
	api_count    += 1

	while ('LastEvaluatedKey' in response and item_count < items_to_query):

		remaining_items_to_query = items_to_query - api_count

		start = time.time()

		response = table.query(
			KeyConditionExpression=Key('hash_id').eq(hash_id),
			Limit=remaining_items_to_query,
			ExclusiveStartKey=response['LastEvaluatedKey']
		)

		elapsed_time  = time.time() - start
		item_count   += response['Count']
		api_count  +=1

	print(str(api_count) + ' api calls made for ' + str(item_count) + ' items took ' + str(elapsed_time) + ' seconds')

# --------------------------------------------------------------------------------------------
def _get_ddb_table_session(tableName):

	dynamodb = boto3.resource('dynamodb')
	table    = dynamodb.Table(tableName)

	return table