#!/usr/bin/python3

import aiobotocore.session
import os
import sys
import glob
import asyncio
import requests
import urllib3
from importlib.metadata import version
from tempfile import TemporaryDirectory
from argparse import ArgumentParser
from pathlib import Path
from dataclasses import dataclass

urllib3.disable_warnings()

PARALLEL_OPEN_FILES = 500 # defines how many files should be downloaded/uploaded simultaneously
PATTERN = "s3://{s3-bucket}+{s3-namespace}.{s3-host}:{s3-port}/{path-to-filename}"

class ProcessException(Exception):
    def __init__(self, message, failed_objects):
        super().__init__(f"\u001b[31m{message}\u001b[0m")

        self.failed_objects = failed_objects

@dataclass
class ObjectPath:
    type: str
    path: str
    bucket: str | None
    url: str | None

def reset_stdouterr():
    "Reset stdout and stderr to default value."

    sys.stdout = sys.__stdout__
    sys.stderr = sys.__stderr__

async def _executor(
    func,
    *args,
    keys: list[str]
) -> list:
    "Takes a function + their args and a list of keys/files and executes the function with his args + each element in the list asynchronously."

    def define_action(
        delete: bool
    ):
        "Returns words for the terminal output depending on the action the user chooses."

        if delete:
            return "Delet", "in"
        elif delete is False:
            return "Download", "from"
        else:
            return "Upload", "to"

    failed_actions = []
    created_objects = []
    action, direction = define_action(args[-1] if isinstance(args[-1], bool) else None)

    print(f"{action}ing objects {direction} S3 object storage ...\n", file=sys.stderr)
    i = 0
    while True:
        futures = {}

        paginated_keys = keys[i * PARALLEL_OPEN_FILES : (i + 1) * PARALLEL_OPEN_FILES]
        if len(paginated_keys) == 0:
            break

        for object_file in paginated_keys:
            futures[asyncio.ensure_future(func(*args, object_file))] = object_file

        for future, object_file in futures.items():
            try:
                created_objects.append(await asyncio.gather(future))
            except Exception as e:
                print(f"\u001b[31m{e}\u001b[0m", file=sys.stderr)
                failed_actions.append(object_file)
        i += 1

    if len(failed_actions) > 0:
        print(f"\nCouldn't {action.lower()} following file(s):", file=sys.stderr)
        for failed in failed_actions:
            print(failed, file=sys.stderr)
        raise ProcessException(f"Couldn't {action.lower()} at least one file.", failed_actions)

    print(f"\n{action}ed {len(keys) - len(failed_actions)} file(s).", file=sys.stderr)

    return created_objects

def _get_next_dir(
    part_path: str,
    full_path: str,
    glob_pattern: bool = False
) -> str:
    """Return the next following directory from the part_path. Example: part_path: docs/cod , full_path example: docs/coding/work/main.py -> returns docs/coding
    if `glob_pattern` is true then return the longest common path of the initial glob/wildcard pattern and an actual found file.
    """

    if glob_pattern:
        return os.path.commonpath([part_path, full_path]).removesuffix("/")

    if not part_path:
        return ""
    part_path = part_path.removesuffix("/")
    return part_path + full_path.removeprefix(part_path).partition("/")[0]

async def list_objects(
    s3_client,
    object_path: ObjectPath,
    local: bool = False,
    no_partial_paths = False
) -> list[str]:
    """Returns a list of s3 keys or local files, depending on the type of the 'object_path' object.\n
    Arguments:

    s3_client AioBaseClient:
        Needs to be a AioBaseClient from 'aiobotocore.session' module for the source.

    object_path ObjectPath:
        Custom object that contains either a local file path or a s3 url and bucket.

    local bool:
        Specify if local files or s3 files should be listed.

    no_partial_paths bool:
        Does not autocomplete partial paths to full paths.
    """

    keys = []
    if local:
        # walk recursively through given path and return all files matching possible unix-glob pattern
        for file in glob.iglob(object_path.path, recursive=True):
            if Path(file).is_dir():
                for deeper_file in glob.iglob(file + "/**", recursive=True):
                    if Path(deeper_file).is_file():
                        keys.append(deeper_file)
            elif Path(file).is_file():
                keys.append(file)
    else:
        # iterate through pages when more than 1000 objects exist in the bucket with the given prefix
        paginator = s3_client.get_paginator('list_objects_v2')
        async for result in paginator.paginate(Bucket=object_path.bucket, Prefix=object_path.path):
            for object in result.get("Contents", []):
                keys.append(object.get("Key"))

        if no_partial_paths:
            all_keys = []
            for key in keys:
                full_part_path = _get_next_dir(object_path.path, key)
                #check if given prefix is a full path, if yes add it to list of keys
                if full_part_path == object_path.path.removesuffix("/"):
                    all_keys.append(key)
            keys = all_keys

    return keys

async def _upload_one_object(
    s3_client,
    bucket: str,
    file_source_path: str,
    s3_path: str,
    local_file: str
) -> str:
    "Upload a single file to a s3 bucket."

    # change source_path to the local file's parent dir if in general just a single file should be uploaded.
    if file_source_path == local_file:
        file_source_path = Path(local_file).parent.__str__()
    s3_file = os.path.join(s3_path, local_file.removeprefix(_get_next_dir(file_source_path, local_file, glob_pattern=True) + "/"))

    with open(local_file, mode='rb') as data:
        await s3_client.put_object(
            Body=data,
            Bucket=bucket,
            Key=s3_file
        )
    return s3_file

async def upload(
    s3_client,
    file_source: ObjectPath,
    s3_dest: ObjectPath,
) -> list[str]:
    """Gets a list of objects and uploads them asynchronously.

    s3_client AioBaseClient:
        Needs to be a AioBaseClient from 'aiobotocore.session' module for the destination.

    file_source ObjectPath:
        Custom object that needs to contains a local file path from where the files should be uploaded.

    s3_dest ObjectPath:
        Custom object that contains a url and bucket to a s3 endpoint to which the files should be uploaded.

    Returns list of objects that were created.
    """

    files = await list_objects(s3_client, file_source, local=True)

    return await _executor(_upload_one_object, s3_client, s3_dest.bucket, file_source.path, s3_dest.path, keys=files)

async def _download_one_object(
    s3_client,
    s3_source: ObjectPath,
    file_dest_path: str,
    delete: bool,
    s3_file: str
) -> str:
    "Downloads a single file from a s3 bucket and creates local dirs recursively if necessary and writes file to desired destination path."

    # allow to set a new name for a single file if the user exactly matches the s3 key in the bucket
    if s3_source.path != s3_file or Path(os.path.join(Path(s3_source.path), file_dest_path)).exists():
        file_dest_path = os.path.join(file_dest_path, s3_file.removeprefix(_get_next_dir(s3_source.path, s3_file) + "/"))

    if delete:
        await s3_client.delete_object(
            Bucket=s3_source.bucket,
            Key=s3_file
        )
        return s3_file

    # create local dirs recursively if they dont exist
    if not Path(file_dest_path).parent.exists():
        if file_dest_path.count("/") != 0:
            os.makedirs(Path(file_dest_path).parent.__str__(), exist_ok=True)

    response = await s3_client.get_object(
        Bucket=s3_source.bucket,
        Key=s3_file
    )

    with open(file_dest_path, "wb") as file:
        async with response['Body'] as data:
            file.write(await data.read())

    return file_dest_path

async def download(
    s3_client,
    s3_source: ObjectPath,
    file_dest_path: str,
    delete: bool = False,
    no_partial_paths: bool = False
) -> list[str]:
    """Gets a list of objects and downloads them asynchronously.

    s3_client AioBaseClient:
        Needs to be a AioBaseClient from 'aiobotocore.session' module for the source.

    s3_source ObjectPath:
        Custom object that needs to contain a s3 url and bucket.

    file_dest_path str:
        The path to a local directory or single file where downloaded files should be safed to.

    delete bool:
        Deletes all objects that match the given key prefix. Will only delete objects if the 's3_source' is a s3 endpoint.

    no_partial_paths bool:
        Does not autocomplete partial paths to full paths.

    Returns list of local files that were created.
    """

    keys = await list_objects(s3_client, s3_source, local=False, no_partial_paths=no_partial_paths)

    return await _executor(_download_one_object, s3_client, s3_source, file_dest_path, delete, keys=keys)

async def transfer_s3_to_s3(
    s3_client_source,
    s3_source: ObjectPath,
    s3_client_dest,
    s3_dest: ObjectPath,
    delete: bool = False,
    no_partial_paths: bool = False
) -> list[str]:
    """Transfers files from one s3 bucket to another s3 bucket.\n
    Arguments:

    s3_client_source AioBaseClient:
        Needs to be a AioBaseClient from 'aiobotocore.session' module for the source.

    s3_source ObjectPath:
        Custom object that needs to contain a s3 url and bucket.

    s3_client_dest AioBaseClient:
        Needs to be a AioBaseClient from 'aiobotocore.session' module for the destination.

    s3_dest ObjectPath:
        Custom object that needs to contain a s3 url and bucket.

    delete bool:
        Deletes all objects that match the given key prefix. Will only delete objects if the 's3_source' is a s3 endpoint.

    no_partial_paths bool:
        Does not autocomplete partial paths to full paths.

    Returns list of objects that were created in the destination bucket.
    """

    with TemporaryDirectory() as tmpd:
        files = await download(s3_client_source, s3_source, tmpd, delete, no_partial_paths=no_partial_paths)
        if delete:
            return files
        return await upload(s3_client_dest, ObjectPath("file", tmpd, None, None), s3_dest)

def _verify_https(
    kwargs: dict,
    url: str,
    insecure: bool = False,
) -> dict:
    "Returns modified kwargs depending whether it could verify given certificate or with system certificates, otherwise use http."

    kwargs["endpoint_url"] = f"https://{url}"
    tmp_kwargs = kwargs.copy()
    cert = tmp_kwargs["verify"]
    if not cert or (cert and not cert.exists()):
        tmp_kwargs["verify"] = True

    # try to validate with given certificate or with system certs.
    try:
        requests.get(tmp_kwargs["endpoint_url"], verify=tmp_kwargs["verify"])
        return tmp_kwargs
    except Exception: pass

    if insecure:
        tmp_kwargs.update({"verify": False})
        print("Could not verify with given or system certificates. Skip TLS verification ...", file=sys.stderr)

        # try to use TLS but skip validation
        try:
            requests.get(tmp_kwargs["endpoint_url"], verify=tmp_kwargs["verify"])
            return tmp_kwargs
        except Exception: pass

    # use http
    if not cert:
        print("Could not verify and use TLS. Using http instead ...", file=sys.stderr)
        tmp_kwargs.update({"verify": False, "use_ssl": False, "endpoint_url": tmp_kwargs["endpoint_url"].replace("https", "http")})

    return tmp_kwargs

async def _s3_syncer(
    source_path: str = None,
    destination_path: str = ".",
    access_key: list = None,
    secret_key: list = None,
    lst: bool = False,
    delete: bool = False,
    to_stdout: bool = False,
    suppress: bool = False,
    insecure: bool = False,
    no_partial_paths: bool = False,
    certs: list[Path] = None
) -> list[str]:
    if suppress:
        class DummyFile(object):
            def write(self, x): pass
        # suppress stdout/stderr
        sys.stdout = DummyFile()
        sys.stderr = DummyFile()

    def s3_object_path_parser(
        path: str
    ) -> ObjectPath:
        "Returns a parsed ObjectPath object that contains the path, type of the path and when its from type 's3', the bucket name and endpoint-url."

        if not path.startswith("s3://"):
            return ObjectPath("file", os.path.realpath(path), None, None)

        path = path.replace("s3://", "")

        file_path = path.partition("/")[2]
        url = path.partition("/")[0]
        bucket = url.rpartition("+")[0]
        url = url.rpartition("+")[2]

        if not bucket:
            raise ProcessException(f"Given s3 url 's3://{path}' has wrong form. Must match following pattern: '{PATTERN}'", path)

        return ObjectPath("s3", file_path, bucket, url)

    if not isinstance(access_key, list) or not isinstance(secret_key, list):
        raise ProcessException(f"Given access key or secret key have not the right type 'list'. Access key has type {type(access_key)}. Secret key has type {type(secret_key)}", None)
    if len(access_key) > 2 or len(secret_key) > 2:
        raise ProcessException(f"To many access keys or secret keys are given. See list(s):\nAccess keys: {access_key}\nSecret keys: {secret_key}", None)

    object_source_path = s3_object_path_parser(source_path)
    object_dest_path = s3_object_path_parser(destination_path)

    url = object_source_path.url if object_source_path.type == "s3" else object_dest_path.url
    if not url:
        raise ProcessException("Could not parse a url out of source or destination path", None)

    kwargs = {"service_name": "s3",
              "aws_access_key_id": os.getenv("S3_ACCESS_KEY_ID_1", access_key[0]),
              "aws_secret_access_key": os.getenv("S3_SECRET_ACCESS_KEY_1", secret_key[0]),
              "verify": certs[0] if certs else None,
              "use_ssl": True}

    created_objects = []

    async with aiobotocore.session.get_session().create_client(**_verify_https(kwargs, url, insecure)) as s3_client:
        if lst:
            keys = await list_objects(s3_client, object_source_path, local=object_source_path.type == "file", no_partial_paths=no_partial_paths)
            for key in keys:
                print(key, file=sys.stdout if to_stdout else sys.stderr)

            print(f"\nFound {len(keys)} object(s) in the source path.", file=sys.stderr)

            reset_stdouterr()

            return keys

        # define whether objects should be upload, downloaded or transfered to another s3 storage
        if object_source_path.type == "file":
            created_objects = await upload(s3_client, object_source_path, object_dest_path)
        elif object_dest_path.type == "file":
            created_objects = await download(s3_client, object_source_path, object_dest_path.path, delete, no_partial_paths)
        else:
            kwargs["aws_access_key_id"] = os.getenv("S3_ACCESS_KEY_ID_2", access_key[-1])
            kwargs["aws_secret_access_key"] = os.getenv("S3_SECRET_ACCESS_KEY_2", secret_key[-1])
            kwargs["verify"] = certs[-1] if certs else None
            async with aiobotocore.session.get_session().create_client(
                **_verify_https(kwargs, object_dest_path.url, insecure)
            ) as s3_client_dest:
                created_objects = await transfer_s3_to_s3(s3_client, object_source_path, s3_client_dest, object_dest_path, delete, no_partial_paths)

    # print created or deleted objects to stdout
    if to_stdout:
        for obj in created_objects:
            for x in obj:
                print(x, file=sys.stdout)

    reset_stdouterr()

    return created_objects

def s3_syncer(
    source_path: str,
    access_key: list[str],
    secret_key: list[str],
    destination_path: str = ".",
    lst: bool = False,
    delete: bool = False,
    to_stdout: bool = False,
    suppress: bool = False,
    insecure: bool = False,
    no_partial_paths: bool = True,
    certs: list[str] = None,
) -> list[str]:
    """Can upload or download objects from and to a s3 bucket. Can also transfer files from one bucket to another.\n
    Arguments:

    source_path str:
        Path to the source object. For local files it can contain unix-like glob/wildcard patterns (Don't forget the quotes). Can be object in s3 or local file. S3 object path needs to have 's3://{s3-bucket}+{s3-namespace}.{s3-host}:{s3-port}/{path-to-filename}' form.

    access_key list[str]:
        Access key id for the s3 service. Can be the username. Alternatively use env var S3_ACCESS_KEY_ID. Separate multiple access keys with another argument call.

    secret_key list[str]:
        Secret key for the s3 service. Alternatively use env var S3_SECRET_ACCESS_KEY. Separate multiple secret keys with another argument call.

    destination_path str: 
        Path to the destination object. Can be object in s3 or local file. S3 object path needs to have 's3://{s3-bucket}+{s3-namespace}.{s3-host}:{s3-port}/{path-to-filename}' form. '{{path-to-filename}}' is more like a prefix or filter to search for the keys. So it doesn't has to match the exact key or 'folder' in the bucket. '{{s3-namespace}}' is obsolete in s3 scality or any other s3 compatible system that dont uses namespaces.

    lst bool:
        Lists objects in the given source path. Doesn't download files. Prints to stdout.

    delete bool:
        Deletes all objects that match the given key prefix. Will only delete objects if the 'source_path' is a s3 endpoint.

    to_stdout bool:
        Print either created objects in s3, created local files or deleted s3 objects to stdout.

    suppress bool:
        Suppresses all output to stdout or stderr.

    insecure bool:
        Do not validate TLS certificates as fallback when given or system certificates failed to validate.

    no_partial_paths bool:
        Does not autocomplete partial paths to full paths. F.e. partial path: 'docs/cod' and existing key in the bucket is: 'docs/coding/work/main.py' would not autocomplete to full path 'docs/coding'. So you have to provide a full path ('directory') like 'docs/coding' to get any results.

    certs list[str]:
        Path to certificate to use for the requests. If you need two different certificates because you're transfering files from one s3 bucket to another s3 bucket, separate their paths with whitespaces. You can use one certificate for both connections. Automatically enables secure connection over TLS. When no certificate is given, use system certificates instead to verify the connection. When connection could not be verified, uses http instead.

    Returns list of files or objects that were created.
    """

    if certs:
        certs = [Path(cert) if cert else None for cert in certs]

    return asyncio.run(_s3_syncer(
        source_path=source_path,
        destination_path=destination_path,
        access_key=access_key,
        secret_key=secret_key,
        lst=lst,
        delete=delete,
        to_stdout=to_stdout,
        suppress=suppress,
        insecure=insecure,
        no_partial_paths=no_partial_paths,
        certs=certs))

def s3_syncer_cli():
    def get_version():
        try:
            return version('s3-syncer')
        except:
            return None

    parser = ArgumentParser("A script for uploading and downloading objects from and to a s3 bucket. You can also copy objects from one s3 storage to another s3 storage (works with different providers f.e. Dell ECS and scality). Support for unix-like glob patterns for local files and prefix search on s3 keys.",)
    parser.add_argument("source_path", type=str, action="store", help=f"Path to the source object. For local files it can contain unix-like glob/wildcard patterns (Don't forget the quotes). Can be object in s3 or local file. S3 object path needs to have '{PATTERN}' form.")
    parser.add_argument("destination_path", type=str, nargs="?", default=".", help=f"Path to the destination object. Can be object in s3 or local file. S3 object path needs to have '{PATTERN}' form. '{{path-to-filename}}' is more like a prefix or filter to search for the keys. So it doesn't has to match the exact key or 'folder' in the bucket. '{{s3-namespace}}' is obsolete in s3 scality or any other s3 compatible system that dont uses namespaces.")
    parser.add_argument("-l", "--list", action="store_true", help="Lists objects in the given source path. Doesn't download files. Prints to stdout.")
    parser.add_argument("-a", "--access_key", action="append", required=True, help="Access key id for the s3 service. Can be the username. Alternatively use env var S3_ACCESS_KEY_ID. Seperate multiple access keys with another argument call.")
    parser.add_argument("-s", "--secret_key", action="append", required=True, help="Secret key for the s3 service. Alternatively use env var S3_SECRET_ACCESS_KEY. Seperate multiple secret keys with another argument call.")
    parser.add_argument("-d", "--delete", action="store_true", help="Deletes all objects that match the given key prefix. Will only delete objects if the 'source_path' is a s3 endpoint.")
    parser.add_argument(      "--to-stdout", action="store_true", dest="stdout", help="Print either created objects in s3, created local files or deleted s3 objects to stdout.")
    parser.add_argument("-c", "--cert", type=Path, action="append", help="Path to certificate to use for the requests. If you need two different certificates because you're transfering files from one s3 bucket to another s3 bucket, comma separate their paths. You can use one certificate for both connections. Automatically enables secure connection over TLS. When no certificate is given, use system certificates instead to verify the connection. When connection could not be verified, uses http instead.")
    parser.add_argument(      "--insecure", action="store_true", help="Do not validate TLS certificates as fallback when given or system certificates failed to validate.")
    parser.add_argument(      "--suppress", action="store_true", help="Suppresses all output to stdout or stderr.")
    parser.add_argument(      "--no-partial-paths", action="store_true", help="Does not autocomplete partial paths to full paths. F.e. partial path: 'docs/cod' and existing key in the bucket is: 'docs/coding/work/main.py' would not autocomplete to full path 'docs/coding'. So you have to provide a full path ('directory') like 'docs/coding' to get any results.")
    parser.add_argument(      "--version", action="version", version=f"s3-syncer {get_version()}", help="Prints the version of the installed package 's3-syncer'.")
    args = parser.parse_args()

    asyncio.run(_s3_syncer(
        source_path=args.source_path,
        destination_path=args.destination_path,
        access_key=args.access_key,
        secret_key=args.secret_key,
        lst=args.list,
        delete=args.delete,
        to_stdout=args.stdout,
        suppress=args.suppress,
        insecure=args.insecure,
        no_partial_paths=args.no_partial_paths,
        certs=args.cert))

if __name__ == "__main__":
    s3_syncer_cli()
