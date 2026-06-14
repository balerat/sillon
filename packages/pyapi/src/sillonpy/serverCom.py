import json
import socket

from silloncommon.rpcHandler import RPCHandler
from silloncommon.commands import ShutDownCmd, DumpCmd
from silloncommon.framing import send_msg, recv_msg
from silloncommon.socket_path import get_socket_path
from sillonpy.daemon import ensure_daemon


class ServerCom:
    def __init__(
        self, uuid, run_name, project_name, platform, organisation, author, project_path
    ):

        self.uuid = uuid
        self.command_id = (
            0  # The ID of the current command (increments by 1 every command sent)
        )
        self.rpc_handler = RPCHandler()
        self.run_name = run_name
        self.project_name = project_name
        self.platform = platform
        self.hostname = socket.gethostname()
        self.organisation = organisation
        self.author = author
        self.project_path = project_path
        # Information to connect to the server and communicate with it

    def connect_server(self):
        # Connects to the server
        ensure_daemon(self.project_path)
        socket_path = get_socket_path(self.project_path)
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(str(socket_path))

        # Register the run into the server
        register_msg = json.dumps(
            {
                "jsonrpc": self.rpc_handler.JSONRPC_VERSION,
                "method": "REGISTER",
                "params": json.dumps(
                    {
                        "run_id": self.uuid,
                        "run_name": self.run_name,
                        "project_name": self.project_name,
                        "platform": self.platform,
                        "hostname": self.hostname,
                        "organisation": self.organisation,
                        "author": self.author,
                        "project_path": str(self.project_path),
                    }
                ),
                "id": 0,
            }
        )
        send_msg(self.sock, register_msg.encode("utf-8"))

        # Awaiting for a response from the server
        reply = recv_msg(self.sock) 

        # Analysing the decoded response. The server replies either with the
        # legacy "ACK" string or a dict {"ack": True, "run_name": <name>} when
        # it has resolved the final (possibly incremented) run name.
        decoded = self.rpc_handler.decode_response(reply.decode("utf-8"))
        result = decoded["result"]
        if isinstance(result, dict):
            if not result.get("ack"):
                raise Exception("Could not register run to the server")
            if result.get("run_name"):
                self.run_name = result["run_name"]
        elif result != "ACK":
            raise Exception("Could not register run to the server")
        self.command_id += 1  # Increment ID

    def dump_run(self):
        """
        This function will tell the server to dump the content of the run to the database.
        """
        command = DumpCmd()
        self.execute_command(command)
        # We then close the connection to the server properly
        self.sock.close()

    def shutdown_server(self):
        command = ShutDownCmd()
        self.execute_command(command)

        # Server should be down, closing connection
        self.sock.close()

    def execute_command(self, p_Command):
        # Connects to the server if not already done
        if not hasattr(self, "sock"):
            self.connect_server()

        # Encode the requested command and sends it to the server
        encoded = self.rpc_handler.encode_request(p_Command, self.command_id, self.uuid)
        send_msg(self.sock , encoded.encode("utf-8"))


        # Awaiting for a response from the server
        reply = recv_msg(self.sock)

        # Return the decoded response
        try:
            decoded = self.rpc_handler.decode_response(reply.decode("utf-8"))
            self.command_id += 1

            return decoded["result"]
        except Exception as e:
            print(f"[SILLONPY] Failure to excute command: {e}")
            return None
