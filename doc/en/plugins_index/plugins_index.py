"""
Script to generate the file `plugins_index.txt` with information about
pytest plugins taken directly from a live PyPI server.

This will evolve to include test compatibility (pythons and pytest versions)
information also.
"""
from __future__ import print_function
from collections import namedtuple
import datetime
from distutils.version import LooseVersion
import itertools
from optparse import OptionParser
import os
import sys
import pytest


def get_proxy(url):
    """
    wrapper function to obtain a xmlrpc proxy, taking in account import
    differences between python 2.X and 3.X

    :param url: url to bind the proxy to
    :return: a ServerProxy instance
    """
    if sys.version_info < (3, 0):
        from xmlrpclib import ServerProxy
    else:
        from xmlrpc.client import ServerProxy
    return ServerProxy(url)


def iter_plugins(client, search='pytest-'):
    """
    Returns an iterator of (name, version) from PyPI.
    
    :param client: ServerProxy
    :param search: package names to search for 
    """
    for plug_data in client.search({'name': search}):
        yield plug_data['name'], plug_data['version']


def get_latest_versions(plugins):
    """
    Returns an iterator of (name, version) from the given list of (name,
    version), but returning only the latest version of the package. Uses
    distutils.LooseVersion to ensure compatibility with PEP386.
    """
    plugins = [(name, LooseVersion(version)) for (name, version) in plugins]
    for name, grouped_plugins in itertools.groupby(plugins, key=lambda x: x[0]):
        name, loose_version = list(grouped_plugins)[-1]
        yield name, str(loose_version)


def obtain_plugins_table(plugins, client):
    """
    Returns information to populate a table of plugins, their versions,
    authors, etc.
    
    The returned information is a list of columns of `ColumnData`
    namedtuples(text, link). Link can be None if the text for that column
    should not be linked to anything.
    
    :param plugins: list of (name, version)
    :param client: ServerProxy
    """
    rows = []
    ColumnData = namedtuple('ColumnData', 'text link')
    headers = ['Name', 'Author', 'Downloads', 'Python 2.7', 'Python 3.3',
               'Summary']
    pytest_version = pytest.__version__
    print('*** pytest-{0} ***'.format(pytest_version))
    plugins = list(plugins)
    for index, (package_name, version) in enumerate(plugins):
        print(package_name, version, '...', end='')

        release_data = client.release_data(package_name, version)
        download_count = release_data['downloads']['last_month']
        url = '.. image:: {site}/status/{name}-{version}'
        image_url = url.format(
            site='http://pytest-plugs.herokuapp.com',
            name=package_name,
            version=version)
        image_url += '?py={py}&pytest={pytest}'
        row = (
            ColumnData(package_name + '-' + version,
                       release_data['release_url']),
            ColumnData(release_data['author'], release_data['author_email']),
            ColumnData(str(download_count), None),
            ColumnData(image_url.format(py='py27', pytest=pytest_version),
                       None),
            ColumnData(image_url.format(py='py33', pytest=pytest_version),
                       None),
            ColumnData(release_data['summary'], None),
        )
        assert len(row) == len(headers)
        rows.append(row)

        print('OK (%d%%)' % ((index + 1) * 100 / len(plugins)))

    return headers, rows


def generate_plugins_index_from_table(filename, headers, rows):
    """
    Generates a RST file with the table data given.
     
    :param filename: output filename
    :param headers: see `obtain_plugins_table`
    :param rows: see `obtain_plugins_table`
    """
    # creates a list of rows, each being a str containing appropriate column
    # text and link
    table_texts = []
    for row in rows:
        column_texts = []
        for i, col_data in enumerate(row):
            text = '`%s <%s>`_' % (
                col_data.text,
                col_data.link) if col_data.link else col_data.text
            column_texts.append(text)
        table_texts.append(column_texts)

    # compute max length of each column so we can build the rst table
    column_lengths = [len(x) for x in headers]
    for column_texts in table_texts:
        for i, row_text in enumerate(column_texts):
            column_lengths[i] = max(column_lengths[i], len(row_text) + 2)

    def get_row_limiter(char):
        return ' '.join(char * length for length in column_lengths)

    with open(filename, 'w') as f:
        # write welcome 
        print('.. _plugins_index:', file=f)
        print(file=f)
        print('List of Third-Party Plugins', file=f)
        print('===========================', file=f)
        print(file=f)

        # table 
        print(get_row_limiter('='), file=f)
        formatted_headers = [
            '{0:^{fill}}'.format(header, fill=column_lengths[i])
            for i, header in enumerate(headers)]
        print(*formatted_headers, file=f)
        print(get_row_limiter('='), file=f)

        for column_texts in table_texts:
            formatted_rows = [
                '{0:^{fill}}'.format(row_text, fill=column_lengths[i])
                for i, row_text in enumerate(column_texts)
            ]
            print(*formatted_rows, file=f)
        print(file=f)
        print(get_row_limiter('='), file=f)
        print(file=f)
        print('*(Downloads are given from last month only)*', file=f)
        print(file=f)
        print('*(Updated on %s)*' % _get_today_as_str(), file=f)


def _get_today_as_str():
    """
    internal. only exists so we can patch it in testing.
    """
    return datetime.date.today().strftime('%Y-%m-%d')


def generate_plugins_index(client, filename):
    """
    Generates an RST file with a table of the latest pytest plugins found in
    PyPI.
    
    :param client: ServerProxy
    :param filename: output filename
    """
    plugins = get_latest_versions(iter_plugins(client))
    headers, rows = obtain_plugins_table(plugins, client)
    generate_plugins_index_from_table(filename, headers, rows)


def main(argv):
    """
    Script entry point. Configures an option parser and calls the appropriate
    internal function.
    """
    filename = os.path.join(os.path.dirname(__file__), 'plugins_index.txt')
    url = 'http://pypi.python.org/pypi'

    parser = OptionParser(
        description='Generates a restructured document of pytest plugins from PyPI')
    parser.add_option('-f', '--filename', default=filename,
                      help='output filename [default: %default]')
    parser.add_option('-u', '--url', default=url,
                      help='url of PyPI server to obtain data from [default: %default]')
    (options, _) = parser.parse_args(argv[1:])

    client = get_proxy(options.url)
    generate_plugins_index(client, options.filename)

    print()
    print('%s Updated.' % options.filename)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
