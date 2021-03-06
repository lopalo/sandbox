import argparse
from sulaco.tests.tools import BlockingClient, TimeoutError

from sulaco.utils import get_pairs


def main(options):
    wait = options.wait
    client = BlockingClient()
    client.connect(host=options.host, port=options.port, seconds=wait)
    while True:
        path = input('Path (leave empty to wait incoming message): ').strip()
        if not path:
            try:
                print(client.recv(seconds=wait))
            except TimeoutError:
                pass
        else:
            string = input('Key-value arguments (key val key val ...): ')
            kwargs = dict(get_pairs(string.split()))
            client.send(dict(path=path, kwargs=kwargs), seconds=wait)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='')
    parser.add_argument('-p', '--port', type=int, required=True)
    parser.add_argument('-w', '--wait', type=int, default=1,
                        help='time in seconds to waiting on '
                        'input and output messages')
    options = parser.parse_args()
    main(options)
