import webbrowser

from textual_serve.server import Server

if __name__ == "__main__":
    server = Server("python -m visualiser")
    webbrowser.open("http://localhost:8000")
    server.serve()
