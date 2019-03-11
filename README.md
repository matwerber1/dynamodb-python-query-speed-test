# dynamodb-python-query-speed-test

# Purpose

This script measures client-side latency when using boto3 to query DynamoDB.

There are two key tests:
1) Test the difference in performance between Python 2.7 and 3.7
2) Test the difference between querying items with one large attribute (144 random chars) vs. 24 smaller attributes (6 chars each, total 144 chars)

Note - this test is only client-side performance. To understand server-side DynamoDB performance, you should instead use CloudWatch metrics.

# TLDR; Test Results

1. A larger number of attributes requires significantly more client processing time to deserialize the response received from DynamoDB.
2. A larger number of attributes leads to larger response size (for the column headings). Since a single query is capped at 1 MB of data, this means fewer max rows can be retrieved per query. In other words, you can retrieve more rows per query if you use compress data into fewer columns. 
3. Python 3.7 deserializes responses from DynamoDB considerably faster than Python 2.7

# Credits

Thanks to switch180 (https://github.com/switch180) for a PR that cleaned up the code, added better timing measurement, local DDB support, and a few other improvements. Thanks to Chad Tindel for pointing out the increased number of items per query is possible when using smaller columns and code errors in the LastEvaluatedKey logic. 

# Disclaimer

* There are many variables to consider when measuring latency, such as distance between server and client, available CPU & memory, bandwidth, etc. Testing in your own environment is the most reliable benchmark.

# Usage

```sh
$ python run.py --help
usage: run.py [-h] [--table TABLE] [--num-items-to-query NUM_ITEMS_TO_QUERY]
              [--seed SEED] [--columns COLUMNS] [--region REGION]
              [--endpoint ENDPOINT] [--rounds ROUNDS]

Test DynamoDB query API speed.

optional arguments:
  -h, --help            show this help message and exit
  --table TABLE         dynamodb table to use for testing
  --num-items-to-query NUM_ITEMS_TO_QUERY
                        number of items to query per API call
                        If you specify 0, then each round of querying
                        will execute a single query to pull as many
                        items as possible; LastEvaluatedKey will be ignored.
  --seed SEED           number of items to put into test table
  --columns COLUMNS     valid values are "one" or "many"
  --region REGION       Region name for auth and endpoint construction
  --endpoint ENDPOINT   Override endpoint
  --rounds ROUNDS       Number of rounds
```

* If a populated table already exists with a hash and sort key named "hash_id" and "sort_id" of type string, you can omit the --seed and --columns options.
* **WARNING** - If the --seed and --columns options are provided, all items (if any) from the specified table will be deleted! Then, it will be seeded with the number of items specified by --seed and --columns will determine whether it has one or many (24) additional attributes containing random characters.
* If --seed and --columns is specified and the table does not already exist, the table will be created with provisioned capacity of 100 RCU and 100 WCU.
* If --table is omitted, it will default to "query_testing_table".
* If --num-items-to-query is omitted, it will default to 5000.
* If --rounds is ommited, it will default to 1000.
* If --seed is specified, you must also specify the --columns attribute.
* --columns value of "one" will create a single 144 random character field in addition to the hash and sort key.
* --columns value of "many" will create a 24 fields of 6 random characters each (144 chars total) in addition to the hash and sort key.
* You can run this script against the AWS-managed DynamoDB service or DynamoDB local

# Example results

Testing was performed on an m5.large in us-east-1 against a DynamoDB table in the same region.

## Example 1 - Python 2.7 with many columns

Query time was ~700ms

```sh
$ python run.py --region us-east-1  --table query_testing_table --rounds 5 --num-items-to-query 1800 --seed 5000 --columns many

-query 1800 --seed 5000 --columns many
DynamoDB table query_testing_table already exists, skipping table creation.
Scanning for items to delete...
Deleting items...
3000 items deleted.
Seeding ddb table...
Batch writing complete. Wrote 5000 total new items.
        Executing 'run_test'
------------------------------
                Executing 'test_query_time'
        Executing 'query_it'
        Function 'query_it' execution time: 728.9ms
Retrieved row count:1800, Number of Query: 1
                Function 'test_query_time' execution time: 729.0ms
------------------------------
Executing 'test_query_time'
        Executing 'query_it'
        Function 'query_it' execution time: 690.4ms
Retrieved row count:1800, Number of Query: 1
Function 'test_query_time' execution time: 690.4ms
------------------------------
Executing 'test_query_time'
        Executing 'query_it'
        Function 'query_it' execution time: 693.2ms
Retrieved row count:1800, Number of Query: 1
Function 'test_query_time' execution time: 693.3ms
------------------------------
Executing 'test_query_time'
        Executing 'query_it'
        Function 'query_it' execution time: 706.3ms
Retrieved row count:1800, Number of Query: 1
Function 'test_query_time' execution time: 706.4ms
------------------------------
Executing 'test_query_time'
        Executing 'query_it'
        Function 'query_it' execution time: 690.5ms
Retrieved row count:1800, Number of Query: 1
Function 'test_query_time' execution time: 690.5ms
        Function 'run_test' execution time: 3509.7ms
Done!
```

## Example 2 - Python 2.7 with one column

Query time improved from ~700ms down to ~120ms just by using one big attribute (144 chars) instead of 24 small attributes (6 chars each, 144 total).

```sh
$ python run.py --region us-east-1  --table query_testing_table --rounds 5 --num-items-to-query 1800 --seed 5000 --columns one

-query 1800 --seed 5000 --columns one
DynamoDB table query_testing_table already exists, skipping table creation.
Scanning for items to delete...
Deleting items...
5000 items deleted.
Seeding ddb table...
Batch writing complete. Wrote 5000 total new items.
        Executing 'run_test'
------------------------------
                Executing 'test_query_time'
        Executing 'query_it'
        Function 'query_it' execution time: 128.4ms
Retrieved row count:1800, Number of Query: 1
                Function 'test_query_time' execution time: 128.5ms
------------------------------
Executing 'test_query_time'
        Executing 'query_it'
        Function 'query_it' execution time: 123.1ms
Retrieved row count:1800, Number of Query: 1
Function 'test_query_time' execution time: 123.2ms
------------------------------
Executing 'test_query_time'
        Executing 'query_it'
        Function 'query_it' execution time: 134.2ms
Retrieved row count:1800, Number of Query: 1
Function 'test_query_time' execution time: 134.2ms
------------------------------
Executing 'test_query_time'
        Executing 'query_it'
        Function 'query_it' execution time: 112.6ms
Retrieved row count:1800, Number of Query: 1
Function 'test_query_time' execution time: 112.7ms
------------------------------
Executing 'test_query_time'
        Executing 'query_it'
        Function 'query_it' execution time: 121.0ms
Retrieved row count:1800, Number of Query: 1
Function 'test_query_time' execution time: 121.1ms
        Function 'run_test' execution time: 619.7ms
Done!
```

## Example 3 - Python 3.7 with one column

Query time improved from ~120ms down to ~75ms just by switching from Python 2.7 to Python 3.7!

```sh
$ python3.7 run.py --region us-east-1  --table query_testing_table --rounds 5 --num-items-to-query 1800

DynamoDB table query_testing_table already exists, skipping table creation.
        Executing 'run_test'
------------------------------
                Executing 'test_query_time'
        Executing 'query_it'
        Function 'query_it' execution time: 109.4ms
Retrieved row count:1800, Number of Query: 1
                Function 'test_query_time' execution time: 109.4ms
------------------------------
Executing 'test_query_time'
        Executing 'query_it'
        Function 'query_it' execution time: 75.3ms
Retrieved row count:1800, Number of Query: 1
Function 'test_query_time' execution time: 75.3ms
------------------------------
Executing 'test_query_time'
        Executing 'query_it'
        Function 'query_it' execution time: 76.6ms
Retrieved row count:1800, Number of Query: 1
Function 'test_query_time' execution time: 76.6ms
------------------------------
Executing 'test_query_time'
        Executing 'query_it'
        Function 'query_it' execution time: 76.1ms
Retrieved row count:1800, Number of Query: 1
Function 'test_query_time' execution time: 76.2ms
------------------------------
Executing 'test_query_time'
        Executing 'query_it'
        Function 'query_it' execution time: 70.3ms
Retrieved row count:1800, Number of Query: 1
Function 'test_query_time' execution time: 70.3ms
        Function 'run_test' execution time: 408.0ms
Done!
```

# Example 4 - Run against DynamoDB local

For reference, you can also run this script against DDB local:

```sh
$ python run.py --table some-table --num-items-to-query 5876 --endpoint http://localhost:8000
DynamoDB table some-table already exists, skipping table creation.
	Executing 'run_test'
------------------------------
		Executing 'test_query_time'
	Executing 'query_it'
	Function 'query_it' execution time: 404.2ms
	Executing 'query_it'
	Function 'query_it' execution time: 79.6ms
Retrieved row count:5876, Number of Query: 2
		Function 'test_query_time' execution time: 486.1ms
```