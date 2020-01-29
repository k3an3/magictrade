#!/usr/bin/env python3
import redis
from argparse import ArgumentParser

storage = redis.StrictRedis(decode_responses=True)


def main(old: str, new: str):
    for key in storage.scan_iter(f"{old}*"):
        new_name = key.replace(old, new)
        storage.renamenx(key, new_name)
        print("replace", key, "with", new_name)

    for key in storage.scan_iter(f"{old}*"):
        if storage.type(key) == 'list':
            new_name = key.replace(old, new)
            print("replace", key, "with", new_name)
            for item in storage.lrange(key, 0, -1):
                storage.rpush(new_name, item)
        storage.delete(key)
        print("delete", key)


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('source_queue', help='Queue name to move from.')
    parser.add_argument('dest_queue', help='Queue name to move to.')
    args = parser.parse_args()
    main(args.source_queue, args.dest_queue)
