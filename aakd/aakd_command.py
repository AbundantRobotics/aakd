#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK

import aakd
from aakd import nice_name

import argcomplete
import argparse
import yaml
import sys


# Helper functions

def drives(args):
    """ Return a list of (name, ip) of drives to act on. """
    ips = args.ip
    names = args.name
    drives_file = args.drives_file
    groups = args.groups
    if ips:
        return [("", i) for i in ips]
    else:
        if not drives_file:
            raise Exception("Please provide and drive file")
        with open(drives_file) as f:
            yy = yaml.load(f, Loader=yaml.Loader)
            drives = []
            if names:
                available_names = yy.keys()
                for n in names:
                    if n in available_names:
                        drives.append((n, yy[n]['ip']))
                    else:
                        raise Exception("Name {} is not in the drive file".format(n))
            else:
                for (name, p) in yy.items():
                    drive_groups = p.get("groups", [])
                    keep = True
                    for g in groups:
                        if g not in drive_groups:
                            keep = False
                    if keep:
                        drives.append((name, p['ip']))

            return drives


def akd_filename(name, ip, args):
    if not args.akd_file:
        filename = name + ".akd"
    else:
        filename = args.akd_file
    return filename


def deep_update_dict(d1, d2):
    for k, v in d2.items():
        if k in d1 and isinstance(d1[k], dict) and isinstance(v, dict):
            deep_update_dict(d1[k], v)
        else:
            d1[k] = v


def load_param_files(args):
    params = {}
    for param_file in args.params_file:
        with open(param_file) as f:
            new_params = yaml.load(f, Loader=yaml.Loader)
            if not set(new_params.keys()).issubset(set(('drives', 'groups'))):
                raise Exception("Paramter file top level keys should be drives or group, see " + param_file)
            deep_update_dict(params, new_params)
    return params



def create_AKD(ip, args):
    trace = args.trace

    lip = ip.split(':')
    if len(lip) == 1:
        return aakd.AKD(ip, trace=trace)
    elif len(lip) == 2:
        return aakd.AKD(lip[0], port=lip[1], trace=trace)
    else:
        raise Exception("Ip '{}' is invalid".format(ip))


def parallel_create_AKD(function, function_extra_args, args, long_running=False):
    stop_var = False

    def stop():
        nonlocal stop_var
        return stop_var

    def thread_fun(name, ip, function_extra_args, args):
        nonlocal stop, long_running
        a = create_AKD(ip, args)
        if long_running:
            function(a, name, ip, stop, *function_extra_args)
        else:
            function(a, name, ip, *function_extra_args)

    import concurrent.futures as futures
    dd = drives(args)
    workers = args.threads if args.threads else len(dd) + 1
    with futures.ThreadPoolExecutor(max_workers=workers) as pool:
        fs = {}
        for (name, ip) in dd:
            nname = nice_name(name, ip)
            f = pool.submit(thread_fun, name, ip, function_extra_args, args)
            fs[f] = nname
        try:
            for f in futures.as_completed(fs.keys()):
                nname = fs[f]
                try:
                    f.result()
                except Exception as e:
                    print(nname, "<Error> ", str(e), file=sys.stderr)
                    if args.stop_on_error and not stop_var:
                        stop_var = True
                        for f in fs.keys():
                            f.cancel()
        except KeyboardInterrupt:
            if not stop_var:
                stop_var = True
                for f in fs.keys():
                    f.cancel()



def list_params(drive_name, args):
    """ Return a list of the parameters for drive_name according to drives_file and params_file"""
    paramtree = load_param_files(args)

    with open(args.drives_file) as f:
        yy = yaml.load(f, Loader=yaml.Loader)
        gs = yy[drive_name]["groups"]

    drive_params = {'DRV.NAME': drive_name}

    # do groups first
    def apply_group_parameters(subtree):
        for p, v in subtree.get("parameters", {}).items():
            drive_params[p] = v
        for (group, subsubtree) in subtree.items():
            if group in gs:
                apply_group_parameters(subsubtree)
    apply_group_parameters(paramtree.get("groups", {}))

    # do specific to the drive
    for p, v in paramtree.get("drives", {}).get(drive_name, {}).items():
        drive_params[p] = v

    return drive_params


def list_params_from_akdfiles(name, ip, args):
    import re
    with open(akd_filename(name, ip, args)) as f:
        param_dict = {}
        for l in f:
            l = l.rstrip('\r\n')
            if l and l[0] != '#':
                g = re.match("^([^ ]+) ([^ \n]+).*", l)
                if not g:
                    raise Exception('Unexpected line in akd file: ' + repr(l))
                param_dict[g.group(1)] = g.group(2)
        return param_dict


# Subcommands function


def akd_cmd(args):
    for (name, ip) in drives(args):
        try:
            a = create_AKD(ip, args)
            print(nice_name(name, ip), ": ", a.commandS(' '.join(args.cmd)))
        except Exception as e:
            print(nice_name(name, ip), " Error: ", str(e), file=sys.stderr)


def akd_info(args):
    for (name, ip) in drives(args):
        try:
            a = create_AKD(ip, args)
            print(nice_name(name, ip), ": ")
            print(a.drv_infos())
        except Exception as e:
            print(nice_name(name, ip), " Error: ", str(e), file=sys.stderr)


def restore_params(args):
    def restore(a, name, ip):
        nonlocal args
        filename = akd_filename(name, ip, args)
        a.load_params(filename, flash_afterward=True, factory_reset=args.factory, trust_drv_nvcheck=not args.force)
    parallel_create_AKD(restore, [], args)


def save_params(args):
    def save(a, name, ip):
        nonlocal args
        filename = akd_filename(name, ip, args)
        print("Saving drive " + nice_name(name, ip) + " to " + str(filename))
        a.flash_params()
        a.save_params(filename, diffonly=not args.full)
    parallel_create_AKD(save, [], args)


def record(args):
    from datetime import datetime
    filename = datetime.now().isoformat(timespec='seconds') + args.filename + '_'
    frequency = args.frequency

    if (16000 % frequency != 0):
        print("Error: Frequency needs to be 16kHz/2^n.")
        exit(-1)

    files = []
    try:
        akds = [create_AKD(ip, args) for (name, ip) in drives(args)]
        files = [
            open(filename + a.name +
                 "_" + str(frequency) + "hz.csv", mode='w')
            for a in akds
        ]
        to_record = [args.fields.split(',')] * len(akds)
        print(to_record)
        aakd.record(akds, files, frequency, to_record)
    finally:
        for f in files:
            f.close()

def monitor_faults(args):
    def rec(a, name, ip, stop):
        nonlocal args
        from datetime import datetime
        while not stop():
            print(nice_name(name, ip), "monitoring started")
            filename = datetime.now().isoformat(timespec='seconds') + args.filename + '_'
            data = aakd.record_on_fault(a, args.frequency, args.duration, args.fields.split(','), stop=stop)
            if not data:
                print(nice_name(name, ip), " Interrupted monitoring")
                return
            faults = a.faults_short()
            with open(filename + name + "_" + str(args.frequency) + "_" + faults, mode='w') as f:
                print(a.rec_header(), file=f)
                for l in data:
                    print(','.join(str(v) for v in l), file=f)
            print(nice_name(name, ip), " recorded ", faults)
    parallel_create_AKD(rec, [], args, long_running=True)



def home_here(args):
    for (name, ip) in drives(args):
        try:
            a = create_AKD(ip, args)
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
            a = create_AKD(ip, args)
            with open(args.script_file) as s:
                for c in s:
                    if c[0] == ' ':  # we do not print the ouput
                        a.commandS(c.rstrip('\r\n').lstrip(' '))
                    else:
                        print(a.commandS(c.rstrip('\r\n')), end=args.separator)
        except Exception as e:
            print(nice_name(name, ip), " Error: ", str(e), file=sys.stderr)
    print()


def list_parameters(args):
    drives_params = {'drives': {}}
    for (name, ip) in drives(args):
        drives_params['drives'][name] = list_params(name, args)
    print(yaml.dump(drives_params, default_flow_style=False))


def check_parameters(args):
    different_parameters = False

    def check(a, name, ip):
        nonlocal different_parameters
        nname = nice_name(name, ip)
        for (p, v) in list_params(name, args).items():
            # TODO we do not know the types, this is a bit messy and fragile
            try:
                dv = a.commandI(p)
            except Exception:
                try:
                    dv = a.commandF(p)
                except Exception:
                    dv = a.commandS(p)
            if isinstance(dv, str):
                if dv != v:
                    different_parameters = True
                    print(nname, p, "is ", dv, " expected ", v)
            elif abs(dv - v) >= 0.003:  # storage of float seems 0.003 accurate
                different_parameters = True
                print(nname, p, "is ", dv, " expected ", v)

    parallel_create_AKD(check, [], args)
    return different_parameters


def apply_parameters(args):

    def apply(a, name, ip):
        nonlocal args
        if args.factory:
            print("Factory reset for ", nice_name(name, ip))
            a.factory_params()
            a.cset("drv.name", name)
        print("Apply parameters for ", nice_name(name, ip))
        a.cset("drv.name", name)
        for (p, v) in list_params(name, args).items():
            a.cset(p, v)

    parallel_create_AKD(apply, [], args)


def compare_parameters(args):
    def compare(a, name, ip):
        nonlocal args
        diff_dict = {'new': {}, 'missing': {}, 'changed': {}}
        params_akdfile = list_params_from_akdfiles(name, ip, args)
        params_paramfile = list_params(name, args)
        unchecked_ones = set(params_akdfile.keys())
        for (p, v) in params_paramfile.items():
            if p not in params_akdfile:
                diff_dict['new'][p] = v
            else:
                unchecked_ones.remove(p)
                if isinstance(v, str):
                    if v != params_akdfile[p]:
                        diff_dict['changed'][p] = {'new': v, 'old': params_akdfile[p]}
                else:
                    if abs(v - float(params_akdfile[p])) > 0.003:
                        diff_dict['changed'][p] = {'new': v, 'old': params_akdfile[p]}
        for p in unchecked_ones:
            diff_dict['missing'][p] = (params_akdfile[p])

        if args.onlynew:
            print(yaml.dump({name: diff_dict['new']}, default_flow_style=False))
        elif args.onlymissing:
            print(yaml.dump({name: diff_dict['missing']}, default_flow_style=False))
        elif args.onlychanged:
            print(yaml.dump({name: diff_dict['changed']}, default_flow_style=False))
        else:
            print(yaml.dump({name: diff_dict}, default_flow_style=False))

    parallel_create_AKD(compare, [], args)


# Completion functions

def completion_names(prefix, parsed_args, **kwargs):
    if parsed_args.drives_file:
        with open(parsed_args.drives_file) as f:
            yy = yaml.load(f, Loader=yaml.Loader)
            return set(yy.keys())
    return []


def completion_groups(prefix, parsed_args, **kwargs):
    if parsed_args.drives_file:
        with open(parsed_args.drives_file) as f:
            yy = yaml.load(f, Loader=yaml.Loader)
            return set(g for (n, p) in yy.items() for g in p.get("groups", []))
    return []


def completion_cmd(prefix, parsed_args, **kwargs):
    if parsed_args.cmd and parsed_args.cmd[0] in aakd.akd_command_list:
        (t, h) = aakd.akd_command_list[parsed_args.cmd[0]]
        argcomplete.warn(h + ' (' + t + ')')
        return []
    return (key for key in aakd.akd_command_list.keys() if key.startswith(prefix))



def main():
    # Parser definition

    parser = argparse.ArgumentParser(description="Run a command on an AKD drive or a list of them.")
    parser.add_argument('--drives_file', '-d', type=str,
                        help="A yaml file with drive descriptions with field 'ip'")
    parser.add_argument('--trace', action='store_true', help='Trace all commands and drive answers, heavy debug')
    parser.add_argument('--threads', '-j', type=int, default=0, help="Limit the number of parallel workers. Default is 0 and it means as many as drives. 1 will execute each drives sequentially.")
    parser.add_argument('--stop_on_error', action='store_true', help='If running on multiple drives, try to stop all when one fails')
    parser.add_argument('--params_file', '-p', type=str, action='append', default=[], help="Parameter yaml files")


    drive_selection = parser.add_mutually_exclusive_group()
    drive_selection.add_argument('--ip', type=str, action='append', default=[], help="Drive IP/hostname")
    ng = drive_selection.add_argument('--name', '-n', type=str, action='append', default=[], help="Drive name according to the drive file")
    ng.completer = completion_names
    pg = drive_selection.add_argument('--groups', '-g', type=str, action='append', default=[],
                                      help="A list of groups the drive need to match, like \"-g arm akdn\"")
    pg.completer = completion_groups

    subparsers = parser.add_subparsers()

    # `cmd` subcommand

    cmd_parser = subparsers.add_parser('cmd')
    cmd_arg = cmd_parser.add_argument('cmd', type=str, nargs='+',
                                      help="Command to give to the drives. `drv.name` or `drv.en 0`.")
    cmd_arg.completer = completion_cmd
    cmd_parser.set_defaults(func=akd_cmd)

    # `info` subcommand

    info_parser = subparsers.add_parser('info', help="Generic informations about drive and motor")
    info_parser.set_defaults(func=akd_info)

    # `restore` subcommand

    restore_parser = subparsers.add_parser(
        'restore',
        description="Restore a drive parameters from a file (20sec per drive).")
    restore_parser.add_argument('--akd_file', '-a', type=str,
                                help="Filename of the drive parameters,"
                                " default to drive internal name.")
    restore_parser.add_argument('--factory', action="store_true",
                                help="Factory reset before writing the parameters")
    restore_parser.add_argument('--force', action="store_true",
                                help="Force restoring even when drv.nvcheck matches")
    restore_parser.set_defaults(func=restore_params)

    # `save` subcommand

    save_parser = subparsers.add_parser(
        'save',
        description="save a drive parameters to flash and to file.")
    save_parser.add_argument('--akd_file', '-a', type=str,
                             help="Filename of the drive parameters, default to drive internal name.")
    save_parser.add_argument('--full', action='store_true', help="Save every parameters even ones at default value.")
    save_parser.set_defaults(func=save_params)

    # `record` subcommand

    record_parser = subparsers.add_parser(
        'record',
        description='Record an akd velocity profile, stop with Ctrl+c')
    record_parser.add_argument('--fields', help='Fields to record', default="il.fb,pl.cmd,pl.err,vl.cmd,vl.fb,il.mi2t")
    record_parser.add_argument('--frequency', type=int, help='Frequency [Hz]', default=1000)
    record_parser.add_argument('--filename', help='Filename postfix (annotation)', default="")
    record_parser.set_defaults(func=record)

    # `monitor_faults` subcommand

    monitor_parser = subparsers.add_parser(
        'monitor_faults',
        description='Record an akd velocity profile, stop with Ctrl+c')
    monitor_parser.add_argument('--fields', help='Fields to record', default="il.fb,pl.cmd,pl.err,vl.cmd,vl.fb,il.mi2t")
    monitor_parser.add_argument('--frequency', type=int, help='Frequency [Hz]', default=1000)
    monitor_parser.add_argument('--duration', type=float, help='Record duration [s]', default=5)
    monitor_parser.add_argument('--filename', help='Filename postfix (annotation)', default="")
    monitor_parser.set_defaults(func=monitor_faults)

    # `home_here subcommand

    home_parser = subparsers.add_parser(
        'home',
        description="Change fb1.offset to ensure current position (pl.fb) is 0.")
    home_parser.set_defaults(func=home_here)

    # `script` subcommand

    script_parser = subparsers.add_parser('script', description='Runs a script')
    script_parser.add_argument('script_file', help='Filename of the script')
    script_parser.add_argument('--separator', default='\n', help='Seperator between command outputs')
    script_parser.set_defaults(func=run_script)

    # `params` subparser

    params_parser = subparsers.add_parser('params', help="Parameter file management for selected drives")

    sub_params_parsers = params_parser.add_subparsers()

    params_list = sub_params_parsers.add_parser('list', help="List parameters set in the file")
    params_list.set_defaults(func=list_parameters)

    params_check = sub_params_parsers.add_parser('check', help="Show differences between drive and parameter file")
    params_check.set_defaults(func=check_parameters)

    params_apply = sub_params_parsers.add_parser('apply', help="Apply parameter file")
    params_apply.set_defaults(func=apply_parameters)
    params_apply.add_argument('--factory', action="store_true",
                              help="Factory reset before writing the parameters")

    params_compare = sub_params_parsers.add_parser('compare', help="Compare parameter file with the drive files")
    params_compare.add_argument('--akd_file', '-a', type=str,
                                help="Filename of the drive parameters,"
                                " default to drive internal name.")
    params_compare_option = params_compare.add_mutually_exclusive_group()
    params_compare_option.add_argument('--onlychanged', action="store_true", help="Print only parameters which would change")
    params_compare_option.add_argument('--onlynew', action="store_true", help="Print only parameters which are new")
    params_compare_option.add_argument('--onlymissing', action="store_true", help="Print only parameters which are missing")
    params_compare.set_defaults(func=compare_parameters)


    argcomplete.autocomplete(parser)
    args = parser.parse_args()
    if 'func' in args.__dict__:
        return args.func(args)
    else:
        return parser.print_usage()


if __name__ == "__main__":
    main()
