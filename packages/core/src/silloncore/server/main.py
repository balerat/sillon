import sys


from .server import Server

# Defining main function
def main():
    if len(sys.argv) < 2:
        print("Usage: sillon-server-daemon <project_path>")
        sys.exit(1)

    server = Server(project_path=sys.argv[1])
    server.run_Server()


if __name__ == "__main__":
    main()
