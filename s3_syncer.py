import boto3
import boto3.session
import os
import sys
import tqdm
import glob
from functools import partial
from argparse import ArgumentParser
from pathlib import Path
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed

def die(msg: str):
    print(f"\u001b[31m{msg}\u001b[0m", file=sys.stderr)
    sys.exit(1)

@dataclass
class ObjectPath:
    type: str
    path: str
    bucket: str | None
    url: str | None

def executor_with_progressbar(
    func: partial,
    keys: list[str],
    upload: bool
) -> None:
    "Takes a partial function and a list of keys/files and executes the partial function + each element in the list asynchronously. Also prints a progress bar."

    failed_downloads = []

    with tqdm.tqdm(desc=f"{'Uploading' if upload else 'Downloading'} objects {'to' if upload else 'from'} S3 object storage", total=len(keys), ascii=True) as pbar:
        with ThreadPoolExecutor(max_workers=100) as executor:
            futures = {
                executor.submit(func, s3_file): s3_file for s3_file in keys
            }
            for future in as_completed(futures):
                if future.exception():
                    print(f"\u001b[31m{future.exception()}\u001b[0m")
                    failed_downloads.append(futures[future])
                pbar.update(1)
    
    if len(failed_downloads) > 0:
        print(f"The following file(s) could not be {'uploaded' if upload else 'downloaded'}:")
        for failed in failed_downloads:
            print(failed)

def get_next_dir(
    part_path: str,
    full_path: str,
    glob_pattern: bool = False
) -> str:
    """Return the next following directory from the part_path. Example: part_path: docs/cod , full_path example: docs/coding/work/main.py -> returns docs/coding
    if `glob_pattern` is true then return the longest common path of the initial glob/wildcard pattern and an actual found file.
    """

    if glob_pattern:
        return os.path.commonpath([part_path, full_path])
    
    part_path = part_path.removesuffix("/")

    return part_path + full_path.removeprefix(part_path).partition("/")[0]

def list_objects(
    s3_client,
    object_path: ObjectPath,
    local: bool = False
) -> list[str]:
    "Returns a list of s3 keys or local files, depending on the type of the 'object_path' object."

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
        try:
            for result in paginator.paginate(Bucket=object_path.bucket, Prefix=object_path.path):
                if result.get("KeyCount") == 0:
                    die(f"Could not find any keys/objects at the given s3 path \u001b[33m'{object_path.path}'\u001b[0m.")
                for object in result.get("Contents"):
                    keys.append(object.get("Key"))
        except Exception as e:
            die(f"Could not get list of objects in bucket '{object_path.bucket}'. Reason: \u001b[33m'{e}'\u001b[0m")

    if len(keys) == 0:
        die(f"Couldn't find any objects/files in the given source path \u001b[33m'{object_path.path}'\u001b[0m.")

    return keys

def upload_one_object(
    s3_client,
    bucket: str,
    source_path: str,
    s3_file: str,
    local_file: str
) -> None:
    "Upload a single file to a s3 bucket."

    # change source_path to the local file's parent dir if in general just a single file should be uploaded.
    if source_path == local_file:
        source_path = Path(local_file).parent.__str__()
    s3_file = os.path.join(s3_file, local_file.removeprefix(get_next_dir(source_path, local_file, glob_pattern=True) + "/"))

    s3_client.upload_file(
        Filename=local_file,
        Bucket=bucket,
        Key=s3_file
    )

def upload(
    s3_client,
    object_path_source: ObjectPath,
    object_path_dest: ObjectPath
) -> None:
    "Gets a list of objects and uploads them asynchronously."

    files = list_objects(s3_client, object_path_source, local=True)

    func = partial(upload_one_object, s3_client, object_path_dest.bucket, object_path_source.path, object_path_dest.path)

    executor_with_progressbar(func, files, upload=True)

def download_one_object(
    s3_client,
    object_path: ObjectPath,
    local_path: str,
    s3_file: str
) -> None:
    "Downloads a single file from a s3 bucket and creates local dirs recursively if necessary and writes file to desired destination path."

    # allow to set a new name for a single file if the user exactly matches the s3 key in the bucket
    if object_path.path != s3_file or os.path.realpath(Path(object_path.path).parent) == local_path:
        local_path = os.path.join(local_path, s3_file.removeprefix(get_next_dir(object_path.path, s3_file) + "/"))

    # create local dirs recursively if they dont exist
    if not Path(local_path).parent.exists():
        if local_path.count("/") != 0:
            os.makedirs(Path(local_path).parent.__str__(), exist_ok=True)

    s3_client.download_file(
        Bucket=object_path.bucket,
        Key=s3_file,
        Filename=local_path
    )

def download(
    s3_client,
    object_path_source: ObjectPath,
    object_path_dest: ObjectPath
) -> None:
    "Gets a list of objects and downloads them asynchronously."

    keys = list_objects(s3_client, object_path_source, local=False)
    
    func = partial(download_one_object, s3_client, object_path_source, object_path_dest.path)

    executor_with_progressbar(func, keys, upload=False)

def s3_object_path_parser(
    path: str
) -> ObjectPath:
    "Returns a parsed ObjectPath object that contains the path, type of the path and when its from type 's3', the bucket name and endpoint-url."
    
    if not path.startswith("s3://"):
        return ObjectPath("file", os.path.realpath(path), None, None)

    path = path.replace("s3://", "")

    file_path = path.partition("/")[2]
    url = path.partition("/")[0]
    bucket = url.partition(".")[0]

    return ObjectPath("s3", file_path, bucket, url)

def main():
    parser = ArgumentParser("A script for uploading and downloading objects from a s3 bucket. Support for unix-like glob patterns for local files and prefix search on s3 keys.", )
    parser.add_argument("source_path", type=str, action="store", help="Path to the source object. For local files it can contain unix-like glob/wildcard patterns (Don't forget the quotes). Can be object in s3 or local file. S3 object path needs to have 's3://{s3-bucket}.{s3-namespace}.{s3-host}:{s3-port}/{path-to-filename}' form.")
    parser.add_argument("destination_path", type=str, nargs="?", default=".", help="Path to the destination object. Can be object in s3 or local file. S3 object path needs to have 's3://{s3-bucket}.{s3-namespace}.{s3-host}:{s3-port}/{path-to-filename}' form. '{path-to-filename}' is more like a prefix or filter to search for the keys. So it doesn't has to match the exact key or 'folder' in the bucket.")
    parser.add_argument("-l", "--list", action="store_true", help="Lists objects in the given source path. Doesn't download files.")
    parser.add_argument("-c", "--cert", type=Path, help="Path to certificate to use for the requests.")
    parser.add_argument("-a", "--access_key", type=str, help="Access key id for the s3 service. Can be the username. Alternatively use env var S3_ACCESS_KEY_ID.")
    parser.add_argument("-s", "--secret_key", type=str, help="Secret key for the s3 service. Alternatively use env var S3_SECRET_ACCESS_KEY.")
    args = parser.parse_args()

    object_source_path = s3_object_path_parser(args.source_path)
    object_dest_path = s3_object_path_parser(args.destination_path)

    url = object_source_path.url if object_source_path.type == "s3" else object_dest_path.url
    if not url:
        die("Could not parse a url out of source or destination path")
    url = url.partition(".")[2]

    if args.cert and not args.cert.exists():
        die("Given certificate path does not exist.")

    s3_client = boto3.session.Session(
            aws_access_key_id=os.getenv("S3_ACCESS_KEY_ID", args.access_key), 
            aws_secret_access_key=os.getenv("S3_SECRET_ACCESS_KEY", args.secret_key)
        ).client(
            "s3",
            verify=str(args.cert) if args.cert else False,
            use_ssl=args.cert is not None,
            endpoint_url=f"{'https' if args.cert else 'http'}://{url}",
        )
    
    if args.list:
        keys = list_objects(s3_client, object_source_path, local=object_source_path.type == "file")
        print(f"Found {len(keys)} object(s) in the source path:\n")
        for key in keys:
            print(key)
        return

    if object_source_path.type == "file":
        upload(s3_client, object_source_path, object_dest_path)
    else:
        download(s3_client, object_source_path, object_dest_path)

if __name__ == "__main__":
    main()
