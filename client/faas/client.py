#  Copyright 2018 U.C. Berkeley RISE Lab
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

from anna.client import AnnaClient
import boto3
import cloudpickle as cp
from functions_pb2 import *
import numpy
from ..include.shared import *
import zmq

class FluentConnection():
    def __init__(self, func_addr, ip=None):
        self.service_addr = 'tcp://'+  func_addr + ':%d'
        self.context = zmq.Context(1)
        kvs_addr = self._connect()

        if ip:
            self.kvs_client = AnnaClient(kvs_addr, ip)
        else:
            self.kvs_client = AnnaClient(kvs_addr)

        self.create_sock = self.context.socket(zmq.REQ)
        self.create_sock.connect(self.service_addr % CREATE_PORT)

        self.call_sock = self.context.socket(zmq.REQ)
        self.call_sock.connect(self.service_addr % CALL_PORT)

        self.list_sock = self.context.socket(zmq.REQ)
        self.list_sock.connect(self.service_addr % LIST_PORT)

        self.rid = 0

    def _connect(self):
        sckt = self.context.socket(zmq.REQ)
        sckt.connect(self.service_addr % CONNECT_PORT)
        sckt.send_string('')

        return sckt.recv_string()

    def list(self, prefix=None):
        for fname in self._get_func_list(prefix):
            print(fname)

    def get(self, name):
        if name not in self._get_func_list():
            print("No function found with name '" + name + "'.")
            print("To view all functions, use the `list` method.")
            return None

        return FluentFunction(name, self, self.kvs_client)

    def _get_func_list(self, prefix=None):
        msg = prefix if prefix else ''
        self.list_sock.send_string(msg)

        flist = FunctionList()
        flist.ParseFromString(self.list_sock.recv())
        return flist

    def exec_func(self, name, args):
        call = FunctionCall()
        call.name = name
        call.request_id = self.rid

        for arg in args:
            argobj = call.args.add()
            serialize_val(arg, argobj)

        self.call_sock.send(call.SerializeToString())

        self.rid += 1
        return self.call_sock.recv_string()

    def register(self, function, name):
        func = Function()
        func.name = name
        func.body = function_ser.dump(function)

        self.create_sock.send(func.SerializeToString())

        resp = self.create_sock.recv_string()

        if 'Success' in resp:
            return FluentFunction(name, self, self.kvs_client)
        else:
            print('Unexpected error while registering function: \n\t%s.'
                    % (resp))
