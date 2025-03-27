#! /usr/bin/env python
#
# Process a CSV file with a list of authors into a LaTeX author list
#
# The data source is expected to be made of 3 text files:
#    - authors.csv: the list of authors with 4 columns named "Firstnames", "Lastname", "Affiliation", "ORCID"
#
# These 3 files are typically built from the Google Docs https://docs.google.com/spreadsheets/d/1SFcJkI0bBoGs5av1o80apeMCXYWd8P-8PEbEJ-odlpI/edit?gid=0#gid=0
#
# Note: this script requires Python >= 3.9
#
# Initial version written by Graeme Stewart (graeme.andrew.stewart@cern.ch) and Michel Jouvin (jouvin@lal.in2p3.fr) for the HSF CWP in 2017
# Modified by the same authors for the HSF EPPSU document in 2025

import sys
PYTHON_MIN = (3, 9)
major, minor, _, _, _ = sys.version_info
if (major, minor) < PYTHON_MIN:
    python_min_str = '.'.join(str(x) for x in PYTHON_MIN)
    # Keep old formatter syntax to be sure it works with old version of Python
    print ("This script requires Python %s or later" % python_min_str)
    sys.exit(2)

import re
import argparse
import csv

# Define some constants related to application exit status
EXIT_STATUS_SUCCESS = 0
EXIT_STATUS_OPTION_ERROR = 3
EXIT_STATUS_FAILURE = 5

# Default input files
AUTHOR_FILE_DEFAULT = "authors.csv"
ARXIV_AUTHOR_FILE_DEFAULT = "hep-eppsu-software-authors.arxiv"
LATEX_AUTHOR_FILE_DEFAULT = "hep-eppsu-software-authors.tex"
ARXIV_AUTHORS_PREFIX_DEFAULT= "HEP Software Foundation: "

# Miscellaneous constants
AFFILIATION_USE_LETTERS = True

class Author():
    """
    Class representing authors, their affiliations and ORCID
    """
    def __init__(self, name:str, affiliation_id:str=None, orcid:str=None) -> None:
        self.name = name
        self.affiliation_id = affiliation_id
        if orcid:
            self.orcid = orcid
        else:
            self.orcid = None


class AffiliationList():
    def __init__(self, index_letter:bool):
        """
        Initialise the affiliation list

        :param index_letter: if True, use a letter for the affiliation index else a number
        """
        self._list = list()
        self._index_letter = index_letter

    def add(self, affiliation:str):
        """
        Append an affiliation to the list and returns its ID

        :param affiliation: affiliation string
        """
        self._list.append(affiliation)
        return self.get_id(affiliation)


    def get_id(self, affiliation:str):
        """
        Return the ID to use as an index for a particular affiliation, based on
        its index in the list. The index can be letter-based or digit-based.

        :param affiliation: affiliation string
        :return: index to use to refer to this affiliation in the author list
        """
        try:
            affiliation_index = self._list.index(affiliation)
        except ValueError:
            return None

        if self._index_letter:
            high_order = affiliation_index // 26
            id = ''
            if high_order > 0:
                id = chr(ord('a') + high_order - 1)
            id += chr(ord('a') + (affiliation_index % 26))
        else:
            id = affiliation_index + 1

        return id


def firstnames_to_initials(firstnames:str) -> str:
    """
    Build a list of initials (as a string) from a string containing
    one or more space-separated names

    :param firsnames: string containng space-separated names
    :return: string containing initials
    """

    initials = ''
    for firstname in re.split('\s', firstnames):
        initials += f'{firstname.capitalize()[0]}.'
    return initials.strip()

def latex_escape(string):
    """
    Function to escape latex reserved characters
    :param string: the string containing the characters to escape
    :return: the escaped string
    """

    CHARS_TO_ESCAPE_PATTERN = re.compile(r'(?<!\\)(?P<char>[&%\$#_{}])')
    SPECIAL_LATEX_CHARS = {'~':'$\\\\textasciitilde$',
                           '^':'$\\\\textasciicircum$'}
    # Do not attempt to escape \ as it may have been added as an escape character
    # and is unlikely to be present in an affiliation or footnote...
    # If it is present, if will have to be escaped manually
    #                       '\\':'$\\\\textbackslash$'}
    # Escape all reserved characters that can be escaped
    string = CHARS_TO_ESCAPE_PATTERN.sub('\\\\\g<char>', string)
    # Then replace special chars
    for special_char, repl in SPECIAL_LATEX_CHARS.items():
       string = re.sub(re.escape(special_char), repl, string)
    return string


def main():

    try:
        parser = argparse.ArgumentParser()
        parser.add_argument('--arxiv-output', dest='arxiv_output_file', default=ARXIV_AUTHOR_FILE_DEFAULT,
                            help='Output Arxiv author file (D: {})'.format(ARXIV_AUTHOR_FILE_DEFAULT))
        parser.add_argument('--arxiv-authors-prefix', dest='arxiv_authors_prefix', default=ARXIV_AUTHORS_PREFIX_DEFAULT,
                            help=f'Prefix for Arxiv authors list: {ARXIV_AUTHORS_PREFIX_DEFAULT}')
        parser.add_argument('--authors-csv', dest='authors', default=AUTHOR_FILE_DEFAULT,
                            help='CSV file containining author list (D: {})'.format(AUTHOR_FILE_DEFAULT))
        parser.add_argument('--more-authors', action='store_true', default=False, help='Add a last entry mentioning more authors are coming')
        parser.add_argument('--output', dest='output_file', default=LATEX_AUTHOR_FILE_DEFAULT,
                            help='Output Latex file (D: {})'.format(LATEX_AUTHOR_FILE_DEFAULT))
        parser.add_argument('--use-initials', action='store_true', default=False, help='Use initials in author first names')
        parser.affil_index = parser.add_mutually_exclusive_group()
        parser.affil_index.add_argument('--affiliation-letters', action='store_true', default=AFFILIATION_USE_LETTERS, help='Use letters are affilition index')
        parser.affil_index.add_argument('--affiliation-numbers', action='store_true', default=not AFFILIATION_USE_LETTERS, help='Use numbers are affilition index')
        options = parser.parse_args()
    except Exception as e:
        parser.invalid_option_value('Parsing error: {}'.format(e.msg))
        return EXIT_STATUS_OPTION_ERROR


    author_list = []
    affiliation_list = AffiliationList(not options.affiliation_numbers)

    # Open and process the authors file sorted by lastname
    # Reuse already existing affiliations when shared by several authors
    with open(options.authors, encoding='utf-8') as author_fh:
        rows = csv.DictReader(author_fh, delimiter=',')
        for author in sorted(rows, key=lambda x: x['Lastname']):
            affiliation_id = affiliation_list.get_id(author['Affiliation'])
            if affiliation_id is None:
                affiliation_id = affiliation_list.add(author['Affiliation'])
            if options.use_initials:
                name = f'{firstnames_to_initials(author["Firstnames"])} {author["Lastname"]}'
            else:
                name = f'{author["Firstnames"]} {author["Lastname"]}'
            author_list.append(Author(name, affiliation_id, author['ORCID']))

    # Optionally add a dummy entry saying that more authors and affiliations are expected
    if options.more_authors:
        affiliation_list.add('Many more to come...')
        author_list.append(Author('And many more to come...', affiliation_list.get_id('Many more to come...')))

    # Write a Latex file representing authors and their affiliations
    with open(options.output_file, 'w', encoding='utf-8') as latex_fh:
        for author in author_list:
            if author.orcid is None:
                orcid_link = ''
            else:
                orcid_link = f'\orcidlink{{{author.orcid}}}'
            name = re.sub('\s', '~', author.name)
            latex_fh.write(f'\\author[{author.affiliation_id}]{{{name}{orcid_link}}}\n')

        latex_fh.write('\n')

        for affiliation in affiliation_list._list:
            latex_fh.write(f"\\affiliation[{affiliation_list.get_id(affiliation)}]{{{affiliation}}}\n")

    # Write out the author list to copy into the arXiv author file
    with open(options.arxiv_output_file, "w", encoding="utf-8") as arxivoutput:
        print(f"{ARXIV_AUTHORS_PREFIX_DEFAULT}{', '.join([author.name for author in author_list])}",
              file=arxivoutput)


if __name__ == '__main__':
    main()

