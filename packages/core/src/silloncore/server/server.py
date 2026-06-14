import traceback
import socket
import selectors
import types
import struct
import logging
import time

from silloncommon.commands import (
    AddMetaDataCmd,
    AddTagCmd,
    AddNoteCmd,
    LogParamCmd,
    LogResultCmd,
    LogFigureCmd,
    DumpCmd,
    ShutDownCmd,
)

from .visitor import CommandVisitor
from silloncommon.rpcHandler import RPCHandler
from silloncommon.database import next_available_name
from silloncore.simulation import Simulations_object
from silloncore.envhandler import ProjectEnvironmentHandler
from silloncommon.socket_path import get_socket_path, get_pidfile_path

# Set the config for the log
logging.basicConfig(
    level=logging.DEBUG,  # Set to INFO in production to hide DEBUG messages
    format="%(asctime)s - %(levelname)-8s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

IDLE_TIMEOUT = 300


class Server:
    def __init__(self, project_path: str):

        self.project_path = project_path
        socket_path = get_socket_path(project_path)
        socket_path.parent.mkdir(parents=True, exist_ok=True)

        # Remove stale socket file if it exists (crash leftover)
        if socket_path.exists():
            socket_path.unlink()

        # Information about the server connection
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.bind(str(socket_path))

        self.a_Is_Active = True
        self.command_visitor = CommandVisitor()
        self.rpchandler = RPCHandler()
        self.logger = logging.getLogger(__name__)

        self.sel = selectors.DefaultSelector()
        self.sock.setsockopt(
            socket.SOL_SOCKET, socket.SO_REUSEADDR, 1
        )  # Tell the server to imediatly release the IP when the server is dead to prevent "IP already in use error"

        # The state of the server
        # IMPORTANT TO KEEP IT SO THE USER CAN CONTROL IT
        self.is_active = True
        self.command_registry = {
            "log_result": LogResultCmd,
            "log_figure": LogFigureCmd,
            "log_param": LogParamCmd,
            "add_metadata": AddMetaDataCmd,
            "add_note": AddNoteCmd,
            "add_tag": AddTagCmd,
            "dump": DumpCmd,
            "shutdown": ShutDownCmd,
        }

        self.simulations = Simulations_object
        self.RunEnvhandlers = {}
        # Mettre les handler en ContextVar ?

    def run_Server(self):
        self.logger.info("Server Starting...")
        self.sock.listen()
        self.sock.setblocking(False)
        self.sel.register(self.sock, selectors.EVENT_READ, self.accept_wrapper)
        self.logger.info("Server registered successfully.")

        self.had_connection = False          # don't idle-timeout before first client
        last_activity = time.monotonic()

        try:
            while self.is_active:
                events = self.sel.select(timeout=1.0)   # short timeout for accurate idle tracking

                if events:
                    last_activity = time.monotonic()
                elif self.had_connection and len(self.simulations.sim_dict) == 0:
                    # Only count idle time after we've served at least one client
                    if time.monotonic() - last_activity >= IDLE_TIMEOUT:
                        self.logger.info("Idle timeout - shutting down.")
                        self.is_active = False

                for key, mask in events:
                    callback = key.data
                    callback(key.fileobj, mask)
        except Exception as e:
            self.logger.error("Error in the event loop: %s", e)
            self.logger.debug("Traceback:\n%s", traceback.format_exc())
        finally:
            self.sel.close()
            self._cleanup()

    def accept_wrapper(self, sock, mask):
        # Accepting new connection
        conn, addr = sock.accept()
        self.had_connection = True

        # Namespace settup
        conn.setblocking(False)
        data = types.SimpleNamespace(addr=addr, inb=b"", outb=b"")

        # Types of events to acknowledge when receiving data
        events = selectors.EVENT_READ | selectors.EVENT_WRITE

        # Wrap service_connection as a closure bound to this connection's data
        def handle(sock, mask):
            self.service_connection(sock, mask, data)

        data.handle = handle
        # Registering the connection in the selector
        self.sel.register(conn, events, handle)

    def service_connection(self, sock, mask, data):
        """Entry point for all I/O events on a client connection. Dispatches to
        read or write handler based on the selector mask."""
        if mask & selectors.EVENT_READ:
            self._handle_read(sock, data)
        if mask & selectors.EVENT_WRITE:
            self._handle_write(sock, data)

    def _handle_read(self, sock, data):
        """Reads incoming bytes into the connection buffer and extracts complete
        length-prefixed messages. Closes the connection if the client disconnects."""
        try:
            chunk = sock.recv(65536)
        except BlockingIOError:
            chunk = b""

        if chunk:
            data.inb += chunk
            while True:
                if len(data.inb) < 4:
                    break
                length = struct.unpack(">I", data.inb[:4])[0]
                if len(data.inb) < 4 + length:
                    break
                raw = data.inb[4 : 4 + length]
                data.inb = data.inb[4 + length :]
                payload = self._process_message(raw, data)
                data.outb += struct.pack(">I", len(payload)) + payload
                self.sel.modify(
                    sock, selectors.EVENT_READ | selectors.EVENT_WRITE, data.handle
                )
        else:
            # client disconnected - find any run registered on this socket and mark it as crashed before Closing
            self._handle_client_disconnect(sock, data)
            self.sel.unregister(sock)
            sock.close()

    def _process_message(self, raw: bytes, data) -> bytes:
        """Decodes a raw message, dispatches it, and returns a framed response.
        On any error, returns a JSON-RPC error response instead of raising."""
        request = None
        try:
            request = self.rpchandler.decode_request(raw.decode("utf-8"))
            result = self._dispatch(request, data)
            return self.rpchandler.encode_response(result, request["id"]).encode(
                "utf-8"
            )
        except Exception as e:
            self.logger.exception("Error handling request")   # <- full traceback in the log
            req_id = request["id"] if request else 0
            return self.rpchandler.encode_response({"error": str(e)}, req_id).encode(
                "utf-8"
            )

    def _dispatch(self, request: dict, data) -> str:
        """Routes a decoded JSON-RPC request to the appropriate command handler
        and returns the result. Raises on unknown commands."""
        command_type = request["method"]
        args = self.rpchandler.decode_params(request["params"])

        if command_type == "REGISTER":
            self.logger.info("Registering new simulation: %s", args)
            if not hasattr(self, "projEnvHandlers"):
                self.projEnvHandlers = ProjectEnvironmentHandler(args["project_path"])
            # Ensure the run name is unique: increment on collision with a
            # finished run (DB) or an in-flight run (registered, not yet dumped).
            if args.get("run_name"):
                in_flight = [sim.run_name for sim in self.simulations.sim_dict.values()]
                args["run_name"] = next_available_name(
                    self.projEnvHandlers.get_engine(), args["run_name"], in_flight
                )
            self.simulations.add_sim(**args)
            data.run_id = args["run_id"]
            self.logger.info("Simulation and env handler created")
            return {"ack": True, "run_name": args["run_name"]}

        if command_type not in self.command_registry:
            raise Exception(f"UnknownCommand: {command_type}")

        self.logger.info("Command: %s", command_type)
        CommandClass = self.command_registry[command_type]
        command = CommandClass(args["name"], args["value"])
        result = command.accept(self.command_visitor, args["run_id"])

        if command_type == "dump":
            self.projEnvHandlers.commit_run(
                self.simulations.sim_dict[args["run_id"]]
            )
            self.simulations.rm_sim(args["run_id"])
        elif command_type == "shutdown":
            self.sel.unregister(self.sock)
            self.sock.close()
            self.is_active = False

        return result

    def _handle_write(self, sock, data):
        """Flushes the output buffer to the socket. Switches the connection back
        to read-only mode once the buffer is fully drained."""
        if data.outb:
            sent = sock.send(data.outb)
            data.outb = data.outb[sent:]
            if not data.outb:
                self.sel.modify(sock, selectors.EVENT_READ, data.handle)

    def _handle_client_disconnect(self, sock, data):
        """mark any registered run as CRASHED when its client disconnects without sending a dump command."""
        run_id = getattr(data, "run_id", None)
        if run_id is None:
            return # either never registered or cleanly dumped
        if run_id not in self.simulations.sim_dict:
            return

        self.logger.warning("Client disconnected without dump -marking run %s as CRASHED", run_id)
        try:
            sim = self.simulations.sim_dict[run_id]
            sim.status = "CRASHED"
            self.projEnvHandlers.commit_run(sim)
            self.simulations.rm_sim(run_id)
        except Exception as e:
            self.logger.error("Failed to commit crashed run %s: %s", run_id, e)

    def _cleanup(self):
        socket_path = get_socket_path(self.project_path)
        pid_file = get_pidfile_path(self.project_path)
        socket_path.unlink(missing_ok=True)
        pid_file.unlink(missing_ok=True)
