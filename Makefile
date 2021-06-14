PROTOC_OUT=./discord_mc_server/gen/proto

proto: proto/proto/mc-management.proto
	@python3 -m grpc_tools.protoc -Iproto/proto/ --python_out=$(PROTOC_OUT) --grpc_python_out=$(PROTOC_OUT) proto/proto/mc-management.proto
	@sed -i -E 's/^import.*_pb2/from . \0/' ./$(PROTOC_OUT)/*.py
