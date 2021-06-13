import asyncio
import logging
from grpc import aio

from .gen.proto import mc_management_pb2_grpc

log = logging.getLogger('rpc')


class MCManagementServicer(mc_management_pb2_grpc.MCManagementServicer):
    def __init__(self):
        super().__init__()
        # TODO: this

    def GetPlayerCount(self, request, context):
        raise NotImplementedError('Method not implemented!')

    def SubscribePlayerCount(self, request, context):
        raise NotImplementedError('Method not implemented!')

    def UpdateWhitelist(self, request, context):
        raise NotImplementedError('Method not implemented!')

    def SubscribePlayerEvent(self, request, context):
        raise NotImplementedError('Method not implemented!')

    def GetResourceConsumption(self, request, context):
        raise NotImplementedError('Method not implemented!')

    def SubscribeResourceConsumptionEvent(self, request, context):
        raise NotImplementedError('Method not implemented!')

    def SubscribeHeartbeat(self, request, context):
        raise NotImplementedError('Method not implemented!')
