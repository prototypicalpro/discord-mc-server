PROTOC=python3 -m grpc_tools.protoc
PROTOC_OUT=./src/gen/proto

proto: proto/proto/mc-management.proto
	$(PROTOC) -Iproto/proto/ --python_out=$(PROTOC_OUT) --grpc_python_out=$(PROTOC_OUT) proto/proto/mc-management.proto
