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
import random
import struct
import subprocess
import sys
import time


# Robinhood credentials
username = ''
password = ''
# OTP secret
secret = ''
# Path to magictrade basedir
install_path = ''


def get_hotp_token(intervals_no):
    key = base64.b32decode(secret, True)
    msg = struct.pack(">Q", intervals_no)
    h = hmac.new(key, msg, hashlib.sha1).digest()
    o = h[19] & 15
    h = (struct.unpack(">I", h[o:o+4])[0] & 0x7fffffff) % 1000000
    return str(h)


def get_totp_token():
    return get_hotp_token(intervals_no=int(time.time())//30)


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'random':
        t = random.randint(0, 23340)
        print("Sleeping {} seconds before reauth.".format(t))
        time.sleep(t)
    token = get_totp_token()
    subprocess.run([install_path + '/venv/bin/magictrade-daemon', '-x', 'papermoney', '-k',
                    install_path + 'magictrade/.oauth2-token'], env={'username': username,
                                                                     'password': password,
                                                                     'mfa_code': token})
    subprocess.run(['systemctl', 'restart', 'magictrade'])
    with open("/var/log/authenticator.log", "a") as f:
        f.write("[{}] Authenticated\n".format(datetime.datetime.now().isoformat()))
