cmdmock
=======

Utility to facilitate mocking non-interactive commands  

## Overview
cmdmock is a tool to autogenerate a simple mocked version of a command.
You just run cmdmock and pass it the command and arguments (if any) to be passed to the command.
cmdmock then runs the command passed to it with the specified arguments, captures the output and
generates a Python script with the output as a hard-coded canned response.

## Example
Say you want to write some code that calls the command 'sensors' and does something with the output.
Let's say the machine you are developing on doesn't have sensors installed and for some reason you can't install it.
You can go to a machine that _does_ have sensors installed and run:

cmdmock sensors -u   (-u option shown to illustrate passing switches)

cmdmock then generates and saves an executable Python script called: sensors.

Now if you run ./sensors -u, it will spit out the same output that was captured by cmdmock.

Now you have a simple script that will parrot the output of a command and you can use it to mock the command.

## Limitations
cmdmock is just a draft. It has essentially zero features.
* only works on Linux
* only works with Python 2
* only supports a single output
* doesn't work with interactive programs
* only handles outputs with printable characters
