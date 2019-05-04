import subprocess
import asyncio
import configparser
from pathlib import Path


def script_directory():
    return Path(__file__).parents[0]


def get_testdata(gen_cmd):
    proc = subprocess.Popen(gen_cmd, stdout=subprocess.PIPE, shell=True)
    stdout, stderr = proc.communicate()
    return stdout


async def run_and_save(prog_number, prog_cmd, input_test):
    out_filename = f"prog{prog_number}.out"
    with open(out_filename, "wb+") as out_file:
        proc = await asyncio.create_subprocess_shell(
            prog_cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=out_file,
            stderr=asyncio.subprocess.PIPE)
        proc.stdin.write(input_test)
        await proc.wait()
    return out_filename


async def save_outputs(numbered_prog_cmds, input_test):
    programs = [
        run_and_save(prog_number, prog_cmd, input_test)
        for prog_number, prog_cmd in numbered_prog_cmds
    ]
    return [await f for f in asyncio.as_completed(programs)]


def find_difference(checker_cmd, filenames):
    for i in range(1, len(filenames)):
        diff = subprocess.Popen([*checker_cmd, filenames[i - 1], filenames[i]],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                cwd=script_directory())
        diff.wait()
        if diff.returncode:
            return filenames[i - 1], filenames[i]


def run_test(gen_cmd, checker_cmd, numbered_prog_cmds, ignore_err=True):
    input = get_testdata(gen_cmd)
    out_filenames = asyncio.run(save_outputs(numbered_prog_cmds, input))
    diff = find_difference(checker_cmd, out_filenames)
    if diff:
        with open("test.in", "wb+") as test_file:
            test_file.write(input)
        raise AssertionError(f"Files {diff[0]} and {diff[1]} differ.")
    return True


if __name__ == "__main__":
    config = configparser.ConfigParser()
    config.read("config.ini")

    gen_cmd = config["GEN"]["command"]
    checker_cmd = [config["CHECKER"]["command"],
                   config["CHECKER"]["command_flags"]]

    prog_cmds = []
    index = 1
    while f"PROG{index}" in config:
        if "off" not in config[f"PROG{index}"]:
            prog_cmds.append((index, config[f"PROG{index}"]["command"]))
        index += 1
    if len(prog_cmds) < 2:
        raise FileNotFoundError("No enough programs to diff")

    # diff_errors = config["GENERAL"]["ignore_err"]

    tests_passed = 0
    while run_test(gen_cmd, checker_cmd, prog_cmds):
        tests_passed += 1
        print(tests_passed)
