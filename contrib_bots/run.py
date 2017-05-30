from __future__ import print_function

import importlib
import logging
import optparse
import os
import sys

our_dir = os.path.dirname(os.path.abspath(__file__))

# For dev setups, we can find the API in the repo itself.
if os.path.exists(os.path.join(our_dir, '../api/zulip')):
    sys.path.append('../api')

from zulip import Client

class RestrictedClient(object):
    def __init__(self, client):
        # Only expose a subset of our Client's functionality
        self.send_message = client.send_message

def get_lib_module(lib_fn):
    lib_fn = os.path.abspath(lib_fn)
    if os.path.dirname(lib_fn) != os.path.join(our_dir, 'lib'):
        print('Sorry, we will only import code from contrib_bots/lib.')
        sys.exit(1)

    if not lib_fn.endswith('.py'):
        print('Please use a .py extension for library files.')
        sys.exit(1)

