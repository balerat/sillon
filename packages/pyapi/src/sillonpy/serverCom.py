import json
import socket
from pathlib import Path

from silloncommon.rpcHandler import RPCHandler
from silloncommon.commands import ShutDownCmd, DumpCmd
from silloncommon.framing import send_msg, recv_msg
from silloncommon import transport
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
        self.sock = transport.connect(self.project_path)
        if self.sock is None:
            raise ConnectionError(
                f"Could not connect to the sillon daemon for {self.project_path}"
            )

        # Register the run into the server. The token proves we can read
        # .sillon/daemon.token, which is what authorises us on the loopback-TCP
        # transport (see silloncommon.transport).
        register_msg = json.dumps(
            {
                "jsonrpc": self.rpc_handler.JSONRPC_VERSION,
                "method": "REGISTER",
                "params": json.dumps(
                    {
                        "auth_token": transport.read_token(self.project_path),
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
                reason = result.get("error", "no acknowledgement")
                raise Exception(f"Could not register run to the server: {reason}")
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
        try:
            self.execute_command(command)
        finally:
            # Close even when the dump failed, so a raised error does not leave
            # the socket open and the daemon holding a half-finished connection.
            self.sock.close()

    def shutdown_server(self):
        command = ShutDownCmd()
        try:
            self.execute_command(command)
        finally:
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

        # Advance the id for every request that actually went out, whatever the
        # answer turns out to be. Skipping it on failure desynchronises our ids
        # from the ones the server is replying to.
        self.command_id += 1

        if reply is None:
            raise ConnectionError(
                "The sillon daemon closed the connection without answering "
                f"'{p_Command.method}'. See "
                f"{Path(self.project_path) / '.sillon' / 'daemon.log'}"
            )

        # decode_response raises on a top-level "error", so a server-side failure
        # reaches the caller instead of being printed and discarded. Letting it
        # propagate is the point: a swallowed error here means the run commits
        # without the data it claims to have.
        decoded = self.rpc_handler.decode_response(reply.decode("utf-8"))
        return decoded["result"]
