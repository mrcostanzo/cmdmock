#!/usr/bin/env python
# -*- coding: utf-8 -*-
# M Costanzo

""" cmdmock is a simple utility to create a mock version of a command with a specific
argument string (or no arguments). It runs the command, takes the output and hard-codes that
output as a canned response which can then be called and regurgitated. It then tries to set
the file to be executable so a module under test or development can call it transparently
"""

import sys
import os
import subprocess
import socket
import datetime
import logging as log
import argparse
import hashlib

__version__ = '0.05'

# TODO get program name with module
# TODO make Python3 compatible
# TODO get rid of sub-second resolution in timestamps
# TODO write how long it took to build vocabulary?
# TODO consider supporting options before the command to change behavior
# TODO optionally enforce exact argument string or return an error (-s --strict?)
# TODO optionally compress output into a blob in case it is catting a big file for example
# TODO explicitly add to path for this shell instance?
# TODO should multiple sequential invocations add to the output? Probably not, just have a training file for that


def handle_args():
    """Parse out arguments"""
    parser = argparse.ArgumentParser(description="Autogenerates a script to mock the output of a command",
                                     epilog="Example: cmdmock sensors -u")
    #parser.add_argument('-i', '--interactive', action='store_true',
    #                  help='Interactively enter a series of invocations')
    parser.add_argument('-f', '--file', dest='training_file',
                        help='Optionally specify a training file with line-separated invocations')
    parser.add_argument('-v', '--verbose', action='store_true', dest='verbose', default=False,
                        help='Print informative messages')
    #parser.add_argument('invocation', help='command to be run with options')
    args = parser.parse_args()
    return args


class InvocationSet(object):
    """ Container to hold, add, and serialize invocations and responses for building a vocabulary.
    Inputs are stored as a list of arguments, the same way argv does it, they are also hashed using
    md5 for searching and indexing. Command responses are stored as big strings along with their
    hashes for easier indexing and comparison. """

    def __init__(self, cmd):
        """ Create empty invocation set for command cmd. We will enforce that all invocations
        begin with cmd or the program will exit with an error. In file mode cmd is the command
        of the first invocation, in interactive mode it is the first command passed """
        self.cmd = cmd          # root command
        self.invocations = {}   # collection of invocation arg permutations, indexed by their hashes
        self.responses = {}     # collection of output responses, indexed by their hashes
        self.call_map = {}      # mapping of what invocations yield what outputs (1-to-1 or many-to-1)

    def add_invocation(self, invocation):
        """ Add invocation to the set, including output and mapping.
        invocation should be a list in the same format as argv provides including the command itself
         """
        if not invocation[0].endswith(self.cmd):
            log.error("Invocation %s does not match command '%s'", invocation, self.cmd)
            raise ValueError

        if len(invocation) > 1:
            ops_and_args = invocation[1:]                   #strip off command
        else:
            ops_and_args = ''                               #hash a null string for command without options
        #log.debug("Invoking %s", str(invocation))
        invocation_hash = hashlib.md5(str(ops_and_args)).hexdigest()  #don't hash cmd itself because paths
        #log.debug("Invocation hash is %s", invocation_hash)
        output = get_response(invocation)
        output_hash = hashlib.md5(output).hexdigest()
        #log.debug("Output hash was %s", output_hash)

        if (output_hash not in self.responses) and (invocation_hash in self.invocations):
            log.warn("New response for equivalent invocation: %s. Does command print time?",
                     invocation)

        if output_hash not in self.responses:       # if output is new add it
            self.responses[output_hash] = output
            log.debug("Invocation %s: adding new output (hash = %s)", invocation[1:], output_hash)

        if invocation_hash not in self.invocations:         # if input is new add to invocations
            self.invocations[invocation_hash] = ops_and_args
            log.debug("Invocation %s: adding new input hash: %s", ops_and_args, invocation_hash)

        self.call_map[invocation_hash] = output_hash    # unconditionally add or update the map
        log.debug("Invocation %s: setting map: (%s : %s)\n", ops_and_args, invocation_hash,
                  self.call_map[invocation_hash])

        #log.debug("Output was:\n%s", output)

    def summarize(self):
        """ Get stats and printouts for debugging """
        log.debug("\n%d invocations mapped to %d outputs via %d map entries\n\n",
                  len(self.invocations), len(self.responses), len(self.call_map))
        log.debug("Invocations:\n%s", str(self.invocations))
        log.debug("Mapping:\n%s", str(self.call_map))
        #log.debug("Outputs:\n%s", str(self.responses))

    def serialize(self):
        """ Generate the code text for all invocations to be written into the output file """
        vocab_string = "CALL_MAP = %s\n\nOUTPUTS = %s\n" %(str(self.call_map), str(self.responses))
        return vocab_string


def get_response(arg_list):
    """ Just runs a subprocess and returns the output """
    proc = subprocess.Popen(arg_list, stdout=subprocess.PIPE)
    proc_response = proc.communicate()
    return proc_response[0]


def write_mock_cmd(vocab):
    """ writes a file named cmd with a constant string of the output """

    output_file = vocab.cmd + '.gpy'  # .gpy is for 'generated python #TODO drop the extension

    shebang = "#!/usr/bin/python\n"
    #date = time.strftime("%d/%m/%Y")
    date = str(datetime.datetime.now())
    try:
        caller = os.getlogin() + '@' + socket.gethostname()
    except OSError:
        caller = 'user@localhost'   # FIXME something better?
    full_invocation = str(sys.argv[1:])
    argument_list = str(sys.argv[2:])

    doc_string = '"""This module was generated by cmdmock.py version ' + __version__ + \
                 '\non ' + date + ' called by ' + caller + '\nwith the following invocation:\n' + \
                 full_invocation + '\n"""\n'

    import_string = "\nimport sys\nimport hashlib\n\n"
    
    vocab_string = vocab.serialize()
    
    main_string = '''\ndef main(argv):\n\t"""Main Module"""\n\n''' \
                  '\tif len(argv) > 1:\n' \
                  '\t\tinvocation_hash = hashlib.md5(str(argv[1:])).hexdigest()\n' \
                  '\telse:\n' \
                  '\t\tinvocation_hash = hashlib.md5("").hexdigest()\n' \
                  '\tif invocation_hash in CALL_MAP:\n' \
                  '\t\tprint OUTPUTS[CALL_MAP[invocation_hash]]\n' \
                  '\telse:\n' \
                  '\t\tprint "Unsupported argument, re-run cmdmock with this argument included"\n' \
                  '\t\traise ValueError\n\n'

    exec_string = '''if __name__ == "__main__":\n\tsys.exit(main(sys.argv))'''

    try:
        log.debug("Writing content to %s", output_file)
        fp = open(output_file, 'w', 0)
        fp.write(shebang)
        fp.write(doc_string)
        fp.write(import_string)
        fp.write(vocab_string)
        fp.write(main_string)
        fp.write(exec_string)
        fp.close()

    except IOError:
        log.exception("write failure")
        sys.exit(1)

    # set file executable
    chmod_args = ('chmod a+x ' + output_file).split()
    subprocess.Popen(chmod_args, stdout=subprocess.PIPE)


def write_serialization(vocab):
    """ Quick test of serialization """
    with open('test_serial.py', 'w', 0) as fp:
        fp.write("#Simple test of vocabulary serialization routine\n\n")
        fp.write(vocab.serialize())


def main(argv):
    """ Main module. """
    args = handle_args()

    if args.verbose:
        log.basicConfig(format="[%(levelname)s]: %(message)s", level=log.DEBUG)
        log.info("Logging level: DEBUG")
        log.info("Script Started %s", str(datetime.datetime.now()))
    else:
        log.basicConfig(format="[%(levelname)s]: %(message)s")

    if args.training_file:
        with open(args.training_file, 'r', 0) as training_file:
            first_line = training_file.readline().strip('\n')
            log.debug("First read %s", first_line)
            vocab = InvocationSet(first_line)

            for line in training_file:
                log.debug("loop read: %s", line)
                vocab.add_invocation(line.split())
    else:
        vocab = InvocationSet(args.invocation)    # initiate the empty vocabulary for command
        single_invocation = list()
        single_invocation.append(args.invocation)
        vocab.add_invocation(single_invocation)
    #vocab.add_invocation(['ls'])
    #vocab.add_invocation(['ls', '-al'])
    #vocab.add_invocation(['ls', '-la'])
    #vocab.add_invocation(['ls', '-a', '-l'])
    #vocab.add_invocation(['ls', '-alh'])
    #vocab.add_invocation(['echo', '"Some text"'])  #test error
    vocab.summarize()
    #write_serialization(vocab)
    
    write_mock_cmd(vocab)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
