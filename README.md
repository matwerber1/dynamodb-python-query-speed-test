# dynamodb-python-query-speed-test

# Purpose

Test effect of many vs. fewer columns of data on client-side speed of queries against Amazon DynamoDB.

# Results

Refer to the write-up at [https://aws.amazon.com/blogs/database/optimizing-amazon-dynamodb-scan-latency-through-schema-design/](https://aws.amazon.com/blogs/database/optimizing-amazon-dynamodb-scan-latency-through-schema-design/)

Thanks to switch180 & Chad Tindel for their contributions and suggestions.  

# Disclaimer

* There are many variables to consider when measuring latency, such as distance between server and client, available CPU & memory, bandwidth, etc. Testing in your own environment is the most reliable benchmark.

# Usage

```sh
usage: run.py [-h] [--table TABLE] [--schema SCHEMA] [--seed SEED]
              [--query QUERY] [--region REGION] [--endpoint ENDPOINT]
              [--rounds ROUNDS] [--skip-seed] [--mode MODE] [--rcu RCU]
              [--wcu WCU]

Test DynamoDB query API speed.

optional arguments:
  -h, --help           show this help message and exit
  --table TABLE        dynamodb table to use for testing
  --schema SCHEMA
  --seed SEED          number of items to write to table
  --query QUERY        number of items to query per API call
  --region REGION      Region name for auth and endpoint construction
  --endpoint ENDPOINT  Override endpoint
  --rounds ROUNDS      Number of rounds
  --skip-seed
  --mode MODE          Table capacity mode = 'PAY_PER_REQUEST' or
                       'PROVISIONED')
  --rcu RCU            Read capacity units (RCUs) (only for provisioned
                       capacity mode)
  --wcu WCU            Write capacity units (WCUs) (only for provisioned
                       capacity mode)
```

## Default settings

Default settings are below:

```sh
# Default settings:
# -----------------------------
# region   = us-east-1
# table    = query_testing_table
# schema   = schemas/long.schema
# seed     = 5000
# query    = 2500
# rounds   = 10
# mode     = PROVISIONED
# rcu      = 200 
# wcu      = 100
# endpoint = (blank) - only needed if running local DDB
```

# Examples

1. Run test with default settings:

```sh
python run.py
```
