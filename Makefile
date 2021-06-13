PROTOC=python3 -m grpc_tools.protoc


proto: proto/proto/mc-management.proto
	$(PROTOC) -Iproto/proto/ --python_out=. --grpc_python_out=. proto/proto/mc-management.proto