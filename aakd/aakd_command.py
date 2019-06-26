#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK

import aakd

import argcomplete
import argparse
import yaml
import sys


# Helper functions

def drives(args):
    """ Return a list of (name, ip) of drives to act on. """
    ip = args.ip
    drives_file = args.drives_file
    groups = args.groups
    if ip:
        return [("", i) for i in ip]
    else:
        with open(drives_file) as f:
            yy = yaml.load(f)
            drives = []
            for (name, p) in yy.items():
                drive_groups = p.get("groups", [])
                keep = True
                for g in groups:
                    if g not in drive_groups:
                        keep = False
                if keep:
                    drives.append((name, p['ip']))
            return drives


def nice_name(name, ip):
    return name + " (ip: " + ip + ")"


# Subcommands function

def akd_cmd(args):
    for (name, ip) in drives(args):
        try:
            a = akd_lib.AKD(ip)
            print(nice_name(name, ip), ": ", a.commandS(' '.join(args.cmd)))
        except Exception as e:
            print(nice_name(name, ip), " Error: ", str(e), file=sys.stderr)


def restore_params(args):
    for (name, ip) in drives(args):
        try:
            a = akd_lib.AKD(ip)
            if not args.akd_file:
                filename = a.name + ".akd"
            else:
                filename = args.akd_file
            print("Restoring drive", nice_name(name, ip), "from", str(filename))
            if args.factory:
                print("Factory reset")
                a.factory_params()
            print("Loading")
            a.load_params(filename)
            print("Flash")
            a.flash_params()
        except Exception as e:
            print(nice_name(name, ip), " Error: ", str(e), file=sys.stderr)


def save_params(args):
    for (name, ip) in drives(args):
        try:
            a = akd_lib.AKD(ip)
            if not args.akd_file:
                filename = a.name + ".akd"
            else:
                filename = args.akd_file
            print("Saving drive " + ip + " to " + str(filename))
            a.flash_params()
            a.save_params(filename)
        except Exception as e:
            print(nice_name(name, ip), " Error: ", str(e), file=sys.stderr)


def record(args):
    filename = args.filename + '_'
    frequency = args.frequency

    if (16000%frequency != 0):
        print("Error: Frequency needs to be 16kHz/2^n.")
        exit(-1)

    files = []
    try:
        akds = [akd_lib.AKD(ip) for (name, ip) in drives(args)]
        files = [
            open(filename + a.commandS("drv.name") +
                 "_" + str(frequency) + "hz.csv", mode='w')
            for a in akds
        ]
        to_record = [args.fields.split(',')] * len(akds)
        print(to_record)
        akd_lib.akd.record(akds, files, frequency, to_record)
    finally:
        for f in files:
            f.close()


def home_here(args):
    for (name, ip) in drives(args):
        try:
            a = akd_lib.AKD(ip)
            current_pos = a.commandF("pl.fb")
            (current_off, unit) = a.commandF("fb1.offset", unit=True)
            new_off = -(current_pos - current_off)
            a.cset("fb1.offset", new_off)
            new_off = a.commandF("fb1.offset")
            print(nice_name(name, ip), "Offset old: {1}[{0}]  new: {2}[{0}]".format(unit, current_off, new_off))
        except Exception as e:
            print(nice_name(name, ip), " Error: ", str(e), file=sys.stderr)

def run_script(args):
    for (name, ip) in drives(args):
        try:
            a = akd_lib.AKD(ip)
            with open(args.script_file) as s:
                for c in s:
                    if c[0] == ' ':  # we do not print the ouput
                        a.commandS(c.rstrip('\r\n').lstrip(' '))
                    else:
                        print(a.commandS(c.rstrip('\r\n')), end=args.separator)
        except Exception as e:
            print(nice_name(name, ip), " Error: ", str(e), file=sys.stderr)
    print()
# Completion functions


def completion_groups(prefix, parsed_args, **kwargs):
    if parsed_args.drives_file:
        with open(parsed_args.drives_file) as f:
            yy = yaml.load(f)
            return set(g for (n, p) in yy.items() for g in p.get("groups", []))
    return []


def completion_cmd(prefix, parsed_args, **kwargs):
    if parsed_args.cmd and parsed_args.cmd[0] in akd_command_list.akd_cmd_list:
        (t, h) = akd_command_list.akd_cmd_list[parsed_args.cmd[0]]
        argcomplete.warn(h + ' (' + t + ')')
        return []
    return (key for key in akd_lib.akd_command_list.keys() if key.startswith(prefix))


# Parser definition


parser = argparse.ArgumentParser(description="Run a command on an AKD drive or a list of them.")
parser.add_argument('--ip', type=str, action='append', default=[],  help="Drive IP/hostname to save")
parser.add_argument('--drives_file', '-d', type=str,
                    help="A yaml file with drive descriptions with field 'ip'")
pg = parser.add_argument('--groups', '-g', type=str, action='append', default=[],
                         help="A list of groups the drive need to match, like \"-g arm akdn\"")
pg.completer = completion_groups


subparsers = parser.add_subparsers()

# `cmd` subcommand

cmd_parser = subparsers.add_parser('cmd')
cmd_arg = cmd_parser.add_argument('cmd', type=str, nargs='+',
                                  help="Command to give to the drives. `drv.name` or `drv.en 0`.")
cmd_arg.completer = completion_cmd
cmd_parser.set_defaults(func=akd_cmd)


# `restore` subcommand

restore_parser = subparsers.add_parser(
    'restore',
    description="Restore a drive parameters from a file (20sec per drive).")
restore_parser.add_argument('--akd_file', '-a', type=str,
                            help="Filename of the drive parameters,"
                            " default to drive internal name.")
restore_parser.add_argument('--factory', action="store_true",
                            help="Factory reset before writing the parameters")
restore_parser.set_defaults(func=restore_params)


# `save` subcommand

save_parser = subparsers.add_parser(
    'save',
    description="save a drive parameters to flash and to file.")
save_parser.add_argument('--akd_file', '-a', type=str,
                            help="Filename of the drive parameters,"
                            " default to drive internal name.")
save_parser.set_defaults(func=save_params)


# `record` subcommand

record_parser = subparsers.add_parser(
    'record',
    description='Record an akd velocity profile, stop with Ctrl+c')
record_parser.add_argument('--fields', help='Fields to record', default="IL.FB,IL.CMD,VL.FB")
record_parser.add_argument('--frequency', type=int, help='Frequency [Hz]', default=1000)
record_parser.add_argument('--filename', help='Filename postfix (annotation)', default="")
record_parser.set_defaults(func=record)

# `home_here subcommand

home_parser = subparsers.add_parser(
        'home',
        description="Change fb1.offset to ensure current position (pl.fb) is 0.")
home_parser.set_defaults(func=home_here)


# `script` subcommand

script_parser = subparsers.add_parser(
    'script',
    description='Runs a script')
script_parser.add_argument('script_file', help='Filename of the script')
script_parser.add_argument('--seperator', default='\n', help='Seperator between command outputs')
script_parser.set_defaults(func=run_script)




argcomplete.autocomplete(parser)
args = parser.parse_args()
if 'func' in args.__dict__:
    args.func(args)

