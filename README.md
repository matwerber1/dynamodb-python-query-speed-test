# dynamodb-python-query-speed-test

# Purpose

This script measures client-side latency when using boto3 to query DynamoDB. 

Again, this test is on client-side performance rather than DynamoDB itself. To understand DynamoDB performance, you should instead use CloudWatch metrics for your table(s) in question.

# Results

See examples at end of readme, see below for summary: 

1. When a query retrieves many items each with many attributes, the python client takes notably longer to deserialize/parse responses.
2. When a query retrieves many items with a single attribute that, in aggregate, is the same size as the "many attributes" test, the client-side deserialize/parse occurs much faster.
3. Python 3.7 performed significantly faster than Python 2.7 (I saw ~2x improvement on larger queries); 
4. On very smaller queries (a few items), Python 2.7 and 3.7 had comparable response times. 

# Disclaimer

* This is a quick and dirty, unofficial test and may be subject to error.
* There are many variables to consider when measuring latency; please run your own tests to be sure!
* To minimize impact of location, latency, etc., I ran my tests un a sufficiently sized EC2 instance (e.g. m4.large) in the same region as the DynamoDB table. 

# Overview
This script performs the following:

1) Creates the user-specified DynamoDB table if it does not already exist.
    * the hash key will be a string attribute named "hash_id"
    * the sort key will be a string attribute named "sort_key"
2) Optionally seeds the table with a user-specified number of items. 
    * all items will be seeded with the same hash_id of "1000" (**Note 1**)
    * each item will receive a random UUID as its sort_id
    * The user must specify "many" or "one" for the --columns flag when seeding the table...
        * "many" will create 24 additional fields, each containing 6 random characters (144 chars total)
        * "one" will create a single additional field containing 144 random characters
    * When seeding the table, the script first deletes any existing items from said table
4) Runs a dynamodb.query() API call against a user-specified dynamoDB table.

**Note 1** - I used the same partition key (aka hash key) for testing for both simplicity as well as testing / confirming throughput of a single partition. 

# Usage

1. Seed table with 3000 items each containing 24 fields of 6 chars each (in addition to the hash_id and sort_id fields); repeatedly query 2800 items from the table.

```sh
python test.py -table ddb-speed-test -query 2800 -seed 3000 -columns many
```

2. Seed table with 3000 items each containing a single field of 144 chars each (in addition to the hash_id and sort_id fields); repeatedly query 2800 items from the table.

```sh
python test.py -table ddb-speed-test -query 2800 -seed 3000 -columns one
```

3. Same as #1 above, but do not seed table (assumes it has been previously seeded)

```sh
python test.py -table ddb-speed-test -query 2800
```

# Example Results

Again, please perform your own testing. These results are only meant to share some basic examples of testing latency. These were performed over a short period of time and not necessarily in the most scientific manner.

Testing environment was EC2 m4.large running in same region as the DynamoDB table.

Example 1 - Python 2.7 querying 3000 items with same hash_id, with 24 attributes of 6 chars each. Response times were approximately **~1.1 seconds per query!**
```
$ python test.py -table ddb-speed-test -query 2800 -seed 3000 -columns many
DynamoDB table ddb-speed-test already exists, skipping table creation.
Scanning for items to delete...
Deleting items...
Deleting batch of items...
2938 items deleted.
Preparing to seed ddb table...
Batch writing complete. Wrote 3000 total new items.
Current query of 2800 items took 1 API calls and took 1.11540293694, avg time across all API calls is:1.11540293694
Current query of 2800 items took 1 API calls and took 1.10201001167, avg time across all API calls is:1.1087064743
Current query of 2800 items took 1 API calls and took 1.08828496933, avg time across all API calls is:1.10189930598
...
```

Example 2 - Python 2.7 - querying 3000 items with same hash_id, with single attribute of 144 random chars. **Response times improved to approximately ~200ms per API query** just by "compacting" the additional fields into a single attribute of the same size.

```
$ python test.py -table ddb-speed-test -query 2800 -seed 3000 -columns one
DynamoDB table ddb-speed-test already exists, skipping table creation.
Scanning for items to delete...
Deleting items...
Deleting batch of items...
2938 items deleted.
Preparing to seed ddb table...
Batch writing complete. Wrote 3000 total new items.
Current query of 2800 items took 1 API calls and took 0.204576969147, avg time across all API calls is:0.204576969147
Current query of 2800 items took 1 API calls and took 0.197309970856, avg time across all API calls is:0.200943470001
Current query of 2800 items took 1 API calls and took 0.170806884766, avg time across all API calls is:0.190897941589
...
```

Example 3 - Python 3.7 - same as example 2, except using Python 3.7 instead of 2.7. As you can see, response times improved even further, down to ~120ms.

```
$ python3.7 test.py -table ddb-speed-test -query 2800 -seed 3000 -columns one                                      
DynamoDB table ddb-speed-test already exists, skipping table creation.
Scanning for items to delete...
Deleting items...
Deleting batch of items...
3124 items deleted.
Preparing to seed ddb table...
Batch writing complete. Wrote 3000 total new items.
Current query of 2800 items took 1 API calls and took 0.154924392700195, avg time across all API calls is:0.154924392700195
Current query of 2800 items took 1 API calls and took 0.115370750427241, avg time across all API calls is:0.135147571637207
Current query of 2800 items took 1 API calls and took 0.1084184646064453, avg time across all API calls is:0.126237862626953
...
```
