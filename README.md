# s3 syncer

A tool for uploading and downloading objects from a s3 endpoint. Build for easy usability. You can also copy objects from one s3 storage to another s3 storage (works with different providers f.e. MinIO and scality).
Support for unix-like glob patterns for local files and prefix search on s3 keys.

# Features
- upload files to s3 bucket
- download s3 objects to local filesystem
- transfer objects from one bucket to another bucket (even for different providers)
- list objects/files in bucket or given local path
- supports unix-like glob patterns for local files
- print either created objects in s3, created local file, deleted s3 objects or listed objects to stdout
- delete function that deletes all s3 objects that match the given key prefix (only deletes s3 objects)
- skip TLS verification when needed
- suppress all output to stdout or stderr when needed
- compatibility with all s3 providers
- blazingly fast

# Usage

You can use the tool as a module in other scripts or as a cli tool. The module is called `s3_syncer`. The binary is called `s3-syncer` and can be used as follows:

```
usage: A script for uploading and downloading objects from a s3 bucket.
       You can also copy objects from one s3 storage to another s3 storage
       (works with different providers f.e. MinIO and Scality).
       Support for unix-like glob patterns for local files and prefix search on s3 keys.
       [-h] [-l] -a ACCESS_KEY -s SECRET_KEY [-d] [--to-stdout] [-c [CERT ...]] [--insecure]
       [--suppress] [--no-partial-paths] [--version] source_path [destination_path]

positional arguments:
  source_path           Path to the source object. For local files it can contain 
                        unix-like glob/wildcard patterns (Don`t forget the quotes).
                        Can be object in s3 or local file. S3 object path needs to have 
                        `s3://{s3-bucket}+{s3-namespace}.{s3-host}:{s3-port}/{path-to-filename}` form.

  destination_path      Path to the destination object. Can be object in s3 or local file.
                        S3 object path needs to have 
                        `s3://{s3-bucket}+{s3-namespace}.{s3-host}:{s3-port}/{path-to-filename}` form.
                        `{path-to-filename}` is more like a prefix or filter to search for the keys.
                        So it doesn`t has to match the exact key or `folder` in the bucket. 
                        `{s3-namespace}` is obsolete in s3 scality or any other s3 compatible system
                        that dont uses namespaces.

options:
  -h, --help                                  show this help message and exit
  -l, --list                                  Lists objects in the given source path. 
                                              Doesn`t download files. Prints to stdout.
  -a ACCESS_KEY, --access_key ACCESS_KEY      Access key id for the s3 service. Can be the username.
                                              Alternatively use env var S3_ACCESS_KEY_ID_1 for the first,
                                              S3_ACCESS_KEY_ID_2 for the second access key.
                                              Seperate multiple access keys with another argument call.
  -s SECRET_KEY, --secret_key SECRET_KEY      Secret key for the s3 service.
                                              Alternatively use env var S3_SECRET_ACCESS_KEY_1 for the first,
                                              S3_SECRET_ACCESS_KEY_2 for the second secret key.
                                              Seperate multiple secret keys with another argument call.
  -d, --delete                                Deletes all objects that match the given key prefix.
                                              Will only delete objects if the 'source_path' is a s3 endpoint.
  --to-stdout                                 Print either created objects in s3 or created local file or deleted s3 objects to stdout.
  -c CERT, --cert CERT                        Path to certificate to use for the requests. If you need two different certificates because
                                              you're transfering files from one s3 bucket to another s3 bucket, comma separate their paths.
                                              You can use one certificate for both connections. Automatically enables secure connection over TLS.
                                              When no certificate is given, use system certificates instead to verify the connection.
                                              When connection could not be verified, uses http instead.
  --insecure                                  Do not validate TLS certificates as fallback when
                                              given or system certificates failed to validate.
  --suppress                                  Suppresses all output to stdout or stderr.
  --no-partial-paths                          Does not autocomplete partial paths to full paths. F.e. partial path: 'docs/cod' and
                                              full path of a key: 'docs/coding/work/main.py' would not autocomplete to
                                              path 'docs/coding'. So you have to provide a full path ('directory').
  --version                                   Prints the version of the installed package 's3-syncer'.
```

# Examples
## Upload examples

All examples with following example file-tree:
```
project
├──README.md
└──docs/
    ├──index.html
    ├──resources.html
    ├──_static/
    |    └──file.png
    └──_static/
        ├──startpage.html
        └──javascripts/
        |    └──application.js
        └──changelog/
            └──1.0.0/
                └──html/
                    └──index.html
```
Current working directory is `/home/local/project`
---
Upload of a directory recursively (standard behavior):
```shell
s3-syncer "/home/local/project/docs/" s3://my-bucket+my-namespace.mys3.domain.com:9021/project5-docs --cert /path/to/bundle.crt --access_key ACCESS_KEY --secret_key SECRET_KEY
```
Would create following keys in the bucket `my-bucket`:

`project5-docs/index.html`\
`project5-docs/resources.html`\
`project5-docs/_static/file.png`\
`project5-docs/_static/startpage.html`\
`project5-docs/_static/javascripts/application.js`\
`project5-docs/changelog/1.0.0/html/index.html`

---
Upload of a single file:
```shell
s3-syncer "README.md" s3://my-bucket+my-namespace.mys3.domain.com:9021/project5 -c /path/to/bundle.crt -a ACCESS_KEY -s SECRET_KEY
```
Would create following key in the bucket `my-bucket`: 

`project5/README.md`

---
Upload of all files in a directory that end with `.html` by use of unix-like glob/wildcard pattern. This would create the s3 key with: `project5/html_docs` + (remove prefix `complete path until first occurrence of an glob/wildcard pattern` of `found file`):
```shell
s3-syncer "/home/local/project/docs/**/*.html" s3://my-bucket+my-namespace.mys3.domain.com:9021/project5/html_docs/ -c /path/to/bundle.crt -a ACCESS_KEY -s SECRET_KEY
```
Would create following keys in the bucket `my-bucket`:

`project5/html_docs/index.html`\
`project5/html_docs/resources.html`\
`project5/html_docs/_static/startpage.html`\
`project5/html_docs/changelog/1.0.0/html/index.html`

## `--list` example

Same example as above but only lists the found files without uploading them. With the `--list` or `-l` option:
```shell
s3-syncer --list "/home/local/project/docs/**/*.html" s3://my-bucket+my-namespace.mys3.domain.com:9021/project5/html_docs/ -c /path/to/bundle.crt -a ACCESS_KEY -s SECRET_KEY
```
Would create following output:
```
/home/local/project/docs/index.html
/home/local/project/docs/resources.html
/home/local/project/docs/_static/startpage.html
/home/local/project/docs/changelog/1.0.0/html/index.html

Found 4 object(s) in the source path.
```

# Download examples

After upload there are following keys in the bucket `my-bucket`:

`project5/README.md`\
`project5-docs/index.html`\
`project5-docs/resources.html`\
`project5-docs/_static/file.png`\
`project5-docs/_static/startpage.html`\
`project5-docs/_static/javascripts/application.js`\
`project5-docs/changelog/1.0.0/html/index.html`\
`project5/html_docs/index.html`\
`project5/html_docs/resources.html`\
`project5/html_docs/_static/startpage.html`\
`project5/html_docs/changelog/1.0.0/html/index.html`

---
Download of a directory with use of prefix matching. Always looks for the next full directory (f.e. prefix `project5` would get `project5-docs` when finding `project5-docs/_static/file.png` key):
```shell
s3-syncer s3://my-bucket+my-namespace.mys3.domain.com:9021/project5 -c /path/to/bundle.crt -a ACCESS_KEY -s SECRET_KEY
```
Would create following local files:

`/home/local/project/README.md`\
`/home/local/project/index.html`\
`/home/local/project/resources.html`\
`/home/local/project/_static/file.png`\
`/home/local/project/_static/startpage.html`\
`/home/local/project/_static/javascripts/application.js`\
`/home/local/project/changelog/1.0.0/html/index.html`\
`/home/local/project/html_docs/index.html`\
`/home/local/project/html_docs/resources.html`\
`/home/local/project/html_docs/_static/startpage.html`\
`/home/local/project/html_docs/changelog/1.0.0/html/index.html`

---
Another example of the download of a directory with use of prefix matching (only difference to previous example is slightly different prefix `project5/`):
```shell
s3-syncer s3://my-bucket+my-namespace.mys3.domain.com:9021/project5/ -c /path/to/bundle.crt -a ACCESS_KEY -s SECRET_KEY
```
Would create following local files:

`/home/local/project/README.md`\
`/home/local/project/html_docs/index.html`\
`/home/local/project/html_docs/resources.html`\
`/home/local/project/html_docs/_static/startpage.html`\
`/home/local/project/html_docs/changelog/1.0.0/html/index.html`

## `--list` example

Same example as above but only lists the found keys in the bucket without downloading them. With the `--list` or `-l` option:
```shell
s3-syncer --list s3://my-bucket+my-namespace.mys3.domain.com:9021/project5/ -c /path/to/bundle.crt -a ACCESS_KEY -s SECRET_KEY
```
Would create following output:
```
project5/README.md
project5/html_docs/index.html
project5/html_docs/resources.html
project5/html_docs/_static/startpage.html
project5/html_docs/changelog/1.0.0/html/index.html

Found 5 object(s) in the source path.
```
---
Download of files in a custom directory:
```shell
s3-syncer s3://my-bucket+my-namespace.mys3.domain.com:9021/project5/ ../my-new-project -c /path/to/bundle.crt -a ACCESS_KEY -s SECRET_KEY
```
Would create following local files:

`/home/local/my-new-project/README.md`\
`/home/local/my-new-project/html_docs/index.html`\
`/home/local/my-new-project/html_docs/resources.html`\
`/home/local/my-new-project/html_docs/_static/startpage.html`\
`/home/local/my-new-project/html_docs/changelog/1.0.0/html/index.html`

## Deleting objects in a s3 bucket
Same example as above but now all the objects that match the given key prefix `project5/` are deleted:
```shell
s3-syncer --delete s3://my-bucket+my-namespace.mys3.domain.com:9021/project5/ -c /path/to/bundle.crt -a ACCESS_KEY -s SECRET_KEY
```
Would delete following objects in the bucket:

`project5/README.md`\
`project5/html_docs/index.html`\
`project5/html_docs/resources.html`\
`project5/html_docs/_static/startpage.html`\
`project5/html_docs/changelog/1.0.0/html/index.html`

**Notes:**
- the deleting only works when ONE s3 endpoint is given as the `source_path`
- when using option `--to-stdout` the keys of the deleted objects are printed to `stdout`. For example see [here](#print-created-objectsfiles-to-stdout)

*In the following examples we pretend that the objects are not deleted.*

---
Download of a single file:
```shell
s3-syncer s3://my-bucket+my-namespace.mys3.domain.com:9021/project5/README.md ../my-new-project/ -c /path/to/bundle.crt -a ACCESS_KEY -s SECRET_KEY
```
Would create following local file:

`/home/local/my-new-project/README.md`

---
Download of a single file but with other local filename (only works when given prefix exactly matches a key in the bucket):
```shell
s3-syncer s3://my-bucket+my-namespace.mys3.domain.com:9021/project5/README.md ../my-new-project/docs.md -c /path/to/bundle.crt -a ACCESS_KEY -s SECRET_KEY
```
Would create following local file:

`/home/local/my-new-project/docs.md`

---
Use credentials as env variables and disable use of TLS by missing the `-c/--cert` argument (don't forget to change the port to a http port):
```shell
S3_ACCESS_KEY_ID=ACCESS_KEY S3_SECRET_ACCESS_KEY=SECRET_KEY s3-syncer s3://my-bucket+my-namespace.mys3.domain.com:9020/path/to/file.html
```

## Print created objects/files to stdout
In this example it prints the locally created files to stdout with the argument `--to-stdout`:
```shell
s3-syncer --to-stdout s3://my-bucket+my-namespace.mys3.domain.com:9021/project5/ ../my-new-project -c /path/to/bundle.crt -a ACCESS_KEY -s SECRET_KEY
```

Would create following output:
```
Downloading objects from S3 object storage ...


Downloaded 6 file(s).
/home/local/my-new-project/README.md
/home/local/my-new-project/html_docs/index.html
/home/local/my-new-project/html_docs/resources.html
/home/local/my-new-project/html_docs/_static/startpage.html
/home/local/my-new-project/html_docs/changelog/1.0.0/html/index.html
```
You can of course suppress output of `stderr` and the only output are the created local files:
```shell
s3-syncer --to-stdout s3://my-bucket+my-namespace.mys3.domain.com:9021/project5/ ../my-new-project -c /path/to/bundle.crt -a ACCESS_KEY -s SECRET_KEY 2> /dev/null
```
```
/home/local/my-new-project/README.md
/home/local/my-new-project/html_docs/index.html
/home/local/my-new-project/html_docs/resources.html
/home/local/my-new-project/html_docs/_static/startpage.html
/home/local/my-new-project/html_docs/changelog/1.0.0/html/index.html
```

## Only download s3 keys that match exactly an fully existing path in the bucket
This can be done by the option `--no-partial-paths`. So f.e. with a partial path given like: `proje` and an existing key in the bucket is: `project5/html_docs/index.html` would not autocomplete to full path `project5`. So you have to provide a full path ('directory') to get results. If a part path like `proje` is provided and this option is used, it will not find anything. Other than when you use f.e. `project5` or `project5/`. This is a full path and therefore keys are found.

# Copy objects from s3 storage to another s3 storage
Following command copies objects from first (f.e. MinIO) s3 storage to the second (f.e. scality) s3 storage. Each access keys and secrets keys need a separate argument call. In this example we also use two different certificates for the request. Note that scality doesn't have namespaces:
```shell
s3-syncer s3://my-bucket+my-namespace.mys3.domain.com:9021/project5/ s3://my-other-bucket+myminio.domain.com:443/new_project5/ -c /path/to/bundle.crt -c /path/to/scality.crt -a FIRST_ACCESS_KEY -a SECOND_ACCESS_KEY -s FIRST_SECRET_KEY -s SECOND_SECRET_KEY
```

Would create following objects in the bucket `my-other-bucket` on s3 endpoint `myminio.domain.com:443`:

`new_project5/README.md`\
`new_project5/html_docs/index.html`\
`new_project5/html_docs/resources.html`\
`new_project5/html_docs/_static/startpage.html`\
`new_project5/html_docs/changelog/1.0.0/html/index.html`

# Handling of errors

When something goes wrong while uploading, transfering or downloading, it raises a custom Exception object with an attribute called `failed_objects` that contains a list of all failed objects.
