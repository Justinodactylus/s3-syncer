# s3 syncer

A tool for uploading and downloading objects from a s3 endpoint.
Support for unix-like glob patterns for local files and prefix search on s3 keys.

# Usage

```
usage: A script for uploading and downloading objects from a s3 bucket.
       Support for unix-like glob patterns for local files and prefix search on s3 keys.
       [-h] [-l] [-c CERT] [-a ACCESS_KEY] [-s SECRET_KEY] source_path [destination_path]

positional arguments:
  source_path           Path to the source object. For local files it can contain 
                        unix-like glob/wildcard patterns (Don`t forget the quotes).
                        Can be object in s3 or local file. S3 object path needs to have 
                        `s3://{s3-bucket}.{s3-namespace}.{s3-host}:{s3-port}/{path-to-filename}` form.

  destination_path      Path to the destination object. Can be object in s3 or local file.
                        S3 object path needs to have 
                        `s3://{s3-bucket}.{s3-namespace}.{s3-host}:{s3-port}/{path-to-filename}` form.
                        `{path-to-filename}` is more like a prefix or filter to search for the keys.
                        So it doesn`t has to match the exact key or `folder` in the bucket.

options:
  -h, --help                                show this help message and exit
  -l, --list                                Lists objects in the given source path. 
                                            Doesn`t download files.
  -c CERT, --cert CERT                      Path to certificate to use for the requests.
                                            Automatically enables secure connection over TLS.
  -a ACCESS_KEY, --access_key ACCESS_KEY    Access key id for the s3 service. Can be the username.
                                            Alternatively use env var S3_ACCESS_KEY_ID.
  -s SECRET_KEY, --secret_key SECRET_KEY    Secret key for the s3 service.
                                            Alternatively use env var S3_SECRET_ACCESS_KEY.
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
Use credentials as env variables and disable use of TLS by missing the `-c/--cert` argument (don't forget to change the port to a http port):
```shell
S3_ACCESS_KEY_ID=ACCESS_KEY S3_SECRET_ACCESS_KEY=SECRET_KEY python3 s3-syncer.py s3://my-bucket.my-namespace.mys3.domain.com:9020/path/to/file.html
```

Upload of a directory recursively (always recursively) with TLS enabled:
```shell
python3 s3-syncer.py /home/local/project/docs/ s3://my-bucket.my-namespace.mys3.domain.com:9021/project5-docs --cert /path/to/bundle.crt --access_key ACCESS_KEY --secret_key SECRET_KEY
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
python3 s3-syncer.py README.md s3://my-bucket.my-namespace.mys3.domain.com:9021/project5 -c /path/to/bundle.crt -a ACCESS_KEY -s SECRET_KEY
```
Would create following key in the bucket `my-bucket`: 

`project5/README.md`

---
Upload of all files in a directory that end with `.html` by use of unix-like glob/wildcard pattern. This would create the s3 key with: `project5/html_docs` + (remove prefix `complete path until first occurrence of an glob/wildcard pattern` of `found file`):
```shell
python3 s3-syncer.py "/home/local/project/docs/**/*.html" s3://my-bucket.my-namespace.mys3.domain.com:9021/project5/html_docs/ -c /path/to/bundle.crt -a ACCESS_KEY -s SECRET_KEY
```
Would create following keys in the bucket `my-bucket`:

`project5/html_docs/index.html`\
`project5/html_docs/resources.html`\
`project5/html_docs/_static/startpage.html`\
`project5/html_docs/changelog/1.0.0/html/index.html`

## `--list` example

Same example as above but only lists the found files without uploading them. With the `--list` or `-l` option:
```shell
python3 s3-syncer.py --list "/home/local/project/docs/**/*.html" s3://my-bucket.my-namespace.mys3.domain.com:9021/project5/html_docs/ -c /path/to/bundle.crt -a ACCESS_KEY -s SECRET_KEY
```
Would create following output:
```
Found 4 object(s) in the source path:

/home/local/project/docs/index.html
/home/local/project/docs/resources.html
/home/local/project/docs/_static/startpage.html
/home/local/project/docs/changelog/1.0.0/html/index.html
```

# Download examples

After upload there are following keys in the bucket `my-bucket`:

`project5/README.md`\
`project5-docs/index.html`\
`project5-docs/resources.html`\
`project5-docs/_static/file.png`\
`project5-docs/_static/startpage.html`\
`project5-docs/_static/javascripts/application.js`\
`project5-docs/changelog/1.0.0/html/index.html`
`project5/html_docs/index.html`\
`project5/html_docs/resources.html`\
`project5/html_docs/_static/startpage.html`\
`project5/html_docs/changelog/1.0.0/html/index.html`

---
Download of a directory with use of prefix matching. Always looks for the next full directory (f.e. prefix `project5` would get `project5-docs` when finding `project5-docs/_static/file.png` key):
```shell
python3 s3-syncer.py s3://my-bucket.my-namespace.mys3.domain.com:9021/project5 -c /path/to/bundle.crt -a ACCESS_KEY -s SECRET_KEY
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
python3 s3-syncer.py s3://my-bucket.my-namespace.mys3.domain.com:9021/project5/ -c /path/to/bundle.crt -a ACCESS_KEY -s SECRET_KEY
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
python3 s3-syncer.py --list s3://my-bucket.my-namespace.mys3.domain.com:9021/project5/ -c /path/to/bundle.crt -a ACCESS_KEY -s SECRET_KEY
```
Would create following output:
```
Found 5 object(s) in the source path:

project5/README.md
project5/html_docs/index.html
project5/html_docs/resources.html
project5/html_docs/_static/startpage.html
project5/html_docs/changelog/1.0.0/html/index.html
```
---
Download of files in a custom directory:
```shell
python3 s3-syncer.py s3://my-bucket.my-namespace.mys3.domain.com:9021/project5/ ../my-new-project -c /path/to/bundle.crt -a ACCESS_KEY -s SECRET_KEY
```
Would create following local files:

`/home/local/my-new-project/README.md`\
`/home/local/my-new-project/html_docs/index.html`\
`/home/local/my-new-project/html_docs/resources.html`\
`/home/local/my-new-project/html_docs/_static/startpage.html`\
`/home/local/my-new-project/html_docs/changelog/1.0.0/html/index.html`

---
Download of a single file:
```shell
python3 s3-syncer.py s3://my-bucket.my-namespace.mys3.domain.com:9021/project5/README.md ../my-new-project/ -c /path/to/bundle.crt -a ACCESS_KEY -s SECRET_KEY
```
Would create following local file:

`/home/local/my-new-project/README.md`

---
Download of a single file but with other local filename (only works when given prefix exactly matches a key in the bucket):
```shell
python3 s3-syncer.py s3://my-bucket.my-namespace.mys3.domain.com:9021/project5/README.md ../my-new-project/docs.md -c /path/to/bundle.crt -a ACCESS_KEY -s SECRET_KEY
```
Would create following local file:

`/home/local/my-new-project/docs.md`

