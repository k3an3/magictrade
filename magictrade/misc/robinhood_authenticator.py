#!/usr/bin/env python3
"""
robinhood_authenticator.py
~~~~~~~~~~~~~~~~~~~~~~~~~~

chown to root, chmod to 700 so it's kept safe.
"""
import base64
import datetime
import hashlib
import hmac
import os
import random
import struct
import subprocess
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

import time


def get_hotp_token(secret, intervals_no):
    key = base64.b32decode(secret, True)
    msg = struct.pack(">Q", intervals_no)
    h = hmac.new(key, msg, hashlib.sha1).digest()
    o = h[19] & 15
    h = (struct.unpack(">I", h[o:o + 4])[0] & 0x7fffffff) % 1000000
    return str(h)


def get_totp_token(secret):
    return get_hotp_token(secret, intervals_no=int(time.time()) // 30)


def main():
    parser = ArgumentParser(description="Robinhood 2FA integration for magictrade.",
                            formatter_class=ArgumentDefaultsHelpFormatter)
    parser.add_argument('--random', action='store_true', help="Wait a random amount of time before authenticating.")
    parser.add_argument('--logfile', default='/var/log/authenticator.log', help='File to log script output.')
    parser.add_argument('--path', required=True, help='Base path to magictrade, containing venv directory.')
    args = parser.parse_args()

    username = os.environ.get('USERNAME')
    password = os.environ.get('PASSWORD')
    otp_secret = os.environ.get('OTP_SECRET')

    if not (username or password or otp_secret):
        raise SystemExit("ERROR! Provide USERNAME, PASSWORD, and OTP_SECRET environment variables.")
    if args.random:
        t = random.randint(0, 23340)
        print("Sleeping {} seconds before reauth.".format(t))
        time.sleep(t)

    token = get_totp_token(otp_secret)
    subprocess.run([args.path + '/venv/bin/magictrade-daemon', '-x', 'papermoney', '-k',
                    args.path + 'magictrade/.oauth2-token'], env={'username': username,
                                                                  'password': password,
                                                                  'mfa_code': token})
    subprocess.run(['systemctl', 'restart', 'magictrade'])
    with open(args.logfile, "a") as f:
        f.write("[{}] Authenticated\n".format(datetime.datetime.now().isoformat()))


if __name__ == '__main__':
    main()
