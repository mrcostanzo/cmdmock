#!/usr/bin/env python
# -*- coding: utf-8 -*-
# M Costanzo

""" cmdmock is a simple utility to create a mock version of a command with a specific
argument string (or no arguments). It runs the command, takes the output and hard-codes that
output as a canned response which can then be called and regurgitated. It then tries to set
the file to be executable so a module under test or development can call it transparently
"""

__version__ = '0.04'

#TODO add time to auto-generated module docstring
#TODO consider supporting options before the command to change behavior
#TODO optionally enforce exact argument string or return an error
#TODO optionally build up the vocabulary of the mocker by running multiple arguments
# and appending their output
#TODO optionally compress output into a blob in case it is catting a big file for example
#TODO support verbose output
#TODO explicitly add to path for this shell instance?

import sys
import os
import subprocess
import socket
import time
import logging as log
import optparse
import hashlib


def handle_args():
    """Parse out arguments"""
    parser = optparse.OptionParser()
    parser.add_option('-i', '--interactive', action='store_true', \
                      help='Interactively enter a series of invocations')
    parser.add_option('-f', '--file', dest='training_file', \
                      help='Optionally specify a training file with line-seperated invocations')
    #parser.add_option('-v', '--verbose', action='store_true', dest='verbose', default=False,
    #                  help='Print informative messages')
    #parser.add_option('-d', '--debug', action='store_true', dest='debug', default=False,
    #                  help='Print all messages including debug')
    (options, args) = parser.parse_args()
    return (options, args)


class InvocationSet(object):
    """ Container to hold, add, and serialize invocations and responses for building a vocabulary.
    Inputs are stored as a list of arguments, the same way argv does it, they are also hashed using
    md5 for searching and indexing. Command responses are stored as big strings along with their
    hashes for easier indexing and comparison. """

    def __init__(self, cmd):
        """ Create empty invocation set for command cmd. We will enforce that all invocations
        begin with cmd or the program will exit with an error. In file mode cmd is the command
        of the first invocation, in interactive mode it is the first command passed """
        self.cmd = cmd          #root command, present in all invocations
        self.invocations = {}   #collection of invocation arg permutations, indexed by their hashes
        self.responses = {}     #collection of output responses, indexed by their hashes
        self.call_map = {}      #mapping of what invocations yield what outputs (1-to-1 or many-to-1)

    def add_invocation(self, invocation):
        """ Add invocation to the set, including output and mapping.
        invocation should be a list in the same format as argv provides including the command itself
         """
        if invocation[0] != self.cmd:
            log.error("Invocation %s does not match command '%s'", invocation, self.cmd)
            raise ValueError

        #log.debug("Invoking %s", str(invocation))
        invocation_hash = hashlib.md5(str(invocation)).hexdigest()
        #log.debug("Invocation hash is %s", invocation_hash)
        output = get_response(invocation)
        output_hash = hashlib.md5(output).hexdigest()
        #log.debug("Output hash was %s", output_hash)

        if (output_hash not in self.responses) and (invocation_hash in self.invocations):
            log.warn("New response for equavalent invocation: %s. Does command print time?", \
                     invocation)

        if output_hash not in self.responses:       #if output is new add it
            self.responses[output_hash] = output
            log.debug("Invocation %s: adding new output (hash = %s)", invocation, output_hash)

        if invocation_hash not in self.invocations:         #if input is new add to invocations
            self.invocations[invocation_hash] = invocation
            log.debug("Invocation %s: adding new input hash: %s", invocation, invocation_hash)

        self.call_map[invocation_hash] = output_hash    # unconditionally add or update the map
        log.debug("Invocation %s: setting map: (%s : %s)\n", invocation, invocation_hash, \
                  self.call_map[invocation_hash])

        #log.debug("Output was:\n%s", output)

    def summarize(self):
        """ Get stats and printouts for debugging """
        log.debug("\n%d invocations mapped to %d outputs via %d map entries\n\n", \
                  len(self.invocations), len(self.responses), len(self.call_map))
        log.debug("Invocations:\n%s", str(self.invocations))
        log.debug("Mapping:\n%s", str(self.call_map))
        #log.debug("Outputs:\n%s", str(self.responses))

    def serialize(self):
        """ Generate the code text for all invocations to be written into the output file """
        vocab_string = "CALL_MAP = %s\n\nOUTPUTS = %s" %(str(self.call_map), str(self.responses))
        return vocab_string


def get_response(arg_list):
    """ Just runs a subprocess and returns the output """
    proc = subprocess.Popen(arg_list, stdout=subprocess.PIPE)
    proc_response = proc.communicate()
    return proc_response[0]


def write_mock_cmd(cmd, output):
    """ writes a file named cmd with a constant string of the output """

    output_file = cmd + '.gpy' # .gpy is for 'generated python #TODO drop the extension

    shebang = "#!/usr/bin/python\n"
    date = time.strftime("%d/%m/%Y")
    caller = os.getlogin() + '@' + socket.gethostname()
    full_invocation = str(sys.argv[1:])
    argument_list = str(sys.argv[2:])

    doc_string = '"""This module was generated by mockcmd.py version ' + __version__ + \
    '\non ' + date + ' called by ' + caller + '\nwith the following invocation:\n' + \
    full_invocation + '\n"""\n'

    import_string = "\nimport sys\n\n"

    canned_string = "CANNED_OUTPUT  = '''" + output + "'''\n\n"

    main_string = '''def main(argv):\n\t"""Main Module"""\n\n''' \
                  '\tif argv[1:] == ' + argument_list + ':\n' \
                  '\t\tprint CANNED_OUTPUT,\n' \
                  '\telse:\n' \
                  '\t\tprint "Unsupported argument"\n' \
                  '\t\traise ValueError\n\n'

    exec_string = '''if __name__ == "__main__":\n\tsys.exit(main(sys.argv))'''

    try:
        log.debug("Writing content to %s", output_file)
        fp = open(output_file, 'w', 0)
        fp.write(shebang)
        fp.write(doc_string)
        fp.write(import_string)
        fp.write(canned_string)
        fp.write(main_string)
        fp.write(exec_string)
        fp.close()

    except IOError:
        log.exception("write failure")
        sys.exit(1)

    #set file executable
    chmod_args = ('chmod a+x ' + output_file).split()
    subprocess.Popen(chmod_args, stdout=subprocess.PIPE)


def write_serialization(vocab):
    """ Quick test of serialization """
    with open('test_serial.py', 'w', 0) as fp:
        fp.write("#Simple test of vocabulary serialization routine\n\n")
        fp.write(vocab.serialize())


def main(argv):
    """ Main module. """
    #(options, args) = handle_args()

    log.basicConfig(format="[%(levelname)s]: %(message)s", level=log.DEBUG)

    vocab = InvocationSet(argv[1])    #initiate the empty vocabulary for command
    vocab.add_invocation(argv[1:])
    vocab.add_invocation(['ls', '-al'])
    vocab.add_invocation(['ls', '-a', '-l'])
    vocab.add_invocation(['ls', '-alh'])
    #vocab.add_invocation(['echo', '"Some text"'])  #test to bomb
    vocab.summarize()
    write_serialization(vocab)
    #print vocab.serialze()


    passed_options = argv[1:]
    log.info("Options passed were: %s", passed_options)
    response = get_response(passed_options)
    log.info("Response was:\n%s", response)
    write_mock_cmd(argv[1], response)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
